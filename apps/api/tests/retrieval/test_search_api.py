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
from app.retrieval.search import SearchHit
import app.retrieval.router as retrieval_router

pytestmark = pytest.mark.integration


def create_sample_pdf(path: Path, text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path.read_bytes()


def create_multiline_pdf(path: Path, lines: list[str]) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_textbox(fitz.Rect(72, 72, 540, 720), "\n".join(lines), fontsize=11)
    document.save(path)
    document.close()
    return path.read_bytes()


def test_search_endpoint_returns_cited_hits(db_session, tmp_path):
    content = create_sample_pdf(tmp_path / "sample.pdf", "The invoice total is 1250 Malaysian Ringgit.")
    stored = save_upload_bytes("invoice.pdf", "application/pdf", content, tmp_path / "storage", 20)
    index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())

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
    assert body["answer"] is not None
    assert body["answer"]["citations"][0]["chunk_id"] == body["hits"][0]["chunk_id"]
    assert body["quality"]["status"] == "answerable"
    assert body["quality"]["confidence"] in {"strong", "moderate"}


def test_search_endpoint_returns_chunk_section_heading(db_session, tmp_path):
    content = create_sample_pdf(
        tmp_path / "resume.pdf",
        "KEY PROJECTS Skin Lesion Classification built a CNN dashboard.",
    )
    stored = save_upload_bytes("resume.pdf", "application/pdf", content, tmp_path / "storage", 20)
    index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())

    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    response = client.post("/search", json={"query": "projects", "top_k": 1})

    assert response.status_code == 200
    body = response.json()
    assert body["hits"][0]["section_heading"] == "KEY PROJECTS"


def test_search_endpoint_overfetches_reranks_and_slices_candidates(monkeypatch):
    candidates = [
        SearchHit(
            chunk_id=f"tool-{index}",
            document_id="document-1",
            document_filename="resume.pdf",
            page_number=1,
            chunk_index=index,
            text="Python and Docker",
            score=0.85,
            source_score=0.85,
            section_heading="TOOLS & PLATFORMS",
        )
        for index in range(11)
    ]
    candidates.append(
        SearchHit(
            chunk_id="project-12",
            document_id="document-1",
            document_filename="resume.pdf",
            page_number=1,
            chunk_index=11,
            text="PROJECTS: skin lesion classification",
            score=0.84,
            source_score=0.84,
            section_heading="KEY PROJECTS",
        )
    )
    requested_limits: list[int] = []

    def search_only_requested_candidates(_db, _embedding, top_k, _document_id):
        requested_limits.append(top_k)
        return candidates[:top_k]

    monkeypatch.setattr(retrieval_router, "search_chunks", search_only_requested_candidates)
    app = create_app()

    def override_db():
        yield object()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    response = TestClient(app).post("/search", json={"query": "projects", "top_k": 2})

    assert response.status_code == 200
    assert requested_limits == [12]
    body = response.json()
    assert len(body["hits"]) == 2
    assert body["hits"][0]["chunk_id"] == "project-12"
    assert body["hits"][0]["source_score"] == 0.84
    assert body["hits"][0]["ranking_signals"] == {"keyword_overlap": 1.0, "section_intent": 1.0}


def test_search_endpoint_abstains_when_retrieved_hits_do_not_answer_question(monkeypatch):
    candidates = [
        SearchHit(
            chunk_id="contact",
            document_id="document-1",
            document_filename="resume.pdf",
            page_number=1,
            chunk_index=0,
            text="Nigel Cheong Kuala Lumpur github.com/nigelcheong1.",
            score=0.46,
            source_score=0.46,
        ),
        SearchHit(
            chunk_id="skills",
            document_id="document-1",
            document_filename="resume.pdf",
            page_number=1,
            chunk_index=1,
            text="TECHNICAL SKILLS Machine Learning, Computer Vision, Python, SQL.",
            score=0.45,
            source_score=0.45,
            section_heading="TECHNICAL SKILLS",
        ),
    ]

    def search_resume_candidates(_db, _embedding, _top_k, _document_id):
        return candidates

    monkeypatch.setattr(retrieval_router, "search_chunks", search_resume_candidates)
    app = create_app()

    def override_db():
        yield object()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    response = TestClient(app).post(
        "/search",
        json={"query": "How does invoice payment work?", "top_k": 2, "document_id": "document-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["hits"]) == 2
    assert body["answer"] is None
    assert body["quality"]["status"] == "insufficient_evidence"
    assert body["quality"]["confidence"] == "weak"
    assert "What technical skills are mentioned?" in body["quality"]["suggested_questions"]


def test_search_endpoint_answers_research_paper_overview_from_profile(db_session, tmp_path):
    content = create_multiline_pdf(
        tmp_path / "paper.pdf",
        [
            "Human-to-Robot Action Recognition with Language Guidance",
            "Abstract",
            "This paper proposes a vision-language transformer for industrial human action recognition.",
            "Method",
            "The method fuses video features with language instructions.",
            "Results",
            "Experiments report improved TOP1 accuracy on Kinetics-400 and UCF-101.",
            "References",
            "D. Wu et al. 2026.",
        ],
    )
    stored = save_upload_bytes("paper.pdf", "application/pdf", content, tmp_path / "storage", 20)
    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())

    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    response = TestClient(app).post(
        "/search",
        json={"query": "What is this document about?", "top_k": 3, "document_id": document.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["document_type"] == "research_paper"
    assert body["query_intent"] == "overview"
    assert body["answer"] is not None
    assert "vision-language transformer" in body["answer"]["summary"]
    assert body["quality"]["status"] == "answerable"


def test_search_endpoint_answers_invoice_totals_from_profile(db_session, tmp_path):
    content = create_multiline_pdf(
        tmp_path / "invoice.pdf",
        [
            "Invoice INV-1001",
            "Vendor: DocIntel Labs",
            "Bill To: Xiamen University Malaysia",
            "Issue Date: 2026-08-01",
            "Due Date: 2026-08-30",
            "Subtotal RM 1,200.00",
            "Tax RM 72.00",
            "Total Due RM 1,272.00",
        ],
    )
    stored = save_upload_bytes("invoice.pdf", "application/pdf", content, tmp_path / "storage", 20)
    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())

    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    response = TestClient(app).post(
        "/search",
        json={"query": "What total amount is due?", "top_k": 3, "document_id": document.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["document_type"] == "invoice"
    assert body["query_intent"] == "amounts"
    assert body["answer"] is not None
    assert "RM 1,272.00" in body["answer"]["summary"]
    assert body["quality"]["confidence"] == "strong"


def test_search_endpoint_returns_type_aware_mismatch_for_research_paper(db_session, tmp_path):
    content = create_multiline_pdf(
        tmp_path / "paper.pdf",
        [
            "Human-to-Robot Action Recognition with Language Guidance",
            "Abstract",
            "This paper proposes a transformer for industrial human action recognition.",
            "References",
            "D. Wu et al. 2026.",
        ],
    )
    stored = save_upload_bytes("paper.pdf", "application/pdf", content, tmp_path / "storage", 20)
    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())

    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    response = TestClient(app).post(
        "/search",
        json={"query": "Who are the parties involved?", "top_k": 3, "document_id": document.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["document_type"] == "research_paper"
    assert body["query_intent"] == "parties"
    assert body["answer"] is None
    assert body["quality"]["status"] == "insufficient_evidence"
    assert "research paper" in body["quality"]["reason"].lower()
