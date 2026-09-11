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


def citation_accuracy(expected_chunk_ids: list[str], cited_chunk_ids: list[str]) -> float:
    expected = set(expected_chunk_ids)
    if not expected:
        return 1.0 if not cited_chunk_ids else 0.0
    return len(expected.intersection(cited_chunk_ids)) / len(expected)


def abstention_safety(expected_status: str, actual_status: str) -> float:
    if expected_status != "insufficient_evidence":
        return 1.0
    return 1.0 if actual_status == "insufficient_evidence" else 0.0


def hallucination_risk_score(unsupported_sentences: int, total_sentences: int) -> float:
    if total_sentences <= 0:
        return 1.0
    return max(0.0, min(1.0, unsupported_sentences / total_sentences))
