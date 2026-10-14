# Shareable Demo Pack

This workspace contains only the fixed source allowlist in [sources.json](sources.json).
It excludes all existing personal uploads, including the enrolment letter and both resumes.
The original files in the personal workspace are not deleted or reindexed.

## Documents

| File | Origin | Purpose |
| --- | --- | --- |
| [ColPali paper](documents/colpali-paper.pdf) | arXiv:2407.01449v6, CC0 linked by its abstract | Real research-paper ingestion and evidence QA |
| [AI RMF 1.0](documents/nist-ai-rmf-1.0.pdf) | NIST AI 100-1, January 2023 | Real technical-report and table evidence |
| [Invoice](documents/sample-invoice.pdf) | Original fictional example | Totals, dates, party roles, line-item table |
| [Agreement](documents/sample-contract.pdf) | Original fictional example | Obligations, confidentiality, termination |
| [Resume](documents/sample-resume.pdf) | Original fictional candidate | Skills, education, projects; no real personal data |
| [Receipt image](documents/sample-receipt.png) | Raster of an original fictional receipt | Genuine local OCR path |

The [receipt source PDF](documents/sample-receipt-source.pdf) is retained for reproducibility,
not uploaded as an additional text-only input. Public originals are unmodified; source URLs,
versions, and SHA-256 checksums are in the catalog. No endorsement by NIST or paper authors
is implied. NIST/third-party notices remain in the report.

Original fictional sample documents are dedicated under [CC0-1.0](https://creativecommons.org/publicdomain/zero/1.0/)
for this demo. That notice does not license the entire app or third-party sources.
The [NIST publication policy](https://www.nist.gov/nist-research-library/nist-publications)
and [ColPali abstract/license link](https://arxiv.org/abs/2407.01449v6) document source permissions.

## Isolated Setup

First install the normal backend/frontend prerequisites. Start the existing PostgreSQL
container with `docker compose up -d`; keep its volume. The demo creates `docintel_demo`,
never drops it, and stores files in ignored `demo/.local/storage`.

From the repository root in PowerShell:

```powershell
.\demo\start_api.ps1 -Python .\apps\api\.venv\Scripts\python.exe -TesseractCommand "C:/Program Files/Tesseract-OCR/tesseract.exe"
```

The helper resolves the Python executable before changing to `apps/api`, so a relative
virtual-environment path from the repository root is supported.

In a second terminal at the repository root:

```powershell
.\apps\api\.venv\Scripts\python.exe demo/load_demo.py --api http://127.0.0.1:8001
```

The loader checks local and existing-upload source checksums, loopback port 8001, API
service identity, and existing workspace filenames before writing. It refuses port 8000,
non-allowlisted workspaces, duplicate names, and substituted contents.
It adds missing samples/cases without deleting data or automatically approving reviews.

For the demo frontend, use a separate checkout/copy if another web server is running:

```powershell
cd apps/web
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8001"
npm run build
node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3002
```

Open http://127.0.0.1:3002. Do not change the normal workspace's API URL to produce public
screenshots. Verify the displayed document list contains only the six catalog entries.

On Linux/macOS, create `docintel_demo`, enable pgvector, and launch the normal API command
with `DOCINTEL_APP_NAME='DocIntel AI Demo API'`, the demo database URL, an absolute demo
storage path, local provider, CORS origin `http://127.0.0.1:3002`, and port 8001. The same
Python loader then applies its safety checks. Tesseract must be configured/on PATH.

## Review Before Measurement

[cases.json](cases.json) contains **25 drafts across six documents**, with 19 answerable
and six negative candidates. Twenty positive anchor spans were machine-matched to indexed
text, including OCR. This is not human label approval or a passing evaluation result.

Use [the source-review checklist](../docs/demo/review-checklist.md). Verify facts, exact page
anchors, and full-document absence rationales independently. Correct wrong/ambiguous labels,
then mark reviewed and run the production benchmark. Publish actual successes and failures
with corpus scope/denominators; do not claim representative real-world accuracy from this
mixed public/fictional pack.

The maintainer completed independent review of all 25 labels on 2026-10-13 in the isolated
workspace. The [recorded baseline](../docs/demo/evaluation-results.md) has 18 automatic
passes and seven failures. This does not auto-approve a fresh import: the distributed JSON
remains draft, and generated answers have not received separate human result assessments.

### Additional Draft Questions

[unseen-cases.json](unseen-cases.json) adds eight new questions in a separate suite on the
same sample documents. They are **not independently reviewed or scored**. This is a
question-level follow-up set, not held-out-document generalization. Leave them draft until
a human checks the sources and absence rationale; do not tune on their outputs and then
describe them as an untouched test set.

From the repository root, with the isolated API running:

```powershell
.\apps\api\.venv\Scripts\python.exe demo/load_demo.py --case-pack unseen-cases.json
```

Select **Portfolio unseen-question source-review candidates** in Evaluation Lab. The loader
writes separate local workspace metadata and does not change reviews in the original suite.

## Media and Rebuilding

Screenshots in `docs/demo/screenshots` are captured from the isolated app, not mockups or
redacted personal screens. The captioned walkthrough uses those real screenshots and is
labelled as a screen-based walkthrough, not a continuous recording.

`generate_samples.py` rebuilds the four original fictional PDFs using ReportLab. It is an
optional authoring dependency, not required to upload the committed samples. Rasterize the
receipt source for the OCR example. If rebuilding files changes bytes, review and update
catalog checksums intentionally; the loader will reject unreviewed substitutions.

Run loader safeguards with `python -m pytest -q demo/tests`. Keep `demo/.local` ignored;
it contains generated storage, logs, process-specific IDs, and frontend build output.

With FFmpeg installed, `python demo/build_walkthrough.py` rebuilds the 48-second silent
walkthrough. On Linux/macOS supply an installed TrueType font via `--font /absolute/path.ttf`.
Its captions and screenshots are fixed to the published baseline; review them before
replacing footage. `python demo/export_benchmark.py RUN_UUID` exports a completed,
source-reviewed demo run without local database IDs or full retrieval traces, after
verifying the workspace's original-file checksums. Review the export before publishing.

For the hardening comparison, commit the evaluated implementation before starting the run,
then use `python demo/export_benchmark.py RUN_UUID --report-kind hardening`. This writes
`docs/demo/evaluation-hardening.json` separately and preserves the historical baseline.
The published screenshots/video still depict the dated baseline, not the new comparison.
