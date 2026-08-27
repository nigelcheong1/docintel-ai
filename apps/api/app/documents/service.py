from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, ChunkEmbedding, Document, DocumentStatus, Page
from app.documents.chunker import chunk_pages
from app.documents.parser import DocumentParseError, parse_pdf
from app.documents.storage import StoredUpload
from app.retrieval.embeddings import EmbeddingProvider


def index_stored_upload(db: Session, stored: StoredUpload, embedder: EmbeddingProvider) -> Document:
    document = Document(
        filename=stored.original_filename,
        stored_filename=stored.stored_filename,
        mime_type=stored.mime_type,
        file_path=str(stored.file_path),
        status=DocumentStatus.PROCESSING,
    )
    db.add(document)
    db.flush()

    if stored.kind == "image":
        document.status = DocumentStatus.DEFERRED_OCR
        document.error_message = "OCR is not enabled in the local-first MVP."
        db.commit()
        db.refresh(document)
        return document

    try:
        parsed_pages = parse_pdf(Path(stored.file_path))
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

        document.status = DocumentStatus.INDEXED
        db.commit()
        db.refresh(document)
        return document
    except DocumentParseError as exc:
        document.status = DocumentStatus.FAILED
        document.error_message = str(exc)
        db.commit()
        db.refresh(document)
        return document


def list_documents(db: Session) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


def get_document_or_404(db: Session, document_id: str) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Document not found.")
    return document
