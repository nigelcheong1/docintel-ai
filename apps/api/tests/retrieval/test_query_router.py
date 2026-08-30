from app.retrieval.query_router import route_query


def test_routes_research_paper_overview_queries():
    route = route_query("What is this document about?", "research_paper")

    assert route.intent == "overview"
    assert "overview" in route.preferred_section_intents
    assert route.mismatch_reason is None


def test_routes_invoice_amount_queries():
    route = route_query("What total amount is due?", "invoice")

    assert route.intent == "amounts"
    assert "amount" in route.preferred_section_intents


def test_routes_contract_parties_queries():
    route = route_query("Who are the parties involved?", "contract")

    assert route.intent == "parties"
    assert "party" in route.preferred_section_intents


def test_marks_contract_question_as_mismatch_for_research_paper():
    route = route_query("Who are the parties involved?", "research_paper")

    assert route.intent == "parties"
    assert "research paper" in route.mismatch_reason.lower()
    assert "contract" in route.mismatch_reason.lower()
