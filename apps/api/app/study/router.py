from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.models import Document, DocumentSummary, StudyAnswer, StudyQuestion
from app.db.session import get_db
from app.study.schemas import (
    DocumentStudySummaryRead,
    GenerateStudyQuestionsRequest,
    StudyAnswerRead,
    StudyQuestionRead,
    SubmitStudyAnswerRequest,
)
from app.study.service import (
    StudyDocumentNotFoundError,
    StudyDocumentNotReadyError,
    StudyQuestionNotFoundError,
    generate_document_summary,
    generate_study_questions,
    get_latest_summary,
    grade_study_answer,
    list_study_questions,
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


def _summary_read(summary: DocumentSummary) -> DocumentStudySummaryRead:
    return DocumentStudySummaryRead.model_validate(summary)


def _answer_read(answer: StudyAnswer) -> StudyAnswerRead:
    return StudyAnswerRead.model_validate(answer)


def _question_read(question: StudyQuestion) -> StudyQuestionRead:
    latest_answer = sorted(question.answers, key=lambda answer: answer.created_at, reverse=True)[0] if question.answers else None
    return StudyQuestionRead(
        id=question.id,
        document_id=question.document_id,
        question=question.question,
        expected_answer=question.expected_answer,
        citations=question.citations,
        created_at=question.created_at,
        latest_answer=_answer_read(latest_answer) if latest_answer is not None else None,
    )


def _ensure_document_exists(db: Session, document_id: str) -> None:
    if db.get(Document, document_id) is None:
        raise HTTPException(status_code=404, detail="Document not found.")


@router.get("/summary", response_model=DocumentStudySummaryRead | None)
def study_summary(document_id: str, db: Annotated[Session, Depends(get_db)]) -> DocumentStudySummaryRead | None:
    _ensure_document_exists(db, document_id)
    summary = get_latest_summary(db, document_id)
    return _summary_read(summary) if summary is not None else None


@router.post("/summary", response_model=DocumentStudySummaryRead)
def generate_study_summary(document_id: str, db: Annotated[Session, Depends(get_db)]) -> DocumentStudySummaryRead:
    try:
        return _summary_read(generate_document_summary(db, document_id))
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
) -> list[StudyQuestionRead]:
    try:
        return [_question_read(question) for question in generate_study_questions(db, document_id, count=request.count)]
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
