# OCR Ingestion Reliability Design

## Goal

DocIntel AI should index scanned PDFs, mixed text/scanned PDFs, and uploaded document images with local OCR when an OCR engine is available. Normal text PDFs should remain fast and should not pay an OCR cost unless their extracted text is sparse.

## Current State

The app already stores uploads, extracts native PDF text with PyMuPDF, chunks pages, embeds chunks with the local embedding model, and returns cited answers through pgvector-backed retrieval. Image uploads are stored with `deferred_ocr`, and low-text PDFs surface parse-quality warnings such as "This PDF has very little extractable text and may need OCR."

The current database is created from SQLAlchemy models through `Base.metadata.create_all()`. There is no migration system yet, so schema changes in this phase must be additive and small.

## Scope

This phase adds local OCR execution and makes ingestion more observable.

- Process image uploads instead of always marking them `deferred_ocr`.
- For PDFs, keep native text extraction as the first pass.
- OCR only pages with little or no native text, so text PDFs stay fast.
- Merge native text and OCR text into the same page, chunk, embedding, and search pipeline.
- Store enough OCR metadata for document quality reporting.
- Show richer document status and quality information in the web UI.
- Let users retry OCR/reindexing from the Documents page.
- Add golden evaluation cases for OCR-ready ingestion behavior and hard negative search behavior.

## Non-Goals

- No paid OCR APIs.
- No authentication or cloud storage.
- No layout-aware form extraction, table reconstruction, or bounding-box overlays.
- No model training or FUNSD fine-tuning.
- No background worker service in this phase. Indexing can remain request-driven, with status updates persisted during the request.

## OCR Engine Strategy

Use a local OCR provider abstraction with a Tesseract-backed implementation.

`OcrProvider` exposes:

```python
class OcrProvider(Protocol):
    engine_name: str

    def is_available(self) -> bool:
        ...

    def ocr_image(self, image: Image.Image, *, language: str) -> OcrPageResult:
        ...
```

`OcrPageResult` contains:

```python
@dataclass(frozen=True)
class OcrPageResult:
    text: str
    confidence: float | None
    engine_name: str
    duration_ms: int
```

The provider should detect availability from:

- `DOCINTEL_OCR_ENABLED`, default `true`.
- `DOCINTEL_TESSERACT_CMD`, optional path to `tesseract.exe`.
- A normal `tesseract` executable on `PATH`.

If OCR is requested but unavailable, image uploads stay `deferred_ocr` because they have no native text path. PDFs stay searchable from native text when chunks exist; PDFs with no usable native chunks become `failed` with this actionable message: "Local OCR is not available. Install Tesseract or set DOCINTEL_TESSERACT_CMD, then retry OCR."

## PDF Extraction Flow

PDF ingestion should use a hybrid flow:

1. Parse every page with PyMuPDF native text extraction.
2. Build the existing parse-quality profile.
3. Select OCR candidate pages where normalized text length is below the low-text threshold.
4. If candidate pages exist and OCR is enabled, render only those pages to images.
5. Run OCR with a bounded DPI and page timeout.
6. Merge the page text:
   - Use native text when it is good enough.
   - Use OCR text when native text is sparse and OCR returns useful text.
   - Keep sparse native text if OCR is unavailable or returns no usable text.
7. Persist pages, chunks, and embeddings from the merged text.

The PDF parser should stop rejecting all-empty PDFs before OCR has a chance to run. The "no extractable text" error should move from the parser into the indexing service after the hybrid OCR step fails to produce usable chunks.

## Image Extraction Flow

Image uploads should use the same OCR provider:

1. Persist the uploaded image as a document.
2. Validate it can be opened by Pillow.
3. OCR the image as page 1.
4. Create one `Page` row, chunks, and embeddings.
5. Mark the document `indexed` when chunks exist.

If OCR is unavailable, the image document should keep a deferred OCR status with an actionable message. If OCR runs but produces no usable text, mark it failed with "OCR completed but no usable text was found."

## Status Model

Keep existing statuses compatible, but add more precise statuses where they improve user trust:

- `uploaded`
- `processing`
- `ocr_processing`
- `indexed`
- `deferred_ocr`
- `failed`

The API should continue returning `status` as a string. The web app should display `ocr_processing` as "OCR running".

## OCR Metadata

Add optional OCR metadata to `Page`:

- `text_source`: `native`, `ocr`, or `hybrid`
- `ocr_engine`: nullable string
- `ocr_confidence`: nullable float
- `ocr_duration_ms`: nullable integer

Add optional ingestion metadata to `Document`:

- `processing_started_at`: nullable datetime
- `processing_completed_at`: nullable datetime
- `processing_duration_ms`: nullable integer

Because there is no migration framework, these columns must be added through additive model changes plus a small startup schema synchronization helper that uses SQLAlchemy inspection to add missing columns for local development databases.

## Quality Report

Extend parse quality with OCR-aware fields:

- `ocr_page_count`
- `native_text_page_count`
- `hybrid_page_count`
- `ocr_confidence_average`
- `ocr_duration_ms`
- `text_source_summary`

The existing fields remain stable so the frontend does not break:

- `page_count`
- `text_page_count`
- `empty_page_count`
- `total_characters`
- `average_characters_per_page`
- `low_text_page_ratio`
- `scanned_likelihood`
- `warnings`

Warnings should distinguish between "OCR recommended", "OCR unavailable", and "OCR produced low-confidence text".

## Performance Guardrails

OCR can be slow, so the implementation must include guardrails:

- Default render DPI: `200`.
- Default max OCR pages per document: `25`.
- Default OCR page timeout seconds: `20`.
- Skip OCR on pages with enough native text.
- Fail gracefully if an image cannot be opened.
- Keep embedding model loading after extraction succeeds.
- Do not retry OCR indefinitely during a single request.

The settings should be configurable:

- `DOCINTEL_OCR_ENABLED`
- `DOCINTEL_OCR_LANGUAGE`
- `DOCINTEL_OCR_DPI`
- `DOCINTEL_OCR_MAX_PAGES`
- `DOCINTEL_OCR_PAGE_TIMEOUT_SECONDS`
- `DOCINTEL_TESSERACT_CMD`

## Search and Answer Behavior

Search should not need a separate OCR search path. OCR text becomes normal page and chunk text, so existing retrieval, reranking, document-aware answers, diagnostics, and citations continue to work.

When a document has no chunks because OCR is deferred or failed, scoped search should return insufficient evidence with a clear reason. It should not show a generic fetch failure.

## Web UI

The Documents page should show:

- OCR status badge for `ocr_processing` and `deferred_ocr`.
- OCR page count and text source summary in the quality panel.
- Processing duration when available.
- A Retry OCR/Reindex action for PDFs and images when OCR is deferred, failed, or quality is poor.

The Search page should show a scoped-document warning when a selected document is not indexed yet because OCR is unavailable or failed.

The Evaluation page should include OCR-related quality cases so regressions are visible alongside the existing universal document QA suite.

## Testing Strategy

Use test doubles for OCR engine behavior so the suite does not require Tesseract to be installed.

Backend tests:

- PDF parser returns sparse pages instead of failing before OCR.
- Hybrid extraction OCRs only sparse pages.
- Image uploads become indexed when the fake OCR provider returns text.
- Image uploads remain `deferred_ocr` when OCR is unavailable.
- Reindex replaces old pages, chunks, embeddings, and OCR metadata.
- OCR metadata appears in document reads and parse-quality reports.
- Search on OCR-indexed chunks returns cited evidence.
- Scoped search on deferred OCR documents returns insufficient evidence, not a frontend fetch-style failure.

Frontend tests:

- Status badge renders `ocr_processing`.
- Document list displays OCR quality fields.
- Retry OCR/Reindex is available for PDFs and images when status is `deferred_ocr` or `failed`, and for PDFs whose parse quality has `scanned_likelihood` of `medium` or `high`.
- Search page displays OCR-related scoped document guidance.
- Evaluation summary includes OCR quality cases.

Verification commands:

```powershell
pytest apps/api/tests
npm --prefix apps/web test
npm --prefix apps/web run lint
npm --prefix apps/web run build
git diff --check
```

## Rollout Notes

This phase should remain local-first. If Tesseract is not installed, the app still works for normal text PDFs and clearly explains how to enable OCR. After this lands, the next phase can consider layout-aware OCR, table extraction, and bounding-box previews.
