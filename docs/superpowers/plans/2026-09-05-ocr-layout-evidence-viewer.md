# OCR Layout Evidence Viewer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local source-page rendering, richer page diagnostics, OCR preprocessing, and an interactive evidence preview to DocIntel AI.

**Architecture:** Keep the current FastAPI document APIs and Next.js workbench. Add a small rendering boundary for page images, derive page health without a migration, and enhance OCR quality at the Tesseract provider edge.

**Tech Stack:** FastAPI, SQLAlchemy, PyMuPDF, Pillow, Tesseract CLI, Next.js, React, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-09-05-ocr-layout-evidence-viewer-design.md`

## Global Constraints

- Local-first only; no paid OCR APIs.
- No background worker service.
- No persistent bounding-box schema.
- No manual annotation workflow.
- Existing document/search routes must remain backward compatible.

---

### Task 1: Page Diagnostics And Source Rendering API

**Files:**
- Create: `apps/api/app/documents/page_rendering.py`
- Modify: `apps/api/app/documents/schemas.py`
- Modify: `apps/api/app/documents/router.py`
- Modify: `apps/api/app/documents/service.py`
- Modify: `apps/api/tests/documents/test_router.py`

**Interfaces:**
- Produces: `render_document_page_image(document: Document, page_number: int, storage_dir: Path | None) -> RenderedPageImage`.
- Produces: `DocumentPageRead.image_url`, `text_density`, `ocr_quality`, and `needs_review`.
- Produces: `GET /documents/{document_id}/pages/{page_number}/image`.

- [x] Write backend tests for page diagnostic fields, PDF page image rendering, image page rendering, and invalid page numbers.
- [x] Run selected tests and confirm they fail because the API and fields do not exist.
- [x] Implement `page_rendering.py`, expose storage path resolution from service, add schema fields, and add the router endpoint.
- [x] Run selected tests and confirm they pass.

### Task 2: OCR Image Preprocessing

**Files:**
- Modify: `apps/api/app/documents/ocr.py`
- Modify: `apps/api/tests/documents/test_ocr.py`

**Interfaces:**
- Produces: `prepare_image_for_ocr(image: Image.Image) -> Image.Image`.
- `TesseractOcrProvider.ocr_image()` uses `prepare_image_for_ocr()` before writing the temporary PNG.

- [x] Write a failing test that small color scans are converted to grayscale, auto-contrasted, and upscaled.
- [x] Run the selected OCR test and confirm it fails because `prepare_image_for_ocr` does not exist.
- [x] Implement deterministic Pillow preprocessing and wire it into the provider.
- [x] Run selected OCR tests and confirm they pass.

### Task 3: Interactive Evidence Preview UI

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/components/document-workbench.tsx`
- Modify: `apps/web/tests/document-workbench.test.tsx`

**Interfaces:**
- Consumes: `DocumentPage.image_url`, `text_density`, `ocr_quality`, and `needs_review`.
- Produces: evidence tab source page preview with zoom controls.

- [x] Write frontend tests for source page preview image, zoom controls, and review-needed page labels.
- [x] Run selected frontend tests and confirm they fail against the current UI.
- [x] Extend frontend types and update the workbench evidence/page panels.
- [x] Run selected frontend tests and confirm they pass.

### Task 4: Full Verification And PR

**Files:**
- Modify: implementation files from Tasks 1-3.
- Modify: this plan if execution notes need to be checked off.

**Interfaces:**
- Produces: one verified feature branch ready for PR.

- [ ] Run `pytest apps/api/tests -q`.
- [ ] Run `npm --prefix apps/web test`.
- [ ] Run `npm --prefix apps/web run lint`.
- [ ] Run `npm --prefix apps/web run build`.
- [ ] Run `git diff --check`.
- [ ] Commit all changes and push `feature/ocr-layout-evidence-viewer`.
