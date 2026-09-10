from app.retrieval.evidence_pack import EvidenceItem, EvidencePack
from app.retrieval.verifier import filter_supported_answer, verify_answer


def make_pack() -> EvidencePack:
    item = EvidenceItem(
        chunk_id="chunk-1",
        document_id="doc-1",
        document_filename="paper.pdf",
        page_number=3,
        chunk_index=1,
        text="From Scopus, 2366 results were obtained, including 1180 papers and 1351 conference proceedings.",
        snippet="From Scopus, 2366 results were obtained.",
        score=0.95,
        source_score=0.95,
        ranking_signals={},
        section_heading="RESULTS",
        subquery="screening counts",
        support_score=0.95,
    )
    return EvidencePack(
        question="How many Scopus results were obtained?",
        rewritten_query="Scopus results",
        subqueries=["Scopus results"],
        items=[item],
        selected_chunk_count=1,
        selected_page_count=1,
        average_support_score=0.95,
    )


def test_verify_answer_accepts_supported_numbers():
    result = verify_answer("The study obtained 2366 Scopus results.", make_pack())

    assert result.status == "verified"
    assert result.hallucination_risk == 0.0
    assert result.sentences[0].supporting_chunk_ids == ["chunk-1"]


def test_verify_answer_rejects_unsupported_numbers():
    result = verify_answer("The study obtained 5000 Scopus results.", make_pack())

    assert result.status == "unsupported"
    assert result.unsupported_sentence_count == 1
    assert result.hallucination_risk == 1.0


def test_filter_supported_answer_removes_unsupported_sentence():
    answer, result = filter_supported_answer(
        "The study obtained 2366 Scopus results. It used a private GPU cluster.",
        make_pack(),
    )

    assert answer == "The study obtained 2366 Scopus results."
    assert result.status == "partially_supported"
    assert result.removed_sentence_count == 1
