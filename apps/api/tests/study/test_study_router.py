from datetime import UTC, datetime

from fastapi.testclient import TestClient

import app.study.router as study_router
from app.db.models import DocumentSummary, StudyAnswer, StudyQuestion
from app.db.session import get_db
from app.main import create_app
from app.study.service import StudyDocumentNotReadyError, StudyQuestionNotFoundError


def client_with_fake_db():
    app = create_app()

    def override_db():
        yield object()

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def sample_citation():
    return {
        "chunk_id": "chunk-1",
        "document_id": "document-1",
        "document_filename": "paper.pdf",
        "page_number": 2,
        "section_heading": "METHOD",
        "page_image_url": "/documents/document-1/pages/2/image",
        "document_page_url": "/documents/document-1?page=2&chunk=chunk-1",
    }


def test_generate_summary_endpoint_returns_cited_summary(monkeypatch):
    def fake_generate_summary(_db, document_id: str):
        return DocumentSummary(
            id="summary-1",
            document_id=document_id,
            content="DocIntel AI summarizes cited evidence.",
            citations=[sample_citation()],
            created_at=datetime(2026, 9, 7, tzinfo=UTC),
        )

    monkeypatch.setattr(study_router, "generate_document_summary", fake_generate_summary)
    response = client_with_fake_db().post("/documents/document-1/study/summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["content"] == "DocIntel AI summarizes cited evidence."
    assert payload["citations"][0]["document_page_url"] == "/documents/document-1?page=2&chunk=chunk-1"


def test_generate_summary_endpoint_returns_400_when_document_is_not_ready(monkeypatch):
    def fake_generate_summary(_db, _document_id: str):
        raise StudyDocumentNotReadyError("Document must be indexed before study features can be generated.")

    monkeypatch.setattr(study_router, "generate_document_summary", fake_generate_summary)
    response = client_with_fake_db().post("/documents/document-1/study/summary")

    assert response.status_code == 400
    assert "must be indexed" in response.json()["detail"]


def test_generate_questions_endpoint_returns_questions(monkeypatch):
    def fake_generate_questions(_db, document_id: str, count: int):
        return [
            StudyQuestion(
                id="question-1",
                document_id=document_id,
                question="What methods are used?",
                expected_answer="The system uses OCR and embeddings.",
                citations=[sample_citation()],
                created_at=datetime(2026, 9, 7, tzinfo=UTC),
            )
        ][:count]

    monkeypatch.setattr(study_router, "generate_study_questions", fake_generate_questions)
    response = client_with_fake_db().post("/documents/document-1/study/questions", json={"count": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["question"] == "What methods are used?"
    assert payload[0]["citations"][0]["chunk_id"] == "chunk-1"


def test_submit_answer_endpoint_returns_score_and_feedback(monkeypatch):
    def fake_grade(_db, document_id: str, question_id: str, answer_text: str):
        assert document_id == "document-1"
        assert question_id == "question-1"
        assert "OCR" in answer_text
        return StudyAnswer(
            id="answer-1",
            question_id=question_id,
            answer_text=answer_text,
            score=0.82,
            feedback="Strong answer. You covered the main cited points.",
            created_at=datetime(2026, 9, 7, tzinfo=UTC),
        )

    monkeypatch.setattr(study_router, "grade_study_answer", fake_grade)
    response = client_with_fake_db().post(
        "/documents/document-1/study/questions/question-1/answers",
        json={"answer_text": "It uses OCR and embeddings."},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["score"] == 0.82
    assert "Strong answer" in payload["feedback"]


def test_submit_answer_endpoint_returns_404_for_wrong_document_question(monkeypatch):
    def fake_grade(_db, _document_id: str, _question_id: str, _answer_text: str):
        raise StudyQuestionNotFoundError("Study question not found for this document.")

    monkeypatch.setattr(study_router, "grade_study_answer", fake_grade)
    response = client_with_fake_db().post(
        "/documents/document-1/study/questions/question-2/answers",
        json={"answer_text": "Wrong document."},
    )

    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
