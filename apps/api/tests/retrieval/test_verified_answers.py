from dataclasses import replace

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


def evidence_item(text: str, chunk_id: str = "chunk-1", heading: str | None = None) -> EvidenceItem:
    return EvidenceItem(chunk_id, "doc-1", "paper.pdf", 1, 0, text, text, 0.95, 0.95, {}, heading, "q", 0.95)


def test_verified_answer_abstains_on_high_ranked_but_irrelevant_text():
    item = evidence_item("The paper reviews human robot collaboration.", heading="ABSTRACT")
    pack = EvidencePack("What private GPU cluster was used?", "GPU cluster", ["GPU cluster"], [item])

    result = build_verified_answer(pack.question, pack)

    assert result.answer is None
    assert result.quality.status == "insufficient_evidence"
    assert result.quality.confidence == "weak"


def test_verified_answer_abstains_when_one_compound_fact_has_no_evidence():
    item = evidence_item("The method uses a transformer.", heading="METHODS")
    pack = EvidencePack(
        "What methods are used and what results are reported?", "methods and results",
        ["What methods are used?", "what results are reported?"], [item], is_multi_hop=True,
    )

    result = build_verified_answer(pack.question, pack)

    assert result.answer is None
    assert result.quality.status == "insufficient_evidence"


def test_verified_answer_uses_relevant_sentence_beyond_preview_snippet():
    text = "Background context discusses robots. " + "Background. " * 30 + "The screening retained 2092 works."
    item = replace(evidence_item(text, heading="RESULTS"), snippet=text[:260])
    pack = EvidencePack("How many works did screening retain?", "screening works", ["screening works"], [item])

    result = build_verified_answer(pack.question, pack)

    assert result.answer is not None
    assert "2092" in result.answer.summary
