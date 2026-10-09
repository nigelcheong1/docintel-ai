from dataclasses import replace
from datetime import UTC, datetime

import pytest

from app.evaluation.document_cases import ResolvedAnchor
from app.evaluation.document_schemas import CaseWrite, ExpectedFact, ResultRead
from app.retrieval.answers import AnswerCitation, ExtractiveAnswer
from app.retrieval.search import EvidenceVerificationRead, SearchHit, SearchResponse, SentenceSupportRead
from app.retrieval.service import SearchExecution


def metrics():
    from app.evaluation import document_metrics
    return document_metrics


def case(**updates):
    payload = dict(document_id="11111111-1111-1111-1111-111111111111", question="How many Scopus results?", expected_outcome="answerable", facts=[{"pattern": "Scopus returned 2366 records"}], anchors=[{"page_number": 1, "quote": "Scopus returned 2366 records."}])
    payload.update(updates)
    return CaseWrite(**payload)


def hit(key="one", page=1, text="Scopus returned 2366 records.", index=0):
    return SearchHit(chunk_id=key, document_id="11111111-1111-1111-1111-111111111111", document_filename="source.pdf", page_number=page, chunk_index=index, text=text, score=0.9, source_score=0.9)


def execution():
    source = hit()
    response = SearchResponse(query="How many Scopus results?", hits=[], answer=ExtractiveAnswer(summary=source.text, citations=[AnswerCitation(chunk_id="one", document_filename="source.pdf", page_number=1)]), quality={"status": "answerable", "confidence": "strong", "reason": "Supported", "evidence_count": 1, "best_score": 0.9, "best_source_score": 0.9, "best_keyword_overlap": 0.9, "best_section_intent": 0.9}, retrieval_mode="hybrid", answer_mode="verified", verification=EvidenceVerificationRead(status="verified", sentences=[SentenceSupportRead(sentence=source.text, status="verified", supporting_chunk_ids=["one"], support_score=1, missing_terms=[], missing_numbers=[])], unsupported_sentence_count=0, removed_sentence_count=0, hallucination_risk=0, reason="Supported"))
    return SearchExecution(response, {response.query: (source,)}, (source,))


def test_zero_denominator_is_not_evaluated():
    result = metrics().make_measurement(0, 0, "ratio", "anchors")
    assert result.value is None
    assert result.denominator == 0


@pytest.mark.parametrize("answer,pattern,want", [
    ("Scopus returned 2,366 records.", "scopus returned 2366 records", True),
    ("Scopus returned 2092 records. WOS returned 2366 records.", "Scopus returned 2366 records", False),
    ("Scopus did not return 2366 records.", "Scopus returned 2366 records", False),
    ("It is not true that Scopus returned 2366 records.", "Scopus returned 2366 records", False),
    ("The study does not use a GPU.", "uses a GPU", False),
    ("There were 12366 records.", "2366 records", False),
])
def test_fact_matching_preserves_quantity_and_negation(answer, pattern, want):
    assert metrics().fact_matches(answer, ExpectedFact(pattern=pattern)) is want


def test_explicit_alternative_matches():
    assert metrics().fact_matches("Scopus yielded 2366 records.", ExpectedFact(pattern="Scopus returned 2366 records", alternatives=["Scopus yielded 2366 records"]))


def test_partial_answer_counts_only_one_of_two_facts():
    result = metrics().score_case(case(facts=[{"pattern": "Scopus returned 2366 records"}, {"pattern": "2092 remained"}]), (ResolvedAnchor(1, "Scopus returned 2366 records.", ("one",)),), execution(), 10)
    assert result["fact_match"].numerator == 1
    assert result["fact_match"].denominator == 2
    assert metrics().case_failure_reasons(case(), result)


def test_trace_recall_differs_from_selected_pack_and_citations():
    current = execution()
    second = hit("two", 2, "After removal, 2092 remained.")
    current = replace(current, candidates_by_subquery={"first": current.selected_evidence, "second": (second,)})
    anchors = (ResolvedAnchor(1, "Scopus returned 2366 records.", ("one",)), ResolvedAnchor(2, second.text, ("two",)))
    result = metrics().score_case(case(), anchors, current, 10)
    assert result["retrieval_anchor_recall_at_5"].value == 1
    assert result["pack_anchor_coverage"].value == 0.5
    assert result["citation_precision"].value == 1
    assert result["citation_anchor_coverage"].value == 0.5


def test_extra_citation_lowers_precision():
    current = execution()
    current.response.answer.citations.append(AnswerCitation(chunk_id="unrelated", document_filename="source.pdf", page_number=8))
    result = metrics().score_case(case(), (ResolvedAnchor(1, hit().text, ("one",)),), current, 10)
    assert result["citation_precision"].numerator == 1
    assert result["citation_precision"].denominator == 2


def test_crossing_quote_needs_all_chunks():
    current = execution()
    first = hit(text="Scopus returned")
    second = hit("two", text="2366 records.", index=1)
    anchors = (ResolvedAnchor(1, "Scopus returned 2366 records.", ("one", "two")),)
    current = replace(current, candidates_by_subquery={"count": (first, second)}, selected_evidence=(first,))
    result = metrics().score_case(case(), anchors, current, 10)
    assert result["retrieval_anchor_recall_at_5"].value == 1
    assert result["pack_anchor_coverage"].value == 0


def test_negative_without_answer_has_no_fact_anchor_or_checker_score():
    current = execution()
    current.response.answer = None
    current.response.quality.status = "insufficient_evidence"
    current.response.verification = None
    negative = case(expected_outcome="insufficient_evidence", facts=[], anchors=[], review_rationale="Scope checked")
    result = metrics().score_case(negative, (), current, 10)
    assert result["abstention_match"].value == 1
    assert result["fact_match"].value is None
    assert result["retrieval_anchor_recall_at_5"].value is None
    assert result["checker_support"].value is None
    assert metrics().case_failure_reasons(negative, result) == []


def saved_result(measurements, tags=None):
    return ResultRead(id="result", run_id="run", case_id_snapshot="case", case_version=1, case_snapshot={"tags": tags or []}, execution_snapshot={}, measurements=measurements, failure_reasons=[], status="pass", duration_ms=10, human_assessment=None, assessment_note="", assessed_at=None, created_at=datetime.now(UTC))


def test_aggregation_uses_denominators_and_null_tag_subsets():
    first = saved_result({"fact_match": metrics().make_measurement(1, 1, "ratio", "required facts")})
    second = saved_result({"fact_match": metrics().make_measurement(0, 3, "ratio", "required facts")})
    result = metrics().aggregate_case_measurements([first, second])
    assert result["fact_match"].value == 0.25
    assert result["fact_match"].denominator == 4
    assert result["table_case_pass_rate"].value is None
    assert result["multi_part_case_pass_rate"].value is None


def test_error_cannot_count_as_correct_negative():
    error = saved_result({"abstention_match": metrics().make_measurement(1, 1, "ratio", "negative cases")}).model_copy(update={"status": "error"})
    assert metrics().aggregate_case_measurements([error])["abstention_match"].value is None
