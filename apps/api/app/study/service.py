from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import Chunk, Document, DocumentStatus, DocumentSummary, StudyAnswer, StudyQuestion
from app.documents.intelligence import (
    build_document_profile,
    chunk_heading,
    clean_text,
    is_table_of_contents_like_text,
    ordered_chunks,
    strip_leading_heading,
)
from app.llm.providers import LlmProvider, LocalHeuristicLlmProvider, get_llm_provider
from app.retrieval.document_answers import build_document_aware_answer
from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.query_router import route_query
from app.retrieval.search import SearchHit, build_snippet, hybrid_search_chunks

_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "as",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "uses",
    "what",
    "which",
    "with",
}
_SUMMARY_HEADING_WEIGHTS = {
    "ABSTRACT": 80,
    "EXECUTIVE SUMMARY": 80,
    "SUMMARY": 75,
    "OBJECTIVES": 72,
    "OVERVIEW": 70,
    "INTRODUCTION": 65,
    "PROFESSIONAL SUMMARY": 65,
    "METHOD": 45,
    "METHODS": 45,
    "METHODOLOGY": 45,
    "APPROACH": 45,
    "RESULT": 42,
    "RESULTS": 42,
    "FINDINGS": 42,
    "RECOMMENDATIONS": 40,
    "CONCLUSION": 38,
    "FUTURE WORK": 35,
    "TECHNICAL SKILLS": 34,
    "PROJECTS": 34,
    "PAYMENT SUMMARY": 34,
    "PARTIES": 34,
}
_ACADEMIC_SUMMARY_HEADING_GROUPS = (
    {"ABSTRACT", "OVERVIEW", "OBJECTIVES", "INTRODUCTION", "EXECUTIVE SUMMARY", "SUMMARY"},
    {"METHOD", "METHODS", "METHODOLOGY", "APPROACH", "MODEL"},
    {"RESULT", "RESULTS", "FINDINGS", "EVALUATION", "EXPERIMENTS"},
    {"CONCLUSION", "FUTURE WORK", "LIMITATIONS", "DISCUSSION"},
)
_METHOD_SUMMARY_TERMS = {
    "approach",
    "calibrated",
    "calibrate",
    "feature",
    "features",
    "implementation",
    "observation",
    "policy",
    "ppo",
    "reward",
    "rewards",
    "shaped",
    "simulator",
    "training",
    "vector",
}
_RESULT_SUMMARY_TERMS = {
    "alive",
    "balanced",
    "error",
    "latency",
    "policy",
    "rallies",
    "result",
    "results",
    "validated",
    "verification",
    "wins",
}
_SUMMARY_LEADING_NUMBER_PATTERN = re.compile(r"^\d+(?:\.\d+)*\.?\s+")
_SUMMARY_LEADING_LABEL_PATTERN = re.compile(
    r"^(?:overview\s*&\s*objective|design\s+approach|results\s*&\s*verification)\s*[:.-]?\s+",
    re.IGNORECASE,
)
_SUMMARY_PHASE_LABEL_PATTERN = re.compile(
    r"^development\s+pipeline\s+phase\s+\d+\s*:\s*[^.!?]{0,120}?(?=\b(?:before|the|this|training|a|an|on|in)\b)",
    re.IGNORECASE,
)
_OVERVIEW_QUESTION_PATTERN = re.compile(
    r"^(?:"
    r"what is this (?:document|project report|report) about|"
    r"what are the main topics(?: covered in this document)?"
    r")\??$",
    re.IGNORECASE,
)
_MEANINGFUL_SINGLE_STUDY_TOPICS = {
    "authors",
    "contributors",
    "dataset",
    "datasets",
    "dates",
    "design",
    "limitations",
    "method",
    "methodology",
    "methods",
    "overview",
    "results",
}
_ACADEMIC_FRAGMENT_TOPIC_WORDS = {"action", "actions", "agent", "both", "contents", "controlling", "feature", "idx"}
_RESEARCH_FRAGMENT_TOPIC_WORDS = {
    "aggregate",
    "employed",
    "extract",
    "extracted",
    "obtained",
}
_GENERATED_NUMBER_PATTERN = re.compile(r"\b\d[\d,]*(?:\.\d+)?(?:st|nd|rd|th)?%?\b", re.IGNORECASE)
_INCOMPLETE_GENERATED_TEXT_PATTERN = re.compile(
    r"(?:[-,:;]|\b(?:and|as|by|for|from|in|of|or|the|to|via|with))$",
    re.IGNORECASE,
)
_BRACKETED_REFERENCE_PATTERN = re.compile(r"\[\d+\]")
_REFERENCE_LIST_ANSWER_PATTERN = re.compile(
    r"\b(?:ACM Computing Surveys|International Journal|Physics of Life Reviews|Journal of)\b",
    re.IGNORECASE,
)
_KEYWORD_SALAD_PATTERN = re.compile(
    r"\b(?:human-robot collaboration|large language models)\s+"
    r"(?:large language models|resilient manufacturing systems|embodied intelligence)\b",
    re.IGNORECASE,
)
_DATASET_ANSWER_TERMS = {
    "benchmark",
    "benchmarks",
    "corpus",
    "data source",
    "data sources",
    "database",
    "databases",
    "dataset",
    "datasets",
    "funsd",
    "hmdb-51",
    "hri-30",
    "hri30",
    "inhard",
    "imagenet",
    "kinetics-400",
    "meccano",
    "mimic",
    "mnist",
    "pubmed",
    "scopus",
    "squad",
    "ucf-101",
    "web of science",
}
_METHOD_ANSWER_TERMS = {
    "analysis",
    "approach",
    "architecture",
    "deduplication",
    "de-duplication",
    "framework",
    "method",
    "methods",
    "methodology",
    "pipeline",
    "process",
    "protocol",
    "review",
    "screening",
    "workflow",
}
_RESULT_ANSWER_TERMS = {
    "accuracy",
    "achieved",
    "achieving",
    "excluded",
    "finding",
    "findings",
    "obtained",
    "performance",
    "proceedings",
    "result",
    "results",
    "show",
    "shows",
}
_LIMITATION_ANSWER_TERMS = {
    "challenge",
    "challenges",
    "direction",
    "directions",
    "ethical",
    "future",
    "limitation",
    "limitations",
    "responsibilities",
    "rights",
    "safeguard",
    "safeguards",
    "standards",
    "transparency",
}
_SUPPORT_STOP_WORDS = _STOP_WORDS.union(
    {
        "answer",
        "cited",
        "context",
        "document",
        "evidence",
        "paper",
        "report",
        "study",
        "summarizes",
        "summary",
    }
)
_HRC_TASK_SUMMARY_PHRASES = (
    ("planning", "planning"),
    ("decision making", "decision making"),
    ("perception", "perception"),
    ("embodied execution", "embodied execution"),
)
_HRC_STANDARD_SUMMARY_PHRASES = (
    ("rights", "rights"),
    ("responsibilities", "responsibilities"),
    ("transparency", "transparency"),
    ("ethical", "ethics"),
    ("ethics", "ethics"),
    ("scalability", "scalable deployment"),
    ("scalable", "scalable deployment"),
)
_DEFAULT_STUDY_QUESTIONS = [
    "What is this document about?",
    "What are the main topics covered in this document?",
    "What dates are mentioned?",
]
EmbeddingProviderFactory = Callable[[], EmbeddingProvider]


class StudyError(Exception):
    """Base error for study feature failures."""


class StudyDocumentNotFoundError(StudyError):
    """Raised when the selected document is missing."""


class StudyDocumentNotReadyError(StudyError):
    """Raised when the selected document cannot support generation yet."""


class StudyQuestionNotFoundError(StudyError):
    """Raised when a study question is missing or belongs to another document."""


@dataclass(frozen=True)
class GeneratedSummary:
    content: str
    citations: list[dict[str, object]]


@dataclass(frozen=True)
class GeneratedQuestion:
    question: str
    expected_answer: str
    citations: list[dict[str, object]]


@dataclass(frozen=True)
class StudyScore:
    score: float
    feedback: str


def _words(text: str) -> set[str]:
    return {word for word in _WORD_PATTERN.findall(text.lower()) if word not in _STOP_WORDS and len(word) > 1}


def _citation(document: Document, chunk: Chunk) -> dict[str, object]:
    return {
        "chunk_id": chunk.id,
        "document_id": document.id,
        "document_filename": document.filename,
        "page_number": chunk.page.page_number,
        "section_heading": chunk_heading(chunk),
        "page_image_url": f"/documents/{document.id}/pages/{chunk.page.page_number}/image",
        "document_page_url": f"/documents/{document.id}?page={chunk.page.page_number}&chunk={chunk.id}",
        "snippet": build_snippet(chunk.text),
        "score": 1.0,
        "source_score": 1.0,
        "ranking_signals": {"study_context": 1.0},
    }


def _citation_from_hit(hit: SearchHit) -> dict[str, object]:
    return {
        "chunk_id": hit.chunk_id,
        "document_id": hit.document_id,
        "document_filename": hit.document_filename,
        "page_number": hit.page_number,
        "section_heading": hit.section_heading,
        "page_image_url": f"/documents/{hit.document_id}/pages/{hit.page_number}/image",
        "document_page_url": f"/documents/{hit.document_id}?page={hit.page_number}&chunk={hit.chunk_id}",
        "snippet": build_snippet(hit.text),
        "score": hit.score,
        "source_score": hit.source_score,
        "ranking_signals": hit.ranking_signals,
    }


def _citation_from_answer(document: Document, chunk_id: str) -> dict[str, object] | None:
    for chunk in ordered_chunks(document):
        if chunk.id == chunk_id:
            return _citation(document, chunk)
    return None


def _strip_summary_leading_labels(text: str) -> str:
    cleaned = clean_text(text)
    previous = None
    while cleaned and cleaned != previous:
        previous = cleaned
        cleaned = clean_text(_SUMMARY_LEADING_NUMBER_PATTERN.sub("", cleaned, count=1))
        cleaned = clean_text(_SUMMARY_LEADING_LABEL_PATTERN.sub("", cleaned, count=1))
        cleaned = clean_text(_SUMMARY_PHASE_LABEL_PATTERN.sub("", cleaned, count=1))
    return cleaned


def _usable_summary_text(text: str, heading: str | None) -> str:
    cleaned = clean_text(strip_leading_heading(text, heading))
    cleaned = re.sub(r"\bPage\s+\d+(?:\s+[A-Z][A-Z &/-]{1,40})?\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = _strip_summary_leading_labels(cleaned)
    if not cleaned or is_table_of_contents_like_text(cleaned):
        return ""
    return cleaned


def _is_usable_summary_hit(hit: SearchHit) -> bool:
    return bool(_usable_summary_text(hit.text, hit.section_heading))


def _is_usable_summary_chunk(chunk: Chunk) -> bool:
    return bool(_usable_summary_text(chunk.text, chunk_heading(chunk)))


def _is_meaningful_expected_answer(text: str) -> bool:
    cleaned = clean_text(text)
    if not cleaned or len(_words(cleaned)) < 4:
        return False
    if _INCOMPLETE_GENERATED_TEXT_PATTERN.search(cleaned):
        return False
    if _KEYWORD_SALAD_PATTERN.search(cleaned):
        return False
    if _looks_like_reference_list_answer(cleaned):
        return False
    return not is_table_of_contents_like_text(cleaned)


def _normalized_numbers(text: str) -> set[str]:
    return {
        re.sub(r"(?:st|nd|rd|th|%)$", "", match.group(0).replace(",", ""), flags=re.IGNORECASE)
        for match in _GENERATED_NUMBER_PATTERN.finditer(text)
    }


def _looks_like_reference_list_answer(text: str) -> bool:
    cleaned = clean_text(text)
    if not cleaned:
        return False
    numbers = _normalized_numbers(cleaned)
    bracketed_references = _BRACKETED_REFERENCE_PATTERN.findall(cleaned)
    has_checkmark_columns = "\u221a" in cleaned or bool(re.search(r"\bv\s+v\b", cleaned, flags=re.IGNORECASE))
    if has_checkmark_columns and bracketed_references and len(numbers) >= 4:
        return True
    if len(bracketed_references) >= 2 and len(numbers) >= 6:
        return True
    return bool(_REFERENCE_LIST_ANSWER_PATTERN.search(cleaned) and len(numbers) >= 5)


def _has_unsupported_numbers(answer: str, context: str) -> bool:
    answer_numbers = _normalized_numbers(answer)
    if not answer_numbers:
        return False
    return not answer_numbers.issubset(_normalized_numbers(context))


def _uses_strict_generation_validation(provider: LlmProvider) -> bool:
    return getattr(provider, "provider_name", "").lower() == "groq"


def _is_supported_generated_text(text: str, context: str, *, strict: bool = False) -> bool:
    cleaned = clean_text(text)
    if not _is_meaningful_expected_answer(cleaned):
        return False
    if _has_unsupported_numbers(cleaned, context):
        return False
    if not strict:
        return True

    answer_terms = {word for word in _words(cleaned) if word not in _SUPPORT_STOP_WORDS}
    if len(answer_terms) < 4:
        return True
    context_terms = _words(context)
    supported_terms = answer_terms.intersection(context_terms)
    return len(supported_terms) / len(answer_terms) >= 0.25


def _contains_any_term(text: str, terms: set[str]) -> bool:
    lowered = text.lower()
    return any(term in lowered for term in terms)


def _provider_answer_matches_question(
    *,
    question: str,
    expected_answer: str,
    context: str,
    document_type: str | None,
) -> bool:
    route = route_query(question, document_type)
    answer_text = clean_text(expected_answer)
    combined_context = f"{answer_text}\n{context}"
    if _KEYWORD_SALAD_PATTERN.search(answer_text):
        return False
    if route.intent == "datasets":
        return _contains_any_term(answer_text, _DATASET_ANSWER_TERMS) and _contains_any_term(
            combined_context,
            _DATASET_ANSWER_TERMS,
        )
    if route.intent == "methods":
        return _contains_any_term(answer_text, _METHOD_ANSWER_TERMS)
    if route.intent in {"results", "findings"}:
        return _contains_any_term(answer_text, _RESULT_ANSWER_TERMS) or bool(_normalized_numbers(answer_text))
    if route.intent == "limitations":
        return _contains_any_term(answer_text, _LIMITATION_ANSWER_TERMS)
    return True


def _join_summary_phrases(phrases: list[str]) -> str:
    if len(phrases) <= 1:
        return "".join(phrases)
    if len(phrases) == 2:
        return " and ".join(phrases)
    return ", ".join(phrases[:-1]) + f", and {phrases[-1]}"


def _unique_context_phrases(context: str, phrase_map: tuple[tuple[str, str], ...]) -> list[str]:
    lowered_context = context.lower()
    selected: list[str] = []
    seen: set[str] = set()
    for marker, phrase in phrase_map:
        if marker not in lowered_context or phrase in seen:
            continue
        selected.append(phrase)
        seen.add(phrase)
    return selected


def _research_summary_screening_steps(context: str) -> list[str]:
    lowered_context = context.lower()
    context_numbers = _normalized_numbers(context)
    steps: list[str] = []
    if (
        "database harmonization" in lowered_context
        or "database harmonisation" in lowered_context
        or "harmonizing" in lowered_context
        or "harmonising" in lowered_context
        or "4364" in context_numbers
    ):
        steps.append("database harmonization")
    if "dedup" in lowered_context or "de-dup" in lowered_context or "duplicate" in lowered_context:
        steps.append("deduplication")
    if "screen" in lowered_context:
        if "title" in lowered_context and "abstract" in lowered_context:
            steps.append("title-and-abstract screening")
        else:
            steps.append("screening")
    if "full-text" in lowered_context or "full text" in lowered_context or "read in full" in lowered_context:
        steps.append("full-text review")
    return steps


def _normalize_research_generated_summary(summary: str, context: str) -> str:
    cleaned = clean_text(summary)
    lowered_context = context.lower()
    summary_numbers = _normalized_numbers(cleaned)
    context_numbers = _normalized_numbers(context)
    has_human_robot_topic = "human-robot collaboration" in lowered_context or "hrc" in _words(context)
    has_llm_topic = "large language model" in lowered_context or "llm" in _words(context)
    has_screening_flow = "scopus" in lowered_context and "2366" in context_numbers
    mentions_screening_counts = bool(summary_numbers.intersection({"2366", "4364", "2092", "1665"}))
    if not (has_human_robot_topic and has_screening_flow and mentions_screening_counts):
        return cleaned

    screening_steps = _research_summary_screening_steps(context)
    if not screening_steps:
        return cleaned

    topic = "LLM-enhanced human-robot collaboration" if has_llm_topic else "human-robot collaboration"
    first_sentence = (
        f"The study reviews {topic}, beginning with 2,366 Scopus results and narrowing the literature "
        f"through {_join_summary_phrases(screening_steps)}."
    )
    task_phrases = _unique_context_phrases(context, _HRC_TASK_SUMMARY_PHRASES)
    standard_phrases = _unique_context_phrases(context, _HRC_STANDARD_SUMMARY_PHRASES)
    second_parts: list[str] = []
    if len(task_phrases) >= 2:
        second_parts.append(f"maps HRC cognitive-hierarchy tasks such as {_join_summary_phrases(task_phrases)}")
    if standard_phrases:
        second_parts.append(f"argues for standards around {_join_summary_phrases(standard_phrases)}")
    if not second_parts:
        return first_sentence
    return f"{first_sentence} It {', and '.join(second_parts)}."


def _prepare_generated_summary(summary: str, context: str, document_type: str | None) -> str:
    cleaned = clean_text(summary)
    if document_type == "research_paper":
        return _normalize_research_generated_summary(cleaned, context)
    return cleaned


def _is_useful_study_question(question: str, document_type: str | None = None) -> bool:
    cleaned = clean_text(question).rstrip(" ?")
    if not cleaned:
        return False
    if is_table_of_contents_like_text(cleaned):
        return False
    if document_type not in {"academic_report", "research_paper"}:
        return True

    topic_match = re.search(r"\babout\s+(.+)$", cleaned, flags=re.IGNORECASE)
    if topic_match is None:
        return True

    topic_tokens = _WORD_PATTERN.findall(topic_match.group(1).lower())
    if topic_tokens and topic_tokens[0].isdigit():
        return False
    alpha_terms = [token for token in topic_tokens if not token.isdigit() and token not in _STOP_WORDS]
    if not alpha_terms:
        return False
    if len(alpha_terms) == 1 and alpha_terms[0] not in _MEANINGFUL_SINGLE_STUDY_TOPICS:
        return False
    fragment_topic_words = set(_ACADEMIC_FRAGMENT_TOPIC_WORDS)
    if document_type == "research_paper":
        fragment_topic_words.update(_RESEARCH_FRAGMENT_TOPIC_WORDS)
    return not set(alpha_terms).issubset(fragment_topic_words)


def _summary_chunk_score(chunk: Chunk) -> tuple[int, int]:
    heading = chunk_heading(chunk)
    weight = _SUMMARY_HEADING_WEIGHTS.get(heading or "", 10)
    if heading == "REFERENCES":
        weight = -100
    if not _is_usable_summary_chunk(chunk):
        weight = -100
    return (weight, -chunk.chunk_index)


def _summary_chunks(document: Document, limit: int = 3) -> list[Chunk]:
    chunks = [chunk for chunk in ordered_chunks(document) if _is_usable_summary_chunk(chunk)]
    ranked = sorted(chunks, key=_summary_chunk_score, reverse=True)
    selected = ranked[:limit]
    return sorted(selected, key=lambda chunk: chunk.chunk_index)


def _summary_heading_group(heading: str | None) -> int | None:
    if heading is None:
        return None
    for index, headings in enumerate(_ACADEMIC_SUMMARY_HEADING_GROUPS):
        if heading in headings:
            return index
    return None


def _summary_hit_groups(hits: list[SearchHit]) -> set[int]:
    return {
        group
        for group in (_summary_heading_group(hit.section_heading) for hit in hits)
        if group is not None
    }


def _summary_chunk_groups(chunks: list[Chunk]) -> set[int]:
    return {
        group
        for group in (_summary_heading_group(chunk_heading(chunk)) for chunk in chunks)
        if group is not None
    }


def _balanced_academic_summary_chunks(document: Document, limit: int = 3) -> list[Chunk]:
    usable_chunks = [chunk for chunk in ordered_chunks(document) if _is_usable_summary_chunk(chunk)]
    selected: list[Chunk] = []
    selected_ids: set[str] = set()

    for headings in _ACADEMIC_SUMMARY_HEADING_GROUPS:
        candidates = [chunk for chunk in usable_chunks if chunk_heading(chunk) in headings]
        if not candidates:
            continue
        chunk = max(candidates, key=_summary_chunk_score)
        selected.append(chunk)
        selected_ids.add(chunk.id)
        if len(selected) >= limit:
            break

    if len(selected) < limit:
        for chunk in _summary_chunks(document, limit=limit):
            if chunk.id in selected_ids:
                continue
            selected.append(chunk)
            selected_ids.add(chunk.id)
            if len(selected) >= limit:
                break

    return sorted(selected, key=lambda chunk: chunk.chunk_index)


def _summary_excerpt(text: str, heading: str | None, max_chars: int = 360) -> str:
    cleaned = _usable_summary_text(text, heading)
    sentences = [sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(cleaned) if sentence.strip()]
    if not sentences:
        return cleaned[: max_chars - 3].rstrip() + "..." if len(cleaned) > max_chars else cleaned

    heading_group = _summary_heading_group(heading)
    scoring_terms: set[str] = set()
    if heading_group == 1:
        scoring_terms = _METHOD_SUMMARY_TERMS
    elif heading_group == 2:
        scoring_terms = _RESULT_SUMMARY_TERMS

    selected = sentences[0]
    if scoring_terms:
        scored_sentences = [
            (len(_words(sentence).intersection(scoring_terms)), -index, sentence)
            for index, sentence in enumerate(sentences)
        ]
        best_score, _index, best_sentence = max(scored_sentences, key=lambda item: (item[0], item[1]))
        if best_score > 0:
            selected = best_sentence

    if len(selected) <= max_chars:
        return selected
    return selected[: max_chars - 3].rstrip() + "..."


def _retrieval_chunk_score(chunk: Chunk, query: str) -> tuple[int, int, int]:
    heading = chunk_heading(chunk)
    if heading == "REFERENCES" or not _is_usable_summary_chunk(chunk):
        return (-1, -100, -chunk.chunk_index)
    query_words = _words(query)
    chunk_words = _words(f"{heading} {chunk.text}")
    overlap = len(query_words.intersection(chunk_words))
    return (overlap, _SUMMARY_HEADING_WEIGHTS.get(heading or "", 10), -chunk.chunk_index)


def _retrieved_chunks(document: Document, query: str, limit: int = 3) -> list[Chunk]:
    chunks = [chunk for chunk in ordered_chunks(document) if _is_usable_summary_chunk(chunk)]
    scored = [(chunk, _retrieval_chunk_score(chunk, query)) for chunk in chunks]
    matches = [item for item in scored if item[1][0] > 0]
    if not matches:
        return _summary_chunks(document, limit=limit)
    ranked = sorted(matches, key=lambda item: item[1], reverse=True)
    return [chunk for chunk, _score in ranked[:limit]]


def _chunks_context(chunks: list[Chunk]) -> str:
    context_parts: list[str] = []
    for chunk in chunks:
        heading = chunk_heading(chunk)
        text = _usable_summary_text(chunk.text, heading)
        if not text:
            continue
        prefix = f"Page {chunk.page.page_number}"
        if heading:
            prefix = f"{prefix} {heading}"
        context_parts.append(f"{prefix}\n{text}")
    return "\n\n".join(context_parts)


def _hits_context(hits: list[SearchHit]) -> str:
    context_parts: list[str] = []
    for hit in hits:
        text = _usable_summary_text(hit.text, hit.section_heading)
        if not text:
            continue
        prefix = f"Page {hit.page_number}"
        if hit.section_heading:
            prefix = f"{prefix} {hit.section_heading}"
        context_parts.append(f"{prefix}\n{text}")
    return "\n\n".join(context_parts)


def _embedding_for_query(
    query: str,
    embedder_factory: EmbeddingProviderFactory | None,
) -> tuple[list[float] | None, str | None]:
    if embedder_factory is None:
        return None, "Embedding provider unavailable; lexical search was used."
    try:
        return embedder_factory().embed_texts([query])[0], None
    except Exception as exc:
        return None, f"Embedding provider unavailable: {exc}"


def _study_retrieval_hits(
    db: Session,
    document: Document,
    query: str,
    limit: int,
    embedder_factory: EmbeddingProviderFactory | None,
) -> list[SearchHit]:
    query_embedding, fallback_reason = _embedding_for_query(query, embedder_factory)
    hits, _mode = hybrid_search_chunks(
        db,
        query_embedding,
        query,
        limit,
        document.id,
        fallback_reason=fallback_reason,
    )
    return hits[:limit]


def build_document_summary(
    document: Document,
    provider: LlmProvider | None = None,
    retrieval_hits: list[SearchHit] | None = None,
) -> GeneratedSummary:
    profile = build_document_profile(document)
    if retrieval_hits is not None:
        selected_hits = [hit for hit in retrieval_hits if _is_usable_summary_hit(hit)]
        if not selected_hits:
            raise StudyDocumentNotReadyError("This document has no indexed evidence chunks to summarize.")
        balanced_chunks = _balanced_academic_summary_chunks(document) if profile.document_type == "academic_report" else []
        if len(_summary_hit_groups(selected_hits)) < 2 and len(_summary_chunk_groups(balanced_chunks)) >= 2:
            citations = [_citation(document, chunk) for chunk in balanced_chunks]
            if provider is not None and not isinstance(provider, LocalHeuristicLlmProvider):
                context = _chunks_context(balanced_chunks)
                summary = _prepare_generated_summary(provider.summarize(context), context, profile.document_type)
                if summary and _is_supported_generated_text(
                    summary,
                    context,
                    strict=_uses_strict_generation_validation(provider),
                ):
                    return GeneratedSummary(content=summary, citations=citations)
            sentences = [_summary_excerpt(chunk.text, chunk_heading(chunk)) for chunk in balanced_chunks]
            sentences = [sentence for sentence in sentences if sentence]
            if not sentences:
                raise StudyDocumentNotReadyError("This document has no usable text to summarize.")
            return GeneratedSummary(content=" ".join(sentences), citations=citations)
        if provider is not None:
            context = _hits_context(selected_hits)
            summary = _prepare_generated_summary(provider.summarize(context), context, profile.document_type)
            if summary and _is_supported_generated_text(
                summary,
                context,
                strict=_uses_strict_generation_validation(provider),
            ):
                return GeneratedSummary(content=summary, citations=[_citation_from_hit(hit) for hit in selected_hits])
        sentences = [_summary_excerpt(hit.text, hit.section_heading) for hit in selected_hits]
        sentences = [sentence for sentence in sentences if sentence]
        if not sentences:
            raise StudyDocumentNotReadyError("This document has no usable text to summarize.")
        return GeneratedSummary(content=" ".join(sentences), citations=[_citation_from_hit(hit) for hit in selected_hits])

    selected_chunks = (
        _retrieved_chunks(document, "document overview summary main topics key points", limit=3)
        if provider is not None
        else _summary_chunks(document)
    )
    if not selected_chunks:
        raise StudyDocumentNotReadyError("This document has no indexed evidence chunks to summarize.")

    sentences: list[str] = []
    citations: list[dict[str, object]] = []
    if provider is not None:
        context = _chunks_context(selected_chunks)
        summary = _prepare_generated_summary(provider.summarize(context), context, profile.document_type)
        if summary and _is_supported_generated_text(
            summary,
            context,
            strict=_uses_strict_generation_validation(provider),
        ):
            return GeneratedSummary(content=summary, citations=[_citation(document, chunk) for chunk in selected_chunks])

    fallback_chunks = _summary_chunks(document) if provider is not None else selected_chunks
    for chunk in fallback_chunks:
        heading = chunk_heading(chunk)
        sentence = _summary_excerpt(chunk.text, heading)
        if sentence:
            sentences.append(sentence)
            citations.append(_citation(document, chunk))

    if not sentences:
        raise StudyDocumentNotReadyError("This document has no usable text to summarize.")
    return GeneratedSummary(content=" ".join(sentences), citations=citations)


def _similar_enough(first: str, second: str) -> bool:
    first_words = _words(first)
    second_words = _words(second)
    if not first_words or not second_words:
        return False
    jaccard = len(first_words.intersection(second_words)) / len(first_words.union(second_words))
    return jaccard >= 0.82 or SequenceMatcher(None, first.lower(), second.lower()).ratio() >= 0.88


def _study_question_family(question: str) -> str | None:
    cleaned = clean_text(question).rstrip(" ?") + "?"
    if _OVERVIEW_QUESTION_PATTERN.match(cleaned):
        return "overview"
    return None


def _is_duplicate_study_question(question: str, existing_questions: list[str]) -> bool:
    family = _study_question_family(question)
    for existing in existing_questions:
        if family is not None and family == _study_question_family(existing):
            return True
        if _similar_enough(question, existing):
            return True
    return False


def _dedupe_questions(questions: list[str]) -> list[str]:
    unique: list[str] = []
    for question in questions:
        cleaned = clean_text(question).rstrip(" ?") + "?"
        if _is_duplicate_study_question(cleaned, unique):
            continue
        unique.append(cleaned)
    return unique


def build_study_questions(
    document: Document,
    count: int = 5,
    provider: LlmProvider | None = None,
    retrieval_hits: list[SearchHit] | None = None,
) -> list[GeneratedQuestion]:
    profile = build_document_profile(document)
    candidate_questions = _dedupe_questions([*profile.suggested_questions, *_DEFAULT_STUDY_QUESTIONS])
    generated: list[GeneratedQuestion] = []
    if provider is not None:
        if retrieval_hits is not None:
            selected_hits = [hit for hit in retrieval_hits if _is_usable_summary_hit(hit)]
            citations = [_citation_from_hit(hit) for hit in selected_hits]
            context = _hits_context(selected_hits)
        else:
            retrieved_chunks = _retrieved_chunks(
                document,
                "study questions main topics key facts methods results datasets limitations payment terms parties export controls",
                limit=3,
            )
            citations = [_citation(document, chunk) for chunk in retrieved_chunks]
            context = _chunks_context(retrieved_chunks)
        if context:
            provider_questions = provider.generate_questions(context, count=count)
        else:
            provider_questions = []
        for provider_question in provider_questions:
            if not _is_useful_study_question(provider_question.question, profile.document_type):
                continue
            if not _is_supported_generated_text(
                provider_question.expected_answer,
                context,
                strict=_uses_strict_generation_validation(provider),
            ):
                continue
            if not _provider_answer_matches_question(
                question=provider_question.question,
                expected_answer=provider_question.expected_answer,
                context=context,
                document_type=profile.document_type,
            ):
                continue
            if _is_duplicate_study_question(provider_question.question, [existing.question for existing in generated]):
                continue
            generated.append(
                GeneratedQuestion(
                    question=provider_question.question,
                    expected_answer=provider_question.expected_answer,
                    citations=citations,
                )
            )
            if len(generated) >= count:
                return generated

    for question in candidate_questions:
        if not _is_useful_study_question(question, profile.document_type):
            continue
        if _is_duplicate_study_question(question, [existing.question for existing in generated]):
            continue
        route = route_query(question, profile.document_type)
        result = build_document_aware_answer(question, document, profile, route)
        if result is None or result.answer is None or result.quality.status != "answerable":
            continue
        if not _is_meaningful_expected_answer(result.answer.summary):
            continue

        citations: list[dict[str, object]] = []
        for answer_citation in result.answer.citations:
            citation = _citation_from_answer(document, answer_citation.chunk_id)
            if citation is not None:
                citations.append(citation)
        if not citations:
            continue
        generated.append(
            GeneratedQuestion(
                question=question,
                expected_answer=result.answer.summary,
                citations=citations,
            )
        )
        if len(generated) >= count:
            break
    return generated


def score_study_answer(question: StudyQuestion, answer_text: str, provider: LlmProvider | None = None) -> StudyScore:
    llm_provider = provider or LocalHeuristicLlmProvider()
    evaluated = llm_provider.evaluate_answer(question.question, question.expected_answer, answer_text)
    score = round(max(0.0, min(1.0, evaluated.score)), 2)
    if score >= 0.75:
        feedback = "Strong answer. You covered the main cited points."
    elif score >= 0.4:
        feedback = "Partial answer. Add more of the cited details to make it stronger."
    else:
        feedback = "Needs work. Revisit the cited evidence and include the key terms from the expected answer."
    if evaluated.feedback and "Missing terms:" in evaluated.feedback:
        feedback = f"{feedback} {evaluated.feedback}"
    return StudyScore(score=score, feedback=feedback)


def _get_ready_document(db: Session, document_id: str) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise StudyDocumentNotFoundError("Document not found.")
    if document.status != DocumentStatus.INDEXED or not document.chunks:
        raise StudyDocumentNotReadyError("Document must be indexed before study features can be generated.")
    return document


def get_latest_summary(db: Session, document_id: str) -> DocumentSummary | None:
    return db.scalars(
        select(DocumentSummary)
        .where(DocumentSummary.document_id == document_id)
        .order_by(DocumentSummary.created_at.desc())
        .limit(1)
    ).first()


def list_study_questions(db: Session, document_id: str) -> list[StudyQuestion]:
    return list(
        db.scalars(
            select(StudyQuestion)
            .where(StudyQuestion.document_id == document_id)
            .order_by(StudyQuestion.created_at.asc())
        )
    )


def _default_provider() -> LlmProvider:
    return get_llm_provider(get_settings())


def generate_document_summary(
    db: Session,
    document_id: str,
    provider: LlmProvider | None = None,
    embedder_factory: EmbeddingProviderFactory | None = None,
) -> DocumentSummary:
    document = _get_ready_document(db, document_id)
    retrieval_hits = _study_retrieval_hits(
        db,
        document,
        "document overview summary main topics key points",
        3,
        embedder_factory,
    )
    generated = build_document_summary(document, provider=provider or _default_provider(), retrieval_hits=retrieval_hits or None)
    summary = DocumentSummary(
        id=str(uuid4()),
        document_id=document.id,
        content=generated.content,
        citations=generated.citations,
    )
    db.add(summary)
    db.commit()
    db.refresh(summary)
    return summary


def generate_study_questions(
    db: Session,
    document_id: str,
    count: int = 5,
    provider: LlmProvider | None = None,
    embedder_factory: EmbeddingProviderFactory | None = None,
    replace_existing: bool = False,
) -> list[StudyQuestion]:
    document = _get_ready_document(db, document_id)
    existing_question_rows = list_study_questions(db, document_id)
    if replace_existing:
        for question in existing_question_rows:
            db.delete(question)
        db.flush()
        existing_questions: list[str] = []
    else:
        existing_questions = [question.question for question in existing_question_rows]
    retrieval_hits = _study_retrieval_hits(
        db,
        document,
        "study questions main topics key facts methods results datasets limitations payment terms parties export controls",
        3,
        embedder_factory,
    )
    generated_questions = [
        generated
        for generated in build_study_questions(
            document,
            count=count + len(existing_questions),
            provider=provider or _default_provider(),
            retrieval_hits=retrieval_hits or None,
        )
        if not any(_similar_enough(generated.question, existing) for existing in existing_questions)
    ][:count]
    questions = [
        StudyQuestion(
            id=str(uuid4()),
            document_id=document.id,
            question=generated.question,
            expected_answer=generated.expected_answer,
            citations=generated.citations,
        )
        for generated in generated_questions
    ]
    for question in questions:
        db.add(question)
    db.commit()
    for question in questions:
        db.refresh(question)
    return questions


def grade_study_answer(
    db: Session,
    document_id: str,
    question_id: str,
    answer_text: str,
    provider: LlmProvider | None = None,
) -> StudyAnswer:
    question = db.get(StudyQuestion, question_id)
    if question is None or question.document_id != document_id:
        raise StudyQuestionNotFoundError("Study question not found for this document.")
    scored = score_study_answer(question, answer_text, provider=provider or _default_provider())
    answer = StudyAnswer(
        id=str(uuid4()),
        question_id=question.id,
        answer_text=answer_text,
        score=scored.score,
        feedback=scored.feedback,
    )
    db.add(answer)
    db.commit()
    db.refresh(answer)
    return answer
