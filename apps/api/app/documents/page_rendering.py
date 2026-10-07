from __future__ import annotations

import io
from hashlib import sha256
from dataclasses import dataclass
from pathlib import Path

import fitz
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, Page, PageImage

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
    from app.documents.service import resolve_document_file_path

    file_path = resolve_document_file_path(document, storage_dir)
    if not file_path.exists():
        raise DocumentPageRenderError("Stored document file was not found.")

    if document.mime_type == "application/pdf":
        return _render_pdf_page(file_path, page_number)
    if document.mime_type.startswith("image/"):
        return _render_image_page(file_path, page_number)
    raise DocumentPageRenderError("Page previews are only supported for PDFs and images.")


def refresh_page_image_metadata(
    db: Session,
    document: Document,
    page_number: int,
    storage_dir: Path | None,
    *,
    rendered: RenderedPageImage | None = None,
) -> PageImage | None:
    page = db.scalar(
        select(Page).where(
            Page.document_id == document.id,
            Page.page_number == page_number,
        )
    )
    if page is None:
        return None

    try:
        if rendered is None:
            rendered = render_document_page_image(document, page_number=page_number, storage_dir=storage_dir)
    except DocumentPageRenderError:
        return None

    image = db.scalar(
        select(PageImage).where(
            PageImage.document_id == document.id,
            PageImage.page_id == page.id,
            PageImage.page_number == page_number,
        )
    )
    if image is None:
        image = PageImage(
            document_id=document.id,
            page_id=page.id,
            page_number=page_number,
            render_dpi=PAGE_PREVIEW_DPI,
            width=page.width,
            height=page.height,
            media_type=rendered.media_type,
        )
        db.add(image)

    image.render_dpi = PAGE_PREVIEW_DPI
    with Image.open(io.BytesIO(rendered.content)) as rendered_image:
        image.width, image.height = rendered_image.size
    image.media_type = rendered.media_type
    image.checksum = sha256(rendered.content).hexdigest()
    db.flush()
    return image
