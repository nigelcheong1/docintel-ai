from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from app.retrieval.reranker import (
    infer_query_intents,
    infer_section_intents,
)

if TYPE_CHECKING:
    from app.retrieval.search import SearchHit


_MAX_ANSWER_HITS = 3
_MAX_SNIPPET_CHARS = 260
_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_DOCUMENT_LANGUAGE_NAMES = (
    "english",
    "malay",
    "bahasa",
    "chinese",
    "mandarin",
    "spanish",
    "french",
    "german",
    "japanese",
    "korean",
    "arabic",
    "hindi",
)
_EXPLICIT_WRITTEN_LANGUAGE = re.compile(
    rf"\b(?:written|drafted|prepared|composed)\s+in\s+(?:the\s+)?(?:{'|'.join(_DOCUMENT_LANGUAGE_NAMES)})\b",
    re.IGNORECASE,
)
_QUALITY_STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "background",
    "candidate",
    "can",
    "could",
    "did",
    "do",
    "does",
    "document",
    "file",
    "for",
    "from",
    "have",
    "has",
    "how",
    "in",
    "is",
    "it",
    "listed",
    "mentioned",
    "of",
    "on",
    "pdf",
    "resume",
    "show",
    "that",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
    "work",
    "working",
    "works",
}

AnswerStatus = Literal["answerable", "insufficient_evidence"]
AnswerConfidence = Literal["strong", "moderate", "weak"]


class AnswerCitation(BaseModel):
    chunk_id: str
    document_filename: str
    page_number: int
    section_heading: str | None = None


class ExtractiveAnswer(BaseModel):
    summary: str
    citations: list[AnswerCitation]


class AnswerQuality(BaseModel):
    status: AnswerStatus
    confidence: AnswerConfidence
    reason: str
    evidence_count: int = Field(ge=0)
    best_score: float = Field(ge=0.0, le=1.0)
    best_source_score: float = Field(ge=0.0, le=1.0)
    best_keyword_overlap: float = Field(ge=0.0, le=1.0)
    best_section_intent: float = Field(ge=0.0, le=1.0)
    suggested_questions: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class _EvidenceSignal:
    hit: SearchHit
    keyword_overlap: float
    section_intent: float
    query_term_count: int
    matched_term_count: int


def _words(text: str) -> set[str]:
    return set(_WORD_PATTERN.findall(text.lower()))


def _expanded_words(text: str) -> set[str]:
    words = _words(text)
    expanded = set(words)
    for word in words:
        if len(word) > 3 and word.endswith("s"):
            expanded.add(word[:-1])
    return expanded


def _quality_query_words(query: str) -> set[str]:
    words = {
        word
        for word in _words(query)
        if word not in _QUALITY_STOP_WORDS and len(word) > 1
    }
    expanded = set(words)
    for word in words:
        if len(word) > 3 and word.endswith("s"):
            expanded.add(word[:-1])
    return expanded


def _normalized_text(text: str) -> str:
    return " ".join(_WORD_PATTERN.findall(text.lower()))


def _is_document_language_query(query: str) -> bool:
    normalized = _normalized_text(query)
    return "written in" in normalized and (
        "language" in normalized
        or bool({"document", "file", "pdf", "resume", "contract", "report"}.intersection(_words(query)))
    )


def _has_explicit_written_language_evidence(hit: SearchHit) -> bool:
    if _EXPLICIT_WRITTEN_LANGUAGE.search(hit.text):
        return True
    normalized_heading = " ".join((hit.section_heading or "").upper().split())
    if normalized_heading in {"CONTRACT LANGUAGE", "DOCUMENT LANGUAGE", "GOVERNING LANGUAGE"}:
        text_words = _words(hit.text)
        return bool(text_words.intersection(_DOCUMENT_LANGUAGE_NAMES))
    return False


def _searchable_text(hit: SearchHit) -> str:
    return " ".join(part for part in (hit.section_heading, hit.text) if part)


def _evidence_signal(query: str, query_intents: set[str], hit: SearchHit) -> _EvidenceSignal:
    query_terms = _quality_query_words(query)
    matched_terms = query_terms.intersection(_expanded_words(_searchable_text(hit)))
    keyword_overlap = len(matched_terms) / len(query_terms) if query_terms else 0.0
    return _EvidenceSignal(
        hit=hit,
        keyword_overlap=keyword_overlap,
        section_intent=float(bool(query_intents.intersection(infer_section_intents(hit.section_heading)))),
        query_term_count=len(query_terms),
        matched_term_count=len(matched_terms),
    )


def _rank_evidence(query: str, hits: Sequence[SearchHit]) -> list[_EvidenceSignal]:
    query_intents = infer_query_intents(query)
    return sorted(
        (_evidence_signal(query, query_intents, hit) for hit in hits),
        key=lambda signal: (
            signal.section_intent,
            signal.keyword_overlap,
            signal.hit.score,
            signal.hit.source_score,
        ),
        reverse=True,
    )


def _candidate_hits(query: str, hits: Sequence[SearchHit]) -> list[SearchHit]:
    query_intents = infer_query_intents(query)
    if _is_document_language_query(query):
        return [hit for hit in hits if _has_explicit_written_language_evidence(hit)]

    matching_section_hits = [
        hit
        for hit in hits
        if query_intents.intersection(infer_section_intents(hit.section_heading))
    ]
    if matching_section_hits:
        return matching_section_hits
    return list(hits)


def _is_sufficient_evidence(signal: _EvidenceSignal) -> bool:
    if signal.section_intent >= 1.0 and signal.keyword_overlap >= 0.25:
        return True
    if signal.query_term_count == 0:
        return False
    if signal.query_term_count == 1:
        return signal.matched_term_count == 1 and signal.hit.source_score >= 0.50
    return signal.matched_term_count >= 2 and signal.keyword_overlap >= 0.60


def _suggest_questions(hits: Sequence[SearchHit]) -> list[str]:
    suggestions_by_intent = {
        "skill": "What technical skills are mentioned?",
        "programming_language": "What programming languages are mentioned?",
        "framework": "What frameworks and libraries are mentioned?",
        "tool": "What tools and platforms are mentioned?",
        "project": "What projects are listed in this document?",
        "education": "What education background is listed?",
        "experience": "What experience is described?",
    }
    suggestions: list[str] = []
    for hit in hits:
        for intent in infer_section_intents(hit.section_heading):
            suggestion = suggestions_by_intent.get(intent)
            if suggestion and suggestion not in suggestions:
                suggestions.append(suggestion)
        if len(suggestions) >= 3:
            return suggestions[:3]

    return suggestions or ["What are the main topics covered in this document?"]


def _confidence_for(signal: _EvidenceSignal) -> AnswerConfidence:
    if signal.section_intent >= 1.0 and signal.keyword_overlap >= 0.50:
        return "strong"
    if signal.keyword_overlap >= 0.75:
        return "strong"
    if signal.section_intent >= 1.0 or signal.keyword_overlap >= 0.45:
        return "moderate"
    return "weak"


def _quality_from_signals(
    *,
    query: str,
    hits: Sequence[SearchHit],
    selected_signals: Sequence[_EvidenceSignal],
    all_signals: Sequence[_EvidenceSignal],
) -> AnswerQuality:
    best_signal = selected_signals[0] if selected_signals else (all_signals[0] if all_signals else None)
    if best_signal is None:
        return AnswerQuality(
            status="insufficient_evidence",
            confidence="weak",
            reason="No indexed evidence was retrieved for this question.",
            evidence_count=0,
            best_score=0.0,
            best_source_score=0.0,
            best_keyword_overlap=0.0,
            best_section_intent=0.0,
            suggested_questions=[],
        )

    if not selected_signals:
        if _is_document_language_query(query):
            reason = "I found nearby text, but no cited passage states the document's written language."
        else:
            reason = "The retrieved documents do not contain enough matching evidence to answer this question."
        return AnswerQuality(
            status="insufficient_evidence",
            confidence="weak",
            reason=reason,
            evidence_count=0,
            best_score=best_signal.hit.score,
            best_source_score=best_signal.hit.source_score,
            best_keyword_overlap=best_signal.keyword_overlap,
            best_section_intent=best_signal.section_intent,
            suggested_questions=_suggest_questions(hits),
        )

    confidence = _confidence_for(best_signal)
    return AnswerQuality(
        status="answerable",
        confidence=confidence,
        reason=f"Answer built from {len(selected_signals)} cited evidence chunk{'s' if len(selected_signals) != 1 else ''}.",
        evidence_count=len(selected_signals),
        best_score=best_signal.hit.score,
        best_source_score=best_signal.hit.source_score,
        best_keyword_overlap=best_signal.keyword_overlap,
        best_section_intent=best_signal.section_intent,
        suggested_questions=_suggest_questions(hits),
    )


def _build_snippet(text: str, query_terms: set[str]) -> str:
    collapsed = " ".join(text.split())
    sentences = [sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(collapsed) if sentence.strip()]
    if not sentences:
        return ""
    selected = max(
        enumerate(sentences),
        key=lambda item: (len(_words(item[1]).intersection(query_terms)), -item[0]),
    )[1]
    if len(selected) <= _MAX_SNIPPET_CHARS:
        return selected
    return selected[: _MAX_SNIPPET_CHARS - 3].rstrip() + "..."


def _select_answer_signals(query: str, hits: Sequence[SearchHit]) -> tuple[list[_EvidenceSignal], AnswerQuality]:
    all_signals = _rank_evidence(query, hits)
    candidate_signals = _rank_evidence(query, _candidate_hits(query, hits))
    selected_signals = [signal for signal in candidate_signals if _is_sufficient_evidence(signal)][:_MAX_ANSWER_HITS]
    quality = _quality_from_signals(
        query=query,
        hits=hits,
        selected_signals=selected_signals,
        all_signals=all_signals,
    )
    return selected_signals, quality


def _build_answer_from_hits(query: str, hits: Sequence[SearchHit]) -> ExtractiveAnswer | None:
    query_terms = _words(query)
    snippets: list[str] = []
    citations: list[AnswerCitation] = []
    for hit in hits:
        snippet = _build_snippet(hit.text, query_terms)
        if not snippet:
            continue
        snippets.append(snippet)
        citations.append(
            AnswerCitation(
                chunk_id=hit.chunk_id,
                document_filename=hit.document_filename,
                page_number=hit.page_number,
                section_heading=hit.section_heading,
            )
        )

    if not snippets:
        return None
    return ExtractiveAnswer(summary=" ".join(snippets), citations=citations)


def build_grounded_answer(query: str, hits: Sequence[SearchHit]) -> tuple[ExtractiveAnswer | None, AnswerQuality]:
    selected_signals, quality = _select_answer_signals(query, hits)
    if quality.status == "insufficient_evidence":
        return None, quality

    answer = _build_answer_from_hits(query, [signal.hit for signal in selected_signals])
    if answer is not None:
        return answer, quality

    return None, AnswerQuality(
        status="insufficient_evidence",
        confidence="weak",
        reason="Retrieved evidence did not contain extractable answer text.",
        evidence_count=0,
        best_score=quality.best_score,
        best_source_score=quality.best_source_score,
        best_keyword_overlap=quality.best_keyword_overlap,
        best_section_intent=quality.best_section_intent,
        suggested_questions=quality.suggested_questions,
    )


def build_extractive_answer(query: str, hits: Sequence[SearchHit]) -> ExtractiveAnswer | None:
    answer, _quality = build_grounded_answer(query, hits)
    return answer
