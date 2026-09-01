from app.documents.chunker import chunk_pages, is_usable_chunk_text
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


def test_is_usable_chunk_text_rejects_sparse_junk():
    assert not is_usable_chunk_text("1 2 3 . -")
    assert is_usable_chunk_text("Valid invoice payment terms include useful words.")


def test_chunk_pages_skips_junk_text_windows():
    text = " ".join(["99"] * 40) + " Valid invoice payment terms include enough useful alphabetic words."
    chunks = chunk_pages([ParsedPage(page_number=1, text=text, width=300, height=200)], chunk_size=20, overlap=0)

    assert all(is_usable_chunk_text(chunk.text) for chunk in chunks)
    assert any("Valid invoice payment terms" in chunk.text for chunk in chunks)
    assert not any(chunk.text.startswith("99 99") for chunk in chunks)


def test_chunk_layout_includes_quality_metadata():
    chunk = chunk_pages(
        [
            ParsedPage(
                page_number=1,
                text="METHOD\nThis section describes the model architecture and encoder.",
                width=300,
                height=200,
            )
        ]
    )[0]

    assert chunk.layout["quality"] == "usable"
    assert chunk.layout["text_density"] > 0
    assert chunk.layout["heading_confidence"] in {"explicit", "inferred", "none"}


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


def test_chunk_pages_normalizes_spaced_academic_headings():
    paper_text = "\n".join(
        [
            "H2R Bridge",
            "A B S T R A C T",
            "Human-robot collaboration improves shared industrial tasks.",
            "M E T H O D",
            "The method fuses language and video features.",
        ]
    )
    pages = [ParsedPage(page_number=1, text=paper_text, width=600, height=800)]

    chunks = chunk_pages(pages)

    headings = [chunk.layout.get("section_heading") for chunk in chunks]
    assert "ABSTRACT" in headings
    assert "METHOD" in headings


def test_chunk_pages_maps_numbered_research_headings_to_canonical_intents():
    pages = [
        ParsedPage(
            page_number=1,
            text="\n".join(
                [
                    "3. Multimodal learning framework",
                    "The proposed framework extracts temporal tokens and uses a visual encoder.",
                    "4. Experiments and results",
                    "The proposed method achieves TOP1 91.10 on HRI30.",
                    "4.3.1. Industrial-like HRI datasets",
                    "The experiments use MECCANO, InHARD, and HRI30.",
                ]
            ),
            width=600,
            height=800,
        )
    ]

    chunks = chunk_pages(pages, chunk_size=40, overlap=0)

    headings = [chunk.layout.get("section_heading") for chunk in chunks]
    assert headings == ["METHOD", "RESULTS", "DATASET"]


def test_chunk_pages_does_not_promote_research_keywords_to_method_headings():
    pages = [
        ParsedPage(
            page_number=1,
            text="\n".join(
                [
                    "Keywords",
                    "Human-robot collaboration",
                    "Intent recognition",
                    "Vision-language models",
                    "Abstract",
                    "This paper proposes a multimodal framework.",
                ]
            ),
            width=600,
            height=800,
        )
    ]

    chunks = chunk_pages(pages, chunk_size=40, overlap=0)

    headings = [chunk.layout.get("section_heading") for chunk in chunks]
    assert headings == ["KEYWORDS", "ABSTRACT"]


def test_chunk_pages_splits_mixed_standalone_and_inline_headings():
    resume_text = "\n".join(
        [
            "Nigel Cheong",
            "Education",
            "Xiamen University Malaysia Technical Skills Python React FastAPI",
            "Key Projects",
            "Document intelligence search platform",
        ]
    )
    pages = [ParsedPage(page_number=1, text=resume_text, width=600, height=800)]

    chunks = chunk_pages(pages)

    headings = [chunk.layout.get("section_heading") for chunk in chunks]
    assert "EDUCATION" in headings
    assert "TECHNICAL SKILLS" in headings
    assert "KEY PROJECTS" in headings

    education_chunk = next(chunk for chunk in chunks if chunk.layout.get("section_heading") == "EDUCATION")
    skills_chunk = next(chunk for chunk in chunks if chunk.layout.get("section_heading") == "TECHNICAL SKILLS")
    assert "Technical Skills" not in education_chunk.text
    assert "Python React FastAPI" in skills_chunk.text


def test_chunk_pages_does_not_label_title_case_phrases_in_regular_prose():
    prose = (
        "This candidate has Work Experience at Acme and Technical Skills include Python, "
        "but this paragraph is written as normal prose rather than formatted resume headings."
    )
    pages = [ParsedPage(page_number=1, text=prose, width=600, height=800)]

    chunks = chunk_pages(pages)

    assert len(chunks) == 1
    assert chunks[0].layout.get("section_heading") is None
    assert chunks[0].text == prose
