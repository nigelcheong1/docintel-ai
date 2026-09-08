from __future__ import annotations

from dataclasses import dataclass

from app.db.models import Document, DocumentStatus
from app.documents.schemas import DocumentProcessingStageRead, DocumentProcessingStatusRead


@dataclass(frozen=True)
class StageDefinition:
    key: str
    label: str


_BASE_STAGES = [
    StageDefinition("upload", "Upload saved"),
    StageDefinition("extract", "Text extracted"),
    StageDefinition("chunk", "Chunks created"),
    StageDefinition("embed", "Embeddings stored"),
    StageDefinition("ready", "Ready"),
]
_OCR_STAGE = StageDefinition("ocr", "OCR completed")
_FAILED_STAGE = StageDefinition("failed", "Needs attention")


def _embedded_chunk_count(document: Document) -> int:
    return sum(1 for chunk in document.chunks if chunk.embedding is not None)


def _ocr_page_count(document: Document) -> int:
    return sum(1 for page in document.pages if page.text_source != "native")


def _stage_sequence(document: Document) -> list[StageDefinition]:
    stages = list(_BASE_STAGES)
    if document.status in {DocumentStatus.OCR_PROCESSING, DocumentStatus.DEFERRED_OCR} or _ocr_page_count(document) > 0:
        stages.insert(2, _OCR_STAGE)
    if document.status == DocumentStatus.FAILED:
        stages.append(_FAILED_STAGE)
    return stages


def _active_stage(document: Document) -> str:
    if document.status == DocumentStatus.INDEXED:
        return "ready"
    if document.status == DocumentStatus.FAILED:
        return "failed"
    if document.status in {DocumentStatus.OCR_PROCESSING, DocumentStatus.DEFERRED_OCR}:
        return "ocr"
    if document.status == DocumentStatus.EMBEDDING:
        return "embed"
    if document.status == DocumentStatus.UPLOADED:
        return "upload"
    if not document.pages:
        return "extract"
    if not document.chunks:
        return "chunk"
    return "embed"


def _progress_percent(active_stage: str, document: Document, stage_keys: list[str]) -> int:
    if document.status == DocumentStatus.INDEXED:
        return 100
    if document.status == DocumentStatus.FAILED and not document.pages and not document.chunks:
        return 0
    if active_stage == "failed":
        completed = sum(1 for key in stage_keys if _stage_status(key, active_stage, document) == "complete")
        return int(round((completed / max(len(stage_keys), 1)) * 100))
    progress_by_stage = {
        "upload": 10,
        "extract": 25,
        "ocr": 40,
        "chunk": 60,
        "embed": 80,
        "ready": 100,
    }
    return progress_by_stage[active_stage]


def _stage_status(
    stage_key: str,
    active_stage: str,
    document: Document,
) -> str:
    if document.status == DocumentStatus.INDEXED:
        return "complete"
    if stage_key == "failed":
        return "failed"
    if document.status == DocumentStatus.DEFERRED_OCR and stage_key == "ocr":
        return "failed"
    if stage_key == active_stage:
        return "active"

    completed_keys: set[str] = set()
    if document.status != DocumentStatus.UPLOADED:
        completed_keys.add("upload")
    if document.pages:
        completed_keys.add("extract")
    if _ocr_page_count(document) > 0 and document.status != DocumentStatus.OCR_PROCESSING:
        completed_keys.add("ocr")
    if document.chunks:
        completed_keys.add("chunk")
    if document.chunks and _embedded_chunk_count(document) == len(document.chunks):
        completed_keys.add("embed")
    return "complete" if stage_key in completed_keys else "pending"


def _stage_detail(stage_key: str, document: Document) -> str | None:
    if stage_key == "extract" and document.pages:
        return f"{len(document.pages)} page{'s' if len(document.pages) != 1 else ''}"
    if stage_key == "ocr":
        ocr_pages = _ocr_page_count(document)
        if document.status == DocumentStatus.DEFERRED_OCR:
            return document.error_message
        return f"{ocr_pages} OCR page{'s' if ocr_pages != 1 else ''}"
    if stage_key == "chunk" and document.chunks:
        return f"{len(document.chunks)} chunk{'s' if len(document.chunks) != 1 else ''}"
    if stage_key == "embed" and document.chunks:
        return f"{_embedded_chunk_count(document)}/{len(document.chunks)} embedded"
    if stage_key == "failed":
        return document.error_message
    return None


def _message(document: Document, active_stage: str) -> str:
    if document.status in {DocumentStatus.FAILED, DocumentStatus.DEFERRED_OCR} and document.error_message:
        return document.error_message
    messages = {
        "upload": "Upload saved. Waiting to start document processing.",
        "extract": "Extracting readable text and page structure.",
        "ocr": "Running OCR for scanned or image-only pages.",
        "chunk": "Creating page-aware evidence chunks.",
        "embed": "Embedding evidence chunks for semantic search.",
        "ready": "Document is indexed and ready for search.",
        "failed": "Document processing needs attention.",
    }
    return messages[active_stage]


def build_processing_status(document: Document) -> DocumentProcessingStatusRead:
    active_stage = _active_stage(document)
    stage_definitions = _stage_sequence(document)
    stage_keys = [stage.key for stage in stage_definitions]
    stages = [
        DocumentProcessingStageRead(
            key=stage.key,
            label=stage.label,
            status=_stage_status(stage.key, active_stage, document),
            detail=_stage_detail(stage.key, document),
        )
        for stage in stage_definitions
    ]
    return DocumentProcessingStatusRead(
        document_id=document.id,
        filename=document.filename,
        status=document.status.value,
        active_stage=active_stage,
        progress_percent=_progress_percent(active_stage, document, stage_keys),
        message=_message(document, active_stage),
        page_count=len(document.pages),
        chunk_count=len(document.chunks),
        embedded_chunk_count=_embedded_chunk_count(document),
        ocr_page_count=_ocr_page_count(document),
        stages=stages,
    )
