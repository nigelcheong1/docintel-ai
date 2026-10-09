from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]
ExpectedOutcome = Literal["answerable", "insufficient_evidence"]
RunStatus = Literal["queued", "running", "completed", "cancelled", "interrupted", "failed"]


class ExpectedFact(BaseModel):
    pattern: ShortText
    alternatives: list[ShortText] = Field(default_factory=list, max_length=10)


class EvidenceAnchor(BaseModel):
    page_number: int = Field(ge=1)
    quote: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


class Measurement(BaseModel):
    value: float | None
    numerator: float = Field(ge=0)
    denominator: int = Field(ge=0)
    unit: Literal["ratio", "ms"]
    scope: str


class CaseWrite(BaseModel):
    document_id: UUID
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    expected_outcome: ExpectedOutcome
    facts: list[ExpectedFact] = Field(default_factory=list, max_length=20)
    anchors: list[EvidenceAnchor] = Field(default_factory=list, max_length=20)
    tags: list[Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]] = Field(default_factory=list, max_length=10)
    review_rationale: str = Field(default="", max_length=4000)


class CaseRead(CaseWrite):
    model_config = ConfigDict(from_attributes=True)
    document_id: UUID | None
    id: str
    suite_id: str
    document_filename: str
    review_state: Literal["draft", "reviewed"]
    content_version: int
    reviewed_at: datetime | None
    review_page_hashes: dict[str, str]
    availability: Literal["ready", "draft", "stale", "unavailable"] = "draft"
    availability_reasons: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SuiteWrite(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class SuiteRead(SuiteWrite):
    model_config = ConfigDict(from_attributes=True)
    id: str
    created_at: datetime
    updated_at: datetime
    case_count: int = 0
    reviewed_count: int = 0


class SuiteDetail(SuiteRead):
    cases: list[CaseRead] = Field(default_factory=list)


class RunCreate(BaseModel):
    suite_id: UUID


class ReviewCaseRequest(BaseModel):
    content_version: int = Field(ge=1)


class ResultAssessmentWrite(BaseModel):
    assessment: Literal["correct", "incorrect", "needs_review"]
    note: str = Field(default="", max_length=4000)


class RunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    suite_id: str | None
    suite_snapshot: dict[str, Any]
    case_snapshots: list[dict[str, Any]]
    pipeline_config: dict[str, Any]
    measurements: dict[str, Measurement]
    status: RunStatus
    cancel_requested: bool
    total_cases: int
    completed_cases: int
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    mode_counts: dict[str, int] = Field(default_factory=dict)
    fallback_count: int = 0
    error_count: int = 0
    unavailable_count: int = 0
    passed_count: int = 0
    failed_count: int = 0


class ResultRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    run_id: str
    case_id_snapshot: str
    case_version: int
    case_snapshot: dict[str, Any]
    execution_snapshot: dict[str, Any]
    measurements: dict[str, Measurement]
    failure_reasons: list[str]
    status: Literal["pass", "fail", "unavailable", "error"]
    duration_ms: float
    human_assessment: Literal["correct", "incorrect", "needs_review"] | None
    assessment_note: str
    assessed_at: datetime | None
    created_at: datetime
