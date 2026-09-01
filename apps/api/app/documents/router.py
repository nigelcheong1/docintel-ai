from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Chunk, Document
from app.documents.parse_quality import build_parse_quality_for_document
from app.db.session import get_db
from app.documents.intelligence import build_document_profile
from app.documents.schemas import ChunkRead, DocumentDetail, DocumentProfileRead, DocumentRead
from app.documents.service import (
    DocumentPersistenceError,
    DocumentReindexError,
    EmbeddingProviderFactory,
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


@router.post("", response_model=DocumentRead)
async def upload_document(
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    embedder_factory: Annotated[EmbeddingProviderFactory, Depends(get_embedding_provider_factory)],
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
        return document_read(index_stored_upload(db, stored, embedder_factory if stored.kind == "pdf" else None))
    except DocumentPersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("", response_model=list[DocumentRead])
def documents(db: Annotated[Session, Depends(get_db)]) -> list[DocumentRead]:
    return [document_read(document) for document in list_documents(db)]


@router.get("/{document_id}", response_model=DocumentDetail)
def document_detail(document_id: str, db: Annotated[Session, Depends(get_db)]) -> DocumentDetail:
    document = get_document_or_404(db, document_id)
    return document_detail_read(document)


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
def delete_document_route(document_id: str, db: Annotated[Session, Depends(get_db)]) -> Response:
    try:
        delete_document(db, document_id)
    except DocumentPersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return Response(status_code=204)


@router.post("/{document_id}/reindex", response_model=DocumentRead)
def reindex_document_route(
    document_id: str,
    db: Annotated[Session, Depends(get_db)],
    embedder_factory: Annotated[EmbeddingProviderFactory, Depends(get_embedding_provider_factory)],
) -> DocumentRead:
    try:
        return document_read(reindex_document(db, document_id, embedder_factory))
    except DocumentReindexError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except DocumentPersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
