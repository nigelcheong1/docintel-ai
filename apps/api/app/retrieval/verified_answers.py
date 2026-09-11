from __future__ import annotations

from dataclasses import dataclass

from app.retrieval.answers import AnswerCitation, AnswerQuality, ExtractiveAnswer
from app.retrieval.evidence_pack import EvidencePack
from app.retrieval.verifier import VerificationResult, filter_supported_answer, verify_answer


@dataclass(frozen=True)
class VerifiedAnswerResult:
    answer: ExtractiveAnswer | None
    quality: AnswerQuality
    verification: VerificationResult


def _quality(status: str, reason: str, evidence_count: int, support: float) -> AnswerQuality:
    return AnswerQuality(
        status="answerable" if status == "answerable" else "insufficient_evidence",
        confidence="strong" if support >= 0.75 else "moderate" if support >= 0.45 else "weak",
        reason=reason,
        evidence_count=evidence_count,
        best_score=support,
        best_source_score=support,
        best_keyword_overlap=support,
        best_section_intent=0.0,
        suggested_questions=[],
    )


def _draft_answer(pack: EvidencePack) -> str:
    snippets = [item.snippet for item in pack.items[:3] if item.snippet]
    return " ".join(snippets)


def build_verified_answer(query: str, evidence_pack: EvidencePack) -> VerifiedAnswerResult:
    if not evidence_pack.items:
        verification = verify_answer("", evidence_pack)
        return VerifiedAnswerResult(
            answer=None,
            quality=_quality("insufficient_evidence", "Verified Answers could not find enough cited evidence.", 0, 0.0),
            verification=verification,
        )

    draft = _draft_answer(evidence_pack)
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
