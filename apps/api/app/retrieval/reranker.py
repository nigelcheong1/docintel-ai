import re
from collections.abc import Sequence
from dataclasses import replace

from app.retrieval.search import SearchHit

_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_INTENT_TERMS = {
    "project": {"project", "projects"},
    "skill": {"skill", "skills"},
    "education": {"education", "educational"},
}
_SOURCE_SCORE_WEIGHT = 0.75
_KEYWORD_OVERLAP_WEIGHT = 0.15
_SECTION_INTENT_WEIGHT = 0.10


def _words(text: str) -> set[str]:
    return set(_WORD_PATTERN.findall(text.lower()))


def infer_query_intents(query: str) -> set[str]:
    query_words = _words(query)
    return {
        intent
        for intent, terms in _INTENT_TERMS.items()
        if query_words.intersection(terms)
    }


def keyword_overlap_score(query: str, text: str) -> float:
    query_words = _words(query)
    if not query_words:
        return 0.0
    return len(query_words.intersection(_words(text))) / len(query_words)


def _section_intent_score(query_intents: set[str], section_heading: str | None) -> float:
    if not query_intents or section_heading is None:
        return 0.0
    heading_words = _words(section_heading)
    return float(
        any(heading_words.intersection(_INTENT_TERMS[intent]) for intent in query_intents)
    )


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
