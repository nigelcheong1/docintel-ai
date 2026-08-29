from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.retrieval.search import SearchHit

_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_INTENT_TERMS = {
    "project": {"project", "projects"},
    "skill": {"skill", "skills"},
    "education": {"education", "educational"},
    "experience": {"experience"},
    "framework": {"framework", "frameworks", "library", "libraries"},
    "tool": {"tool", "tools"},
}
_QUERY_INTENT_PHRASES = {
    "experience": {"work experience", "work history", "employment history"},
    "programming_language": {"programming language", "programming languages"},
}
_SECTION_INTENTS = {
    "TECHNICAL SKILLS": {"skill"},
    "CORE SKILLS": {"skill"},
    "TOOLS & PLATFORMS": {"skill", "tool"},
    "FRAMEWORKS & LIBRARIES": {"framework", "skill"},
    "PROGRAMMING LANGUAGES": {"programming_language", "skill"},
    "PROJECTS": {"project"},
    "KEY PROJECTS": {"project"},
    "EDUCATION": {"education"},
    "EXPERIENCE": {"experience"},
    "WORK EXPERIENCE": {"experience"},
    "WORK HISTORY": {"experience"},
    "EMPLOYMENT HISTORY": {"experience"},
}
_SKILL_FAMILY_INTENTS = {"framework", "programming_language", "tool"}
_SOURCE_SCORE_WEIGHT = 0.75
_KEYWORD_OVERLAP_WEIGHT = 0.15
_SECTION_INTENT_WEIGHT = 0.10


def _words(text: str) -> set[str]:
    return set(_WORD_PATTERN.findall(text.lower()))


def infer_query_intents(query: str) -> set[str]:
    query_words = _words(query)
    intents = {
        intent
        for intent, terms in _INTENT_TERMS.items()
        if query_words.intersection(terms)
    }
    normalized_query = " ".join(_WORD_PATTERN.findall(query.lower()))
    intents.update(
        intent
        for intent, phrases in _QUERY_INTENT_PHRASES.items()
        if any(phrase in normalized_query for phrase in phrases)
    )
    if intents.intersection(_SKILL_FAMILY_INTENTS):
        intents.add("skill")
    return intents


def infer_section_intents(section_heading: str | None) -> set[str]:
    if section_heading is None:
        return set()
    normalized_heading = " ".join(section_heading.upper().split())
    if normalized_heading in _SECTION_INTENTS:
        return set(_SECTION_INTENTS[normalized_heading])
    return set()


def keyword_overlap_score(query: str, text: str) -> float:
    query_words = _words(query)
    if not query_words:
        return 0.0
    return len(query_words.intersection(_words(text))) / len(query_words)


def _section_intent_score(query_intents: set[str], section_heading: str | None) -> float:
    return float(bool(query_intents.intersection(infer_section_intents(section_heading))))


def rerank_hits(query: str, hits: Sequence[SearchHit]) -> list[SearchHit]:
    query_intents = infer_query_intents(query)
    reranked_hits: list[SearchHit] = []
    for hit in hits:
        searchable_text = " ".join(part for part in (hit.section_heading, hit.text) if part)
        keyword_overlap = keyword_overlap_score(query, searchable_text)
        section_intent = _section_intent_score(query_intents, hit.section_heading)
        score = (
            _SOURCE_SCORE_WEIGHT * hit.source_score
            + _KEYWORD_OVERLAP_WEIGHT * keyword_overlap
            + _SECTION_INTENT_WEIGHT * section_intent
        )
        reranked_hits.append(
            replace(
                hit,
                score=score,
                ranking_signals={
                    "keyword_overlap": keyword_overlap,
                    "section_intent": section_intent,
                },
            )
        )
    return sorted(reranked_hits, key=lambda hit: hit.score, reverse=True)
