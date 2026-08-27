from collections import defaultdict
from collections.abc import Sequence

from app.db.models import RetrievalResult
from app.evaluation.metrics import hit_rate_at_k, mean_reciprocal_rank


def aggregate_retrieval_metrics(results: Sequence[RetrievalResult]) -> dict[str, int | float]:
    grouped: dict[str, list[RetrievalResult]] = defaultdict(list)
    for result in results:
        grouped[result.question_id].append(result)

    if not grouped:
        return {
            "evaluated_questions": 0,
            "hit_rate_at_5": 0.0,
            "mean_reciprocal_rank": 0.0,
        }

    hit_rates: list[float] = []
    reciprocal_ranks: list[float] = []
    for question_id, question_results in grouped.items():
        expected_chunk_ids = [result.chunk_id for result in question_results]
        highest_rank = max(result.rank for result in question_results)
        ranked_chunk_ids = [f"missing:{question_id}:{rank}" for rank in range(1, highest_rank + 1)]
        for result in question_results:
            ranked_chunk_ids[result.rank - 1] = result.chunk_id

        hit_rates.append(hit_rate_at_k(expected_chunk_ids, ranked_chunk_ids, k=5))
        reciprocal_ranks.append(mean_reciprocal_rank(expected_chunk_ids, ranked_chunk_ids))

    question_count = len(grouped)
    return {
        "evaluated_questions": question_count,
        "hit_rate_at_5": sum(hit_rates) / question_count,
        "mean_reciprocal_rank": sum(reciprocal_ranks) / question_count,
    }
