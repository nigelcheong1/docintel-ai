from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Literal, Protocol

from app.db.models import Document
from app.documents.schemas import ParseQualityRead

ScanLikelihood = Literal["low", "medium", "high"]

_TEXT_PAGE_MIN_CHARS = 20
_LOW_TEXT_PAGE_MAX_CHARS = 80


class PageText(Protocol):
    text: str


def normalized_text_length(text: str) -> int:
    return len(" ".join(text.split()))


def _text_length(page: PageText) -> int:
    return normalized_text_length(page.text)


def _scan_likelihood(page_count: int, low_text_page_ratio: float) -> ScanLikelihood:
    if page_count == 0 or low_text_page_ratio >= 0.75:
        return "high"
    if low_text_page_ratio >= 0.35:
        return "medium"
    return "low"


def _warnings(likelihood: ScanLikelihood) -> list[str]:
    if likelihood == "high":
        return ["This PDF has very little extractable text and may need OCR."]
    if likelihood == "medium":
        return ["Some pages have sparse extractable text."]
    return []


def build_parse_quality_from_pages(pages: Sequence[PageText]) -> ParseQualityRead:
    page_count = len(pages)
    text_lengths = [_text_length(page) for page in pages]
    text_sources = [getattr(page, "text_source", "native") or "native" for page in pages]
    text_source_summary = dict(Counter(text_sources))
    ocr_confidences = [
        float(confidence)
        for page in pages
        if (confidence := getattr(page, "ocr_confidence", None)) is not None
    ]
    total_characters = sum(text_lengths)
    text_page_count = sum(1 for length in text_lengths if length >= _TEXT_PAGE_MIN_CHARS)
    empty_page_count = sum(1 for length in text_lengths if length == 0)
    low_text_page_count = sum(1 for length in text_lengths if length < _LOW_TEXT_PAGE_MAX_CHARS)
    average_characters_per_page = total_characters / page_count if page_count else 0.0
    low_text_page_ratio = low_text_page_count / page_count if page_count else 1.0
    likelihood = _scan_likelihood(page_count, low_text_page_ratio)

    return ParseQualityRead(
        page_count=page_count,
        text_page_count=text_page_count,
        empty_page_count=empty_page_count,
        total_characters=total_characters,
        average_characters_per_page=round(average_characters_per_page, 2),
        low_text_page_ratio=round(low_text_page_ratio, 4),
        scanned_likelihood=likelihood,
        warnings=_warnings(likelihood),
        ocr_page_count=text_source_summary.get("ocr", 0),
        native_text_page_count=text_source_summary.get("native", 0),
        hybrid_page_count=text_source_summary.get("hybrid", 0),
        ocr_confidence_average=round(sum(ocr_confidences) / len(ocr_confidences), 2) if ocr_confidences else None,
        ocr_duration_ms=sum(int(getattr(page, "ocr_duration_ms", 0) or 0) for page in pages),
        text_source_summary=text_source_summary,
    )


def build_parse_quality_for_document(document: Document) -> ParseQualityRead | None:
    if not document.pages:
        return None
    pages = sorted(document.pages, key=lambda page: page.page_number)
    return build_parse_quality_from_pages(pages)
