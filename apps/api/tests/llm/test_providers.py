from app.core.config import Settings
from app.llm.providers import GroqLlmProvider, LocalHeuristicLlmProvider, get_llm_provider


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


def test_groq_provider_parses_json_object_wrapped_in_markdown_fence():
    provider = GroqLlmProvider(
        api_key="test-key",
        model_name="test-model",
        base_url="https://groq.example.test/openai/v1",
        timeout_seconds=30,
    )

    provider._chat = lambda _prompt, **_kwargs: (
        "```json\n"
        '{"questions":[{"question":"What methods are used?",'
        '"expected_answer":"The study uses a systematic review and three-tiered screening."}]}'
        "\n```"
    )

    questions = provider.generate_questions("Context", count=1)

    assert questions[0].question == "What methods are used?"
    assert questions[0].expected_answer == "The study uses a systematic review and three-tiered screening."


def test_groq_provider_requests_deterministic_json_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"choices": [{"message": {"content": '{"questions":[]}'}}]}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def post(self, url, headers, json):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.llm.providers.httpx.Client", FakeClient)
    provider = GroqLlmProvider(
        api_key="test-key",
        model_name="test-model",
        base_url="https://groq.example.test/openai/v1",
        timeout_seconds=30,
    )

    provider.generate_questions("Context", count=1)

    assert captured["json"]["temperature"] == 0.0
    assert captured["json"]["response_format"] == {"type": "json_object"}
