from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.documents.router import get_embedding_provider
from app.documents.service import index_stored_upload
from app.documents.storage import save_upload_bytes
from app.main import create_app
from app.retrieval.embeddings import FakeEmbeddingProvider

pytestmark = pytest.mark.integration


def create_sample_pdf(path: Path, text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path.read_bytes()


def test_search_endpoint_returns_cited_hits(db_session, tmp_path):
    content = create_sample_pdf(tmp_path / "sample.pdf", "The invoice total is 1250 Malaysian Ringgit.")
    stored = save_upload_bytes("invoice.pdf", "application/pdf", content, tmp_path / "storage", 20)
    index_stored_upload(db_session, stored, FakeEmbeddingProvider())

    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    response = client.post("/search", json={"query": "invoice total", "top_k": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "invoice total"
    assert len(body["hits"]) >= 1
    assert body["hits"][0]["document_filename"] == "invoice.pdf"
    assert body["hits"][0]["page_number"] == 1
    assert "invoice" in body["hits"][0]["snippet"].lower()
