from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.db.models import Chunk, Document
from app.documents.intelligence import chunk_heading, clean_text, ordered_chunks, strip_leading_heading
from app.documents.schemas import DocumentFactRead, DocumentProfileRead
from app.retrieval.answers import AnswerCitation, AnswerQuality, ExtractiveAnswer
from app.retrieval.query_router import QueryRoute

_MAX_ANSWER_CHUNKS = 3
_MAX_SUMMARY_CHARS = 480
_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class DocumentAwareAnswer:
    answer: ExtractiveAnswer | None
    quality: AnswerQuality
    query_intent: str
    document_type: str


def _quality(
    *,
    status: Literal["answerable", "insufficient_evidence"],
    confidence: Literal["strong", "moderate", "weak"],
    reason: str,
    evidence_count: int,
    suggested_questions: list[str],
) -> AnswerQuality:
    signal = 1.0 if status == "answerable" else 0.0
    return AnswerQuality(
        status=status,
        confidence=confidence,
        reason=reason,
        evidence_count=evidence_count,
        best_score=signal,
        best_source_score=signal,
        best_keyword_overlap=signal,
        best_section_intent=signal,
        suggested_questions=suggested_questions[:3],
    )


def _no_answer(reason: str, profile: DocumentProfileRead, route: QueryRoute) -> DocumentAwareAnswer:
    return DocumentAwareAnswer(
        answer=None,
        quality=_quality(
            status="insufficient_evidence",
            confidence="weak",
            reason=reason,
            evidence_count=0,
            suggested_questions=profile.suggested_questions,
        ),
        query_intent=route.intent,
        document_type=profile.document_type,
    )


def _citation(chunk: Chunk) -> AnswerCitation:
    return AnswerCitation(
        chunk_id=chunk.id,
        document_filename=chunk.document.filename,
        page_number=chunk.page.page_number,
        section_heading=chunk_heading(chunk),
    )


def _words(text: str) -> set[str]:
    return set(_WORD_PATTERN.findall(text.lower()))


def _snippet(text: str, query: str, *, prefer_first: bool = False) -> str:
    cleaned = clean_text(text)
    sentences = [sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(cleaned) if sentence.strip()]
    if not sentences:
        return cleaned[: _MAX_SUMMARY_CHARS - 3].rstrip() + "..." if len(cleaned) > _MAX_SUMMARY_CHARS else cleaned
    if prefer_first:
        selected = sentences[0]
    else:
        query_words = _words(query)
        selected = max(
            enumerate(sentences),
            key=lambda item: (len(_words(item[1]).intersection(query_words)), -item[0]),
        )[1]
    if len(selected) <= _MAX_SUMMARY_CHARS:
        return selected
    return selected[: _MAX_SUMMARY_CHARS - 3].rstrip() + "..."


def _build_answer(
    *,
    query: str,
    chunks: list[Chunk],
    profile: DocumentProfileRead,
    route: QueryRoute,
    confidence: Literal["strong", "moderate", "weak"],
    reason: str,
    prefer_first_sentence: bool = False,
) -> DocumentAwareAnswer | None:
    selected_chunks = chunks[:_MAX_ANSWER_CHUNKS]
    snippets: list[str] = []
    citations: list[AnswerCitation] = []
    seen_chunk_ids: set[str] = set()
    for chunk in selected_chunks:
        if chunk.id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(chunk.id)
        snippet = _snippet(strip_leading_heading(chunk.text, chunk_heading(chunk)), query, prefer_first=prefer_first_sentence)
        if not snippet:
            continue
        snippets.append(snippet)
        citations.append(_citation(chunk))

    if not snippets:
        return None
    return DocumentAwareAnswer(
        answer=ExtractiveAnswer(summary=" ".join(snippets), citations=citations),
        quality=_quality(
            status="answerable",
            confidence=confidence,
            reason=reason,
            evidence_count=len(citations),
            suggested_questions=profile.suggested_questions,
        ),
        query_intent=route.intent,
        document_type=profile.document_type,
    )


def _chunk_text(chunk: Chunk) -> str:
    return " ".join(part for part in (chunk_heading(chunk), chunk.text) if part).lower()


def _chunks_by_heading_or_terms(
    document: Document,
    *,
    headings: set[str],
    terms: set[str],
    exclude_references: bool = True,
) -> list[Chunk]:
    matches: list[Chunk] = []
    for chunk in ordered_chunks(document):
        heading = chunk_heading(chunk)
        if exclude_references and (heading == "REFERENCES" or _chunk_text(chunk).startswith("references")):
            continue
        normalized_text = _chunk_text(chunk)
        if heading in headings or any(term in normalized_text for term in terms):
            matches.append(chunk)
    return matches


def _fallback_opening_chunks(document: Document) -> list[Chunk]:
    return [
        chunk
        for chunk in ordered_chunks(document)
        if chunk_heading(chunk) != "REFERENCES" and not _chunk_text(chunk).startswith("references")
    ][:_MAX_ANSWER_CHUNKS]


def _chunks_containing_values(document: Document, values: list[str]) -> list[Chunk]:
    selected: list[Chunk] = []
    lowered_values = [value.lower() for value in values]
    for chunk in ordered_chunks(document):
        lowered_text = chunk.text.lower()
        if any(value in lowered_text for value in lowered_values):
            selected.append(chunk)
    return selected


def _answer_from_facts(
    *,
    query: str,
    facts: list[DocumentFactRead],
    document: Document,
    profile: DocumentProfileRead,
    route: QueryRoute,
    label: str,
    confidence: Literal["strong", "moderate", "weak"] = "moderate",
) -> DocumentAwareAnswer | None:
    values = [fact.value for fact in facts[:6]]
    if not values:
        return None
    chunks = _chunks_containing_values(document, values)
    if not chunks:
        chunks = _fallback_opening_chunks(document)
    if not chunks:
        return None
    result = _build_answer(
        query=query,
        chunks=chunks,
        profile=profile,
        route=route,
        confidence=confidence,
        reason=f"Document-aware {route.intent} answer built from extracted {label} evidence.",
    )
    if result is None or result.answer is None:
        return None

    fact_text = f"{label.capitalize()} mentioned: {', '.join(values)}."
    return DocumentAwareAnswer(
        answer=ExtractiveAnswer(summary=fact_text, citations=result.answer.citations),
        quality=result.quality,
        query_intent=result.query_intent,
        document_type=result.document_type,
    )


def _overview_answer(query: str, document: Document, profile: DocumentProfileRead, route: QueryRoute) -> DocumentAwareAnswer | None:
    chunks = _chunks_by_heading_or_terms(
        document,
        headings={"ABSTRACT", "EXECUTIVE SUMMARY", "SUMMARY", "ABOUT ME", "OVERVIEW", "INTRODUCTION"},
        terms={"abstract", "executive summary", "overview", "introduction", "this paper", "this report"},
    )
    if not chunks:
        chunks = _fallback_opening_chunks(document)
    return _build_answer(
        query=query,
        chunks=chunks,
        profile=profile,
        route=route,
        confidence="strong" if chunks else "moderate",
        reason="Document-aware overview answer built from high-level sections.",
        prefer_first_sentence=True,
    )


def _date_answer(query: str, document: Document, profile: DocumentProfileRead, route: QueryRoute) -> DocumentAwareAnswer | None:
    return _answer_from_facts(
        query=query,
        facts=profile.key_dates,
        document=document,
        profile=profile,
        route=route,
        label="dates",
        confidence="moderate",
    )


def _amount_answer(query: str, document: Document, profile: DocumentProfileRead, route: QueryRoute) -> DocumentAwareAnswer | None:
    money_facts = [fact for fact in profile.key_numbers if fact.kind == "amount"]
    facts = money_facts or profile.key_numbers
    return _answer_from_facts(
        query=query,
        facts=facts,
        document=document,
        profile=profile,
        route=route,
        label="amounts and metrics",
        confidence="strong" if money_facts else "moderate",
    )


def _party_answer(query: str, document: Document, profile: DocumentProfileRead, route: QueryRoute) -> DocumentAwareAnswer | None:
    party_facts = [
        fact
        for fact in profile.key_entities
        if fact.label in {"Party", "Entity"} and fact.value.lower() not in {"this paper", "this agreement"}
    ]
    result = _answer_from_facts(
        query=query,
        facts=party_facts,
        document=document,
        profile=profile,
        route=route,
        label="parties or entities",
        confidence="moderate",
    )
    if result is None:
        chunks = _chunks_by_heading_or_terms(
            document,
            headings={"PARTIES", "BILL TO", "VENDOR", "CLIENT"},
            terms={"between", "bill to", "vendor", "client", "customer", "supplier"},
        )
        return _build_answer(
            query=query,
            chunks=chunks,
            profile=profile,
            route=route,
            confidence="moderate",
            reason="Document-aware parties answer built from party-related sections.",
        )
    return result


def _section_answer(
    query: str,
    document: Document,
    profile: DocumentProfileRead,
    route: QueryRoute,
    *,
    headings: set[str],
    terms: set[str],
    confidence: Literal["strong", "moderate", "weak"] = "moderate",
) -> DocumentAwareAnswer | None:
    chunks = _chunks_by_heading_or_terms(document, headings=headings, terms=terms)
    return _build_answer(
        query=query,
        chunks=chunks,
        profile=profile,
        route=route,
        confidence=confidence,
        reason=f"Document-aware {route.intent} answer built from matching sections.",
    )


def build_document_aware_answer(
    query: str,
    document: Document,
    profile: DocumentProfileRead,
    route: QueryRoute,
) -> DocumentAwareAnswer | None:
    if route.mismatch_reason:
        return _no_answer(route.mismatch_reason, profile, route)

    if route.intent == "overview":
        return _overview_answer(query, document, profile, route)
    if route.intent == "dates":
        result = _date_answer(query, document, profile, route)
        return result or _no_answer("No dates were detected in this document.", profile, route)
    if route.intent == "amounts":
        result = _amount_answer(query, document, profile, route)
        return result or _no_answer("No amounts, totals, or measurable metrics were detected in this document.", profile, route)
    if route.intent == "parties":
        result = _party_answer(query, document, profile, route)
        return result or _no_answer("No party, vendor, client, or bill-to evidence was detected in this document.", profile, route)
    if route.intent == "datasets":
        dataset_facts = [fact for fact in profile.key_entities if fact.kind == "dataset"]
        result = _answer_from_facts(
            query=query,
            facts=dataset_facts,
            document=document,
            profile=profile,
            route=route,
            label="datasets",
            confidence="strong" if dataset_facts else "moderate",
        )
        if result:
            return result
        return _section_answer(
            query,
            document,
            profile,
            route,
            headings={"EXPERIMENTS", "EVALUATION", "RESULTS", "DATASET", "DATASETS"},
            terms={"dataset", "datasets", "benchmark", "benchmarks", "corpus"},
        )
    if route.intent == "methods":
        return _section_answer(
            query,
            document,
            profile,
            route,
            headings={"METHODOLOGY", "METHOD", "METHODS", "APPROACH", "MODEL"},
            terms={"method", "approach", "model", "architecture", "propose", "proposed", "framework"},
            confidence="strong",
        )
    if route.intent == "results":
        return _section_answer(
            query,
            document,
            profile,
            route,
            headings={"RESULT", "RESULTS", "EVALUATION", "FINDINGS", "EXPERIMENTS"},
            terms={"result", "accuracy", "performance", "top1", "top5", "f1", "findings", "improve"},
            confidence="strong",
        )
    if route.intent in {"limitations", "risks", "obligations"}:
        return _section_answer(
            query,
            document,
            profile,
            route,
            headings={
                "LIMITATION",
                "LIMITATIONS",
                "FUTURE WORK",
                "DISCUSSION",
                "RISKS",
                "OBLIGATIONS",
                "RESPONSIBILITIES",
                "TERMINATION",
                "LIABILITY",
                "RECOMMENDATIONS",
            },
            terms={
                "limitation",
                "limitations",
                "future",
                "challenge",
                "risk",
                "obligation",
                "shall",
                "must",
                "responsible",
                "termination",
                "liability",
            },
        )
    return None
