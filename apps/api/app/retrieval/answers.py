from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import BaseModel

from app.retrieval.reranker import (
    infer_query_intents,
    infer_section_intents,
    keyword_overlap_score,
)

if TYPE_CHECKING:
    from app.retrieval.search import SearchHit


_MAX_ANSWER_HITS = 3
_MAX_SNIPPET_CHARS = 260
_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")


class AnswerCitation(BaseModel):
    chunk_id: str
    document_filename: str
    page_number: int
    section_heading: str | None = None


class ExtractiveAnswer(BaseModel):
    summary: str
    citations: list[AnswerCitation]


def _words(text: str) -> set[str]:
    return set(_WORD_PATTERN.findall(text.lower()))


def _build_snippet(text: str, query_terms: set[str]) -> str:
    collapsed = " ".join(text.split())
    sentences = [sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(collapsed) if sentence.strip()]
    if not sentences:
        return ""
    selected = max(
        enumerate(sentences),
        key=lambda item: (len(_words(item[1]).intersection(query_terms)), -item[0]),
    )[1]
    if len(selected) <= _MAX_SNIPPET_CHARS:
        return selected
    return selected[: _MAX_SNIPPET_CHARS - 3].rstrip() + "..."


def _select_answer_hits(query: str, hits: Sequence[SearchHit]) -> Sequence[SearchHit]:
    query_intents = infer_query_intents(query)
    matching_section_hits = [
        hit
        for hit in hits
        if query_intents.intersection(infer_section_intents(hit.section_heading))
    ]
    if matching_section_hits:
        return matching_section_hits[:_MAX_ANSWER_HITS]
    return sorted(
        hits,
        key=lambda hit: (
            keyword_overlap_score(query, " ".join(part for part in (hit.section_heading, hit.text) if part)),
            hit.score,
        ),
        reverse=True,
    )[:_MAX_ANSWER_HITS]


def build_extractive_answer(query: str, hits: Sequence[SearchHit]) -> ExtractiveAnswer | None:
    query_terms = _words(query)
    snippets: list[str] = []
    citations: list[AnswerCitation] = []
    for hit in _select_answer_hits(query, hits):
        snippet = _build_snippet(hit.text, query_terms)
        if not snippet:
            continue
        snippets.append(snippet)
        citations.append(
            AnswerCitation(
                chunk_id=hit.chunk_id,
                document_filename=hit.document_filename,
                page_number=hit.page_number,
                section_heading=hit.section_heading,
            )
        )

    if not snippets:
        return None
    return ExtractiveAnswer(summary=" ".join(snippets), citations=citations)
