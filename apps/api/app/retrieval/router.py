from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.documents.router import get_embedding_provider
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
    hits = rerank_hits(
        request.query,
        search_chunks(db, query_embedding, request.top_k, request.document_id),
    )
    return SearchResponse(
        query=request.query,
        hits=[format_search_hit(hit) for hit in hits],
    )
