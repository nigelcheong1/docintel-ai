from datetime import datetime
from typing import Literal

from pydantic import BaseModel

DocumentKind = Literal["pdf", "image"]


class DocumentRead(BaseModel):
    id: str
    filename: str
    mime_type: str
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentRead):
    page_count: int
    chunk_count: int


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
