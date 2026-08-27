from app.documents.chunker import chunk_pages
from app.documents.parser import ParsedPage


def test_chunk_pages_keeps_page_numbers_and_indexes():
    text = " ".join(f"word{i}" for i in range(260))
    pages = [ParsedPage(page_number=2, text=text, width=600, height=800)]

    chunks = chunk_pages(pages, chunk_size=80, overlap=10)

    assert len(chunks) >= 3
    assert chunks[0].page_number == 2
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[0].token_estimate == len(chunks[0].text.split())
    assert chunks[0].layout["source"] == "pymupdf"


def test_chunk_pages_skips_blank_pages():
    pages = [ParsedPage(page_number=1, text="   ", width=100, height=100)]

    assert chunk_pages(pages) == []
