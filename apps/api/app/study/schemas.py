from datetime import datetime

from pydantic import BaseModel, Field


class StudyCitationRead(BaseModel):
    chunk_id: str
    document_id: str
    document_filename: str
    page_number: int
    section_heading: str | None = None
    page_image_url: str
    document_page_url: str


class DocumentStudySummaryRead(BaseModel):
    id: str
    document_id: str
    content: str
    citations: list[StudyCitationRead]
    created_at: datetime

    model_config = {"from_attributes": True}


class StudyAnswerRead(BaseModel):
    id: str
    question_id: str
    answer_text: str
    score: float = Field(ge=0.0, le=1.0)
    feedback: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StudyQuestionRead(BaseModel):
    id: str
    document_id: str
    question: str
    expected_answer: str
    citations: list[StudyCitationRead]
    created_at: datetime
    latest_answer: StudyAnswerRead | None = None

    model_config = {"from_attributes": True}


class GenerateStudyQuestionsRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=10)


class SubmitStudyAnswerRequest(BaseModel):
    answer_text: str = Field(min_length=1)
