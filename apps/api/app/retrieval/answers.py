from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import BaseModel

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


def build_extractive_answer(query: str, hits: Sequence[SearchHit]) -> ExtractiveAnswer | None:
    query_terms = _words(query)
    snippets: list[str] = []
    citations: list[AnswerCitation] = []
    for hit in hits[:_MAX_ANSWER_HITS]:
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
