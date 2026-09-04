from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image

from app.db.models import Document
from app.documents.service import resolve_document_file_path

PAGE_PREVIEW_DPI = 150


class DocumentPageRenderError(ValueError):
    pass


@dataclass(frozen=True)
class RenderedPageImage:
    content: bytes
    media_type: str


def _render_pdf_page(file_path: Path, page_number: int) -> RenderedPageImage:
    try:
        with fitz.open(file_path) as pdf:
            if page_number < 1 or page_number > pdf.page_count:
                raise DocumentPageRenderError(f"Page {page_number} is outside this PDF's page range.")
            pixmap = pdf[page_number - 1].get_pixmap(dpi=PAGE_PREVIEW_DPI, alpha=False)
            return RenderedPageImage(content=pixmap.tobytes("png"), media_type="image/png")
    except DocumentPageRenderError:
        raise
    except Exception as exc:
        raise DocumentPageRenderError(f"Could not render PDF page: {exc}") from exc


def _render_image_page(file_path: Path, page_number: int) -> RenderedPageImage:
    if page_number != 1:
        raise DocumentPageRenderError(f"Page {page_number} is outside this image document's page range.")

    try:
        with Image.open(file_path) as image:
            output = io.BytesIO()
            image.convert("RGB").save(output, format="PNG")
            return RenderedPageImage(content=output.getvalue(), media_type="image/png")
    except Exception as exc:
        raise DocumentPageRenderError(f"Could not render image page: {exc}") from exc


def render_document_page_image(
    document: Document,
    *,
    page_number: int,
    storage_dir: Path | None,
) -> RenderedPageImage:
    file_path = resolve_document_file_path(document, storage_dir)
    if not file_path.exists():
        raise DocumentPageRenderError("Stored document file was not found.")

    if document.mime_type == "application/pdf":
        return _render_pdf_page(file_path, page_number)
    if document.mime_type.startswith("image/"):
        return _render_image_page(file_path, page_number)
    raise DocumentPageRenderError("Page previews are only supported for PDFs and images.")
