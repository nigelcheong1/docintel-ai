from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.documents.router import get_embedding_provider
from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.search import SearchHitRead, SearchRequest, SearchResponse, build_snippet, search_chunks

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    db: Annotated[Session, Depends(get_db)],
    embedder: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> SearchResponse:
    query_embedding = embedder.embed_texts([request.query])[0]
    hits = search_chunks(db, query_embedding, request.top_k, request.document_id)
    return SearchResponse(
        query=request.query,
        hits=[
            SearchHitRead(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                document_filename=hit.document_filename,
                page_number=hit.page_number,
                chunk_index=hit.chunk_index,
                score=hit.score,
                snippet=build_snippet(hit.text),
                section_heading=hit.section_heading,
            )
            for hit in hits
        ],
    )
