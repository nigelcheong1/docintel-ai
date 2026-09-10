from app.retrieval.evidence_pack import build_evidence_pack
from app.retrieval.search import SearchHit


def make_hit(
    chunk_id: str,
    page: int,
    text: str,
    score: float = 0.8,
    heading: str | None = None,
) -> SearchHit:
    return SearchHit(
        chunk_id=chunk_id,
        document_id="doc-1",
        document_filename="paper.pdf",
        page_number=page,
        chunk_index=page,
        text=text,
        score=score,
        source_score=score,
        ranking_signals={"keyword_overlap": score},
        section_heading=heading,
    )


def test_evidence_pack_dedupes_chunks_and_preserves_subquery():
    hits = {
        "results": [
            make_hit("chunk-1", 3, "RESULTS The study reports 2366 Scopus results.", 0.95, "RESULTS"),
            make_hit("chunk-1", 3, "RESULTS The study reports 2366 Scopus results.", 0.90, "RESULTS"),
        ]
    }

    pack = build_evidence_pack("What results are reported?", hits, "hybrid")

    assert [item.chunk_id for item in pack.items] == ["chunk-1"]
    assert pack.items[0].subquery == "results"
    assert pack.selected_chunk_count == 1
    assert pack.rejected[0].reason == "Duplicate chunk already selected."


def test_evidence_pack_keeps_diverse_pages_before_lower_rank_same_page():
    hits = {
        "screening": [
            make_hit("chunk-1", 3, "Page three gives Scopus screening counts.", 0.95),
            make_hit("chunk-2", 3, "Another page three screening passage.", 0.92),
            make_hit("chunk-3", 5, "Page five gives full-text analysis counts.", 0.88),
        ]
    }

    pack = build_evidence_pack("How many results remained after screening?", hits, "hybrid", max_items=2)

    assert [item.chunk_id for item in pack.items] == ["chunk-1", "chunk-3"]
    assert pack.selected_page_count == 2
    assert any(rejected.chunk_id == "chunk-2" for rejected in pack.rejected)
