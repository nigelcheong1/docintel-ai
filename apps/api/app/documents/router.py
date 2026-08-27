from functools import lru_cache
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Chunk
from app.db.session import get_db
from app.documents.schemas import ChunkRead, DocumentDetail, DocumentRead
from app.documents.service import (
    DocumentPersistenceError,
    EmbeddingProviderFactory,
    get_document_or_404,
    index_stored_upload,
    list_documents,
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
        return index_stored_upload(db, stored, embedder_factory if stored.kind == "pdf" else None)
    except DocumentPersistenceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("", response_model=list[DocumentRead])
def documents(db: Annotated[Session, Depends(get_db)]) -> list[DocumentRead]:
    return list_documents(db)


@router.get("/{document_id}", response_model=DocumentDetail)
def document_detail(document_id: str, db: Annotated[Session, Depends(get_db)]) -> DocumentDetail:
    document = get_document_or_404(db, document_id)
    return DocumentDetail(
        id=document.id,
        filename=document.filename,
        mime_type=document.mime_type,
        status=document.status.value,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
        page_count=len(document.pages),
        chunk_count=len(document.chunks),
    )


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
