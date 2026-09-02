from pathlib import Path

import fitz
import pytest
from PIL import Image
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import Chunk, ChunkEmbedding, Document, DocumentStatus, Page
from app.documents.ocr import OcrPageResult
from app.documents.storage import save_upload_bytes
from app.documents.service import (
    DocumentPersistenceError,
    DocumentReindexError,
    delete_document,
    index_stored_upload,
    reindex_document,
)
from app.retrieval.embeddings import FakeEmbeddingProvider

pytestmark = pytest.mark.integration


def create_sample_pdf(path: Path, text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path.read_bytes()


class FakeOcrProvider:
    engine_name = "fake-ocr"

    def __init__(self, available: bool = True, text: str = "OCR searchable content from scanned document") -> None:
        self.available = available
        self.text = text

    def is_available(self) -> bool:
        return self.available

    def ocr_image(self, image: Image.Image, *, language: str) -> OcrPageResult:
        return OcrPageResult(text=self.text, confidence=88.0, engine_name=self.engine_name, duration_ms=5)


def test_index_stored_upload_indexes_pdf(db_session, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    content = create_sample_pdf(pdf_path, "Payment due date is 2026-09-01")
    stored = save_upload_bytes("sample.pdf", "application/pdf", content, tmp_path / "storage", 20)

    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())

    assert document.status == DocumentStatus.INDEXED
    assert len(document.pages) == 1
    assert len(document.chunks) >= 1
    assert document.chunks[0].embedding is not None


def test_index_stored_upload_fails_cleanly_when_pdf_has_no_usable_chunks(db_session, tmp_path):
    pdf_path = tmp_path / "sparse.pdf"
    content = create_sample_pdf(pdf_path, ".")
    stored = save_upload_bytes("sparse.pdf", "application/pdf", content, tmp_path / "storage", 20)

    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())

    assert document.status == DocumentStatus.FAILED
    assert "not enough usable text" in (document.error_message or "").lower()


def test_index_stored_upload_indexes_image_with_available_ocr(db_session, tmp_path):
    image_path = tmp_path / "scan.png"
    Image.new("RGB", (120, 60), "white").save(image_path)
    stored = save_upload_bytes("scan.png", "image/png", image_path.read_bytes(), tmp_path / "storage", 20)

    document = index_stored_upload(
        db_session,
        stored,
        lambda: FakeEmbeddingProvider(),
        ocr_provider_factory=lambda: FakeOcrProvider(),
        ocr_language="eng",
        ocr_dpi=200,
        ocr_max_pages=25,
    )

    assert document.status == DocumentStatus.INDEXED
    assert document.processing_started_at is not None
    assert document.processing_completed_at is not None
    assert document.processing_duration_ms is not None
    assert document.pages[0].text_source == "ocr"
    assert document.pages[0].ocr_engine == "fake-ocr"
    assert document.pages[0].ocr_confidence == 88.0
    assert "OCR searchable content" in document.chunks[0].text


def test_index_stored_upload_reports_sparse_image_ocr_failure(db_session, tmp_path):
    image_path = tmp_path / "portrait.png"
    Image.new("RGB", (120, 60), "white").save(image_path)
    stored = save_upload_bytes("portrait.png", "image/png", image_path.read_bytes(), tmp_path / "storage", 20)

    document = index_stored_upload(
        db_session,
        stored,
        lambda: FakeEmbeddingProvider(),
        ocr_provider_factory=lambda: FakeOcrProvider(text="WG | ow"),
        ocr_language="eng",
        ocr_dpi=200,
        ocr_max_pages=25,
    )

    assert document.status == DocumentStatus.FAILED
    assert "OCR ran" in (document.error_message or "")
    assert "readable document text" in (document.error_message or "")


def test_index_stored_upload_defers_image_when_ocr_is_unavailable(db_session, tmp_path):
    stored = save_upload_bytes("scan.png", "image/png", b"image-bytes", tmp_path / "storage", 20)

    document = index_stored_upload(
        db_session,
        stored,
        lambda: FakeEmbeddingProvider(),
        ocr_provider_factory=lambda: FakeOcrProvider(available=False),
        ocr_language="eng",
        ocr_dpi=200,
        ocr_max_pages=25,
    )

    assert document.status == DocumentStatus.DEFERRED_OCR
    assert "Local OCR is not available" in (document.error_message or "")


def test_index_stored_upload_persists_malformed_pdf_failure_without_loading_model(db_session, tmp_path):
    stored = save_upload_bytes(
        "malformed.pdf",
        "application/pdf",
        b"not a valid PDF",
        tmp_path / "storage",
        20,
    )

    def unexpected_embedder():
        raise AssertionError("embedding provider must not load before parsing succeeds")

    document = index_stored_upload(db_session, stored, unexpected_embedder)

    persisted = db_session.get(Document, document.id)
    assert persisted is not None
    assert persisted.status == DocumentStatus.FAILED
    assert "Could not read PDF" in (persisted.error_message or "")


def test_index_stored_upload_persists_embedding_provider_failure(db_session, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    content = create_sample_pdf(pdf_path, "Embedding failure fixture with enough searchable document words")
    stored = save_upload_bytes("sample.pdf", "application/pdf", content, tmp_path / "storage", 20)

    def failing_embedder():
        raise RuntimeError("local model could not be loaded")

    document = index_stored_upload(db_session, stored, failing_embedder)

    persisted = db_session.get(Document, document.id)
    assert persisted is not None
    assert persisted.status == DocumentStatus.FAILED
    assert persisted.error_message == "Indexing failed: local model could not be loaded"


def test_index_stored_upload_removes_file_when_document_persistence_fails(db_session, tmp_path, monkeypatch):
    stored = save_upload_bytes("scan.png", "image/png", b"image-bytes", tmp_path / "storage", 20)

    def fail_commit():
        raise SQLAlchemyError("forced persistence failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)

    with pytest.raises(DocumentPersistenceError, match="Could not persist"):
        index_stored_upload(db_session, stored, None)

    assert not stored.file_path.exists()


def test_index_stored_upload_does_not_need_refresh_after_initial_commit(db_session, tmp_path, monkeypatch):
    stored = save_upload_bytes("scan.png", "image/png", b"image-bytes", tmp_path / "storage", 20)

    def fail_refresh(_document):
        raise SQLAlchemyError("forced refresh failure")

    monkeypatch.setattr(db_session, "refresh", fail_refresh)

    document = index_stored_upload(db_session, stored, None)
    persisted = db_session.scalar(select(Document).where(Document.id == document.id))

    assert persisted is not None
    assert persisted.status == DocumentStatus.DEFERRED_OCR
    assert stored.file_path.exists()


def test_index_stored_upload_marks_failed_when_deferred_status_cannot_commit(db_session, tmp_path, monkeypatch):
    stored = save_upload_bytes("scan.png", "image/png", b"image-bytes", tmp_path / "storage", 20)
    original_commit = db_session.commit
    commit_calls = 0

    def fail_deferred_status_commit():
        nonlocal commit_calls
        commit_calls += 1
        if commit_calls == 2:
            raise SQLAlchemyError("forced deferred status failure")
        original_commit()

    monkeypatch.setattr(db_session, "commit", fail_deferred_status_commit)

    document = index_stored_upload(db_session, stored, None)
    persisted = db_session.scalar(select(Document).where(Document.id == document.id))

    assert persisted is not None
    assert persisted.status == DocumentStatus.FAILED
    assert persisted.error_message == "Could not persist the deferred OCR status."


def test_delete_document_removes_database_records_and_stored_file(db_session, tmp_path):
    stored = save_upload_bytes("scan.png", "image/png", b"image-bytes", tmp_path / "storage", 20)
    document = index_stored_upload(db_session, stored, None)

    delete_document(db_session, document.id)

    assert db_session.get(Document, document.id) is None
    assert not stored.file_path.exists()


def test_delete_document_resolves_legacy_relative_storage_path(db_session, tmp_path, monkeypatch):
    storage_dir = tmp_path / "api" / "storage"
    storage_dir.mkdir(parents=True)
    stored_file = storage_dir / "legacy.png"
    stored_file.write_bytes(b"image-bytes")
    document = Document(
        filename="legacy.png",
        stored_filename=stored_file.name,
        mime_type="image/png",
        file_path=str(Path("storage") / stored_file.name),
        status=DocumentStatus.DEFERRED_OCR,
    )
    db_session.add(document)
    db_session.commit()
    outside_cwd = tmp_path / "outside"
    outside_cwd.mkdir()
    monkeypatch.chdir(outside_cwd)

    delete_document(db_session, document.id, storage_dir=storage_dir)

    assert db_session.get(Document, document.id) is None
    assert not stored_file.exists()


def test_delete_document_keeps_database_record_when_file_removal_fails(db_session, tmp_path, monkeypatch):
    stored = save_upload_bytes("scan.png", "image/png", b"image-bytes", tmp_path / "storage", 20)
    document = index_stored_upload(db_session, stored, None)

    def fail_unlink(self, missing_ok=False):
        raise OSError("storage is unavailable")

    monkeypatch.setattr(Path, "unlink", fail_unlink)

    with pytest.raises(DocumentPersistenceError, match="remove the document file"):
        delete_document(db_session, document.id)

    assert db_session.get(Document, document.id) is not None
    assert stored.file_path.exists()


def test_delete_document_restores_stored_file_when_database_commit_fails(db_session, tmp_path, monkeypatch):
    stored = save_upload_bytes("scan.png", "image/png", b"image-bytes", tmp_path / "storage", 20)
    document = index_stored_upload(db_session, stored, None)

    def fail_commit():
        raise SQLAlchemyError("forced deletion commit failure")

    monkeypatch.setattr(db_session, "commit", fail_commit)

    with pytest.raises(DocumentPersistenceError):
        delete_document(db_session, document.id)

    assert db_session.get(Document, document.id) is not None
    assert stored.file_path.exists()
    assert stored.file_path.read_bytes() == b"image-bytes"


def test_reindex_document_replaces_prior_pages_chunks_and_embeddings(db_session, tmp_path):
    storage_dir = tmp_path / "storage"
    original_pdf_path = tmp_path / "original.pdf"
    stored = save_upload_bytes(
        "resume.pdf",
        "application/pdf",
        create_sample_pdf(original_pdf_path, "Original document content with enough searchable words"),
        storage_dir,
        20,
    )
    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())
    old_page_ids = [page.id for page in document.pages]
    old_chunk_ids = [chunk.id for chunk in document.chunks]
    old_embedding_ids = [chunk.embedding.id for chunk in document.chunks if chunk.embedding is not None]

    replacement = fitz.open()
    for text in (
        "Replacement first page with enough searchable content",
        "Replacement second page with enough searchable content",
    ):
        page = replacement.new_page()
        page.insert_text((72, 72), text)
    replacement.save(stored.file_path)
    replacement.close()

    reindexed = reindex_document(db_session, document.id, lambda: FakeEmbeddingProvider())

    assert reindexed.status == DocumentStatus.INDEXED
    assert len(reindexed.pages) == 2
    assert any("Replacement first page" in chunk.text for chunk in reindexed.chunks)
    assert any("Replacement second page" in chunk.text for chunk in reindexed.chunks)
    assert db_session.scalars(select(Page).where(Page.id.in_(old_page_ids))).all() == []
    assert db_session.scalars(select(Chunk).where(Chunk.id.in_(old_chunk_ids))).all() == []
    assert db_session.scalars(select(ChunkEmbedding).where(ChunkEmbedding.id.in_(old_embedding_ids))).all() == []


def test_reindex_document_resolves_legacy_relative_storage_path(db_session, tmp_path, monkeypatch):
    storage_dir = tmp_path / "api" / "storage"
    storage_dir.mkdir(parents=True)
    stored_file = storage_dir / "legacy.png"
    Image.new("RGB", (120, 60), "white").save(stored_file)
    document = Document(
        filename="legacy.png",
        stored_filename=stored_file.name,
        mime_type="image/png",
        file_path=str(Path("storage") / stored_file.name),
        status=DocumentStatus.DEFERRED_OCR,
    )
    db_session.add(document)
    db_session.commit()
    outside_cwd = tmp_path / "outside"
    outside_cwd.mkdir()
    monkeypatch.chdir(outside_cwd)

    reindexed = reindex_document(
        db_session,
        document.id,
        lambda: FakeEmbeddingProvider(),
        storage_dir=storage_dir,
        ocr_provider_factory=lambda: FakeOcrProvider(),
    )

    assert reindexed.status == DocumentStatus.INDEXED
    assert reindexed.pages[0].text_source == "ocr"


def test_reindex_document_preserves_prior_index_when_embedding_fails(db_session, tmp_path):
    original_pdf_path = tmp_path / "original.pdf"
    stored = save_upload_bytes(
        "resume.pdf",
        "application/pdf",
        create_sample_pdf(original_pdf_path, "Original searchable content with enough words"),
        tmp_path / "storage",
        20,
    )
    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())
    old_page_ids = [page.id for page in document.pages]
    old_chunk_ids = [chunk.id for chunk in document.chunks]
    old_embedding_ids = [chunk.embedding.id for chunk in document.chunks if chunk.embedding is not None]

    def failing_embedder():
        raise RuntimeError("local model could not be loaded")

    with pytest.raises(DocumentReindexError, match="local model could not be loaded"):
        reindex_document(db_session, document.id, failing_embedder)

    db_session.expire_all()
    persisted = db_session.get(Document, document.id)
    assert persisted is not None
    assert persisted.status == DocumentStatus.INDEXED
    assert persisted.error_message is None
    assert [page.id for page in persisted.pages] == old_page_ids
    assert [chunk.id for chunk in persisted.chunks] == old_chunk_ids
    assert [chunk.embedding.id for chunk in persisted.chunks if chunk.embedding is not None] == old_embedding_ids
