from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Document
from app.db.session import get_db
from app.documents.intelligence import build_document_profile
from app.documents.router import get_embedding_provider
from app.retrieval.answers import build_grounded_answer
from app.retrieval.document_answers import build_document_aware_answer
from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.query_router import route_query
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
    document = None
    profile = None
    route = route_query(request.query)
    if request.document_id is not None and hasattr(db, "get"):
        document = db.get(Document, request.document_id)
        if document is not None:
            profile = build_document_profile(document)
            route = route_query(request.query, profile.document_type)

    typed_answer = (
        build_document_aware_answer(request.query, document, profile, route)
        if document is not None and profile is not None
        else None
    )
    if typed_answer is not None:
        answer = typed_answer.answer
        quality = typed_answer.quality
        query_intent = typed_answer.query_intent
        document_type = typed_answer.document_type
    else:
        answer, quality = build_grounded_answer(request.query, hits)
        query_intent = route.intent
        document_type = profile.document_type if profile is not None else None
    return SearchResponse(
        query=request.query,
        hits=[format_search_hit(hit) for hit in hits],
        answer=answer,
        quality=quality,
        document_type=document_type,
        query_intent=query_intent,
    )
