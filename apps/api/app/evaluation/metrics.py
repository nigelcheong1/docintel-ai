def hit_rate_at_k(expected_chunk_ids: list[str], ranked_chunk_ids: list[str], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be greater than zero.")
    expected = set(expected_chunk_ids)
    retrieved = set(ranked_chunk_ids[:k])
    return 1.0 if expected.intersection(retrieved) else 0.0


def mean_reciprocal_rank(expected_chunk_ids: list[str], ranked_chunk_ids: list[str]) -> float:
    expected = set(expected_chunk_ids)
    for index, chunk_id in enumerate(ranked_chunk_ids, start=1):
        if chunk_id in expected:
            return 1.0 / index
    return 0.0
