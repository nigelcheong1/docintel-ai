# Evaluation Diagnostics Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a golden QA evaluation workbench, search diagnostics, and clearer evidence grouping for DocIntel AI.

**Architecture:** Extend existing FastAPI schemas and services rather than replacing the RAG pipeline. Add deterministic in-memory golden fixtures that use current document intelligence and answer builders. Update the Next.js Search and Evaluation pages to display diagnostics and per-document-type benchmark health.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy models for in-memory fixtures, pytest, Next.js, React, Vitest, Testing Library, Tailwind CSS, lucide-react.

**Spec:** `docs/superpowers/specs/2026-08-31-evaluation-diagnostics-workbench-design.md`

## Global Constraints

- Keep answers extractive and cited; do not add uncited generative answers.
- Do not train a model in this phase.
- Reuse existing document type, query intent, and answer quality structures.
- Keep `apps/web/next-env.d.ts` out of commits because it is generated locally.

---

### Task 1: Search Diagnostics Contract

**Files:**
- Modify: `apps/api/app/retrieval/search.py`
- Modify: `apps/api/app/retrieval/router.py`
- Test: `apps/api/tests/retrieval/test_search_api.py`
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Test: `apps/web/tests/api-client.test.ts`

**Interfaces:**
- Produces: `SearchDiagnostics` with `document_type`, `query_intent`, `quality_status`, `confidence`, `reason`, `answer_chunk_ids`, `answer_evidence_count`, `related_result_count`, and `top_rejected_reasons`.
- Consumes: existing `SearchResponse`, `AnswerQuality`, and `SearchHitRead`.

- [ ] Write failing API and web tests expecting `/search` responses to include diagnostics and `result_role` per hit.
- [ ] Run focused tests and verify they fail because fields are missing.
- [ ] Add backend diagnostics builders and hit role assignment.
- [ ] Add frontend types.
- [ ] Run focused tests and verify they pass.

### Task 2: Golden QA Evaluation Engine

**Files:**
- Create: `apps/api/app/evaluation/golden.py`
- Modify: `apps/api/app/evaluation/router.py`
- Test: `apps/api/tests/evaluation/test_golden_eval.py`

**Interfaces:**
- Produces: `GoldenEvalResponse`, `GoldenEvalCaseResult`, and `run_golden_evaluation()`.
- Consumes: `build_document_profile()`, `route_query()`, and `build_document_aware_answer()`.

- [ ] Write failing tests for research-paper, resume, invoice, contract, report, and hard-negative cases.
- [ ] Run focused tests and verify they fail because endpoint/service is missing.
- [ ] Implement in-memory document fixtures and case grading.
- [ ] Run focused tests and verify they pass.

### Task 3: Search Evidence UI

**Files:**
- Modify: `apps/web/components/search-results.tsx`
- Test: `apps/web/tests/search-results.test.tsx`

**Interfaces:**
- Consumes: `SearchResponse.diagnostics` and hit `result_role`.
- Produces: UI sections named `Answer evidence` and `Related evidence`, plus a compact `Diagnostics` details area.

- [ ] Write failing component tests for evidence grouping and diagnostics.
- [ ] Run focused tests and verify they fail.
- [ ] Implement the UI grouping and diagnostics display.
- [ ] Run focused tests and verify they pass.

### Task 4: Evaluation Workbench UI

**Files:**
- Modify: `apps/web/app/evaluation/page.tsx`
- Modify: `apps/web/components/evaluation-summary.tsx`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/lib/types.ts`
- Test: `apps/web/tests/evaluation-page.test.tsx`
- Test: `apps/web/tests/evaluation-summary.test.tsx`

**Interfaces:**
- Consumes: `getGoldenEval()`.
- Produces: benchmark summary cards and per-case result rows.

- [ ] Write failing UI tests for golden benchmark loading and case rendering.
- [ ] Run focused tests and verify they fail.
- [ ] Implement API client and UI.
- [ ] Run focused tests and verify they pass.

### Task 5: Verification and Branch Prep

**Files:**
- No production edits.

- [ ] Run full API tests with `DOCINTEL_TEST_DATABASE_URL`.
- [ ] Run full web tests.
- [ ] Run web lint and build.
- [ ] Run `git diff --check`.
- [ ] Commit intended files only.
- [ ] Push branch and provide the PR link.

