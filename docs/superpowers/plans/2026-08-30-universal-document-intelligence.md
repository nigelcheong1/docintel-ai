# Universal Document Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Track progress with checkbox status.

**Goal:** Build a local universal document intelligence layer with profiling, query routing, typed extractive answers, expanded hybrid retrieval, and a profile-aware UI.

**Architecture:** Keep the existing local FastAPI + pgvector + sentence-transformers + Next.js stack. Add an on-demand document profile from stored pages/chunks, route selected-document queries by intent, then answer from typed extractive strategies before falling back to the existing answer gate.

**Spec:** `docs/superpowers/specs/2026-08-30-universal-document-intelligence-design.md`

## Global Constraints

- No paid APIs, OpenAI API, Ollama generation, OCR, or model training in this phase.
- Generate synthetic evaluation fixtures inside tests; no user dataset download is needed today.
- Keep answers extractive and cited.
- Prefer type-aware abstention over weak generic answers.
- Add failing tests before production code.
- Leave unrelated local changes untouched.

---

### Task 1: Backend Document Profile

**Files:**
- Add: `apps/api/app/documents/intelligence.py`
- Modify: `apps/api/app/documents/schemas.py`
- Modify: `apps/api/app/documents/router.py`
- Test: `apps/api/tests/documents/test_intelligence.py`
- Test: `apps/api/tests/documents/test_profile_api.py`

**Interfaces:**
- Add `DocumentProfileRead`, `DocumentSectionRead`, and `DocumentFactRead`.
- Add `build_document_profile(document) -> DocumentProfileRead`.
- Add `GET /documents/{document_id}/profile`.

- [x] Step 1: Write tests for type detection, profile facts, and profile endpoint.
- [x] Step 2: Implement profile extraction from pages and chunks.
- [x] Step 3: Run focused document tests.

### Task 2: Backend Query Routing And Typed Answers

**Files:**
- Add: `apps/api/app/retrieval/query_router.py`
- Add: `apps/api/app/retrieval/document_answers.py`
- Modify: `apps/api/app/retrieval/router.py`
- Modify: `apps/api/app/retrieval/search.py`
- Modify: `apps/api/app/retrieval/reranker.py`
- Test: `apps/api/tests/retrieval/test_query_router.py`
- Test: `apps/api/tests/retrieval/test_document_answers.py`
- Test: `apps/api/tests/retrieval/test_search_api.py`

**Interfaces:**
- Add `query_intent` and `document_type` to `SearchResponse`.
- Add typed answer strategies for overview, dates, amounts, parties, risks/obligations, datasets, methods, results, and limitations.
- Expand section intent scoring for research papers, invoices, contracts, reports, and generic documents.

- [x] Step 1: Write tests for research, invoice, contract, and mismatch queries.
- [x] Step 2: Implement query routing and typed extractive answers.
- [x] Step 3: Integrate with `/search` before fallback answer gating.
- [x] Step 4: Run focused retrieval tests.

### Task 3: Frontend Profile-Aware Search

**Files:**
- Add: `apps/web/components/document-profile-panel.tsx`
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/app/search/page.tsx`
- Modify: `apps/web/components/search-results.tsx`
- Test: `apps/web/tests/api-client.test.ts`
- Test: `apps/web/tests/document-profile-panel.test.tsx`
- Test: `apps/web/tests/search-page.test.tsx`
- Test: `apps/web/tests/search-results.test.tsx`

**Interfaces:**
- Add `getDocumentProfile(documentId)`.
- Show selected-document type, overview, key facts, sections, and suggested questions.
- Display query intent and document type in answer/no-answer panels.

- [x] Step 1: Write UI tests for profile rendering and suggested-question flow.
- [x] Step 2: Implement the profile panel and API client changes.
- [x] Step 3: Update search results metadata display.
- [x] Step 4: Run focused frontend tests.

### Task 4: Verification, Review, And Push

**Files:**
- No planned production changes unless verification reveals defects.

- [x] Step 1: Run full backend tests.
- [x] Step 2: Run full frontend tests, lint, and build.
- [x] Step 3: Run `git diff --check` and review the branch diff.
- [x] Step 4: Use a sidecar review agent for final code review.
- [ ] Step 5: Commit and push `feature/universal-document-intelligence`.
- [ ] Step 6: Provide the PR compare URL if a PR is not created automatically.
