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


def test_listed_resume_project_question_stays_project_scoped():
    route = route_query("What projects are listed in this document?", "resume")

    assert route.intent == "projects"
    assert "project" in route.preferred_section_intents


def test_routes_contract_parties_queries():
    route = route_query("Who are the parties involved?", "contract")

    assert route.intent == "parties"
    assert "party" in route.preferred_section_intents


def test_marks_contract_question_as_mismatch_for_research_paper():
    route = route_query("Who are the parties involved?", "research_paper")

    assert route.intent == "parties"
    assert "research paper" in route.mismatch_reason.lower()
    assert "contract" in route.mismatch_reason.lower()


def test_routes_all_generated_profile_suggestions():
    questions = {
        "research_paper": [
            "What is this document about?",
            "What methods are used?",
            "What datasets are mentioned?",
            "What results are reported?",
            "What limitations or future work are discussed?",
        ],
        "invoice": [
            "What total amount is due?",
            "When is payment due?",
            "Who is the invoice billed to?",
            "What payment terms are mentioned?",
        ],
        "contract": [
            "Who are the parties involved?",
            "What obligations are mentioned?",
            "What risks or termination terms are mentioned?",
            "What dates are mentioned?",
        ],
        "report": [
            "What is this document about?",
            "What are the key findings?",
            "What recommendations are listed?",
            "What risks are mentioned?",
        ],
        "resume": [
            "What technical skills are mentioned?",
            "What projects are listed in this document?",
            "What education background is listed?",
            "What experience is described?",
        ],
    }

    for document_type, suggested_questions in questions.items():
        for question in suggested_questions:
            route = route_query(question, document_type)
            assert route.intent != "evidence_search", f"{document_type}: {question}"
