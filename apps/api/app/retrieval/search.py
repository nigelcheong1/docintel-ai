from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, ChunkEmbedding, Document, Page
from app.retrieval.answers import AnswerQuality, ExtractiveAnswer


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
    score: float
    source_score: float
    ranking_signals: dict[str, float]
    snippet: str
    section_heading: str | None = None


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHitRead]
    answer: ExtractiveAnswer | None
    quality: AnswerQuality
    document_type: str | None = None
    query_intent: str = "evidence_search"


def build_snippet(text: str, max_chars: int = 260) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 3].rstrip() + "..."


def format_search_hit(hit: SearchHit) -> SearchHitRead:
    return SearchHitRead(
        chunk_id=hit.chunk_id,
        document_id=hit.document_id,
        document_filename=hit.document_filename,
        page_number=hit.page_number,
        chunk_index=hit.chunk_index,
        score=hit.score,
        source_score=hit.source_score,
        ranking_signals=hit.ranking_signals,
        snippet=build_snippet(hit.text),
        section_heading=hit.section_heading,
    )


def cosine_distance_to_score(distance: float) -> float:
    return max(0.0, min(1.0, 1.0 - distance))


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
