import pytest

from app.retrieval.answers import build_grounded_answer
from app.retrieval.search import SearchHit


def evidence(text, *, chunk="source", page=1, heading=None, score=0.9):
    return SearchHit(chunk, "doc", "sample.pdf", page, 0, text, score, score, {}, heading)


def test_publication_question_rejects_topic_header_without_a_date():
    hit = evidence("Example AI Framework 1.0 Risks to interpretability can be addressed by communicating predictions.")
    answer, quality = build_grounded_answer("When was Example AI Framework 1.0 published?", [hit])
    assert answer is None
    assert quality.status == "insufficient_evidence"


def test_publication_question_selects_dated_front_matter_over_topic_overlap():
    query = "When was Example AI Framework 1.0 published?"
    irrelevant = evidence("Example AI Framework 1.0 explains why a system made a prediction.", chunk="body", page=12, score=0.99)
    publication = evidence("Example AI Framework 1.0 This publication is available from https://doi.org/10.1234/example January 2024.", chunk="publication", page=2, score=0.7)
    answer, _ = build_grounded_answer(query, [irrelevant, publication])
    assert answer is not None
    assert "January 2024" in answer.summary
    assert [citation.chunk_id for citation in answer.citations] == ["publication"]


def test_billed_to_question_keeps_customer_role_distinct_from_supplier():
    hit = evidence("Invoice number: SAMPLE-22. Supplier: Sample Supplier Ltd. Bill to: Sample Customer Co.", heading="INVOICE")
    answer, _ = build_grounded_answer("Who is the invoice billed to?", [hit])
    assert answer is not None
    assert answer.summary == "Bill to: Sample Customer Co."


def test_matching_method_in_abstract_is_not_hidden_by_a_method_heading():
    abstract = evidence("A late interaction matching method compares page embeddings.", chunk="abstract", heading="ABSTRACT")
    unrelated = evidence("Methods We processed the evaluation corpus using standard software.", chunk="methods", heading="METHODS", score=0.99)
    answer, _ = build_grounded_answer("What matching method is used?", [unrelated, abstract])
    assert answer is not None
    assert "late interaction" in answer.summary
    assert [citation.chunk_id for citation in answer.citations] == ["abstract"]


def test_counted_list_question_returns_names_not_a_generic_list_description():
    vague = evidence("The Framework Core describes four specific functions to address system risks.", chunk="vague", score=0.99)
    named = evidence("Framework Core. The Core is composed of four functions: GOVERN, MAP, MEASURE, and MANAGE.", chunk="named", score=0.85)
    answer, _ = build_grounded_answer("What are the four functions of the Framework Core?", [vague, named])
    assert answer is not None
    assert all(name in answer.summary for name in ("GOVERN", "MAP", "MEASURE", "MANAGE"))
    assert [citation.chunk_id for citation in answer.citations] == ["named"]


def test_price_question_returns_the_requested_item_amount_without_explicit_price_word():
    hit = evidence("Coffee: USD 4.00. Sandwich: USD 6.00.", heading="ITEMS")
    answer, _ = build_grounded_answer("What is the coffee price?", [hit])
    assert answer is not None
    assert answer.summary == "Coffee: USD 4.00."


def test_answer_does_not_cut_off_a_fact_at_the_preview_character_limit():
    text = "We introduce a benchmark that " + "covers visually rich documents from many domains and languages " * 6 + "and is named ClearBench."
    answer, _ = build_grounded_answer("What benchmark is introduced?", [evidence(text)])
    assert answer is not None
    assert answer.summary == text
    assert "..." not in answer.summary


def test_date_question_does_not_borrow_a_year_from_an_unrelated_sentence():
    hit = evidence("The report was published online. A separate customer workshop occurred in January 2022.")
    answer, _ = build_grounded_answer("When was the report published?", [hit])
    assert answer is None


def test_payment_terms_selects_the_value_not_a_repeated_heading():
    hit = evidence("Payment terms Payment is due on 12 April 2027. Payment terms are net 15 days.", heading="PAYMENT TERMS")
    answer, _ = build_grounded_answer("What are the payment terms?", [hit])
    assert answer is not None
    assert answer.summary == "Payment terms are net 15 days."


def test_parties_question_does_not_prefer_a_matching_agreement_title():
    title = evidence("Services Agreement", chunk="title", score=0.99)
    parties = evidence("The parties are Sample Provider Ltd and Example Customer Co.", chunk="parties", score=0.8)
    answer, _ = build_grounded_answer("Who are the parties to the services agreement?", [title, parties])
    assert answer is not None
    assert answer.summary == parties.text
    assert [citation.chunk_id for citation in answer.citations] == ["parties"]


def test_degree_completion_year_is_found_in_a_labelled_education_entry():
    hit = evidence("Education Bachelor of Science, Example College, 2021.", heading="EDUCATION")
    answer, _ = build_grounded_answer("When was the degree completed?", [hit])
    assert answer is not None
    assert "2021" in answer.summary


def test_degree_completion_does_not_borrow_an_employment_year():
    hit = evidence("Education details are not provided. Work experience began in 2021.", heading="EDUCATION")
    answer, _ = build_grounded_answer("When was the degree completed?", [hit])
    assert answer is None


def test_parties_retain_agreement_identity_when_multiple_agreements_are_retrieved():
    wrong = evidence("The parties are OtherCo and ElseCo.", chunk="wrong", score=0.99)
    correct = evidence("The software services agreement parties are Alpha and Beta.", chunk="correct", score=0.8)
    answer, _ = build_grounded_answer("Who are the parties to the software services agreement?", [wrong, correct])
    assert answer is not None
    assert [citation.chunk_id for citation in answer.citations] == ["correct"]


@pytest.mark.parametrize("entry", [
    "Education: The Bachelor of Science degree started in 2018.",
    "Education: Bachelor of Science, expected graduation in 2028.",
    "Education: Bachelor of Science, enrolled in 2018.",
])
def test_completion_year_is_not_an_enrolment_or_expected_year(entry):
    answer, _ = build_grounded_answer("When was the degree completed?", [evidence(entry, heading="EDUCATION")])
    assert answer is None


@pytest.mark.parametrize("query", [
    "What date was Example AI Framework 1.0 published?",
    "What is the release date of Example AI Framework 1.0?",
])
def test_explicit_date_wording_requires_a_date_value(query):
    answer, _ = build_grounded_answer(query, [evidence("Example AI Framework 1.0 discusses interpretability and risk.")])
    assert answer is None


def test_publication_year_must_belong_to_the_requested_publication():
    hit = evidence("Example AI Framework 1.0 discusses risk. An unrelated article was published in 2024.")
    answer, _ = build_grounded_answer("When was Example AI Framework 1.0 published?", [hit])
    assert answer is None


def test_item_price_does_not_borrow_another_items_amount_in_the_same_sentence():
    answer, _ = build_grounded_answer("What is the coffee price?", [evidence("Coffee is sold here and the sandwich costs USD 6.00.")])
    assert answer is None


def test_counted_list_rejects_adjectives_when_named_items_are_available():
    vague = evidence("The four Framework Core functions are important, complex, interrelated and documented.", chunk="vague", score=0.99)
    named = evidence("The Framework Core has four functions: GOVERN, MAP, MEASURE, and MANAGE.", chunk="named", score=0.85)
    answer, _ = build_grounded_answer("What are the four functions of the Framework Core?", [vague, named])
    assert answer is not None
    assert [citation.chunk_id for citation in answer.citations] == ["named"]


def test_angular_degrees_do_not_match_education():
    answer, _ = build_grounded_answer("How many degrees is the rotation?", [evidence("Education covers rotation in 3 modules.")])
    assert answer is None


@pytest.mark.parametrize("query,text", [
    ("What cost function is used?", "The cost function is cross-entropy."),
    ("When should the valve be replaced?", "The valve should be replaced if it leaks."),
])
def test_incidental_value_words_do_not_force_money_or_calendar_answers(query, text):
    answer, _ = build_grounded_answer(query, [evidence(text)])
    assert answer is not None


def test_count_question_accepts_synonymous_screening_count_wording():
    hit = evidence("Screening began with 2,400 CatalogX records.", heading="RESULTS")
    answer, _ = build_grounded_answer("How many total results were initially obtained from CatalogX?", [hit])
    assert answer is not None
    assert "2,400" in answer.summary


def test_direct_answer_sentence_outranks_keywords_scattered_across_a_chunk():
    direct = evidence("We introduce ClearBench, a visual document retrieval benchmark with tasks across several domains.", chunk="direct", score=0.8)
    indirect = evidence("Visual document retrieval is discussed. We fill the gap with OldBench, a document benchmark. We introduce our paper.", chunk="indirect", score=0.99)
    answer, _ = build_grounded_answer("What is the visual document retrieval benchmark introduced in this paper?", [indirect, direct])
    assert answer is not None
    assert answer.citations[0].chunk_id == "direct"


def test_named_functions_do_not_use_an_unrelated_contents_page_colon():
    contents = evidence("Four Framework Core functions Appendix A: Descriptions, Figures, Profiles, and Tasks.", chunk="contents", score=0.99)
    named = evidence("The Framework Core has four functions: GOVERN, MAP, MEASURE, and MANAGE.", chunk="named", score=0.85)
    answer, _ = build_grounded_answer("What are the four functions of the Framework Core?", [contents, named])
    assert answer is not None
    assert [citation.chunk_id for citation in answer.citations] == ["named"]
