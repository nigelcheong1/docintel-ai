from app.db.models import ChunkEmbedding, Document, DocumentStatus, Page


def test_document_status_values_are_stable():
    assert DocumentStatus.UPLOADED.value == "uploaded"
    assert DocumentStatus.PROCESSING.value == "processing"
    assert DocumentStatus.INDEXED.value == "indexed"
    assert DocumentStatus.DEFERRED_OCR.value == "deferred_ocr"
    assert DocumentStatus.FAILED.value == "failed"


def test_document_status_includes_ocr_processing():
    assert DocumentStatus.OCR_PROCESSING.value == "ocr_processing"


def test_page_ocr_metadata_columns_are_declared():
    columns = Page.__table__.columns

    assert columns["text_source"].nullable is False
    assert columns["ocr_engine"].nullable is True
    assert columns["ocr_confidence"].nullable is True
    assert columns["ocr_duration_ms"].nullable is True


def test_document_processing_metadata_columns_are_declared():
    columns = Document.__table__.columns

    assert columns["processing_started_at"].nullable is True
    assert columns["processing_completed_at"].nullable is True
    assert columns["processing_duration_ms"].nullable is True


def test_chunk_embedding_uses_384_dimensions():
    column_type = ChunkEmbedding.__table__.columns["embedding"].type

    assert getattr(column_type, "dim", None) == 384
