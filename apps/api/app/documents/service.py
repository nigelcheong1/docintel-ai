from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import Chunk, ChunkEmbedding, Document, DocumentStatus, Page, utc_now
from app.documents.chunker import chunk_pages
from app.documents.extraction import ExtractedPage, extract_image_pages, extract_pdf_pages
from app.documents.ocr import OcrProvider
from app.documents.parser import DocumentParseError
from app.documents.storage import StoredUpload
from app.retrieval.embeddings import EmbeddingProvider


class DocumentPersistenceError(RuntimeError):
    pass


class DocumentReindexError(ValueError):
    pass


EmbeddingProviderFactory = Callable[[], EmbeddingProvider]
OcrProviderFactory = Callable[[], OcrProvider]
OCR_UNAVAILABLE_MESSAGE = (
    "Local OCR is not available. Install Tesseract OCR or configure DOCINTEL_TESSERACT_CMD, then retry OCR."
)


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


def _persist_deferred_ocr_status(db: Session, document: Document, document_id: str, error_message: str) -> Document:
    try:
        document.status = DocumentStatus.DEFERRED_OCR
        document.error_message = error_message
        db.commit()
        return document
    except SQLAlchemyError:
        return _persist_failed_status(db, document_id, "Could not persist the deferred OCR status.")


def _start_ocr_processing(db: Session, document: Document) -> None:
    document.status = DocumentStatus.OCR_PROCESSING
    document.error_message = None
    document.processing_started_at = utc_now()
    document.processing_completed_at = None
    document.processing_duration_ms = None
    db.commit()


def _complete_ocr_processing(document: Document) -> None:
    if document.processing_started_at is None:
        return
    document.processing_completed_at = utc_now()
    document.processing_duration_ms = max(
        0,
        int((document.processing_completed_at - document.processing_started_at).total_seconds() * 1000),
    )


def _add_index_records_from_pages(
    db: Session,
    document: Document,
    extracted_pages: list[ExtractedPage],
    embedder_factory: EmbeddingProviderFactory,
) -> None:
    pages = [
        Page(
            document_id=document.id,
            page_number=extracted_page.page_number,
            text=extracted_page.text,
            width=extracted_page.width,
            height=extracted_page.height,
            text_source=extracted_page.text_source,
            ocr_engine=extracted_page.ocr_engine,
            ocr_confidence=extracted_page.ocr_confidence,
            ocr_duration_ms=extracted_page.ocr_duration_ms,
        )
        for extracted_page in extracted_pages
    ]
    db.add_all(pages)
    db.flush()
    page_models = {page.page_number: page for page in pages}

    text_chunks = chunk_pages(extracted_pages)
    if not text_chunks:
        raise DocumentParseError("There is not enough usable text in this document for local search. It may need OCR.")

    embedder = embedder_factory()
    vectors = embedder.embed_texts([chunk.text for chunk in text_chunks])
    chunks = [
        Chunk(
            document_id=document.id,
            page_id=page_models[text_chunk.page_number].id,
            chunk_index=text_chunk.chunk_index,
            text=text_chunk.text,
            token_estimate=text_chunk.token_estimate,
            layout=text_chunk.layout,
        )
        for text_chunk in text_chunks
    ]
    db.add_all(chunks)
    db.flush()
    db.add_all(
        [
            ChunkEmbedding(chunk_id=chunk.id, model_name=embedder.model_name, embedding=vector)
            for chunk, vector in zip(chunks, vectors, strict=True)
        ]
    )


def index_stored_upload(
    db: Session,
    stored: StoredUpload,
    embedder_factory: EmbeddingProviderFactory | None,
    *,
    ocr_provider_factory: OcrProviderFactory | None = None,
    ocr_language: str = "eng",
    ocr_dpi: int = 200,
    ocr_max_pages: int = 25,
) -> Document:
    persisted_document = _persist_new_document(db, stored)
    document = persisted_document.model
    document_id = persisted_document.document_id

    try:
        ocr_provider = ocr_provider_factory() if ocr_provider_factory is not None else None
        if stored.kind == "image":
            if ocr_provider is None or not ocr_provider.is_available():
                return _persist_deferred_ocr_status(db, document, document_id, OCR_UNAVAILABLE_MESSAGE)
            if embedder_factory is None:
                raise RuntimeError("No embedding provider is configured for document indexing.")

            _start_ocr_processing(db, document)
            extraction_result = extract_image_pages(Path(document.file_path), ocr_provider=ocr_provider, language=ocr_language)
            if not extraction_result.pages:
                raise DocumentParseError("OCR completed, but no searchable text was found in this image.")
        else:
            if embedder_factory is None:
                raise RuntimeError("No embedding provider is configured for document indexing.")
            if ocr_provider is not None and ocr_provider.is_available() and ocr_max_pages > 0:
                _start_ocr_processing(db, document)
            extraction_result = extract_pdf_pages(
                Path(document.file_path),
                ocr_provider=ocr_provider,
                language=ocr_language,
                dpi=ocr_dpi,
                max_ocr_pages=ocr_max_pages,
            )

        _add_index_records_from_pages(db, document, extraction_result.pages, embedder_factory)
        if extraction_result.ocr_page_count:
            _complete_ocr_processing(document)
        elif document.status == DocumentStatus.OCR_PROCESSING:
            document.processing_started_at = None
        document.status = DocumentStatus.INDEXED
        document.error_message = None
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
    file_contents: bytes | None = None
    if file_path.exists():
        try:
            file_contents = file_path.read_bytes()
        except OSError as exc:
            raise DocumentPersistenceError("Could not prepare the document file for deletion.") from exc

    try:
        db.delete(document)
        db.flush()
    except SQLAlchemyError as exc:
        db.rollback()
        raise DocumentPersistenceError("Could not delete the document.") from exc

    if file_contents is not None:
        try:
            file_path.unlink()
        except OSError as exc:
            db.rollback()
            raise DocumentPersistenceError("Could not remove the document file.") from exc

    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        if file_contents is not None:
            try:
                file_path.write_bytes(file_contents)
            except OSError as restore_exc:
                raise DocumentPersistenceError("Could not restore the document file after database failure.") from restore_exc
        raise DocumentPersistenceError("Could not delete the document.") from exc


def reindex_document(
    db: Session,
    document_id: str,
    embedder_factory: EmbeddingProviderFactory,
    *,
    ocr_provider_factory: OcrProviderFactory | None = None,
    ocr_language: str = "eng",
    ocr_dpi: int = 200,
    ocr_max_pages: int = 25,
) -> Document:
    document = get_document_or_404(db, document_id)
    document_kind = "image" if document.mime_type.startswith("image/") else "pdf"

    try:
        document.status = DocumentStatus.PROCESSING
        document.error_message = None
        for page in list(document.pages):
            db.delete(page)
        db.flush()

        ocr_provider = ocr_provider_factory() if ocr_provider_factory is not None else None
        if document_kind == "image":
            if ocr_provider is None or not ocr_provider.is_available():
                raise DocumentReindexError(OCR_UNAVAILABLE_MESSAGE)
            document.status = DocumentStatus.OCR_PROCESSING
            document.processing_started_at = utc_now()
            document.processing_completed_at = None
            document.processing_duration_ms = None
            extraction_result = extract_image_pages(Path(document.file_path), ocr_provider=ocr_provider, language=ocr_language)
            if not extraction_result.pages:
                raise DocumentParseError("OCR completed, but no searchable text was found in this image.")
        else:
            extraction_result = extract_pdf_pages(
                Path(document.file_path),
                ocr_provider=ocr_provider,
                language=ocr_language,
                dpi=ocr_dpi,
                max_ocr_pages=ocr_max_pages,
            )

        _add_index_records_from_pages(db, document, extraction_result.pages, embedder_factory)
        if extraction_result.ocr_page_count:
            _complete_ocr_processing(document)
        document.status = DocumentStatus.INDEXED
        db.commit()
        db.expire(document, ["pages", "chunks"])
        return document
    except SQLAlchemyError as exc:
        db.rollback()
        raise DocumentPersistenceError("Could not reindex the document.") from exc
    except Exception as exc:
        db.rollback()
        raise DocumentReindexError(_failure_message(exc)) from exc
