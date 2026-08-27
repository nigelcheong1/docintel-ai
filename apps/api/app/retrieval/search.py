from dataclasses import dataclass


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    document_id: str
    document_filename: str
    page_number: int
    chunk_index: int
    text: str
    score: float


def build_snippet(text: str, max_chars: int = 260) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 3].rstrip() + "..."


def cosine_distance_to_score(distance: float) -> float:
    return max(0.0, min(1.0, 1.0 - distance))
