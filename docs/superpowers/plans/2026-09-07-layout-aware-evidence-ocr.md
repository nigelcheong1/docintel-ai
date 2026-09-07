# Layout-Aware Evidence And Faster OCR Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add source-preview search results, citation deep links, chunk highlighting, page processing labels, and stronger OCR routing/preprocessing.

**Architecture:** Keep the current FastAPI and Next.js boundaries. Derive new metadata from existing document/page/chunk fields to avoid migrations, and keep OCR routing in small tested helpers inside the extraction layer.

**Tech Stack:** FastAPI, SQLAlchemy, PyMuPDF, Pillow, Tesseract CLI, Next.js, React, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-09-07-layout-aware-evidence-ocr-design.md`

## Global Constraints

- Local-first only; no paid OCR APIs.
- No database migration.
- No persistent OCR bounding boxes.
- No background worker service.
- Existing document/search routes remain backward compatible.

---

### Task 1: Backend Evidence Metadata

**Files:**
- Modify: `apps/api/app/retrieval/search.py`
- Modify: `apps/api/tests/retrieval/test_search_formatting.py`
- Modify: `apps/api/tests/retrieval/test_search_api.py`

**Interfaces:**
- Produces: `SearchHitRead.page_image_url: str`
- Produces: `SearchHitRead.document_page_url: str`

- [x] Add failing formatter/API tests expecting every formatted hit to include `/documents/{document_id}/pages/{page_number}/image` and `/documents/{document_id}?page={page_number}&chunk={chunk_id}`.
- [x] Run the selected backend tests and confirm they fail because the fields are missing.
- [x] Add the fields to `SearchHitRead` and derive them in `format_search_hit()`.
- [x] Run the selected backend tests and confirm they pass.

Note: formatter coverage passed. The DB-backed search API test could not be fully rerun because local PostgreSQL was unreachable in this session.

### Task 2: Page Processing Status

**Files:**
- Modify: `apps/api/app/documents/schemas.py`
- Modify: `apps/api/app/documents/router.py`
- Modify: `apps/api/tests/documents/test_router.py`
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/components/document-workbench.tsx`
- Modify: `apps/web/tests/document-workbench.test.tsx`

**Interfaces:**
- Produces: `DocumentPageRead.processing_status`
- Consumes: `DocumentPage.processing_status`

- [x] Add failing backend tests for `native_text`, `ocr_strong`, `ocr_moderate`, `ocr_weak`, and `missing_text` page statuses.
- [x] Add failing frontend tests that page cards display readable processing labels.
- [x] Run selected backend/frontend tests and confirm they fail because the status field is missing.
- [x] Derive `processing_status` in the router and display it in the workbench page cards.
- [x] Run selected backend/frontend tests and confirm they pass.

### Task 3: Search Source Preview UI

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/components/search-results.tsx`
- Modify: `apps/web/tests/search-results.test.tsx`

**Interfaces:**
- Consumes: `SearchHit.page_image_url`
- Consumes: `SearchHit.document_page_url`

- [x] Add failing tests that an evidence card opens an inline source page preview, uses the API image URL, zooms in/out/resets, and links to the chunk-aware document URL.
- [x] Run selected frontend tests and confirm they fail against the current UI.
- [x] Add compact preview controls and update `Open page` link behavior.
- [x] Run selected frontend tests and confirm they pass.

### Task 4: Document Workbench Citation Highlight

**Files:**
- Modify: `apps/web/app/documents/[documentId]/page.tsx`
- Modify: `apps/web/components/document-workbench-page.tsx`
- Modify: `apps/web/components/document-workbench.tsx`
- Modify: `apps/web/tests/document-workbench.test.tsx`

**Interfaces:**
- Consumes: `?chunk={chunk_id}` from document deep links.
- Produces: selected chunk highlighting inside the evidence tab.

- [x] Add failing tests that `initialChunkId` highlights the selected chunk and that the route parses the `chunk` query parameter.
- [x] Run selected frontend tests and confirm they fail because chunk deep links are ignored.
- [x] Pass `initialChunkId` through the page wrapper and add a selected-citation state/label in the workbench.
- [x] Run selected frontend tests and confirm they pass.

### Task 5: OCR Routing And Image Normalization

**Files:**
- Modify: `apps/api/app/documents/extraction.py`
- Modify: `apps/api/app/documents/ocr.py`
- Modify: `apps/api/tests/documents/test_extraction.py`
- Modify: `apps/api/tests/documents/test_ocr.py`

**Interfaces:**
- Produces: `should_ocr_pdf_page(text: str) -> bool`
- Produces: `pdf_ocr_page_numbers(pages: list[ParsedPage], max_ocr_pages: int) -> list[int]`
- `prepare_image_for_ocr()` applies EXIF orientation normalization before existing preprocessing.

- [x] Add failing OCR routing tests for dense native pages, sparse pages, and the max-page cap.
- [x] Add a failing preprocessing test that orientation normalization is applied before OCR preparation.
- [x] Run selected tests and confirm they fail because the helpers/normalization are missing.
- [x] Add the extraction helpers and wire `extract_pdf_pages()` through them.
- [x] Add `ImageOps.exif_transpose()` at the start of OCR preprocessing.
- [x] Run selected tests and confirm they pass.

### Task 6: Full Verification And Push

**Files:**
- Modify: this plan as tasks are completed.

**Interfaces:**
- Produces: one verified feature branch ready for PR.

- [x] Run API tests.
- [x] Run web tests.
- [x] Run web lint.
- [x] Run web build.
- [x] Run `git diff --check`.
- [ ] Commit all changes.
- [ ] Push `feature/layout-aware-evidence-ocr`.

Verification notes:
- API focused tests: 15 passed.
- API non-DB suite: 139 passed, 43 deselected, ignoring existing unmarked DB-backed profile endpoint test.
- DB-backed document/search endpoint checks are blocked until local PostgreSQL accepts `docintel_test` connections.
- Web tests: 76 passed.
- Web lint: passed.
- Web build: passed.
- `git diff --check`: passed with Windows line-ending warnings only.
