# Layout-Aware Evidence And Faster OCR Design

## Goal

Make DocIntel AI feel more like a source-grounded document intelligence product by connecting answers to inspectable source pages, highlighting cited chunks, and improving OCR routing for mixed native/scanned documents.

## Scope

This phase builds on the existing page preview, OCR diagnostics, document workbench, and search result separation.

1. Search results expose source preview metadata for every hit.
2. Search result cards let users preview the cited page inline with zoom controls.
3. Citation/open-page links deep-link to the selected page and chunk.
4. The document workbench highlights a cited chunk when opened from search.
5. Page diagnostics expose a stable page processing status derived from current page/chunk/OCR fields.
6. PDF OCR routing is centralized in a tested helper so dense native-text pages are skipped, sparse/scanned pages are OCR candidates, and the max-page cap is deterministic.
7. Image OCR preprocessing applies orientation normalization before grayscale, contrast, upscale, and sharpen steps.

## Out Of Scope

- No database migration.
- No persistent OCR bounding boxes.
- No paid OCR or cloud document APIs.
- No background worker service.
- No manual annotation/review workflow.
- No full PDF canvas text selection layer.

## Backend Design

`documents.router` continues to derive page diagnostics dynamically. It will add `processing_status` to `DocumentPageRead`, using only `Page.text`, `Page.text_source`, chunk count, and OCR confidence. This keeps old indexed rows compatible.

`retrieval.search` will add `page_image_url` and `document_page_url` to `SearchHitRead`. The formatter can derive both from `document_id`, `page_number`, and `chunk_id`, so no retrieval query changes are needed. `document_page_url` points to `/documents/{document_id}?page={page_number}&chunk={chunk_id}` for frontend deep links.

`documents.extraction` will introduce `should_ocr_pdf_page()` and `pdf_ocr_page_numbers()` as small policy helpers. `extract_pdf_pages()` will call them instead of owning the routing logic inline. The policy is deterministic: OCR only sparse native-text pages, never pages with enough usable text, and never more than `max_ocr_pages`.

`documents.ocr.prepare_image_for_ocr()` will apply EXIF orientation normalization before preprocessing. This improves phone/photo scans without changing caller contracts.

## Frontend Design

`SearchResults` becomes the first place users can inspect source pages. Each evidence card keeps the current answer/result content and adds a compact source preview action. Opening it reveals a local page image with zoom in, zoom out, and reset controls. The preview uses the `page_image_url` from the API.

`Open page` links use `document_page_url` when available. That URL includes the cited `chunk` id.

`DocumentWorkbenchPage` parses both `page` and `chunk` query params and passes them to `DocumentWorkbench`. The workbench opens the evidence tab for deep links, selects the requested page, marks the cited chunk as selected, and shows a "Selected citation" badge.

Page list cards show the new `processing_status` label and retain the existing OCR quality/review signals.

## Error Handling

If a hit has no `page_image_url`, the source preview action is hidden. If the image fails to load, the browser shows the normal broken image state and the user can still open the page link.

If a deep-linked chunk id is not present in the loaded chunks, the workbench still selects the requested page and renders normally.

## Testing

Backend tests cover:
- Page diagnostics include `processing_status`.
- Search hit formatting includes `page_image_url` and `document_page_url`.
- PDF OCR routing skips dense pages and caps sparse page OCR deterministically.
- Image preprocessing applies orientation normalization without breaking existing grayscale/upscale behavior.

Frontend tests cover:
- Search evidence cards can open a page preview using `page_image_url`.
- Preview zoom controls update the visible zoom state.
- Search open-page links include `page`, `chunk`, and use `document_page_url`.
- Document workbench deep links highlight the selected chunk.
- Page cards show processing status labels.
