from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, DocumentEvalCase, DocumentEvalSuite, DocumentStatus, Page, utc_now
from app.evaluation.document_schemas import CaseRead, CaseWrite


@dataclass(frozen=True)
class ResolvedAnchor:
    page_number: int
    quote: str
    chunk_ids: tuple[str, ...]


@dataclass(frozen=True)
class CaseReadiness:
    availability: str
    anchors: tuple[ResolvedAnchor, ...] = ()
    reasons: tuple[str, ...] = ()


def normalize_source(text: str) -> str:
    return " ".join(re.sub(r"(?<=\w)-\s*\n\s*(?=\w)", "", text).split())


def page_text_hash(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


def join_source_texts(texts: list[str]) -> str:
    joined = ""
    for text in texts:
        current = normalize_source(text)
        if not joined:
            joined = current
            continue
        # Chunk overlap is already source text; do not duplicate it in a quote.
        overlap = next((size for size in range(min(len(joined), len(current)), 0, -1)
                        if joined[-size:] == current[:size] and (size == len(current) or current[size].isspace())), 0)
        joined = (joined + current[overlap:]) if overlap else (joined + " " + current)
    return joined


def _get_case(db: Session, case_id: str, *, lock: bool = False) -> DocumentEvalCase:
    statement = select(DocumentEvalCase).where(DocumentEvalCase.id == case_id)
    if lock:
        statement = statement.with_for_update()
    case = db.scalar(statement.execution_options(populate_existing=True))
    if case is None:
        raise HTTPException(404, "Benchmark case not found.")
    return case


def _document(db: Session, document_id: str) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        raise HTTPException(404, "Document not found.")
    return document


def create_case(db: Session, suite_id: str, data: CaseWrite) -> DocumentEvalCase:
    suite = db.get(DocumentEvalSuite, suite_id)
    if suite is None:
        raise HTTPException(404, "Benchmark suite not found.")
    document = _document(db, str(data.document_id))
    case = DocumentEvalCase(suite_id=suite_id, document_filename=document.filename, **data.model_dump(mode="json"))
    db.add(case)
    suite.updated_at = utc_now()
    db.commit()
    db.refresh(case)
    return case


def update_case(db: Session, case_id: str, data: CaseWrite) -> DocumentEvalCase:
    case = _get_case(db, case_id, lock=True)
    document = _document(db, str(data.document_id))
    payload = data.model_dump(mode="json")
    if any(getattr(case, key) != value for key, value in payload.items()):
        for key, value in payload.items():
            setattr(case, key, value)
        case.document_filename = document.filename
        case.content_version += 1
        case.review_state = "draft"
        case.reviewed_at = None
        case.review_page_hashes = {}
        db.get(DocumentEvalSuite, case.suite_id).updated_at = utc_now()
    db.commit()
    db.refresh(case)
    return case


def _resolve_sources(db: Session, case: DocumentEvalCase) -> CaseReadiness:
    pages = list(db.scalars(select(Page).where(Page.document_id == case.document_id).order_by(Page.page_number)))
    page_map = {page.page_number: page for page in pages}
    if not pages:
        return CaseReadiness("stale", reasons=("Document pages are missing; review the source again.",))
    if case.review_state == "reviewed":
        relevant_pages = pages if case.expected_outcome == "insufficient_evidence" else [page_map[n] for n in {anchor["page_number"] for anchor in case.anchors} if n in page_map]
        hashes = {str(page.page_number): page_text_hash(page.text) for page in relevant_pages}
        if hashes != case.review_page_hashes:
            return CaseReadiness("stale", reasons=("Source pages changed after review; review the case again.",))
    resolved = []
    for anchor in case.anchors:
        page = page_map.get(anchor["page_number"])
        quote = normalize_source(anchor["quote"])
        if page is None or quote not in normalize_source(page.text):
            return CaseReadiness("stale", reasons=(f"Quote cannot be resolved on page {anchor['page_number']}.",))
        chunks = list(db.scalars(select(Chunk).where(Chunk.page_id == page.id).order_by(Chunk.chunk_index)))
        match = None
        for width in range(1, len(chunks) + 1):
            for start in range(len(chunks) - width + 1):
                group = chunks[start:start + width]
                if quote in join_source_texts([chunk.text for chunk in group]):
                    match = tuple(chunk.id for chunk in group)
                    break
            if match is not None:
                break
        if match is None:
            return CaseReadiness("stale", reasons=(f"Quote is not represented in indexed chunks on page {page.page_number}.",))
        resolved.append(ResolvedAnchor(page.page_number, anchor["quote"], match))
    return CaseReadiness("ready", tuple(resolved))


def check_case_readiness(db: Session, case: DocumentEvalCase) -> CaseReadiness:
    document = db.get(Document, case.document_id) if case.document_id else None
    if document is None:
        return CaseReadiness("unavailable", reasons=("The selected document is no longer available.",))
    if document.status != DocumentStatus.INDEXED or not Path(document.file_path).is_file():
        return CaseReadiness("unavailable", reasons=("Document must be indexed and its local file must exist.",))
    if case.review_state != "reviewed":
        return CaseReadiness("draft", reasons=("This case has not been reviewed.",))
    return _resolve_sources(db, case)


def review_case(db: Session, case_id: str, content_version: int) -> DocumentEvalCase:
    case = _get_case(db, case_id, lock=True)
    if case.content_version != content_version:
        raise HTTPException(409, "Case changed; reload and review the current version.")
    if case.expected_outcome == "answerable" and (not case.facts or not case.anchors):
        raise HTTPException(422, "Answerable cases require expected facts and source quotes.")
    if case.expected_outcome == "insufficient_evidence" and (case.facts or not case.review_rationale.strip()):
        raise HTTPException(422, "Negative cases require a scope-review rationale and no required facts.")
    document = _document(db, case.document_id) if case.document_id else None
    if document is None or document.status != DocumentStatus.INDEXED or not Path(document.file_path).is_file():
        raise HTTPException(409, "Indexed document and local file are required for source review.")
    # Explicit re-review resolves current sources rather than comparing old hashes.
    previous_state = case.review_state
    case.review_state = "draft"
    readiness = _resolve_sources(db, case)
    case.review_state = previous_state
    if readiness.availability != "ready":
        raise HTTPException(409, " ".join(readiness.reasons))
    pages = list(db.scalars(select(Page).where(Page.document_id == case.document_id)))
    numbers = {anchor["page_number"] for anchor in case.anchors}
    case.review_page_hashes = {str(page.page_number): page_text_hash(page.text) for page in pages
                              if case.expected_outcome == "insufficient_evidence" or page.page_number in numbers}
    case.review_state = "reviewed"
    case.reviewed_at = utc_now()
    db.commit()
    db.refresh(case)
    return case


def read_case(db: Session, case: DocumentEvalCase) -> CaseRead:
    readiness = check_case_readiness(db, case)
    return CaseRead.model_validate(case).model_copy(update={"availability": readiness.availability, "availability_reasons": list(readiness.reasons)})
