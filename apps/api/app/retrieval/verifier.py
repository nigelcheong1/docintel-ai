from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Literal

from app.retrieval.evidence_pack import EvidenceItem, EvidencePack

VerificationStatus = Literal["verified", "partially_supported", "unsupported"]
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_NUMBER_PATTERN = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?\b")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "from", "in", "is", "it", "of", "on", "or",
    "the", "this", "to", "used", "were", "was", "with",
}


@dataclass(frozen=True)
class SentenceSupport:
    sentence: str
    status: VerificationStatus
    supporting_chunk_ids: list[str]
    support_score: float
    missing_terms: list[str]
    missing_numbers: list[str]


@dataclass(frozen=True)
class VerificationResult:
    status: VerificationStatus
    sentences: list[SentenceSupport]
    unsupported_sentence_count: int
    removed_sentence_count: int
    hallucination_risk: float
    reason: str


def _sentences(answer: str) -> list[str]:
    return [sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(answer.strip()) if sentence.strip()]


def _words(text: str) -> set[str]:
    return {word for word in _WORD_PATTERN.findall(text.lower()) if word not in _STOPWORDS and len(word) > 1}


def _numbers(text: str) -> set[str]:
    return {number.replace(",", "") for number in _NUMBER_PATTERN.findall(text)}


def _support_sentence(sentence: str, items: list[EvidenceItem]) -> SentenceSupport:
    sentence_words = _words(sentence)
    sentence_numbers = _numbers(sentence)
    best_item: EvidenceItem | None = None
    best_overlap = 0.0
    missing_terms: list[str] = []
    missing_numbers: list[str] = []
    for item in items:
        evidence_text = item.text.lower()
        evidence_words = _words(evidence_text)
        overlap = len(sentence_words.intersection(evidence_words)) / len(sentence_words) if sentence_words else 0.0
        if overlap > best_overlap:
            best_overlap = overlap
            best_item = item

    if best_item is None:
        return SentenceSupport(sentence, "unsupported", [], 0.0, sorted(sentence_words), sorted(sentence_numbers))

    best_text = best_item.text.lower()
    missing_numbers = sorted(number for number in sentence_numbers if number not in _numbers(best_text))
    missing_terms = sorted(word for word in sentence_words if word not in _words(best_text))[:8]
    is_supported = best_overlap >= 0.45 and not missing_numbers
    status: VerificationStatus = "verified" if is_supported else "unsupported"
    return SentenceSupport(
        sentence=sentence,
        status=status,
        supporting_chunk_ids=[best_item.chunk_id] if is_supported else [],
        support_score=round(best_overlap, 6),
        missing_terms=[] if is_supported else missing_terms,
        missing_numbers=missing_numbers,
    )


def verify_answer(answer: str, evidence_pack: EvidencePack) -> VerificationResult:
    supports = [_support_sentence(sentence, evidence_pack.items) for sentence in _sentences(answer)]
    unsupported_count = sum(1 for support in supports if support.status == "unsupported")
    if not supports or unsupported_count == len(supports):
        status: VerificationStatus = "unsupported"
    elif unsupported_count:
        status = "partially_supported"
    else:
        status = "verified"
    risk = unsupported_count / len(supports) if supports else 1.0
    return VerificationResult(
        status=status,
        sentences=supports,
        unsupported_sentence_count=unsupported_count,
        removed_sentence_count=0,
        hallucination_risk=round(risk, 6),
        reason=(
            "Every answer sentence is supported by selected evidence."
            if status == "verified"
            else "Some answer sentences lack selected evidence support."
        ),
    )


def filter_supported_answer(answer: str, evidence_pack: EvidencePack) -> tuple[str, VerificationResult]:
    result = verify_answer(answer, evidence_pack)
    supported = [sentence.sentence for sentence in result.sentences if sentence.status == "verified"]
    filtered_answer = " ".join(supported)
    removed = len(result.sentences) - len(supported)
    status: VerificationStatus
    if supported and removed:
        status = "partially_supported"
    elif supported:
        status = "verified"
    else:
        status = "unsupported"
    return filtered_answer, replace(
        result,
        status=status,
        removed_sentence_count=removed,
        reason=(
            "Unsupported answer sentences were removed."
            if removed and supported
            else result.reason
        ),
    )
