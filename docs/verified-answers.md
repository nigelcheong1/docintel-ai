# Verified Answers

## Using the feature

1. Open **Search** and select a document, or leave **All documents** selected.
2. Enable **Verified Answers** beside the query field and submit a question.
3. Open **Evidence selection details** to inspect the rewritten query, subqueries, and rejected evidence. Open **Sentence support** for the supporting source links.
4. Open **Evaluation** in the sidebar. The **Evaluation Lab** page includes the Verified Answers benchmark, case details, and existing evaluation history.
5. Reindex existing documents to populate table/cell and page-image metadata. Opening a source preview refreshes the image checksum and pixel dimensions.

Verified Answers uses local query planning, the existing hybrid retriever and reranker, a small evidence pack, extractive answers, and sentence checks. It does not require model training or a new API key. Standard search remains the default.

## Reliability and Scope

- Each requested fact must pass relevance checks. Questions with insufficient evidence return an abstention. Multi-part questions retrieve with separate embeddings and reserve evidence context for each part.
- Verification checks terms, capitalized entities, numbers, percentage units, and negation against individual evidence sentences. These are deterministic checks, not a learned entailment model or a calibrated probability of correctness. The reported hallucination-risk value is the unsupported-sentence fraction.
- Page/chunk citations are visible in Search. Table records retain row/column positions, available header labels, cell text, and source chunk/page links; a separate cell-level retrieval engine and citation viewer are future work.
- Tab/pipe-delimited tables preserve header labels and rows. Ambiguous native-text tables retain low-confidence source text. This is not complete reconstruction of every PDF table layout.
- Page-image metadata is stored during indexing; previews render on demand and refresh metadata without rendering twice. No visual embedding index or GPU dependency is added.
- Benchmark values are measured on local synthetic fixtures using lexical retrieval, reranking, evidence selection, and verification. They do not establish accuracy on arbitrary uploaded PDFs or evaluate vector retrieval quality. A retrieval-drop regression verifies that recall and verifier scores fall when relevant evidence disappears.

## Verification

Verified locally on this feature branch:

- 232 backend tests passed; 62 cases deselected by the documented local non-integration filter.
- 3 focused Verified Answers route tests passed, including distinct subquery embeddings.
- 99 web tests passed; frontend lint, TypeScript/production build, backend compile, and whitespace checks passed.
- Playwright checked Search and Evaluation at 1440, 900, and 390 pixels, including the toggle and expanded diagnostics. No page errors or horizontal overflow were found. Browser API responses used generated local fixtures.
- A SQLite-backed preview endpoint test verified that checksums and rendered dimensions are persisted and each preview renders only once.

PostgreSQL integration tests were not run locally: Docker and a local PostgreSQL service were unavailable. The existing GitHub CI workflow runs the full backend suite against a dedicated pgvector PostgreSQL database. That suite must pass before merging.

## Review Decisions

The final branch review was a self-review; no independent reviewer tool was available. It added regression tests and fixed unrelated-evidence acceptance, incomplete multi-part answers, reused subquery embeddings, context starvation, repeated evidence, page counting across documents, changed entities/negation/percentage units, table truncation/source links, and disconnected preview metadata.

The initial plan supplied hand-selected fixture evidence and coverage labels. The final implementation runs fixture retrieval and evidence selection and exposes measured metrics instead, so failures can affect the scorecard. This expands the evaluation work to satisfy the design's promised metrics.

The initial decision to keep visible citations at chunk/page level remains in effect; cell metadata is groundwork for a later viewer and retrieval extension. The cost is that this phase does not expose individual cells as independently clickable citations. Search result cards are built from the selected pack so each answer citation can be opened.

Deferred test coverage from the earlier review: more evidence-pack diagnostic metadata cases and mixed qualitative verifier cases. Existing accent borders in Search were retained to match the application's current design; the UI detector reported those existing borders.
