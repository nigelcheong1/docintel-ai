# Product Grade Workspace Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refresh DocIntel AI into a polished Academic Teal + Ink + Amber workspace while improving text-PDF parse quality, ingestion cleanliness, search diagnostics, and evaluation coverage.

**Architecture:** Keep the existing local-first FastAPI, SQLAlchemy, pgvector, and Next.js architecture. Add computed parse-quality contracts without a database migration, tighten chunk/search quality in backend services, and introduce small frontend UI primitives that existing pages consume. Use TDD for each behavior change.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy, PyMuPDF, pytest, Next.js, React, TypeScript, Vitest, Testing Library, Tailwind CSS, lucide-react.

**Spec:** `docs/superpowers/specs/2026-09-01-product-grade-workspace-quality-design.md`

## Global Constraints

- Use Academic Teal + Ink + Amber: primary `#0F766E`, deep teal `#115E59`, ink `#111827`, slate `#475569`, background `#F8FAFC`, surface `#FFFFFF`, border `#CBD5E1`, amber `#D97706`, success `#059669`, warning `#F59E0B`, error `#DC2626`.
- Keep answers extractive and cited.
- Defer full OCR to the next phase.
- Add scanned-PDF and low-text detection without introducing OCR execution.
- Avoid a database migration in this phase; compute parse quality from existing pages, chunks, document status, and error message.
- Do not expose raw internal chunk IDs in user-facing diagnostics.
- Keep `apps/web/next-env.d.ts` out of commits because it is generated locally.
- Every backend and frontend behavior change starts with a failing test.

---

### Task 1: Backend Parse Quality Contract

**Files:**
- Create: `apps/api/app/documents/parse_quality.py`
- Modify: `apps/api/app/documents/parser.py`
- Modify: `apps/api/app/documents/schemas.py`
- Modify: `apps/api/app/documents/router.py`
- Test: `apps/api/tests/documents/test_parse_quality.py`
- Test: `apps/api/tests/documents/test_parser.py`
- Test: `apps/api/tests/documents/test_router.py`

**Interfaces:**
- Produces: `ParseQualityRead` Pydantic model with `page_count: int`, `text_page_count: int`, `empty_page_count: int`, `total_characters: int`, `average_characters_per_page: float`, `low_text_page_ratio: float`, `scanned_likelihood: Literal["low", "medium", "high"]`, `warnings: list[str]`.
- Produces: `build_parse_quality_from_pages(pages: Sequence[ParsedPage]) -> ParseQualityRead`.
- Produces: `build_parse_quality_for_document(document: Document) -> ParseQualityRead`.
- Consumes: existing `ParsedPage`, `Document`, `Page`, and document router read models.

- [ ] **Step 1: Write failing parse-quality unit tests**

```python
from app.documents.parse_quality import build_parse_quality_from_pages
from app.documents.parser import ParsedPage


def test_parse_quality_marks_text_pdf_as_low_scan_likelihood():
    profile = build_parse_quality_from_pages([
        ParsedPage(page_number=1, text="Invoice total due is RM 1,200.00 " * 20, width=300, height=200),
        ParsedPage(page_number=2, text="Payment terms are net 30 days " * 20, width=300, height=200),
    ])

    assert profile.page_count == 2
    assert profile.text_page_count == 2
    assert profile.empty_page_count == 0
    assert profile.scanned_likelihood == "low"
    assert profile.warnings == []


def test_parse_quality_warns_for_sparse_text_pdf():
    profile = build_parse_quality_from_pages([
        ParsedPage(page_number=1, text=".", width=300, height=200),
        ParsedPage(page_number=2, text="", width=300, height=200),
    ])

    assert profile.low_text_page_ratio == 1
    assert profile.scanned_likelihood == "high"
    assert "This PDF has very little extractable text and may need OCR." in profile.warnings
```

- [ ] **Step 2: Run tests to verify RED**

Run: `python -m pytest apps/api/tests/documents/test_parse_quality.py -q`

Expected: FAIL because `app.documents.parse_quality` does not exist.

- [ ] **Step 3: Implement parse-quality helpers**

Create `parse_quality.py` with:
- `ScanLikelihood = Literal["low", "medium", "high"]`
- `_density_for_page(page: ParsedPage) -> int`
- `build_parse_quality_from_pages(...)`
- `build_parse_quality_for_document(...)`

Rules:
- `page_count` is total pages.
- `text_page_count` counts pages with at least 20 non-whitespace characters.
- `empty_page_count` counts pages with no extracted text after stripping.
- `low_text_page_ratio` counts pages below 80 characters divided by page count.
- `scanned_likelihood` is `high` when all pages are empty or low-text ratio is at least `0.75`, `medium` when low-text ratio is at least `0.35`, otherwise `low`.
- Add warning `"This PDF has very little extractable text and may need OCR."` for high likelihood.
- Add warning `"Some pages have sparse extractable text."` for medium likelihood.

- [ ] **Step 4: Add schema field tests**

Extend router tests to expect `parse_quality` on `GET /documents` and `GET /documents/{document_id}`:

```python
assert response.json()[0]["parse_quality"]["scanned_likelihood"] == "low"
assert detail_response.json()["parse_quality"]["page_count"] == 1
```

Run: `python -m pytest apps/api/tests/documents/test_router.py -q`

Expected: FAIL because API responses do not include `parse_quality`.

- [ ] **Step 5: Add parse-quality schema and router mapping**

Modify `DocumentRead`:

```python
class ParseQualityRead(BaseModel):
    page_count: int
    text_page_count: int
    empty_page_count: int
    total_characters: int
    average_characters_per_page: float
    low_text_page_ratio: float
    scanned_likelihood: Literal["low", "medium", "high"]
    warnings: list[str]

class DocumentRead(BaseModel):
    ...
    parse_quality: ParseQualityRead | None = None
```

Add router helper:

```python
def document_read(document: Document) -> DocumentRead:
    return DocumentRead(
        id=document.id,
        filename=document.filename,
        mime_type=document.mime_type,
        status=document.status.value,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
        parse_quality=build_parse_quality_for_document(document),
    )
```

Use it for list, upload, reindex, and detail responses.

- [ ] **Step 6: Run focused tests to verify GREEN**

Run:

```powershell
python -m pytest apps/api/tests/documents/test_parse_quality.py apps/api/tests/documents/test_parser.py apps/api/tests/documents/test_router.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/api/app/documents/parse_quality.py apps/api/app/documents/parser.py apps/api/app/documents/schemas.py apps/api/app/documents/router.py apps/api/tests/documents/test_parse_quality.py apps/api/tests/documents/test_parser.py apps/api/tests/documents/test_router.py
git commit -m "feat: expose pdf parse quality"
```

### Task 2: Cleaner Chunking and Faster Index Persistence

**Files:**
- Modify: `apps/api/app/documents/chunker.py`
- Modify: `apps/api/app/documents/service.py`
- Test: `apps/api/tests/documents/test_chunker.py`
- Test: `apps/api/tests/documents/test_service.py`

**Interfaces:**
- Produces: `is_usable_chunk_text(text: str) -> bool`.
- Produces: chunk layout keys `text_density`, `heading_confidence`, and `quality`.
- Consumes: `chunk_pages()` output in document indexing.

- [ ] **Step 1: Write failing chunk filter tests**

Add tests:

```python
from app.documents.chunker import chunk_pages, is_usable_chunk_text
from app.documents.parser import ParsedPage


def test_chunk_pages_skips_junk_text_windows():
    chunks = chunk_pages([
        ParsedPage(page_number=1, text="1 2 3\n.\n-\nValid invoice payment terms with enough useful words.", width=300, height=200)
    ], chunk_size=12, overlap=0)

    assert all(is_usable_chunk_text(chunk.text) for chunk in chunks)
    assert any("Valid invoice payment terms" in chunk.text for chunk in chunks)


def test_chunk_layout_includes_quality_metadata():
    chunk = chunk_pages([
        ParsedPage(page_number=1, text="METHOD\nThis section describes the model architecture and encoder.", width=300, height=200)
    ])[0]

    assert chunk.layout["quality"] == "usable"
    assert chunk.layout["text_density"] > 0
    assert chunk.layout["heading_confidence"] in {"explicit", "inferred", "none"}
```

Run: `python -m pytest apps/api/tests/documents/test_chunker.py -q`

Expected: FAIL because `is_usable_chunk_text` and layout keys are missing.

- [ ] **Step 2: Implement chunk quality metadata**

In `chunker.py`:
- Add `is_usable_chunk_text(text)` requiring at least 4 word tokens and at least 16 alphabetic characters.
- Add `text_density` as alphabetic character count divided by total non-space character count.
- Add `heading_confidence` as `"explicit"` when `section.heading` exists, otherwise `"none"`.
- Skip chunks that fail `is_usable_chunk_text`.
- Keep existing section-heading behavior.

- [ ] **Step 3: Run chunker tests to verify GREEN**

Run: `python -m pytest apps/api/tests/documents/test_chunker.py -q`

Expected: PASS.

- [ ] **Step 4: Write failing service tests for no usable chunks**

Add:

```python
def test_index_stored_upload_fails_cleanly_when_pdf_has_no_usable_chunks(db_session, tmp_path):
    pdf_path = tmp_path / "sparse.pdf"
    content = create_sample_pdf(pdf_path, ".")
    stored = save_upload_bytes("sparse.pdf", "application/pdf", content, tmp_path / "storage", 20)

    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())

    assert document.status == DocumentStatus.FAILED
    assert "not enough usable text" in (document.error_message or "").lower()
```

Run: `python -m pytest apps/api/tests/documents/test_service.py -q`

Expected: FAIL because indexing currently embeds whatever chunks exist or fails with a generic path.

- [ ] **Step 5: Improve index persistence**

In `_add_pdf_index_records()`:
- Parse pages.
- Build text chunks.
- If no chunks remain, raise `DocumentParseError("This PDF does not contain enough usable text for local search. It may need OCR.")`.
- Use `db.add_all(page_objects)` and `db.flush()` once for pages.
- Embed all chunk texts in one call as today.
- Create all `Chunk` rows, `db.add_all(chunks)`, `db.flush()` once.
- Create all `ChunkEmbedding` rows and `db.add_all(embeddings)`.

- [ ] **Step 6: Run service tests to verify GREEN**

Run:

```powershell
python -m pytest apps/api/tests/documents/test_chunker.py apps/api/tests/documents/test_service.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/api/app/documents/chunker.py apps/api/app/documents/service.py apps/api/tests/documents/test_chunker.py apps/api/tests/documents/test_service.py
git commit -m "feat: improve pdf chunk quality"
```

### Task 3: Search Diagnostics and Intent Quality

**Files:**
- Modify: `apps/api/app/retrieval/query_router.py`
- Modify: `apps/api/app/retrieval/router.py`
- Modify: `apps/api/app/retrieval/reranker.py`
- Modify: `apps/api/app/retrieval/search.py`
- Test: `apps/api/tests/retrieval/test_query_router.py`
- Test: `apps/api/tests/retrieval/test_search_api.py`
- Test: `apps/api/tests/retrieval/test_reranker.py`

**Interfaces:**
- Produces: user-safe `SearchDiagnostics.top_rejected_reasons`.
- Produces: expanded `route_query()` intents for `authors`, `contributions`, `findings`, `recommendations`, `payment_due`, and `unknown_domain`.
- Consumes: current `SearchResponse`, `AnswerQuality`, and `SearchHit` models.

- [ ] **Step 1: Write failing query-router tests**

Add tests:

```python
def test_route_query_detects_research_contributions():
    route = route_query("What are the main contributions?")
    assert route.intent == "contributions"
    assert "overview" in route.preferred_section_intents or "method" in route.preferred_section_intents


def test_route_query_detects_invoice_payment_due_separately():
    route = route_query("What total amount is due?", "research_paper")
    assert route.intent == "amounts"
    assert route.mismatch_reason is not None
```

Run: `python -m pytest apps/api/tests/retrieval/test_query_router.py -q`

Expected: FAIL for missing or weaker intent coverage.

- [ ] **Step 2: Expand route rules conservatively**

Add route rules:
- `authors`: terms `author`, `authors`, `who wrote`, preferred sections `overview`.
- `contributions`: terms `contribution`, `contributions`, `novel`, `propose`, `introduced`, preferred sections `overview`, `method`.
- `findings`: terms `finding`, `findings`, `insight`, preferred sections `result`.
- `recommendations`: keep existing but include `next steps`.
- `payment_due`: terms `payment due`, `when is payment due`, preferred sections `date`, `payment`.

Keep existing behavior for current golden tests.

- [ ] **Step 3: Write failing diagnostics test for user-safe rejected reasons**

In `test_search_api.py`, assert:

```python
assert all(":" not in reason for reason in payload["diagnostics"]["top_rejected_reasons"])
assert "Related evidence was not cited because" in payload["diagnostics"]["top_rejected_reasons"][0]
```

Run: `python -m pytest apps/api/tests/retrieval/test_search_api.py -q`

Expected: FAIL because rejected reasons currently include raw chunk IDs.

- [ ] **Step 4: Replace raw chunk diagnostics**

In `_build_search_diagnostics()`:
- Replace `"{chunk_id}: not cited in the answer"` with messages such as:
  - `"Related evidence was not cited because it ranked below the selected answer evidence."`
  - `"Related evidence matched the topic but not the requested answer intent."`
  - `"Related evidence was kept for context only."`
- Do not expose `chunk_id` inside `top_rejected_reasons`.

- [ ] **Step 5: Improve reranker signal names without breaking old data**

Keep `keyword_overlap` and `section_intent`. Add optional `document_focus` when scoped to a document is not needed in this phase, so do not change reranker function signature unless tests demand it.

- [ ] **Step 6: Run focused tests to verify GREEN**

Run:

```powershell
python -m pytest apps/api/tests/retrieval/test_query_router.py apps/api/tests/retrieval/test_search_api.py apps/api/tests/retrieval/test_reranker.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```powershell
git add apps/api/app/retrieval/query_router.py apps/api/app/retrieval/router.py apps/api/app/retrieval/reranker.py apps/api/app/retrieval/search.py apps/api/tests/retrieval/test_query_router.py apps/api/tests/retrieval/test_search_api.py apps/api/tests/retrieval/test_reranker.py
git commit -m "feat: refine search diagnostics and intents"
```

### Task 4: Backend Golden Evaluation Expansion

**Files:**
- Modify: `apps/api/app/evaluation/golden.py`
- Modify: `apps/api/app/evaluation/metrics.py`
- Test: `apps/api/tests/evaluation/test_golden_eval.py`
- Test: `apps/api/tests/evaluation/test_metrics.py`

**Interfaces:**
- Produces: golden cases that cover parse quality, diagnostics, hard negatives, and user-safe output.
- Consumes: current `/eval/golden` response schema.

- [ ] **Step 1: Write failing golden eval tests**

Add expectations:

```python
def test_golden_eval_includes_user_safe_diagnostics_case():
    response = run_golden_evaluation()
    case = next(item for item in response.cases if item.case_id == "research-hard-negative-total-due")
    assert case.passed
    assert "chunk" not in case.quality_reason.lower()


def test_golden_eval_reports_quality_dimensions():
    response = run_golden_evaluation()
    assert response.summary.quality_dimensions["answer_quality"] >= 1
    assert response.summary.quality_dimensions["abstention_safety"] >= 1
    assert response.summary.quality_dimensions["parse_quality"] >= 1
```

Run: `python -m pytest apps/api/tests/evaluation/test_golden_eval.py -q`

Expected: FAIL until cases and summary fields are updated.

- [ ] **Step 2: Add deterministic cases**

Add `quality_dimensions: dict[str, int]` to `GoldenEvalSummary`.

Add `quality_dimension: str = "answer_quality"` to `GoldenCaseSpec`.

Assign:
- Existing answerable cases: `answer_quality`.
- Existing hard-negative cases: `abstention_safety`.
- New case `parse-quality-low-text-guidance`: `parse_quality`.

The new parse-quality case should use `build_parse_quality_from_pages()` with sparse extracted text and pass when the profile has `scanned_likelihood == "high"` and includes `"This PDF has very little extractable text and may need OCR."`.

- [ ] **Step 3: Run evaluation tests to verify GREEN**

Run:

```powershell
python -m pytest apps/api/tests/evaluation/test_golden_eval.py apps/api/tests/evaluation/test_metrics.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add apps/api/app/evaluation/golden.py apps/api/app/evaluation/metrics.py apps/api/tests/evaluation/test_golden_eval.py apps/api/tests/evaluation/test_metrics.py
git commit -m "test: expand golden quality coverage"
```

### Task 5: Frontend Design System Foundation

**Files:**
- Create: `apps/web/components/ui/button.tsx`
- Create: `apps/web/components/ui/badge.tsx`
- Create: `apps/web/components/ui/panel.tsx`
- Create: `apps/web/components/docintel-logo.tsx`
- Create: `apps/web/components/cursor-spotlight.tsx`
- Modify: `apps/web/app/globals.css`
- Modify: `apps/web/tailwind.config.ts`
- Modify: `apps/web/components/app-shell.tsx`
- Test: `apps/web/tests/ui-button.test.tsx`
- Test: `apps/web/tests/app-shell.test.tsx`

**Interfaces:**
- Produces: `Button` component with props `variant?: "primary" | "secondary" | "ghost" | "danger"`, `isLoading?: boolean`, `leftIcon?: ReactNode`, `rightIcon?: ReactNode`.
- Produces: `Badge` component with props `tone?: "neutral" | "teal" | "amber" | "success" | "danger"`.
- Produces: `Panel` component with props `tone?: "default" | "soft" | "accent"`.
- Produces: `DocIntelLogo`.
- Produces: `CursorSpotlight`.

- [ ] **Step 1: Write failing UI primitive tests**

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Button } from "@/components/ui/button";

describe("Button", () => {
  it("shows loading state and keeps the accessible name", () => {
    render(<Button isLoading>Search</Button>);
    expect(screen.getByRole("button", { name: /Search/ })).toBeDisabled();
    expect(screen.getByText("Search")).toBeInTheDocument();
  });
});
```

Run: `npm --prefix apps/web test -- ui-button.test.tsx`

Expected: FAIL because `Button` does not exist.

- [ ] **Step 2: Implement UI primitives**

Use React components with Tailwind classes. Button requirements:
- Stable rounded `rounded-md`, not oversized pill styling.
- `transition`, `focus-visible:ring-2`, `active:translate-y-px`.
- Loading spinner using CSS class `.docintel-spinner`.
- Disabled state prevents interaction and lowers contrast.

Global CSS requirements:
- Add CSS variables for palette.
- Add body background with subtle non-dominant surface gradient.
- Add `.cursor-spotlight` support with `prefers-reduced-motion` guard.
- Keep font size responsive through Tailwind breakpoints, not viewport units.

- [ ] **Step 3: Write failing AppShell/logo tests**

Extend `app-shell.test.tsx`:

```tsx
expect(screen.getByLabelText("DocIntel AI home")).toBeInTheDocument();
expect(screen.getByText("DocIntel")).toBeInTheDocument();
expect(screen.getByText("AI")).toBeInTheDocument();
```

Run: `npm --prefix apps/web test -- app-shell.test.tsx`

Expected: FAIL until logo and shell are updated.

- [ ] **Step 4: Implement shell redesign**

In `AppShell`:
- Render `CursorSpotlight`.
- Use `DocIntelLogo`.
- Use sidebar with ink background or soft teal surface, not plain white.
- Highlight active-style navigation through hover/focus states where possible without needing `usePathname` tests. If using `usePathname`, keep `AppShell` client-side.
- Keep mobile navigation accessible.

- [ ] **Step 5: Run focused web tests to verify GREEN**

Run:

```powershell
npm --prefix apps/web test -- ui-button.test.tsx app-shell.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/components/ui/button.tsx apps/web/components/ui/badge.tsx apps/web/components/ui/panel.tsx apps/web/components/docintel-logo.tsx apps/web/components/cursor-spotlight.tsx apps/web/app/globals.css apps/web/tailwind.config.ts apps/web/components/app-shell.tsx apps/web/tests/ui-button.test.tsx apps/web/tests/app-shell.test.tsx
git commit -m "feat: add docintel design system"
```

### Task 6: Frontend Data Contract for Parse Quality

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/tests/api-client.test.ts`
- Test: `apps/web/tests/documents-page.test.tsx`
- Test: `apps/web/tests/document-list.test.tsx`

**Interfaces:**
- Consumes: backend `parse_quality`.
- Produces: TypeScript `ParseQuality` and updated `DocumentSummary`.

- [ ] **Step 1: Write failing type/API tests**

Add API fixture assertion:

```tsx
expect(document.parse_quality?.scanned_likelihood).toBe("low");
expect(document.parse_quality?.warnings).toEqual([]);
```

Run: `npm --prefix apps/web test -- api-client.test.ts`

Expected: FAIL until types and fixtures are updated.

- [ ] **Step 2: Add frontend types**

Add:

```ts
export type ParseQuality = {
  page_count: number;
  text_page_count: number;
  empty_page_count: number;
  total_characters: number;
  average_characters_per_page: number;
  low_text_page_ratio: number;
  scanned_likelihood: "low" | "medium" | "high";
  warnings: string[];
};
```

Then add `parse_quality?: ParseQuality | null` to `DocumentSummary`.

- [ ] **Step 3: Run focused tests to verify GREEN**

Run: `npm --prefix apps/web test -- api-client.test.ts`

Expected: PASS.

- [ ] **Step 4: Commit**

```powershell
git add apps/web/lib/types.ts apps/web/tests/api-client.test.ts
git commit -m "feat: type parse quality in web client"
```

### Task 7: Documents and Dashboard UX Refresh

**Files:**
- Modify: `apps/web/app/page.tsx`
- Modify: `apps/web/app/documents/page.tsx`
- Modify: `apps/web/components/document-list.tsx`
- Modify: `apps/web/components/upload-panel.tsx`
- Modify: `apps/web/components/status-badge.tsx`
- Test: `apps/web/tests/dashboard-page.test.tsx`
- Test: `apps/web/tests/documents-page.test.tsx`
- Test: `apps/web/tests/document-list.test.tsx`
- Test: `apps/web/tests/status-badge.test.tsx`

**Interfaces:**
- Consumes: `DocumentSummary.parse_quality`.
- Produces: polished dashboard cards, parse-quality badges, upload actions, and document action buttons.

- [ ] **Step 1: Write failing dashboard tests**

Assert:

```tsx
expect(screen.getByText("Workspace intelligence")).toBeInTheDocument();
expect(screen.getByText("Ready for cited search")).toBeInTheDocument();
expect(screen.getByRole("link", { name: /Ask documents/ })).toBeInTheDocument();
```

Run: `npm --prefix apps/web test -- dashboard-page.test.tsx`

Expected: FAIL until dashboard copy/layout changes.

- [ ] **Step 2: Implement dashboard refresh**

Use `Panel`, `Button`, and `Badge`. Include:
- document count
- indexed count
- warning count from `parse_quality.warnings`
- evaluation runs count
- action links for upload, search, evaluation

- [ ] **Step 3: Write failing documents tests for parse quality**

Assert a document with `parse_quality.scanned_likelihood = "high"` renders:

```tsx
expect(screen.getByText("OCR recommended")).toBeInTheDocument();
expect(screen.getByText("This PDF has very little extractable text and may need OCR.")).toBeInTheDocument();
```

Run: `npm --prefix apps/web test -- document-list.test.tsx documents-page.test.tsx`

Expected: FAIL until list renders parse-quality status.

- [ ] **Step 4: Implement documents refresh**

Update:
- Upload panel with clearer dropzone-style surface and loading action.
- Document list with metadata row, page/chunk counts, quality badge, warnings, and refined reindex/delete buttons.
- Status badge tones aligned to palette.

- [ ] **Step 5: Run focused tests to verify GREEN**

Run:

```powershell
npm --prefix apps/web test -- dashboard-page.test.tsx documents-page.test.tsx document-list.test.tsx status-badge.test.tsx
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/app/page.tsx apps/web/app/documents/page.tsx apps/web/components/document-list.tsx apps/web/components/upload-panel.tsx apps/web/components/status-badge.tsx apps/web/tests/dashboard-page.test.tsx apps/web/tests/documents-page.test.tsx apps/web/tests/document-list.test.tsx apps/web/tests/status-badge.test.tsx
git commit -m "feat: refresh dashboard and documents ux"
```

### Task 8: Search and Evaluation UX Refresh

**Files:**
- Modify: `apps/web/app/search/page.tsx`
- Modify: `apps/web/components/search-results.tsx`
- Modify: `apps/web/app/evaluation/page.tsx`
- Modify: `apps/web/components/evaluation-summary.tsx`
- Test: `apps/web/tests/search-page.test.tsx`
- Test: `apps/web/tests/search-results.test.tsx`
- Test: `apps/web/tests/evaluation-page.test.tsx`
- Test: `apps/web/tests/evaluation-summary.test.tsx`

**Interfaces:**
- Consumes: `SearchResponse`, `SearchDiagnostics`, and `GoldenEvalResponse`.
- Produces: polished search answer panel, citation cards, diagnostics panel, evaluation filters, and status visuals.

- [ ] **Step 1: Write failing SearchResults tests for user-safe diagnostics**

Update diagnostics fixture:

```tsx
top_rejected_reasons: ["Related evidence was not cited because it ranked below the selected answer evidence."]
```

Assert:

```tsx
expect(screen.queryByText(/related-1:/)).not.toBeInTheDocument();
expect(screen.getByText(/ranked below the selected answer evidence/)).toBeInTheDocument();
```

Run: `npm --prefix apps/web test -- search-results.test.tsx`

Expected: FAIL until component copy and fixtures align.

- [ ] **Step 2: Redesign search results**

Use:
- `Panel` for answer and abstention.
- `Badge` for document type, intent, confidence, and citation count.
- `Button` for suggested questions.
- Evidence cards with answer evidence visually stronger than related evidence.
- Diagnostics as a polished section with clear labels.

- [ ] **Step 3: Write failing search page tests for interactive search button**

Assert:

```tsx
expect(screen.getByRole("button", { name: /Search/ })).toHaveClass("transition");
```

Run: `npm --prefix apps/web test -- search-page.test.tsx`

Expected: FAIL until the page uses `Button`.

- [ ] **Step 4: Redesign search page controls**

Use `Panel`, `Button`, accessible labels, better empty/loading/error copy, and the same visual rhythm as Dashboard and Documents.

- [ ] **Step 5: Write failing evaluation summary tests**

Assert:

```tsx
expect(screen.getByText("Quality coverage")).toBeInTheDocument();
expect(screen.getByText("Abstention safety")).toBeInTheDocument();
expect(screen.getByText("All passing")).toBeInTheDocument();
```

Run: `npm --prefix apps/web test -- evaluation-summary.test.tsx evaluation-page.test.tsx`

Expected: FAIL until evaluation UI is refreshed.

- [ ] **Step 6: Redesign evaluation UI**

Use summary panels for pass rate, case count, answerable cases, abstentions, failed cases, and document-type coverage. Keep the existing case table but improve spacing, badges, and filters. Use interactive buttons for run and refresh actions.

- [ ] **Step 7: Run focused tests to verify GREEN**

Run:

```powershell
npm --prefix apps/web test -- search-page.test.tsx search-results.test.tsx evaluation-page.test.tsx evaluation-summary.test.tsx
```

Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add apps/web/app/search/page.tsx apps/web/components/search-results.tsx apps/web/app/evaluation/page.tsx apps/web/components/evaluation-summary.tsx apps/web/tests/search-page.test.tsx apps/web/tests/search-results.test.tsx apps/web/tests/evaluation-page.test.tsx apps/web/tests/evaluation-summary.test.tsx
git commit -m "feat: refresh search and evaluation ux"
```

### Task 9: Full Verification and PR Prep

**Files:**
- No production edits unless verification finds defects.

- [ ] **Step 1: Run full API tests**

Run:

```powershell
python -m pytest apps/api/tests -q
```

Expected: all API tests pass.

- [ ] **Step 2: Run full web tests**

Run:

```powershell
npm --prefix apps/web test
```

Expected: all web tests pass.

- [ ] **Step 3: Run web lint**

Run:

```powershell
npm --prefix apps/web run lint
```

Expected: no lint errors.

- [ ] **Step 4: Run web build**

Run:

```powershell
npm --prefix apps/web run build
```

Expected: production build succeeds.

- [ ] **Step 5: Check whitespace and generated files**

Run:

```powershell
git diff --check
git status --short
```

Expected: no whitespace errors. `apps/web/next-env.d.ts` may remain locally modified, but it must not be staged or committed.

- [ ] **Step 6: Push branch**

Run:

```powershell
git push -u origin feature/product-grade-workspace-quality
```

Expected: branch pushed successfully.

- [ ] **Step 7: Provide PR link**

Open or report:

```text
https://github.com/nigelcheong1/docintel-ai/compare/feature/product-grade-workspace-quality?expand=1
```
