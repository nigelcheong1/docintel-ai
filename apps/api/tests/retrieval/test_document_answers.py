from app.db.models import Chunk, Document, DocumentStatus, Page
from app.documents.intelligence import build_document_profile
from app.retrieval.document_answers import build_document_aware_answer
from app.retrieval.query_router import route_query


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


def answer_for(query: str, document: Document):
    profile = build_document_profile(document)
    route = route_query(query, profile.document_type)
    return build_document_aware_answer(query, document, profile, route)


def test_builds_research_paper_overview_from_abstract():
    document = make_document(
        "paper.pdf",
        "Title\nAbstract\nThis paper proposes a language-guided transformer for human-robot action recognition.",
        [
            (
                "ABSTRACT This paper proposes a language-guided transformer for human-robot action recognition.",
                "ABSTRACT",
            ),
            ("REFERENCES Smith 2024.", "REFERENCES"),
        ],
    )

    result = answer_for("What is this document about?", document)

    assert result is not None
    assert result.answer is not None
    assert result.quality.status == "answerable"
    assert result.query_intent == "overview"
    assert "language-guided transformer" in result.answer.summary
    assert result.answer.citations[0].section_heading == "ABSTRACT"


def test_builds_invoice_amount_answer_from_total_chunk():
    document = make_document(
        "invoice.pdf",
        "Invoice\nDue Date 2026-08-30\nTotal Due RM 1,272.00",
        [("PAYMENT SUMMARY Due Date 2026-08-30 Total Due RM 1,272.00", "PAYMENT SUMMARY")],
    )

    result = answer_for("What total amount is due?", document)

    assert result is not None
    assert result.answer is not None
    assert "RM 1,272.00" in result.answer.summary
    assert result.quality.confidence == "strong"


def test_builds_research_metric_answer_from_table_numbers():
    document = make_document(
        "paper.pdf",
        "Abstract\nThe paper evaluates action recognition.\nResults\nTOP1(%) TOP5(%) F1 score(%) Random 30.650 85.028 25.455",
        [
            ("ABSTRACT The paper evaluates action recognition.", "ABSTRACT"),
            ("RESULTS TOP1(%) TOP5(%) F1 score(%) Random 30.650 85.028 25.455", "RESULTS"),
        ],
    )

    result = answer_for("What amounts or totals are mentioned?", document)

    assert result is not None
    assert result.answer is not None
    assert "30.650" in result.answer.summary


def test_builds_contract_parties_answer():
    document = make_document(
        "agreement.pdf",
        "Service Agreement\nThis agreement is between Acme Robotics Sdn Bhd and Beta University.",
        [("This agreement is between Acme Robotics Sdn Bhd and Beta University.", "PARTIES")],
    )

    result = answer_for("Who are the parties involved?", document)

    assert result is not None
    assert result.answer is not None
    assert "Acme Robotics Sdn Bhd" in result.answer.summary
    assert "Beta University" in result.answer.summary


def test_abstains_with_type_aware_reason_for_contract_question_on_research_paper():
    document = make_document(
        "paper.pdf",
        "Title\nAbstract\nThis paper studies video action recognition.",
        [("ABSTRACT This paper studies video action recognition.", "ABSTRACT")],
    )

    result = answer_for("Who are the parties involved?", document)

    assert result is not None
    assert result.answer is None
    assert result.quality.status == "insufficient_evidence"
    assert "research paper" in result.quality.reason.lower()
    assert "What methods are used?" in result.quality.suggested_questions
