from types import SimpleNamespace

from app.evaluation import document_runs as runs
from app.evaluation.document_cases import CaseReadiness
from app.evaluation.document_schemas import CaseWrite
from app.retrieval.search import SearchResponse
from app.retrieval.service import SearchExecution


def test_provider_failed_negative_is_error_not_measured_abstention(monkeypatch):
    snapshot = CaseWrite(document_id="11111111-1111-1111-1111-111111111111", question="What private GPU was used?", expected_outcome="insufficient_evidence", review_rationale="Checked document scope.").model_dump(mode="json")
    snapshot.update(id="case", content_version=1, document_filename="source.pdf", review_state="reviewed", review_page_hashes={"1": "hash"})
    response = SearchResponse(query=snapshot["question"], hits=[], answer=None,
        quality={"status": "insufficient_evidence", "confidence": "weak", "reason": "No evidence", "evidence_count": 0, "best_score": 0, "best_source_score": 0, "best_keyword_overlap": 0, "best_section_intent": 0},
        retrieval_mode="lexical", retrieval_fallback_reason="Embedding provider unavailable", answer_mode="verified")
    monkeypatch.setattr(runs, "check_case_readiness", lambda *_args: CaseReadiness("ready"))
    monkeypatch.setattr(runs.search_service, "execute_search", lambda *_args: SearchExecution(response, {}, ()))
    result = runs._execute_case(SimpleNamespace(rollback=lambda: None), "run", snapshot, lambda: None)
    assert result.status == "error"
    assert result.measurements == {}
    assert "abstention" in " ".join(result.failure_reasons).lower()
    assert result.execution_snapshot["response"]["retrieval_mode"] == "lexical"
