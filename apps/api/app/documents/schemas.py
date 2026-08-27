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


class ChunkRead(BaseModel):
    id: str
    document_id: str
    page_number: int
    chunk_index: int
    text: str
    token_estimate: int
