from dataclasses import dataclass

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, ChunkEmbedding, Document, Page


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    document_id: str
    document_filename: str
    page_number: int
    chunk_index: int
    text: str
    score: float


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
    snippet: str


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHitRead]


def build_snippet(text: str, max_chars: int = 260) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 3].rstrip() + "..."


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
        hits.append(
            SearchHit(
                chunk_id=chunk.id,
                document_id=document.id,
                document_filename=document.filename,
                page_number=page.page_number,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                score=cosine_distance_to_score(float(raw_distance)),
            )
        )
    return hits
