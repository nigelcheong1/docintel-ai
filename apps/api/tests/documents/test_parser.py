from pathlib import Path

import fitz
import pytest

from app.documents.parser import DocumentParseError, parse_pdf


def create_sample_pdf(path: Path, text: str) -> None:
    document = fitz.open()
    page = document.new_page(width=300, height=200)
    page.insert_text((36, 72), text)
    document.save(path)
    document.close()


def test_parse_pdf_extracts_page_text(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    create_sample_pdf(pdf_path, "Invoice Number INV-1001")

    pages = parse_pdf(pdf_path)

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "INV-1001" in pages[0].text
    assert pages[0].width == 300
    assert pages[0].height == 200


def test_parse_pdf_rejects_empty_pdf(tmp_path):
    pdf_path = tmp_path / "empty.pdf"
    document = fitz.open()
    document.new_page()
    document.save(pdf_path)
    document.close()

    with pytest.raises(DocumentParseError, match="No extractable text"):
        parse_pdf(pdf_path)
