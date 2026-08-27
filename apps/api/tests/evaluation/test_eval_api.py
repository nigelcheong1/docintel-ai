import pytest
from fastapi.testclient import TestClient

from app.db.models import Chunk, Document, DocumentStatus, Page, Question, RetrievalResult
from app.db.session import get_db
from app.main import create_app

pytestmark = pytest.mark.integration


def create_client(db_session):
    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    return TestClient(app)


def add_retrieval_fixture(db_session):
    document = Document(
        filename="benchmark.pdf",
        stored_filename="benchmark.pdf",
        mime_type="application/pdf",
        file_path="storage/benchmark.pdf",
        status=DocumentStatus.INDEXED,
    )
    page = Page(document=document, page_number=1, text="Benchmark evidence")
    chunks = [
        Chunk(document=document, page=page, chunk_index=index, text=f"Chunk {index}", token_estimate=2)
        for index in range(3)
    ]
    first_question = Question(text="First benchmark question")
    second_question = Question(text="Second benchmark question")
    db_session.add_all([document, page, *chunks, first_question, second_question])
    db_session.flush()
    db_session.add_all(
        [
            RetrievalResult(question=first_question, chunk=chunks[0], score=0.9, rank=2),
            RetrievalResult(question=first_question, chunk=chunks[1], score=0.7, rank=8),
            RetrievalResult(question=second_question, chunk=chunks[2], score=0.8, rank=6),
        ]
    )
    db_session.commit()


def test_eval_runs_endpoint_persists_truthful_empty_run(db_session):
    client = create_client(db_session)

    create_response = client.post("/eval/runs")

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == "local-retrieval-benchmark"
    assert created["model_name"] == "BAAI/bge-small-en-v1.5"
    assert created["metrics"] == {
        "evaluated_questions": 0,
        "hit_rate_at_5": 0.0,
        "mean_reciprocal_rank": 0.0,
    }

    list_response = client.get("/eval/runs")

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == created["id"]


def test_eval_run_aggregates_stored_retrieval_results_by_question(db_session):
    add_retrieval_fixture(db_session)
    client = create_client(db_session)

    response = client.post("/eval/runs")

    assert response.status_code == 200
    assert response.json()["metrics"] == pytest.approx(
        {
            "evaluated_questions": 2,
            "hit_rate_at_5": 0.5,
            "mean_reciprocal_rank": 1 / 3,
        }
    )
