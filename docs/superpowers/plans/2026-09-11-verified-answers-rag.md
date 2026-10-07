# Verified Answers RAG Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add opt-in Verified Answers that builds a cited evidence pack, verifies answer support, handles multi-hop and table-heavy questions, stores page-image/table metadata, and reports reliability metrics.

**Architecture:** Extend the existing search route instead of replacing it. New retrieval modules will split/rewrite questions, build deduplicated evidence packs from hybrid retrieval, generate extractive answers, and verify sentence support; document indexing will persist lightweight table/page-image metadata; the UI will expose a Verified Answers toggle and diagnostics.

**Tech Stack:** FastAPI, SQLAlchemy, pgvector, PyMuPDF, pytest, Next.js, React, TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-10-verified-answers-rag-design.md`

**Implementation Status:** Tasks 1-8 are implemented and locally verified. Task 9's local unit, route, UI, lint, compile, build, and whitespace checks passed. The full PostgreSQL-focused command remains pending because Docker/PostgreSQL were unavailable; see `docs/verified-answers.md` for the verification record and review decisions. PR notes are prepared in the local execution workspace; publishing remains pending.

## Global Constraints

- The user-facing feature name is **Verified Answers**.
- Do not add a user-facing alternate name for the strict answer mode.
- Keep current search behavior as the default with `answer_mode: "standard"`.
- Add opt-in strict behavior with `answer_mode: "verified"`.
- The app remains local-first and must work without model training, paid APIs, GPUs, or external vector stores.
- Optional LLM provider failure must fall back to deterministic local answer generation.
- Table extraction uncertainty must not fail indexing.
- Page-image metadata must prepare future visual retrieval without requiring eager image storage.
- Existing search, document, OCR, study, and evaluation APIs remain backward compatible.
- Use the existing `sync_local_schema` approach; do not introduce a migration framework.

---

## File Structure

- `apps/api/app/retrieval/multihop.py`: deterministic query rewrite and decomposition.
- `apps/api/app/retrieval/evidence_pack.py`: evidence item models, pack selection, dedupe, diversity, and rejected reasons.
- `apps/api/app/retrieval/verifier.py`: deterministic sentence-level support checks.
- `apps/api/app/retrieval/verified_answers.py`: orchestrates evidence pack, answer generation, verifier, and final quality response.
- `apps/api/app/retrieval/search.py`: request/response schema extensions.
- `apps/api/app/retrieval/router.py`: routes `answer_mode="verified"` into the new pipeline.
- `apps/api/app/documents/tables.py`: lightweight table detection and structured cell extraction.
- `apps/api/app/documents/page_rendering.py`: page-image metadata refresh helper.
- `apps/api/app/documents/service.py`: persists detected tables and initial page-image metadata during indexing/reindexing.
- `apps/api/app/db/models.py`: `PageImage`, `DocumentTable`, `DocumentTableCell` models and relationships.
- `apps/api/app/db/init_db.py`: local schema sync for new metadata tables/columns.
- `apps/api/app/evaluation/golden.py`: verified answer, table, multi-hop, and hallucination-risk golden cases.
- `apps/api/app/evaluation/metrics.py`: reliability metric helpers.
- `apps/web/lib/types.ts`: Verified Answers API types.
- `apps/web/lib/api.ts`: sends `answer_mode` and parses verified diagnostics.
- `apps/web/app/search/page.tsx`: **Verified Answers** toggle and request state.
- `apps/web/components/search-results.tsx`: evidence-pack and verifier diagnostics UI.
- `apps/web/app/evaluation/page.tsx`: broader Evaluation Lab copy.
- `apps/web/components/evaluation-summary.tsx`: verified reliability scorecard.

---

### Task 1: Multi-Hop Query Planning

**Files:**
- Create: `apps/api/app/retrieval/multihop.py`
- Test: `apps/api/tests/retrieval/test_multihop.py`

**Interfaces:**
- Produces: `rewrite_query(question: str) -> str`
- Produces: `split_subqueries(question: str) -> list[str]`
- Produces: `build_query_plan(question: str) -> QueryPlan`
- Produces: `QueryPlan(original_query: str, rewritten_query: str, subqueries: list[str], is_multi_hop: bool)`

- [x] **Step 1: Write failing tests for rewrite and decomposition**

```python
from app.retrieval.multihop import build_query_plan, rewrite_query, split_subqueries


def test_rewrite_query_removes_document_filler():
    assert rewrite_query("What does the document say about datasets?") == "datasets"


def test_split_subqueries_extracts_compound_facts():
    subqueries = split_subqueries(
        "How many total results were initially obtained from Scopus, and how many were consolidated after duplicate removal?"
    )

    assert subqueries == [
        "How many total results were initially obtained from Scopus?",
        "How many were consolidated after duplicate removal?",
    ]


def test_build_query_plan_marks_multi_hop_only_for_distinct_subqueries():
    simple = build_query_plan("What methods are used?")
    compound = build_query_plan("What methods are used and what results are reported?")

    assert simple.subqueries == ["methods"]
    assert simple.is_multi_hop is False
    assert compound.subqueries == ["What methods are used?", "what results are reported?"]
    assert compound.is_multi_hop is True
```

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest -q apps/api/tests/retrieval/test_multihop.py`

Expected: FAIL because `app.retrieval.multihop` does not exist.

- [x] **Step 3: Implement query planning**

Create `apps/api/app/retrieval/multihop.py`:

```python
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
    return cleaned.strip(" ?:;,.") or _clean_question(question)


def _with_question_mark(text: str) -> str:
    return text if text.endswith("?") else f"{text}?"


def split_subqueries(question: str) -> list[str]:
    cleaned = _clean_question(question)
    separators = [", and ", " and what ", " and how ", " and which ", ";"]
    for separator in separators:
        if separator in cleaned.lower():
            lowered = cleaned.lower()
            split_at = lowered.find(separator)
            first = cleaned[:split_at].strip(" ,;")
            second = cleaned[split_at + len(separator) :].strip(" ,;")
            if separator.startswith(" and what "):
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
```

- [x] **Step 4: Run tests to verify pass**

Run: `python -m pytest -q apps/api/tests/retrieval/test_multihop.py`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/api/app/retrieval/multihop.py apps/api/tests/retrieval/test_multihop.py
git commit -m "Add verified query planning"
```

---

### Task 2: Evidence Pack Builder

**Files:**
- Create: `apps/api/app/retrieval/evidence_pack.py`
- Test: `apps/api/tests/retrieval/test_evidence_pack.py`

**Interfaces:**
- Consumes: `SearchHit` from `app.retrieval.search`
- Consumes: `QueryPlan` from `app.retrieval.multihop`
- Produces: `EvidenceItem`
- Produces: `RejectedEvidence`
- Produces: `EvidencePack`
- Produces: `build_evidence_pack(question: str, hits_by_subquery: dict[str, list[SearchHit]], retrieval_mode: str, fallback_reason: str | None = None) -> EvidencePack`

- [x] **Step 1: Write failing tests for dedupe, diversity, and diagnostics**

```python
from app.retrieval.evidence_pack import build_evidence_pack
from app.retrieval.search import SearchHit


def make_hit(chunk_id: str, page: int, text: str, score: float = 0.8, heading: str | None = None) -> SearchHit:
    return SearchHit(
        chunk_id=chunk_id,
        document_id="doc-1",
        document_filename="paper.pdf",
        page_number=page,
        chunk_index=page,
        text=text,
        score=score,
        source_score=score,
        ranking_signals={"keyword_overlap": score},
        section_heading=heading,
    )


def test_evidence_pack_dedupes_chunks_and_preserves_subquery():
    hits = {
        "results": [
            make_hit("chunk-1", 3, "RESULTS The study reports 2366 Scopus results.", 0.95, "RESULTS"),
            make_hit("chunk-1", 3, "RESULTS The study reports 2366 Scopus results.", 0.90, "RESULTS"),
        ]
    }

    pack = build_evidence_pack("What results are reported?", hits, "hybrid")

    assert [item.chunk_id for item in pack.items] == ["chunk-1"]
    assert pack.items[0].subquery == "results"
    assert pack.selected_chunk_count == 1
    assert pack.rejected[0].reason == "Duplicate chunk already selected."


def test_evidence_pack_keeps_diverse_pages_before_lower_rank_same_page():
    hits = {
        "screening": [
            make_hit("chunk-1", 3, "Page three gives Scopus screening counts.", 0.95),
            make_hit("chunk-2", 3, "Another page three screening passage.", 0.92),
            make_hit("chunk-3", 5, "Page five gives full-text analysis counts.", 0.88),
        ]
    }

    pack = build_evidence_pack("How many results remained after screening?", hits, "hybrid", max_items=2)

    assert [item.chunk_id for item in pack.items] == ["chunk-1", "chunk-3"]
    assert pack.selected_page_count == 2
    assert any(rejected.chunk_id == "chunk-2" for rejected in pack.rejected)
```

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest -q apps/api/tests/retrieval/test_evidence_pack.py`

Expected: FAIL because `app.retrieval.evidence_pack` does not exist.

- [x] **Step 3: Implement evidence pack models and selection**

Create `apps/api/app/retrieval/evidence_pack.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from app.retrieval.search import SearchHit, build_snippet

EvidenceRetrievalMode = Literal["hybrid", "vector", "lexical"]


@dataclass(frozen=True)
class EvidenceItem:
    chunk_id: str
    document_id: str
    document_filename: str
    page_number: int
    chunk_index: int
    text: str
    snippet: str
    score: float
    source_score: float
    ranking_signals: dict[str, float]
    section_heading: str | None
    subquery: str
    support_score: float


@dataclass(frozen=True)
class RejectedEvidence:
    chunk_id: str
    page_number: int
    subquery: str
    reason: str


@dataclass(frozen=True)
class EvidencePack:
    question: str
    rewritten_query: str
    subqueries: list[str]
    items: list[EvidenceItem]
    rejected: list[RejectedEvidence] = field(default_factory=list)
    retrieval_mode: EvidenceRetrievalMode = "hybrid"
    retrieval_fallback_reason: str | None = None
    selected_chunk_count: int = 0
    selected_page_count: int = 0
    average_support_score: float = 0.0
    is_multi_hop: bool = False


def _support_score(hit: SearchHit) -> float:
    keyword = hit.ranking_signals.get("keyword_overlap", 0.0)
    section = hit.ranking_signals.get("section_intent", 0.0)
    return round(max(hit.score, hit.source_score, keyword, section), 6)


def _item_from_hit(hit: SearchHit, subquery: str) -> EvidenceItem:
    return EvidenceItem(
        chunk_id=hit.chunk_id,
        document_id=hit.document_id,
        document_filename=hit.document_filename,
        page_number=hit.page_number,
        chunk_index=hit.chunk_index,
        text=hit.text,
        snippet=build_snippet(hit.text),
        score=hit.score,
        source_score=hit.source_score,
        ranking_signals=dict(hit.ranking_signals),
        section_heading=hit.section_heading,
        subquery=subquery,
        support_score=_support_score(hit),
    )


def build_evidence_pack(
    question: str,
    hits_by_subquery: dict[str, list[SearchHit]],
    retrieval_mode: EvidenceRetrievalMode,
    fallback_reason: str | None = None,
    *,
    rewritten_query: str | None = None,
    is_multi_hop: bool = False,
    max_items: int = 5,
) -> EvidencePack:
    selected: list[EvidenceItem] = []
    rejected: list[RejectedEvidence] = []
    seen_chunks: set[str] = set()
    used_pages: set[int] = set()
    ranked_candidates: list[tuple[str, SearchHit]] = []
    for subquery, hits in hits_by_subquery.items():
        ranked_candidates.extend((subquery, hit) for hit in hits)

    ranked_candidates.sort(key=lambda pair: (pair[1].score, pair[1].source_score), reverse=True)

    deferred_same_page: list[tuple[str, SearchHit]] = []
    for subquery, hit in ranked_candidates:
        if hit.chunk_id in seen_chunks:
            rejected.append(RejectedEvidence(hit.chunk_id, hit.page_number, subquery, "Duplicate chunk already selected."))
            continue
        if len(selected) >= max_items:
            rejected.append(RejectedEvidence(hit.chunk_id, hit.page_number, subquery, "Evidence pack context limit reached."))
            continue
        if hit.page_number in used_pages and len(selected) + len(deferred_same_page) < len(ranked_candidates):
            deferred_same_page.append((subquery, hit))
            continue
        selected.append(_item_from_hit(hit, subquery))
        seen_chunks.add(hit.chunk_id)
        used_pages.add(hit.page_number)

    for subquery, hit in deferred_same_page:
        if len(selected) >= max_items:
            rejected.append(RejectedEvidence(hit.chunk_id, hit.page_number, subquery, "Lower priority evidence from an already selected page."))
            continue
        if hit.chunk_id in seen_chunks:
            rejected.append(RejectedEvidence(hit.chunk_id, hit.page_number, subquery, "Duplicate chunk already selected."))
            continue
        selected.append(_item_from_hit(hit, subquery))
        seen_chunks.add(hit.chunk_id)
        used_pages.add(hit.page_number)

    average = sum(item.support_score for item in selected) / len(selected) if selected else 0.0
    return EvidencePack(
        question=question,
        rewritten_query=rewritten_query or question,
        subqueries=list(hits_by_subquery.keys()),
        items=selected,
        rejected=rejected[:5],
        retrieval_mode=retrieval_mode,
        retrieval_fallback_reason=fallback_reason,
        selected_chunk_count=len(selected),
        selected_page_count=len({item.page_number for item in selected}),
        average_support_score=round(average, 6),
        is_multi_hop=is_multi_hop,
    )
```

- [x] **Step 4: Run tests to verify pass**

Run: `python -m pytest -q apps/api/tests/retrieval/test_evidence_pack.py`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/api/app/retrieval/evidence_pack.py apps/api/tests/retrieval/test_evidence_pack.py
git commit -m "Add evidence pack builder"
```

---

### Task 3: Evidence Verifier

**Files:**
- Create: `apps/api/app/retrieval/verifier.py`
- Test: `apps/api/tests/retrieval/test_verifier.py`

**Interfaces:**
- Consumes: `EvidencePack`, `EvidenceItem`
- Produces: `SentenceSupport`
- Produces: `VerificationResult`
- Produces: `verify_answer(answer: str, evidence_pack: EvidencePack) -> VerificationResult`
- Produces: `filter_supported_answer(answer: str, evidence_pack: EvidencePack) -> tuple[str, VerificationResult]`

- [x] **Step 1: Write failing tests for supported and unsupported claims**

```python
from app.retrieval.evidence_pack import EvidenceItem, EvidencePack
from app.retrieval.verifier import filter_supported_answer, verify_answer


def make_pack() -> EvidencePack:
    item = EvidenceItem(
        chunk_id="chunk-1",
        document_id="doc-1",
        document_filename="paper.pdf",
        page_number=3,
        chunk_index=1,
        text="From Scopus, 2366 results were obtained, including 1180 papers and 1351 conference proceedings.",
        snippet="From Scopus, 2366 results were obtained.",
        score=0.95,
        source_score=0.95,
        ranking_signals={},
        section_heading="RESULTS",
        subquery="screening counts",
        support_score=0.95,
    )
    return EvidencePack(
        question="How many Scopus results were obtained?",
        rewritten_query="Scopus results",
        subqueries=["Scopus results"],
        items=[item],
        selected_chunk_count=1,
        selected_page_count=1,
        average_support_score=0.95,
    )


def test_verify_answer_accepts_supported_numbers():
    result = verify_answer("The study obtained 2366 Scopus results.", make_pack())

    assert result.status == "verified"
    assert result.hallucination_risk == 0.0
    assert result.sentences[0].supporting_chunk_ids == ["chunk-1"]


def test_verify_answer_rejects_unsupported_numbers():
    result = verify_answer("The study obtained 5000 Scopus results.", make_pack())

    assert result.status == "unsupported"
    assert result.unsupported_sentence_count == 1
    assert result.hallucination_risk == 1.0


def test_filter_supported_answer_removes_unsupported_sentence():
    answer, result = filter_supported_answer(
        "The study obtained 2366 Scopus results. It used a private GPU cluster.",
        make_pack(),
    )

    assert answer == "The study obtained 2366 Scopus results."
    assert result.status == "partially_supported"
    assert result.removed_sentence_count == 1
```

- [x] **Step 2: Run tests to verify failure**

Run: `python -m pytest -q apps/api/tests/retrieval/test_verifier.py`

Expected: FAIL because `app.retrieval.verifier` does not exist.

- [x] **Step 3: Implement verifier**

Create `apps/api/app/retrieval/verifier.py`:

```python
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Literal

from app.retrieval.evidence_pack import EvidenceItem, EvidencePack

VerificationStatus = Literal["verified", "partially_supported", "unsupported"]
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+")
_WORD_PATTERN = re.compile(r"[a-z0-9]+")
_NUMBER_PATTERN = re.compile(r"\b\d[\d,]*(?:\.\d+)?%?\b")
_STOPWORDS = {
    "a", "an", "and", "are", "as", "from", "in", "is", "it", "of", "on", "or",
    "the", "this", "to", "used", "were", "was", "with",
}


@dataclass(frozen=True)
class SentenceSupport:
    sentence: str
    status: VerificationStatus
    supporting_chunk_ids: list[str]
    support_score: float
    missing_terms: list[str]
    missing_numbers: list[str]


@dataclass(frozen=True)
class VerificationResult:
    status: VerificationStatus
    sentences: list[SentenceSupport]
    unsupported_sentence_count: int
    removed_sentence_count: int
    hallucination_risk: float
    reason: str


def _sentences(answer: str) -> list[str]:
    return [sentence.strip() for sentence in _SENTENCE_BOUNDARY.split(answer.strip()) if sentence.strip()]


def _words(text: str) -> set[str]:
    return {word for word in _WORD_PATTERN.findall(text.lower()) if word not in _STOPWORDS and len(word) > 1}


def _numbers(text: str) -> set[str]:
    return {number.replace(",", "") for number in _NUMBER_PATTERN.findall(text)}


def _support_sentence(sentence: str, items: list[EvidenceItem]) -> SentenceSupport:
    sentence_words = _words(sentence)
    sentence_numbers = _numbers(sentence)
    best_item: EvidenceItem | None = None
    best_overlap = 0.0
    missing_terms: list[str] = []
    missing_numbers: list[str] = []
    for item in items:
        evidence_text = item.text.lower()
        evidence_words = _words(evidence_text)
        overlap = len(sentence_words.intersection(evidence_words)) / len(sentence_words) if sentence_words else 0.0
        if overlap > best_overlap:
            best_overlap = overlap
            best_item = item

    if best_item is None:
        return SentenceSupport(sentence, "unsupported", [], 0.0, sorted(sentence_words), sorted(sentence_numbers))

    best_text = best_item.text.lower()
    missing_numbers = sorted(number for number in sentence_numbers if number not in _numbers(best_text))
    missing_terms = sorted(word for word in sentence_words if word not in _words(best_text))[:8]
    is_supported = best_overlap >= 0.45 and not missing_numbers
    status: VerificationStatus = "verified" if is_supported else "unsupported"
    return SentenceSupport(
        sentence=sentence,
        status=status,
        supporting_chunk_ids=[best_item.chunk_id] if is_supported else [],
        support_score=round(best_overlap, 6),
        missing_terms=[] if is_supported else missing_terms,
        missing_numbers=missing_numbers,
    )


def verify_answer(answer: str, evidence_pack: EvidencePack) -> VerificationResult:
    supports = [_support_sentence(sentence, evidence_pack.items) for sentence in _sentences(answer)]
    unsupported_count = sum(1 for support in supports if support.status == "unsupported")
    if not supports or unsupported_count == len(supports):
        status: VerificationStatus = "unsupported"
    elif unsupported_count:
        status = "partially_supported"
    else:
        status = "verified"
    risk = unsupported_count / len(supports) if supports else 1.0
    return VerificationResult(
        status=status,
        sentences=supports,
        unsupported_sentence_count=unsupported_count,
        removed_sentence_count=0,
        hallucination_risk=round(risk, 6),
        reason=(
            "Every answer sentence is supported by selected evidence."
            if status == "verified"
            else "Some answer sentences lack selected evidence support."
        ),
    )


def filter_supported_answer(answer: str, evidence_pack: EvidencePack) -> tuple[str, VerificationResult]:
    result = verify_answer(answer, evidence_pack)
    supported = [sentence.sentence for sentence in result.sentences if sentence.status == "verified"]
    filtered_answer = " ".join(supported)
    removed = len(result.sentences) - len(supported)
    status: VerificationStatus
    if supported and removed:
        status = "partially_supported"
    elif supported:
        status = "verified"
    else:
        status = "unsupported"
    return filtered_answer, replace(
        result,
        status=status,
        removed_sentence_count=removed,
        reason=(
            "Unsupported answer sentences were removed."
            if removed and supported
            else result.reason
        ),
    )
```

- [x] **Step 4: Run tests to verify pass**

Run: `python -m pytest -q apps/api/tests/retrieval/test_verifier.py`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/api/app/retrieval/verifier.py apps/api/tests/retrieval/test_verifier.py
git commit -m "Add evidence verifier"
```

---

### Task 4: Verified Answer Pipeline

**Files:**
- Create: `apps/api/app/retrieval/verified_answers.py`
- Modify: `apps/api/app/retrieval/search.py`
- Modify: `apps/api/app/retrieval/router.py`
- Test: `apps/api/tests/retrieval/test_verified_answers.py`
- Modify: `apps/api/tests/retrieval/test_search_api.py`

**Interfaces:**
- Consumes: `build_query_plan(question: str) -> QueryPlan`
- Consumes: `build_evidence_pack(question: str, hits_by_subquery: dict[str, list[SearchHit]], retrieval_mode: EvidenceRetrievalMode, fallback_reason: str | None = None, *, rewritten_query: str | None = None, is_multi_hop: bool = False, max_items: int = 5) -> EvidencePack`
- Consumes: `filter_supported_answer(answer: str, evidence_pack: EvidencePack)`
- Produces: `build_verified_answer(query: str, evidence_pack: EvidencePack) -> VerifiedAnswerResult`
- Produces: `SearchRequest.answer_mode: Literal["standard", "verified"] = "standard"`
- Produces: `SearchResponse.answer_mode: Literal["standard", "verified"]`
- Produces: `SearchResponse.evidence_pack`
- Produces: `SearchResponse.verification`

- [x] **Step 1: Write failing unit tests for verified answer behavior**

```python
from app.retrieval.evidence_pack import EvidenceItem, EvidencePack
from app.retrieval.verified_answers import build_verified_answer


def test_build_verified_answer_returns_cited_answer_when_supported():
    item = EvidenceItem(
        chunk_id="chunk-1",
        document_id="doc-1",
        document_filename="paper.pdf",
        page_number=3,
        chunk_index=1,
        text="The three screening stages were database harmonization, title and abstract screening, and full-text analysis.",
        snippet="The three screening stages were database harmonization, title and abstract screening, and full-text analysis.",
        score=0.9,
        source_score=0.9,
        ranking_signals={},
        section_heading="RESULTS",
        subquery="screening stages",
        support_score=0.9,
    )
    pack = EvidencePack(
        question="What were the three screening stages?",
        rewritten_query="screening stages",
        subqueries=["screening stages"],
        items=[item],
        selected_chunk_count=1,
        selected_page_count=1,
        average_support_score=0.9,
    )

    result = build_verified_answer("What were the three screening stages?", pack)

    assert result.answer is not None
    assert result.quality.status == "answerable"
    assert result.verification.status == "verified"
    assert result.answer.citations[0].chunk_id == "chunk-1"


def test_build_verified_answer_abstains_without_evidence():
    pack = EvidencePack("What is the total due?", "total due", ["total due"], [])

    result = build_verified_answer("What is the total due?", pack)

    assert result.answer is None
    assert result.quality.status == "insufficient_evidence"
    assert result.verification.status == "unsupported"
```

- [x] **Step 2: Write failing router test for opt-in mode**

```python
def test_search_request_accepts_verified_answer_mode():
    from app.retrieval.search import SearchRequest

    request = SearchRequest(query="What methods are used?", answer_mode="verified")

    assert request.answer_mode == "verified"
```

- [x] **Step 3: Run tests to verify failure**

Run: `python -m pytest -q apps/api/tests/retrieval/test_verified_answers.py apps/api/tests/retrieval/test_search_api.py -k verified`

Expected: FAIL because verified schemas and pipeline do not exist.

- [x] **Step 4: Add read models to search schemas**

Modify `apps/api/app/retrieval/search.py` to add:

```python
AnswerMode = Literal["standard", "verified"]


class EvidenceItemRead(BaseModel):
    chunk_id: str
    document_id: str
    document_filename: str
    page_number: int
    chunk_index: int
    snippet: str
    score: float
    source_score: float
    ranking_signals: dict[str, float]
    section_heading: str | None = None
    subquery: str
    support_score: float


class RejectedEvidenceRead(BaseModel):
    chunk_id: str
    page_number: int
    subquery: str
    reason: str


class EvidencePackRead(BaseModel):
    question: str
    rewritten_query: str
    subqueries: list[str]
    items: list[EvidenceItemRead]
    rejected: list[RejectedEvidenceRead]
    retrieval_mode: Literal["hybrid", "vector", "lexical"]
    retrieval_fallback_reason: str | None = None
    selected_chunk_count: int
    selected_page_count: int
    average_support_score: float
    is_multi_hop: bool


class SentenceSupportRead(BaseModel):
    sentence: str
    status: Literal["verified", "partially_supported", "unsupported"]
    supporting_chunk_ids: list[str]
    support_score: float
    missing_terms: list[str]
    missing_numbers: list[str]


class EvidenceVerificationRead(BaseModel):
    status: Literal["verified", "partially_supported", "unsupported"]
    sentences: list[SentenceSupportRead]
    unsupported_sentence_count: int
    removed_sentence_count: int
    hallucination_risk: float
    reason: str
```

Also add `answer_mode: AnswerMode = "standard"` to `SearchRequest`, and add `answer_mode`, `evidence_pack`, and `verification` to `SearchResponse`.

- [x] **Step 5: Implement verified answer orchestration**

Create `apps/api/app/retrieval/verified_answers.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

from app.retrieval.answers import AnswerCitation, AnswerQuality, ExtractiveAnswer
from app.retrieval.evidence_pack import EvidencePack
from app.retrieval.verifier import VerificationResult, filter_supported_answer, verify_answer


@dataclass(frozen=True)
class VerifiedAnswerResult:
    answer: ExtractiveAnswer | None
    quality: AnswerQuality
    verification: VerificationResult


def _quality(status: str, reason: str, evidence_count: int, support: float) -> AnswerQuality:
    return AnswerQuality(
        status="answerable" if status == "answerable" else "insufficient_evidence",
        confidence="strong" if support >= 0.75 else "moderate" if support >= 0.45 else "weak",
        reason=reason,
        evidence_count=evidence_count,
        best_score=support,
        best_source_score=support,
        best_keyword_overlap=support,
        best_section_intent=0.0,
        suggested_questions=[],
    )


def _draft_answer(pack: EvidencePack) -> str:
    snippets = [item.snippet for item in pack.items[:3] if item.snippet]
    return " ".join(snippets)


def build_verified_answer(query: str, evidence_pack: EvidencePack) -> VerifiedAnswerResult:
    if not evidence_pack.items:
        verification = verify_answer("", evidence_pack)
        return VerifiedAnswerResult(
            answer=None,
            quality=_quality("insufficient_evidence", "Verified Answers could not find enough cited evidence.", 0, 0.0),
            verification=verification,
        )

    draft = _draft_answer(evidence_pack)
    filtered, verification = filter_supported_answer(draft, evidence_pack)
    if not filtered or verification.status == "unsupported":
        return VerifiedAnswerResult(
            answer=None,
            quality=_quality(
                "insufficient_evidence",
                "Verified Answers removed unsupported claims and no supported answer remained.",
                0,
                evidence_pack.average_support_score,
            ),
            verification=verification,
        )

    citations = [
        AnswerCitation(
            chunk_id=item.chunk_id,
            document_filename=item.document_filename,
            page_number=item.page_number,
            section_heading=item.section_heading,
        )
        for item in evidence_pack.items
        if item.chunk_id in {chunk_id for sentence in verification.sentences for chunk_id in sentence.supporting_chunk_ids}
    ]
    return VerifiedAnswerResult(
        answer=ExtractiveAnswer(summary=filtered, citations=citations),
        quality=_quality(
            "answerable",
            "Verified Answers built the answer from selected cited evidence.",
            len(citations),
            evidence_pack.average_support_score,
        ),
        verification=verification,
    )
```

- [x] **Step 6: Route verified requests through the new pipeline**

Modify `apps/api/app/retrieval/router.py`:

```python
from app.retrieval.evidence_pack import EvidencePack, build_evidence_pack
from app.retrieval.multihop import build_query_plan
from app.retrieval.verified_answers import build_verified_answer
from app.retrieval.verifier import VerificationResult


def _read_evidence_pack(pack: EvidencePack) -> EvidencePackRead:
    return EvidencePackRead(
        question=pack.question,
        rewritten_query=pack.rewritten_query,
        subqueries=pack.subqueries,
        items=[
            EvidenceItemRead(
                chunk_id=item.chunk_id,
                document_id=item.document_id,
                document_filename=item.document_filename,
                page_number=item.page_number,
                chunk_index=item.chunk_index,
                snippet=item.snippet,
                score=item.score,
                source_score=item.source_score,
                ranking_signals=item.ranking_signals,
                section_heading=item.section_heading,
                subquery=item.subquery,
                support_score=item.support_score,
            )
            for item in pack.items
        ],
        rejected=[
            RejectedEvidenceRead(
                chunk_id=item.chunk_id,
                page_number=item.page_number,
                subquery=item.subquery,
                reason=item.reason,
            )
            for item in pack.rejected
        ],
        retrieval_mode=pack.retrieval_mode,
        retrieval_fallback_reason=pack.retrieval_fallback_reason,
        selected_chunk_count=pack.selected_chunk_count,
        selected_page_count=pack.selected_page_count,
        average_support_score=pack.average_support_score,
        is_multi_hop=pack.is_multi_hop,
    )


def _read_verification(result: VerificationResult) -> EvidenceVerificationRead:
    return EvidenceVerificationRead(
        status=result.status,
        sentences=[
            SentenceSupportRead(
                sentence=sentence.sentence,
                status=sentence.status,
                supporting_chunk_ids=sentence.supporting_chunk_ids,
                support_score=sentence.support_score,
                missing_terms=sentence.missing_terms,
                missing_numbers=sentence.missing_numbers,
            )
            for sentence in result.sentences
        ],
        unsupported_sentence_count=result.unsupported_sentence_count,
        removed_sentence_count=result.removed_sentence_count,
        hallucination_risk=result.hallucination_risk,
        reason=result.reason,
    )
```

Inside `search`, after query embedding:

```python
plan = build_query_plan(request.query)
if request.answer_mode == "verified":
    hits_by_subquery: dict[str, list[SearchHit]] = {}
    retrieval_modes: list[str] = []
    fallback_reason = embedding_failure_reason
    for subquery in plan.subqueries:
        candidates, mode = hybrid_search_chunks(
            db,
            query_embedding,
            subquery,
            candidate_limit,
            request.document_id,
            vector_search=search_chunks,
            fallback_reason=embedding_failure_reason,
        )
        hits_by_subquery[subquery] = rerank_hits(subquery, candidates)[: request.top_k]
        retrieval_modes.append(mode.mode)
        fallback_reason = fallback_reason or mode.fallback_reason
    pack_mode = "hybrid" if "hybrid" in retrieval_modes else "vector" if "vector" in retrieval_modes else "lexical"
    pack = build_evidence_pack(
        request.query,
        hits_by_subquery,
        pack_mode,
        fallback_reason,
        rewritten_query=plan.rewritten_query,
        is_multi_hop=plan.is_multi_hop,
    )
    verified = build_verified_answer(request.query, pack)
    answer_chunk_ids = [citation.chunk_id for citation in verified.answer.citations] if verified.answer is not None else []
    answer_chunk_id_set = set(answer_chunk_ids)
    display_hits = _augment_hits_with_answer_evidence(hits_by_subquery[plan.subqueries[0]], document, answer_chunk_ids)
    diagnostics = _build_search_diagnostics(
        hits=display_hits,
        answer_chunk_ids=answer_chunk_ids,
        quality_status=verified.quality.status,
        confidence=verified.quality.confidence,
        reason=verified.quality.reason,
        document_type=profile.document_type if profile is not None else None,
        query_intent=route.intent,
    )
    return SearchResponse(
        query=request.query,
        hits=[format_search_hit(hit, answer_chunk_id_set) for hit in display_hits],
        answer=verified.answer,
        quality=verified.quality,
        document_type=profile.document_type if profile is not None else None,
        query_intent=route.intent,
        diagnostics=diagnostics,
        retrieval_mode=pack.retrieval_mode,
        retrieval_fallback_reason=pack.retrieval_fallback_reason,
        answer_mode="verified",
        evidence_pack=_read_evidence_pack(pack),
        verification=_read_verification(verified.verification),
    )
```

Keep the existing standard branch unchanged except for `answer_mode="standard"`.

- [x] **Step 7: Run tests to verify pass**

Run: `python -m pytest -q apps/api/tests/retrieval/test_verified_answers.py apps/api/tests/retrieval/test_search_api.py -k verified`

Expected: PASS.

- [x] **Step 8: Commit**

```bash
git add apps/api/app/retrieval apps/api/tests/retrieval/test_verified_answers.py apps/api/tests/retrieval/test_search_api.py
git commit -m "Add verified answer search pipeline"
```

---

### Task 5: Table-Aware Extraction And Page Image Metadata

**Files:**
- Modify: `apps/api/app/db/models.py`
- Modify: `apps/api/app/db/init_db.py`
- Create: `apps/api/app/documents/tables.py`
- Modify: `apps/api/app/documents/page_rendering.py`
- Modify: `apps/api/app/documents/service.py`
- Modify: `apps/api/tests/db/test_models.py`
- Modify: `apps/api/tests/db/test_init_db.py`
- Create: `apps/api/tests/documents/test_tables.py`
- Modify: `apps/api/tests/documents/test_service.py`

**Interfaces:**
- Produces: `PageImage`
- Produces: `DocumentTable`
- Produces: `DocumentTableCell`
- Produces: `detect_tables(pages: list[ExtractedPage]) -> list[DetectedTable]`
- Produces: `refresh_page_image_metadata(db: Session, document: Document, page_number: int, storage_dir: Path | None) -> PageImage | None`

- [x] **Step 1: Write failing model and schema sync tests**

```python
from app.db.models import DocumentTable, DocumentTableCell, PageImage


def test_page_image_columns_are_declared():
    columns = PageImage.__table__.columns

    assert PageImage.__tablename__ == "page_images"
    assert columns["document_id"].nullable is False
    assert columns["page_id"].nullable is False
    assert columns["page_number"].nullable is False
    assert columns["render_dpi"].nullable is False
    assert columns["media_type"].nullable is False


def test_document_table_columns_are_declared():
    columns = DocumentTable.__table__.columns

    assert DocumentTable.__tablename__ == "document_tables"
    assert columns["document_id"].nullable is False
    assert columns["page_id"].nullable is False
    assert columns["source_chunk_id"].nullable is True
    assert columns["extraction_confidence"].nullable is False


def test_document_table_cell_columns_are_declared():
    columns = DocumentTableCell.__table__.columns

    assert DocumentTableCell.__tablename__ == "document_table_cells"
    assert columns["table_id"].nullable is False
    assert columns["row_index"].nullable is False
    assert columns["column_label"].nullable is True
    assert columns["text"].nullable is False
```

- [x] **Step 2: Write failing table detection test**

```python
from app.documents.extraction import ExtractedPage
from app.documents.tables import detect_tables


def test_detect_tables_extracts_rows_and_cells_from_text_table():
    page = ExtractedPage(
        page_number=10,
        text=(
            "Table 4 Key literature review\n"
            "Reference Year Task planning Environmental perception Embodied execution\n"
            "Chen et al. 2026 √ √ √\n"
            "Lou et al. 2025 √  √\n"
        ),
        width=612,
        height=792,
        text_source="native",
    )

    tables = detect_tables([page])

    assert len(tables) == 1
    assert tables[0].caption == "Table 4 Key literature review"
    assert tables[0].page_number == 10
    assert tables[0].rows[0].cells[0].text == "Chen et al."
    assert any(cell.text == "2026" for cell in tables[0].rows[0].cells)
```

- [x] **Step 3: Run tests to verify failure**

Run: `python -m pytest -q apps/api/tests/db/test_models.py apps/api/tests/db/test_init_db.py apps/api/tests/documents/test_tables.py`

Expected: FAIL because models and table detector do not exist.

- [x] **Step 4: Add models and schema sync**

Modify `apps/api/app/db/models.py` with relationships and models:

```python
class PageImage(Base):
    __tablename__ = "page_images"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    render_dpi: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[float | None]
    height: Mapped[float | None]
    media_type: Mapped[str] = mapped_column(String(100), nullable=False, default="image/png")
    checksum: Mapped[str | None] = mapped_column(String(128))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)


class DocumentTable(Base):
    __tablename__ = "document_tables"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    source_chunk_id: Mapped[str | None] = mapped_column(ForeignKey("chunks.id", ondelete="SET NULL"))
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    table_index: Mapped[int] = mapped_column(Integer, nullable=False)
    caption: Mapped[str | None] = mapped_column(Text)
    extraction_confidence: Mapped[str] = mapped_column(String(20), nullable=False, default="low")
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    column_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    metadata_: Mapped[dict[str, Any]] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)


class DocumentTableCell(Base):
    __tablename__ = "document_table_cells"
    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    table_id: Mapped[str] = mapped_column(ForeignKey("document_tables.id", ondelete="CASCADE"), nullable=False)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    source_chunk_id: Mapped[str | None] = mapped_column(ForeignKey("chunks.id", ondelete="SET NULL"))
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    column_index: Mapped[int] = mapped_column(Integer, nullable=False)
    column_label: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
```

Add `page_images`, `document_tables`, and `document_table_cells` relationships to `Document` and `Page`. Add a `cells` relationship to `DocumentTable`. Update `sync_local_schema` to rely on `Base.metadata.create_all` for new tables and keep the existing column-add behavior for older local databases.

- [x] **Step 5: Implement table detector**

Create `apps/api/app/documents/tables.py` with dataclasses `DetectedTable`, `DetectedTableRow`, `DetectedTableCell` and a heuristic detector:

```python
def detect_tables(pages: list[ExtractedPage]) -> list[DetectedTable]:
    tables = []
    for page in pages:
        lines = [line.strip() for line in page.text.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if line.lower().startswith("table "):
                body = lines[index + 1 : index + 6]
                rows = [_parse_table_row(row_index, row) for row_index, row in enumerate(body) if _is_table_row(row)]
                if rows:
                    tables.append(DetectedTable(page.page_number, line, rows, "moderate"))
    return tables
```

Use regex token grouping so row text such as `Chen et al. 2026 √ √ √` becomes cells `Chen et al.`, `2026`, `√`, `√`, `√`.

- [x] **Step 6: Persist table records and initial page-image metadata**

Modify `_add_index_records_from_pages` in `apps/api/app/documents/service.py` after chunks are flushed:

```python
def _first_chunk_for_page(chunks: list[Chunk], page_number: int) -> Chunk | None:
    return next((chunk for chunk in chunks if chunk.page.page_number == page_number), None)


db.add_all(
    PageImage(
        document_id=document.id,
        page_id=page_models[extracted_page.page_number].id,
        page_number=extracted_page.page_number,
        render_dpi=PAGE_PREVIEW_DPI,
        width=extracted_page.width,
        height=extracted_page.height,
        media_type="image/png",
    )
    for extracted_page in extracted_pages
)

detected_tables = detect_tables(extracted_pages)
for table_index, detected in enumerate(detected_tables):
    page = page_models[detected.page_number]
    source_chunk = _first_chunk_for_page(chunks, detected.page_number)
    table = DocumentTable(
        document_id=document.id,
        page_id=page.id,
        source_chunk_id=source_chunk.id if source_chunk is not None else None,
        page_number=detected.page_number,
        table_index=table_index,
        caption=detected.caption,
        extraction_confidence=detected.extraction_confidence,
        row_count=len(detected.rows),
        column_count=max((len(row.cells) for row in detected.rows), default=0),
        metadata_={"detector": "native-text-heuristic"},
    )
    db.add(table)
    db.flush()
    cells = [
        DocumentTableCell(
            table_id=table.id,
            document_id=document.id,
            page_id=page.id,
            source_chunk_id=source_chunk.id if source_chunk is not None else None,
            page_number=detected.page_number,
            row_index=row.row_index,
            column_index=cell.column_index,
            column_label=cell.column_label,
            text=cell.text,
        )
        for row in detected.rows
        for cell in row.cells
        if cell.text
    ]
    db.add_all(cells)
```

Also add one `PageImage` metadata row per page using native page width/height and `PAGE_PREVIEW_DPI`.

- [x] **Step 7: Run tests to verify pass**

Run: `python -m pytest -q apps/api/tests/db/test_models.py apps/api/tests/db/test_init_db.py apps/api/tests/documents/test_tables.py`

Expected: PASS.

- [x] **Step 8: Commit**

```bash
git add apps/api/app/db apps/api/app/documents apps/api/tests/db apps/api/tests/documents/test_tables.py apps/api/tests/documents/test_service.py
git commit -m "Add table and page image metadata"
```

---

### Task 6: Verified Evaluation Lab Metrics

**Files:**
- Modify: `apps/api/app/evaluation/metrics.py`
- Modify: `apps/api/app/evaluation/golden.py`
- Modify: `apps/api/tests/evaluation/test_metrics.py`
- Modify: `apps/api/tests/evaluation/test_golden_eval.py`

**Interfaces:**
- Consumes: `build_verified_answer`
- Produces: `citation_accuracy(expected_chunk_ids: list[str], cited_chunk_ids: list[str]) -> float`
- Produces: `abstention_safety(expected_status: str, actual_status: str) -> float`
- Produces: golden quality dimensions `verified_answers`, `citation_accuracy`, `table_qa`, `multi_hop_qa`, `hallucination_risk`

- [x] **Step 1: Write failing metric tests**

```python
from app.evaluation.metrics import abstention_safety, citation_accuracy, hallucination_risk_score


def test_citation_accuracy_scores_expected_citations():
    assert citation_accuracy(["a", "b"], ["a", "c"]) == 0.5
    assert citation_accuracy(["a"], ["a"]) == 1.0


def test_abstention_safety_rewards_expected_abstention():
    assert abstention_safety("insufficient_evidence", "insufficient_evidence") == 1.0
    assert abstention_safety("insufficient_evidence", "answerable") == 0.0


def test_hallucination_risk_score_clamps_range():
    assert hallucination_risk_score(unsupported_sentences=1, total_sentences=4) == 0.25
    assert hallucination_risk_score(unsupported_sentences=0, total_sentences=0) == 1.0
```

- [x] **Step 2: Write failing golden eval tests**

```python
from app.evaluation.golden import run_golden_evaluation


def test_golden_eval_reports_verified_dimensions():
    response = run_golden_evaluation()

    assert "verified_answers" in response.summary.quality_dimensions
    assert "table_qa" in response.summary.quality_dimensions
    assert "multi_hop_qa" in response.summary.quality_dimensions
    assert response.summary.quality_dimensions["hallucination_risk"] >= 1
```

- [x] **Step 3: Run tests to verify failure**

Run: `python -m pytest -q apps/api/tests/evaluation/test_metrics.py apps/api/tests/evaluation/test_golden_eval.py`

Expected: FAIL because metrics/dimensions do not exist.

- [x] **Step 4: Implement metric helpers**

Modify `apps/api/app/evaluation/metrics.py`:

```python
def citation_accuracy(expected_chunk_ids: list[str], cited_chunk_ids: list[str]) -> float:
    expected = set(expected_chunk_ids)
    if not expected:
        return 1.0 if not cited_chunk_ids else 0.0
    return len(expected.intersection(cited_chunk_ids)) / len(expected)


def abstention_safety(expected_status: str, actual_status: str) -> float:
    if expected_status != "insufficient_evidence":
        return 1.0
    return 1.0 if actual_status == "insufficient_evidence" else 0.0


def hallucination_risk_score(unsupported_sentences: int, total_sentences: int) -> float:
    if total_sentences <= 0:
        return 1.0
    return max(0.0, min(1.0, unsupported_sentences / total_sentences))
```

- [x] **Step 5: Add verified golden cases**

Modify `apps/api/app/evaluation/golden.py` so synthetic documents include a table-like chunk and cases include:

```python
GoldenCaseSpec(
    "research-table-reference-2026",
    "research",
    "Which 2026 reference includes check marks for task planning, environmental perception, and embodied execution?",
    "answerable",
    ("Chen et al.", "2026"),
    "results",
    "table_qa",
)
```

Route selected golden cases through `build_verified_answer` using a hand-built evidence pack so the verifier and hallucination risk are exercised locally.

- [x] **Step 6: Run tests to verify pass**

Run: `python -m pytest -q apps/api/tests/evaluation/test_metrics.py apps/api/tests/evaluation/test_golden_eval.py`

Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add apps/api/app/evaluation apps/api/tests/evaluation
git commit -m "Expand verified answer evaluation"
```

---

### Task 7: Frontend Verified Answers Search UI

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/search/page.tsx`
- Modify: `apps/web/components/search-results.tsx`
- Modify: `apps/web/tests/api-client.test.ts`
- Modify: `apps/web/tests/search-page.test.tsx`
- Modify: `apps/web/tests/search-results.test.tsx`

**Interfaces:**
- Consumes: `SearchRequest.answer_mode`
- Consumes: `SearchResponse.evidence_pack`
- Consumes: `SearchResponse.verification`
- Produces: `searchDocuments(query: string, topK?: number, documentId?: string, answerMode?: AnswerMode)`
- Produces: **Verified Answers** toggle in Search page
- Produces: evidence-pack and verifier diagnostics in Search results

- [x] **Step 1: Write failing API client test**

```typescript
it("sends verified answer mode when requested", async () => {
  const fetchMock = vi.spyOn(global, "fetch").mockResolvedValueOnce(
    new Response(JSON.stringify({ query: "q", hits: [], answer: null, quality: baseQuality, answer_mode: "verified" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );

  await searchDocuments("q", 5, "doc-1", "verified");

  expect(JSON.parse(fetchMock.mock.calls[0][1]?.body as string)).toMatchObject({
    query: "q",
    top_k: 5,
    document_id: "doc-1",
    answer_mode: "verified",
  });
});
```

- [x] **Step 2: Write failing UI tests**

```typescript
it("toggles Verified Answers before searching", async () => {
  render(<SearchPage />);

  await userEvent.click(screen.getByRole("switch", { name: /verified answers/i }));
  await userEvent.type(screen.getByLabelText(/search query/i), "What results are reported?");
  await userEvent.click(screen.getByRole("button", { name: /search/i }));

  expect(searchDocumentsMock).toHaveBeenCalledWith("What results are reported?", 5, undefined, "verified");
});


it("shows verified diagnostics", () => {
  render(
    <SearchResults
      hits={[]}
      answer={null}
      quality={baseQuality}
      evidencePack={sampleEvidencePack}
      verification={sampleVerification}
    />,
  );

  expect(screen.getByText("Verified Answers")).toBeInTheDocument();
  expect(screen.getByText("Evidence pack")).toBeInTheDocument();
  expect(screen.getByText("Hallucination risk")).toBeInTheDocument();
});
```

- [x] **Step 3: Run tests to verify failure**

Run: `npm test -- api-client.test.ts search-page.test.tsx search-results.test.tsx`

Expected: FAIL because types, API parameter, toggle, and diagnostics are missing.

- [x] **Step 4: Add frontend types and API parameter**

Modify `apps/web/lib/types.ts`:

```typescript
export type AnswerMode = "standard" | "verified";
export type VerificationStatus = "verified" | "partially_supported" | "unsupported";

export type EvidencePackItem = {
  chunk_id: string;
  document_id: string;
  document_filename: string;
  page_number: number;
  chunk_index: number;
  snippet: string;
  score: number;
  source_score: number;
  ranking_signals: Record<string, number>;
  section_heading?: string | null;
  subquery: string;
  support_score: number;
};

export type RejectedEvidence = {
  chunk_id: string;
  page_number: number;
  subquery: string;
  reason: string;
};

export type EvidencePack = {
  question: string;
  rewritten_query: string;
  subqueries: string[];
  items: EvidencePackItem[];
  rejected: RejectedEvidence[];
  retrieval_mode: "hybrid" | "vector" | "lexical";
  retrieval_fallback_reason?: string | null;
  selected_chunk_count: number;
  selected_page_count: number;
  average_support_score: number;
  is_multi_hop: boolean;
};

export type SentenceSupport = {
  sentence: string;
  status: VerificationStatus;
  supporting_chunk_ids: string[];
  support_score: number;
  missing_terms: string[];
  missing_numbers: string[];
};

export type EvidenceVerification = {
  status: VerificationStatus;
  sentences: SentenceSupport[];
  unsupported_sentence_count: number;
  removed_sentence_count: number;
  hallucination_risk: number;
  reason: string;
};
```

Modify `apps/web/lib/api.ts`:

```typescript
export async function searchDocuments(
  query: string,
  topK = 5,
  documentId?: string,
  answerMode: AnswerMode = "standard",
): Promise<SearchResponse> {
  const response = await fetch(`${API_BASE_URL}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK, document_id: documentId, answer_mode: answerMode }),
  });
  return parseJsonResponse<SearchResponse>(response);
}
```

- [x] **Step 5: Add toggle and diagnostics UI**

Modify `apps/web/app/search/page.tsx`:

```tsx
const [answerMode, setAnswerMode] = useState<AnswerMode>("standard");

<button
  type="button"
  role="switch"
  aria-checked={answerMode === "verified"}
  aria-label="Verified Answers"
  onClick={() => setAnswerMode((current) => (current === "verified" ? "standard" : "verified"))}
>
  Verified Answers
</button>
```

Pass `answerMode` to `searchDocuments` and pass `response.evidence_pack` / `response.verification` to `SearchResults`.

Modify `apps/web/components/search-results.tsx` with compact panels:

```tsx
function formatPercent(value: number) {
  return `${Math.round(value * 100)}%`;
}

function VerifiedDiagnosticsPanel({
  evidencePack,
  verification,
}: {
  evidencePack?: EvidencePack | null;
  verification?: EvidenceVerification | null;
}) {
  if (!evidencePack && !verification) {
    return null;
  }

  return (
    <Panel className="p-5" aria-labelledby="verified-answers-heading">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="verified-answers-heading" className="text-sm font-semibold">Verified Answers</h2>
        {verification ? <Badge tone={verification.status === "verified" ? "success" : "amber"}>{verification.status.replaceAll("_", " ")}</Badge> : null}
      </div>
      {evidencePack ? (
        <dl className="mt-3 grid gap-3 text-xs sm:grid-cols-4">
          <div>
            <dt className="text-slate-500">Evidence pack</dt>
            <dd className="mt-1 font-medium text-slate-700">{evidencePack.selected_chunk_count} chunks</dd>
          </div>
          <div>
            <dt className="text-slate-500">Pages</dt>
            <dd className="mt-1 font-medium text-slate-700">{evidencePack.selected_page_count}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Subqueries</dt>
            <dd className="mt-1 font-medium text-slate-700">{evidencePack.subqueries.length}</dd>
          </div>
          <div>
            <dt className="text-slate-500">Support</dt>
            <dd className="mt-1 font-medium text-slate-700">{formatPercent(evidencePack.average_support_score)}</dd>
          </div>
        </dl>
      ) : null}
      {verification ? (
        <p className="mt-3 text-xs leading-5 text-slate-600">
          Hallucination risk: {formatPercent(verification.hallucination_risk)}. {verification.reason}
        </p>
      ) : null}
    </Panel>
  );
}
```

- [x] **Step 6: Run tests to verify pass**

Run: `npm test -- api-client.test.ts search-page.test.tsx search-results.test.tsx`

Expected: PASS.

- [x] **Step 7: Commit**

```bash
git add apps/web/lib apps/web/app/search/page.tsx apps/web/components/search-results.tsx apps/web/tests
git commit -m "Add verified answers search UI"
```

---

### Task 8: Frontend Evaluation Lab UI

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/app/evaluation/page.tsx`
- Modify: `apps/web/components/evaluation-summary.tsx`
- Modify: `apps/web/tests/evaluation-page.test.tsx`
- Modify: `apps/web/tests/evaluation-summary.test.tsx`

**Interfaces:**
- Consumes: expanded `GoldenEvalResponse.summary.quality_dimensions`
- Produces: Evaluation Lab copy and verified metric badges

- [x] **Step 1: Write failing UI test**

```typescript
it("labels the evaluation page as an Evaluation Lab", () => {
  render(<EvaluationPage />);

  expect(screen.getByRole("heading", { name: "Evaluation Lab" })).toBeInTheDocument();
});


it("renders verified quality dimensions", () => {
  render(<EvaluationSummary runs={[]} golden={goldenWithVerifiedMetrics} />);

  expect(screen.getByText("Verified Answers")).toBeInTheDocument();
  expect(screen.getByText("Table QA")).toBeInTheDocument();
  expect(screen.getByText("Multi-hop QA")).toBeInTheDocument();
  expect(screen.getByText("Hallucination risk")).toBeInTheDocument();
});
```

- [x] **Step 2: Run tests to verify failure**

Run: `npm test -- evaluation-page.test.tsx evaluation-summary.test.tsx`

Expected: FAIL because copy/labels do not exist.

- [x] **Step 3: Update copy and dimension formatting**

Modify `apps/web/app/evaluation/page.tsx` heading to `Evaluation Lab` and supporting copy to mention verified answer quality, citation accuracy, retrieval recall, abstention safety, and hallucination risk.

Modify `formatQualityDimension` in `apps/web/components/evaluation-summary.tsx`:

```typescript
const labels: Record<string, string> = {
  answer_quality: "Answer quality",
  abstention_safety: "Abstention safety",
  citation_accuracy: "Citation accuracy",
  hallucination_risk: "Hallucination risk",
  multi_hop_qa: "Multi-hop QA",
  ocr_readiness: "OCR readiness",
  parse_quality: "Parse quality",
  table_qa: "Table QA",
  verified_answers: "Verified Answers",
};
```

- [x] **Step 4: Run tests to verify pass**

Run: `npm test -- evaluation-page.test.tsx evaluation-summary.test.tsx`

Expected: PASS.

- [x] **Step 5: Commit**

```bash
git add apps/web/app/evaluation/page.tsx apps/web/components/evaluation-summary.tsx apps/web/tests/evaluation-page.test.tsx apps/web/tests/evaluation-summary.test.tsx
git commit -m "Update evaluation lab for verified answers"
```

---

### Task 9: Integration Verification And Pull Request Prep

**Files:**
- Modify: `docs/superpowers/plans/2026-09-11-verified-answers-rag.md`

**Interfaces:**
- Produces: completed feature branch with all checked tasks.

- [ ] **Step 1: Run focused API tests**

Run:

```powershell
python -m pytest -q apps/api/tests/retrieval apps/api/tests/documents/test_tables.py apps/api/tests/evaluation
```

Expected: PASS.

- [x] **Step 2: Run full non-integration API verification**

Run:

```powershell
python -m pytest -q -m "not integration" -k "not uses_hybrid_retrieval_hits and not falls_back_to_ranked_chunks_when_retrieval_has_no_hits and not can_replace_stale_existing_questions"
```

Expected: PASS.

- [x] **Step 3: Run web tests**

Run:

```powershell
npm test
```

from `apps/web`.

Expected: PASS.

- [x] **Step 4: Run web lint**

Run:

```powershell
npm run lint
```

from `apps/web`.

Expected: exits with code 0.

- [x] **Step 5: Run backend compile check**

Run:

```powershell
python -m compileall app
```

from `apps/api`.

Expected: exits with code 0.

- [x] **Step 6: Run web build**

Run:

```powershell
npm run build
```

from `apps/web`.

Expected: exits with code 0.

- [x] **Step 7: Run diff whitespace check**

Run:

```powershell
git diff --check
```

Expected: exits with code 0.

- [x] **Step 8: Update plan checkboxes**

Mark completed task checkboxes in this plan using `- [x]` only for tasks that passed their verification.

- [x] **Step 9: Commit final plan update**

```bash
git add docs/superpowers/plans/2026-09-11-verified-answers-rag.md
git commit -m "Mark verified answers plan complete"
```

- [ ] **Step 10: Prepare PR**

Use the finishing-a-development-branch workflow to inspect branch status, summarize commits, and decide whether to merge or open a PR.
