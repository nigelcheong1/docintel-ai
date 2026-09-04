from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Chunk, Document
from app.documents.parse_quality import build_parse_quality_for_document
from app.db.session import get_db
from app.documents.intelligence import build_document_profile
from app.documents.ocr import TesseractOcrProvider
from app.documents.page_rendering import DocumentPageRenderError, render_document_page_image
from app.documents.schemas import ChunkRead, DocumentDetail, DocumentPageRead, DocumentProfileRead, DocumentRead
from app.documents.service import (
    DocumentPersistenceError,
    DocumentReindexError,
    EmbeddingProviderFactory,
    OcrProviderFactory,
    delete_document,
    get_document_or_404,
    index_stored_upload,
    list_documents,
    reindex_document,
)
from app.documents.storage import FileValidationError, UploadTooLargeError, save_upload_stream
from app.retrieval.embeddings import LocalEmbeddingProvider

router = APIRouter(prefix="/documents", tags=["documents"])


@lru_cache
def get_cached_embedding_provider(model_name: str, dimension: int) -> LocalEmbeddingProvider:
    return LocalEmbeddingProvider(model_name, dimension)


def get_embedding_provider(settings: Annotated[Settings, Depends(get_settings)]) -> LocalEmbeddingProvider:
    return get_cached_embedding_provider(settings.embedding_model_name, settings.embedding_dimension)


def get_embedding_provider_factory(
    settings: Annotated[Settings, Depends(get_settings)],
) -> EmbeddingProviderFactory:
    return lambda: get_cached_embedding_provider(settings.embedding_model_name, settings.embedding_dimension)


def get_ocr_provider_factory(settings: Annotated[Settings, Depends(get_settings)]) -> OcrProviderFactory:
    return lambda: TesseractOcrProvider(
        enabled=settings.ocr_enabled,
        tesseract_cmd=settings.tesseract_cmd,
        timeout_seconds=settings.ocr_page_timeout_seconds,
    )


def document_read(document: Document) -> DocumentRead:
    return DocumentRead(
        id=document.id,
        filename=document.filename,
        mime_type=document.mime_type,
        status=document.status.value,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
        parse_quality=build_parse_quality_for_document(document),
    )


def document_detail_read(document: Document) -> DocumentDetail:
    return DocumentDetail(
        id=document.id,
        filename=document.filename,
        mime_type=document.mime_type,
        status=document.status.value,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
        parse_quality=build_parse_quality_for_document(document),
        page_count=len(document.pages),
        chunk_count=len(document.chunks),
    )


def _text_preview(text: str, limit: int = 240) -> str:
    normalized = " ".join(text.split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 1].rstrip()}..."


def _page_text_density(page) -> float:
    area = float((page.width or 0) * (page.height or 0))
    if area <= 0:
        return 0.0
    return round((len(page.text) / area) * 1000, 3)


def _page_ocr_quality(page) -> str:
    if page.text_source == "native":
        return "native"
    if page.ocr_confidence is None:
        return "missing"
    if page.ocr_confidence >= 85:
        return "strong"
    if page.ocr_confidence >= 65:
        return "moderate"
    return "weak"


def _page_needs_review(page) -> bool:
    ocr_quality = _page_ocr_quality(page)
    return not page.text.strip() or len(page.chunks) == 0 or ocr_quality in {"weak", "missing"}


def document_page_read(document: Document) -> list[DocumentPageRead]:
    return [
        DocumentPageRead(
            document_id=document.id,
            page_number=page.page_number,
            image_url=f"/documents/{document.id}/pages/{page.page_number}/image",
            text_source=page.text_source,
            text_preview=_text_preview(page.text),
            character_count=len(page.text),
            chunk_count=len(page.chunks),
            token_estimate=sum(chunk.token_estimate for chunk in page.chunks),
            text_density=_page_text_density(page),
            ocr_quality=_page_ocr_quality(page),
            needs_review=_page_needs_review(page),
            ocr_engine=page.ocr_engine,
            ocr_confidence=page.ocr_confidence,
            ocr_duration_ms=page.ocr_duration_ms,
        )
        for page in sorted(document.pages, key=lambda item: item.page_number)
    ]


@router.post("", response_model=DocumentRead)
async def upload_document(
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    embedder_factory: Annotated[EmbeddingProviderFactory, Depends(get_embedding_provider_factory)],
    ocr_provider_factory: Annotated[OcrProviderFactory, Depends(get_ocr_provider_factory)],
) -> DocumentRead:
    try:
        stored = await save_upload_stream(
            file.filename or "document",
            file.content_type,
            file,
            settings.storage_dir,
            settings.max_upload_mb,
        )
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    except FileValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        return document_read(
            index_stored_upload(
                db,
                stored,
                embedder_factory,
                ocr_provider_factory=ocr_provider_factory,
                ocr_language=settings.ocr_language,
                ocr_dpi=settings.ocr_dpi,
                ocr_max_pages=settings.ocr_max_pages,
            )
        )
    except DocumentPersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("", response_model=list[DocumentRead])
def documents(db: Annotated[Session, Depends(get_db)]) -> list[DocumentRead]:
    return [document_read(document) for document in list_documents(db)]


@router.get("/{document_id}", response_model=DocumentDetail)
def document_detail(document_id: str, db: Annotated[Session, Depends(get_db)]) -> DocumentDetail:
    document = get_document_or_404(db, document_id)
    return document_detail_read(document)


@router.get("/{document_id}/pages", response_model=list[DocumentPageRead])
def document_pages(document_id: str, db: Annotated[Session, Depends(get_db)]) -> list[DocumentPageRead]:
    document = get_document_or_404(db, document_id)
    return document_page_read(document)


@router.get("/{document_id}/pages/{page_number}/image")
def document_page_image(
    document_id: str,
    page_number: int,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    document = get_document_or_404(db, document_id)
    try:
        rendered = render_document_page_image(document, page_number=page_number, storage_dir=settings.storage_dir)
    except DocumentPageRenderError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return Response(content=rendered.content, media_type=rendered.media_type)


@router.get("/{document_id}/profile", response_model=DocumentProfileRead)
def document_profile(document_id: str, db: Annotated[Session, Depends(get_db)]) -> DocumentProfileRead:
    document = get_document_or_404(db, document_id)
    return build_document_profile(document)


@router.get("/{document_id}/chunks", response_model=list[ChunkRead])
def document_chunks(document_id: str, db: Annotated[Session, Depends(get_db)]) -> list[ChunkRead]:
    document = get_document_or_404(db, document_id)
    chunks = sorted(document.chunks, key=lambda item: item.chunk_index)
    return [
        ChunkRead(
            id=chunk.id,
            document_id=chunk.document_id,
            page_number=chunk.page.page_number,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            token_estimate=chunk.token_estimate,
        )
        for chunk in chunks
        if isinstance(chunk, Chunk)
    ]


@router.delete("/{document_id}", status_code=204)
def delete_document_route(
    document_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> Response:
    try:
        delete_document(db, document_id, storage_dir=settings.storage_dir)
    except DocumentPersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/{document_id}/reindex", response_model=DocumentRead)
def reindex_document_route(
    document_id: str,
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    embedder_factory: Annotated[EmbeddingProviderFactory, Depends(get_embedding_provider_factory)],
    ocr_provider_factory: Annotated[OcrProviderFactory, Depends(get_ocr_provider_factory)],
) -> DocumentRead:
    try:
        return document_read(
            reindex_document(
                db,
                document_id,
                embedder_factory,
                storage_dir=settings.storage_dir,
                ocr_provider_factory=ocr_provider_factory,
                ocr_language=settings.ocr_language,
                ocr_dpi=settings.ocr_dpi,
                ocr_max_pages=settings.ocr_max_pages,
            )
        )
    except DocumentReindexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DocumentPersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
