from app.core.config import Settings
from app.llm.providers import LocalHeuristicLlmProvider, get_llm_provider


def test_local_provider_summarizes_context_with_concise_sentences():
    provider = LocalHeuristicLlmProvider()

    summary = provider.summarize(
        "Page 1\nDocIntel extracts cited evidence. It generates study questions. It ignores unrelated noise.",
    )

    assert summary == "DocIntel extracts cited evidence. It generates study questions."


def test_local_provider_generates_unique_questions_from_context():
    provider = LocalHeuristicLlmProvider()

    questions = provider.generate_questions(
        "Payment terms require settlement within 30 days. Confidentiality obligations survive termination.",
        count=2,
    )

    assert [question.question for question in questions] == [
        "What does the document say about payment terms?",
        "What does the document say about confidentiality obligations?",
    ]
    assert all(question.expected_answer for question in questions)


def test_local_provider_evaluates_answers_with_missing_terms_feedback():
    provider = LocalHeuristicLlmProvider()

    evaluation = provider.evaluate_answer(
        question="What are the payment terms?",
        expected_answer="Payment terms require settlement within 30 days.",
        user_answer="Payment must be settled.",
    )

    assert 0 < evaluation.score < 1
    assert "Missing terms:" in evaluation.feedback
    assert "terms" in evaluation.feedback


def test_groq_provider_without_key_falls_back_to_local_provider():
    provider = get_llm_provider(Settings(llm_provider="groq", groq_api_key=None))

    assert isinstance(provider, LocalHeuristicLlmProvider)
    assert provider.provider_name == "local"
