from app.retrieval.multihop import build_query_plan, rewrite_query, split_subqueries


def test_rewrite_query_removes_document_filler():
    assert rewrite_query("What does the document say about datasets?") == "datasets"


def test_split_subqueries_extracts_compound_facts():
    subqueries = split_subqueries(
        "How many total results were initially obtained from Scopus, and how many were consolidated after duplicate removal?"
    )

    assert subqueries == [
        "How many total results were initially obtained from Scopus?",
        "How many were consolidated after duplicate removal?",
    ]


def test_build_query_plan_marks_multi_hop_only_for_distinct_subqueries():
    simple = build_query_plan("What methods are used?")
    compound = build_query_plan("What methods are used and what results are reported?")

    assert simple.subqueries == ["methods"]
    assert simple.is_multi_hop is False
    assert compound.original_query == "What methods are used and what results are reported?"
    assert compound.rewritten_query == "What methods are used and what results are reported"
    assert compound.subqueries == ["What methods are used?", "what results are reported?"]
    assert compound.is_multi_hop is True
