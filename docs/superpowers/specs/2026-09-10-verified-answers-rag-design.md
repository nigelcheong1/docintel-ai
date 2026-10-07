# Verified Answers RAG Design

## Goal

Add a stricter answer pipeline that makes DocIntel AI more competitive for document QA: it should answer only from cited evidence, explain how evidence was selected, abstain when support is weak, handle table-heavy documents better, prepare page-image metadata for future visual retrieval, support multi-hop questions, and measure whether changes improve answer quality.

The user-facing name is **Verified Answers**. Product UI, API labels shown to users, and docs should consistently use that name. Developer-facing code can use neutral names such as `verified`, `evidence_pack`, `verifier`, and `rag_eval`.

## Product Scope

This phase extends the existing local-first RAG workspace. It does not require model training, paid APIs, GPUs, or external vector stores. Optional LLM providers can improve phrasing later, but the core reliability features must work with deterministic local logic.

The target user flow is:

1. Upload or reindex a document.
2. The indexer extracts page text, creates chunks, records page-image metadata, and detects table-like content.
3. The user asks a question in Search.
4. The user can enable **Verified Answers** with a toggle beside the search controls.
5. The backend rewrites/splits the question, runs hybrid retrieval, reranks candidates, builds an evidence pack, generates an answer only from selected evidence, and verifies sentence support.
6. The UI shows answer citations, evidence-pack diagnostics, verifier status, and abstention reasons.
7. The Evaluation page reports retrieval recall, citation accuracy, verifier pass rate, abstention safety, and hallucination risk on golden cases.

## Architecture

### Search Modes

Keep the current search behavior as the default. Add an optional request field:

- `answer_mode: "standard" | "verified"`

When `answer_mode` is `standard`, the existing hybrid retrieval and document-aware answer paths remain backward compatible. When it is `verified`, the route uses the new strict pipeline and returns expanded diagnostics.

### Evidence Pack Builder

Create a focused retrieval module that builds a clean evidence pack before answer generation:

`question -> query rewrite -> optional subqueries -> hybrid retrieval -> rerank -> dedupe/diversify -> selected evidence pack -> answer`

The evidence pack should contain:

- original question
- rewritten query
- subqueries used for multi-hop retrieval
- selected evidence items with chunk id, page, section heading, text, score, source score, retrieval source, and ranking signals
- rejected evidence reasons for the top discarded candidates
- coverage stats such as selected page count, selected chunk count, average support score, and retrieval mode

Selection rules:

- Prefer answer-relevant chunks over merely related chunks.
- Deduplicate repeated chunks and near-duplicate snippets.
- Prefer a small set of diverse pages/sections unless a single precise chunk is enough.
- Preserve exact chunk/page citations.
- Cap context size so answer generation stays fast and stable.

### Multi-Hop Retrieval

Add deterministic query decomposition for questions that ask for multiple facts, comparisons, counts, stages, or "and" clauses. Each subquery retrieves separately through the same hybrid search path. The pack builder then merges results while preserving which subquery selected each evidence item.

Examples:

- "How many results were found and how many remained after screening?"
- "What are the methods and results?"
- "Which table reference includes planning, perception, and embodied execution?"

If decomposition produces weak or duplicate subqueries, fall back to the rewritten original query.

### Answer Generation

Verified Answers should initially use extractive or tightly grounded abstractive generation:

- For precise fact questions, prefer short extractive answers from selected snippets.
- For overview questions, allow a concise synthesis, but every sentence must be supported by selected chunks.
- If an optional LLM provider is enabled, pass only the evidence pack text and require a compact answer with cited support. The verifier still decides whether the final answer is acceptable.

Unsupported claims are removed when the remaining answer is still useful. If removal leaves no useful answer, return `insufficient_evidence`.

### Evidence Verifier

Add a verifier that checks every answer sentence against the selected evidence pack. The first version is deterministic:

- Match important terms, numbers, dates, named entities, acronyms, and table labels.
- Require all numbers/dates in a sentence to appear in cited evidence.
- Require each sentence to have at least one supporting evidence item.
- Flag unsupported sentences, weak support, and citation gaps.

The verifier returns:

- `status: "verified" | "partially_supported" | "unsupported"`
- per-sentence support records
- removed unsupported sentence count
- hallucination risk score
- abstention reason when evidence is too weak

This can later be upgraded with an optional LLM verifier, but the local verifier remains the default.

### Table-Aware Extraction

Add lightweight table detection during indexing before full table OCR/vision work:

- Detect table-like blocks from native PDF text using repeated columns, separators, dense numeric rows, checkmark columns, and table captions.
- Store table records linked to document/page/chunk.
- Store structured rows/cells when extraction is reliable enough; otherwise store a table text block with `extraction_confidence: "low"`.
- Make table cells citeable by recording row index, column label, cell text, source chunk id, and page number.

The first implementation can use PyMuPDF text extraction and heuristics. It does not need Camelot/Tabula unless the current parser cannot capture enough structure.

### Page Image Index

The app already renders page previews on demand. This phase should persist page-image metadata so future visual retrieval can be added cleanly:

- page image availability
- render DPI
- image width and height
- media type
- optional checksum/cache key
- generated-at timestamp

The first implementation may store metadata without eagerly writing every image to disk. If a preview is requested, the metadata can be refreshed after rendering. This prepares the schema for ColPali/ColQwen-style retrieval later without adding GPU dependencies now.

### Evaluation Lab

Expand the Evaluation page and backend golden evaluation to measure the verified pipeline directly. Add metrics:

- answer quality pass rate
- citation accuracy
- retrieval recall at 5
- evidence-pack coverage
- verifier pass rate
- abstention safety
- hallucination risk
- table QA pass rate
- multi-hop QA pass rate

Golden cases should include normal answerable questions, hard negatives, table questions, and multi-hop questions. The UI should show a compact scorecard plus failed case details with the evidence/verifier reason.

## Backend Interfaces

Extend search schemas:

- `SearchRequest.answer_mode`
- `SearchResponse.answer_mode`
- expanded `SearchDiagnostics`
- new `EvidencePackRead`
- new `EvidenceVerifierRead`
- optional `table_citations` on citations or evidence items

Create retrieval modules:

- `app/retrieval/evidence_pack.py`
- `app/retrieval/verifier.py`
- `app/retrieval/multihop.py`

Create document modules:

- `app/documents/tables.py`
- extend `app/documents/page_rendering.py` for metadata refresh

Extend database models:

- `PageImage`
- `DocumentTable`
- `DocumentTableCell`

Use the existing `sync_local_schema` approach to keep local development databases usable without introducing a migration framework in this phase.

## Frontend Interfaces

On the Search page:

- Add a **Verified Answers** toggle beside the search controls.
- Keep the current search button and document selector.
- Show a concise verified answer status badge: `Verified`, `Needs review`, or `Not enough evidence`.
- Add an evidence-pack diagnostics panel with subqueries, selected evidence count, rejected evidence reasons, verifier status, and hallucination risk.
- Keep source preview actions on citations and evidence cards.

On the Evaluation page:

- Rename the page section from only "Universal document QA" to a broader evaluation lab section.
- Add verified-pipeline metrics.
- Show table and multi-hop coverage in quality badges.
- Preserve existing evaluation run history.

## Error Handling

- If vector embeddings fail, verified search can still run lexical retrieval and clearly report the fallback.
- If an optional LLM provider fails, verified search falls back to local extractive answer generation.
- If table extraction is uncertain, store low-confidence table evidence instead of failing document indexing.
- If page image rendering fails, search still works and diagnostics report that page-image metadata is unavailable.
- If evidence verification fails, return `insufficient_evidence` rather than an unsupported answer.

## Testing Requirements

Backend tests:

- Evidence pack builder rewrites queries, dedupes candidates, preserves citations, and records rejected reasons.
- Multi-hop splitter creates useful subqueries for compound questions and falls back for simple questions.
- Verifier accepts supported sentences and rejects unsupported numbers/dates/entities.
- Verified search abstains on weak evidence and returns diagnostics.
- Table extraction stores table/cell records for table-like PDF text.
- Page-image metadata is declared and refreshed without requiring eager image storage.
- Evaluation metrics include verifier, table, multi-hop, abstention, and hallucination-risk dimensions.

Frontend tests:

- Search API client sends `answer_mode`.
- Search page toggles **Verified Answers** and displays verified diagnostics.
- Search results show verifier status, evidence-pack details, and abstention reasons.
- Evaluation page displays the expanded scorecard and failed verified cases.

Verification commands:

- `python -m pytest -q -m "not integration" -k "not uses_hybrid_retrieval_hits and not falls_back_to_ranked_chunks_when_retrieval_has_no_hits and not can_replace_stale_existing_questions"`
- `npm test`
- `npm run lint`
- `python -m compileall app`
- `npm run build`
- `git diff --check`

## Rollout

Implement in one feature branch, but split commits by subsystem:

1. Backend evidence pack, verifier, and multi-hop logic.
2. Search route/schema integration.
3. Table/page-image metadata persistence.
4. Evaluation Lab metrics.
5. Frontend Verified Answers UI.
6. Final verification and pull request.

Existing users can keep using normal search. Verified Answers is opt-in until evaluation metrics show it is consistently better.

## Non-Goals

- No fine-tuning or training in this phase.
- No mandatory paid API provider.
- No GPU-only visual retrieval.
- No full table reconstruction for every possible PDF layout.
- No migration framework replacement.
- No alternate user-facing name for the strict answer mode.
