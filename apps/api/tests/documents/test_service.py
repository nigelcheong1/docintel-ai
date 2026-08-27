from pathlib import Path

import fitz
import pytest
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.db.models import Document, DocumentStatus
from app.documents.storage import save_upload_bytes
from app.documents.service import DocumentPersistenceError, index_stored_upload
from app.retrieval.embeddings import FakeEmbeddingProvider

pytestmark = pytest.mark.integration


def create_sample_pdf(path: Path, text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path.read_bytes()


def test_index_stored_upload_indexes_pdf(db_session, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    content = create_sample_pdf(pdf_path, "Payment due date is 2026-09-01")
    stored = save_upload_bytes("sample.pdf", "application/pdf", content, tmp_path / "storage", 20)

    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())

    assert document.status == DocumentStatus.INDEXED
    assert len(document.pages) == 1
    assert len(document.chunks) >= 1
    assert document.chunks[0].embedding is not None


def test_index_stored_upload_defers_image_ocr(db_session, tmp_path):
    stored = save_upload_bytes("scan.png", "image/png", b"image-bytes", tmp_path / "storage", 20)

    document = index_stored_upload(db_session, stored, None)

    assert document.status == DocumentStatus.DEFERRED_OCR
    assert document.error_message == "OCR is not enabled in the local-first MVP."


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
    content = create_sample_pdf(pdf_path, "Embedding failure fixture")
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
