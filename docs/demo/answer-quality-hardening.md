# Answer-Quality Hardening

**Date:** 2026-10-14. **Scope:** regression comparison on the same 25 independently
source-reviewed labels across six public/fictional documents. This is not a new-document
test, general accuracy estimate, or model comparison. The implementation was developed
against the original failures; this suite is no longer an untouched holdout.

## Recorded Run

- Evaluated implementation: `dbb92e97fc2507095249f90653474a6710a9c33a`.
- The API was restarted on committed code before the run began.
- Run window: 14:48:48 to 14:49:30 UTC on 2026-10-14.
- Local `BAAI/bge-small-en-v1.5`, CPU, 384 dimensions, verified answers, top five.
- Retrieval modes: 24 hybrid, one vector; zero lexical fallbacks, errors, or unavailable cases.
- Mean search execution latency: 1,624 ms across 25 successful executions. This is not a
  controlled performance comparison; it excludes ingestion/model download time.
- Generated answers have no separate human result assessments. Source-label review and
  automatic checks are not human approval of those answers.

The [portable export](evaluation-hardening.json) retains all answers, citations, expected
facts/anchors, and measurement scopes without local database IDs or raw retrieval traces.
The [original baseline](evaluation-results.md) and its JSON export remain unchanged.

## Comparison

| Measurement | Baseline | Hardened | Scope |
| --- | --- | --- | --- |
| Cases passing every automatic check | 18/25 | 25/25 | Frozen regression cases |
| Outcome match | 22/25 | 25/25 | Answerable vs. insufficient evidence |
| Expected fact patterns | 17/30 | 30/30 | Approved literal patterns, not semantic correctness |
| Citation precision | 12/17 | 20/20 | Unique cited chunks matching reviewed anchors |
| Cited-anchor coverage | 12/20 | 20/20 | Required anchors represented by cited text |
| Evidence-pack anchor coverage | 17/20 | 20/20 | Required anchors in selected evidence |
| Reviewed-anchor recall at five | 18/20 | 20/20 | Top five candidates per subquery, before selection |
| Negative outcome match | 6/6 | 6/6 | Reviewed abstention cases |
| Table case checks | 2/2 | 2/2 | Two table-tagged cases only |
| Multi-part case checks | 1/5 | 5/5 | Five multi-part cases only |
| Deterministic sentence support | See baseline export | 23/23 | Accepted answer sentences, not entailment probabilities |

Labels, source-review timestamps, case versions, facts, anchors, tags, source files, and
scoring rules were not modified to improve the comparison. No failed cases were removed.

## Changes and Safeguards

Answer selection now ranks requested-value-bearing sentences before the verified top-five
cutoff, preserves complete answer spans, and treats headings as hints instead of hard
filters. Explicit dates, processing stages, counted named lists, billed-to roles, and
item-price associations have conservative checks. Publication identifiers cannot supply
a date; education start/expected years cannot supply a completion date.

Compound questions support who/when follow-ups and shared price fields. Quoted names and
item-name conjunctions are preserved. Pronoun follow-ups require a shared selected span
or matching named entity, rather than combining different projects' facts.

Regression tests also cover unrelated publication dates, role/title confusion, contents-page
enumerations, mathematical degrees vs. education, conditional questions, cost functions,
and legitimate start-plus-completion sentences. These are synthetic checks, not additional
independently reviewed document cases.

## Remaining Limits

All ranking, decomposition, value checks, entity matching, and sentence verification remain
heuristic. Unrecognized wording, punctuation, date formats, item names, or references can
abstain or produce imperfect selections. These checks do not establish semantic entailment,
resolve source contradictions, or make the system production-ready. No model training or
trained reranker was introduced.

[Eight new question drafts](../../demo/unseen-cases.json) were loaded into a separate suite
on the same documents. At the maintainer's request they remain **draft and unscored**.
They do not demonstrate unseen-document generalization. Review them independently before
measurement; keep their results separate and retain any failures.

The published screenshots and walkthrough depict the earlier baseline. They were not
relabelled to imply that the new comparison was already shown in those captures.

## Reproduce Safely

Use the isolated sample workspace described in [the demo guide](../../demo/README.md).
Never point integration tests or public demo tooling at personal uploads. A fresh import
has draft labels and requires independent review; the loader does not auto-approve them.

After committing the implementation, restart the demo API, run the original reviewed suite,
and export its completed run separately:

```powershell
python demo/export_benchmark.py RUN_UUID --report-kind hardening
```

Inspect source previews and answers, not only the green case badges. For a portfolio v1,
freeze major feature expansion; use this comparison as documented regression evidence and
describe the app as a local document intelligence MVP.
