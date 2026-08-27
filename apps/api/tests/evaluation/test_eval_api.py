import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import create_app

pytestmark = pytest.mark.integration


def test_eval_runs_endpoint_creates_and_lists_runs(db_session):
    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    create_response = client.post("/eval/runs")

    assert create_response.status_code == 200
    created = create_response.json()
    assert created["name"] == "sample-retrieval-eval"
    assert created["model_name"] == "BAAI/bge-small-en-v1.5"
    assert created["metrics"] == {"hit_rate_at_5": 0.0, "mean_reciprocal_rank": 0.0}

    list_response = client.get("/eval/runs")

    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == created["id"]
