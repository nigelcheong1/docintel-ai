# Local Development

Use Docker for PostgreSQL and run FastAPI/Next.js directly. Commands start at the
repository root unless shown otherwise. Keep services bound to loopback.

## Prerequisites

- Python 3.11 or 3.12, Node.js 24 with npm, and Docker Compose.
- Docker Desktop on Windows with its Linux engine running.
- Tesseract with English language data for image/scanned-PDF OCR. Native-text PDFs
  do not require OCR. Without Tesseract, image inputs report an OCR-required state.
- Network access for initial dependency installation and embedding-model download.
  Cached weights can be reused locally; a GPU or paid API is not required.

## Configure and Start

On a fresh checkout only:

```powershell
Copy-Item .env.example .env
docker compose up -d
```

Never overwrite an existing `.env` containing configured paths or secrets. Backend settings
use the `DOCINTEL_` prefix and read `.env` in the API working directory and `../../.env`.
Environment variables take precedence. The frontend does not read the repository-root
backend `.env`; set its public API URL separately.

### Windows

Backend terminal:

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend terminal from the repository root:

```powershell
cd apps/web
npm ci
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open http://127.0.0.1:3000. If 3000 is occupied, use 3001; the example CORS
configuration includes both loopback ports. Do not stop an unrelated process to free a port.

### Linux and macOS

```bash
cp .env.example .env # fresh checkout only
docker compose up -d
cd apps/api
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal from the repository root:

```bash
cd apps/web
npm ci
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Linux CI exercises the full backend PostgreSQL suite and frontend tests/build.
The documentation does not claim a separately verified macOS desktop installation.

## OCR

Install Tesseract from a trusted distribution and verify `tesseract --version`.
On Ubuntu/Debian, use the `tesseract-ocr` package; on macOS use the Tesseract Homebrew
formula. On Windows, configure an installed executable when it is not on PATH:

```dotenv
DOCINTEL_TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
DOCINTEL_OCR_ENABLED=true
DOCINTEL_OCR_LANGUAGE=eng
DOCINTEL_OCR_DPI=200
DOCINTEL_OCR_MAX_PAGES=25
DOCINTEL_OCR_PAGE_TIMEOUT_SECONDS=20
```

Restart the backend after settings changes. Tesseract is a system dependency, not installed
by `pip install -r requirements.txt`. Existing OCR-required files can be retried/reindexed
after installation. Inspect source images and confidence diagnostics: OCR is not guaranteed
to preserve numbers, reading order, or complex layouts.

## Optional Hosted Generation

The default `DOCINTEL_LLM_PROVIDER=local` uses heuristics. It is not Ollama or another local
chat model. To opt into Groq for summaries, study questions, and learner feedback, set the
following in an ignored backend `.env` and restart:

```dotenv
DOCINTEL_LLM_PROVIDER=groq
DOCINTEL_GROQ_API_KEY=your_private_key
DOCINTEL_LLM_MODEL_NAME=llama-3.1-8b-instant
DOCINTEL_LLM_TIMEOUT_SECONDS=30
```

The model name shown is the app's configured default, not a promise of provider availability.
Check the provider's supported models for your account. Groq requires network access and may
have limits/costs. Context and learner/expected answers can leave the machine. Use only
documents you are authorized to send. Never place provider keys in `NEXT_PUBLIC_` variables,
screenshots, source control, or issue reports. Verified Answers does not use Groq.

## Storage Persistence

Two stores must remain consistent:

| Store | Default | Contains |
| --- | --- | --- |
| PostgreSQL | Named `docintel-postgres-data` Docker volume | Document records, pages/chunks, vectors, study data, benchmark cases/history |
| Originals | `apps/api/storage` | Uploaded PDF/image files used by parsing and source previews |

Relative `DOCINTEL_STORAGE_DIR` paths resolve against the API root, not arbitrary terminal
directories. When multiple Git checkouts share a database, use the same absolute storage path:

```dotenv
DOCINTEL_STORAGE_DIR=C:/your-workspace/docintel-ai/apps/api/storage
```

Back up both the database (for example using `pg_dump`) and original-file directory.
Keep backups outside Git. Moving only database records does not move original files.
Startup adds/synchronizes local schema; it is not a backup or production migration system.
Do not remove/reset Docker volumes to fix an empty document list.

The [public demo](../../demo/README.md) uses a separate `docintel_demo` database and local
storage on ports 8001/3002. Backend tests use another disposable database, not either workspace.

## Verification

From the repository root, prepare a disposable PostgreSQL database:

```powershell
$exists = docker exec docintel-postgres psql -U docintel -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='docintel_test'"
if (-not $exists) { docker exec docintel-postgres createdb -U docintel docintel_test }
docker exec docintel-postgres psql -U docintel -d docintel_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
$env:DOCINTEL_TEST_DATABASE_URL = "postgresql+psycopg://docintel:docintel@localhost:5432/docintel_test"
cd apps/api
.\.venv\Scripts\python.exe -m pytest -q
```

The guard requires an explicit PostgreSQL database with `test` in its name. Integration
fixtures drop/recreate tables there. Never bypass that guard or use a valuable database
simply because its name happens to contain `test`.

Linux equivalent:

```bash
# After creating docintel_test and enabling vector as above:
cd apps/api
DOCINTEL_TEST_DATABASE_URL=postgresql+psycopg://docintel:docintel@localhost:5432/docintel_test .venv/bin/python -m pytest -q
```

Frontend checks from `apps/web`:

```powershell
npm test
npm run lint
node node_modules/typescript/bin/tsc --noEmit --incremental false
npm run build
```

Demo safety checks from the repository root, using the backend environment:

```powershell
.\apps\api\.venv\Scripts\python.exe -m pytest -q demo/tests
```

For a production frontend preview, build with the intended public API URL, then run:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
npm run build
node node_modules/next/dist/bin/next start --hostname 127.0.0.1 --port 3000
```

Public frontend variables are baked into the build; changing them only at `next start`
does not retarget an existing bundle. Do not run two dev servers against the same checkout's
`.next/dev` directory. Use a separate checkout/copy for an isolated simultaneous demo.

## Troubleshooting

| Symptom | Check / Action |
| --- | --- |
| `'next' is not recognized` | Run `npm ci` inside `apps/web`, then `npm run dev`; verify Node/npm are installed. |
| Windows `npm ci` EPERM/SWC lock | Stop the Next.js process using this checkout with Ctrl+C, then retry. Do not indiscriminately kill all Node processes or delete dependency folders while a server uses them. |
| Old uploads disappear | Check the running API URL, database URL, Docker volume, and storage directory. A worktree may use different local settings. Do not reset data. |
| Indexed record but source unavailable | Verify the original file exists under the configured storage; database presence alone is insufficient. |
| OCR required | Check the executable, language data, enabled setting, and page/time limits. Restart, then retry OCR. |
| Lexical fallback | Inspect the reported embedding-provider error, model cache/network, and installed PyTorch/sentence-transformers dependencies. A lexical pass is not a vector retrieval pass. |
| Browser connection/CORS error | Match API base URL and allowed origin including port; restart the relevant server after configuration changes. |
| Draft cannot be reviewed | Read the editor's prerequisite checklist; complete source inspection and current-version save. |
| Abandoned benchmark after restart | It is interrupted, not silently resumed. Inspect saved progress and start another run. |

The `/health` endpoint confirms API responsiveness; it does not certify database, model,
OCR, or answer quality. Include sanitized diagnostics in bug reports, never keys or personal sources.

## Optional FUNSD Experiments

`apps/api/scripts/download_funsd.py` clones ignored `data/raw/funsd` for experiments.
Its repository contains DVC pointers and QA JSON but not all original images. Acquire the
original dataset according to its source terms before image experiments; these fixtures
are separate from uploaded-document benchmarks and the public demo corpus.
