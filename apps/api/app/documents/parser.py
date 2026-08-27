from dataclasses import dataclass
from pathlib import Path

import fitz


class DocumentParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str
    width: float
    height: float


def parse_pdf(file_path: Path) -> list[ParsedPage]:
    pages: list[ParsedPage] = []
    with fitz.open(file_path) as document:
        for index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            rect = page.rect
            pages.append(
                ParsedPage(
                    page_number=index,
                    text=text,
                    width=float(rect.width),
                    height=float(rect.height),
                )
            )

    if not any(page.text for page in pages):
        raise DocumentParseError("No extractable text found in this PDF.")

    return pages
