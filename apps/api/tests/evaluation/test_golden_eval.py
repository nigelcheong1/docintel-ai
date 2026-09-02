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


def test_golden_eval_endpoint_reports_universal_document_qa_coverage():
    client = TestClient(create_app())

    response = client.get("/eval/golden")

    assert response.status_code == 200
    body = response.json()
    assert body["name"] == "universal-document-qa-golden"
    assert body["summary"]["total_cases"] == 16
    assert body["summary"]["passed_cases"] == body["summary"]["total_cases"]
    assert body["summary"]["pass_rate"] == 1.0
    assert body["summary"]["quality_dimensions"] == {
        "abstention_safety": 1,
        "answer_quality": 12,
        "ocr_readiness": 2,
        "parse_quality": 1,
    }
    assert body["summary"]["document_types"] == {
        "contract": 2,
        "invoice": 2,
        "ocr_readiness": 2,
        "parse_quality": 1,
        "report": 2,
        "research_paper": 5,
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
