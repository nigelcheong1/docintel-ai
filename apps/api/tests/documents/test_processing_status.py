from datetime import UTC, datetime, timedelta

from app.db.models import Chunk, Document, DocumentStatus, Page
from app.documents.processing_status import build_processing_status


def make_document(status: DocumentStatus = DocumentStatus.PROCESSING) -> Document:
    return Document(
        id="document-1",
        filename="sample.pdf",
        stored_filename="sample.pdf",
        mime_type="application/pdf",
        file_path="/tmp/sample.pdf",
        status=status,
        processing_started_at=datetime(2026, 9, 8, 1, 0, tzinfo=UTC),
    )


def test_processing_status_reports_stage_progress_for_indexed_document():
    document = make_document(DocumentStatus.INDEXED)
    document.processing_completed_at = document.processing_started_at + timedelta(seconds=3)
    page = Page(
        id="page-1",
        document_id=document.id,
        document=document,
        page_number=1,
        text="Searchable native text.",
        width=612,
        height=792,
        text_source="native",
    )
    document.pages = [page]
    document.chunks = [
        Chunk(
            id="chunk-1",
            document_id=document.id,
            page_id=page.id,
            page=page,
            chunk_index=0,
            text="Searchable native text.",
            token_estimate=3,
            layout={},
        )
    ]

    status = build_processing_status(document)

    assert status.document_id == "document-1"
    assert status.status == "indexed"
    assert status.active_stage == "ready"
    assert status.progress_percent == 100
    assert status.page_count == 1
    assert status.chunk_count == 1
    assert [stage.key for stage in status.stages] == ["upload", "extract", "chunk", "embed", "ready"]
    assert all(stage.status == "complete" for stage in status.stages)


def test_processing_status_reports_embedding_as_active_stage():
    document = make_document(DocumentStatus.EMBEDDING)
    page = Page(
        id="page-1",
        document_id=document.id,
        document=document,
        page_number=1,
        text="Extracted text waiting for embedding.",
        width=612,
        height=792,
        text_source="native",
    )
    document.pages = [page]
    document.chunks = [
        Chunk(
            id="chunk-1",
            document_id=document.id,
            page_id=page.id,
            page=page,
            chunk_index=0,
            text="Extracted text waiting for embedding.",
            token_estimate=5,
            layout={},
        )
    ]

    status = build_processing_status(document)

    assert status.active_stage == "embed"
    assert status.progress_percent == 80
    assert status.stages[-2].status == "active"
    assert status.stages[-1].status == "pending"


def test_processing_status_reports_failed_reason_and_failed_stage():
    document = make_document(DocumentStatus.FAILED)
    document.error_message = "Indexing failed: local model could not be loaded"

    status = build_processing_status(document)

    assert status.active_stage == "failed"
    assert status.progress_percent == 0
    assert status.message == "Indexing failed: local model could not be loaded"
    assert status.stages[-1].key == "failed"
    assert status.stages[-1].status == "failed"
