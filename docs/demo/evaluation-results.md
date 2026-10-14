# Source-Reviewed Demo Baseline

**Date:** 2026-10-13. **Scope:** 25 human-reviewed labels across six allowlisted inputs:
two public-source PDFs and four original fictional examples. Nineteen answerable cases,
six negative cases, two table-tagged cases, three OCR cases, and five multi-part cases.
The maintainer confirmed completion of independent source review; API snapshots recorded
all 25 as reviewed and ready before execution. Generated answers have **not** received
separate human result assessments. This is not an external benchmark or model comparison.

## Execution

- 25/25 finished; 18 automatic passes, seven failures, zero unavailable, zero errors.
- Local `BAAI/bge-small-en-v1.5`, CPU, 384 dimensions, top-k 5, Verified Answers.
- 24 hybrid executions, one vector execution, zero lexical fallbacks.
- Mean execution latency: 1,423 ms/case on this already-initialized local run. This is not
  a hardware-normalized latency benchmark and excludes ingestion/model download time.
- [Portable JSON result record](evaluation-baseline.json) retains scoped measurements,
  approved facts/anchors, answer text/citations, and every failure. Original files and
  their checksums are in [the catalog](../../demo/sources.json).

The pipeline snapshot records base HEAD `1381aa5`; the run used uncommitted portfolio-v1
polish changes. It is a dated baseline, not a claim of bit-identical replay on every device.
Subsequent regression fixes in this phase do not silently replace this historical run.

## Measurements

| Check | Numerator / Denominator | Meaning |
| --- | --- | --- |
| Cases passing all automatic checks | 18/25 | Strict case-level gate |
| Outcome match | 22/25 | Returned answer vs. abstention matches reviewed outcome |
| Fact pattern match | 17/30 | Required literal/token patterns match the generated answer |
| Citation precision | 12/17 | Unique cited chunks match reviewed anchors |
| Citation anchor coverage | 12/20 | Reviewed anchors represented by cited source text |
| Evidence-pack anchor coverage | 17/20 | Reviewed anchors in selected evidence |
| Reviewed-anchor recall at 5 | 18/20 | Anchors across top five reranked candidates per subquery |
| Negative outcome match | 6/6 | Abstention on reviewed negative cases |
| Sentence checker support | 18/18 | Returned sentences accepted by deterministic checker |
| Table-tagged case checks | 2/2 | Small table-only subset |
| Multi-part case checks | 1/5 | Small multi-part subset |

Sentence support is **not** answer relevance, completeness, factual truth, or a calibrated
hallucination probability. An extract supported by a source can still answer the wrong
question. Pattern/anchor gates can also reject useful alternative wording or source pages;
they require human interpretation, not silent relaxation of the labels.

## Visible Failures

| Question / Source | Observed Problem | Next Investigation |
| --- | --- | --- |
| Visual retrieval benchmark / ColPali | Selected a noisy conclusion extract on page 10 instead of the approved page-1 anchor; fact and citation gates failed | Sentence boundaries, answer selection, and strict-pattern limitations |
| Benchmark and mechanism / ColPali | Missing matching-mechanism fact and anchors | Subquery recall and complete multi-part selection |
| Publication date / NIST | Returned unrelated interpretability prose instead of January 2023 | Date-intent retrieval and relevance gate |
| Four Core functions / NIST | Returned a generic statement without naming the functions | Prefer explicit enumerations over generic keyword overlap |
| Supplier and billed-to party / invoice | Abstained despite both roles in selected source | Multi-part role matching |
| Degree and completion year / fictional resume | Abstained despite available education text | Reference resolution and date/education coverage |
| Coffee and sandwich prices / OCR receipt | Abstained despite available OCR item prices | Conjoined item queries and amount associations |

All failures remain in the published record. No cases were removed, auto-approved, or
relabelled after observing outcomes. Keep this pack as a regression baseline; improvements
need a separate run plus additional held-out documents, not only tuning to these 25 cases.

## Portfolio Position

The historical baseline above is preserved. See the separate
[2026-10-14 hardening comparison](answer-quality-hardening.md) for a later run on the same
frozen suite. It does not convert these development cases into held-out accuracy evidence.

This project demonstrates end-to-end ingestion, local retrieval, citation inspection,
explicit abstention, persisted evaluations, and honest failure analysis. It is suitable
to describe as a **local portfolio MVP**, not a production service or universally accurate
RAG system. Freeze feature expansion; prioritize relevance and multi-part completeness
as the next focused quality phase. Unit/CI checks and document-quality checks are separate.

Suggested resume wording:

> Built a full-stack document intelligence workspace with Next.js, FastAPI, PostgreSQL/
> pgvector, local OCR, hybrid retrieval, cited answers, and a versioned evaluation lab;
> evaluated 25 independently source-reviewed cases across six public/fictional documents
> and documented retrieval and multi-part failure modes.
