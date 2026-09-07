from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, DocumentStatus, DocumentSummary, StudyAnswer, StudyQuestion
from app.documents.intelligence import build_document_profile, chunk_heading, clean_text, ordered_chunks, strip_leading_heading
from app.retrieval.document_answers import build_document_aware_answer
from app.retrieval.query_router import route_query

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
_DEFAULT_STUDY_QUESTIONS = [
    "What is this document about?",
    "What are the main topics covered in this document?",
    "What dates are mentioned?",
]


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
    }


def _citation_from_answer(document: Document, chunk_id: str) -> dict[str, object] | None:
    for chunk in ordered_chunks(document):
        if chunk.id == chunk_id:
            return _citation(document, chunk)
    return None


def _first_sentence(text: str, max_chars: int = 360) -> str:
    cleaned = clean_text(text)
    sentences = [sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(cleaned) if sentence.strip()]
    selected = sentences[0] if sentences else cleaned
    if len(selected) <= max_chars:
        return selected
    return selected[: max_chars - 3].rstrip() + "..."


def _summary_chunk_score(chunk: Chunk) -> tuple[int, int]:
    heading = chunk_heading(chunk)
    weight = _SUMMARY_HEADING_WEIGHTS.get(heading or "", 10)
    if heading == "REFERENCES":
        weight = -100
    return (weight, -chunk.chunk_index)


def _summary_chunks(document: Document, limit: int = 3) -> list[Chunk]:
    chunks = [chunk for chunk in ordered_chunks(document) if clean_text(chunk.text)]
    ranked = sorted(chunks, key=_summary_chunk_score, reverse=True)
    selected = ranked[:limit]
    return sorted(selected, key=lambda chunk: chunk.chunk_index)


def build_document_summary(document: Document) -> GeneratedSummary:
    selected_chunks = _summary_chunks(document)
    if not selected_chunks:
        raise StudyDocumentNotReadyError("This document has no indexed evidence chunks to summarize.")

    sentences: list[str] = []
    citations: list[dict[str, object]] = []
    for chunk in selected_chunks:
        heading = chunk_heading(chunk)
        sentence = _first_sentence(strip_leading_heading(chunk.text, heading))
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


def build_study_questions(document: Document, count: int = 5) -> list[GeneratedQuestion]:
    profile = build_document_profile(document)
    candidate_questions = _dedupe_questions([*profile.suggested_questions, *_DEFAULT_STUDY_QUESTIONS])
    generated: list[GeneratedQuestion] = []
    for question in candidate_questions:
        route = route_query(question, profile.document_type)
        result = build_document_aware_answer(question, document, profile, route)
        if result is None or result.answer is None or result.quality.status != "answerable":
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


def score_study_answer(question: StudyQuestion, answer_text: str) -> StudyScore:
    expected_words = _words(question.expected_answer)
    answer_words = _words(answer_text)
    if not expected_words or not answer_words:
        score = 0.0
    else:
        score = len(expected_words.intersection(answer_words)) / len(expected_words)
    score = round(max(0.0, min(1.0, score)), 2)
    if score >= 0.75:
        feedback = "Strong answer. You covered the main cited points."
    elif score >= 0.4:
        feedback = "Partial answer. Add more of the cited details to make it stronger."
    else:
        feedback = "Needs work. Revisit the cited evidence and include the key terms from the expected answer."
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


def generate_document_summary(db: Session, document_id: str) -> DocumentSummary:
    document = _get_ready_document(db, document_id)
    generated = build_document_summary(document)
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


def generate_study_questions(db: Session, document_id: str, count: int = 5) -> list[StudyQuestion]:
    document = _get_ready_document(db, document_id)
    existing_questions = [question.question for question in list_study_questions(db, document_id)]
    generated_questions = [
        generated
        for generated in build_study_questions(document, count=count + len(existing_questions))
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


def grade_study_answer(db: Session, document_id: str, question_id: str, answer_text: str) -> StudyAnswer:
    question = db.get(StudyQuestion, question_id)
    if question is None or question.document_id != document_id:
        raise StudyQuestionNotFoundError("Study question not found for this document.")
    scored = score_study_answer(question, answer_text)
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
