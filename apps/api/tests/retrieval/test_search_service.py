import pytest
from fastapi.testclient import TestClient

from app.db.models import Document, DocumentStatus
from app.db.session import get_db
from app.documents.router import get_embedding_provider_factory
from app.main import create_app
from app.retrieval.search import RetrievalMode, SearchHit, SearchRequest


def service():
    from app.retrieval import service as search_service
    return search_service


class Embedder:
    def embed_texts(self, texts):
        return [[0.0] * 384 for _ in texts]


def hit(index):
    return SearchHit(chunk_id=f"chunk-{index}", document_id="document-1", document_filename="paper.pdf", page_number=1, chunk_index=index, text="Scopus returned 2366 records.", score=0.99 - index / 100, source_score=0.99 - index / 100)


@pytest.mark.parametrize("answer_mode", ["standard", "verified"])
def test_search_route_delegates_to_shared_service(monkeypatch, answer_mode):
    module = service()
    monkeypatch.setattr(module, "hybrid_search_chunks", lambda *_args, **_kwargs: ([hit(0)], RetrievalMode(mode="hybrid")))
    request = SearchRequest(query="How many records did Scopus return?", answer_mode=answer_mode)
    expected = module.execute_search(request, object(), lambda: Embedder())
    app = create_app()
    app.dependency_overrides[get_db] = lambda: object()
    app.dependency_overrides[get_embedding_provider_factory] = lambda: lambda: Embedder()
    response = TestClient(app).post("/search", json=request.model_dump())
    assert response.status_code == 200
    assert response.json() == expected.response.model_dump(mode="json")
    assert response.json()["retrieval_mode"] == "hybrid"


def test_trace_is_top_five_per_subquery_before_pack_selection(monkeypatch):
    module = service()
    monkeypatch.setattr(module, "hybrid_search_chunks", lambda *_args, **_kwargs: ([hit(i) for i in range(7)], RetrievalMode(mode="hybrid")))
    execution = module.execute_search(SearchRequest(query="How many records did Scopus return?", answer_mode="verified", top_k=2), object(), lambda: Embedder())
    trace = next(iter(execution.candidates_by_subquery.values()))
    assert len(trace) == 5
    assert len(execution.selected_evidence) == 1
    assert len({item.chunk_id for item in trace} - {item.chunk_id for item in execution.selected_evidence}) == 4
    assert trace[0].text == "Scopus returned 2366 records."


def test_fallback_reason_is_retained_in_shared_execution(monkeypatch):
    module = service()
    class BrokenEmbedder:
        def embed_texts(self, texts):
            raise RuntimeError("Provider unavailable")
    def retrieve(_db, embedding, _query, *_args, **kwargs):
        assert embedding is None
        return [hit(0)], RetrievalMode(mode="lexical", fallback_reason=kwargs["fallback_reason"])
    monkeypatch.setattr(module, "hybrid_search_chunks", retrieve)
    execution = module.execute_search(SearchRequest(query="How many records did Scopus return?", answer_mode="verified"), object(), lambda: BrokenEmbedder())
    assert execution.response.retrieval_mode == "lexical"
    assert "Provider unavailable" in execution.response.retrieval_fallback_reason


def test_empty_document_has_empty_trace_without_embedding():
    document = Document(id="document-1", filename="empty.pdf", stored_filename="empty.pdf", mime_type="application/pdf", file_path="empty.pdf", status=DocumentStatus.DEFERRED_OCR)
    class Database:
        def get(self, _model, _id):
            return document
    def no_embedder():
        pytest.fail("An unindexed document must not call embeddings")
    execution = service().execute_search(SearchRequest(query="What does this say?", document_id=document.id, answer_mode="verified"), Database(), no_embedder)
    assert execution.response.answer is None
    assert execution.candidates_by_subquery == {}
    assert execution.selected_evidence == ()
