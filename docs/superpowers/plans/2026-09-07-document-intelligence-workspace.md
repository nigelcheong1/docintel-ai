# Document Intelligence Workspace Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add persistent cited summaries, study questions, answer grading, and document workbench UI tabs.

**Architecture:** Add a focused `study` backend module with persisted SQLAlchemy models and deterministic local generation. Extend the existing Next.js document workbench through typed API client methods and two new tabs.

**Tech Stack:** FastAPI, SQLAlchemy, Pydantic, pytest, Next.js, React, TypeScript, Vitest.

**Spec:** `docs/superpowers/specs/2026-09-07-document-intelligence-workspace-design.md`

## Global Constraints

- Local-first only; no paid cloud LLM integration in this phase.
- Generation is synchronous behind explicit user actions.
- Existing document, search, OCR, and evaluation routes remain backward compatible.
- New UI follows the Academic Teal + Ink + Amber palette.

---

### Task 1: Persistent Study Models

**Files:**
- Modify: `apps/api/app/db/models.py`
- Modify: `apps/api/app/db/init_db.py`
- Modify: `apps/api/tests/db/test_models.py`

**Interfaces:**
- Produces: `DocumentSummary`, `StudyQuestion`, `StudyAnswer`
- Produces: relationships from `Document` to summaries/questions

- [x] Write failing model tests for table names, nullable fields, JSON citations, and relationships.
- [x] Run model tests and confirm they fail because the classes do not exist.
- [x] Add SQLAlchemy models and relationships.
- [x] Run model tests and confirm they pass.

### Task 2: Backend Study Service

**Files:**
- Create: `apps/api/app/study/__init__.py`
- Create: `apps/api/app/study/service.py`
- Create: `apps/api/app/study/schemas.py`
- Create: `apps/api/tests/study/test_service.py`

**Interfaces:**
- Produces: `generate_document_summary(db, document_id)`
- Produces: `generate_study_questions(db, document_id, count=5)`
- Produces: `grade_study_answer(db, document_id, question_id, answer_text)`

- [x] Write failing service tests for cited summary generation.
- [x] Write failing service tests for question generation and deduplication.
- [x] Write failing service tests for answer grading.
- [x] Run service tests and confirm they fail because the service does not exist.
- [x] Implement deterministic service logic.
- [x] Run service tests and confirm they pass.

### Task 3: Backend Study API

**Files:**
- Create: `apps/api/app/study/router.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/api/tests/study/test_router.py`

**Interfaces:**
- Produces: `/documents/{document_id}/study/summary`
- Produces: `/documents/{document_id}/study/questions`
- Produces: `/documents/{document_id}/study/questions/{question_id}/answers`

- [x] Write failing router tests for get/generate summary.
- [x] Write failing router tests for get/generate questions.
- [x] Write failing router tests for answer submission validation.
- [x] Run router tests and confirm they fail because routes are missing.
- [x] Add router and include it in the app.
- [x] Run router tests and confirm they pass.

### Task 4: Frontend Study API Types

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/lib/api.ts`
- Modify: `apps/web/tests/api-client.test.ts`

**Interfaces:**
- Produces: `DocumentStudySummary`, `StudyQuestion`, `StudyAnswer`
- Produces: `getDocumentStudySummary`, `generateDocumentStudySummary`, `getStudyQuestions`, `generateStudyQuestions`, `submitStudyAnswer`

- [x] Write failing API client tests for the new endpoints.
- [x] Run API client tests and confirm they fail.
- [x] Add types and API client functions.
- [x] Run API client tests and confirm they pass.

### Task 5: Document Workbench Summary And Study UI

**Files:**
- Modify: `apps/web/components/document-workbench.tsx`
- Modify: `apps/web/tests/document-workbench.test.tsx`

**Interfaces:**
- Consumes: study API client functions from Task 4
- Produces: `Summary` and `Study` workbench tabs

- [x] Write failing UI tests for summary generation and citation links.
- [x] Write failing UI tests for question generation and answer feedback.
- [x] Run selected frontend tests and confirm they fail.
- [x] Add summary and study tabs with interactive buttons.
- [x] Run selected frontend tests and confirm they pass.

### Task 6: Verification And Commit

**Files:**
- Modify: this plan as tasks are completed.

**Interfaces:**
- Produces: one feature branch ready for PR.

- [x] Run API focused tests.
- [x] Run web tests.
- [x] Run web lint/build if practical.
- [x] Run `git diff --check`.
- [x] Commit all changes.

Verification notes:
- Focused API tests: 17 passed.
- API non-integration suite: 151 passed, 44 deselected.
- API integration suite with `docintel_test`: 44 passed, 151 deselected.
- Full API suite with `docintel_test`: 195 passed.
- Full web test suite: 81 passed.
- Web lint: passed.
- Web build: passed.
- `git diff --check`: passed with Windows line-ending warnings only.
