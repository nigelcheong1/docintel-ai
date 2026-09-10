from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

SummaryGenerationMode = Literal["concise", "detailed"]
StudyGenerationMode = Literal["balanced", "exam", "revision"]
GenerationQualityStatus = Literal["grounded", "needs_review"]


class StudyCitationRead(BaseModel):
    chunk_id: str
    document_id: str
    document_filename: str
    page_number: int
    section_heading: str | None = None
    page_image_url: str | None = None
    document_page_url: str | None = None
    snippet: str | None = None
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    source_score: float | None = Field(default=None, ge=0.0, le=1.0)
    ranking_signals: dict[str, float] = Field(default_factory=dict)


class DocumentStudySummaryRead(BaseModel):
    id: str
    document_id: str
    content: str
    citations: list[StudyCitationRead]
    created_at: datetime
    is_preview: bool = False
    generation_mode: SummaryGenerationMode | None = None
    generation_provider: str | None = None
    citation_count: int = Field(default=0, ge=0)
    quality_status: GenerationQualityStatus = "needs_review"

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
    is_preview: bool = False
    generation_mode: StudyGenerationMode | None = None
    generation_provider: str | None = None
    citation_count: int = Field(default=0, ge=0)
    quality_status: GenerationQualityStatus = "needs_review"
    latest_answer: StudyAnswerRead | None = None
    answer_count: int = 0
    recent_answers: list[StudyAnswerRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class GenerateStudySummaryRequest(BaseModel):
    preview: bool = False
    mode: SummaryGenerationMode = "concise"
    content: str | None = Field(default=None, min_length=1)
    citations: list[StudyCitationRead] | None = None


class StudyQuestionDraft(BaseModel):
    question: str = Field(min_length=1)
    expected_answer: str = Field(min_length=1)
    citations: list[StudyCitationRead] = Field(default_factory=list)


class GenerateStudyQuestionsRequest(BaseModel):
    count: int = Field(default=5, ge=1, le=10)
    replace_existing: bool = False
    preview: bool = False
    mode: StudyGenerationMode = "balanced"
    questions: list[StudyQuestionDraft] | None = None


class SubmitStudyAnswerRequest(BaseModel):
    answer_text: str = Field(min_length=1)
