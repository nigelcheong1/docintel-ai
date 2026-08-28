from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import Chunk, ChunkEmbedding, Document, DocumentStatus, Page
from app.documents.chunker import chunk_pages
from app.documents.parser import DocumentParseError, parse_pdf
from app.documents.storage import StoredUpload
from app.retrieval.embeddings import EmbeddingProvider


class DocumentPersistenceError(RuntimeError):
    pass


class DocumentReindexError(ValueError):
    pass


EmbeddingProviderFactory = Callable[[], EmbeddingProvider]


@dataclass(frozen=True)
class PersistedDocument:
    model: Document
    document_id: str


def _persist_new_document(db: Session, stored: StoredUpload) -> PersistedDocument:
    document = Document(
        filename=stored.original_filename,
        stored_filename=stored.stored_filename,
        mime_type=stored.mime_type,
        file_path=str(stored.file_path),
        status=DocumentStatus.PROCESSING,
    )
    try:
        db.add(document)
        db.flush()
        document_id = document.id
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        stored.file_path.unlink(missing_ok=True)
        raise DocumentPersistenceError("Could not persist the uploaded document.") from exc
    return PersistedDocument(model=document, document_id=document_id)


def _failure_message(exc: Exception) -> str:
    if isinstance(exc, DocumentParseError):
        return str(exc)
    if isinstance(exc, SQLAlchemyError):
        return "Indexing failed because extracted content could not be stored in the database."
    detail = str(exc).strip() or exc.__class__.__name__
    return f"Indexing failed: {detail[:500]}"


def _persist_failed_status(db: Session, document_id: str, error_message: str) -> Document:
    try:
        db.rollback()
        document = db.get(Document, document_id)
        if document is None:
            raise DocumentPersistenceError("The document record disappeared during indexing.")
        document.status = DocumentStatus.FAILED
        document.error_message = error_message
        db.commit()
        return document
    except SQLAlchemyError as exc:
        db.rollback()
        raise DocumentPersistenceError("Could not persist the document indexing failure.") from exc


def _add_pdf_index_records(
    db: Session,
    document: Document,
    embedder_factory: EmbeddingProviderFactory,
) -> None:
    parsed_pages = parse_pdf(Path(document.file_path))
    embedder = embedder_factory()
    page_models: dict[int, Page] = {}
    for parsed_page in parsed_pages:
        page = Page(
            document_id=document.id,
            page_number=parsed_page.page_number,
            text=parsed_page.text,
            width=parsed_page.width,
            height=parsed_page.height,
        )
        db.add(page)
        db.flush()
        page_models[parsed_page.page_number] = page

    text_chunks = chunk_pages(parsed_pages)
    vectors = embedder.embed_texts([chunk.text for chunk in text_chunks])
    for text_chunk, vector in zip(text_chunks, vectors, strict=True):
        chunk = Chunk(
            document_id=document.id,
            page_id=page_models[text_chunk.page_number].id,
            chunk_index=text_chunk.chunk_index,
            text=text_chunk.text,
            token_estimate=text_chunk.token_estimate,
            layout=text_chunk.layout,
        )
        db.add(chunk)
        db.flush()
        db.add(ChunkEmbedding(chunk_id=chunk.id, model_name=embedder.model_name, embedding=vector))


def index_stored_upload(
    db: Session,
    stored: StoredUpload,
    embedder_factory: EmbeddingProviderFactory | None,
) -> Document:
    persisted_document = _persist_new_document(db, stored)
    document = persisted_document.model
    document_id = persisted_document.document_id

    if stored.kind == "image":
        try:
            document.status = DocumentStatus.DEFERRED_OCR
            document.error_message = "OCR is not enabled in the local-first MVP."
            db.commit()
            return document
        except SQLAlchemyError as exc:
            return _persist_failed_status(db, document_id, "Could not persist the deferred OCR status.")

    try:
        if embedder_factory is None:
            raise RuntimeError("No embedding provider is configured for PDF indexing.")
        _add_pdf_index_records(db, document, embedder_factory)
        document.status = DocumentStatus.INDEXED
        db.commit()
        return document
    except Exception as exc:
        return _persist_failed_status(db, document_id, _failure_message(exc))


def list_documents(db: Session) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


def get_document_or_404(db: Session, document_id: str) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Document not found.")
    return document


def delete_document(db: Session, document_id: str) -> None:
    document = get_document_or_404(db, document_id)
    file_path = Path(document.file_path)
    deleting_file_path: Path | None = None
    if file_path.exists():
        deleting_file_path = file_path.with_name(f"{file_path.name}.{uuid4().hex}.deleting")
        try:
            file_path.replace(deleting_file_path)
        except OSError as exc:
            raise DocumentPersistenceError("Could not stage the document file for deletion.") from exc

    try:
        db.delete(document)
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        if deleting_file_path is not None:
            try:
                deleting_file_path.replace(file_path)
            except OSError as restore_exc:
                raise DocumentPersistenceError("Could not restore the document file after database failure.") from restore_exc
        raise DocumentPersistenceError("Could not delete the document.") from exc

    if deleting_file_path is not None:
        try:
            deleting_file_path.unlink(missing_ok=True)
        except OSError:
            pass


def reindex_document(
    db: Session,
    document_id: str,
    embedder_factory: EmbeddingProviderFactory,
) -> Document:
    document = get_document_or_404(db, document_id)
    if Path(document.stored_filename).suffix.lower() != ".pdf":
        raise DocumentReindexError("Only PDF documents can be reindexed.")

    try:
        document.status = DocumentStatus.PROCESSING
        document.error_message = None
        for page in list(document.pages):
            db.delete(page)
        db.flush()
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise DocumentPersistenceError("Could not clear the document before reindexing.") from exc

    try:
        _add_pdf_index_records(db, document, embedder_factory)
        document.status = DocumentStatus.INDEXED
        db.commit()
        db.expire(document, ["pages", "chunks"])
        return document
    except Exception as exc:
        return _persist_failed_status(db, document_id, _failure_message(exc))
