from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

from app.retrieval.reranker import (
    infer_query_intents,
    infer_section_intents,
)
from app.retrieval.terms import matching_words

if TYPE_CHECKING:
    from app.retrieval.search import SearchHit


_MAX_ANSWER_HITS = 3
_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_SENTENCE_BOUNDARY = re.compile(r"(?<!\bal\.)(?<!\bfig\.)(?<!\beq\.)(?<=[.!?])\s+", re.IGNORECASE)
_COUNT_QUERY_PATTERN = re.compile(r"\bhow\s+many\b", re.IGNORECASE)
_DATE_QUERY_PATTERN = re.compile(r"\bdates?\b|\bwhen\s+(?:is|was|were|did|will)\b", re.IGNORECASE)
_PUBLICATION_QUERY_PATTERN = re.compile(r"\b(?:published|publication|release|released|issued)\b", re.IGNORECASE)
_CALENDAR_DATE_PATTERN = re.compile(r"\b(?:19|20)\d{2}\b|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b")
_DURATION_PATTERN = re.compile(r"\b\d+\s+(?:days?|weeks?|months?|years?)\b", re.IGNORECASE)
_NUMBER_PATTERN = re.compile(r"\b\d+(?:[,.]\d+)*\b")
_PRICE_QUERY_PATTERN = re.compile(r"\bprices?\b|\bcost\b", re.IGNORECASE)
_MONEY_PATTERN = re.compile(
    r"(?:\b(?:USD|EUR|GBP|MYR|RM)\s*|[$\u00a3\u20ac])\d"
    r"|\d+(?:[,.]\d+)*\s+(?:Malaysian\s+)?(?:Ringgit|dollars?|euros?|pounds?)\b",
    re.IGNORECASE,
)
_BILL_TO_PATTERN = re.compile(r"\bbill(?:ed)?\s+to\b", re.IGNORECASE)
_PARTIES_QUERY_PATTERN = re.compile(r"^who\s+(?:are|were)\s+(?:the\s+)?parties\b", re.IGNORECASE)
_EDUCATION_DEGREE_PATTERN = re.compile(r"\b(?:listed|completed|completion|earned|education|academic|graduated)\b", re.IGNORECASE)
_NON_COMPLETION_PATTERN = re.compile(
    r"\b(?:started|starting|began|enrolled|enrolment|enrollment|expected|anticipated|pursuing)\b|\bin progress\b",
    re.IGNORECASE,
)
_LIST_QUERY_PATTERN = re.compile(
    r"^(?:what|which)\s+(?:are|were)\s+(?:the\s+)?"
    r"(?P<count>\d+|two|three|four|five|six|seven|eight|nine|ten)\s+(?P<item>[a-z][a-z-]*)\b",
    re.IGNORECASE,
)
_LIST_COUNTS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10}
_COUNT_WORDS = {
    "zero", "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
    "sixteen", "seventeen", "eighteen", "nineteen", "twenty", "thirty", "forty",
    "fifty", "sixty", "seventy", "eighty", "ninety", "hundred", "thousand",
    "million", "billion",
}
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
    "many",
    "mentioned",
    "of",
    "on",
    "pdf",
    "paper",
    "resume",
    "remained",
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
    "used",
    "was",
    "were",
    "report",
    "reported",
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
    snippet: str
    snippet_matches: int
    requires_sentence_match: bool


def _words(text: str) -> set[str]:
    return matching_words(text)


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
    if _PARTIES_QUERY_PATTERN.search(query):
        words.difference_update({"agreement", "contract", "service", "services"})
    if _is_education_degree_query(query):
        words.discard("degree")
        words.add("education")
    if _is_price_query(query):
        words.difference_update({"price", "prices", "cost"})
    if "education" in words and _DATE_QUERY_PATTERN.search(query):
        words.difference_update({"completed", "completion"})
    if _COUNT_QUERY_PATTERN.search(query):
        focused = words.difference({
            "total", "initially", "initial", "original", "obtained", "records",
            "record", "results", "result", "entries", "entry", "before", "after",
        })
        if focused:
            words = focused
    # Count a plural and its stem as one requested concept, not two requirements.
    return {word[:-1] if len(word) > 3 and word.endswith("s") else word for word in words}


def _is_education_degree_query(query: str) -> bool:
    return "degree" in _words(query) and bool(_EDUCATION_DEGREE_PATTERN.search(query))


def _is_price_query(query: str) -> bool:
    return bool(_PRICE_QUERY_PATTERN.search(query)) and not re.search(r"\bcost functions?\b", query, re.IGNORECASE)


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
    snippet = _build_snippet(hit.text, query_terms, query)
    return _EvidenceSignal(
        hit=hit,
        keyword_overlap=keyword_overlap,
        section_intent=float(bool(query_intents.intersection(infer_section_intents(hit.section_heading)))),
        query_term_count=len(query_terms),
        matched_term_count=len(matched_terms),
        snippet=snippet,
        snippet_matches=len(query_terms.intersection(_expanded_words(snippet))),
        requires_sentence_match=bool(_DATE_QUERY_PATTERN.search(query)),
    )


def _rank_evidence(query: str, hits: Sequence[SearchHit]) -> list[_EvidenceSignal]:
    query_intents = infer_query_intents(query)
    return sorted(
        (_evidence_signal(query, query_intents, hit) for hit in hits),
        key=lambda signal: (
            bool(signal.snippet),
            signal.snippet_matches / max(1, signal.query_term_count),
            signal.keyword_overlap,
            signal.snippet_matches / max(1, len(signal.snippet.split())),
            signal.section_intent,
            signal.hit.score,
            signal.hit.source_score,
        ),
        reverse=True,
    )


def _candidate_hits(query: str, hits: Sequence[SearchHit]) -> list[SearchHit]:
    if _is_document_language_query(query):
        return [hit for hit in hits if _has_explicit_written_language_evidence(hit)]

    return list(hits)


def rank_answer_evidence(query: str, hits: Sequence[SearchHit]) -> list[SearchHit]:
    ranked: list[SearchHit] = []
    for signal in _rank_evidence(query, hits):
        relevant = float(_is_sufficient_evidence(signal))
        density = min(1.0, 10 * signal.snippet_matches / max(1, len(signal.snippet.split())))
        # Requested values and focused spans outrank repeated topic headers.
        sentence_coverage = signal.snippet_matches / max(1, signal.query_term_count)
        score = relevant * (
            0.60 + 0.20 * sentence_coverage + 0.10 * signal.keyword_overlap
            + 0.05 * density + 0.05 * signal.hit.score
        )
        ranked.append(replace(
            signal.hit, score=round(score, 6),
            ranking_signals={
                **signal.hit.ranking_signals,
                "answer_relevance": relevant,
                "sentence_focus": round(density, 6),
            },
        ))
    return sorted(ranked, key=lambda hit: hit.score, reverse=True)


def _is_sufficient_evidence(signal: _EvidenceSignal) -> bool:
    if not signal.snippet:
        return False
    if signal.query_term_count == 0:
        return False
    if signal.requires_sentence_match and signal.snippet_matches / signal.query_term_count < 0.50:
        return False
    if signal.query_term_count == 1:
        return (
            signal.matched_term_count == 1
            and (signal.hit.source_score >= 0.50 or signal.section_intent >= 1.0)
            and (signal.snippet_matches > 0 or signal.section_intent >= 1.0)
        )
    if not signal.snippet_matches:
        return False
    if signal.section_intent >= 1.0 and signal.matched_term_count >= 2 and signal.keyword_overlap >= 0.50:
        return True
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


def _requested_value_present(query: str, sentence: str) -> bool:
    if _COUNT_QUERY_PATTERN.search(query) and not (_NUMBER_PATTERN.search(sentence) or _words(sentence).intersection(_COUNT_WORDS)):
        return False
    if _DATE_QUERY_PATTERN.search(query):
        if not (_CALENDAR_DATE_PATTERN.search(sentence) or (not _PUBLICATION_QUERY_PATTERN.search(query) and _DURATION_PATTERN.search(sentence))):
            return False
        if _PUBLICATION_QUERY_PATTERN.search(query) and not _words(sentence).intersection({"publish", "release", "released", "issued"}):
            return False
        if _is_education_degree_query(query) and _NON_COMPLETION_PATTERN.search(sentence):
            return False
    if _is_price_query(query) and not _MONEY_PATTERN.search(sentence):
        return False
    if _BILL_TO_PATTERN.search(query) and not _BILL_TO_PATTERN.search(sentence):
        return False
    requested_list = _LIST_QUERY_PATTERN.search(query)
    if requested_list:
        count = requested_list.group("count").lower()
        required = int(count) if count.isdigit() else _LIST_COUNTS[count]
        count_forms = [str(required), *[word for word, value in _LIST_COUNTS.items() if value == required]]
        item = re.escape(requested_list.group("item"))
        # Bind the list marker to the requested count/type, not another colon on the page.
        tail = re.search(
            rf"\b(?:{'|'.join(count_forms)})\s+{item}\s*(?::|\b(?:named|called)\b)\s*(.+)",
            sentence, re.IGNORECASE,
        )
        if not tail or len(re.split(r",\s*(?:and\s+)?|\s+and\s+", tail.group(1))) < required:
            return False
    return True


def _build_snippet(text: str, query_terms: set[str], query: str = "") -> str:
    collapsed = " ".join(text.split())
    spans = _SENTENCE_BOUNDARY.split(collapsed)
    if _PUBLICATION_QUERY_PATTERN.search(query):
        # A bare publication-date continuation belongs to the adjacent named publication.
        spans = [
            f"{spans[index - 1]} {span}"
            if index and re.match(r"^(?:published|released|issued)\b", span, re.IGNORECASE)
            and "publish" in _words(spans[index - 1]) else span
            for index, span in enumerate(spans)
        ]
    if _is_price_query(query):
        # Separate item clauses so one product cannot borrow another's amount.
        spans = [clause for span in spans for clause in re.split(r"\s+(?:and|but|whereas)\s+", span, flags=re.IGNORECASE)]
    sentences = [sentence.strip() for sentence in spans if sentence.strip() and _requested_value_present(query, sentence)]
    if not sentences:
        return ""
    selected = max(
        enumerate(sentences),
        key=lambda item: (
            len(_expanded_words(item[1]).intersection(query_terms)),
            len(_expanded_words(item[1]).intersection(query_terms)) / max(1, len(item[1].split())),
            -item[0],
        ),
    )[1]
    return selected


def _select_answer_signals(query: str, hits: Sequence[SearchHit]) -> tuple[list[_EvidenceSignal], AnswerQuality]:
    all_signals = _rank_evidence(query, hits)
    candidate_signals = _rank_evidence(query, _candidate_hits(query, hits))
    selected_signals = [
        signal for signal in candidate_signals
        if _is_sufficient_evidence(signal) and _has_requested_quantity(query, signal.hit)
    ][:_MAX_ANSWER_HITS]
    quality = _quality_from_signals(
        query=query,
        hits=hits,
        selected_signals=selected_signals,
        all_signals=all_signals,
    )
    return selected_signals, quality


def _has_requested_quantity(query: str, hit: SearchHit) -> bool:
    if not _COUNT_QUERY_PATTERN.search(query):
        return True
    # An unrelated number elsewhere in the chunk cannot support the answer sentence.
    snippet_words = _words(_build_snippet(hit.text, _quality_query_words(query), query))
    return any(word.isdigit() or word in _COUNT_WORDS for word in snippet_words)


def _build_answer_from_hits(query: str, hits: Sequence[SearchHit]) -> ExtractiveAnswer | None:
    query_terms = _quality_query_words(query)
    snippets: list[str] = []
    citations: list[AnswerCitation] = []
    for hit in hits:
        snippet = _build_snippet(hit.text, query_terms, query)
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
