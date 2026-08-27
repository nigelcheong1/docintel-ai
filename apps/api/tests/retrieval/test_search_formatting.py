from app.retrieval.search import build_snippet, cosine_distance_to_score


def test_build_snippet_truncates_long_text():
    text = "A" * 400

    snippet = build_snippet(text, max_chars=50)

    assert len(snippet) == 50
    assert snippet.endswith("...")


def test_cosine_distance_to_score_is_clamped():
    assert cosine_distance_to_score(0.0) == 1.0
    assert cosine_distance_to_score(1.0) == 0.0
    assert cosine_distance_to_score(2.0) == 0.0
