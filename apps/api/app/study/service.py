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
_MEANINGFUL_SINGLE_STUDY_TOPICS = {
    "authors",
    "contributors",
    "dates",
    "design",
    "limitations",
    "method",
    "methodology",
    "methods",
    "overview",
    "results",
}
_ACADEMIC_FRAGMENT_TOPIC_WORDS = {"agent", "both", "contents", "controlling", "feature", "idx"}
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
    return not is_table_of_contents_like_text(cleaned)


def _is_useful_study_question(question: str, document_type: str | None = None) -> bool:
    cleaned = clean_text(question).rstrip(" ?")
    if not cleaned:
        return False
    if is_table_of_contents_like_text(cleaned):
        return False
    if document_type != "academic_report":
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
    return not set(alpha_terms).issubset(_ACADEMIC_FRAGMENT_TOPIC_WORDS)


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
                summary = clean_text(provider.summarize(_chunks_context(balanced_chunks)))
                if not summary:
                    raise StudyDocumentNotReadyError("This document has no usable text to summarize.")
                return GeneratedSummary(content=summary, citations=citations)
            sentences = [_summary_excerpt(chunk.text, chunk_heading(chunk)) for chunk in balanced_chunks]
            sentences = [sentence for sentence in sentences if sentence]
            if not sentences:
                raise StudyDocumentNotReadyError("This document has no usable text to summarize.")
            return GeneratedSummary(content=" ".join(sentences), citations=citations)
        if provider is not None:
            summary = clean_text(provider.summarize(_hits_context(selected_hits)))
            if not summary:
                raise StudyDocumentNotReadyError("This document has no usable text to summarize.")
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
        summary = clean_text(provider.summarize(_chunks_context(selected_chunks)))
        if not summary:
            raise StudyDocumentNotReadyError("This document has no usable text to summarize.")
        return GeneratedSummary(content=summary, citations=[_citation(document, chunk) for chunk in selected_chunks])

    for chunk in selected_chunks:
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


def _dedupe_questions(questions: list[str]) -> list[str]:
    unique: list[str] = []
    for question in questions:
        cleaned = clean_text(question).rstrip(" ?") + "?"
        if any(_similar_enough(cleaned, existing) for existing in unique):
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
            if not _is_meaningful_expected_answer(provider_question.expected_answer):
                continue
            if any(_similar_enough(provider_question.question, existing.question) for existing in generated):
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
        if any(_similar_enough(question, existing.question) for existing in generated):
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
