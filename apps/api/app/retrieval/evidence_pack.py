from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.retrieval.search import SearchHit, build_snippet

EvidenceRetrievalMode = Literal["hybrid", "vector", "lexical"]


@dataclass(frozen=True)
class EvidenceItem:
    chunk_id: str
    document_id: str
    document_filename: str
    page_number: int
    chunk_index: int
    text: str
    snippet: str
    score: float
    source_score: float
    ranking_signals: dict[str, float]
    section_heading: str | None
    subquery: str
    support_score: float


@dataclass(frozen=True)
class RejectedEvidence:
    chunk_id: str
    page_number: int
    subquery: str
    reason: str


@dataclass(frozen=True)
class EvidencePack:
    question: str
    rewritten_query: str
    subqueries: list[str]
    items: list[EvidenceItem]
    rejected: list[RejectedEvidence] = field(default_factory=list)
    retrieval_mode: EvidenceRetrievalMode = "hybrid"
    retrieval_fallback_reason: str | None = None
    selected_chunk_count: int = 0
    selected_page_count: int = 0
    average_support_score: float = 0.0
    is_multi_hop: bool = False


def _support_score(hit: SearchHit) -> float:
    keyword = hit.ranking_signals.get("keyword_overlap", 0.0)
    section = hit.ranking_signals.get("section_intent", 0.0)
    return round(max(hit.score, hit.source_score, keyword, section), 6)


def _item_from_hit(hit: SearchHit, subquery: str) -> EvidenceItem:
    return EvidenceItem(
        chunk_id=hit.chunk_id,
        document_id=hit.document_id,
        document_filename=hit.document_filename,
        page_number=hit.page_number,
        chunk_index=hit.chunk_index,
        text=hit.text,
        snippet=build_snippet(hit.text),
        score=hit.score,
        source_score=hit.source_score,
        ranking_signals=dict(hit.ranking_signals),
        section_heading=hit.section_heading,
        subquery=subquery,
        support_score=_support_score(hit),
    )


def build_evidence_pack(
    question: str,
    hits_by_subquery: dict[str, list[SearchHit]],
    retrieval_mode: EvidenceRetrievalMode,
    fallback_reason: str | None = None,
    *,
    rewritten_query: str | None = None,
    is_multi_hop: bool = False,
    max_items: int = 5,
) -> EvidencePack:
    selected: list[EvidenceItem] = []
    rejected: list[RejectedEvidence] = []
    seen_chunks: set[str] = set()
    used_pages: set[int] = set()
    ranked_candidates: list[tuple[str, SearchHit]] = []
    for subquery, hits in hits_by_subquery.items():
        ranked_candidates.extend((subquery, hit) for hit in hits)

    ranked_candidates.sort(key=lambda pair: (pair[1].score, pair[1].source_score), reverse=True)

    deferred_same_page: list[tuple[str, SearchHit]] = []
    for subquery, hit in ranked_candidates:
        if hit.chunk_id in seen_chunks:
            rejected.append(RejectedEvidence(hit.chunk_id, hit.page_number, subquery, "Duplicate chunk already selected."))
            continue
        if len(selected) >= max_items:
            rejected.append(RejectedEvidence(hit.chunk_id, hit.page_number, subquery, "Evidence pack context limit reached."))
            continue
        if hit.page_number in used_pages and len(selected) + len(deferred_same_page) < len(ranked_candidates):
            deferred_same_page.append((subquery, hit))
            continue
        selected.append(_item_from_hit(hit, subquery))
        seen_chunks.add(hit.chunk_id)
        used_pages.add(hit.page_number)

    for subquery, hit in deferred_same_page:
        if len(selected) >= max_items:
            rejected.append(
                RejectedEvidence(hit.chunk_id, hit.page_number, subquery, "Lower priority evidence from an already selected page.")
            )
            continue
        if hit.chunk_id in seen_chunks:
            rejected.append(RejectedEvidence(hit.chunk_id, hit.page_number, subquery, "Duplicate chunk already selected."))
            continue
        selected.append(_item_from_hit(hit, subquery))
        seen_chunks.add(hit.chunk_id)
        used_pages.add(hit.page_number)

    average = sum(item.support_score for item in selected) / len(selected) if selected else 0.0
    return EvidencePack(
        question=question,
        rewritten_query=rewritten_query or question,
        subqueries=list(hits_by_subquery.keys()),
        items=selected,
        rejected=rejected[:5],
        retrieval_mode=retrieval_mode,
        retrieval_fallback_reason=fallback_reason,
        selected_chunk_count=len(selected),
        selected_page_count=len({item.page_number for item in selected}),
        average_support_score=round(average, 6),
        is_multi_hop=is_multi_hop,
    )
