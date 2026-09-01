from __future__ import annotations

import re
from dataclasses import dataclass, field

_WORD_PATTERN = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class QueryRoute:
    intent: str
    preferred_section_intents: set[str] = field(default_factory=set)
    mismatch_reason: str | None = None


def _normalized(query: str) -> str:
    return " ".join(_WORD_PATTERN.findall(query.lower()))


def _has_any(normalized_query: str, terms: set[str]) -> bool:
    return any(term in normalized_query for term in terms)


def _mismatch_reason(intent: str, document_type: str | None) -> str | None:
    if document_type == "research_paper" and intent == "parties":
        return (
            "This document is classified as a research paper, so contract-style parties are not expected. "
            "Ask about authors, methods, datasets, results, or limitations instead."
        )
    if document_type == "research_paper" and intent in {"amounts", "payment_due", "payment_terms"}:
        return (
            "This document is classified as a research paper, so invoice totals or payment due amounts are not expected. "
            "Ask about metrics, datasets, results, methods, or limitations instead."
        )
    if document_type == "invoice" and intent in {"methods", "datasets", "results", "limitations"}:
        return (
            "This document is classified as an invoice, so research-paper evidence for this question is not expected."
        )
    if document_type == "resume" and intent in {"amounts", "parties", "obligations", "risks"}:
        return (
            "This document is classified as a resume, so invoice or contract evidence for this question is not expected."
        )
    if document_type == "contract" and intent in {"datasets", "methods", "results", "limitations"}:
        return (
            "This document is classified as a contract, so research-paper evidence for this question is not expected."
        )
    return None


def route_query(query: str, document_type: str | None = None) -> QueryRoute:
    normalized_query = _normalized(query)

    if _has_any(
        normalized_query,
        {
            "what is this document about",
            "what is the document about",
            "what are the main topics",
            "main topics",
            "summarize",
            "summary",
            "overview",
        },
    ):
        return QueryRoute("overview", {"overview", "background", "summary"})

    intent_rules: list[tuple[str, set[str], set[str]]] = [
        ("authors", {"author", "authors", "who wrote", "written by"}, {"overview"}),
        (
            "contributions",
            {"contribution", "contributions", "main contribution", "novel", "propose", "proposed", "introduce", "introduced"},
            {"overview", "method"},
        ),
        ("datasets", {"dataset", "datasets", "benchmark", "benchmarks", "corpus", "data used"}, {"dataset", "evaluation"}),
        ("methods", {"method", "methods", "methodology", "approach", "model", "architecture", "technique"}, {"method"}),
        ("results", {"result", "results", "accuracy", "performance", "f1", "top1", "top5"}, {"result"}),
        ("findings", {"finding", "findings", "insight", "insights"}, {"result"}),
        ("limitations", {"limitation", "limitations", "future work", "challenge", "challenges", "drawback"}, {"limitation", "risk"}),
        ("recommendations", {"recommendation", "recommendations", "recommended", "next steps"}, {"recommendation", "result"}),
        ("risks", {"risk", "risks", "issue", "issues", "termination terms"}, {"risk", "limitation"}),
        ("obligations", {"obligation", "obligations", "responsibility", "responsibilities", "shall", "must", "duties"}, {"obligation"}),
        ("payment_due", {"payment due", "when is payment due", "when payment due"}, {"date", "payment"}),
        ("dates", {"date", "dates", "deadline", "deadlines", "when", "due date", "effective date"}, {"date"}),
        ("payment_terms", {"payment terms", "payment term", "terms of payment"}, {"payment", "date", "amount"}),
        ("amounts", {"amount", "amounts", "total", "totals", "subtotal", "balance", "price", "cost", "fee", "tax"}, {"amount", "payment"}),
        ("parties", {"party", "parties", "involved", "bill to", "billed to", "vendor", "client", "customer", "supplier"}, {"party"}),
        ("skills", {"skill", "skills", "technical skill", "technical skills"}, {"skill"}),
        ("programming_language", {"programming language", "programming languages"}, {"programming_language", "skill"}),
        ("frameworks", {"framework", "frameworks", "library", "libraries"}, {"framework", "skill"}),
        ("tools", {"tool", "tools", "platform", "platforms"}, {"tool", "skill"}),
        ("projects", {"project", "projects"}, {"project"}),
        ("education", {"education", "educational", "background"}, {"education"}),
        ("experience", {"experience", "work history", "employment"}, {"experience"}),
    ]
    for intent, terms, section_intents in intent_rules:
        if _has_any(normalized_query, terms):
            return QueryRoute(
                intent=intent,
                preferred_section_intents=section_intents,
                mismatch_reason=_mismatch_reason(intent, document_type),
            )

    return QueryRoute("evidence_search", set())
