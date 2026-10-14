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
_COMPOUND_SEPARATORS = (", and ", " and what ", " and how ", " and which ", " and who ", " and when ", ";")
_QUOTED_TEXT_PATTERN = re.compile(r'"[^"]*"|\u201c[^\u201d]*\u201d' r"|(?<!\w)'[^']*'(?!\w)")
_SHARED_PRICE_PATTERN = re.compile(
    r"(What are (?:the )?(?:listed )?)([\w-]+(?: [\w-]+)*) and ([\w-]+(?: [\w-]+)*)( prices)",
    re.IGNORECASE,
)
_ITEM_CONJUNCTION_PATTERN = re.compile(r"\b(?:and|or)\b", re.IGNORECASE)
_SINGULAR_TOPIC_PATTERN = re.compile(
    r"^(?:what|which) (?P<topic>[a-z0-9-]+(?: [a-z0-9-]+)*) (?:is|was) "
    r"(?:listed|reported|described|mentioned|used)$",
    re.IGNORECASE,
)
_TOPIC_LINK_PATTERN = re.compile(r"\b(?:and|or|of|for|from|in|on|at|with|by|to)\b", re.IGNORECASE)
_FOLLOWUP_PRONOUN_PATTERN = re.compile(
    r"^(?P<prefix>(?:(?:when|where|why|how|what) (?:is|was|does|did|has|had|can|could|will|would)"
    r"|who [a-z-]+) )it\b",
    re.IGNORECASE,
)
_AUXILIARY_PATTERN = re.compile(r"^(?:is|are|was|were|do|does|did|has|have|had|can|could|will|would)\b", re.IGNORECASE)


@dataclass(frozen=True)
class QueryPlan:
    original_query: str
    rewritten_query: str
    subqueries: list[str]
    is_multi_hop: bool


def _clean_question(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    for opening, closing in (("\"", "\""), ("\u201c", "\u201d")):
        if cleaned.startswith(opening) and cleaned.endswith(closing) and len(cleaned) > 1:
            cleaned = cleaned[1:-1].strip()
            break
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


def _resolve_singular_pronoun(first: str, second: str) -> str:
    match = _SINGULAR_TOPIC_PATTERN.fullmatch(first)
    if not match:
        return second
    topic = match.group("topic")
    if _TOPIC_LINK_PATTERN.search(topic):
        return second
    antecedent = topic if topic.lower().startswith("the ") else f"the {topic}"
    return _FOLLOWUP_PRONOUN_PATTERN.sub(lambda followup: f"{followup.group('prefix')}{antecedent}", second)


def split_subqueries(question: str) -> list[str]:
    cleaned = _clean_question(question)
    shared = re.fullmatch(r"(What (?:is|are) (?:the )?)(methods|results|findings|risks|limitations|datasets) and (methods|results|findings|risks|limitations|datasets)", cleaned, re.IGNORECASE)
    if shared:
        prefix, first, second = shared.groups()
        return [_with_question_mark(f"{prefix}{first}"), _with_question_mark(f"{prefix}{second}")]
    shared_prices = _SHARED_PRICE_PATTERN.fullmatch(cleaned)
    if shared_prices:
        prefix, first, second, suffix = shared_prices.groups()
        # Extra conjunctions and title-cased name pairs leave item boundaries ambiguous.
        if not _ITEM_CONJUNCTION_PATTERN.search(f"{first} {second}") and not (first.istitle() and second.istitle()):
            return [_with_question_mark(f"{prefix}{first}{suffix}"), _with_question_mark(f"{prefix}{second}{suffix}")]
    # Keep conjunctions inside quoted titles and names out of clause detection.
    lowered = _QUOTED_TEXT_PATTERN.sub(lambda match: " " * len(match.group()), cleaned).lower()
    for separator in _COMPOUND_SEPARATORS:
        if separator in lowered:
            split_at = lowered.find(separator)
            first = cleaned[:split_at].strip(" ,;")
            second = cleaned[split_at + len(separator) :].strip(" ,;")
            if separator == ", and " and second:
                if not re.match(r"^(?:what|how|which|who|when|why|where)\b", second, re.IGNORECASE):
                    continue
                second = second[0].upper() + second[1:]
            elif separator.startswith(" and what "):
                second = f"what {second}"
            elif separator.startswith(" and how "):
                second = f"how {second}"
            elif separator.startswith(" and which "):
                second = f"which {second}"
            elif separator == " and who ":
                if second and second.split()[0].istitle() and not _AUXILIARY_PATTERN.match(second):
                    continue
                second = f"who {second}"
            elif separator == " and when ":
                if not _AUXILIARY_PATTERN.match(second):
                    continue
                second = f"when {second}"
            if first and second and first.lower() != second.lower():
                second = _resolve_singular_pronoun(first, second)
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
