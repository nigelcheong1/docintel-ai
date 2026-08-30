from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.retrieval.search import SearchHit

_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_INTENT_TERMS = {
    "amount": {"amount", "amounts", "total", "totals", "subtotal", "balance", "tax"},
    "date": {"date", "dates", "deadline", "deadlines", "when"},
    "dataset": {"dataset", "datasets", "benchmark", "benchmarks", "corpus"},
    "method": {"method", "methods", "methodology", "approach", "model", "architecture"},
    "obligation": {"obligation", "obligations", "responsibility", "responsibilities"},
    "party": {"party", "parties", "involved", "vendor", "client", "customer", "supplier"},
    "project": {"project", "projects"},
    "result": {"result", "results", "finding", "findings", "accuracy", "performance"},
    "risk": {"risk", "risks", "limitation", "limitations", "challenge", "challenges"},
    "skill": {"skill", "skills"},
    "education": {"education", "educational"},
    "experience": {"experience"},
    "framework": {"framework", "frameworks", "library", "libraries"},
    "tool": {"tool", "tools"},
}
_QUERY_INTENT_PHRASES = {
    "amount": {"total due", "balance due", "payment due"},
    "date": {"due date", "effective date", "key dates"},
    "dataset": {"datasets mentioned", "benchmarks mentioned", "data used"},
    "experience": {"work experience", "work history", "employment history"},
    "method": {"methods used", "methodology used"},
    "result": {"results reported", "key findings"},
    "risk": {"future work", "termination terms"},
    "payment_terms": {"payment terms", "payment term"},
    "recommendation": {"recommendations listed", "key recommendations"},
    "programming_language": {"programming language", "programming languages"},
    "summary": {"what is this document about", "main topics", "summarize", "summary", "overview"},
}
_SECTION_INTENTS = {
    "ABSTRACT": {"summary", "overview"},
    "KEYWORDS": {"summary"},
    "INTRODUCTION": {"summary", "overview", "background"},
    "BACKGROUND": {"background"},
    "RELATED WORK": {"background"},
    "LITERATURE REVIEW": {"background"},
    "METHODOLOGY": {"method"},
    "METHOD": {"method"},
    "METHODS": {"method"},
    "APPROACH": {"method"},
    "MODEL": {"method"},
    "EXPERIMENT": {"method", "result"},
    "EXPERIMENTS": {"method", "result"},
    "EXPERIMENTAL SETUP": {"method"},
    "EVALUATION": {"result", "dataset"},
    "RESULT": {"result"},
    "RESULTS": {"result"},
    "DISCUSSION": {"result", "risk"},
    "LIMITATION": {"risk"},
    "LIMITATIONS": {"risk"},
    "FUTURE WORK": {"risk"},
    "CONCLUSION": {"summary", "result"},
    "REFERENCES": {"reference"},
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
    "INVOICE": {"summary", "amount"},
    "INVOICE DETAILS": {"summary", "amount", "party"},
    "INVOICE SUMMARY": {"summary", "amount", "date", "payment"},
    "PAYMENT SUMMARY": {"amount", "date", "payment"},
    "PAYMENT TERMS": {"amount", "date", "payment", "payment_terms"},
    "BILL TO": {"party"},
    "SHIP TO": {"party"},
    "VENDOR": {"party"},
    "CLIENT": {"party"},
    "ITEMS": {"amount"},
    "SUBTOTAL": {"amount"},
    "TAX": {"amount"},
    "TOTAL": {"amount"},
    "BALANCE DUE": {"amount"},
    "AGREEMENT": {"summary", "party"},
    "PARTIES": {"party"},
    "TERMS": {"obligation"},
    "OBLIGATIONS": {"obligation"},
    "RESPONSIBILITIES": {"obligation"},
    "PAYMENT": {"amount", "payment"},
    "CONFIDENTIALITY": {"obligation", "risk"},
    "TERMINATION": {"risk"},
    "LIABILITY": {"risk"},
    "GOVERNING LAW": {"risk"},
    "SIGNATURES": {"party"},
    "EFFECTIVE DATE": {"date"},
    "EXECUTIVE SUMMARY": {"summary", "overview"},
    "FINDINGS": {"result"},
    "RECOMMENDATIONS": {"result", "risk", "recommendation"},
    "RISKS": {"risk"},
    "NEXT STEPS": {"risk"},
    "OVERVIEW": {"summary", "overview"},
    "OBJECTIVES": {"summary"},
    "SCOPE": {"summary"},
    "ANALYSIS": {"result"},
    "DATASET": {"dataset"},
    "DATASETS": {"dataset"},
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
