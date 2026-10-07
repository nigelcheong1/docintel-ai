import pytest

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


def test_split_subqueries_preserves_a_list_of_table_columns():
    question = "Which reference includes planning, perception, and embodied execution?"

    assert split_subqueries(question) == [rewrite_query(question)]


def test_split_subqueries_handles_shared_interrogative():
    assert split_subqueries("What are the methods and results?") == ["What are the methods?", "What are the results?"]


@pytest.mark.parametrize("quotes", [('"', '"'), ("\u201c", "\u201d")])
def test_query_plan_removes_outer_quotes_from_copied_questions(quotes):
    question = "How many results were obtained from Scopus, and how many remained after duplicate removal?"
    plan = build_query_plan(f"{quotes[0]}{question}{quotes[1]}")

    assert plan.subqueries == [
        "How many results were obtained from Scopus?",
        "How many remained after duplicate removal?",
    ]
    assert plan.rewritten_query == question.rstrip("?")
