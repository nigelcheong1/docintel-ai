from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from app.db.models import Chunk, Document
from app.documents.intelligence import (
    chunk_heading,
    clean_research_text,
    clean_text,
    is_research_table_like_text,
    is_research_noise_sentence,
    ordered_chunks,
    research_text_after_heading,
    strip_leading_heading,
)
from app.documents.schemas import DocumentFactRead, DocumentProfileRead
from app.retrieval.answers import AnswerCitation, AnswerQuality, ExtractiveAnswer
from app.retrieval.query_router import QueryRoute

_MAX_ANSWER_CHUNKS = 3
_MAX_SUMMARY_CHARS = 480
_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_RESEARCH_RESULT_CLAIM_TERMS = {
    "achieve",
    "achieved",
    "achieves",
    "achieving",
    "demonstrate",
    "demonstrated",
    "demonstrates",
    "finding",
    "findings",
    "highlight",
    "highlighted",
    "highlights",
    "improve",
    "improved",
    "improvement",
    "outperform",
    "outperformed",
    "outperforms",
    "performance",
    "result",
    "results",
    "show",
    "shown",
    "shows",
}
_RESEARCH_PARAMETER_SETTING_PATTERN = re.compile(
    r"\b(?:number of .*heads|transformer heads|layers|dimensions?|embedding|width|parameters?|"
    r"H\s*=|L[VTL]?\s*=|D[VTL]?\s*=|batch size|learning rate)\b",
    re.IGNORECASE,
)
_RESEARCH_METHOD_SNIPPET_TERMS = {
    "architecture",
    "attention",
    "encoder",
    "framework",
    "fusion",
    "model",
    "module",
    "pipeline",
    "prompt",
    "temporal",
    "token",
    "transformer",
    "visual",
}
_RESEARCH_LIMITATION_CLAIM_TERMS = {
    "adaptation",
    "bottleneck",
    "bottlenecks",
    "challenge",
    "challenges",
    "direction",
    "directions",
    "future",
    "goal",
    "limitation",
    "limitations",
    "limited",
    "mapping",
    "overcome",
    "refinement",
    "room",
}
_RESEARCH_FUTURE_DIRECTION_PATTERN = re.compile(
    r"\b(?:future research directions include|future directions include|future work|to address these challenges)\b",
    re.IGNORECASE,
)
_QUERY_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "about",
    "does",
    "document",
    "discussed",
    "in",
    "is",
    "mentioned",
    "or",
    "reported",
    "the",
    "this",
    "used",
    "what",
    "which",
}
_INVOICE_AMOUNT_QUERY_PATTERNS = {
    "amount due",
    "balance due",
    "invoice amount",
    "invoice total",
    "payment due",
    "subtotal",
    "total amount",
    "total due",
}


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


def _normalized(text: str) -> str:
    return " ".join(_WORD_PATTERN.findall(text.lower()))


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


def _answer_text_for_chunk(chunk: Chunk, profile: DocumentProfileRead, route: QueryRoute) -> str:
    heading = chunk_heading(chunk)
    if profile.document_type != "research_paper":
        return strip_leading_heading(chunk.text, heading)

    target_heading = heading
    if route.intent == "overview" and "ABSTRACT" in clean_text(chunk.text):
        target_heading = "ABSTRACT"
    text = research_text_after_heading(chunk.text, target_heading)
    return clean_research_text(text)


def _research_snippet(text: str, query: str, *, intent: str | None = None, prefer_first: bool = False) -> str:
    cleaned = clean_research_text(text)
    sentences = [
        sentence.strip()
        for sentence in _SENTENCE_BOUNDARY.split(cleaned)
        if sentence.strip() and not is_research_noise_sentence(sentence)
    ]
    if not sentences:
        return ""
    if prefer_first:
        if intent == "overview":
            selected_sentences: list[str] = []
            for sentence in sentences[:3]:
                candidate = " ".join([*selected_sentences, sentence])
                if len(candidate) > _MAX_SUMMARY_CHARS and selected_sentences:
                    break
                selected_sentences.append(sentence)
            selected = " ".join(selected_sentences)
        else:
            selected = sentences[0]
    else:
        query_words = _words(query).difference(_QUERY_STOPWORDS)

        def score_sentence(sentence: str, index: int) -> tuple[int, int, int]:
            sentence_words = _words(sentence)
            lower_sentence = sentence.lower()
            intent_score = 0
            if intent == "methods":
                intent_score = len(sentence_words.intersection(_RESEARCH_METHOD_SNIPPET_TERMS))
            elif intent == "results":
                intent_score = len(sentence_words.intersection(_RESEARCH_RESULT_CLAIM_TERMS))
                if any(metric in lower_sentence for metric in ("top1", "top-1", "top5", "top-5", "f1", "accuracy")):
                    intent_score += 2
                if _RESEARCH_PARAMETER_SETTING_PATTERN.search(sentence):
                    intent_score -= 4
            elif intent == "limitations":
                intent_score = len(sentence_words.intersection(_RESEARCH_LIMITATION_CLAIM_TERMS))
                if _RESEARCH_FUTURE_DIRECTION_PATTERN.search(sentence):
                    intent_score += 5
            else:
                intent_score = int(
                    bool(
                        sentence_words.intersection(
                            {"achieve", "achieved", "result", "results", "propose", "proposed", "method", "future"}
                        )
                    )
                )
            return (
                intent_score,
                len(sentence_words.intersection(query_words)),
                -index,
            )

        selected = max(
            enumerate(sentences),
            key=lambda item: score_sentence(item[1], item[0]),
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
        answer_text = _answer_text_for_chunk(chunk, profile, route)
        snippet = (
            _research_snippet(answer_text, query, intent=route.intent, prefer_first=prefer_first_sentence)
            if profile.document_type == "research_paper"
            else _snippet(answer_text, query, prefer_first=prefer_first_sentence)
        )
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
    return clean_text(" ".join(part for part in (chunk_heading(chunk), chunk.text) if part)).lower()


def _chunks_by_heading_or_terms(
    document: Document,
    *,
    headings: set[str],
    terms: set[str],
    exclude_references: bool = True,
    prefer_heading_matches: bool = False,
    exclude_table_like: bool = False,
    include_following_unheaded: bool = False,
) -> list[Chunk]:
    matches: list[Chunk] = []
    heading_matches: list[Chunk] = []
    term_matches: list[Chunk] = []
    carry_heading_match = False
    for chunk in ordered_chunks(document):
        heading = chunk_heading(chunk)
        if exclude_references and (heading == "REFERENCES" or _chunk_text(chunk).startswith("references")):
            carry_heading_match = False
            continue
        if exclude_table_like and is_research_table_like_text(chunk.text):
            continue
        normalized_text = _chunk_text(chunk)
        if heading in headings:
            heading_matches.append(chunk)
            carry_heading_match = True
        elif include_following_unheaded and carry_heading_match and heading is None:
            heading_matches.append(chunk)
        else:
            if heading is not None:
                carry_heading_match = False
            if any(term in normalized_text for term in terms):
                term_matches.append(chunk)
    if prefer_heading_matches and heading_matches:
        return heading_matches
    matches.extend(heading_matches)
    matches.extend(term_matches)
    return matches


def _research_answer_chunk_score(chunk: Chunk, intent: str) -> int:
    heading = chunk_heading(chunk)
    text = clean_research_text(research_text_after_heading(chunk.text, heading)).lower()
    words = set(_WORD_PATTERN.findall(text))
    score = 0
    if intent == "results":
        score += 4 if heading in {"RESULT", "RESULTS", "EVALUATION", "EXPERIMENT", "EXPERIMENTS"} else 0
        score += 2 * len(words.intersection(_RESEARCH_RESULT_CLAIM_TERMS))
        if any(metric in text for metric in ("top1", "top-1", "top5", "top-5", "f1", "accuracy")):
            score += 3
        if _RESEARCH_PARAMETER_SETTING_PATTERN.search(text):
            score -= 8
    elif intent == "limitations":
        score += 4 if heading in {"LIMITATION", "LIMITATIONS", "FUTURE WORK", "CONCLUSION", "DISCUSSION"} else 0
        score += 2 * len(words.intersection(_RESEARCH_LIMITATION_CLAIM_TERMS))
        if _RESEARCH_FUTURE_DIRECTION_PATTERN.search(text):
            score += 8
        if text.startswith("this paper presents") and not _RESEARCH_FUTURE_DIRECTION_PATTERN.search(text):
            score -= 4
    return score


def _rank_research_answer_chunks(chunks: list[Chunk], intent: str) -> list[Chunk]:
    if intent not in {"results", "limitations"}:
        return chunks

    scored = [(_research_answer_chunk_score(chunk, intent), index, chunk) for index, chunk in enumerate(chunks)]
    if not scored:
        return chunks
    best_score = max(score for score, _index, _chunk in scored)
    if best_score <= 0:
        return chunks
    cutoff = max(1, best_score - 2)
    filtered = [(score, index, chunk) for score, index, chunk in scored if score >= cutoff]
    return [chunk for _score, _index, chunk in sorted(filtered, key=lambda item: (-item[0], item[1]))]


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


def _chunk_for_fact(document: Document, fact: DocumentFactRead) -> Chunk | None:
    lowered_value = fact.value.lower()
    for chunk in ordered_chunks(document):
        if lowered_value in chunk.text.lower():
            return chunk
    return None


def _fact_relevance(query: str, fact: DocumentFactRead) -> int:
    normalized_query = _normalized(query)
    searchable = _normalized(f"{fact.label} {fact.kind} {fact.source_text}")
    query_words = _words(query)
    score = len(query_words.intersection(_words(searchable)))

    label = fact.label.lower()
    source = fact.source_text.lower()
    if "total" in normalized_query and "total" in label:
        score += 6
    if "due" in normalized_query and "due" in label:
        score += 5
    if "payment" in normalized_query and ("payment" in source or "due" in label):
        score += 2
    if "issue" in normalized_query and "issue" in label:
        score += 5
    if "effective" in normalized_query and "effective" in label:
        score += 5
    if "subtotal" in normalized_query and "subtotal" in label:
        score += 5
    if "tax" in normalized_query and "tax" in label:
        score += 5
    if ("billed to" in normalized_query or "bill to" in normalized_query) and "bill to" in source:
        score += 5
    if fact.kind == "metric" and any(term in normalized_query for term in ("amount", "total", "metric", "number")):
        score += 1
    return score


def _rank_facts(query: str, facts: list[DocumentFactRead]) -> list[DocumentFactRead]:
    ranked = sorted(facts, key=lambda fact: _fact_relevance(query, fact), reverse=True)
    if not ranked:
        return []
    best_score = _fact_relevance(query, ranked[0])
    if best_score <= 0:
        return ranked[:_MAX_ANSWER_CHUNKS]
    return [fact for fact in ranked if _fact_relevance(query, fact) == best_score][:_MAX_ANSWER_CHUNKS]


def _fact_label(fact: DocumentFactRead) -> str:
    return fact.label[:1].upper() + fact.label[1:]


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
    pairs: list[tuple[DocumentFactRead, Chunk]] = []
    seen_values: set[str] = set()
    for fact in _rank_facts(query, facts):
        chunk = _chunk_for_fact(document, fact)
        if chunk is None:
            continue
        key = f"{fact.kind}:{fact.value.lower()}"
        if key in seen_values:
            continue
        seen_values.add(key)
        pairs.append((fact, chunk))
        if len(pairs) >= _MAX_ANSWER_CHUNKS:
            break

    if not pairs:
        return None

    citations: list[AnswerCitation] = []
    seen_chunk_ids: set[str] = set()
    for _fact, chunk in pairs:
        if chunk.id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(chunk.id)
        citations.append(_citation(chunk))

    fact_text = f"{label.capitalize()} mentioned: " + ", ".join(
        f"{_fact_label(fact)}: {fact.value}" for fact, _chunk in pairs
    ) + "."
    return DocumentAwareAnswer(
        answer=ExtractiveAnswer(summary=fact_text, citations=citations),
        quality=_quality(
            status="answerable",
            confidence=confidence,
            reason=f"Document-aware {route.intent} answer built from extracted {label} evidence.",
            evidence_count=len(citations),
            suggested_questions=profile.suggested_questions,
        ),
        query_intent=route.intent,
        document_type=profile.document_type,
    )


def _dataset_answer(
    *,
    facts: list[DocumentFactRead],
    document: Document,
    profile: DocumentProfileRead,
    route: QueryRoute,
) -> DocumentAwareAnswer | None:
    selected_facts: list[DocumentFactRead] = []
    seen_values: set[str] = set()
    for fact in facts:
        key = fact.value.lower()
        if key in seen_values:
            continue
        seen_values.add(key)
        selected_facts.append(fact)
        if len(selected_facts) >= 8:
            break

    if not selected_facts:
        return None

    citations: list[AnswerCitation] = []
    seen_chunk_ids: set[str] = set()
    for fact in selected_facts:
        chunk = _chunk_for_fact(document, fact)
        if chunk is None or chunk.id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(chunk.id)
        citations.append(_citation(chunk))
        if len(citations) >= _MAX_ANSWER_CHUNKS:
            break

    if not citations:
        return None

    return DocumentAwareAnswer(
        answer=ExtractiveAnswer(
            summary="Datasets mentioned: " + ", ".join(fact.value for fact in selected_facts) + ".",
            citations=citations,
        ),
        quality=_quality(
            status="answerable",
            confidence="strong",
            reason="Document-aware datasets answer built from extracted dataset evidence.",
            evidence_count=len(citations),
            suggested_questions=profile.suggested_questions,
        ),
        query_intent=route.intent,
        document_type=profile.document_type,
    )


def _overview_answer(query: str, document: Document, profile: DocumentProfileRead, route: QueryRoute) -> DocumentAwareAnswer | None:
    if profile.document_type == "research_paper":
        chunks = _chunks_by_heading_or_terms(
            document,
            headings={"ABSTRACT"},
            terms={"abstract"},
            prefer_heading_matches=True,
        )
        used_preferred_heading = any(
            chunk_heading(chunk) == "ABSTRACT" or _chunk_text(chunk).startswith("abstract") for chunk in chunks
        )
        if not used_preferred_heading:
            chunks = []
        if not chunks:
            chunks = _chunks_by_heading_or_terms(
                document,
                headings={"INTRODUCTION", "CONCLUSION"},
                terms=set(),
                prefer_heading_matches=True,
            )
            used_preferred_heading = bool(chunks and any(chunk_heading(chunk) in {"INTRODUCTION", "CONCLUSION"} for chunk in chunks))
    else:
        chunks = _chunks_by_heading_or_terms(
            document,
            headings={"ABSTRACT", "EXECUTIVE SUMMARY", "SUMMARY", "ABOUT ME", "OVERVIEW", "INTRODUCTION"},
            terms={"abstract", "executive summary", "overview", "introduction", "this paper", "this report"},
        )
        used_preferred_heading = bool(chunks)
    if not chunks:
        chunks = _fallback_opening_chunks(document)
        used_preferred_heading = False
    return _build_answer(
        query=query,
        chunks=chunks,
        profile=profile,
        route=route,
        confidence="strong" if used_preferred_heading else "moderate",
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
    normalized_query = _normalized(query)
    if profile.document_type == "research_paper" and any(
        pattern in normalized_query for pattern in _INVOICE_AMOUNT_QUERY_PATTERNS
    ):
        return _no_answer(
            "This document is classified as a research paper, so invoice totals or payment due amounts are not expected. "
            "Ask about metrics, datasets, results, methods, or limitations instead.",
            profile,
            route,
        )

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
    prefer_heading_matches: bool = False,
    require_heading_for_strong: bool = False,
    exclude_table_like: bool = False,
    include_following_unheaded: bool = False,
) -> DocumentAwareAnswer | None:
    chunks = _chunks_by_heading_or_terms(
        document,
        headings=headings,
        terms=terms,
        prefer_heading_matches=prefer_heading_matches,
        exclude_table_like=exclude_table_like,
        include_following_unheaded=include_following_unheaded,
    )
    if profile.document_type == "research_paper":
        chunks = _rank_research_answer_chunks(chunks, route.intent)
    answer_confidence = confidence
    if require_heading_for_strong and confidence == "strong":
        has_heading_evidence = any(chunk_heading(chunk) in headings for chunk in chunks[:_MAX_ANSWER_CHUNKS])
        if not has_heading_evidence:
            answer_confidence = "moderate"
    return _build_answer(
        query=query,
        chunks=chunks,
        profile=profile,
        route=route,
        confidence=answer_confidence,
        reason=f"Document-aware {route.intent} answer built from matching sections.",
    )


def _build_section_body_answer(
    *,
    query: str,
    chunks: list[Chunk],
    profile: DocumentProfileRead,
    route: QueryRoute,
    confidence: Literal["strong", "moderate", "weak"],
    reason: str,
) -> DocumentAwareAnswer | None:
    selected_chunks = chunks[:_MAX_ANSWER_CHUNKS]
    snippets: list[str] = []
    citations: list[AnswerCitation] = []
    seen_chunk_ids: set[str] = set()
    for chunk in selected_chunks:
        if chunk.id in seen_chunk_ids:
            continue
        seen_chunk_ids.add(chunk.id)
        body = clean_text(_answer_text_for_chunk(chunk, profile, route))
        if not body:
            continue
        snippet = body if len(body) <= _MAX_SUMMARY_CHARS else body[: _MAX_SUMMARY_CHARS - 3].rstrip() + "..."
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


def _resume_section_answer(
    query: str,
    document: Document,
    profile: DocumentProfileRead,
    route: QueryRoute,
) -> DocumentAwareAnswer | None:
    section_map: dict[str, tuple[set[str], set[str]]] = {
        "skills": (
            {"TECHNICAL SKILLS", "CORE SKILLS", "SKILLS", "PROGRAMMING LANGUAGES", "FRAMEWORKS", "TOOLS"},
            {"skill", "skills", "python", "sql", "machine learning", "framework", "tool"},
        ),
        "programming_language": (
            {"PROGRAMMING LANGUAGES", "TECHNICAL SKILLS", "CORE SKILLS", "SKILLS"},
            {"programming language", "python", "javascript", "sql", "c++", "java"},
        ),
        "frameworks": (
            {"FRAMEWORKS", "LIBRARIES", "TECHNICAL SKILLS", "CORE SKILLS", "SKILLS"},
            {"framework", "frameworks", "library", "libraries", "pytorch", "tensorflow", "react"},
        ),
        "tools": (
            {"TOOLS", "PLATFORMS", "TECHNICAL SKILLS", "CORE SKILLS", "SKILLS"},
            {"tool", "tools", "platform", "git", "docker", "figma"},
        ),
        "projects": (
            {"PROJECTS", "SELECTED PROJECTS", "RESEARCH PROJECTS", "ACADEMIC PROJECTS"},
            {"project", "projects", "dashboard", "classification", "prediction", "system"},
        ),
        "education": (
            {"EDUCATION", "ACADEMIC BACKGROUND", "QUALIFICATIONS"},
            {"education", "degree", "university", "college", "cgpa"},
        ),
        "experience": (
            {"EXPERIENCE", "WORK EXPERIENCE", "EMPLOYMENT", "PROFESSIONAL EXPERIENCE"},
            {"experience", "work history", "employment", "internship", "tutor"},
        ),
    }
    section_config = section_map.get(route.intent)
    if section_config is None:
        return None

    headings, terms = section_config
    chunks = _chunks_by_heading_or_terms(
        document,
        headings=headings,
        terms=terms,
        prefer_heading_matches=True,
    )
    return _build_section_body_answer(
        query=query,
        chunks=chunks,
        profile=profile,
        route=route,
        confidence="strong" if any(chunk_heading(chunk) in headings for chunk in chunks[:1]) else "moderate",
        reason=f"Document-aware {route.intent} answer built from resume sections.",
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
    if route.intent == "payment_due":
        result = _date_answer(query, document, profile, route)
        if result is not None:
            return result
        return _section_answer(
            query,
            document,
            profile,
            route,
            headings={"PAYMENT TERMS", "PAYMENT SUMMARY", "PAYMENT"},
            terms={"payment due", "due date", "balance due", "total due"},
            confidence="strong",
        ) or _no_answer("No payment due date evidence was detected in this document.", profile, route)
    if route.intent == "amounts":
        result = _amount_answer(query, document, profile, route)
        return result or _no_answer("No amounts, totals, or measurable metrics were detected in this document.", profile, route)
    if route.intent == "payment_terms":
        return _section_answer(
            query,
            document,
            profile,
            route,
            headings={"PAYMENT TERMS", "PAYMENT SUMMARY", "PAYMENT"},
            terms={"payment terms", "payment term", "due date", "balance due", "total due"},
            confidence="strong",
        )
    if route.intent == "parties":
        result = _party_answer(query, document, profile, route)
        return result or _no_answer("No party, vendor, client, or bill-to evidence was detected in this document.", profile, route)
    if profile.document_type == "resume" and route.intent in {
        "skills",
        "programming_language",
        "frameworks",
        "tools",
        "projects",
        "education",
        "experience",
    }:
        result = _resume_section_answer(query, document, profile, route)
        return result or _no_answer("No matching resume section evidence was detected in this document.", profile, route)
    if route.intent == "datasets":
        dataset_facts = [fact for fact in profile.key_entities if fact.kind == "dataset"]
        result = _dataset_answer(
            facts=dataset_facts,
            document=document,
            profile=profile,
            route=route,
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
            terms={
                "approach",
                "architecture",
                "attention",
                "encoder",
                "framework",
                "fusion",
                "method",
                "model",
                "module",
                "pipeline",
                "propose",
                "proposed",
                "temporal",
                "transformer",
                "visual",
            },
            confidence="strong",
            prefer_heading_matches=profile.document_type == "research_paper",
            require_heading_for_strong=profile.document_type == "research_paper",
            exclude_table_like=profile.document_type == "research_paper",
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
            prefer_heading_matches=profile.document_type == "research_paper",
            require_heading_for_strong=profile.document_type == "research_paper",
            include_following_unheaded=profile.document_type == "research_paper",
        )
    if route.intent == "recommendations":
        return _section_answer(
            query,
            document,
            profile,
            route,
            headings={"RECOMMENDATIONS", "NEXT STEPS", "CONCLUSION"},
            terms={"recommendation", "recommendations", "recommend", "should", "next steps"},
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
            prefer_heading_matches=profile.document_type == "research_paper",
            include_following_unheaded=profile.document_type == "research_paper",
        )
    return None
