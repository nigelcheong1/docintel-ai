# Document Benchmarks

## Start the Feature Checkout

Use the checkout for `feature/document-validation-trust`, currently located at:

```text
C:\Users\nigel\Documents\Codex\2026-08-27\i-w\work\docintel-ai\.worktrees\feature-verified-answers-rag
```

Keep PostgreSQL and its existing volume running. Stop the old backend with
Ctrl+C, then restart it from this checkout's `apps/api` directory:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Startup creates the additional benchmark tables. It does not replace the
documents, pages, chunks, summaries, or study sets. Keep the existing local
`.env` database and storage settings. Do not reset Docker volumes or use a new
empty database to address an empty document list.

In another PowerShell window, from this checkout's `apps/web` directory:

```powershell
npm run dev -- --hostname 127.0.0.1 --port 3001
```

Open [Evaluation Lab](http://127.0.0.1:3001/evaluation). If dependencies are
missing, stop any Next.js process using this checkout before `npm ci`; a running
Windows SWC library can prevent installation. No model training or new cloud
provider is needed. Search and document benchmarks use the same configured
embedding provider and Verified Answers pipeline.

## Create and Review Cases

1. Open **Document Benchmarks**, the default Evaluation Lab tab. **Fixture
   Tests** is a separate synthetic, lexical-retrieval scorecard; it does not
   measure uploaded documents. Existing retrieval history remains there.
2. Enter a suite name and select **Create suite**, then **Add case**.
3. Select the actual uploaded document and enter a question. Choose
   **Answerable** or **Not enough evidence**.
4. For answerable cases, add concise expected fact patterns, optional approved
   alternatives (one per line), and page-number/exact-quote evidence anchors.
   Include entities with numbers: a pattern such as `Scopus returned 2366`
   is stronger than `2366` alone. Quotes may cross adjacent chunks; anchor
   resolution is checked against current page text and the index.
5. Tags are comma-separated. Use `table` and `multi-part` for those measured
   subsets. A subset without eligible reviewed cases is **Not evaluated**,
   never 100%.
6. Select **Save draft**. Saving never marks a case reviewed. Preview each
   anchor with its eye button, inspect the source page, close the viewer,
   then select **Mark reviewed**.
7. For a negative case, provide a review rationale describing the inspected
   scope and why the answer is absent. Use **Open document scope** and its
   workbench link to inspect the full document. Confirm **I reviewed the
   whole document scope** before marking reviewed. An automated abstention
   is not sufficient justification for a negative label.

Editing case content clears source review and increments its version when
saved. A source text change makes a reviewed case stale; review it again.
Unchanged reindexing can change chunk IDs without invalidating the page-based
review. Missing files, missing indexed evidence, and unavailable documents
are not scored as successful abstentions.

The editor marks required review fields with a red asterisk and always shows
**Review prerequisites** above **Mark reviewed**. Answerable cases need a
question, indexed source, expected facts, complete page/quote anchors, the
current draft saved, and every anchor previewed. Negative cases need a
question, indexed source, scope-review rationale, a saved draft, inspected
document scope and explicit scope confirmation. Negative cases omit expected
facts; their evidence anchors are optional. Alternatives and tags remain optional.
Any optional rows that are added must still have valid values.

Incomplete review requirements do not prevent saving a valid draft. Blank
questions and malformed entered rows are rejected locally, with field-level
errors and focus moved to the first invalid field. Editing resets source
review prerequisites. Backend source checks remain authoritative.

## Run and Inspect

- **Run benchmark** is disabled when the selected suite has no reviewed cases.
  Only reviewed cases enter the run snapshot. Stale or unavailable reviewed
  cases produce unavailable results rather than misleading passes.
- Only one run can be queued/running at once. A conflict message means wait
  for the active run or select it in **Saved run** and cancel it.
- Progress and completed case results are saved after each case. Navigating
  away stops browser polling, not the backend run. Returning restores saved
  history and selection. **Cancel run** takes effect between cases; completed
  results are retained.
- After backend restart, abandoned active runs become **interrupted** and
  release the active slot. They are not silently resumed; start another run.
- Filter results by **Failed**, **Unavailable**, **Errors**, or **Needs human
  review**. Inspection shows the reviewed case version and expected snapshot,
  actual answer/citations, latency, mode/fallback reason, sentence checks,
  candidates before selection, and the selected evidence pack.
- Human assessment (**Correct**, **Incorrect**, **Needs review**) and notes
  are saved separately from automatic checks. Editing live cases or deleting
  a suite does not rewrite historical expectations, answers, or scores.

Every measurement carries its numerator, denominator, and scope. Run scores
apply to completed evaluated cases, not all documents or unfinished work.
Failures, unavailable cases, and execution errors remain visible beside those
scores. Lexical fallback is explicitly reported; it is not a passing vector
retrieval test. A provider-failed negative case is an execution error with no
abstention score; missing semantic retrieval must not inflate safe-abstention
results. Positive lexical answers can still be checked, with fallback visible.
Fact checks are normalized pattern checks, not semantic judges.
Sentence-check support counts are not a calibrated hallucination probability.

## First Real-Document Checks

Start locally with the uploaded Paper 10 and inspect its page 3:

- An answerable question about the initial Scopus result count and the count
  remaining after deduplication. Review and label each requested part from
  the source, keeping the combined-database pool distinct from Scopus alone.
- A negative question about a private GPU cluster, after checking the full
  paper for that information. Record the source-scope rationale.

Do not silently repair contradictory source numbers or force a 100% result.
Record ambiguity in the human assessment. Add table and multi-part cases only
after inspecting the relevant sources. Build toward 30-50 independently
reviewed cases across several documents, with meaningful unanswerable cases;
the application deliberately does not seed fabricated reviewed examples.

## Evidence for a Failure

Provide the question, selected document, case version, run ID/status, retrieval
mode and fallback reason, and these screenshots:

1. The expected snapshot and actual answer with automatic failure reasons.
2. The relevant source page and exact anchor quote in Source Viewer.
3. Expanded candidates and selected evidence, plus relevant case measurements.
4. Progress/error state and any red backend startup/request error, with API
   keys and connection passwords removed.

Also check desktop and a narrow mobile viewport: tabs, form fields, editor
actions, result filters and source links must remain readable and usable.

## Automated Verification

Backend integration tests DROP and recreate tables. Use a dedicated disposable
database whose name contains `test`, never the development `docintel` database:

```powershell
$env:DOCINTEL_TEST_DATABASE_URL = "postgresql+psycopg://docintel:docintel@localhost:5432/docintel_verified_fix_test"
python -m pytest -q
```

Run frontend checks from `apps/web`:

```powershell
npm test
npm run lint
node node_modules/typescript/bin/tsc --noEmit --incremental false
```

Missing-source, changed-source, cross-chunk quotes, altered labels, cancellation,
restart recovery, active-run conflicts and provider fallback are exercised with
test-owned documents. Do not delete or reindex personal uploads to provoke them.

## Implementation Verification Record

On 2026-10-12, fresh verification passed the full backend suite (375 tests)
against the disposable PostgreSQL database `docintel_verified_fix_test`, the
frontend suite (139 tests), ESLint, and TypeScript with incremental compilation
disabled. Frontend tests used the checked-in Vitest configuration without a
temporary path-resolution override. Existing React `act` warnings remain in
the frontend suite; they are not test failures.

The first full backend run exposed a default-settings test reading the local
storage override from `.env`. Default-settings tests now explicitly exclude
dotenv and clear settings environment variables. Runtime settings, database
configuration, and uploaded files were not changed by that test-only fix.

Independent review earlier identified seven issues; regression tests reproduced
and verified fixes for failed-provider negatives, signed quantities and
comparisons, reversed negation, equivalent overlapping evidence, line-wrapped
quotes, pending editor requests, and legacy relative upload paths.

The local real-document smoke run completed two reviewed cases: an answerable
count question and a negative question. Both automatic checks passed with hybrid
retrieval and no fallbacks. This is a two-case smoke test, not a claim of general
retrieval accuracy or hallucination-free answers. The editor's required-field
markers, outcome-specific review gates, and inline errors were also checked at
desktop and mobile widths. Private cases and source excerpts were not seeded or
committed. GitHub CI, including the production frontend build, must pass before
merge.

## Execution Decisions

- PowerShell/manual progress records replaced the Git Bash helper scripts when
  the sandbox denied MSYS kernel-object access. The cost is losing the helper's
  automatic bookkeeping validation, not a change in product behavior.
- Earlier restricted verification used a temporary path-resolution override
  and could not reach PostgreSQL or the live browser. The 2026-10-12 unrestricted
  verification supersedes those limitations; no override was committed.
- A small reviewed suite is not evidence of universal accuracy. Expand the
  independently reviewed dataset across multiple documents, including table,
  multi-part, OCR, and unanswerable cases, before publishing quality claims.
- GitHub CI and the private dataset's labels still need independent confirmation.
- The guide is complete; source highlighting and arithmetic contradiction
  detection remain deferred as approved. Contradictions still need human review.
