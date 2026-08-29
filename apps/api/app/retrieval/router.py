from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.documents.router import get_embedding_provider
from app.retrieval.answers import build_grounded_answer
from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.reranker import rerank_hits
from app.retrieval.search import SearchRequest, SearchResponse, format_search_hit, search_chunks

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    db: Annotated[Session, Depends(get_db)],
    embedder: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> SearchResponse:
    query_embedding = embedder.embed_texts([request.query])[0]
    candidate_limit = min(50, max(request.top_k * 4, request.top_k + 10))
    hits = rerank_hits(
        request.query,
        search_chunks(db, query_embedding, candidate_limit, request.document_id),
    )[: request.top_k]
    answer, quality = build_grounded_answer(request.query, hits)
    return SearchResponse(
        query=request.query,
        hits=[format_search_hit(hit) for hit in hits],
        answer=answer,
        quality=quality,
    )
