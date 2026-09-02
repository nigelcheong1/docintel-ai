from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image

from app.documents.ocr import OcrProvider
from app.documents.parse_quality import normalized_text_length
from app.documents.parser import DocumentParseError, parse_pdf

LOW_TEXT_PAGE_MAX_CHARS = 80


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    width: float | None
    height: float | None
    text_source: str
    ocr_engine: str | None = None
    ocr_confidence: float | None = None
    ocr_duration_ms: int | None = None


@dataclass(frozen=True)
class ExtractionResult:
    pages: list[ExtractedPage]
    ocr_page_count: int
    ocr_duration_ms: int


def _is_sparse_text(text: str) -> bool:
    return normalized_text_length(text) < LOW_TEXT_PAGE_MAX_CHARS


def _page_image(page: fitz.Page, *, dpi: int) -> Image.Image:
    pixmap = page.get_pixmap(dpi=dpi, alpha=False)
    return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


def extract_pdf_pages(
    file_path: Path,
    *,
    ocr_provider: OcrProvider | None,
    language: str,
    dpi: int,
    max_ocr_pages: int,
) -> ExtractionResult:
    native_pages = parse_pdf(file_path)
    extracted_pages = [
        ExtractedPage(
            page_number=page.page_number,
            text=page.text,
            width=page.width,
            height=page.height,
            text_source="native",
        )
        for page in native_pages
    ]

    if ocr_provider is None or not ocr_provider.is_available() or max_ocr_pages <= 0:
        return ExtractionResult(pages=extracted_pages, ocr_page_count=0, ocr_duration_ms=0)

    sparse_indexes = [
        index for index, page in enumerate(extracted_pages) if _is_sparse_text(page.text)
    ][:max_ocr_pages]
    if not sparse_indexes:
        return ExtractionResult(pages=extracted_pages, ocr_page_count=0, ocr_duration_ms=0)

    ocr_page_count = 0
    ocr_duration_ms = 0
    pages_by_number = {page.page_number: page for page in extracted_pages}
    try:
        with fitz.open(file_path) as document:
            for index in sparse_indexes:
                native_page = native_pages[index]
                ocr_result = ocr_provider.ocr_image(_page_image(document[index], dpi=dpi), language=language)
                ocr_duration_ms += ocr_result.duration_ms
                ocr_text = " ".join(ocr_result.text.split())
                if not ocr_text:
                    continue
                ocr_page_count += 1
                text_source = "hybrid" if native_page.text else "ocr"
                merged_text = f"{native_page.text}\n{ocr_text}".strip() if native_page.text else ocr_text
                pages_by_number[native_page.page_number] = ExtractedPage(
                    page_number=native_page.page_number,
                    text=merged_text,
                    width=native_page.width,
                    height=native_page.height,
                    text_source=text_source,
                    ocr_engine=ocr_result.engine_name,
                    ocr_confidence=ocr_result.confidence,
                    ocr_duration_ms=ocr_result.duration_ms,
                )
    except Exception as exc:
        raise DocumentParseError(f"Could not render PDF page for OCR: {exc}") from exc

    return ExtractionResult(
        pages=[pages_by_number[page.page_number] for page in native_pages],
        ocr_page_count=ocr_page_count,
        ocr_duration_ms=ocr_duration_ms,
    )


def extract_image_pages(file_path: Path, *, ocr_provider: OcrProvider | None, language: str) -> ExtractionResult:
    if ocr_provider is None or not ocr_provider.is_available():
        return ExtractionResult(pages=[], ocr_page_count=0, ocr_duration_ms=0)

    try:
        with Image.open(file_path) as image:
            width, height = image.size
            ocr_result = ocr_provider.ocr_image(image.convert("RGB"), language=language)
    except Exception as exc:
        raise DocumentParseError(f"Could not read image for OCR: {exc}") from exc

    text = " ".join(ocr_result.text.split())
    if not text:
        return ExtractionResult(pages=[], ocr_page_count=0, ocr_duration_ms=ocr_result.duration_ms)

    return ExtractionResult(
        pages=[
            ExtractedPage(
                page_number=1,
                text=text,
                width=float(width),
                height=float(height),
                text_source="ocr",
                ocr_engine=ocr_result.engine_name,
                ocr_confidence=ocr_result.confidence,
                ocr_duration_ms=ocr_result.duration_ms,
            )
        ],
        ocr_page_count=1,
        ocr_duration_ms=ocr_result.duration_ms,
    )
