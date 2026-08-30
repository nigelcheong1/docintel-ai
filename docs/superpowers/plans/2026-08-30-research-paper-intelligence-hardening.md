# Research Paper Intelligence Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:test-driven-development for each behavior change. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make research-paper search and answers robust enough for university-paper workflows by cleaning PDF noise, detecting academic structure, selecting section-faithful evidence, and surfacing useful paper-specific facts.

**Architecture:** Keep the local FastAPI + pgvector + sentence-transformers + Next.js stack. Add a focused research-paper intelligence layer around the existing universal document profile and document-aware answer builder, without paid APIs, external LLMs, OCR, or training.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy, pgvector, sentence-transformers, Next.js, TypeScript, Vitest, pytest.

**Spec:** User-approved chat design from 2026-08-30 screenshots: improve bad ScienceDirect title/overview/methods/results/limitations outputs for research papers.

## Global Constraints

- No paid APIs, OpenAI API, Ollama generation, OCR, or model training in this phase.
- Use synthetic research-paper fixtures in tests; no user dataset download is needed today.
- Answers must remain extractive and cited.
- Prefer weak or moderate confidence over wrong strong-confidence answers.
- Do not touch unrelated local changes in the main checkout.

---

### Task 1: Research Paper Text Cleaning

**Files:**
- Modify: `apps/api/app/documents/intelligence.py`
- Modify: `apps/api/app/retrieval/document_answers.py`
- Test: `apps/api/tests/documents/test_intelligence.py`
- Test: `apps/api/tests/retrieval/test_document_answers.py`

**Interfaces:**
- Add reusable research-paper text cleanup helpers.
- Use them before profile previews, title inference, answer sentence selection, and citation snippets.

- [x] Step 1: Write failing tests for ScienceDirect/Elsevier boilerplate, author-affiliation noise, copyright text, and broken one-token sentences.
- [x] Step 2: Implement cleanup helpers.
- [x] Step 3: Verify focused tests pass.

### Task 2: Academic Structure And Facts

**Files:**
- Modify: `apps/api/app/documents/intelligence.py`
- Modify: `apps/api/app/documents/chunker.py`
- Test: `apps/api/tests/documents/test_intelligence.py`

**Interfaces:**
- Improve title inference to skip publisher boilerplate.
- Add research-specific facts for methods, datasets, metrics, and contributions using existing `DocumentFactRead`.
- Filter noisy dates/numbers from research-paper profiles.

- [x] Step 1: Write failing tests for title, abstract overview, useful entities, and noisy fact filtering.
- [x] Step 2: Implement profile heuristics.
- [x] Step 3: Verify focused tests pass.

### Task 3: Section-Faithful Research Answers

**Files:**
- Modify: `apps/api/app/retrieval/document_answers.py`
- Modify: `apps/api/app/retrieval/reranker.py`
- Test: `apps/api/tests/retrieval/test_document_answers.py`
- Test: `apps/api/tests/retrieval/test_reranker.py`

**Interfaces:**
- Add research-paper answer policies for overview, methods, datasets, results, and limitations.
- Require appropriate section evidence before strong confidence.
- Prefer table/result chunks only for metric-heavy questions.

- [x] Step 1: Write failing tests from the paper screenshots.
- [x] Step 2: Implement section-faithful answer selection.
- [x] Step 3: Verify focused tests pass.

### Task 4: Frontend Paper Profile Labels

**Files:**
- Modify: `apps/web/components/document-profile-panel.tsx`
- Test: `apps/web/tests/document-profile-panel.test.tsx`

**Interfaces:**
- For research papers, rename generic "Entities" and "Numbers" labels into paper-friendly labels.
- Show fact labels when they add meaning.

- [x] Step 1: Write failing UI tests for research-paper labels.
- [x] Step 2: Implement label rendering.
- [x] Step 3: Verify focused frontend tests pass.

### Task 5: Verification And Push

**Files:**
- No planned production changes unless verification reveals defects.

- [x] Step 1: Run full backend tests.
- [x] Step 2: Run full frontend tests, lint, and build.
- [x] Step 3: Run `git diff --check`.
- [ ] Step 4: Commit and push `feature/research-paper-intelligence-hardening`.
- [ ] Step 5: Provide GitHub PR URL and manual testing steps.
