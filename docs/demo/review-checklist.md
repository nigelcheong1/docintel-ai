# Source Review Checklist

Fresh imports contain **25 draft cases**; importing does not approve labels. This is a mixed
corpus of two public-source documents and four fictional examples. It is not
a representative accuracy benchmark. Machine checks confirmed the 20 positive
anchor spans exist in the indexed source text; that does not establish correct
labels, semantic answer quality, or safe abstention.

The maintainer independently reviewed all 25 labels in the isolated workspace on
2026-10-13 before the [recorded baseline run](evaluation-results.md). This record is
separate from the draft templates and does not approve the generated answers.

Open the isolated [Evaluation Lab](http://127.0.0.1:3002/evaluation). Select
**Portfolio source-review candidates**, then edit each case. Check every fact
and source anchor before **Mark reviewed**. For negative cases, inspect the
whole source, check the rationale, and explicitly confirm the scope review.
Correct ambiguous or wrong labels before running anything. Do not mark cases
reviewed because an automated answer happened to match.

| Case | Source | Expected Outcome | Review Focus |
| --- | --- | --- | --- |
| `paper-benchmark` | ColPali, PDF p.1 | Answerable | ViDoRe benchmark name |
| `paper-input` | ColPali, PDF p.1 | Answerable | Images of document pages |
| `paper-matching` | ColPali, PDF p.1 | Answerable | Late interaction mechanism |
| `paper-multi` | ColPali, PDF p.1 | Answerable | Both benchmark and mechanism |
| `paper-negative` | Full ColPali paper | Not enough evidence | Publisher invoice number absent |
| `framework-date` | AI RMF, PDF p.2 | Answerable | January 2023 publication date |
| `framework-functions` | AI RMF, PDF p.25 | Answerable | GOVERN, MAP, MEASURE, MANAGE |
| `framework-voluntary` | AI RMF, PDF p.7 | Answerable | Voluntary use |
| `framework-table` | AI RMF, PDF p.27 | Answerable | Exact GOVERN 1.1 row |
| `framework-negative` | Full AI RMF report | Not enough evidence | No required API key |
| `invoice-total` | Fictional invoice p.1 | Answerable | USD 550.00 total, not subtotal |
| `invoice-due` | Fictional invoice p.1 | Answerable | Due date and net-30 terms |
| `invoice-parties` | Fictional invoice p.1 | Answerable | Supplier and billed-to roles |
| `invoice-table` | Fictional invoice p.1 | Answerable | USD 300.00 line total, not unit price |
| `invoice-negative` | Full fictional invoice | Not enough evidence | No bank account number |
| `contract-parties` | Fictional agreement p.1 | Answerable | Both parties |
| `contract-confidentiality` | Fictional agreement p.1 | Answerable | 12 months after termination |
| `contract-termination` | Fictional agreement p.1 | Answerable | 14-day written notice |
| `contract-negative` | Full fictional agreement | Not enough evidence | No governing-law clause |
| `resume-skills` | Fictional resume p.1 | Answerable | Listed skills only |
| `resume-education` | Fictional resume p.1 | Answerable | Degree and completion year |
| `resume-negative` | Full fictional resume | Not enough evidence | No birth date |
| `receipt-total` | Fictional receipt image | Answerable | OCR total agrees with image |
| `receipt-items` | Fictional receipt image | Answerable | Both item-price associations |
| `receipt-negative` | Full fictional receipt image | Not enough evidence | Cash payment; no card number |

After review, run the benchmark and inspect failures, source pages, citations,
fallback counts, and human assessments. Publish the actual measurements with
their denominators, model/mode, and corpus scope. Do not hide failing cases,
silently weaken labels, or turn an untested subset into a passing percentage.

The enrolment letter and both personal resumes are absent from the isolated
workspace. The fictional resume is newly authored; it is not derived from any
personal upload. Sources and checksums are recorded in [the demo catalog](../../demo/sources.json).
