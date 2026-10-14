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


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        (
            "What degree is listed, and when was it completed?",
            ["What degree is listed?", "When was the degree completed?"],
        ),
        (
            "Which certification was reported, and who issued it?",
            ["Which certification was reported?", "Who issued the certification?"],
        ),
        (
            "What research project is described, and when was it completed?",
            ["What research project is described?", "When was the research project completed?"],
        ),
        (
            "What PhD is listed, and when was it completed?",
            ["What PhD is listed?", "When was the PhD completed?"],
        ),
        (
            'What research project is described, and when was it renamed "It Works"?',
            ['What research project is described?', 'When was the research project renamed "It Works"?'],
        ),
    ],
)
def test_split_subqueries_carries_a_clear_topic_into_singular_pronouns(question, expected):
    assert split_subqueries(question) == expected


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        (
            "What are the listed coffee and sandwich prices?",
            ["What are the listed coffee prices?", "What are the listed sandwich prices?"],
        ),
        (
            "What are the tea and coffee prices?",
            ["What are the tea prices?", "What are the coffee prices?"],
        ),
        (
            "What are the sandwich and coffee prices?",
            ["What are the sandwich prices?", "What are the coffee prices?"],
        ),
        (
            "What are the scanning and editing prices?",
            ["What are the scanning prices?", "What are the editing prices?"],
        ),
        (
            "What are the listed document indexing and evidence review prices?",
            ["What are the listed document indexing prices?", "What are the listed evidence review prices?"],
        ),
        (
            "What are the PDF conversion and 3D printing prices?",
            ["What are the PDF conversion prices?", "What are the 3D printing prices?"],
        ),
        (
            "What are the metadata-editing and archival-storage prices?",
            ["What are the metadata-editing prices?", "What are the archival-storage prices?"],
        ),
    ],
)
def test_query_plan_decomposes_shared_item_prices(question, expected):
    plan = build_query_plan(question)

    assert plan.original_query == question
    assert plan.rewritten_query == question.rstrip("?")
    assert plan.subqueries == expected
    assert plan.is_multi_hop is True


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        (
            "What degree is listed and when was it completed?",
            ["What degree is listed?", "when was the degree completed?"],
        ),
        (
            "What degree is listed and who awarded it?",
            ["What degree is listed?", "who awarded the degree?"],
        ),
        (
            "When did the course end and who supervised the assessment?",
            ["When did the course end?", "who supervised the assessment?"],
        ),
    ],
)
def test_split_subqueries_recognizes_who_and_when_without_a_comma(question, expected):
    assert split_subqueries(question) == expected


@pytest.mark.parametrize(
    "question",
    [
        "Which reference includes planning, perception, and embodied execution?",
        "Which entry includes coffee, tea, and sandwich prices?",
        'What are the listed "fish and chips" prices?',
        "What are the listed Bread and Butter prices?",
        'What are the listed "research and development" prices?',
        "What are the listed 'scanning and editing' prices?",
        "What are the listed \u201cdocument indexing and evidence review\u201d prices?",
        "What are the scanning, indexing, and editing prices?",
        "What are the scanning and indexing and editing prices?",
        "What are the scanning or indexing and editing prices?",
        "Which employer is listed as Johnson and Johnson?",
        'Which employer is listed as "Who and When Labs"?',
        "Which employer is listed as Who and When Labs?",
        "Which employer is listed as Who and Who Labs?",
        'Which report mentions "Research and What Works"?',
        "Which report mentions 'Research and What Works'?",
        "Which report mentions \u201cResearch and What Works\u201d?",
    ],
)
def test_query_plan_preserves_criteria_lists_and_entity_conjunctions(question):
    plan = build_query_plan(question)

    assert plan.subqueries == [question.rstrip("?")]
    assert plan.is_multi_hop is False


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        (
            "What degree and diploma are listed, and when was it completed?",
            ["What degree and diploma are listed?", "When was it completed?"],
        ),
        (
            "What did Maya discuss with Lina, and when was it completed?",
            ["What did Maya discuss with Lina?", "When was it completed?"],
        ),
        (
            "What degree is listed on the certificate, and when was it completed?",
            ["What degree is listed on the certificate?", "When was it completed?"],
        ),
        (
            "What degree is listed, and when were they completed?",
            ["What degree is listed?", "When were they completed?"],
        ),
        (
            "What degree or certificate is listed, and when was it completed?",
            ["What degree or certificate is listed?", "When was it completed?"],
        ),
        (
            "What degree from the program is listed, and when was it completed?",
            ["What degree from the program is listed?", "When was it completed?"],
        ),
        (
            "What degree is listed, and when was the diploma replaced after it expired?",
            ["What degree is listed?", "When was the diploma replaced after it expired?"],
        ),
    ],
)
def test_split_subqueries_does_not_guess_ambiguous_or_mismatched_antecedents(question, expected):
    assert split_subqueries(question) == expected


def test_rewrite_query_preserves_a_compound_when_clause_ending_in_a_fact_verb():
    plan = build_query_plan("What degree is listed and when was it mentioned?")

    assert plan.rewritten_query == "What degree is listed and when was it mentioned"
    assert plan.subqueries == ["What degree is listed?", "when was the degree mentioned?"]
    assert plan.is_multi_hop is True
