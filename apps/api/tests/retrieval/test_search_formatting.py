from app.retrieval.search import SearchHit, build_snippet, cosine_distance_to_score, format_search_hit


def test_build_snippet_truncates_long_text():
    text = "A" * 400

    snippet = build_snippet(text, max_chars=50)

    assert len(snippet) == 50
    assert snippet.endswith("...")


def test_cosine_distance_to_score_is_clamped():
    assert cosine_distance_to_score(0.0) == 1.0
    assert cosine_distance_to_score(1.0) == 0.0
    assert cosine_distance_to_score(2.0) == 0.0


def test_format_search_hit_exposes_source_score_and_ranking_signals():
    hit = SearchHit(
        chunk_id="chunk-1",
        document_id="document-1",
        document_filename="resume.pdf",
        page_number=1,
        chunk_index=2,
        text="KEY PROJECTS Built a local search tool.",
        score=0.93,
        source_score=0.88,
        ranking_signals={"keyword_overlap": 1.0, "section_intent": 1.0},
        section_heading="KEY PROJECTS",
    )

    formatted = format_search_hit(hit)

    assert formatted.score == 0.93
    assert formatted.source_score == 0.88
    assert formatted.ranking_signals == {"keyword_overlap": 1.0, "section_intent": 1.0}
    assert formatted.section_heading == "KEY PROJECTS"
