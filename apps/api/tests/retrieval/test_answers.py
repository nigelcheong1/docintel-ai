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


def test_build_extractive_answer_prefers_matching_sections_and_does_not_force_three_citations():
    skill_hit = make_hit(
        chunk_id="skill",
        text="Technical Skills Python SQL PyTorch.",
        page_number=1,
        section_heading="TECHNICAL SKILLS",
    )
    education_hit = make_hit(
        chunk_id="education",
        text="EDUCATION B.Eng. Artificial Intelligence.",
        page_number=1,
        section_heading="EDUCATION",
    )
    experience_hit = make_hit(
        chunk_id="experience",
        text="EXPERIENCE Mathematics Tutor.",
        page_number=1,
        section_heading="EXPERIENCE",
    )

    answer = build_extractive_answer(
        "What technical skills are mentioned?",
        [skill_hit, education_hit, experience_hit],
    )

    assert answer is not None
    assert [citation.chunk_id for citation in answer.citations] == ["skill"]
    assert "EDUCATION" not in answer.summary
    assert "EXPERIENCE" not in answer.summary


def test_build_extractive_answer_uses_programming_language_section_for_language_queries():
    project_hit = make_hit(
        chunk_id="project",
        text="PROJECTS Thesis medical segmentation.",
        page_number=1,
        section_heading="PROJECTS",
    )
    language_hit = make_hit(
        chunk_id="languages",
        text="Programming Languages Python, C++, C language.",
        page_number=1,
        section_heading="PROGRAMMING LANGUAGES",
    )

    answer = build_extractive_answer(
        "What programming languages does this candidate know?",
        [project_hit, language_hit],
    )

    assert answer is not None
    assert [citation.chunk_id for citation in answer.citations] == ["languages"]
    assert "Python" in answer.summary
    assert "PROJECTS" not in answer.summary


def test_build_extractive_answer_does_not_treat_bare_work_as_experience_intent():
    invoice_hit = make_hit(
        chunk_id="invoice",
        text="Invoice payment is due within 30 days.",
        page_number=1,
        section_heading="PAYMENT TERMS",
    )
    experience_hit = make_hit(
        chunk_id="experience",
        text="Work history includes accounting process improvements.",
        page_number=2,
        section_heading="WORK EXPERIENCE",
    )

    answer = build_extractive_answer(
        "How does invoice payment work?",
        [invoice_hit, experience_hit],
    )

    assert answer is not None
    assert answer.citations[0].chunk_id == "invoice"
    assert answer.summary.startswith("Invoice payment is due within 30 days.")


def test_build_extractive_answer_does_not_treat_bare_language_as_programming_intent():
    contract_hit = make_hit(
        chunk_id="contract",
        text="This contract is written in English language.",
        page_number=1,
        section_heading="GOVERNING LANGUAGE",
    )
    language_hit = make_hit(
        chunk_id="languages",
        text="Programming Languages Python and SQL.",
        page_number=2,
        section_heading="PROGRAMMING LANGUAGES",
    )

    answer = build_extractive_answer(
        "What language is this contract written in?",
        [contract_hit, language_hit],
    )

    assert answer is not None
    assert answer.citations[0].chunk_id == "contract"
    assert answer.summary.startswith("This contract is written in English language.")
