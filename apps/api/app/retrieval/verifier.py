from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Literal

from app.retrieval.evidence_pack import EvidenceItem, EvidencePack

VerificationStatus = Literal["verified", "partially_supported", "unsupported"]
_SENTENCE_BOUNDARY = re.compile(r"(?<!\bal\.)(?<=[.!?])\s+", re.IGNORECASE)
_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_NUMBER_PATTERN = re.compile(r"(?<!\w)[+-]?\d[\d,]*(?:\.\d+)?%?(?!\w)")
_ENTITY_PATTERN = re.compile(r"\b[A-Z][A-Za-z0-9-]+\b")
_NEGATIONS = {"not", "no", "never", "without", "neither", "cannot"}
_STOPWORDS = {
    "a", "an", "and", "are", "as", "from", "in", "is", "it", "of", "on", "or",
    "the", "this", "to", "used", "were", "was", "with", "study",
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
    entity_words = {
        word for entity in _ENTITY_PATTERN.findall(sentence) for word in _words(entity)
    }
    candidates: list[SentenceSupport] = []
    for item in items:
        for evidence_sentence in _sentences(item.text):
            evidence_words = _words(evidence_sentence)
            overlap = len(sentence_words.intersection(evidence_words)) / len(sentence_words) if sentence_words else 0.0
            missing_numbers = sorted(sentence_numbers - _numbers(evidence_sentence))
            missing_terms = sorted(sentence_words - evidence_words)
            same_negation = sentence_words.intersection(_NEGATIONS) == evidence_words.intersection(_NEGATIONS)
            supported = overlap >= 0.8 and not missing_numbers and same_negation and entity_words.issubset(evidence_words)
            candidates.append(SentenceSupport(
                sentence=sentence,
                status="verified" if supported else "unsupported",
                supporting_chunk_ids=[item.chunk_id] if supported else [],
                support_score=round(overlap, 6),
                missing_terms=[] if supported else missing_terms[:8],
                missing_numbers=missing_numbers,
            ))
    if not candidates:
        return SentenceSupport(sentence, "unsupported", [], 0.0, sorted(sentence_words), sorted(sentence_numbers))
    return max(candidates, key=lambda candidate: (candidate.status == "verified", candidate.support_score))


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
