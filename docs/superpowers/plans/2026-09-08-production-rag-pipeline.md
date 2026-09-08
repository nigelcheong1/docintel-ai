# Production RAG Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add background document processing, hybrid retrieval, optional LLM generation, citation source preview, and richer document readiness UI.

**Architecture:** Keep the app local-first and synchronous internally where tests need determinism, but expose upload/reindex as background jobs through FastAPI `BackgroundTasks`. Add focused modules for processing status, hybrid retrieval, LLM providers, and source citation payloads, then wire the existing study/search/workbench UI to those interfaces.

**Tech Stack:** FastAPI, SQLAlchemy, pgvector, SentenceTransformers, httpx, pytest, Next.js, React, TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-08-production-rag-pipeline-design.md`

## Global Constraints

- The app remains local-first and must run without paid API keys.
- Optional LLM support must not fail startup when no provider key is configured.
- Existing search, document, OCR, evaluation, summary, and study routes remain backward compatible.
- Background work uses FastAPI `BackgroundTasks`; no external queue service is introduced.
- Hybrid retrieval must degrade to lexical search if vector search fails.
- UI changes use the Academic Teal + Ink + Amber palette and keep sidebar navigation clickable.

---

### Task 1: Processing Status Model And API

**Files:**
- Modify: `apps/api/app/db/models.py`
- Modify: `apps/api/app/db/init_db.py`
- Modify: `apps/api/app/documents/schemas.py`
- Create: `apps/api/app/documents/processing_status.py`
- Modify: `apps/api/app/documents/router.py`
- Modify: `apps/api/tests/db/test_models.py`
- Create: `apps/api/tests/documents/test_processing_status.py`
- Modify: `apps/api/tests/documents/test_router.py`

**Interfaces:**
- Produces: `DocumentStatus.EMBEDDING`
- Produces: `DocumentProcessingStatusRead`
- Produces: `build_processing_status(document: Document) -> DocumentProcessingStatusRead`
- Produces: `GET /documents/{document_id}/status`

- [x] Write failing model/schema tests for the `embedding` status and `DocumentProcessingStatusRead` shape.
- [x] Run targeted tests and confirm they fail because the status/schema do not exist.
- [x] Add the enum value, schema, and local schema sync for Postgres enum.
- [x] Add `build_processing_status` that derives stages, progress, active stage, and failed/deferred messages from document fields.
- [x] Add `GET /documents/{document_id}/status`.
- [x] Run targeted tests and confirm they pass.

### Task 2: Background Upload And Reindex Jobs

**Files:**
- Modify: `apps/api/app/documents/service.py`
- Modify: `apps/api/app/documents/router.py`
- Modify: `apps/api/tests/documents/test_router.py`

**Interfaces:**
- Produces: `create_upload_record(db: Session, stored: StoredUpload) -> Document`
- Produces: `process_document_upload(document_id: str, stored: StoredUpload, embedder_factory, ocr_provider_factory, ...) -> None`
- Produces: upload and reindex routes that schedule indexing with `BackgroundTasks`

- [x] Write failing router tests showing upload returns `processing` before background task execution and later reaches `indexed`.
- [x] Write failing router tests showing reindex returns quickly with processing status and preserves retry errors.
- [x] Run targeted tests and confirm they fail with current synchronous behavior.
- [x] Split document record creation from indexing.
- [x] Add background task wrappers with route-owned session execution.
- [x] Update upload/reindex routes to schedule background indexing.
- [x] Run targeted tests and confirm they pass.

### Task 3: Hybrid Retrieval And Lexical Fallback

**Files:**
- Modify: `apps/api/app/retrieval/search.py`
- Modify: `apps/api/app/retrieval/reranker.py`
- Modify: `apps/api/app/retrieval/router.py`
- Modify: `apps/api/tests/retrieval/test_search_api.py`
- Create: `apps/api/tests/retrieval/test_hybrid_search.py`

**Interfaces:**
- Produces: `lexical_search_chunks(db, query, top_k, document_id=None) -> list[SearchHit]`
- Produces: `hybrid_search_chunks(db, query_embedding, query, top_k, document_id=None) -> tuple[list[SearchHit], RetrievalMode]`
- Produces: diagnostics ranking signals `vector_score`, `lexical_score`, `keyword_overlap`, `section_intent`

- [x] Write failing tests for lexical search returning useful chunks without embeddings.
- [x] Write failing tests for hybrid merge deduplicating vector and lexical candidates.
- [x] Write failing tests for vector failure degrading to lexical search and exposing fallback diagnostics.
- [x] Run targeted tests and confirm they fail.
- [x] Implement lexical search and hybrid merge.
- [x] Update reranker signals and search diagnostics.
- [x] Run targeted tests and confirm they pass.

### Task 4: Optional LLM Provider Layer

**Files:**
- Modify: `apps/api/app/core/config.py`
- Create: `apps/api/app/llm/__init__.py`
- Create: `apps/api/app/llm/providers.py`
- Create: `apps/api/tests/llm/test_providers.py`

**Interfaces:**
- Produces: `LlmProvider` protocol
- Produces: `LocalHeuristicLlmProvider`
- Produces: `GroqLlmProvider`
- Produces: `get_llm_provider(settings: Settings) -> LlmProvider`

- [x] Write failing tests for local summary/question/evaluation provider output.
- [x] Write failing tests that Groq provider is disabled without an API key.
- [x] Run targeted tests and confirm they fail.
- [x] Add settings for provider, model, base URL, API key, timeout.
- [x] Implement local provider and optional Groq-compatible HTTP provider.
- [x] Run targeted tests and confirm they pass.

### Task 5: Study And Summary Use Cited Retrieval Context

**Files:**
- Modify: `apps/api/app/study/service.py`
- Modify: `apps/api/app/study/router.py`
- Modify: `apps/api/tests/study/test_study_service.py`
- Modify: `apps/api/tests/study/test_study_router.py`

**Interfaces:**
- Consumes: `LlmProvider`
- Consumes: `hybrid_search_chunks`
- Produces: retrieval-grounded summary/questions/evaluation with preserved citations

- [x] Write failing tests showing summary generation uses retrieved cited context instead of only heading weights.
- [x] Write failing tests showing study questions dedupe LLM/local generated questions.
- [x] Write failing tests showing answer feedback includes missing key terms in local mode.
- [x] Run targeted tests and confirm they fail.
- [x] Inject/use provider and retrieval context in study service.
- [x] Preserve deterministic local fallback for existing tests.
- [x] Run targeted tests and confirm they pass.

### Task 6: Frontend Processing Status And Polling

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/components/document-list.tsx`
- Modify: `apps/web/app/documents/page.tsx`
- Modify: `apps/web/tests/api-client.test.ts`
- Modify: `apps/web/tests/document-list.test.tsx`
- Modify: `apps/web/tests/documents-page.test.tsx`

**Interfaces:**
- Produces: `DocumentProcessingStatus`
- Produces: `getDocumentStatus(documentId: string)`
- Produces: progress UI and polling while documents process

- [x] Write failing API client test for status endpoint.
- [x] Write failing UI tests for progress label/bar and processing polling.
- [x] Run targeted tests and confirm they fail.
- [x] Add types/API method.
- [x] Add document list progress display.
- [x] Add documents page refresh/polling while active jobs exist.
- [x] Run targeted tests and confirm they pass.

### Task 7: Citation Source Viewer

**Files:**
- Modify: `apps/web/components/search-results.tsx`
- Modify: `apps/web/components/document-workbench.tsx`
- Create: `apps/web/components/source-viewer.tsx`
- Modify: `apps/web/tests/search-results.test.tsx`
- Modify: `apps/web/tests/document-workbench.test.tsx`

**Interfaces:**
- Produces: reusable `SourceViewer`
- Consumes: search hits and study citations with page image URLs and document page URLs

- [x] Write failing UI tests that clicking a search citation opens a source viewer.
- [x] Write failing UI tests that summary/study citations open the same source viewer.
- [x] Run targeted tests and confirm they fail.
- [x] Add `SourceViewer` panel with page image preview, snippet, section, scores, and workbench link.
- [x] Wire search, summary, and study citation buttons.
- [x] Run targeted tests and confirm they pass.

### Task 8: Verification And PR

**Files:**
- Modify: this plan as tasks are completed.

**Interfaces:**
- Produces: one feature branch ready for PR.

- [x] Run full API tests.
- [x] Run full web tests.
- [x] Run web lint.
- [x] Run web build.
- [x] Run `git diff --check`.
- [x] Commit all changes.
