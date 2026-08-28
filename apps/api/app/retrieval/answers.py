from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    from app.retrieval.search import SearchHit


_MAX_ANSWER_HITS = 3
_MAX_SNIPPET_CHARS = 260


class AnswerCitation(BaseModel):
    chunk_id: str
    document_filename: str
    page_number: int
    section_heading: str | None = None


class ExtractiveAnswer(BaseModel):
    summary: str
    citations: list[AnswerCitation]


def _build_snippet(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= _MAX_SNIPPET_CHARS:
        return collapsed
    return collapsed[: _MAX_SNIPPET_CHARS - 3].rstrip() + "..."


def build_extractive_answer(query: str, hits: Sequence[SearchHit]) -> ExtractiveAnswer | None:
    del query
    snippets: list[str] = []
    citations: list[AnswerCitation] = []
    for hit in hits[:_MAX_ANSWER_HITS]:
        snippet = _build_snippet(hit.text)
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
