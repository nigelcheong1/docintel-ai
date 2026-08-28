from app.retrieval.answers import build_extractive_answer
from app.retrieval.search import SearchHit


def make_hit(*, chunk_id: str, text: str, page_number: int, section_heading: str | None) -> SearchHit:
    return SearchHit(
        chunk_id=chunk_id,
        document_id="document-1",
        document_filename="invoice.pdf",
        page_number=page_number,
        chunk_index=0,
        text=text,
        score=0.9,
        source_score=0.8,
        section_heading=section_heading,
    )


def test_build_extractive_answer_returns_none_when_there_are_no_hits():
    assert build_extractive_answer("invoice total", []) is None


def test_build_extractive_answer_uses_top_ranked_evidence_with_citations():
    top_hit = make_hit(
        chunk_id="chunk-top",
        text="The invoice total is 1250 Malaysian Ringgit.",
        page_number=2,
        section_heading="INVOICE SUMMARY",
    )
    lower_hit = make_hit(
        chunk_id="chunk-lower",
        text="Payment is due within 30 days.",
        page_number=3,
        section_heading="PAYMENT TERMS",
    )

    answer = build_extractive_answer("invoice total", [top_hit, lower_hit])

    assert answer is not None
    assert answer.summary.startswith("The invoice total is 1250 Malaysian Ringgit.")
    assert answer.citations[0].chunk_id == "chunk-top"
    assert answer.citations[0].document_filename == "invoice.pdf"
    assert answer.citations[0].page_number == 2
    assert answer.citations[0].section_heading == "INVOICE SUMMARY"


def test_build_extractive_answer_selects_the_sentence_matching_query_terms():
    hit = make_hit(
        chunk_id="chunk-focused",
        text=(
            "The supplier was founded in 2012. "
            "The invoice total is 1250 Malaysian Ringgit. "
            "Payment is due within 30 days."
        ),
        page_number=2,
        section_heading="INVOICE SUMMARY",
    )

    answer = build_extractive_answer("invoice total", [hit])

    assert answer is not None
    assert answer.summary == "The invoice total is 1250 Malaysian Ringgit."
