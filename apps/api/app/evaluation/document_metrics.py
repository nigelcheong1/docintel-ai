import re
from typing import Literal

from app.evaluation.document_cases import ResolvedAnchor, join_source_texts, normalize_source
from app.evaluation.document_schemas import CaseWrite, ExpectedFact, Measurement, ResultRead
from app.retrieval.search import SearchHit
from app.retrieval.service import SearchExecution

SCOPES = {
    "outcome_match": "Successfully executed reviewed cases",
    "fact_match": "Required approved fact patterns",
    "retrieval_anchor_recall_at_5": "Required anchors across top five reranked candidates per subquery, before pack selection",
    "citation_precision": "Unique cited chunks matching reviewed anchors",
    "citation_anchor_coverage": "Required anchors represented by cited source text",
    "pack_anchor_coverage": "Required anchors represented in selected evidence",
    "abstention_match": "Successfully executed reviewed negative cases",
    "checker_support": "Sentences accepted by the deterministic evidence checker",
    "latency": "Mean execution milliseconds per successfully executed case",
    "table_case_pass_rate": "Automatically passing reviewed cases tagged table",
    "multi_part_case_pass_rate": "Automatically passing reviewed cases tagged multi-part",
}
_NEGATION = {"no", "not", "never", "without", "neither", "nor"}


def make_measurement(numerator: float, denominator: int, unit: Literal["ratio", "ms"], scope: str) -> Measurement:
    return Measurement(value=numerator / denominator if denominator else None, numerator=numerator, denominator=denominator, unit=unit, scope=scope)


def _tokens(text: str) -> list[str]:
    text = re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", text.lower())
    text = re.sub(r"n['\u2019]t\b", " not", text)
    return re.findall(r"[a-z0-9]+(?:\.\d+)?", text)


def fact_matches(answer: str, fact: ExpectedFact) -> bool:
    sentences = re.split(r"(?<!\bal\.)(?<=[.!?])\s+", answer, flags=re.IGNORECASE)
    for pattern in [fact.pattern, *fact.alternatives]:
        expected = _tokens(pattern)
        if not expected:
            continue
        for sentence in sentences:
            actual = _tokens(sentence)
            if bool(set(expected) & _NEGATION) != bool(set(actual) & _NEGATION):
                continue
            if any(actual[start:start + len(expected)] == expected for start in range(len(actual) - len(expected) + 1)):
                return True
    return False


def _anchor_covered(anchor: ResolvedAnchor, hits: list[SearchHit]) -> bool:
    unique = {hit.chunk_id: hit for hit in hits if hit.page_number == anchor.page_number and hit.chunk_id in anchor.chunk_ids}
    if not set(anchor.chunk_ids) <= unique.keys():
        return False
    text = join_source_texts([hit.text for hit in sorted(unique.values(), key=lambda item: item.chunk_index)])
    return normalize_source(anchor.quote) in text


def score_case(case: CaseWrite, anchors: tuple[ResolvedAnchor, ...], execution: SearchExecution, duration_ms: float) -> dict[str, Measurement]:
    response = execution.response
    answer = response.answer
    answer_text = answer.summary if answer else ""
    citation_ids = {citation.chunk_id for citation in answer.citations} if answer else set()
    negative = case.expected_outcome == "insufficient_evidence"
    actual_negative = response.quality.status == "insufficient_evidence" and answer is None and not citation_ids
    actual_positive = response.quality.status == "answerable" and answer is not None
    trace = [hit for candidates in execution.candidates_by_subquery.values() for hit in candidates[:5]]
    selected = list(execution.selected_evidence)
    all_hits = {hit.chunk_id: hit for hit in [*trace, *selected]}
    cited = [all_hits[chunk_id] for chunk_id in citation_ids if chunk_id in all_hits]
    anchor_ids = {chunk_id for anchor in anchors for chunk_id in anchor.chunk_ids}
    sentences = response.verification.sentences if answer and response.verification else []
    counts = {
        "outcome_match": (int(actual_negative if negative else actual_positive), 1),
        "fact_match": (sum(fact_matches(answer_text, fact) for fact in case.facts) if not negative else 0, len(case.facts) if not negative else 0),
        "retrieval_anchor_recall_at_5": (sum(_anchor_covered(anchor, trace) for anchor in anchors) if not negative else 0, len(anchors) if not negative else 0),
        "citation_precision": (len(citation_ids & anchor_ids) if not negative else 0, len(citation_ids) if not negative else 0),
        "citation_anchor_coverage": (sum(_anchor_covered(anchor, cited) for anchor in anchors) if not negative else 0, len(anchors) if not negative else 0),
        "pack_anchor_coverage": (sum(_anchor_covered(anchor, selected) for anchor in anchors) if not negative else 0, len(anchors) if not negative else 0),
        "abstention_match": (int(actual_negative) if negative else 0, int(negative)),
        "checker_support": (sum(sentence.status == "verified" for sentence in sentences), len(sentences)),
        "latency": (duration_ms, 1),
    }
    return {key: make_measurement(numerator, denominator, "ms" if key == "latency" else "ratio", SCOPES[key]) for key, (numerator, denominator) in counts.items()}


def case_failure_reasons(case: CaseWrite, measurements: dict[str, Measurement]) -> list[str]:
    required = ["outcome_match", "abstention_match"] if case.expected_outcome == "insufficient_evidence" else ["outcome_match", "fact_match", "retrieval_anchor_recall_at_5", "citation_precision", "citation_anchor_coverage", "pack_anchor_coverage", "checker_support"]
    return [f"{key.replace('_', ' ')} did not pass every required check." for key in required if key not in measurements or measurements[key].value != 1]


def aggregate_case_measurements(results: list[ResultRead]) -> dict[str, Measurement]:
    eligible = [result for result in results if result.status in {"pass", "fail"}]
    aggregates = {}
    for key, scope in SCOPES.items():
        if key in {"table_case_pass_rate", "multi_part_case_pass_rate"}:
            tag = "table" if key == "table_case_pass_rate" else "multi-part"
            subset = [result for result in eligible if tag in result.case_snapshot.get("tags", [])]
            aggregates[key] = make_measurement(sum(result.status == "pass" for result in subset), len(subset), "ratio", scope)
        else:
            values = [result.measurements[key] for result in eligible if key in result.measurements]
            aggregates[key] = make_measurement(sum(item.numerator for item in values), sum(item.denominator for item in values), "ms" if key == "latency" else "ratio", scope)
    return aggregates
