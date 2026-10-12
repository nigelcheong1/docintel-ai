# Real-Document Evaluation and Evidence Trust Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evaluate reviewed questions against uploaded documents through production Verified Answers, retaining inspectable results and honestly scoped measurements.

**Architecture:** Extract the existing search pipeline into a shared service with an internal pre-selection trace. Add separate persisted benchmark tables, source review, sequential background execution, and a typed Evaluation Lab interface. Keep legacy evaluation endpoints and Search behavior compatible while replacing misleading UI trust labels.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLAlchemy, PostgreSQL/pgvector, existing BGE embeddings, Next.js 16, React 19, TypeScript, lucide, pytest, Vitest/Testing Library.

**Spec:** `docs/superpowers/specs/2026-10-08-document-validation-trust-design.md`

**Execution Status (2026-10-12):** Tasks 1-9 implemented. Seven independent
review findings reproduced and fixed. Latest checks: 131 frontend tests,
121 focused backend tests, lint and TypeScript pass. Task 10 live/PostgreSQL
verification remains pending runtime restrictions. See
`docs/testing/document-benchmarks.md` for the operator guide and decisions.

## Global Constraints

- Preserve uploads, summaries, study sets, local credentials, and the user's running development servers. Schema changes are additive only.
- No model training, additional cloud provider, cloud judge, new dependency, or private document excerpts committed to GitHub.
- Retain the feature name `Verified Answers`; do not call it DocRAG Mode.
- Run only reviewed cases, at most 100 per run, sequentially; enforce one active benchmark globally with a database constraint.
- Expected facts and anchors are scoring labels only and must never enter retrieval or answer generation.
- Measurements include value, numerator, denominator, unit, and scope. Zero-denominator values are null and display `Not evaluated`.
- Retain `/eval/golden`, `/eval/runs`, and the legacy risk field; do not weaken evidence checks or abstention thresholds.
- Use nullable document references with `ON DELETE SET NULL`, preserving historical snapshots.
- Defer suite import/export, source highlighting, excerpt/title extraction polish, and arithmetic inconsistency detection.
- Preserve the existing teal/neutral UI, responsive conventions, and existing source preview/workbench controls.
- Preserve unrelated `apps/web/next-env.d.ts` changes. Do not merge PR #26 or publish this feature without user authorization.

## Review Focus

- Backend restart or two near-simultaneous Run clicks: retain completed results, release abandoned runs, and admit only one active run. Task 5 tests this.
- Reindexing changes chunk IDs or a quote straddles chunk boundaries: unchanged source remains reviewable; changed source requires review. Task 2 tests this.
- A missing file or embedding failure accompanies a negative case: do not report a correct abstention or successful vector coverage. Tasks 5 and 6 test this.
- Both answers contain the same numbers but associate them with different entities, or reverse negation: fact matching must fail. Task 4 tests this.
- A suite has no reviewed table cases, or the user leaves an active run: show `Not evaluated` and restore persisted progress when returning. Tasks 7 and 9 test this.

---

## File Map and Test Commands

Backend additions under `apps/api/app/evaluation/`: `document_schemas.py` (contracts), `document_cases.py` (CRUD/review), `document_metrics.py` (pure scoring), `document_runs.py` (lifecycle/worker), and `document_router.py` (HTTP boundary). Existing model definitions remain in `app/db/models.py`; extraction adds `app/retrieval/service.py`.

Frontend additions: `lib/document-evaluation.ts` (typed client), `components/evaluation-metric.tsx` (scoped measurement), `document-benchmarks.tsx` (suite orchestration), `benchmark-case-editor.tsx` (source review), and `benchmark-run-results.tsx` (progress/results), all under `apps/web/`.

Commands below run from `apps/api` or `apps/web` as stated. Integration tests must use only the existing dedicated test database:

```powershell
$env:DOCINTEL_TEST_DATABASE_URL = 'postgresql+psycopg://docintel:docintel@localhost:5432/docintel_verified_fix_test'
```

Never substitute the development `docintel` database: the test fixture drops test tables.

### Task 1: Persistent Benchmark Models and Contracts

**Files:** Modify `apps/api/app/db/models.py`, `apps/api/app/db/init_db.py`; create `apps/api/app/evaluation/document_schemas.py`; test `apps/api/tests/evaluation/test_document_schema.py`.

**Interfaces:**
- Produce ORM `DocumentEvalSuite`, `DocumentEvalCase`, `DocumentEvalRun`, `DocumentEvalResult` with UUID IDs and UTC timestamps.
- Suite fields: `name`, `created_at`, `updated_at`. Case fields: `suite_id`, nullable `document_id`, `document_filename`, `question`, `expected_outcome`, JSONB `facts`, `anchors`, `tags`, `review_rationale`, `review_state`, `content_version`, `reviewed_at`, JSONB `review_page_hashes`.
- Run fields: nullable `suite_id`, JSONB `suite_snapshot`, `case_snapshots`, `pipeline_config`, `measurements`, `status`, nullable unique integer `active_slot`, `cancel_requested`, `total_cases`, `completed_cases`, `created_at`, `started_at`, `finished_at`, nullable `error`. Active slot is 1 for queued/running and null for terminal states, with a check constraint allowing only 1 or null.
- Result fields: `run_id`, `case_id_snapshot`, `case_version`, JSONB `case_snapshot`, `execution_snapshot`, `measurements`, `failure_reasons`, `status`, `duration_ms`, nullable `human_assessment`, `assessment_note`, `assessed_at`, `created_at`. Run results do not reference deletable live cases.
- Pydantic contracts: `ExpectedFact(pattern: str, alternatives: list[str])`, `EvidenceAnchor(page_number: int, quote: str)`, `Measurement(value: float | None, numerator: float, denominator: int, unit: Literal['ratio','ms'], scope: str)`.
- `CaseWrite` has `document_id: UUID`, `question: str`, `expected_outcome: Literal['answerable','insufficient_evidence']`, `facts: list[ExpectedFact]`, `anchors: list[EvidenceAnchor]`, `tags: list[str]`, `review_rationale: str`. `CaseRead` adds identity/version/review/hash fields and computed `availability: Literal['ready','draft','stale','unavailable']`.
- Limits: suite name 1-120 characters; question 1-2000; each fact/alternative 1-1000; quote 1-4000; rationale/note at most 4000; at most 20 facts, 10 alternatives per fact, 20 anchors, 10 tags of 1-40 characters. Page numbers are positive. Whitespace-only required inputs fail validation.
- `SuiteRead` adds `case_count` and `reviewed_count`; `SuiteDetail(SuiteRead)` adds `cases: list[CaseRead]`; `RunRead` exposes the run fields above plus mode/error/unavailable counts derived from results; `ResultRead` exposes result fields above. Write contracts are `SuiteWrite(name)`, `RunCreate(suite_id: UUID)`, `ReviewCaseRequest(content_version: int)`, and `ResultAssessmentWrite(assessment: Literal['correct','incorrect','needs_review'], note: str)`.

- [ ] Write `test_schema_sync_preserves_existing_uploads`, `test_document_delete_retains_case_and_run_snapshots`, `test_only_one_active_slot`, and schema limit tests. Assert an existing Document/Chunk survives sync, document deletion nulls only the case reference, a second slot-1 run raises `IntegrityError`, and whitespace/oversized inputs raise validation errors.
- [ ] Run `python -m pytest tests/evaluation/test_document_schema.py -v`; confirm failures are missing models/contracts, not database misconfiguration.
- [ ] Add the four tables and schemas with cascade restricted to owned benchmark children. Include new tables in additive schema sync; never alter legacy `EvalRun.metrics`.
- [ ] Rerun the targeted file; require every assertion to pass against PostgreSQL.
- [ ] Commit only Task 1 files: `feat: add persistent document benchmark contracts`.

### Task 2: Case Editing, Source Anchors, and Explicit Review

**Files:** Create `apps/api/app/evaluation/document_cases.py`; test `apps/api/tests/evaluation/test_document_cases.py`.

**Interfaces:**
- Consume Task 1 contracts/models and existing `Document`, `Page`, `Chunk`.
- Produce `create_case(db: Session, suite_id: str, data: CaseWrite) -> DocumentEvalCase`, `update_case(db: Session, case_id: str, data: CaseWrite) -> DocumentEvalCase`, and `review_case(db: Session, case_id: str, content_version: int) -> DocumentEvalCase`.
- Produce immutable `ResolvedAnchor(page_number: int, quote: str, chunk_ids: tuple[str, ...])` and `CaseReadiness(availability: str, anchors: tuple[ResolvedAnchor, ...], reasons: tuple[str, ...])`; `check_case_readiness(db: Session, case: DocumentEvalCase) -> CaseReadiness`.
- Produce `normalize_source(text: str) -> str` and `page_text_hash(text: str) -> str`: collapse whitespace and normalize line-wrap hyphenation; hash the complete page text with SHA-256, not a truncated snippet.
- Source resolution uses page text plus ordered current chunks, accepting quotes across adjacent chunks. Review snapshots affected page hashes for positives and every page hash for reviewed negatives.

- [ ] Write tests asserting new cases are drafts; meaningful edits increment version and clear review; review with an old version conflicts; positive review without facts/anchors fails; negative review without rationale or with required facts fails.
- [ ] Add `test_unchanged_reindex_reresolves_new_chunk_ids`, `test_anchor_crosses_adjacent_chunk_boundary`, `test_changed_or_removed_page_requires_review`, and `test_negative_scope_change_requires_review`. Assert stable source permits new chunk IDs, a complete quote resolves all participating chunks, and changed/missing pages are stale.
- [ ] Run `python -m pytest tests/evaluation/test_document_cases.py -v`; require the expected red state.
- [ ] Implement case CRUD/readiness/review. Require indexed document, existing local file, resolvable sources, and at least one page for negative scope review. Use 404 for missing identities, 409 for stale version/source, and 422 for invalid expectations. Never infer negative review from a failed search.
- [ ] Rerun targeted tests and Task 1 tests; require green.
- [ ] Commit Task 2 files: `feat: add source-checked benchmark case review`.

### Task 3: One Shared Production Search Service and Candidate Trace

**Files:** Create `apps/api/app/retrieval/service.py`; modify `apps/api/app/retrieval/router.py`, `apps/api/tests/retrieval/test_search_api.py`; test `apps/api/tests/retrieval/test_search_service.py`.

**Interfaces:**
- Consume existing `SearchRequest`, `SearchResponse`, `SearchHit`, and `EmbeddingProviderFactory` without changing their public request/response contracts.
- Produce immutable `SearchExecution(response: SearchResponse, candidates_by_subquery: dict[str, tuple[SearchHit, ...]], selected_evidence: tuple[SearchHit, ...])`.
- Produce `execute_search(request: SearchRequest, db: Session, embedder_factory: EmbeddingProviderFactory) -> SearchExecution`. Trace stores full text and scores from the first five reranked candidates for each subquery, before evidence-pack selection; selected evidence retains full text separately.
- `POST /search` delegates to this service and returns only `.response`. Continue using `get_embedding_provider_factory` and its existing cache/settings.

- [ ] Write `test_search_route_delegates_to_shared_service` and `test_trace_is_top_five_per_subquery_before_pack_selection`; assert route response parity and that a candidate rejected from the pack remains in the trace. Add standard/verified, empty-document, hybrid, and lexical-fallback parity assertions.
- [ ] Run `python -m pytest tests/retrieval/test_search_service.py -v`; confirm missing-service failures.
- [ ] Move orchestration/helpers into the service, preserving retrieval settings and support thresholds. Update existing monkeypatches to the new service boundary; keep embedding dependency overrides valid and do not add expectation arguments.
- [ ] Run `python -m pytest tests/retrieval -v`; require all existing retrieval behavior and new trace tests to pass.
- [ ] Commit Task 3 files: `refactor: share verified search execution and retrieval trace`.

### Task 4: Scoped Automatic Measurements Without Accuracy Claims

**Files:** Create `apps/api/app/evaluation/document_metrics.py`; test `apps/api/tests/evaluation/test_document_metrics.py`.

**Interfaces:**
- Consume `CaseWrite`, `ResolvedAnchor`, `SearchExecution`, and `Measurement`.
- Produce `make_measurement(numerator: float, denominator: int, unit: Literal['ratio','ms'], scope: str) -> Measurement`, `fact_matches(answer: str, fact: ExpectedFact) -> bool`, `score_case(case: CaseWrite, anchors: tuple[ResolvedAnchor, ...], execution: SearchExecution, duration_ms: float) -> dict[str, Measurement]`, `case_failure_reasons(case: CaseWrite, measurements: dict[str, Measurement]) -> list[str]`, and `aggregate_case_measurements(results: list[ResultRead]) -> dict[str, Measurement]`.
- Keys: `outcome_match`, `fact_match`, `retrieval_anchor_recall_at_5`, `citation_precision`, `citation_anchor_coverage`, `pack_anchor_coverage`, `abstention_match`, `checker_support`, `latency`, `table_case_pass_rate`, `multi_part_case_pass_rate`.
- Match approved phrases within individual sentences after lowercasing, whitespace collapse, and thousands-separator normalization. Preserve token order and sentence negation; require an explicitly approved alternative for other phrasings. Do not use bag-of-words matching, automatic semantic paraphrases, or unrelated numbers elsewhere in the answer.
- Anchor coverage requires the normalized full quote in ordered candidate/selected/cited source text on its page. Citation precision counts unique cited chunks belonging to resolved reviewed anchors; extra citations lower precision.
- A positive passes automatic checks only when outcome/fact match, retrieval recall, citation precision/coverage, pack coverage, and checker support each equal 1 with nonzero denominators. A negative requires matching abstention with no answer and no citations. Return a reason per failed required check; latency and tag-subset aggregates do not gate an individual result. This is not human correctness certification.

- [ ] Write tests with exact assertions: `make_measurement(0,0,'ratio','anchors').value is None`; swapped Scopus/WOS counts and reversed negation fail; comma-formatted approved counts match; one missing fact gives numerator 1/denominator 2; an approved alternative matches.
- [ ] Add trace-versus-pack tests, crossing-quote coverage, and citation tests: one relevant plus one unrelated citation gives 1/2 precision; omitting one of two anchors gives 1/2 anchor coverage despite perfect precision. Negative cases have no anchor/fact denominator; no generated sentence gives null checker support; absent table/multi-part tags give null subset metrics.
- [ ] Run `python -m pytest tests/evaluation/test_document_metrics.py -v`; verify red for the new functions.
- [ ] Implement pure scoring and weighted aggregation by summed numerators/denominators, never average percentages with different sample sizes. Exclude unavailable/error results from successful-execution metric denominators, expose their counts, and prevent any run containing them from receiving an all-passing label.
- [ ] Rerun targeted tests; require green with explicit metric units/scopes.
- [ ] Commit Task 4 files: `feat: score reviewed evidence with explicit denominators`.

### Task 5: Persisted Background Runs, Cancellation, and Recovery

**Files:** Create `apps/api/app/evaluation/document_runs.py`; modify `apps/api/app/main.py`; test `apps/api/tests/evaluation/test_document_runs.py`.

**Interfaces:**
- Consume Task 2 readiness, Task 3 execution, Task 4 scoring/failure reasons, and existing `SessionLocal`/`SessionFactory` and cached embedding factory.
- Produce `create_document_run(db: Session, suite_id: str, pipeline_config: dict[str, object]) -> DocumentEvalRun`, `execute_document_run(run_id: str, session_factory: SessionFactory, embedder_factory: EmbeddingProviderFactory) -> None`, `request_run_cancel(db: Session, run_id: str) -> DocumentEvalRun`, `interrupt_abandoned_runs(db: Session) -> int`.
- Snapshots include exact case version/question/expectations/review hashes, resolved anchor/chunk identities, complete answer/citations/selected source/trace, `SearchResponse.model_dump(mode='json')`, model/device/top_k=5/answer_mode=verified, and git revision when discoverable; revision unavailable is null, never fabricated.
- Run states are queued/running/completed/cancelled/interrupted/failed. Result states are pass/fail/unavailable/error. Persist one result/progress increment per attempted case and clear active slot on every terminal path.

- [ ] Write tests proving drafts are excluded, zero reviewed cases and more than 100 reject run creation, case edits after queueing cannot change the snapshot, and two independent sessions cannot both reserve active slot 1.
- [ ] Add `test_cancel_keeps_finished_results`, `test_startup_interrupts_without_rerun`, `test_missing_file_is_unavailable_not_abstention`, `test_provider_fallback_records_lexical_mode`, and `test_worker_exception_is_error_not_negative_pass`. Assert progress/result persistence after each case and terminal slot release.
- [ ] Run `python -m pytest tests/evaluation/test_document_runs.py -v`; require expected red tests.
- [ ] Implement the sequential worker with fresh DB sessions, reviewed snapshot readiness checks before each execution, and document-scoped `SearchRequest` containing only the question and ordinary search options. A lexical fallback can be scored but is labeled lexical with its reason; provider/request failure without a valid response is error. Fatal worker failures mark failed and preserve results. Startup invokes interruption after additive initialization.
- [ ] Rerun Tasks 1-5 tests; require lifecycle, concurrency, and snapshot assertions to pass.
- [ ] Commit Task 5 files: `feat: persist cancellable document benchmark runs`.

### Task 6: Benchmark HTTP Routes and Human Assessment

**Files:** Create `apps/api/app/evaluation/document_router.py`; modify `apps/api/app/main.py`; test `apps/api/tests/evaluation/test_document_eval_api.py`.

**Interfaces:**
- Consume Tasks 1, 2, and 5. Mount an `APIRouter(prefix='/eval')` alongside the legacy router.
- Suite endpoints: `GET/POST /document-suites`, `GET/PUT/DELETE /document-suites/{suite_id}`; GET detail returns SuiteDetail, list returns `list[SuiteRead]`, writes return SuiteRead, and deletion returns 204.
- Case endpoints: `POST /document-suites/{suite_id}/cases`, `PUT/DELETE /document-suites/{suite_id}/cases/{case_id}`, `POST /document-suites/{suite_id}/cases/{case_id}/review`. Return CaseRead; deletion returns 204. Check suite ownership on every nested case route.
- Run endpoints: `POST /document-runs` -> 202 RunRead and background scheduling; `GET /document-runs?suite_id=...` -> list[RunRead]; `GET /document-runs/{run_id}` -> RunRead; `GET /document-runs/{run_id}/results` -> list[ResultRead]; `POST /document-runs/{run_id}/cancel` -> RunRead.
- Human review: `PUT /document-runs/{run_id}/results/{result_id}/assessment` -> ResultRead. Only assessment/note/timestamp mutate; executed snapshots and scores remain unchanged.

- [ ] Write API tests for suite/case CRUD/review, 404/422/409 failures, active-run conflict, immediate 202 scheduling, progress/results, idempotent terminal cancellation, suite deletion retaining runs, and human assessment isolation.
- [ ] Add `test_expected_labels_never_enter_execute_search` recording the production service arguments; assert only question/document_id/top_k/answer_mode enter search. Prove missing documents never become negative passes and unknown/misowned result IDs return 404.
- [ ] Run `python -m pytest tests/evaluation/test_document_eval_api.py -v`; confirm missing-route red tests.
- [ ] Implement thin route handlers, response validation, and injectable background worker/session factory for integration tests. Catch active-slot uniqueness conflicts as 409, roll back sessions, and preserve `/eval/runs` and `/eval/golden`.
- [ ] Run `python -m pytest tests/evaluation tests/retrieval/test_search_api.py -v`; require new API and legacy contracts to pass.
- [ ] Commit Task 6 files: `feat: expose reviewed document benchmark API`.

### Task 7: Honest Search and Fixture Trust Indicators

**Files:** Modify `apps/api/app/evaluation/golden.py`, `apps/web/lib/types.ts`, `apps/web/components/search-results.tsx`, `apps/web/components/evaluation-summary.tsx`; create `apps/web/components/evaluation-metric.tsx`; modify corresponding existing frontend tests and `apps/api/tests/evaluation/test_golden_eval.py`.

**Interfaces:**
- Add backward-compatible `GoldenEvalSummary.verified_measurements: dict[str, Measurement]`, leaving existing `verified_metrics` scalar values available. Ratios of case-average metrics use the actual eligible case count and a scope naming case averages; do not call this a raw sentence/anchor denominator.
- Define frontend `EvaluationMeasurement` matching Measurement. Produce `EvaluationMetric({label, measurement}: {label: string; measurement: EvaluationMeasurement})` showing percentage or ms, numerator/denominator, scope, and `Not evaluated` for null.
- Search's checked count is `verification.sentences.length`; supported count filters `sentence.status === 'verified'`; removed count uses `removed_sentence_count`. Keep the API's `hallucination_risk` field but do not render it as probability or a UI percentage.

- [ ] Add backend assertions that fixture answer quality uses five Verified cases, positive-case metrics use four, abstention uses one, and table/multi-part use their actual subsets. Empty subsets give null in new measurements, while the old response remains compatible.
- [ ] Add UI assertions for `Evidence checks passed`, `Needs review`, and `Not enough evidence`; no answer displays `No answer generated`; checked/supported/removed counts display correctly. Assert no visible `Hallucination risk` or old plain `Verified` badge.
- [ ] Add measurement tests for null, 1/2, zero supported sentences, and fractional case-average numerator. Fixture panel says `Synthetic fixture tests` and `Lexical retrieval`; legacy histories say `Retrieval history`, not real-document runs.
- [ ] Run API golden tests and `npm test -- tests/search-results.test.tsx tests/evaluation-summary.test.tsx tests/evaluation-metric.test.tsx`; verify the copy/count expectations fail before changes.
- [ ] Implement additive fixture measurement metadata and shared metric renderer; relabel trust summaries without changing retrieval/checking behavior.
- [ ] Rerun targeted tests and `npm run lint`; require green.
- [ ] Commit Task 7 files: `fix: scope evaluation scores and evidence trust labels`.

### Task 8: Suite Management and Source-Reviewed Case Editor

**Files:** Create `apps/web/lib/document-evaluation.ts`, `apps/web/components/document-benchmarks.tsx`, `apps/web/components/benchmark-case-editor.tsx`; modify `apps/web/lib/api.ts`, `apps/web/lib/types.ts`, `apps/web/app/evaluation/page.tsx`; test `apps/web/tests/document-evaluation-api.test.ts`, `document-benchmarks.test.tsx`, `benchmark-case-editor.test.tsx`, and existing `evaluation-page.test.tsx`.

**Interfaces:**
- Frontend types mirror SuiteRead, CaseWrite/Read, RunRead, ResultRead, outcome/status unions, and assessment. No `any` or legacy scalar-metric coercion.
- Export existing `API_BASE_URL: string` and `parseJsonResponse<T>(response: Response): Promise<T>` from `lib/api.ts` without changing their behavior. The new client reuses them and handles 204 deletions separately.
- Client exports typed helpers `listDocumentSuites(): Promise<DocumentEvalSuite[]>`, `createDocumentSuite(name: string): Promise<DocumentEvalSuite>`, `getDocumentSuite(id: string): Promise<DocumentEvalSuiteDetail>`, `updateDocumentSuite(id: string,name: string): Promise<DocumentEvalSuite>`, `deleteDocumentSuite(id: string): Promise<void>`, `saveDocumentCase(suiteId: string,data: DocumentCaseWrite,caseId?: string): Promise<DocumentEvalCase>`, `deleteDocumentCase(suiteId: string,caseId: string): Promise<void>`, `reviewDocumentCase(suiteId: string,caseId: string,version: number): Promise<DocumentEvalCase>`.
- Components: `DocumentBenchmarks()` owns suites/cases/selection; `BenchmarkCaseEditor({suiteId, documents, initialCase, onSaved, onCancel}: {suiteId: string; documents: DocumentSummary[]; initialCase?: DocumentEvalCase; onSaved: (value: DocumentEvalCase) => void; onCancel: () => void})` edits typed cases. Reuse `getDocuments()` and `SourceViewer({source: SourceViewerSource, onClose: () => void})`, with current page/chunk URLs resolved from the existing document detail/chunk APIs.
- Evaluation tabs have accessible tab semantics, `Document Benchmarks` default and `Fixture Tests` separate; preserve separately labeled retrieval history.

- [ ] Write client URL/method/payload/error tests; UI tests for empty suite creation, native document selection, outcome controls, editable fact alternatives/anchors/tags/rationale, explicit draft/reviewed/stale badges, edit invalidation, and validation messages.
- [ ] Test review opens the selected page/quote before the user marks reviewed; no automatic approval after save. Negative review requires scope rationale. Draft-only suites disable Run, and deleting a suite requires an explicit confirmation action.
- [ ] Run the new tests and `tests/evaluation-page.test.tsx`; verify expected red assertions.
- [ ] Implement the typed client, suite actions, and editor using existing input/modal conventions, segmented outcome controls, lucide action icons/tooltips, and source preview controls. Do not seed fabricated reviewed cases or send private labels to external services.
- [ ] Rerun targeted tests, lint, and `node node_modules/typescript/bin/tsc --noEmit --incremental false`; require green.
- [ ] Commit Task 8 files: `feat: add document benchmark suite and review editor`.

### Task 9: Run Progress, Failure Inspection, and Saved Result Review

**Files:** Extend `apps/web/lib/document-evaluation.ts`, `apps/web/components/document-benchmarks.tsx`; create `apps/web/components/benchmark-run-results.tsx`; test `apps/web/tests/benchmark-run-results.test.tsx` and extend client/benchmark tests.

**Interfaces:**
- Export `createDocumentRun(suiteId: string): Promise<DocumentEvalRun>`, `listDocumentRuns(suiteId?: string): Promise<DocumentEvalRun[]>`, `getDocumentRun(runId: string): Promise<DocumentEvalRun>`, `getDocumentRunResults(runId: string): Promise<DocumentEvalResult[]>`, `cancelDocumentRun(runId: string): Promise<DocumentEvalRun>`, `assessDocumentResult(runId: string,resultId: string,assessment: DocumentAssessment,note: string): Promise<DocumentEvalResult>` with types from Task 8.
- `BenchmarkRunResults({runId}: {runId: string})` polls persisted run/results every 2000 ms only while queued/running, clears timers on unmount, restores current/history selection on return, and offers retry on polling error without discarding stored results.
- Case filters: All, Failed, Unavailable, Errors, Needs human review. Show snapshot expectations beside actual answer, sentence checks, trace versus selected evidence, citations, reviewed version, mode/fallback, elapsed time, and separate human assessment.

- [ ] Write timer-controlled tests for immediate run creation, incremental results, cancel between cases, polling cleanup, restored progress after remount, and polling request failure retaining prior results. Assert globally busy 409 is actionable.
- [ ] Test incomplete/error/unavailable runs never show all-passing; lexical fallback is visible; absent tagged subsets show `Not evaluated`; edited live cases do not change historical expectations; assessment controls do not alter automatic scores.
- [ ] Run `npm test -- tests/benchmark-run-results.test.tsx tests/document-benchmarks.test.tsx tests/document-evaluation-api.test.ts`; require expected red failures.
- [ ] Implement persisted run selection/history and result inspection with shared scoped metrics, existing source links, compact responsive rows, predictable filters, and explicit progress/error/interrupted states. A pass badge is scoped to completed evaluated cases and never claims semantic correctness or vector coverage on fallback.
- [ ] Rerun targeted tests, lint, and TypeScript checking; require green.
- [ ] Commit Task 9 files: `feat: inspect persisted document benchmark runs and failures`.

### Task 10: Whole-Phase Verification, Live Evidence, and Handoff

**Files:** Add `docs/testing/document-benchmarks.md`; adjust only feature-owned code/tests if verification exposes defects. Do not commit private real-document fixtures, screenshots, or expected-source quotes.

**Interfaces:** Consume the complete reviewed workflow; produce a truthful verification report and operator instructions, not a new product API.

- [ ] Run all backend tests with the dedicated test URL: `python -m pytest -q`. Require zero failures; distinguish skipped integration tests from passed tests.
- [ ] Run `npm test`, `npm run lint`, and `node node_modules/typescript/bin/tsc --noEmit --incremental false`; require zero failures/errors and record actual counts.
- [ ] Inspect desktop and narrow/mobile Evaluation Lab and Search using the allowed browser tool. Verify tabs, editor validation/source review, run progress, filters, evidence links, null metrics, and no clipped/overlapping controls. Reuse existing frontend/backend servers unless a separate preview is necessary.
- [ ] Exercise live Paper 10 positive count and missing-GPU cases through the shared BGE/PostgreSQL path. Inspect page 3 evidence; keep reviewed cases local, document actual mode/latency/outcomes, and do not force a 100% result or silently repair the source's numeric inconsistency.
- [ ] Verify missing-document, stale-source, cancellation, fallback, and restart recovery using test-owned data; never delete or reindex the user's documents to provoke failures.
- [ ] Request a fresh independent whole-branch code review; fix confirmed issues with failing tests, then rerun affected and full suites as appropriate.
- [ ] Write the testing guide with restart requirements for additive backend tables, where to create/review cases, how to run/cancel/inspect results, what screenshots demonstrate a failure, and the distinction between automatic checks and human assessment. Training is not required.
- [ ] Check `git diff --check` and status for secrets, uploaded data, and unrelated generated files. Commit feature-owned documentation/fixes only. Report verified results and remaining dataset review work; push/create a PR only when authorized, attach any created PR, and do not merge automatically.

## Self-Review and Execution Gate

- Spec coverage: Tasks 1-2 cover preservation/review/identity; 3-6 cover shared execution, trace, scores, lifecycle and API; 7-9 cover honest labels and UI states; 10 covers full/live verification. Deferred work stays excluded.
- Interfaces: SearchExecution carries pre-pack candidates and full selected source; all new measured values use Measurement/EvaluationMeasurement, separate from legacy EvalRun scalar metrics. Case snapshots, human assessment, and live labels have distinct ownership.
- Review Focus: all five conditions above have explicit tests in their owning tasks.
- Proportion: no implementation bodies or new abstraction framework; tasks follow existing storage, dependency, API, test, and UI patterns.
- Implementation starts only after the user reviews this plan and selects/confirms Native or Subagent-driven execution. Native in this chat is recommended because retrieval, metrics, and persistence have shared interfaces, with a fresh whole-branch review at the end.
