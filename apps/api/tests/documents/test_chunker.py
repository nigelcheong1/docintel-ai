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


def test_chunk_pages_splits_compact_resume_by_section_headings():
    resume_text = (
        "NIGEL CHEONG Student in AI Studies "
        "EDUCATION Xiamen University Malaysia Bachelor of Software Engineering "
        "CORE SKILLS Python SQL React Docker "
        "Technical Skills Pandas PyTorch FastAPI PostgreSQL "
        "KEY PROJECTS Skin Lesion Classification built a CNN dashboard "
        "EXPERIENCE AI Research Assistant evaluated document pipelines"
    )
    pages = [ParsedPage(page_number=1, text=resume_text, width=600, height=800)]

    chunks = chunk_pages(pages)

    headings = [chunk.layout.get("section_heading") for chunk in chunks]
    assert "EDUCATION" in headings
    assert "CORE SKILLS" in headings
    assert "TECHNICAL SKILLS" in headings
    assert "KEY PROJECTS" in headings

    project_chunk = next(
        chunk for chunk in chunks if chunk.layout.get("section_heading") == "KEY PROJECTS"
    )
    assert "Skin Lesion Classification" in project_chunk.text
    assert "EDUCATION" not in project_chunk.text


def test_chunk_pages_splits_title_case_headings_on_their_own_lines():
    resume_text = "\n".join(
        [
            "Nigel Cheong",
            "Education",
            "Xiamen University Malaysia Bachelor of Software Engineering",
            "Technical Skills",
            "Python React FastAPI PostgreSQL",
            "Projects",
            "Document intelligence search platform",
        ]
    )
    pages = [ParsedPage(page_number=1, text=resume_text, width=600, height=800)]

    chunks = chunk_pages(pages)

    headings = [chunk.layout.get("section_heading") for chunk in chunks]
    assert "EDUCATION" in headings
    assert "TECHNICAL SKILLS" in headings
    assert "PROJECTS" in headings
