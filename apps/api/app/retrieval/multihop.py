from __future__ import annotations

import re
from dataclasses import dataclass

_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_FILLER_PREFIXES = (
    "what does the document say about ",
    "what does this document say about ",
    "what is this document about",
    "tell me about ",
)
_WHAT_FACT_PATTERN = re.compile(
    r"^what (?P<topic>.+?) (?:is|are|was|were) (?:used|reported|described|mentioned)$",
    re.IGNORECASE,
)
_COMPOUND_SEPARATORS = (", and ", " and what ", " and how ", " and which ", ";")


@dataclass(frozen=True)
class QueryPlan:
    original_query: str
    rewritten_query: str
    subqueries: list[str]
    is_multi_hop: bool


def _clean_question(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    return cleaned.rstrip(" ?")


def rewrite_query(question: str) -> str:
    cleaned = _clean_question(question)
    lowered = cleaned.lower()
    for prefix in _FILLER_PREFIXES:
        if lowered.startswith(prefix):
            cleaned = cleaned[len(prefix) :]
            break
    is_compound = any(separator in lowered for separator in _COMPOUND_SEPARATORS)
    match = None if is_compound else _WHAT_FACT_PATTERN.match(cleaned)
    if match:
        cleaned = match.group("topic")
    return cleaned.strip(" ?:;,.") or _clean_question(question)


def _with_question_mark(text: str) -> str:
    return text if text.endswith("?") else f"{text}?"


def split_subqueries(question: str) -> list[str]:
    cleaned = _clean_question(question)
    for separator in _COMPOUND_SEPARATORS:
        if separator in cleaned.lower():
            lowered = cleaned.lower()
            split_at = lowered.find(separator)
            first = cleaned[:split_at].strip(" ,;")
            second = cleaned[split_at + len(separator) :].strip(" ,;")
            if separator == ", and " and second:
                second = second[0].upper() + second[1:]
            elif separator.startswith(" and what "):
                second = f"what {second}"
            elif separator.startswith(" and how "):
                second = f"how {second}"
            elif separator.startswith(" and which "):
                second = f"which {second}"
            if first and second and first.lower() != second.lower():
                return [_with_question_mark(first), _with_question_mark(second)]
    return [rewrite_query(question)]


def build_query_plan(question: str) -> QueryPlan:
    rewritten = rewrite_query(question)
    subqueries = split_subqueries(question)
    normalized = {" ".join(_WORD_PATTERN.findall(item.lower())) for item in subqueries}
    is_multi_hop = len(subqueries) > 1 and len(normalized) == len(subqueries)
    return QueryPlan(
        original_query=question,
        rewritten_query=rewritten,
        subqueries=subqueries,
        is_multi_hop=is_multi_hop,
    )
