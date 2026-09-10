from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentSummary, StudyAnswer, StudyQuestion
from app.db.session import get_db
from app.documents.router import get_embedding_provider_factory
from app.documents.service import EmbeddingProviderFactory
from app.study.schemas import (
    DocumentStudySummaryRead,
    GenerateStudySummaryRequest,
    GenerateStudyQuestionsRequest,
    StudyAnswerRead,
    StudyCitationRead,
    StudyQuestionRead,
    SubmitStudyAnswerRequest,
)
from app.study.service import (
    GeneratedQuestion,
    GeneratedSummary,
    StudyDocumentNotFoundError,
    StudyDocumentNotReadyError,
    StudyQuestionNotFoundError,
    default_study_generation_provider_name,
    generate_document_summary,
    generate_study_questions,
    get_latest_summary,
    grade_study_answer,
    list_study_questions,
    preview_document_summary,
    preview_study_questions,
    save_generated_document_summary,
    save_generated_study_questions,
)

router = APIRouter(prefix="/documents/{document_id}/study", tags=["study"])


def _raise_study_error(exc: Exception) -> None:
    if isinstance(exc, StudyDocumentNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, StudyDocumentNotReadyError):
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if isinstance(exc, StudyQuestionNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    raise HTTPException(status_code=500, detail="Study generation failed.") from exc


def _citation_quality(citations: list[StudyCitationRead]) -> str:
    return "grounded" if citations else "needs_review"


def _provider_name() -> str:
    return default_study_generation_provider_name()


def _summary_read(
    summary: DocumentSummary,
    *,
    generation_mode: str | None = None,
    generation_provider: str | None = None,
    is_preview: bool = False,
) -> DocumentStudySummaryRead:
    citations = _citation_reads(summary.citations)
    return DocumentStudySummaryRead(
        id=summary.id,
        document_id=summary.document_id,
        content=summary.content,
        citations=citations,
        created_at=summary.created_at,
        is_preview=is_preview,
        generation_mode=generation_mode,
        generation_provider=generation_provider,
        citation_count=len(citations),
        quality_status=_citation_quality(citations),
    )


def _summary_preview_read(
    document_id: str,
    generated: GeneratedSummary,
    *,
    generation_mode: str,
    generation_provider: str,
) -> DocumentStudySummaryRead:
    citations = _citation_reads(generated.citations)
    return DocumentStudySummaryRead(
        id=f"preview-summary-{uuid4()}",
        document_id=document_id,
        content=generated.content,
        citations=citations,
        created_at=datetime.now(UTC),
        is_preview=True,
        generation_mode=generation_mode,
        generation_provider=generation_provider,
        citation_count=len(citations),
        quality_status=_citation_quality(citations),
    )


def _answer_read(answer: StudyAnswer) -> StudyAnswerRead:
    return StudyAnswerRead.model_validate(answer)


def _citation_read(citation: dict[str, object]) -> StudyCitationRead:
    payload = dict(citation)
    document_id = payload.get("document_id")
    page_number = payload.get("page_number")
    chunk_id = payload.get("chunk_id")
    if document_id and page_number and not payload.get("page_image_url"):
        payload["page_image_url"] = f"/documents/{document_id}/pages/{page_number}/image"
    if document_id and page_number and chunk_id and not payload.get("document_page_url"):
        payload["document_page_url"] = f"/documents/{document_id}?page={page_number}&chunk={chunk_id}"
    payload.setdefault("ranking_signals", {})
    return StudyCitationRead.model_validate(payload)


def _citation_reads(citations: list[dict[str, object]]) -> list[StudyCitationRead]:
    return [_citation_read(citation) for citation in citations]


def _question_read(
    question: StudyQuestion,
    *,
    generation_mode: str | None = None,
    generation_provider: str | None = None,
    is_preview: bool = False,
) -> StudyQuestionRead:
    recent_answers = sorted(question.answers, key=lambda answer: answer.created_at, reverse=True)
    latest_answer = recent_answers[0] if recent_answers else None
    citations = _citation_reads(question.citations)
    return StudyQuestionRead(
        id=question.id,
        document_id=question.document_id,
        question=question.question,
        expected_answer=question.expected_answer,
        citations=citations,
        created_at=question.created_at,
        is_preview=is_preview,
        generation_mode=generation_mode,
        generation_provider=generation_provider,
        citation_count=len(citations),
        quality_status=_citation_quality(citations),
        latest_answer=_answer_read(latest_answer) if latest_answer is not None else None,
        answer_count=len(question.answers),
        recent_answers=[_answer_read(answer) for answer in recent_answers[:3]],
    )


def _question_preview_read(
    document_id: str,
    generated: GeneratedQuestion,
    *,
    generation_mode: str,
    generation_provider: str,
    index: int,
) -> StudyQuestionRead:
    citations = _citation_reads(generated.citations)
    return StudyQuestionRead(
        id=f"preview-question-{index}-{uuid4()}",
        document_id=document_id,
        question=generated.question,
        expected_answer=generated.expected_answer,
        citations=citations,
        created_at=datetime.now(UTC),
        is_preview=True,
        generation_mode=generation_mode,
        generation_provider=generation_provider,
        citation_count=len(citations),
        quality_status=_citation_quality(citations),
        latest_answer=None,
        answer_count=0,
        recent_answers=[],
    )


def _citation_payloads(citations: list[StudyCitationRead] | None) -> list[dict[str, object]]:
    return [citation.model_dump(exclude_none=True) for citation in citations or []]


def _ensure_document_exists(db: Session, document_id: str) -> None:
    if db.get(Document, document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")


@router.get("/summary", response_model=DocumentStudySummaryRead | None)
def study_summary(document_id: str, db: Annotated[Session, Depends(get_db)]) -> DocumentStudySummaryRead | None:
    _ensure_document_exists(db, document_id)
    summary = get_latest_summary(db, document_id)
    return _summary_read(summary) if summary is not None else None


@router.post("/summary", response_model=DocumentStudySummaryRead)
def generate_study_summary(
    document_id: str,
    request: Annotated[GenerateStudySummaryRequest, Body(default_factory=GenerateStudySummaryRequest)],
    db: Annotated[Session, Depends(get_db)],
    embedder_factory: Annotated[EmbeddingProviderFactory, Depends(get_embedding_provider_factory)],
) -> DocumentStudySummaryRead:
    generation_provider = _provider_name()
    try:
        if request.content is not None:
            return _summary_read(
                save_generated_document_summary(
                    db,
                    document_id,
                    GeneratedSummary(
                        content=request.content,
                        citations=_citation_payloads(request.citations),
                    ),
                ),
                generation_mode=request.mode,
                generation_provider=generation_provider,
            )
        if request.preview:
            return _summary_preview_read(
                document_id,
                preview_document_summary(
                    db,
                    document_id,
                    embedder_factory=embedder_factory,
                    mode=request.mode,
                ),
                generation_mode=request.mode,
                generation_provider=generation_provider,
            )
        return _summary_read(
            generate_document_summary(
                db,
                document_id,
                embedder_factory=embedder_factory,
                mode=request.mode,
            ),
            generation_mode=request.mode,
            generation_provider=generation_provider,
        )
    except Exception as exc:  # noqa: BLE001 - API boundary converts typed study errors to HTTP responses.
        _raise_study_error(exc)
    raise HTTPException(status_code=500, detail="Study generation failed.")


@router.get("/questions", response_model=list[StudyQuestionRead])
def study_questions(document_id: str, db: Annotated[Session, Depends(get_db)]) -> list[StudyQuestionRead]:
    _ensure_document_exists(db, document_id)
    return [_question_read(question) for question in list_study_questions(db, document_id)]


@router.post("/questions", response_model=list[StudyQuestionRead])
def generate_questions(
    document_id: str,
    request: GenerateStudyQuestionsRequest,
    db: Annotated[Session, Depends(get_db)],
    embedder_factory: Annotated[EmbeddingProviderFactory, Depends(get_embedding_provider_factory)],
) -> list[StudyQuestionRead]:
    generation_provider = _provider_name()
    try:
        if request.questions is not None:
            generated_questions = [
                GeneratedQuestion(
                    question=question.question,
                    expected_answer=question.expected_answer,
                    citations=_citation_payloads(question.citations),
                )
                for question in request.questions
            ]
            return [
                _question_read(
                    question,
                    generation_mode=request.mode,
                    generation_provider=generation_provider,
                )
                for question in save_generated_study_questions(
                    db,
                    document_id,
                    generated_questions,
                    replace_existing=request.replace_existing,
                )
            ]
        if request.preview:
            return [
                _question_preview_read(
                    document_id,
                    question,
                    generation_mode=request.mode,
                    generation_provider=generation_provider,
                    index=index,
                )
                for index, question in enumerate(
                    preview_study_questions(
                        db,
                        document_id,
                        count=request.count,
                        embedder_factory=embedder_factory,
                        mode=request.mode,
                    ),
                    start=1,
                )
            ]
        return [
            _question_read(
                question,
                generation_mode=request.mode,
                generation_provider=generation_provider,
            )
            for question in generate_study_questions(
                db,
                document_id,
                count=request.count,
                embedder_factory=embedder_factory,
                replace_existing=request.replace_existing,
                mode=request.mode,
            )
        ]
    except Exception as exc:  # noqa: BLE001 - API boundary converts typed study errors to HTTP responses.
        _raise_study_error(exc)
    raise HTTPException(status_code=500, detail="Study generation failed.")


@router.post("/questions/{question_id}/answers", response_model=StudyAnswerRead)
def submit_study_answer(
    document_id: str,
    question_id: str,
    request: SubmitStudyAnswerRequest,
    db: Annotated[Session, Depends(get_db)],
) -> StudyAnswerRead:
    try:
        return _answer_read(grade_study_answer(db, document_id, question_id, request.answer_text))
    except Exception as exc:  # noqa: BLE001 - API boundary converts typed study errors to HTTP responses.
        _raise_study_error(exc)
    raise HTTPException(status_code=500, detail="Study answer grading failed.")
