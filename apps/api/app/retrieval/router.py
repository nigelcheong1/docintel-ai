from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.documents.router import get_embedding_provider_factory
from app.documents.service import EmbeddingProviderFactory
from app.retrieval import service
from app.retrieval.search import SearchRequest, SearchResponse

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    db: Annotated[Session, Depends(get_db)],
    embedder_factory: Annotated[EmbeddingProviderFactory, Depends(get_embedding_provider_factory)],
) -> SearchResponse:
    return service.execute_search(request, db, embedder_factory).response
