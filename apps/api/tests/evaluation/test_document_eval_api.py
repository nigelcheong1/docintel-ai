from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.db.models import Chunk, Document, DocumentEvalRun, DocumentStatus, Page
from app.db.session import get_db
from app.documents.router import get_embedding_provider_factory
from app.main import create_app

pytestmark = pytest.mark.integration


class BrokenEmbedder:
    def embed_texts(self, texts):
        raise RuntimeError("Test lexical fallback")


@pytest.fixture
def api(db_session, tmp_path):
    path = tmp_path / "source.pdf"
    path.touch()
    document = Document(filename="source.pdf", stored_filename="source.pdf", mime_type="application/pdf", file_path=str(path), status=DocumentStatus.INDEXED)
    page = Page(document=document, page_number=1, text="From Scopus, an aggregate of 2366 results were obtained.")
    chunk = Chunk(document=document, page=page, chunk_index=0, text=page.text)
    db_session.add_all([document, page, chunk])
    db_session.commit()
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_embedding_provider_factory] = lambda: lambda: BrokenEmbedder()
    return TestClient(app), document


def add_reviewed(api, *, negative=False):
    client, document = api
    response = client.post("/eval/document-suites", json={"name": "Reviewed counts"})
    assert response.status_code == 201
    suite = response.json()
    payload = {"document_id": document.id, "question": "What private GPU cluster was used?" if negative else "How many results were initially obtained from Scopus?", "expected_outcome": "insufficient_evidence" if negative else "answerable", "facts": [] if negative else [{"pattern": "From Scopus, an aggregate of 2366 results were obtained"}], "anchors": [] if negative else [{"page_number": 1, "quote": "From Scopus, an aggregate of 2366 results were obtained."}], "tags": ["missing-evidence"] if negative else ["numeric"], "review_rationale": "Entire document scope reviewed; no GPU hardware is reported." if negative else ""}
    response = client.post(f"/eval/document-suites/{suite['id']}/cases", json=payload)
    assert response.status_code == 201
    case = response.json()
    assert case["review_state"] == "draft"
    response = client.post(f"/eval/document-suites/{suite['id']}/cases/{case['id']}/review", json={"content_version": 1})
    assert response.status_code == 200
    assert response.json()["availability"] == "ready"
    return suite, case, payload


def test_suite_case_crud_review_and_ownership(api):
    client, _document = api
    suite, case, payload = add_reviewed(api)
    assert client.get("/eval/document-suites").json()[0]["reviewed_count"] == 1
    detail = client.get(f"/eval/document-suites/{suite['id']}").json()
    assert detail["cases"][0]["content_version"] == 1
    renamed = client.put(f"/eval/document-suites/{suite['id']}", json={"name": "Revised counts"})
    assert renamed.json()["name"] == "Revised counts"
    payload["question"] = "How many Scopus results?"
    updated = client.put(f"/eval/document-suites/{suite['id']}/cases/{case['id']}", json=payload)
    assert updated.json()["review_state"] == "draft"
    assert updated.json()["content_version"] == 2
    assert client.post(f"/eval/document-suites/{suite['id']}/cases/{case['id']}/review", json={"content_version": 1}).status_code == 409
    other = client.post("/eval/document-suites", json={"name": "Other"}).json()
    assert client.put(f"/eval/document-suites/{other['id']}/cases/{case['id']}", json=payload).status_code == 404
    assert client.delete(f"/eval/document-suites/{other['id']}/cases/{case['id']}").status_code == 404
    assert client.delete(f"/eval/document-suites/{suite['id']}/cases/{case['id']}").status_code == 204
    assert client.delete(f"/eval/document-suites/{suite['id']}").status_code == 204


def test_validation_and_missing_ids(api):
    client, _document = api
    assert client.post("/eval/document-suites", json={"name": " "}).status_code == 422
    assert client.get(f"/eval/document-suites/{uuid4()}").status_code == 404
    assert client.get("/eval/document-suites/invalid").status_code == 422
    assert client.get(f"/eval/document-runs/{uuid4()}/results").status_code == 404


def test_run_progress_results_and_assessment_are_persisted(api, db_session):
    client, _document = api
    suite, case, _payload = add_reviewed(api)
    response = client.post("/eval/document-runs", json={"suite_id": suite["id"]})
    assert response.status_code == 202
    run = response.json()
    assert run["status"] == "queued"
    current = client.get(f"/eval/document-runs/{run['id']}").json()
    assert current["status"] == "completed"
    assert current["completed_cases"] == 1
    assert current["mode_counts"] == {"lexical": 1}
    assert current["fallback_count"] == 1
    result = client.get(f"/eval/document-runs/{run['id']}/results").json()[0]
    assert result["status"] == "pass"
    assessed = client.put(f"/eval/document-runs/{run['id']}/results/{result['id']}/assessment", json={"assessment": "needs_review", "note": "Inspect the original source for numeric consistency."}).json()
    assert assessed["human_assessment"] == "needs_review"
    assert assessed["measurements"] == result["measurements"]
    assert assessed["execution_snapshot"] == result["execution_snapshot"]
    assert client.put(f"/eval/document-runs/{uuid4()}/results/{result['id']}/assessment", json={"assessment": "correct"}).status_code == 404
    assert client.post(f"/eval/document-runs/{run['id']}/cancel").json()["status"] == "completed"
    assert client.get(f"/eval/document-runs?suite_id={suite['id']}").json()[0]["id"] == run["id"]
    assert client.delete(f"/eval/document-suites/{suite['id']}").status_code == 204
    assert client.get(f"/eval/document-runs/{run['id']}").json()["suite_id"] is None
    assert client.get(f"/eval/document-runs/{run['id']}/results").json()[0]["case_id_snapshot"] == case["id"]


def test_active_run_conflicts_and_queued_cancel_releases_slot(api, db_session):
    client, _document = api
    suite, _case, _payload = add_reviewed(api)
    busy = DocumentEvalRun(status="queued", active_slot=1)
    db_session.add(busy)
    db_session.commit()
    assert client.post("/eval/document-runs", json={"suite_id": suite["id"]}).status_code == 409
    assert client.post(f"/eval/document-runs/{busy.id}/cancel").json()["status"] == "cancelled"
    assert client.post(f"/eval/document-runs/{busy.id}/cancel").json()["status"] == "cancelled"
    assert client.post("/eval/document-runs", json={"suite_id": suite["id"]}).status_code == 202


def test_expected_labels_never_enter_execute_search(api, monkeypatch):
    from app.retrieval import service
    client, document = api
    suite, _case, _payload = add_reviewed(api)
    original = service.execute_search
    recorded = []
    def execute(request, db, embedder_factory):
        recorded.append(request.model_dump())
        return original(request, db, embedder_factory)
    monkeypatch.setattr(service, "execute_search", execute)
    assert client.post("/eval/document-runs", json={"suite_id": suite["id"]}).status_code == 202
    assert recorded == [{"query": "How many results were initially obtained from Scopus?", "document_id": document.id, "top_k": 5, "answer_mode": "verified"}]


def test_deleted_document_is_not_correct_abstention(api, db_session):
    client, document = api
    suite, _case, _payload = add_reviewed(api, negative=True)
    db_session.delete(document)
    db_session.commit()
    response = client.post("/eval/document-runs", json={"suite_id": suite["id"]})
    assert response.status_code == 202
    results = client.get(f"/eval/document-runs/{response.json()['id']}/results").json()
    assert results[0]["status"] == "unavailable"
    assert results[0]["measurements"] == {}
