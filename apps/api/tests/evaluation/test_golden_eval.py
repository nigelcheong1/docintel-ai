from fastapi.testclient import TestClient

from app.evaluation.golden import run_golden_evaluation
from app.main import create_app


def test_golden_eval_includes_ocr_quality_cases():
    result = run_golden_evaluation()

    cases_by_id = {case.case_id: case for case in result.cases}

    assert "ocr-image-deferred-guidance" in cases_by_id
    assert "ocr-sparse-pdf-guidance" in cases_by_id
    assert cases_by_id["ocr-image-deferred-guidance"].passed is True
    assert cases_by_id["ocr-sparse-pdf-guidance"].passed is True
    assert result.summary.quality_dimensions["ocr_readiness"] == 2


def test_golden_eval_reports_verified_dimensions():
    result = run_golden_evaluation()

    assert "verified_answers" in result.summary.quality_dimensions
    assert "citation_accuracy" in result.summary.quality_dimensions
    assert "table_qa" in result.summary.quality_dimensions
    assert "multi_hop_qa" in result.summary.quality_dimensions
    assert result.summary.quality_dimensions["hallucination_risk"] >= 1


def test_golden_eval_reports_measured_verified_scorecard():
    result = run_golden_evaluation()

    metrics = result.summary.verified_metrics
    assert {"citation_accuracy", "retrieval_recall_at_5", "evidence_pack_coverage", "verifier_pass_rate",
            "abstention_safety", "hallucination_risk", "table_qa_pass_rate", "multi_hop_qa_pass_rate"} <= metrics.keys()
    assert all(0.0 <= value <= 1.0 for value in metrics.values())
    assert metrics["abstention_safety"] == 1.0
    table_case = next(case for case in result.cases if case.quality_dimension == "table_qa")
    assert table_case.verification_status == "verified"
    assert table_case.metrics["retrieval_recall_at_5"] == 1.0


def test_fixture_metrics_detect_dropped_retrieval_evidence(monkeypatch):
    import app.evaluation.golden as golden

    monkeypatch.setattr(golden, "rerank_hits", lambda _query, _hits: [])

    result = run_golden_evaluation()

    assert result.summary.verified_metrics["retrieval_recall_at_5"] == 0.0
    assert result.summary.verified_metrics["verifier_pass_rate"] == 0.0


def test_golden_eval_endpoint_reports_universal_document_qa_coverage():
    client = TestClient(create_app())

    response = client.get("/eval/golden")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "universal-document-qa-golden"
    assert body["summary"]["total_cases"] == 21
    assert body["summary"]["passed_cases"] == body["summary"]["total_cases"]
    assert body["summary"]["pass_rate"] == 1.0
    assert body["summary"]["quality_dimensions"] == {
        "abstention_safety": 1,
        "answer_quality": 12,
        "citation_accuracy": 1,
        "hallucination_risk": 1,
        "multi_hop_qa": 1,
        "ocr_readiness": 2,
        "parse_quality": 1,
        "table_qa": 1,
        "verified_answers": 1,
    }
    assert body["summary"]["document_types"] == {
        "contract": 2,
        "invoice": 2,
        "ocr_readiness": 2,
        "parse_quality": 1,
        "report": 2,
        "research_paper": 10,
        "resume": 2,
    }
    assert {case["document_type"] for case in body["cases"]} == {
        "contract",
        "invoice",
        "ocr_readiness",
        "parse_quality",
        "report",
        "research_paper",
        "resume",
    }
    total_due_case = next(case for case in body["cases"] if case["case_id"] == "research-hard-negative-total-due")
    assert total_due_case["passed"] is True
    assert total_due_case["actual_status"] == "insufficient_evidence"
    assert total_due_case["answer_preview"] is None
    assert total_due_case["citation_count"] == 0
    assert "chunk" not in total_due_case["quality_reason"].lower()
    assert "invoice" in " ".join(total_due_case["failure_reasons"] + [total_due_case["quality_reason"]]).lower()
    parse_quality_case = next(case for case in body["cases"] if case["case_id"] == "parse-quality-low-text-guidance")
    assert parse_quality_case["passed"] is True
    assert parse_quality_case["query_intent"] == "parse_quality"
    assert "OCR" in parse_quality_case["answer_preview"]
    ocr_image_case = next(case for case in body["cases"] if case["case_id"] == "ocr-image-deferred-guidance")
    assert ocr_image_case["passed"] is True
    assert ocr_image_case["query_intent"] == "ocr_readiness"
    assert "retry" in ocr_image_case["quality_reason"].lower()


def test_golden_eval_endpoint_exposes_actionable_case_details():
    client = TestClient(create_app())

    response = client.get("/eval/golden")

    body = response.json()
    methods_case = next(case for case in body["cases"] if case["case_id"] == "research-methods")
    assert methods_case["query_intent"] == "methods"
    assert methods_case["confidence"] in {"strong", "moderate"}
    assert methods_case["citation_count"] >= 1
    assert "vision-language" in methods_case["answer_preview"].lower()
    assert methods_case["expected_terms"] == ["vision-language", "encoder"]
