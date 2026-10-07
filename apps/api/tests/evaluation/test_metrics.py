import pytest

from app.evaluation.metrics import (
    abstention_safety,
    citation_accuracy,
    hallucination_risk_score,
    hit_rate_at_k,
    mean_reciprocal_rank,
)


def test_hit_rate_at_k_returns_one_when_expected_id_is_in_top_k():
    assert hit_rate_at_k(["chunk-3"], ["chunk-1", "chunk-3", "chunk-5"], k=2) == 1.0


def test_hit_rate_at_k_returns_zero_when_expected_id_is_outside_top_k():
    assert hit_rate_at_k(["chunk-9"], ["chunk-1", "chunk-3", "chunk-5"], k=3) == 0.0


def test_mean_reciprocal_rank_returns_first_matching_rank_inverse():
    assert mean_reciprocal_rank(["chunk-5"], ["chunk-1", "chunk-3", "chunk-5"]) == 1 / 3


def test_citation_accuracy_scores_expected_citations():
    assert citation_accuracy(["a", "b"], ["a", "c"]) == 0.5
    assert citation_accuracy(["a"], ["a"]) == 1.0


def test_abstention_safety_rewards_expected_abstention():
    assert abstention_safety("insufficient_evidence", "insufficient_evidence") == 1.0
    assert abstention_safety("insufficient_evidence", "answerable") == 0.0


def test_hallucination_risk_score_clamps_range():
    assert hallucination_risk_score(unsupported_sentences=1, total_sentences=4) == 0.25
    assert hallucination_risk_score(unsupported_sentences=0, total_sentences=0) == 1.0


def test_citation_accuracy_penalizes_extra_unrelated_citations():
    assert citation_accuracy(["a"], ["a", "unrelated"]) == 0.5
    assert hallucination_risk_score(unsupported_sentences=9, total_sentences=4) == 1.0


@pytest.mark.parametrize("k", [0, -1])
def test_hit_rate_at_k_rejects_non_positive_k(k):
    with pytest.raises(ValueError, match="greater than zero"):
        hit_rate_at_k(["chunk-1"], ["chunk-1"], k=k)
