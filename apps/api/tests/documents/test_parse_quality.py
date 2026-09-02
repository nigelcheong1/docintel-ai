from app.documents.parse_quality import build_parse_quality_from_pages
from app.documents.parser import ParsedPage


class OcrPage:
    def __init__(self, text: str, text_source: str, confidence: float | None, duration_ms: int | None) -> None:
        self.text = text
        self.text_source = text_source
        self.ocr_confidence = confidence
        self.ocr_duration_ms = duration_ms


def test_parse_quality_marks_text_pdf_as_low_scan_likelihood():
    profile = build_parse_quality_from_pages(
        [
            ParsedPage(
                page_number=1,
                text="Invoice total due is RM 1,200.00 " * 20,
                width=300,
                height=200,
            ),
            ParsedPage(
                page_number=2,
                text="Payment terms are net 30 days " * 20,
                width=300,
                height=200,
            ),
        ]
    )

    assert profile.page_count == 2
    assert profile.text_page_count == 2
    assert profile.empty_page_count == 0
    assert profile.scanned_likelihood == "low"
    assert profile.warnings == []


def test_parse_quality_warns_for_sparse_text_pdf():
    profile = build_parse_quality_from_pages(
        [
            ParsedPage(page_number=1, text=".", width=300, height=200),
            ParsedPage(page_number=2, text="", width=300, height=200),
        ]
    )

    assert profile.low_text_page_ratio == 1
    assert profile.scanned_likelihood == "high"
    assert "This PDF has very little extractable text and may need OCR." in profile.warnings


def test_parse_quality_reports_ocr_metadata():
    profile = build_parse_quality_from_pages(
        [
            OcrPage("Native searchable text " * 8, "native", None, None),
            OcrPage("OCR searchable text " * 8, "ocr", 91.0, 15),
            OcrPage("Hybrid searchable text " * 8, "hybrid", 81.0, 25),
        ]
    )

    assert profile.native_text_page_count == 1
    assert profile.ocr_page_count == 1
    assert profile.hybrid_page_count == 1
    assert profile.ocr_confidence_average == 86.0
    assert profile.ocr_duration_ms == 40
    assert profile.text_source_summary == {"native": 1, "ocr": 1, "hybrid": 1}
