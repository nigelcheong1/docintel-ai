from __future__ import annotations

from dataclasses import dataclass, replace

from app.retrieval.answers import AnswerCitation, AnswerQuality, ExtractiveAnswer, build_grounded_answer
from app.retrieval.evidence_pack import EvidencePack
from app.retrieval.search import SearchHit
from app.retrieval.verifier import VerificationResult, filter_supported_answer, verify_answer


@dataclass(frozen=True)
class VerifiedAnswerResult:
    answer: ExtractiveAnswer | None
    quality: AnswerQuality
    verification: VerificationResult


def _quality(status: str, reason: str, evidence_count: int, support: float) -> AnswerQuality:
    return AnswerQuality(
        status="answerable" if status == "answerable" else "insufficient_evidence",
        confidence=("strong" if support >= 0.75 else "moderate") if status == "answerable" else "weak",
        reason=reason,
        evidence_count=evidence_count,
        best_score=support,
        best_source_score=support,
        best_keyword_overlap=support,
        best_section_intent=0.0,
        suggested_questions=[],
    )


def _draft_answer(query: str, pack: EvidencePack) -> str:
    hits = [
        SearchHit(
            chunk_id=item.chunk_id, document_id=item.document_id,
            document_filename=item.document_filename, page_number=item.page_number,
            chunk_index=item.chunk_index, text=item.text, score=item.score,
            source_score=item.source_score, ranking_signals=item.ranking_signals,
            section_heading=item.section_heading,
        )
        for item in pack.items
    ]
    queries = pack.subqueries or [query]
    drafts: list[str] = []
    for subquery in queries:
        answer, quality = build_grounded_answer(subquery, hits)
        if answer is None or quality.status != "answerable":
            return ""
        best_hit = next(hit for hit in hits if hit.chunk_id == answer.citations[0].chunk_id)
        answer, _ = build_grounded_answer(subquery, [best_hit])
        if answer is None:
            return ""
        if answer.summary not in drafts:
            drafts.append(answer.summary)
    return " ".join(drafts)


def build_verified_answer(query: str, evidence_pack: EvidencePack) -> VerifiedAnswerResult:
    if not evidence_pack.items:
        verification = verify_answer("", evidence_pack)
        return VerifiedAnswerResult(
            answer=None,
            quality=_quality("insufficient_evidence", "Verified Answers could not find enough cited evidence.", 0, 0.0),
            verification=verification,
        )

    draft = _draft_answer(query, evidence_pack)
    if not draft:
        verification = replace(
            verify_answer("", evidence_pack),
            reason="Selected evidence does not answer every requested part of the question.",
        )
        return VerifiedAnswerResult(
            answer=None,
            quality=_quality("insufficient_evidence", verification.reason, 0, evidence_pack.average_support_score),
            verification=verification,
        )
    filtered, verification = filter_supported_answer(draft, evidence_pack)
    if not filtered or verification.status == "unsupported":
        return VerifiedAnswerResult(
            answer=None,
            quality=_quality(
                "insufficient_evidence",
                "Verified Answers removed unsupported claims and no supported answer remained.",
                0,
                evidence_pack.average_support_score,
            ),
            verification=verification,
        )

    supported_chunk_ids = {
        chunk_id for sentence in verification.sentences for chunk_id in sentence.supporting_chunk_ids
    }
    citations = [
        AnswerCitation(
            chunk_id=item.chunk_id,
            document_filename=item.document_filename,
            page_number=item.page_number,
            section_heading=item.section_heading,
        )
        for item in evidence_pack.items
        if item.chunk_id in supported_chunk_ids
    ]
    return VerifiedAnswerResult(
        answer=ExtractiveAnswer(summary=filtered, citations=citations),
        quality=_quality(
            "answerable",
            "Verified Answers built the answer from selected cited evidence.",
            len(citations),
            evidence_pack.average_support_score,
        ),
        verification=verification,
    )
