from pathlib import Path

import fitz
from PIL import Image

from app.documents.extraction import extract_image_pages, extract_pdf_pages
from app.documents.ocr import OcrPageResult


class FakeOcrProvider:
    engine_name = "fake-ocr"

    def __init__(self, text: str = "OCR text from scanned page") -> None:
        self.text = text
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def ocr_image(self, image: Image.Image, *, language: str) -> OcrPageResult:
        self.calls += 1
        return OcrPageResult(text=self.text, confidence=91.5, engine_name=self.engine_name, duration_ms=7)


def create_pdf(path: Path, page_texts: list[str]) -> bytes:
    document = fitz.open()
    for text in page_texts:
        page = document.new_page(width=900, height=200)
        if text:
            page.insert_text((36, 72), text)
    document.save(path)
    document.close()
    return path.read_bytes()


def test_extract_pdf_pages_ocr_only_sparse_pages(tmp_path):
    pdf_path = tmp_path / "mixed.pdf"
    create_pdf(pdf_path, ["Native text with enough words to remain searchable " * 8, ""])
    provider = FakeOcrProvider()

    result = extract_pdf_pages(pdf_path, ocr_provider=provider, language="eng", dpi=120, max_ocr_pages=25)

    assert provider.calls == 1
    assert [page.text_source for page in result.pages] == ["native", "ocr"]
    assert "Native text" in result.pages[0].text
    assert result.pages[1].text == "OCR text from scanned page"
    assert result.ocr_page_count == 1


def test_extract_image_pages_uses_ocr_as_page_one(tmp_path):
    image_path = tmp_path / "scan.png"
    Image.new("RGB", (120, 60), "white").save(image_path)
    provider = FakeOcrProvider("Receipt total is RM 42.00")

    result = extract_image_pages(image_path, ocr_provider=provider, language="eng")

    assert provider.calls == 1
    assert len(result.pages) == 1
    assert result.pages[0].page_number == 1
    assert result.pages[0].text == "Receipt total is RM 42.00"
    assert result.pages[0].text_source == "ocr"
