from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Protocol

import httpx

from app.core.config import Settings

_SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[.!?])\s+")
_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_PAGE_MARKER_PATTERN = re.compile(r"^\s*page\s+\d+(?:\s+[A-Za-z &/-]{1,40})?\s*$", re.IGNORECASE)
_DOTTED_LEADER_PATTERN = re.compile(r"\.{4,}")

_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "what",
    "with",
}

_QUESTION_TOPICS = (
    "overview objective",
    "design approach",
    "development pipeline",
    "training pipeline",
    "payment terms",
    "confidentiality obligations",
    "total amount",
    "contract parties",
    "datasets",
    "methods",
    "results",
    "limitations",
)


@dataclass(frozen=True)
class GeneratedQuestionResult:
    question: str
    expected_answer: str


@dataclass(frozen=True)
class AnswerEvaluationResult:
    score: float
    feedback: str


class LlmProvider(Protocol):
    provider_name: str

    def summarize(self, context: str) -> str:
        """Return a concise summary grounded in the provided context."""

    def generate_questions(self, context: str, count: int) -> list[GeneratedQuestionResult]:
        """Generate study questions from the provided context."""

    def evaluate_answer(self, question: str, expected_answer: str, user_answer: str) -> AnswerEvaluationResult:
        """Grade a study answer against the expected answer."""


def _normalize_context(context: str) -> str:
    lines = []
    for line in context.splitlines():
        stripped = line.strip()
        if not stripped or _PAGE_MARKER_PATTERN.match(stripped):
            continue
        lower = stripped.lower()
        if "table of contents" in lower or _DOTTED_LEADER_PATTERN.search(stripped):
            continue
        lines.append(stripped)
    return " ".join(lines)


def _sentences(context: str) -> list[str]:
    normalized = _normalize_context(context)
    if not normalized:
        return []
    return [sentence.strip() for sentence in _SENTENCE_SPLIT_PATTERN.split(normalized) if sentence.strip()]


def _words(text: str) -> set[str]:
    return {word for word in _WORD_PATTERN.findall(text.lower()) if word not in _STOPWORDS}


def _sentence_for_topic(sentences: list[str], topic: str) -> str | None:
    topic_words = _words(topic)
    for sentence in sentences:
        if topic.lower() in sentence.lower():
            return sentence
    for sentence in sentences:
        sentence_words = _words(sentence)
        if topic_words and topic_words.issubset(sentence_words):
            return sentence
    return None


class LocalHeuristicLlmProvider:
    provider_name = "local"

    def summarize(self, context: str) -> str:
        selected = _sentences(context)[:2]
        if not selected:
            return "No usable context was available for summarization."
        return " ".join(selected)

    def generate_questions(self, context: str, count: int) -> list[GeneratedQuestionResult]:
        if count <= 0:
            return []

        sentences = _sentences(context)
        questions: list[GeneratedQuestionResult] = []
        seen: set[str] = set()

        for topic in _QUESTION_TOPICS:
            evidence = _sentence_for_topic(sentences, topic)
            if not evidence:
                continue
            question = f"What does the document say about {topic}?"
            if question in seen:
                continue
            questions.append(GeneratedQuestionResult(question=question, expected_answer=evidence))
            seen.add(question)
            if len(questions) >= count:
                return questions

        for sentence in sentences:
            terms = sorted(_words(sentence))
            if not terms:
                continue
            topic = " ".join(terms[:2])
            question = f"What does the document say about {topic}?"
            if question in seen:
                continue
            questions.append(GeneratedQuestionResult(question=question, expected_answer=sentence))
            seen.add(question)
            if len(questions) >= count:
                return questions

        if not questions:
            questions.append(
                GeneratedQuestionResult(
                    question="What are the main points in this document?",
                    expected_answer=self.summarize(context),
                )
            )

        return questions[:count]

    def evaluate_answer(self, question: str, expected_answer: str, user_answer: str) -> AnswerEvaluationResult:
        expected_terms = _words(expected_answer) or _words(question)
        user_terms = _words(user_answer)
        if not expected_terms:
            return AnswerEvaluationResult(score=0.0, feedback="No expected answer was available for grading.")

        overlap = expected_terms & user_terms
        score = round(len(overlap) / len(expected_terms), 2)
        missing = sorted(expected_terms - user_terms)
        if not missing:
            return AnswerEvaluationResult(score=1.0, feedback="Strong answer. It covers the key terms.")

        feedback = "Missing terms: " + ", ".join(missing[:8]) + "."
        if score == 0:
            feedback = "No key terms matched. " + feedback
        return AnswerEvaluationResult(score=score, feedback=feedback)


class GroqLlmProvider:
    provider_name = "groq"

    def __init__(self, api_key: str, model_name: str, base_url: str, timeout_seconds: int) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._local_fallback = LocalHeuristicLlmProvider()

    def summarize(self, context: str) -> str:
        prompt = (
            "Summarize the document context in two concise sentences. "
            "Use only facts present in the context.\n\n"
            f"Context:\n{context}"
        )
        return self._chat(prompt).strip()

    def generate_questions(self, context: str, count: int) -> list[GeneratedQuestionResult]:
        prompt = (
            "Generate JSON for study questions from this context. "
            'Return only an array of objects with "question" and "expected_answer". '
            f"Return {count} items.\n\nContext:\n{context}"
        )
        raw = self._chat(prompt)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return self._local_fallback.generate_questions(context, count)

        questions: list[GeneratedQuestionResult] = []
        if isinstance(payload, list):
            for item in payload:
                if not isinstance(item, dict):
                    continue
                question = str(item.get("question", "")).strip()
                expected_answer = str(item.get("expected_answer", "")).strip()
                if question and expected_answer:
                    questions.append(GeneratedQuestionResult(question=question, expected_answer=expected_answer))
                if len(questions) >= count:
                    break
        return questions or self._local_fallback.generate_questions(context, count)

    def evaluate_answer(self, question: str, expected_answer: str, user_answer: str) -> AnswerEvaluationResult:
        prompt = (
            "Grade the user answer against the expected answer. "
            'Return only JSON like {"score": 0.0, "feedback": "..."}.\n\n'
            f"Question: {question}\nExpected answer: {expected_answer}\nUser answer: {user_answer}"
        )
        raw = self._chat(prompt)
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            return self._local_fallback.evaluate_answer(question, expected_answer, user_answer)

        try:
            score = float(payload.get("score", 0.0))
        except (AttributeError, TypeError, ValueError):
            return self._local_fallback.evaluate_answer(question, expected_answer, user_answer)
        feedback = str(payload.get("feedback", "")).strip()
        return AnswerEvaluationResult(score=max(0.0, min(1.0, score)), feedback=feedback or "Answer evaluated.")

    def _chat(self, prompt: str) -> str:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        with httpx.Client(timeout=self.timeout_seconds) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        data = response.json()
        return str(data["choices"][0]["message"]["content"])


def get_llm_provider(settings: Settings) -> LlmProvider:
    provider = settings.llm_provider.lower().strip()
    if provider == "groq" and settings.groq_api_key:
        return GroqLlmProvider(
            api_key=settings.groq_api_key,
            model_name=settings.llm_model_name,
            base_url=settings.groq_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    return LocalHeuristicLlmProvider()
