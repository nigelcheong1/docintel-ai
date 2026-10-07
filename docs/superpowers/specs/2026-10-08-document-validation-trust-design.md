# Real-Document Evaluation and Evidence Trust

Date: 2026-10-08
Status: Proposed; awaiting user review. Product implementation has not started.

## Intent

The user wants reliable, cited answers over their uploaded documents and an
Evaluation Lab that measures those documents rather than presenting synthetic
fixture results as universal accuracy. Existing uploads, summaries, study sets,
and local API credentials must be preserved. No model training or additional
cloud provider is required for this phase.

Success means a reviewer can save a source-checked question, run it through the
same Verified Answers pipeline as Search, inspect the answer and evidence, and
see an honestly scoped result with its sample count. A passing automated check
must not be presented as proof of semantic correctness.

## Scope and Sequence

1. Publish the already tested embedding/paraphrase/development-origin fixes in
   a follow-up PR. PR #25 is already merged; do not merge the follow-up without
   the normal review and CI checks.
2. Extend Evaluation Lab with persistent real-document cases and runs.
3. Replace misleading trust labels and expose metric denominators in Search
   and both evaluation views.

The previously suggested source-viewer highlighting, complete excerpts,
title/method extraction cleanup, and arithmetic inconsistency detection are a
separate follow-up. They must not be silently claimed as part of this phase.

## Approaches Considered

- More synthetic fixtures alone: inexpensive regression coverage but does not
  exercise the uploaded PDFs, PostgreSQL vectors, or embedding provider.
- Reviewed local document cases using the production retrieval service:
  recommended. It measures the real path without a new API or training job.
- An LLM-as-judge benchmark: possible later, but adds cost, privacy decisions,
  and another fallible model. It is not a substitute for reviewed ground truth.

## Existing System

- `GET /eval/golden` builds in-memory synthetic documents. Its 21 total cases
  include five Verified Answers cases using fixture lexical retrieval.
- `POST /eval/runs` aggregates stored retrieval history. It does not execute a
  reviewed document benchmark.
- `POST /search` owns query planning, BGE embeddings, hybrid retrieval,
  reranking, evidence selection, strict answering, and sentence checking.
- Search displays an unsupported-sentence fraction as "Hallucination risk".
  The verifier is deterministic, not a learned entailment model or calibrated
  estimate of correctness.
- Local schema initialization is additive. New evaluation tables must not
  rebuild, drop, or relocate document tables or uploaded files.

## Evaluation Workflow

Evaluation Lab will have `Document Benchmarks` and `Fixture Tests` tabs. Saved
search-history aggregates remain separately labeled as retrieval history.

Within Document Benchmarks, a user selects a suite and can add a case, edit it,
review its source, mark it reviewed, and run reviewed cases. A case records:

- A selected uploaded document and question.
- Expected outcome: answerable or insufficient evidence.
- Expected facts, with explicitly approved alternative phrasings where needed.
- Evidence anchors: PDF page number and a source quote.
- Tags such as numeric, table, paraphrase, multi-part, or missing evidence.
- Review state, review timestamp, and a version of the reviewed contents.

Answerable cases require expected facts and resolvable evidence anchors.
Insufficient-evidence cases require a reviewer rationale and no required answer
facts. They need review of the document's scope, not merely an unsuccessful
search. Editing the question, expectations, document, or anchors clears review
approval. Drafts are never silently included in scored runs.

The initial target is 30-50 reviewed questions across multiple papers and
reports. The product will support creating and reviewing that dataset; it will
not fabricate 30-50 "manually checked" cases. Starter questions inferred from
the supplied Paper 10 screenshots may be offered as drafts. Their review status
must remain explicit until the user or a documented source review approves them.

## Persistence and Document Identity

Use new SQLAlchemy tables for suites, cases, document runs, and case results.
Keep legacy `EvalRun` payloads unchanged rather than mixing nested benchmark
details into its scalar metrics contract.

- Suites have a name, creation/update timestamps, and cases.
- Cases retain document identity, a filename snapshot, expectations, anchors,
  tags, review state, and content version.
- Runs retain suite/case snapshots, pipeline revision when available, embedding
  model, retrieval settings, timestamps, progress, and aggregate measurements.
- Case results retain the executed question, answer, citations, selected
  evidence, candidate retrieval trace, timing, retrieval mode/fallback,
  verification output, measurements, and failure reasons.

Use nullable document references with `ON DELETE SET NULL`, retaining identifying
snapshots and historical run results. Missing documents become unavailable
cases, not successful abstentions. No deletion of old uploads is required.

Anchor identity is page number plus normalized source quote, not a volatile
chunk UUID. When a reviewer approves a case, save the affected page-text hashes.
Before running, verify those page hashes and resolve anchors to current chunks.
Unchanged page text can re-resolve after reindexing; changed or missing text
marks the case stale and requires review. Run snapshots preserve the exact
matched chunk IDs and text used at execution time.

Suite JSON import/export is deferred until the native case editor and review
workflow are working. No document contents, benchmark questions from private
files, or source excerpts are pushed to GitHub or sent to a cloud judge.

## Shared Production Pipeline

Extract a callable search service from the existing route without changing
Search behavior. Both interactive Search and document evaluation must call
that service with the same settings and cached embedding provider.

Evaluation execution is document-scoped and uses Verified Answers. It must not
inject the expected facts or anchors into retrieval or generation. Those labels
are used only after the actual answer is produced.

Expose an internal retrieval trace before evidence selection: the top five
reranked candidates for each subquery, including source text, page, and scores.
The current response's displayed hits represent the selected evidence pack;
they cannot truthfully be used as the original retrieval top-five list.

## Runs and Failures

Run reviewed cases sequentially in a backend background task with an independent
database session. Persist case results as they finish, and return a run ID
immediately so the UI can poll progress. This local application supports one
active document benchmark at a time; enforce that guard atomically in the DB.

Run states: queued, running, completed, cancelled, interrupted, or failed.
Stop requests take effect between cases. Completed results remain available.
Backend startup marks abandoned active runs interrupted rather than pretending
they completed or rerunning them automatically. Navigating away from the UI
does not destroy the stored run or its results.

Unindexed documents, missing files, stale anchors, and provider/request failures
are recorded as unavailable or execution errors, not correct abstentions. A
lexical fallback is visibly recorded per case and summarized in the run; a
fallback run must not be advertised as successful vector-retrieval coverage.

Bound suites to 100 cases per run and validate question/quote lengths. No
benchmark operation reindexes or mutates document chunks. Incomplete runs show
progress and partial results, never an unqualified "All passing" badge.

## Measurements

Each measurement carries a value, numerator, denominator, unit, and scope.
Zero-denominator values are null and display `Not evaluated`, never 100%.

- Expected-outcome match: executed cases with the reviewed answer/abstention
  outcome. Execution failures cannot count as correct abstentions.
- Expected-fact match: matched approved fact patterns out of required facts.
  Normalize case, whitespace, and numeric punctuation; preserve negation and
  entity/quantity associations. Arbitrary semantic paraphrase is not certified.
- Evidence recall at 5 per subquery: required anchors found across each
  subquery's top-five candidates, before pack selection. Show the anchor count
  and this scope, not an ambiguous global "recall at 5".
- Citation precision: cited chunks matching reviewed evidence anchors out of
  all cited chunks. Report required-anchor coverage separately so extra or
  missing citations cannot hide behind a perfect precision value.
- Evidence-pack coverage: required anchors represented in selected evidence.
- Abstention outcome match: correct abstentions out of reviewed negative cases.
- Evidence-check support: sentences accepted by the existing deterministic
  checker. Label it as a checker result, not factual accuracy.
- Latency and retrieval-mode counts, including fallback and execution errors.

Table and multi-part scores use only cases with those reviewed tags and display
their own sample counts. An untested category remains `Not evaluated`.

Separate optional human assessment of actual answers from automatic fact-match
results. A reviewer can mark a saved result correct, incorrect, or needs review
with a note; automatic scores do not populate this assessment themselves.

The Paper 10 mismatch (1,180 + 1,351 differs from 2,366) is an example of why a
source-supported sentence may still warrant review. This phase will preserve
source wording and reviewer notes; general arithmetic detection is deferred.

## Trust Indicators

Search retains the feature name `Verified Answers` but uses a badge such as
`Evidence checks passed`, `Needs review`, or `Not enough evidence`. Replace
the hallucination-risk percentage with counts of sentences checked, supported,
and removed. An abstention with no answer shows `No answer generated`; it is
not assigned 100% hallucination risk in the visible UI.

Retain the existing API risk field temporarily for backward compatibility; new
clients derive their visible labels from sentence counts and status. Do not
weaken support thresholds or change abstention behavior as part of relabeling.

Fixture Tests is explicitly identified as synthetic and lexical-only. Every
fixture metric shows its actual denominator, which may differ from the total
21 cases. Real-document results show the suite, reviewed case count, execution
mode, timestamp, and partial/error counts. Historical results stay immutable
when labels are edited; a new run captures the new case versions.

## API and UI Boundaries

Add document-benchmark routes under `/eval/document-suites` and
`/eval/document-runs` for suite/case management, review, run creation, progress,
results, cancellation, and result assessment. Keep `/eval/golden` and existing
`/eval/runs` contracts available. Use Pydantic schemas and typed frontend clients.

The case editor uses a native document selector, explicit expected-outcome
controls, editable facts/anchors, review commands, and validation errors. The
run view provides progress, per-case outcomes, expected versus actual answers,
evidence links, failure filters, and scoped metrics. Empty, draft-only, stale,
fallback, interrupted, and request-error states must be usable.

Preserve the current teal/neutral UI, lucide icons, and responsive conventions.
No new landing page or marketing copy is needed. Sources remain local and are
opened with existing preview/workbench controls.

## Verification Plan

- TDD for measurement denominators, numeric/entity associations, negation,
  partial multi-part answers, unsupported facts, and citation precision/coverage.
- Dedicated PostgreSQL test database for additive schema initialization,
  persistence, review invalidation, reindex anchor resolution, missing documents,
  run snapshots, cancellation, interruption, and active-run guards.
- API tests prove Search and benchmarks invoke the same pipeline, expectations
  never leak into retrieval, and fallback/errors cannot create misleading passes.
- Frontend tests cover tabs, editor validation, metric counts/null values, review
  states, progress, errors, filters, and removal of probability-like risk labels.
- Full backend/frontend suites, lint, type checking, and desktop/mobile browser
  verification. Do not stop or replace the user's existing dev servers casually.
- Live Paper 10 numeric and negative cases against real PostgreSQL/BGE, with
  page evidence inspection. Report observed failures instead of tuning scores to
  force a 100% result.

## Approval and Implementation Handoff

The user has approved the phase direction. This written design still needs
review before an implementation plan and product-code changes. After approval,
prepare the implementation plan and agree on inline execution. Keep the tested
bug-fix follow-up separate from the new feature work, and do not merge the new
phase without reviewed tests and CI.
