from app.db.models import Chunk, Document, DocumentStatus, Page
from app.documents.intelligence import build_document_profile


def make_document(filename: str, page_text: str, chunks: list[tuple[str, str | None]]) -> Document:
    document = Document(
        id="doc-1",
        filename=filename,
        stored_filename=filename,
        mime_type="application/pdf",
        file_path=f"/tmp/{filename}",
        status=DocumentStatus.INDEXED,
    )
    page = Page(
        id="page-1",
        document_id=document.id,
        page_number=1,
        text=page_text,
        width=612,
        height=792,
    )
    document.pages = [page]
    document.chunks = [
        Chunk(
            id=f"chunk-{index}",
            document_id=document.id,
            page_id=page.id,
            page=page,
            chunk_index=index,
            text=text,
            token_estimate=len(text.split()),
            layout={"section_heading": heading} if heading else {},
        )
        for index, (text, heading) in enumerate(chunks)
    ]
    return document


def test_profile_detects_research_paper_sections_and_questions():
    document = make_document(
        "paper.pdf",
        "\n".join(
            [
                "Human-to-Robot Action Recognition with Language Guidance",
                "Abstract",
                "We propose a multimodal transformer for human robot interaction.",
                "Introduction",
                "Human action recognition has advanced with vision-language models.",
                "Results",
                "The method improves TOP1 accuracy on Kinetics-400 and UCF-101.",
                "References",
            ]
        ),
        [
            ("ABSTRACT We propose a multimodal transformer for human robot interaction.", "ABSTRACT"),
            ("RESULTS The method improves TOP1 accuracy on Kinetics-400 and UCF-101.", "RESULTS"),
        ],
    )

    profile = build_document_profile(document)

    assert profile.document_type == "research_paper"
    assert profile.title == "Human-to-Robot Action Recognition with Language Guidance"
    assert [section.heading for section in profile.sections] == [
        "ABSTRACT",
        "INTRODUCTION",
        "RESULTS",
        "REFERENCES",
    ]
    assert any(fact.value == "Kinetics-400" for fact in profile.key_entities)
    assert "What is this document about?" in profile.suggested_questions
    assert "What results are reported?" in profile.suggested_questions


def test_profile_detects_invoice_amounts_and_dates():
    document = make_document(
        "invoice.pdf",
        "\n".join(
            [
                "Invoice INV-1001",
                "Bill To: Xiamen University Malaysia",
                "Issue Date: 2026-08-01",
                "Due Date: 2026-08-30",
                "Subtotal RM 1,200.00",
                "Tax RM 72.00",
                "Total Due RM 1,272.00",
            ]
        ),
        [
            ("Invoice INV-1001 Bill To: Xiamen University Malaysia", "INVOICE DETAILS"),
            ("Issue Date: 2026-08-01 Due Date: 2026-08-30 Total Due RM 1,272.00", "PAYMENT SUMMARY"),
        ],
    )

    profile = build_document_profile(document)

    assert profile.document_type == "invoice"
    assert any(fact.value == "2026-08-30" for fact in profile.key_dates)
    assert any(fact.value == "RM 1,272.00" for fact in profile.key_numbers)
    assert "What total amount is due?" in profile.suggested_questions


def test_profile_extracts_research_table_metrics_without_percent_symbols():
    document = make_document(
        "paper.pdf",
        "Abstract\nThe paper evaluates action recognition.\nResults\nTOP1(%) TOP5(%) F1 score(%) Random 30.650 85.028 25.455",
        [
            ("ABSTRACT The paper evaluates action recognition.", "ABSTRACT"),
            ("RESULTS TOP1(%) TOP5(%) F1 score(%) Random 30.650 85.028 25.455", "RESULTS"),
        ],
    )

    profile = build_document_profile(document)

    assert profile.document_type == "research_paper"
    assert any(fact.value == "30.650" for fact in profile.key_numbers)


def test_profile_merges_chunk_sections_with_numbered_page_headings():
    document = make_document(
        "paper.pdf",
        "\n".join(
            [
                "Language Guided Human-to-Robot Action Recognition",
                "Abstract",
                "This paper studies human robot interaction.",
                "1. Introduction",
                "Human action recognition is important for robotics.",
                "2. Method",
                "The method fuses video and language features.",
            ]
        ),
        [
            ("ABSTRACT This paper studies human robot interaction.", "ABSTRACT"),
        ],
    )

    profile = build_document_profile(document)

    assert [section.heading for section in profile.sections] == ["ABSTRACT", "INTRODUCTION", "METHOD"]


def test_profile_detects_contract_parties_and_obligation_sections():
    document = make_document(
        "service-agreement.pdf",
        "\n".join(
            [
                "Service Agreement",
                "This agreement is between Acme Robotics Sdn Bhd and Beta University.",
                "Effective Date: January 1, 2026",
                "Obligations",
                "Acme Robotics shall provide maintenance support.",
                "Termination",
                "Either party may terminate with thirty days notice.",
            ]
        ),
        [
            ("This agreement is between Acme Robotics Sdn Bhd and Beta University.", "PARTIES"),
            ("Obligations Acme Robotics shall provide maintenance support.", "OBLIGATIONS"),
            ("Termination Either party may terminate with thirty days notice.", "TERMINATION"),
        ],
    )

    profile = build_document_profile(document)

    assert profile.document_type == "contract"
    assert any(section.heading == "OBLIGATIONS" for section in profile.sections)
    assert any(fact.value == "Acme Robotics Sdn Bhd" for fact in profile.key_entities)
    assert "Who are the parties involved?" in profile.suggested_questions


def test_profile_detects_reports_with_findings_recommendations_and_risks():
    document = make_document(
        "quarterly-report.pdf",
        "\n".join(
            [
                "Q3 Student Research Operations Report",
                "Executive Summary",
                "The report reviews lab usage and thesis milestones.",
                "Findings",
                "Students submitted 24 draft proposals.",
                "Recommendations",
                "Increase supervisor office hours before proposal week.",
                "Risks",
                "Delayed ethics approval may affect data collection.",
            ]
        ),
        [
            ("EXECUTIVE SUMMARY The report reviews lab usage and thesis milestones.", "EXECUTIVE SUMMARY"),
            ("FINDINGS Students submitted 24 draft proposals.", "FINDINGS"),
            ("RECOMMENDATIONS Increase supervisor office hours before proposal week.", "RECOMMENDATIONS"),
            ("RISKS Delayed ethics approval may affect data collection.", "RISKS"),
        ],
    )

    profile = build_document_profile(document)

    assert profile.document_type == "report"
    assert "What recommendations are listed?" in profile.suggested_questions
    assert any(section.heading == "FINDINGS" for section in profile.sections)
