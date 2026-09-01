from app.documents.parse_quality import build_parse_quality_from_pages
from app.documents.parser import ParsedPage


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
