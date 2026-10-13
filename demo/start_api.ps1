param([string]$Python = "python", [string]$TesseractCommand = "")
$ErrorActionPreference = "Stop"
$pythonExecutable = (Get-Command $Python -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
$root = Split-Path -Parent $PSScriptRoot
$exists = docker exec docintel-postgres psql -U docintel -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='docintel_demo'"
if ($LASTEXITCODE -ne 0) { throw "Start the existing database with docker compose up -d first." }
if (-not $exists) {
    docker exec docintel-postgres createdb -U docintel docintel_demo
    if ($LASTEXITCODE -ne 0) { throw "Could not create the isolated demo database." }
}
docker exec docintel-postgres psql -U docintel -d docintel_demo -c "CREATE EXTENSION IF NOT EXISTS vector;"
if ($LASTEXITCODE -ne 0) { throw "Could not enable pgvector in the demo database." }
$env:DOCINTEL_APP_NAME = "DocIntel AI Demo API"
$env:DOCINTEL_DATABASE_URL = "postgresql+psycopg://docintel:docintel@localhost:5432/docintel_demo"
$env:DOCINTEL_STORAGE_DIR = Join-Path $PSScriptRoot ".local/storage"
$env:DOCINTEL_LLM_PROVIDER = "local"
$env:DOCINTEL_BACKEND_CORS_ORIGINS = '["http://localhost:3002","http://127.0.0.1:3002"]'
if ($TesseractCommand) { $env:DOCINTEL_TESSERACT_CMD = $TesseractCommand }
Set-Location -LiteralPath (Join-Path $root "apps/api")
& $pythonExecutable -m uvicorn app.main:app --host 127.0.0.1 --port 8001
exit $LASTEXITCODE
