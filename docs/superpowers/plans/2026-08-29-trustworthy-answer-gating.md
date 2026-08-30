# Trustworthy Answer Gating Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Track progress with checkbox status.

**Goal:** Harden RAG reliability by adding an answer quality gate, confidence labels, abstention behavior, suggested questions, and frontend trust UI.

**Architecture:** Keep retrieval local-only. Reuse existing pgvector search, reranking signals, and extractive answer builder. Add a backend answer-quality contract and have the frontend render it directly.

**Spec:** `docs/superpowers/specs/2026-08-29-trustworthy-answer-gating-design.md`

## Global Constraints

- No paid APIs, OpenAI API, Ollama generation, OCR, or model training in this phase.
- Keep answers extractive and cited.
- Return nearest evidence even when withholding an answer.
- Add failing tests before production code.
- Leave unrelated local changes untouched.

---

### Task 1: Backend Quality Gate

**Files:**
- Modify: `apps/api/app/retrieval/answers.py`
- Modify: `apps/api/app/retrieval/search.py`
- Modify: `apps/api/app/retrieval/router.py`
- Test: `apps/api/tests/retrieval/test_answers.py`
- Test: `apps/api/tests/retrieval/test_search_api.py`

**Interfaces:**
- Add `AnswerQuality` with `status`, `confidence`, `reason`, `suggested_questions`, and evidence signal fields.
- Add `build_grounded_answer(query, hits) -> tuple[ExtractiveAnswer | None, AnswerQuality]`.
- Extend `SearchResponse` with `quality`.

- [x] Step 1: Write backend tests for answerable, unrelated, unsupported language-detection, and response-schema cases.
- [x] Step 2: Implement answer-quality models and gating thresholds.
- [x] Step 3: Route `/search` through the gate before building the answer.
- [x] Step 4: Run focused backend tests.

### Task 2: Frontend Trust UI

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/app/search/page.tsx`
- Modify: `apps/web/components/search-results.tsx`
- Test: `apps/web/tests/search-results.test.tsx`
- Test: `apps/web/tests/search-page.test.tsx`
- Test: `apps/web/tests/api-client.test.ts`

**Interfaces:**
- Consume `SearchResponse.quality`.
- Display confidence for answerable responses.
- Display abstention reason and suggested questions when `answer` is null because evidence is insufficient.

- [x] Step 1: Write frontend tests for confidence display and no-answer panel.
- [x] Step 2: Update TypeScript models and search page state.
- [x] Step 3: Update `SearchResults` rendering.
- [x] Step 4: Run focused frontend tests.

### Task 3: Review, Verification, And Push

**Files:**
- No planned production changes unless verification reveals defects.

- [x] Step 1: Run full backend tests.
- [x] Step 2: Run full frontend tests, lint, and build.
- [x] Step 3: Run `git diff --check` and review the branch diff.
- [x] Step 4: Use a sidecar review agent for final code review.
- [x] Step 5: Commit and push `feature/trustworthy-answer-gating`.
- [x] Step 6: Provide the PR compare URL if a PR is not created automatically.
