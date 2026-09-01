# Product Grade Workspace Quality Design

**Goal:** Make DocIntel AI feel like a polished, trustworthy document intelligence workspace while improving text-PDF processing speed, retrieval accuracy, diagnostics, and evaluation coverage.

## Scope

This phase upgrades the existing local-first FastAPI, PostgreSQL, pgvector, and Next.js application. It keeps the app extractive and cited, but makes the product feel more complete and makes the backend more reliable for common text-based PDFs.

In scope:
- Academic Teal + Ink + Amber visual identity across the app.
- A custom DocIntel AI logo mark and improved wordmark treatment.
- Shared interactive UI primitives for buttons, panels, badges, inputs, tabs, and evidence cards.
- A subtle desktop cursor spotlight effect that respects reduced-motion preferences and does not run on touch-first devices.
- Redesigned Dashboard, Documents, Search, and Evaluation pages.
- Cleaner search result structure that separates answer evidence, related evidence, and diagnostics.
- Text-PDF parse quality profiling, including page count, text density, empty-page ratio, extraction warnings, and scanned-PDF likelihood.
- Faster and cleaner ingestion for text PDFs by batching database writes where practical and trimming junk chunks before embedding.
- Improved chunk metadata for section quality, text density, heading confidence, and extraction quality.
- Stronger query routing for research, invoice, contract, resume, report, and generic evidence-search intents.
- More human-readable backend diagnostics that avoid exposing raw internal chunk IDs in the UI.
- Expanded golden evaluation cases for retrieval quality, hard negatives, parser quality flags, and UI-safe diagnostics.

Out of scope:
- Full OCR for scanned PDFs. Scanned-PDF detection and user-facing OCR guidance are included, but OCR execution is deferred to the next phase.
- External LLM generation or paid hosted APIs.
- Authentication, cloud deployment, and multi-user projects.
- A large background job queue unless current synchronous ingestion blocks the planned improvements.

## Visual Identity

The chosen palette is Academic Teal + Ink + Amber:
- Primary teal: `#0F766E`
- Deep teal: `#115E59`
- Ink text: `#111827`
- Slate text: `#475569`
- App background: `#F8FAFC`
- Surface: `#FFFFFF`
- Soft teal surface: `#ECFDF5`
- Border: `#CBD5E1`
- Amber accent: `#D97706`
- Success: `#059669`
- Warning: `#F59E0B`
- Error: `#DC2626`

The logo mark will be a compact inline SVG or CSS-backed React component. It should combine a document outline with a citation or intelligence-node motif. The wordmark should use a clean modern font stack and stronger weight contrast than the current plain text label.

The UI should feel professional and lively, not like a marketing page. It should use restrained motion, purposeful color, scan-friendly spacing, and clear information hierarchy.

## Frontend Architecture

The frontend will introduce a small design system inside the existing Next.js app:
- `components/ui/button.tsx` for reusable button variants, loading state, icon support, focus styles, and pressed interactions.
- `components/ui/badge.tsx` for status, metadata, and confidence labels.
- `components/ui/panel.tsx` for page sections and repeated cards.
- `components/docintel-logo.tsx` for the logo mark and wordmark.
- `components/cursor-spotlight.tsx` for the desktop-only pointer glow.

Existing feature components will consume those primitives instead of duplicating border, color, and hover styles. The redesign should keep cards at modest border radii and avoid nested card layouts.

Page changes:
- Dashboard: convert the home page into a workspace overview with document count, indexed count, evaluation health, upload/search shortcuts, and a more confident first impression.
- Documents: improve upload affordance, document status scanning, parse-quality warnings, and reindex/delete actions.
- Search: promote the answer panel, make citations scannable, group answer evidence separately from related evidence, hide noisy diagnostics behind polished copy, and keep suggested questions easy to use.
- Evaluation: make pass rate, coverage, abstentions, failures, and document-type filters visually clear.

## Backend Architecture

The backend will remain local-first and deterministic. It should improve speed and quality without replacing the current pipeline.

PDF profiling:
- Add a parse profile derived from extracted pages before chunking.
- Track page count, pages with text, empty pages, total characters, average characters per page, low-text pages, scanned-likelihood, and warnings.
- Expose profile data in document read/list APIs so the frontend can show useful quality status.

Ingestion quality and speed:
- Filter empty and near-empty chunks before embedding.
- Normalize repeated whitespace and hyphenation artifacts more consistently.
- Batch page, chunk, and embedding persistence where it keeps the code clear.
- Avoid embedding when there are no usable chunks and return a clear parse quality failure.

Retrieval quality:
- Keep vector retrieval as the base.
- Preserve reranker signals, but improve human-readable diagnostics.
- Make answer evidence promotion explicit in response metadata.
- Expand query intent detection for amounts, parties, dates, summaries, methods, datasets, results, limitations, skills, projects, findings, risks, and recommendations.
- For document-type mismatches, return a clear abstention with better suggested questions.

Evaluation:
- Add golden cases for parse-quality warnings and human-readable diagnostics.
- Keep tests deterministic and in-memory where possible.
- Continue to verify answerability, citations, confidence, document type, query intent, and expected evidence keywords.

## Data Flow

Upload flow:
1. User uploads a PDF.
2. Backend stores the file and creates a processing document record.
3. Parser extracts page text and parse metadata.
4. Profile builder identifies text quality and scanned-PDF likelihood.
5. Chunker creates structured chunks and drops unusable chunks.
6. Embedder embeds usable chunks.
7. Database stores pages, chunks, embeddings, and parse-quality metadata.
8. Documents API returns indexing status and quality warnings.

Search flow:
1. User asks a question in a scoped document or across all documents.
2. Query router detects intent, optionally using document type.
3. Retrieval fetches vector candidates.
4. Reranker applies section, keyword, and document-type signals.
5. Document-aware answer builder either returns cited extractive answer evidence or abstains.
6. Diagnostics are translated into user-safe labels and reasons.
7. Frontend renders answer evidence, related evidence, suggested questions, and expandable diagnostics.

## Error Handling

- Scanned or low-text PDFs should not fail with a generic error. They should show a clear message that OCR is needed in a future phase.
- Backend errors should remain concise and user-safe.
- Search should gracefully handle empty document sets, deleted documents, insufficient evidence, and network failures.
- UI controls should show loading and disabled states during upload, reindex, delete, and search actions.

## Testing

Backend tests:
- Parser profile unit tests for text PDFs, low-text PDFs, and empty PDFs.
- Chunker tests for junk-chunk filtering and metadata.
- Documents API tests for profile fields and scanned-PDF warnings.
- Search API tests for user-safe diagnostics and answer evidence grouping.
- Query router tests for expanded intents.
- Golden evaluation tests for parse-quality and diagnostics cases.

Frontend tests:
- UI primitive tests for button loading, disabled state, and accessible labels.
- App shell/logo tests.
- Search page and search results tests for answer evidence, related evidence, diagnostics, and hard negatives.
- Documents page tests for parse-quality status and upload/reindex/delete states.
- Evaluation page tests for summary cards, filters, and failure/pass rendering.

Full verification:
- API test suite passes.
- Web test suite passes.
- Web lint passes.
- Web build passes.
- `git diff --check` passes.

## Success Criteria

- The app no longer reads as a plain white prototype.
- All primary pages share a coherent Academic Teal + Ink + Amber visual system.
- Buttons and interactive controls feel responsive and accessible.
- Cursor tracking adds polish without blocking usability or accessibility.
- Search answers remain cited and extractive.
- Search diagnostics are useful to users and do not expose raw internal chunk IDs.
- Text-PDF ingestion is cleaner and more robust.
- Low-quality or scanned PDFs receive clear guidance.
- Golden evaluation covers backend quality improvements, not only UI rendering.
- Existing Phase 3 behavior continues to pass.
