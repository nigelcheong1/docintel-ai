# OCR Layout Evidence Viewer Design

## Goal

DocIntel AI should let users inspect the original page behind each evidence chunk, while improving local OCR quality before text reaches retrieval.

## Scope

- Render stored PDF pages and uploaded image documents through local API endpoints.
- Add page-level diagnostics that tell the frontend whether a page has enough text, whether OCR was used, and whether the page needs human review.
- Improve Tesseract input quality with deterministic Pillow preprocessing.
- Add an interactive evidence preview to the document workbench with page image, zoom controls, OCR/source badges, and page health signals.
- Keep all processing local-first and deterministic.

## Non-Goals

- No paid OCR APIs.
- No background worker service.
- No persistent bounding-box schema.
- No manual annotation workflow.
- No authentication or sharing.

## Backend Design

Add a focused page rendering module that resolves a persisted document file and returns a rendered page as bytes. PDFs render one page to PNG with PyMuPDF at a bounded preview DPI. Image documents expose page 1 as normalized PNG bytes through Pillow. Missing files, invalid page numbers, and unsupported document types return clear HTTP errors.

Extend `DocumentPageRead` with derived fields:

- `image_url`: frontend-safe URL for the rendered source page.
- `text_density`: characters per page area, rounded for display.
- `ocr_quality`: `native`, `strong`, `moderate`, `weak`, or `missing`.
- `needs_review`: true when a page has no chunks, no text, or weak OCR confidence.

Improve OCR preprocessing inside `TesseractOcrProvider` before the temporary image is written: convert to grayscale, auto-contrast, upscale small scans, and sharpen. This keeps the provider boundary stable while making future OCR calls more reliable.

## Frontend Design

The document workbench evidence tab becomes a visual review surface. The selected page shows a source preview image above or beside evidence chunks, depending on viewport width. Users can zoom in, zoom out, and reset zoom. Page cards show whether a page needs review and why. Existing search and document links remain stable.

## Testing Strategy

Backend tests cover:

- page diagnostics include image URLs and page health fields;
- PDF page rendering returns PNG bytes;
- image page rendering returns PNG bytes for page 1;
- invalid page numbers return HTTP errors;
- OCR preprocessing converts and enlarges small images without calling Tesseract.

Frontend tests cover:

- the workbench renders the selected page preview image;
- zoom controls update the preview scale;
- page cards expose review-needed labels;
- existing page selection still switches to evidence view.

