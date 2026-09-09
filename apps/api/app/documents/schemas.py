from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DocumentKind = Literal["pdf", "image"]


class ParseQualityRead(BaseModel):
    page_count: int
    text_page_count: int
    empty_page_count: int
    total_characters: int
    average_characters_per_page: float
    low_text_page_ratio: float
    scanned_likelihood: Literal["low", "medium", "high"]
    warnings: list[str]
    ocr_page_count: int = 0
    native_text_page_count: int = 0
    hybrid_page_count: int = 0
    ocr_confidence_average: float | None = None
    ocr_duration_ms: int = 0
    text_source_summary: dict[str, int] = Field(default_factory=dict)


class DocumentRead(BaseModel):
    id: str
    filename: str
    mime_type: str
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    parse_quality: ParseQualityRead | None = None
    page_count: int
    chunk_count: int

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentRead):
    pass


class DocumentPageRead(BaseModel):
    document_id: str
    page_number: int
    image_url: str
    text_source: str
    text_preview: str
    character_count: int
    chunk_count: int
    token_estimate: int
    text_density: float
    ocr_quality: Literal["native", "strong", "moderate", "weak", "missing"]
    processing_status: Literal["native_text", "ocr_strong", "ocr_moderate", "ocr_weak", "missing_text"]
    needs_review: bool
    ocr_engine: str | None = None
    ocr_confidence: float | None = None
    ocr_duration_ms: int | None = None


class DocumentProcessingStageRead(BaseModel):
    key: Literal["upload", "extract", "ocr", "chunk", "embed", "ready", "failed"]
    label: str
    status: Literal["pending", "active", "complete", "failed"]
    detail: str | None = None


class DocumentProcessingStatusRead(BaseModel):
    document_id: str
    filename: str
    status: str
    active_stage: Literal["upload", "extract", "ocr", "chunk", "embed", "ready", "failed"]
    progress_percent: int
    message: str
    page_count: int
    chunk_count: int
    embedded_chunk_count: int
    ocr_page_count: int
    stages: list[DocumentProcessingStageRead]


class DocumentSectionRead(BaseModel):
    heading: str
    page_number: int
    text_preview: str
    intents: list[str]


class DocumentFactRead(BaseModel):
    kind: str
    label: str
    value: str
    page_number: int
    source_text: str


class DocumentProfileRead(BaseModel):
    document_id: str
    filename: str
    document_type: str
    title: str | None
    overview: str | None
    sections: list[DocumentSectionRead]
    key_dates: list[DocumentFactRead]
    key_numbers: list[DocumentFactRead]
    key_entities: list[DocumentFactRead]
    suggested_questions: list[str]


class ChunkRead(BaseModel):
    id: str
    document_id: str
    page_number: int
    chunk_index: int
    text: str
    token_estimate: int


class UploadError(BaseModel):
    detail: str
