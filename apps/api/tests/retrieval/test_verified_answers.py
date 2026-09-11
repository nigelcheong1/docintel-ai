from app.retrieval.evidence_pack import EvidenceItem, EvidencePack
from app.retrieval.verified_answers import build_verified_answer


def test_build_verified_answer_returns_cited_answer_when_supported():
    item = EvidenceItem(
        chunk_id="chunk-1",
        document_id="doc-1",
        document_filename="paper.pdf",
        page_number=3,
        chunk_index=1,
        text=(
            "The three screening stages were database harmonization, title and abstract screening, "
            "and full-text analysis."
        ),
        snippet=(
            "The three screening stages were database harmonization, title and abstract screening, "
            "and full-text analysis."
        ),
        score=0.9,
        source_score=0.9,
        ranking_signals={},
        section_heading="RESULTS",
        subquery="screening stages",
        support_score=0.9,
    )
    pack = EvidencePack(
        question="What were the three screening stages?",
        rewritten_query="screening stages",
        subqueries=["screening stages"],
        items=[item],
        selected_chunk_count=1,
        selected_page_count=1,
        average_support_score=0.9,
    )

    result = build_verified_answer("What were the three screening stages?", pack)

    assert result.answer is not None
    assert result.quality.status == "answerable"
    assert result.verification.status == "verified"
    assert result.answer.citations[0].chunk_id == "chunk-1"


def test_build_verified_answer_abstains_without_evidence():
    pack = EvidencePack("What is the total due?", "total due", ["total due"], [])

    result = build_verified_answer("What is the total due?", pack)

    assert result.answer is None
    assert result.quality.status == "insufficient_evidence"
    assert result.verification.status == "unsupported"
