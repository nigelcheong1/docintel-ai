# Smart Document Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade DocIntel AI from basic local vector search into a more useful local document workspace with document actions, smarter reranking, and cited extractive answers.

**Architecture:** Reuse the existing FastAPI, SQLAlchemy, pgvector, sentence-transformers, and Next.js app. Add focused service functions for document actions, a retrieval reranker, an extractive answer builder, and UI controls that expose the new capabilities.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL/pgvector, PyMuPDF, sentence-transformers, Next.js, React, TypeScript, Tailwind CSS, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-08-28-smart-document-workspace-design.md`

## Global Constraints

- Local-only: no OpenAI API or paid hosted AI services.
- No model training in this phase.
- Reuse existing parser, chunker, embedding, and database models where possible.
- Keep document deletion and reindexing explicit user actions.
- Every behavior change gets a failing test before production code.

---

### Task 1: Document Delete And Reindex API

**Files:**
- Modify: `apps/api/app/documents/service.py`
- Modify: `apps/api/app/documents/router.py`
- Modify: `apps/api/app/documents/schemas.py`
- Test: `apps/api/tests/documents/test_service.py`
- Test: `apps/api/tests/documents/test_router.py`

**Interfaces:**
- Produces: `delete_document(db: Session, document_id: str) -> None`
- Produces: `reindex_document(db: Session, document_id: str, embedder_factory: EmbeddingProviderFactory) -> Document`
- Produces: `DELETE /documents/{document_id}`
- Produces: `POST /documents/{document_id}/reindex`

- [ ] Write failing service tests for deleting a document and removing its stored file.
- [ ] Write failing service tests for reindexing a PDF after clearing old pages/chunks/embeddings.
- [ ] Write failing router tests for `DELETE /documents/{document_id}` and `POST /documents/{document_id}/reindex`.
- [ ] Implement service functions using existing SQLAlchemy relationships and `parse_pdf`, `chunk_pages`, and `EmbeddingProvider`.
- [ ] Implement routes with clear 404 and failure behavior.
- [ ] Run `pytest tests/documents/test_service.py tests/documents/test_router.py`.
- [ ] Commit as `feat: add document management actions`.

### Task 2: Smarter Local Reranking

**Files:**
- Create: `apps/api/app/retrieval/reranker.py`
- Modify: `apps/api/app/retrieval/search.py`
- Test: `apps/api/tests/retrieval/test_reranker.py`
- Test: `apps/api/tests/retrieval/test_search_formatting.py`

**Interfaces:**
- Produces: `infer_query_intents(query: str) -> set[str]`
- Produces: `keyword_overlap_score(query: str, text: str) -> float`
- Produces: `rerank_hits(query: str, hits: Sequence[SearchHit]) -> list[SearchHit]`
- Extends: `SearchHit` with `source_score: float`, `ranking_signals: dict[str, float]`
- Extends: `SearchHitRead` with `source_score: float`, `ranking_signals: dict[str, float]`

- [ ] Write failing tests that `project` queries rank `PROJECTS`/`KEY PROJECTS` over unrelated sections when vector scores are close.
- [ ] Write failing tests that `skill` and `education` queries prefer matching sections.
- [ ] Write failing tests for keyword overlap scoring.
- [ ] Implement reranking with a transparent blended score.
- [ ] Wire reranking into `/search` after vector retrieval.
- [ ] Run `pytest tests/retrieval/test_reranker.py tests/retrieval/test_search_api.py tests/retrieval/test_search_formatting.py`.
- [ ] Commit as `feat: add local retrieval reranking`.

### Task 3: Extractive Answer API

**Files:**
- Create: `apps/api/app/retrieval/answers.py`
- Modify: `apps/api/app/retrieval/search.py`
- Modify: `apps/api/app/retrieval/router.py`
- Test: `apps/api/tests/retrieval/test_answers.py`
- Test: `apps/api/tests/retrieval/test_search_api.py`

**Interfaces:**
- Produces: `AnswerCitation` model fields: `chunk_id`, `document_filename`, `page_number`, `section_heading`
- Produces: `ExtractiveAnswer` model fields: `summary`, `citations`
- Produces: `build_extractive_answer(query: str, hits: Sequence[SearchHit]) -> ExtractiveAnswer | None`
- Extends: `SearchResponse.answer`

- [ ] Write failing tests for no-hit answer behavior.
- [ ] Write failing tests for a cited answer from top-ranked evidence.
- [ ] Implement concise extractive summary generation from top snippets.
- [ ] Wire answer into `/search`.
- [ ] Run `pytest tests/retrieval/test_answers.py tests/retrieval/test_search_api.py`.
- [ ] Commit as `feat: add cited extractive answers`.

### Task 4: Frontend Document Workspace

**Files:**
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/components/document-list.tsx`
- Modify: `apps/web/app/documents/page.tsx`
- Test: `apps/web/tests/document-list.test.tsx`
- Test: `apps/web/tests/api-client.test.ts`

**Interfaces:**
- Consumes: `DELETE /documents/{document_id}`
- Consumes: `POST /documents/{document_id}/reindex`
- Displays: filename, status, page count, chunk count, updated time, delete and reindex buttons.

- [ ] Write failing API client tests for `deleteDocument` and `reindexDocument`.
- [ ] Write failing component tests for document metadata and action buttons.
- [ ] Implement API client functions.
- [ ] Implement document action controls with disabled/loading states.
- [ ] Refresh document list after each successful action.
- [ ] Run `npm test -- api-client.test.ts document-list.test.tsx`.
- [ ] Commit as `feat: improve document workspace`.

### Task 5: Frontend Search Answer Experience

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/components/search-results.tsx`
- Modify: `apps/web/app/search/page.tsx`
- Test: `apps/web/tests/search-results.test.tsx`

**Interfaces:**
- Consumes: `SearchResponse.answer`
- Displays: extractive answer panel, citation count, section label, score, source score, and ranking signals.

- [ ] Write failing tests for answer panel rendering.
- [ ] Write failing tests for ranking signal display.
- [ ] Implement answer panel above evidence cards.
- [ ] Make cards more scannable while staying consistent with the existing UI.
- [ ] Run `npm test -- search-results.test.tsx`.
- [ ] Commit as `feat: add search answer experience`.

### Task 6: Verification And Pull Request

**Files:**
- No production source changes unless verification reveals a tested defect.

**Interfaces:**
- Produces: pushed branch `feature/smart-document-workspace`.

- [ ] Run backend full tests with `DOCINTEL_TEST_DATABASE_URL=postgresql+psycopg://docintel:docintel@localhost:5432/docintel_test python -m pytest`.
- [ ] Run frontend full tests with `npm test`.
- [ ] Run frontend lint with `npm run lint`.
- [ ] Run frontend build with `npm run build`.
- [ ] Request code review before pushing.
- [ ] Fix any critical or important review issues with tests.
- [ ] Push branch to GitHub.
- [ ] Create PR if permissions allow, otherwise provide the PR URL.
