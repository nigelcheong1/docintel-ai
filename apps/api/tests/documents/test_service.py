from pathlib import Path

import fitz
import pytest

from app.db.models import DocumentStatus
from app.documents.storage import save_upload_bytes
from app.documents.service import index_stored_upload
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

    document = index_stored_upload(db_session, stored, FakeEmbeddingProvider())

    assert document.status == DocumentStatus.INDEXED
    assert len(document.pages) == 1
    assert len(document.chunks) >= 1
    assert document.chunks[0].embedding is not None


def test_index_stored_upload_defers_image_ocr(db_session, tmp_path):
    stored = save_upload_bytes("scan.png", "image/png", b"image-bytes", tmp_path / "storage", 20)

    document = index_stored_upload(db_session, stored, FakeEmbeddingProvider())

    assert document.status == DocumentStatus.DEFERRED_OCR
    assert document.error_message == "OCR is not enabled in the local-first MVP."
