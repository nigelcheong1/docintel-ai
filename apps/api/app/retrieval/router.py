from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, DocumentStatus
from app.db.session import get_db
from app.documents.intelligence import build_document_profile
from app.documents.router import get_embedding_provider_factory
from app.documents.service import EmbeddingProviderFactory
from app.retrieval.answers import AnswerQuality, build_grounded_answer
from app.retrieval.evidence_pack import EvidenceItem, EvidencePack, build_evidence_pack
from app.retrieval.multihop import build_query_plan
from app.retrieval.document_answers import build_document_aware_answer
from app.retrieval.query_router import route_query
from app.retrieval.reranker import rerank_hits
from app.retrieval.search import (
    EvidenceItemRead,
    EvidencePackRead,
    EvidenceVerificationRead,
    RejectedEvidenceRead,
    SearchDiagnostics,
    SearchHit,
    SearchRequest,
    SearchResponse,
    SentenceSupportRead,
    format_search_hit,
    hybrid_search_chunks,
    search_chunks,
)
from app.retrieval.verified_answers import build_verified_answer
from app.retrieval.verifier import VerificationResult

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


def _search_hit_from_evidence_item(item: EvidenceItem) -> SearchHit:
    return SearchHit(
        chunk_id=item.chunk_id,
        document_id=item.document_id,
        document_filename=item.document_filename,
        page_number=item.page_number,
        chunk_index=item.chunk_index,
        text=item.text,
        score=item.score,
        source_score=item.source_score,
        ranking_signals=item.ranking_signals,
        section_heading=item.section_heading,
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


def _read_evidence_pack(pack: EvidencePack) -> EvidencePackRead:
    return EvidencePackRead(
        question=pack.question,
        rewritten_query=pack.rewritten_query,
        subqueries=pack.subqueries,
        items=[
            EvidenceItemRead(
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                document_filename=item.document_filename,
                page_number=item.page_number,
                chunk_index=item.chunk_index,
                snippet=item.snippet,
                score=item.score,
                source_score=item.source_score,
                ranking_signals=item.ranking_signals,
                section_heading=item.section_heading,
                subquery=item.subquery,
                support_score=item.support_score,
            )
            for item in pack.items
        ],
        rejected=[
            RejectedEvidenceRead(
                chunk_id=item.chunk_id,
                page_number=item.page_number,
                subquery=item.subquery,
                reason=item.reason,
            )
            for item in pack.rejected
        ],
        retrieval_mode=pack.retrieval_mode,
        retrieval_fallback_reason=pack.retrieval_fallback_reason,
        selected_chunk_count=pack.selected_chunk_count,
        selected_page_count=pack.selected_page_count,
        average_support_score=pack.average_support_score,
        is_multi_hop=pack.is_multi_hop,
    )


def _read_verification(result: VerificationResult) -> EvidenceVerificationRead:
    return EvidenceVerificationRead(
        status=result.status,
        sentences=[
            SentenceSupportRead(
                sentence=sentence.sentence,
                status=sentence.status,
                supporting_chunk_ids=sentence.supporting_chunk_ids,
                support_score=sentence.support_score,
                missing_terms=sentence.missing_terms,
                missing_numbers=sentence.missing_numbers,
            )
            for sentence in result.sentences
        ],
        unsupported_sentence_count=result.unsupported_sentence_count,
        removed_sentence_count=result.removed_sentence_count,
        hallucination_risk=result.hallucination_risk,
        reason=result.reason,
    )


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
        answer_mode=request.answer_mode,
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
    plan = build_query_plan(request.query)
    if request.answer_mode == "verified":
        hits_by_subquery: dict[str, list[SearchHit]] = {}
        retrieval_modes: list[str] = []
        fallback_reason = embedding_failure_reason
        for subquery in plan.subqueries:
            candidates, mode = hybrid_search_chunks(
                db,
                query_embedding,
                subquery,
                candidate_limit,
                request.document_id,
                vector_search=search_chunks,
                fallback_reason=embedding_failure_reason,
            )
            hits_by_subquery[subquery] = rerank_hits(subquery, candidates)[: request.top_k]
            retrieval_modes.append(mode.mode)
            fallback_reason = fallback_reason or mode.fallback_reason

        pack_mode = "hybrid" if "hybrid" in retrieval_modes else "vector" if "vector" in retrieval_modes else "lexical"
        pack = build_evidence_pack(
            request.query,
            hits_by_subquery,
            pack_mode,
            fallback_reason,
            rewritten_query=plan.rewritten_query,
            is_multi_hop=plan.is_multi_hop,
        )
        verified = build_verified_answer(request.query, pack)
        answer_chunk_ids = [citation.chunk_id for citation in verified.answer.citations] if verified.answer is not None else []
        answer_chunk_id_set = set(answer_chunk_ids)
        evidence_hits = [_search_hit_from_evidence_item(item) for item in pack.items]
        display_hits = _augment_hits_with_answer_evidence(evidence_hits, document, answer_chunk_ids)
        diagnostics = _build_search_diagnostics(
            hits=display_hits,
            answer_chunk_ids=answer_chunk_ids,
            quality_status=verified.quality.status,
            confidence=verified.quality.confidence,
            reason=verified.quality.reason,
            document_type=profile.document_type if profile is not None else None,
            query_intent=route.intent,
        )
        return SearchResponse(
            query=request.query,
            hits=[format_search_hit(hit, answer_chunk_id_set) for hit in display_hits],
            answer=verified.answer,
            quality=verified.quality,
            document_type=profile.document_type if profile is not None else None,
            query_intent=route.intent,
            diagnostics=diagnostics,
            retrieval_mode=pack.retrieval_mode,
            retrieval_fallback_reason=pack.retrieval_fallback_reason,
            answer_mode="verified",
            evidence_pack=_read_evidence_pack(pack),
            verification=_read_verification(verified.verification),
        )

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
        answer_mode="standard",
    )
