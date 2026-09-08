import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, ChunkEmbedding, Document, Page
from app.retrieval.answers import AnswerQuality, ExtractiveAnswer

_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_LEXICAL_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "does",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "what",
    "when",
    "who",
    "with",
}


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    document_id: str
    document_filename: str
    page_number: int
    chunk_index: int
    text: str
    score: float
    source_score: float
    ranking_signals: dict[str, float] = field(default_factory=dict)
    section_heading: str | None = None


@dataclass(frozen=True)
class RetrievalMode:
    mode: Literal["hybrid", "vector", "lexical"]
    fallback_reason: str | None = None


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    document_id: str | None = None


class SearchHitRead(BaseModel):
    chunk_id: str
    document_id: str
    document_filename: str
    page_number: int
    chunk_index: int
    page_image_url: str
    document_page_url: str
    score: float
    source_score: float
    ranking_signals: dict[str, float]
    snippet: str
    section_heading: str | None = None
    result_role: Literal["answer_evidence", "related"] = "related"


class SearchDiagnostics(BaseModel):
    document_type: str | None
    query_intent: str
    quality_status: Literal["answerable", "insufficient_evidence"]
    confidence: Literal["strong", "moderate", "weak"]
    reason: str
    answer_chunk_ids: list[str]
    answer_evidence_count: int
    related_result_count: int
    top_rejected_reasons: list[str]


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHitRead]
    answer: ExtractiveAnswer | None
    quality: AnswerQuality
    document_type: str | None = None
    query_intent: str = "evidence_search"
    diagnostics: SearchDiagnostics | None = None
    retrieval_mode: Literal["hybrid", "vector", "lexical"] = "vector"
    retrieval_fallback_reason: str | None = None


def build_snippet(text: str, max_chars: int = 260) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 3].rstrip() + "..."


def format_search_hit(hit: SearchHit, answer_chunk_ids: set[str] | None = None) -> SearchHitRead:
    answer_chunk_ids = answer_chunk_ids or set()
    return SearchHitRead(
        chunk_id=hit.chunk_id,
        document_id=hit.document_id,
        document_filename=hit.document_filename,
        page_number=hit.page_number,
        chunk_index=hit.chunk_index,
        page_image_url=f"/documents/{hit.document_id}/pages/{hit.page_number}/image",
        document_page_url=f"/documents/{hit.document_id}?page={hit.page_number}&chunk={hit.chunk_id}",
        score=hit.score,
        source_score=hit.source_score,
        ranking_signals=hit.ranking_signals,
        snippet=build_snippet(hit.text),
        section_heading=hit.section_heading,
        result_role="answer_evidence" if hit.chunk_id in answer_chunk_ids else "related",
    )


def cosine_distance_to_score(distance: float) -> float:
    return max(0.0, min(1.0, 1.0 - distance))


def _words(text: str) -> set[str]:
    return {word for word in _WORD_PATTERN.findall(text.lower()) if word not in _LEXICAL_STOPWORDS and len(word) > 1}


def _lexical_score(query: str, text: str, section_heading: str | None) -> float:
    query_words = _words(query)
    if not query_words:
        return 0.0
    searchable_text = " ".join(part for part in (section_heading, text) if part)
    searchable_words = _words(searchable_text)
    if not searchable_words:
        return 0.0
    overlap = len(query_words.intersection(searchable_words)) / len(query_words)
    return round(max(0.0, min(1.0, overlap)), 6)


def _search_hit_from_models(chunk: Chunk, page: Page, document: Document, score: float) -> SearchHit:
    section_heading = chunk.layout.get("section_heading") if isinstance(chunk.layout, dict) else None
    return SearchHit(
        chunk_id=chunk.id,
        document_id=document.id,
        document_filename=document.filename,
        page_number=page.page_number,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        score=score,
        source_score=score,
        ranking_signals={"lexical_score": score},
        section_heading=section_heading if isinstance(section_heading, str) else None,
    )


def lexical_search_chunks(
    db: Session,
    query: str,
    top_k: int,
    document_id: str | None = None,
) -> list[SearchHit]:
    if not hasattr(db, "execute"):
        return []
    statement = (
        select(Chunk, Page, Document)
        .join(Page, Page.id == Chunk.page_id)
        .join(Document, Document.id == Chunk.document_id)
        .order_by(Document.created_at.desc(), Chunk.chunk_index.asc())
    )
    if document_id is not None:
        statement = statement.where(Document.id == document_id)

    scored_hits: list[SearchHit] = []
    for chunk, page, document in db.execute(statement):
        section_heading = chunk.layout.get("section_heading") if isinstance(chunk.layout, dict) else None
        lexical_score = _lexical_score(query, chunk.text, section_heading if isinstance(section_heading, str) else None)
        if lexical_score <= 0:
            continue
        scored_hits.append(_search_hit_from_models(chunk, page, document, lexical_score))
    return sorted(scored_hits, key=lambda hit: (hit.source_score, -hit.chunk_index), reverse=True)[:top_k]


def search_chunks(
    db: Session,
    query_embedding: list[float],
    top_k: int,
    document_id: str | None = None,
) -> list[SearchHit]:
    distance = ChunkEmbedding.embedding.cosine_distance(query_embedding).label("distance")
    statement = (
        select(Chunk, Page, Document, distance)
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == Chunk.id)
        .join(Page, Page.id == Chunk.page_id)
        .join(Document, Document.id == Chunk.document_id)
        .order_by(distance)
        .limit(top_k)
    )
    if document_id is not None:
        statement = statement.where(Document.id == document_id)

    hits: list[SearchHit] = []
    for chunk, page, document, raw_distance in db.execute(statement):
        section_heading = chunk.layout.get("section_heading") if isinstance(chunk.layout, dict) else None
        source_score = cosine_distance_to_score(float(raw_distance))
        hits.append(
            SearchHit(
                chunk_id=chunk.id,
                document_id=document.id,
                document_filename=document.filename,
                page_number=page.page_number,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                score=source_score,
                source_score=source_score,
                section_heading=section_heading if isinstance(section_heading, str) else None,
            )
        )
    return hits


def _tag_vector_hit(hit: SearchHit) -> SearchHit:
    ranking_signals = dict(hit.ranking_signals)
    ranking_signals.setdefault("vector_score", hit.source_score)
    ranking_signals.setdefault("lexical_score", 0.0)
    return replace(hit, ranking_signals=ranking_signals)


def _merge_hybrid_hits(vector_hits: Sequence[SearchHit], lexical_hits: Sequence[SearchHit]) -> list[SearchHit]:
    merged: dict[str, SearchHit] = {}
    for hit in vector_hits:
        merged[hit.chunk_id] = _tag_vector_hit(hit)
    for hit in lexical_hits:
        existing = merged.get(hit.chunk_id)
        lexical_score = hit.ranking_signals.get("lexical_score", hit.source_score)
        if existing is None:
            ranking_signals = dict(hit.ranking_signals)
            ranking_signals.setdefault("vector_score", 0.0)
            ranking_signals["lexical_score"] = lexical_score
            merged[hit.chunk_id] = replace(hit, ranking_signals=ranking_signals)
            continue
        ranking_signals = dict(existing.ranking_signals)
        ranking_signals["lexical_score"] = lexical_score
        merged[hit.chunk_id] = replace(
            existing,
            source_score=max(existing.source_score, lexical_score),
            score=max(existing.score, lexical_score),
            ranking_signals=ranking_signals,
        )
    return sorted(merged.values(), key=lambda hit: (hit.source_score, -hit.chunk_index), reverse=True)


VectorSearch = Callable[[Session, list[float], int, str | None], list[SearchHit]]


def hybrid_search_chunks(
    db: Session,
    query_embedding: list[float] | None,
    query: str,
    top_k: int,
    document_id: str | None = None,
    *,
    vector_search: VectorSearch | None = None,
    fallback_reason: str | None = None,
) -> tuple[list[SearchHit], RetrievalMode]:
    vector_search = vector_search or search_chunks
    lexical_hits = lexical_search_chunks(db, query, top_k, document_id)
    if query_embedding is None:
        return lexical_hits, RetrievalMode(
            mode="lexical",
            fallback_reason=fallback_reason or "Embedding provider unavailable; lexical search was used.",
        )
    try:
        vector_hits = vector_search(db, query_embedding, top_k, document_id)
    except Exception as exc:
        return lexical_hits, RetrievalMode(mode="lexical", fallback_reason=str(exc))

    merged_hits = _merge_hybrid_hits(vector_hits, lexical_hits)
    if vector_hits and lexical_hits:
        mode: Literal["hybrid", "vector", "lexical"] = "hybrid"
    elif vector_hits:
        mode = "vector"
    else:
        mode = "lexical"
    return merged_hits[:top_k], RetrievalMode(mode=mode)
