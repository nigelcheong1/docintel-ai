from app.db.models import ChunkEmbedding, DocumentStatus


def test_document_status_values_are_stable():
    assert DocumentStatus.UPLOADED.value == "uploaded"
    assert DocumentStatus.PROCESSING.value == "processing"
    assert DocumentStatus.INDEXED.value == "indexed"
    assert DocumentStatus.DEFERRED_OCR.value == "deferred_ocr"
    assert DocumentStatus.FAILED.value == "failed"


def test_chunk_embedding_uses_384_dimensions():
    column_type = ChunkEmbedding.__table__.columns["embedding"].type

    assert getattr(column_type, "dim", None) == 384
