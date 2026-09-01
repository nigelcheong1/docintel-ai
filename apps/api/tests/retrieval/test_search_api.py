from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from app.db.models import Chunk, Document, DocumentStatus, Page
from app.db.session import get_db
from app.documents.router import get_embedding_provider
from app.documents.service import index_stored_upload
from app.documents.storage import save_upload_bytes
from app.main import create_app
from app.retrieval.embeddings import FakeEmbeddingProvider
from app.retrieval.search import SearchHit
import app.retrieval.router as retrieval_router

pytestmark = pytest.mark.integration


class InMemoryDocumentDb:
    def __init__(self, document: Document) -> None:
        self.document = document

    def get(self, model, document_id: str):
        if model is Document and document_id == self.document.id:
            return self.document
        return None


def make_in_memory_document(filename: str, chunks: list[tuple[str, str | None, int]]) -> Document:
    document = Document(
        id="document-1",
        filename=filename,
        stored_filename=filename,
        mime_type="application/pdf",
        file_path=f"/tmp/{filename}",
        status=DocumentStatus.INDEXED,
    )
    page_texts: dict[int, list[str]] = {}
    for text, _heading, page_number in chunks:
        page_texts.setdefault(page_number, []).append(text)
    pages = [
        Page(
            id=f"page-{page_number}",
            document_id=document.id,
            page_number=page_number,
            text="\n".join(texts),
            width=612,
            height=792,
        )
        for page_number, texts in sorted(page_texts.items())
    ]
    pages_by_number = {page.page_number: page for page in pages}
    document.pages = pages
    document.chunks = [
        Chunk(
            id=f"chunk-{index}",
            document_id=document.id,
            page_id=pages_by_number[page_number].id,
            page=pages_by_number[page_number],
            chunk_index=index,
            text=text,
            token_estimate=len(text.split()),
            layout={"section_heading": heading} if heading else {},
        )
        for index, (text, heading, page_number) in enumerate(chunks)
    ]
    return document


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


def test_search_endpoint_returns_diagnostics_and_evidence_roles(monkeypatch):
    candidates = [
        SearchHit(
            chunk_id="invoice-total",
            document_id="document-1",
            document_filename="invoice.pdf",
            page_number=1,
            chunk_index=0,
            text="PAYMENT SUMMARY Total Due RM 1,272.00",
            score=0.88,
            source_score=0.88,
            section_heading="PAYMENT SUMMARY",
        ),
        SearchHit(
            chunk_id="invoice-vendor",
            document_id="document-1",
            document_filename="invoice.pdf",
            page_number=1,
            chunk_index=1,
            text="Vendor DocIntel Labs",
            score=0.62,
            source_score=0.62,
            section_heading="VENDOR",
        ),
    ]

    def search_invoice_candidates(_db, _embedding, _top_k, _document_id):
        return candidates

    monkeypatch.setattr(retrieval_router, "search_chunks", search_invoice_candidates)
    app = create_app()

    def override_db():
        yield object()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    response = TestClient(app).post("/search", json={"query": "What total amount is due?", "top_k": 2})

    assert response.status_code == 200
    body = response.json()
    assert body["diagnostics"] == {
        "document_type": None,
        "query_intent": "amounts",
        "quality_status": "answerable",
        "confidence": "strong",
        "reason": "Answer built from 1 cited evidence chunk.",
        "answer_chunk_ids": ["invoice-total"],
        "answer_evidence_count": 1,
        "related_result_count": 1,
        "top_rejected_reasons": [
            "Related evidence was not cited because it ranked below the selected answer evidence."
        ],
    }
    assert all("invoice-vendor" not in reason for reason in body["diagnostics"]["top_rejected_reasons"])
    assert body["hits"][0]["result_role"] == "answer_evidence"
    assert body["hits"][1]["result_role"] == "related"


def test_search_endpoint_includes_document_aware_evidence_when_vector_hit_misses_cited_chunk(monkeypatch):
    document = make_in_memory_document(
        "paper.pdf",
        [
            (
                "ABSTRACT This paper introduces H2R Bridge for human-robot collaboration and few-shot intention recognition.",
                "ABSTRACT",
                1,
            ),
            (
                "METHOD The system uses a temporal encoder and robot command generation.",
                "METHOD",
                2,
            ),
        ],
    )
    vector_only_hit = SearchHit(
        chunk_id="chunk-1",
        document_id=document.id,
        document_filename=document.filename,
        page_number=2,
        chunk_index=1,
        text="METHOD The system uses a temporal encoder and robot command generation.",
        score=0.61,
        source_score=0.61,
        section_heading="METHOD",
    )

    def search_method_candidate(_db, _embedding, _top_k, _document_id):
        return [vector_only_hit]

    monkeypatch.setattr(retrieval_router, "search_chunks", search_method_candidate)
    app = create_app()

    def override_db():
        yield InMemoryDocumentDb(document)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    response = TestClient(app).post(
        "/search",
        json={"query": "What is this document about?", "top_k": 1, "document_id": document.id},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["answer"]["citations"][0]["chunk_id"] == "chunk-0"
    assert [hit["chunk_id"] for hit in body["hits"]] == ["chunk-0", "chunk-1"]
    assert body["hits"][0]["result_role"] == "answer_evidence"
    assert body["hits"][1]["result_role"] == "related"
    assert body["diagnostics"]["answer_chunk_ids"] == ["chunk-0"]
    assert body["diagnostics"]["answer_evidence_count"] == 1
    assert body["diagnostics"]["related_result_count"] == 1


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
