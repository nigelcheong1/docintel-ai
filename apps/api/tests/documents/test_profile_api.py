from pathlib import Path

import fitz
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.documents.router import get_embedding_provider
from app.documents.service import index_stored_upload
from app.documents.storage import save_upload_bytes
from app.main import create_app
from app.retrieval.embeddings import FakeEmbeddingProvider


def create_multiline_pdf(path: Path, lines: list[str]) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(fitz.Rect(72, 72, 540, 720), "\n".join(lines), fontsize=11)
    document.save(path)
    document.close()
    return path.read_bytes()


def test_document_profile_endpoint_returns_detected_type_and_suggestions(db_session, tmp_path):
    content = create_multiline_pdf(
        tmp_path / "paper.pdf",
        [
            "Language Guided Human-to-Robot Action Recognition",
            "Abstract",
            "This paper studies human robot interaction with a vision-language transformer.",
            "Method",
            "The approach fuses video features with language instructions.",
            "Results",
            "Experiments use Kinetics-400 and UCF-101 benchmarks.",
        ],
    )
    stored = save_upload_bytes("paper.pdf", "application/pdf", content, tmp_path / "storage", 20)
    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())

    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    response = client.get(f"/documents/{document.id}/profile")

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == document.id
    assert body["document_type"] == "research_paper"
    assert "What is this document about?" in body["suggested_questions"]
    assert any(section["heading"] == "ABSTRACT" for section in body["sections"])
