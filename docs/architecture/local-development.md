# Local Development

Run the database in Docker and the backend and frontend directly from PowerShell. Start all commands from the repository root unless a command changes directories.

## Prerequisites

- Docker Desktop with WSL 2 integration enabled.
- Python 3.11 or 3.12.
- Node.js 24 with `node` and `npm` available in PowerShell.

## Start the Database

```powershell
docker compose up -d
```

## Start the Backend

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend health check:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

## Run Backend Tests Safely

Integration tests require an explicit disposable database and refuse to run against the normal `docintel` development database. Create the dedicated database once, enable pgvector, and export its URL before running the suite:

```powershell
$docintelTestExists = docker exec docintel-postgres psql -U docintel -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='docintel_test'"
if (-not $docintelTestExists) {
  docker exec docintel-postgres createdb -U docintel docintel_test
}
docker exec docintel-postgres psql -U docintel -d docintel_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
$env:DOCINTEL_TEST_DATABASE_URL = "postgresql+psycopg://docintel:docintel@localhost:5432/docintel_test"
cd apps/api
.\.venv\Scripts\python.exe -m pytest -v
```

The integration fixture creates and drops tables only inside `docintel_test`. It has no fallback URL.

## Start the Frontend

Open a second PowerShell window from the repository root:

```powershell
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`.

## Download FUNSD

```powershell
python apps/api/scripts/download_funsd.py
python apps/api/scripts/ingest_funsd.py
```

The download helper clones the FUNSD GitHub repository into ignored `data/raw/funsd`. The clone contains DVC dataset pointers and FUNSD QA JSON files, but not the original raw images. Download the original dataset or retrieve the DVC data before running image-based experiments.
