from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, DocumentStatus
from app.db.session import get_db
from app.documents.intelligence import build_document_profile
from app.documents.router import get_embedding_provider_factory
from app.documents.service import EmbeddingProviderFactory
from app.retrieval.answers import AnswerQuality, build_grounded_answer
from app.retrieval.document_answers import build_document_aware_answer
from app.retrieval.query_router import route_query
from app.retrieval.reranker import rerank_hits
from app.retrieval.search import (
    SearchDiagnostics,
    SearchHit,
    SearchRequest,
    SearchResponse,
    format_search_hit,
    hybrid_search_chunks,
    search_chunks,
)

router = APIRouter(tags=["search"])


def _build_search_diagnostics(
    *,
    hits: list[SearchHit],
    answer_chunk_ids: list[str],
    quality_status: str,
    confidence: str,
    reason: str,
    document_type: str | None,
    query_intent: str,
) -> SearchDiagnostics:
    answer_chunk_id_set = set(answer_chunk_ids)
    related_hits = [hit for hit in hits if hit.chunk_id not in answer_chunk_id_set]
    rejected_reasons = [
        "Related evidence was not cited because it ranked below the selected answer evidence.",
        "Related evidence matched the broader topic but not the requested answer intent.",
        "Related evidence was kept for context only.",
    ][: len(related_hits[:3])]
    if quality_status == "insufficient_evidence" and not rejected_reasons:
        rejected_reasons = ["No indexed evidence passed the answerability checks"]

    return SearchDiagnostics(
        document_type=document_type,
        query_intent=query_intent,
        quality_status=quality_status,
        confidence=confidence,
        reason=reason,
        answer_chunk_ids=answer_chunk_ids,
        answer_evidence_count=len(answer_chunk_ids),
        related_result_count=len(related_hits),
        top_rejected_reasons=rejected_reasons,
    )


def _section_heading_for_chunk(chunk: Chunk) -> str | None:
    section_heading = chunk.layout.get("section_heading") if isinstance(chunk.layout, dict) else None
    return section_heading if isinstance(section_heading, str) else None


def _search_hit_from_chunk(chunk: Chunk, document: Document) -> SearchHit:
    return SearchHit(
        chunk_id=chunk.id,
        document_id=document.id,
        document_filename=document.filename,
        page_number=chunk.page.page_number,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        score=1.0,
        source_score=1.0,
        ranking_signals={"answer_evidence": 1.0},
        section_heading=_section_heading_for_chunk(chunk),
    )


def _augment_hits_with_answer_evidence(
    hits: list[SearchHit],
    document: Document | None,
    answer_chunk_ids: list[str],
) -> list[SearchHit]:
    if not answer_chunk_ids:
        return hits

    hits_by_id = {hit.chunk_id: hit for hit in hits}
    document_chunks_by_id = {chunk.id: chunk for chunk in document.chunks} if document is not None else {}
    merged_hits: list[SearchHit] = []
    seen_chunk_ids: set[str] = set()

    for chunk_id in answer_chunk_ids:
        hit = hits_by_id.get(chunk_id)
        if hit is None:
            chunk = document_chunks_by_id.get(chunk_id)
            if chunk is not None:
                hit = _search_hit_from_chunk(chunk, document)
        if hit is not None and hit.chunk_id not in seen_chunk_ids:
            merged_hits.append(hit)
            seen_chunk_ids.add(hit.chunk_id)

    for hit in hits:
        if hit.chunk_id not in seen_chunk_ids:
            merged_hits.append(hit)
            seen_chunk_ids.add(hit.chunk_id)

    return merged_hits


def _selected_document_no_chunks_reason(document: Document) -> str:
    if document.status == DocumentStatus.DEFERRED_OCR:
        return document.error_message or "This selected document needs OCR before it can be searched."
    if document.status == DocumentStatus.OCR_PROCESSING:
        return "OCR is still running for this selected document. Try again after processing completes."
    if document.status == DocumentStatus.FAILED:
        detail = document.error_message or "Document indexing failed."
        return f"{detail} Reindex the document before searching it."
    return "This selected document does not have indexed searchable evidence yet."


def _empty_scoped_document_response(
    *,
    request: SearchRequest,
    document: Document,
    document_type: str | None,
    query_intent: str,
) -> SearchResponse:
    reason = _selected_document_no_chunks_reason(document)
    quality = AnswerQuality(
        status="insufficient_evidence",
        confidence="weak",
        reason=reason,
        evidence_count=0,
        best_score=0.0,
        best_source_score=0.0,
        best_keyword_overlap=0.0,
        best_section_intent=0.0,
        suggested_questions=[],
    )
    diagnostics = _build_search_diagnostics(
        hits=[],
        answer_chunk_ids=[],
        quality_status=quality.status,
        confidence=quality.confidence,
        reason=quality.reason,
        document_type=document_type,
        query_intent=query_intent,
    )
    return SearchResponse(
        query=request.query,
        hits=[],
        answer=None,
        quality=quality,
        document_type=document_type,
        query_intent=query_intent,
        diagnostics=diagnostics,
    )


def _embedding_fallback_reason(exc: Exception) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    return f"Embedding provider unavailable: {message}"


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    db: Annotated[Session, Depends(get_db)],
    embedder_factory: Annotated[EmbeddingProviderFactory, Depends(get_embedding_provider_factory)],
) -> SearchResponse:
    document = None
    profile = None
    route = route_query(request.query)
    if request.document_id is not None and hasattr(db, "get"):
        document = db.get(Document, request.document_id)
        if document is not None:
            profile = build_document_profile(document)
            route = route_query(request.query, profile.document_type)
            if not document.chunks:
                return _empty_scoped_document_response(
                    request=request,
                    document=document,
                    document_type=profile.document_type,
                    query_intent=route.intent,
                )

    query_embedding: list[float] | None = None
    embedding_failure_reason: str | None = None
    try:
        embedder = embedder_factory()
        query_embedding = embedder.embed_texts([request.query])[0]
    except Exception as exc:
        embedding_failure_reason = _embedding_fallback_reason(exc)

    candidate_limit = min(50, max(request.top_k * 4, request.top_k + 10))
    candidate_hits, retrieval_mode = hybrid_search_chunks(
        db,
        query_embedding,
        request.query,
        candidate_limit,
        request.document_id,
        vector_search=search_chunks,
        fallback_reason=embedding_failure_reason,
    )
    hits = rerank_hits(request.query, candidate_hits)[: request.top_k]

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
    answer_chunk_ids = [citation.chunk_id for citation in answer.citations] if answer is not None else []
    answer_chunk_id_set = set(answer_chunk_ids)
    display_hits = _augment_hits_with_answer_evidence(hits, document, answer_chunk_ids)
    diagnostics = _build_search_diagnostics(
        hits=display_hits,
        answer_chunk_ids=answer_chunk_ids,
        quality_status=quality.status,
        confidence=quality.confidence,
        reason=quality.reason,
        document_type=document_type,
        query_intent=query_intent,
    )
    return SearchResponse(
        query=request.query,
        hits=[format_search_hit(hit, answer_chunk_id_set) for hit in display_hits],
        answer=answer,
        quality=quality,
        document_type=document_type,
        query_intent=query_intent,
        diagnostics=diagnostics,
        retrieval_mode=retrieval_mode.mode,
        retrieval_fallback_reason=retrieval_mode.fallback_reason,
    )
