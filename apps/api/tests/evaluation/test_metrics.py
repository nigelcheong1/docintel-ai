import pytest

from app.evaluation.metrics import hit_rate_at_k, mean_reciprocal_rank


def test_hit_rate_at_k_returns_one_when_expected_id_is_in_top_k():
    assert hit_rate_at_k(["chunk-3"], ["chunk-1", "chunk-3", "chunk-5"], k=2) == 1.0


def test_hit_rate_at_k_returns_zero_when_expected_id_is_outside_top_k():
    assert hit_rate_at_k(["chunk-9"], ["chunk-1", "chunk-3", "chunk-5"], k=3) == 0.0


def test_mean_reciprocal_rank_returns_first_matching_rank_inverse():
    assert mean_reciprocal_rank(["chunk-5"], ["chunk-1", "chunk-3", "chunk-5"]) == 1 / 3


@pytest.mark.parametrize("k", [0, -1])
def test_hit_rate_at_k_rejects_non_positive_k(k):
    with pytest.raises(ValueError, match="greater than zero"):
        hit_rate_at_k(["chunk-1"], ["chunk-1"], k=k)
