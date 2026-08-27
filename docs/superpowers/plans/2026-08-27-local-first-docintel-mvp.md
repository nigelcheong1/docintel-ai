# Local-First DocIntel MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local-only full-stack document intelligence MVP that uploads PDFs, extracts text, creates local embeddings, stores vectors in pgvector, returns cited retrieval results, and reports simple retrieval metrics.

**Architecture:** The project is a monorepo with a FastAPI backend, a Next.js frontend, and PostgreSQL with pgvector running through Docker Compose. Backend and frontend run on the host during development while Docker supplies database infrastructure. The MVP is retrieval-first: no paid AI APIs and no generated answers until the retrieval pipeline is reliable.

**Tech Stack:** Next.js, TypeScript, Tailwind CSS, FastAPI, Python 3.11 or 3.12, SQLAlchemy, PostgreSQL, pgvector, PyMuPDF, sentence-transformers, BAAI/bge-small-en-v1.5, pytest, Vitest, Docker Compose.

**Spec:** `docs/superpowers/specs/2026-08-27-local-only-docintel-design.md`

## Global Constraints

- The first release will not use OpenAI, Anthropic, hosted vector databases, or paid APIs.
- Week one indexes PDFs; image uploads are stored with a clear deferred-OCR status.
- Docker runs PostgreSQL and pgvector; backend and frontend run on the host during development.
- Local embedding model is `BAAI/bge-small-en-v1.5`.
- Embedding vectors are 384-dimensional and stored as `vector(384)`.
- Datasets, uploaded documents, local models, database files, and `.env` files must not be committed.
- Ollama answer generation, OCR, authentication, cloud deployment, fine-tuning, and bounding-box overlays are outside this MVP plan.
- Frontend first screen is the usable app, not a marketing landing page.
- UI should be quiet, practical, work-focused, and evidence-first.
- Windows PowerShell is the primary local command environment for this project.

---

## File Structure Map

Create or modify these files during implementation:

```text
docintel-ai/
  .env.example
  .github/workflows/ci.yml
  README.md
  docker-compose.yml
  infra/docker/001-init-pgvector.sql
  apps/
    api/
      requirements.txt
      pytest.ini
      app/
        __init__.py
        main.py
        api/__init__.py
        core/config.py
        db/__init__.py
        db/session.py
        db/models.py
        db/init_db.py
        documents/__init__.py
        documents/router.py
        documents/schemas.py
        documents/storage.py
        documents/parser.py
        documents/chunker.py
        documents/service.py
        retrieval/__init__.py
        retrieval/embeddings.py
        retrieval/router.py
        retrieval/search.py
        evaluation/__init__.py
        evaluation/metrics.py
        evaluation/router.py
      scripts/
        download_funsd.py
        ingest_funsd.py
      tests/
        conftest.py
        test_health.py
        core/test_config.py
        db/test_models.py
        documents/test_storage.py
        documents/test_parser.py
        documents/test_chunker.py
        retrieval/test_embeddings.py
        retrieval/test_search_formatting.py
        evaluation/test_metrics.py
    web/
      package.json
      tsconfig.json
      next.config.ts
      postcss.config.mjs
      tailwind.config.ts
      vitest.config.ts
      app/globals.css
      app/layout.tsx
      app/page.tsx
      app/documents/page.tsx
      app/search/page.tsx
      app/evaluation/page.tsx
      components/app-shell.tsx
      components/document-list.tsx
      components/evaluation-summary.tsx
      components/search-results.tsx
      components/status-badge.tsx
      components/upload-panel.tsx
      lib/api.ts
      lib/types.ts
      tests/setup.ts
      tests/api-client.test.ts
      tests/status-badge.test.tsx
  docs/
    architecture/local-development.md
    architecture/system-overview.md
    architecture/system-overview.mmd
```

Responsibility boundaries:

- `apps/api/app/core`: configuration and app-wide settings only.
- `apps/api/app/db`: database connection, tables, and initialization only.
- `apps/api/app/documents`: upload validation, local storage, parsing, chunking, and document indexing orchestration.
- `apps/api/app/retrieval`: embedding provider abstraction and vector search.
- `apps/api/app/evaluation`: deterministic retrieval metrics with no paid LLM calls.
- `apps/web/lib`: typed API client and shared frontend types.
- `apps/web/components`: reusable UI components with no direct database or filesystem logic.
- `apps/web/app`: route-level screens and data-flow composition.
- `infra/docker`: database init scripts used by Docker Compose.

---

## Task 1: Backend Foundation and Docker Infrastructure

**Files:**
- Create: `.env.example`
- Create: `docker-compose.yml`
- Create: `infra/docker/001-init-pgvector.sql`
- Create: `apps/api/requirements.txt`
- Create: `apps/api/pytest.ini`
- Create: `apps/api/app/__init__.py`
- Create: `apps/api/app/main.py`
- Create: `apps/api/app/core/config.py`
- Test: `apps/api/tests/test_health.py`
- Test: `apps/api/tests/core/test_config.py`

**Interfaces:**
- Produces: `Settings` class in `app.core.config` with `app_name: str`, `database_url: str`, `storage_dir: Path`, `max_upload_mb: int`, `embedding_model_name: str`, `embedding_dimension: int`, and `backend_cors_origins: list[str]`.
- Produces: `get_settings() -> Settings`.
- Produces: `create_app() -> FastAPI`.
- Produces: `GET /health` returning `{"status": "ok", "service": "DocIntel AI API"}`.

- [ ] **Step 1: Create backend dependency and test configuration files**

Create `apps/api/requirements.txt`:

```text
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic-settings==2.7.1
python-multipart==0.0.20
SQLAlchemy==2.0.36
psycopg[binary]==3.2.3
pgvector==0.3.6
PyMuPDF==1.25.1
sentence-transformers==3.3.1
numpy==2.2.1
pytest==8.3.4
httpx==0.28.1
```

Create `apps/api/pytest.ini`:

```ini
[pytest]
pythonpath = .
testpaths = tests
markers =
    integration: tests that require Docker services
```

- [ ] **Step 2: Create environment and Docker database files**

Create `.env.example`:

```text
DOCINTEL_APP_NAME=DocIntel AI API
DOCINTEL_DATABASE_URL=postgresql+psycopg://docintel:docintel@localhost:5432/docintel
DOCINTEL_STORAGE_DIR=storage
DOCINTEL_MAX_UPLOAD_MB=20
DOCINTEL_EMBEDDING_MODEL_NAME=BAAI/bge-small-en-v1.5
DOCINTEL_EMBEDDING_DIMENSION=384
DOCINTEL_BACKEND_CORS_ORIGINS=["http://localhost:3000"]
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

Create `docker-compose.yml`:

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg17
    container_name: docintel-postgres
    environment:
      POSTGRES_USER: docintel
      POSTGRES_PASSWORD: docintel
      POSTGRES_DB: docintel
    ports:
      - "5432:5432"
    volumes:
      - docintel-postgres-data:/var/lib/postgresql/data
      - ./infra/docker/001-init-pgvector.sql:/docker-entrypoint-initdb.d/001-init-pgvector.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U docintel -d docintel"]
      interval: 5s
      timeout: 3s
      retries: 10

volumes:
  docintel-postgres-data:
```

Create `infra/docker/001-init-pgvector.sql`:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

- [ ] **Step 3: Install backend dependencies**

Run:

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Expected: all packages install successfully.

- [ ] **Step 4: Write failing health and config tests**

Create `apps/api/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_service_status():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "DocIntel AI API"}
```

Create `apps/api/tests/core/test_config.py`:

```python
from pathlib import Path

from app.core.config import Settings


def test_settings_have_local_only_defaults():
    settings = Settings()

    assert settings.app_name == "DocIntel AI API"
    assert settings.embedding_model_name == "BAAI/bge-small-en-v1.5"
    assert settings.embedding_dimension == 384
    assert settings.storage_dir == Path("storage")
    assert "localhost:5432/docintel" in settings.database_url
```

- [ ] **Step 5: Run tests to verify they fail before implementation**

Run:

```powershell
pytest tests/test_health.py tests/core/test_config.py -v
```

Expected: tests fail because `app.main` and `app.core.config` do not exist.

- [ ] **Step 6: Implement settings and health endpoint**

Create `apps/api/app/__init__.py` as an empty package file.

Create `apps/api/app/core/config.py`:

```python
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DOCINTEL_", env_file=(".env", "../../.env"), extra="ignore")

    app_name: str = "DocIntel AI API"
    database_url: str = "postgresql+psycopg://docintel:docintel@localhost:5432/docintel"
    storage_dir: Path = Path("storage")
    max_upload_mb: int = 20
    embedding_model_name: str = "BAAI/bge-small-en-v1.5"
    embedding_dimension: int = 384
    backend_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

Create `apps/api/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
```

- [ ] **Step 7: Validate Docker Compose syntax**

Run:

```powershell
cd ..\..
docker compose config
```

Expected: Compose prints normalized configuration with a `postgres` service and no errors.

- [ ] **Step 8: Run tests to verify foundation passes**

Run:

```powershell
cd apps/api
pytest tests/test_health.py tests/core/test_config.py -v
```

Expected: 2 tests pass.

- [ ] **Step 9: Commit foundation**

Run:

```powershell
cd ..\..
git add .env.example docker-compose.yml infra/docker/001-init-pgvector.sql apps/api
git commit -m "feat: add backend foundation and docker database"
```

---

## Task 2: Database Models and Session Management

**Files:**
- Create: `apps/api/app/db/__init__.py`
- Create: `apps/api/app/db/session.py`
- Create: `apps/api/app/db/models.py`
- Create: `apps/api/app/db/init_db.py`
- Test: `apps/api/tests/db/test_models.py`

**Interfaces:**
- Consumes: `get_settings() -> Settings`.
- Produces: `Base` declarative model base.
- Produces: `DocumentStatus` enum with values `uploaded`, `processing`, `indexed`, `deferred_ocr`, and `failed`.
- Produces models: `Document`, `Page`, `Chunk`, `ChunkEmbedding`, `Question`, `RetrievalResult`, `EvalRun`.
- Produces: `engine`, `SessionLocal`, `get_db() -> Iterator[Session]`.
- Produces: `init_db() -> None`.

- [ ] **Step 1: Write failing model tests**

Create `apps/api/tests/db/test_models.py`:

```python
from app.db.models import ChunkEmbedding, DocumentStatus


def test_document_status_values_are_stable():
    assert DocumentStatus.UPLOADED.value == "uploaded"
    assert DocumentStatus.PROCESSING.value == "processing"
    assert DocumentStatus.INDEXED.value == "indexed"
    assert DocumentStatus.DEFERRED_OCR.value == "deferred_ocr"
    assert DocumentStatus.FAILED.value == "failed"


def test_chunk_embedding_uses_384_dimensions():
    column_type = ChunkEmbedding.__table__.columns["embedding"].type

    assert getattr(column_type, "dim", None) == 384
```

- [ ] **Step 2: Run tests to verify they fail before implementation**

Run:

```powershell
cd apps/api
pytest tests/db/test_models.py -v
```

Expected: tests fail because `app.db.models` does not exist.

- [ ] **Step 3: Implement session management**

Create `apps/api/app/db/__init__.py` as an empty package file.

Create `apps/api/app/db/session.py`:

```python
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Implement database models**

Create `apps/api/app/db/models.py`:

```python
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    INDEXED = "indexed"
    DEFERRED_OCR = "deferred_ocr"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_path: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status", values_callable=lambda enum: [item.value for item in enum]),
        nullable=False,
        default=DocumentStatus.UPLOADED,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    pages: Mapped[list["Page"]] = relationship(back_populates="document", cascade="all, delete-orphan")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class Page(Base):
    __tablename__ = "pages"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    width: Mapped[float | None]
    height: Mapped[float | None]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[Document] = relationship(back_populates="pages")
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="page", cascade="all, delete-orphan")


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    page_id: Mapped[str] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_estimate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    layout: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped[Document] = relationship(back_populates="chunks")
    page: Mapped[Page] = relationship(back_populates="chunks")
    embedding: Mapped["ChunkEmbedding"] = relationship(back_populates="chunk", cascade="all, delete-orphan")


class ChunkEmbedding(Base):
    __tablename__ = "chunk_embeddings"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, unique=True)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    chunk: Mapped[Chunk] = relationship(back_populates="embedding")


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    retrieval_results: Mapped[list["RetrievalResult"]] = relationship(back_populates="question", cascade="all, delete-orphan")


class RetrievalResult(Base):
    __tablename__ = "retrieval_results"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), nullable=False)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False)
    score: Mapped[float] = mapped_column(nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    question: Mapped[Question] = relationship(back_populates="retrieval_results")
    chunk: Mapped[Chunk] = relationship()


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    metrics: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
```

- [ ] **Step 5: Implement database initialization**

Create `apps/api/app/db/init_db.py`:

```python
from app.db.models import Base
from app.db.session import engine


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 6: Register database initialization on API startup**

Modify `apps/api/app/main.py`:

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.init_db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
```

- [ ] **Step 7: Run database model tests**

Run:

```powershell
cd apps/api
pytest tests/db/test_models.py -v
```

Expected: 2 tests pass.

- [ ] **Step 8: Run Docker database smoke check**

Run:

```powershell
cd ..\..
docker compose up -d
docker exec docintel-postgres psql -U docintel -d docintel -c "SELECT extname FROM pg_extension WHERE extname = 'vector';"
```

Expected: query output contains `vector`.

- [ ] **Step 9: Commit database schema**

Run:

```powershell
git add apps/api/app/db apps/api/app/main.py apps/api/tests/db
git commit -m "feat: add database models and pgvector schema"
```

---

## Task 3: Upload Validation and Local File Storage

**Files:**
- Create: `apps/api/app/documents/__init__.py`
- Create: `apps/api/app/documents/schemas.py`
- Create: `apps/api/app/documents/storage.py`
- Test: `apps/api/tests/documents/test_storage.py`

**Interfaces:**
- Produces: `DocumentKind = Literal["pdf", "image"]`.
- Produces: `UploadValidation` dataclass with `kind: DocumentKind`, `mime_type: str`, `extension: str`, and `size_bytes: int`.
- Produces: `StoredUpload` dataclass with `original_filename: str`, `stored_filename: str`, `mime_type: str`, `file_path: Path`, `kind: DocumentKind`, and `size_bytes: int`.
- Produces: `FileValidationError(ValueError)`.
- Produces: `validate_upload(filename: str, content_type: str | None, size_bytes: int, max_upload_mb: int) -> UploadValidation`.
- Produces: `save_upload_bytes(filename: str, content_type: str | None, content: bytes, storage_dir: Path, max_upload_mb: int) -> StoredUpload`.

- [ ] **Step 1: Write failing storage tests**

Create `apps/api/tests/documents/test_storage.py`:

```python
import pytest

from app.documents.storage import FileValidationError, save_upload_bytes, validate_upload


def test_validate_upload_accepts_pdf():
    result = validate_upload("sample.pdf", "application/pdf", 1024, max_upload_mb=20)

    assert result.kind == "pdf"
    assert result.extension == ".pdf"
    assert result.mime_type == "application/pdf"


def test_validate_upload_rejects_unsupported_extension():
    with pytest.raises(FileValidationError, match="Unsupported file type"):
        validate_upload("notes.txt", "text/plain", 32, max_upload_mb=20)


def test_validate_upload_rejects_large_file():
    with pytest.raises(FileValidationError, match="File is larger than"):
        validate_upload("large.pdf", "application/pdf", 21 * 1024 * 1024, max_upload_mb=20)


def test_save_upload_bytes_writes_unique_file(tmp_path):
    stored = save_upload_bytes(
        filename="form.pdf",
        content_type="application/pdf",
        content=b"%PDF sample",
        storage_dir=tmp_path,
        max_upload_mb=20,
    )

    assert stored.original_filename == "form.pdf"
    assert stored.kind == "pdf"
    assert stored.file_path.exists()
    assert stored.file_path.read_bytes() == b"%PDF sample"
    assert stored.stored_filename.endswith(".pdf")
```

- [ ] **Step 2: Run tests to verify they fail before implementation**

Run:

```powershell
cd apps/api
pytest tests/documents/test_storage.py -v
```

Expected: tests fail because `app.documents.storage` does not exist.

- [ ] **Step 3: Implement storage schemas**

Create `apps/api/app/documents/__init__.py` as an empty package file.

Create `apps/api/app/documents/schemas.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

DocumentKind = Literal["pdf", "image"]


class DocumentRead(BaseModel):
    id: str
    filename: str
    mime_type: str
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class ChunkRead(BaseModel):
    id: str
    document_id: str
    page_number: int
    chunk_index: int
    text: str
    token_estimate: int
```

- [ ] **Step 4: Implement upload validation and storage**

Create `apps/api/app/documents/storage.py`:

```python
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from app.documents.schemas import DocumentKind

ALLOWED_EXTENSIONS: dict[str, tuple[DocumentKind, str]] = {
    ".pdf": ("pdf", "application/pdf"),
    ".png": ("image", "image/png"),
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
}


class FileValidationError(ValueError):
    pass


@dataclass(frozen=True)
class UploadValidation:
    kind: DocumentKind
    mime_type: str
    extension: str
    size_bytes: int


@dataclass(frozen=True)
class StoredUpload:
    original_filename: str
    stored_filename: str
    mime_type: str
    file_path: Path
    kind: DocumentKind
    size_bytes: int


def validate_upload(filename: str, content_type: str | None, size_bytes: int, max_upload_mb: int) -> UploadValidation:
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise FileValidationError("Unsupported file type. Upload a PDF, PNG, JPG, or JPEG document.")

    max_bytes = max_upload_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise FileValidationError(f"File is larger than {max_upload_mb} MB.")

    kind, default_mime = ALLOWED_EXTENSIONS[extension]
    return UploadValidation(
        kind=kind,
        mime_type=content_type or default_mime,
        extension=extension,
        size_bytes=size_bytes,
    )


def save_upload_bytes(
    filename: str,
    content_type: str | None,
    content: bytes,
    storage_dir: Path,
    max_upload_mb: int,
) -> StoredUpload:
    validation = validate_upload(filename, content_type, len(content), max_upload_mb)
    storage_dir.mkdir(parents=True, exist_ok=True)
    stored_filename = f"{uuid4().hex}{validation.extension}"
    file_path = storage_dir / stored_filename
    file_path.write_bytes(content)
    return StoredUpload(
        original_filename=filename,
        stored_filename=stored_filename,
        mime_type=validation.mime_type,
        file_path=file_path,
        kind=validation.kind,
        size_bytes=validation.size_bytes,
    )
```

- [ ] **Step 5: Run storage tests**

Run:

```powershell
cd apps/api
pytest tests/documents/test_storage.py -v
```

Expected: 4 tests pass.

- [ ] **Step 6: Commit storage layer**

Run:

```powershell
cd ..\..
git add apps/api/app/documents apps/api/tests/documents/test_storage.py
git commit -m "feat: add upload validation and local storage"
```

---

## Task 4: PDF Parsing and Text Chunking

**Files:**
- Create: `apps/api/app/documents/parser.py`
- Create: `apps/api/app/documents/chunker.py`
- Test: `apps/api/tests/documents/test_parser.py`
- Test: `apps/api/tests/documents/test_chunker.py`

**Interfaces:**
- Produces: `ParsedPage` dataclass with `page_number: int`, `text: str`, `width: float`, and `height: float`.
- Produces: `TextChunk` dataclass with `page_number: int`, `chunk_index: int`, `text: str`, `token_estimate: int`, and `layout: dict[str, object]`.
- Produces: `DocumentParseError(ValueError)`.
- Produces: `parse_pdf(file_path: Path) -> list[ParsedPage]`.
- Produces: `chunk_pages(pages: Sequence[ParsedPage], chunk_size: int = 900, overlap: int = 120) -> list[TextChunk]`.

- [ ] **Step 1: Write failing parser test**

Create `apps/api/tests/documents/test_parser.py`:

```python
from pathlib import Path

import fitz
import pytest

from app.documents.parser import DocumentParseError, parse_pdf


def create_sample_pdf(path: Path, text: str) -> None:
    document = fitz.open()
    page = document.new_page(width=300, height=200)
    page.insert_text((36, 72), text)
    document.save(path)
    document.close()


def test_parse_pdf_extracts_page_text(tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    create_sample_pdf(pdf_path, "Invoice Number INV-1001")

    pages = parse_pdf(pdf_path)

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert "INV-1001" in pages[0].text
    assert pages[0].width == 300
    assert pages[0].height == 200


def test_parse_pdf_rejects_empty_pdf(tmp_path):
    pdf_path = tmp_path / "empty.pdf"
    document = fitz.open()
    document.new_page()
    document.save(pdf_path)
    document.close()

    with pytest.raises(DocumentParseError, match="No extractable text"):
        parse_pdf(pdf_path)
```

- [ ] **Step 2: Write failing chunker test**

Create `apps/api/tests/documents/test_chunker.py`:

```python
from app.documents.chunker import chunk_pages
from app.documents.parser import ParsedPage


def test_chunk_pages_keeps_page_numbers_and_indexes():
    text = " ".join(f"word{i}" for i in range(260))
    pages = [ParsedPage(page_number=2, text=text, width=600, height=800)]

    chunks = chunk_pages(pages, chunk_size=80, overlap=10)

    assert len(chunks) >= 3
    assert chunks[0].page_number == 2
    assert chunks[0].chunk_index == 0
    assert chunks[1].chunk_index == 1
    assert chunks[0].token_estimate == len(chunks[0].text.split())
    assert chunks[0].layout["source"] == "pymupdf"


def test_chunk_pages_skips_blank_pages():
    pages = [ParsedPage(page_number=1, text="   ", width=100, height=100)]

    assert chunk_pages(pages) == []
```

- [ ] **Step 3: Run tests to verify they fail before implementation**

Run:

```powershell
cd apps/api
pytest tests/documents/test_parser.py tests/documents/test_chunker.py -v
```

Expected: tests fail because parser and chunker modules do not exist.

- [ ] **Step 4: Implement PDF parsing**

Create `apps/api/app/documents/parser.py`:

```python
from dataclasses import dataclass
from pathlib import Path

import fitz


class DocumentParseError(ValueError):
    pass


@dataclass(frozen=True)
class ParsedPage:
    page_number: int
    text: str
    width: float
    height: float


def parse_pdf(file_path: Path) -> list[ParsedPage]:
    pages: list[ParsedPage] = []
    with fitz.open(file_path) as document:
        for index, page in enumerate(document, start=1):
            text = page.get_text("text").strip()
            rect = page.rect
            pages.append(
                ParsedPage(
                    page_number=index,
                    text=text,
                    width=float(rect.width),
                    height=float(rect.height),
                )
            )

    if not any(page.text for page in pages):
        raise DocumentParseError("No extractable text found in this PDF.")

    return pages
```

- [ ] **Step 5: Implement chunking**

Create `apps/api/app/documents/chunker.py`:

```python
from dataclasses import dataclass
from collections.abc import Sequence

from app.documents.parser import ParsedPage


@dataclass(frozen=True)
class TextChunk:
    page_number: int
    chunk_index: int
    text: str
    token_estimate: int
    layout: dict[str, object]


def chunk_pages(pages: Sequence[ParsedPage], chunk_size: int = 900, overlap: int = 120) -> list[TextChunk]:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than zero.")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be greater than or equal to zero and smaller than chunk_size.")

    chunks: list[TextChunk] = []
    chunk_index = 0
    step = chunk_size - overlap

    for page in pages:
        words = page.text.split()
        if not words:
            continue

        for start in range(0, len(words), step):
            window = words[start : start + chunk_size]
            if not window:
                continue
            text = " ".join(window)
            chunks.append(
                TextChunk(
                    page_number=page.page_number,
                    chunk_index=chunk_index,
                    text=text,
                    token_estimate=len(window),
                    layout={
                        "source": "pymupdf",
                        "page_width": page.width,
                        "page_height": page.height,
                        "word_start": start,
                        "word_end": start + len(window),
                    },
                )
            )
            chunk_index += 1

    return chunks
```

- [ ] **Step 6: Run parser and chunker tests**

Run:

```powershell
cd apps/api
pytest tests/documents/test_parser.py tests/documents/test_chunker.py -v
```

Expected: 4 tests pass.

- [ ] **Step 7: Commit parsing and chunking**

Run:

```powershell
cd ..\..
git add apps/api/app/documents/parser.py apps/api/app/documents/chunker.py apps/api/tests/documents
git commit -m "feat: add pdf parsing and text chunking"
```

---

## Task 5: Local Embedding Provider and Search Formatting

**Files:**
- Create: `apps/api/app/retrieval/__init__.py`
- Create: `apps/api/app/retrieval/embeddings.py`
- Create: `apps/api/app/retrieval/search.py`
- Test: `apps/api/tests/retrieval/test_embeddings.py`
- Test: `apps/api/tests/retrieval/test_search_formatting.py`

**Interfaces:**
- Consumes: `Settings.embedding_model_name` and `Settings.embedding_dimension`.
- Produces: `EmbeddingProvider` protocol with `embed_texts(texts: Sequence[str]) -> list[list[float]]`.
- Produces: `LocalEmbeddingProvider(model_name: str, expected_dimension: int)`.
- Produces: `FakeEmbeddingProvider(dimension: int = 384)`.
- Produces: `SearchHit` dataclass with `chunk_id`, `document_id`, `document_filename`, `page_number`, `chunk_index`, `text`, `score`.
- Produces: `build_snippet(text: str, max_chars: int = 260) -> str`.
- Produces: `cosine_distance_to_score(distance: float) -> float`.

- [ ] **Step 1: Write failing embedding tests**

Create `apps/api/tests/retrieval/test_embeddings.py`:

```python
import pytest

from app.retrieval.embeddings import FakeEmbeddingProvider, normalize_embedding_dimension


def test_fake_embedding_provider_returns_stable_dimension():
    provider = FakeEmbeddingProvider(dimension=384)

    vectors = provider.embed_texts(["invoice total", "purchase order"])

    assert len(vectors) == 2
    assert len(vectors[0]) == 384
    assert vectors[0] == provider.embed_texts(["invoice total"])[0]


def test_normalize_embedding_dimension_rejects_wrong_size():
    with pytest.raises(ValueError, match="Expected embedding dimension 384"):
        normalize_embedding_dimension([0.1, 0.2], expected_dimension=384)
```

- [ ] **Step 2: Write failing search formatting tests**

Create `apps/api/tests/retrieval/test_search_formatting.py`:

```python
from app.retrieval.search import build_snippet, cosine_distance_to_score


def test_build_snippet_truncates_long_text():
    text = "A" * 400

    snippet = build_snippet(text, max_chars=50)

    assert len(snippet) == 50
    assert snippet.endswith("...")


def test_cosine_distance_to_score_is_clamped():
    assert cosine_distance_to_score(0.0) == 1.0
    assert cosine_distance_to_score(1.0) == 0.0
    assert cosine_distance_to_score(2.0) == 0.0
```

- [ ] **Step 3: Run tests to verify they fail before implementation**

Run:

```powershell
cd apps/api
pytest tests/retrieval/test_embeddings.py tests/retrieval/test_search_formatting.py -v
```

Expected: tests fail because retrieval modules do not exist.

- [ ] **Step 4: Implement embedding providers**

Create `apps/api/app/retrieval/__init__.py` as an empty package file.

Create `apps/api/app/retrieval/embeddings.py`:

```python
import hashlib
import random
from collections.abc import Sequence
from typing import Protocol


class EmbeddingProvider(Protocol):
    model_name: str
    dimension: int

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        ...


def normalize_embedding_dimension(vector: Sequence[float], expected_dimension: int) -> list[float]:
    if len(vector) != expected_dimension:
        raise ValueError(f"Expected embedding dimension {expected_dimension}, got {len(vector)}.")
    return [float(value) for value in vector]


class LocalEmbeddingProvider:
    def __init__(self, model_name: str, expected_dimension: int) -> None:
        from sentence_transformers import SentenceTransformer

        self.model_name = model_name
        self.dimension = expected_dimension
        self._model = SentenceTransformer(model_name)

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        embeddings = self._model.encode(list(texts), normalize_embeddings=True)
        return [normalize_embedding_dimension(vector.tolist(), self.dimension) for vector in embeddings]


class FakeEmbeddingProvider:
    model_name = "fake-local-embedding"

    def __init__(self, dimension: int = 384) -> None:
        self.dimension = dimension

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
        rng = random.Random(seed)
        return [rng.uniform(-1.0, 1.0) for _ in range(self.dimension)]
```

- [ ] **Step 5: Implement search formatting**

Create `apps/api/app/retrieval/search.py`:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    document_id: str
    document_filename: str
    page_number: int
    chunk_index: int
    text: str
    score: float


def build_snippet(text: str, max_chars: int = 260) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 3].rstrip() + "..."


def cosine_distance_to_score(distance: float) -> float:
    return max(0.0, min(1.0, 1.0 - distance))
```

- [ ] **Step 6: Run embedding and formatting tests**

Run:

```powershell
cd apps/api
pytest tests/retrieval/test_embeddings.py tests/retrieval/test_search_formatting.py -v
```

Expected: 4 tests pass.

- [ ] **Step 7: Commit local embedding abstraction**

Run:

```powershell
cd ..\..
git add apps/api/app/retrieval apps/api/tests/retrieval
git commit -m "feat: add local embedding provider abstraction"
```

---

## Task 6: Document Indexing API

**Files:**
- Create: `apps/api/app/documents/router.py`
- Create: `apps/api/app/documents/service.py`
- Modify: `apps/api/app/main.py`
- Modify: `apps/api/app/documents/schemas.py`
- Test: `apps/api/tests/documents/test_service.py`

**Interfaces:**
- Consumes: `save_upload_bytes`, `parse_pdf`, `chunk_pages`, `EmbeddingProvider`, and database models.
- Produces: `index_stored_upload(db: Session, stored: StoredUpload, embedder: EmbeddingProvider) -> Document`.
- Produces: `list_documents(db: Session) -> list[Document]`.
- Produces: `get_document_or_404(db: Session, document_id: str) -> Document`.
- Produces: `POST /documents`, `GET /documents`, `GET /documents/{document_id}`, and `GET /documents/{document_id}/chunks`.

- [ ] **Step 1: Extend response schemas**

Modify `apps/api/app/documents/schemas.py`:

```python
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

DocumentKind = Literal["pdf", "image"]


class DocumentRead(BaseModel):
    id: str
    filename: str
    mime_type: str
    status: str
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentDetail(DocumentRead):
    page_count: int
    chunk_count: int


class ChunkRead(BaseModel):
    id: str
    document_id: str
    page_number: int
    chunk_index: int
    text: str
    token_estimate: int


class UploadError(BaseModel):
    detail: str
```

- [ ] **Step 2: Write failing service test**

Create `apps/api/tests/documents/test_service.py`:

```python
from pathlib import Path

import fitz
import pytest

from app.db.models import DocumentStatus
from app.documents.storage import save_upload_bytes
from app.documents.service import index_stored_upload
from app.retrieval.embeddings import FakeEmbeddingProvider

pytestmark = pytest.mark.integration


def create_sample_pdf(path: Path, text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path.read_bytes()


def test_index_stored_upload_indexes_pdf(db_session, tmp_path):
    pdf_path = tmp_path / "sample.pdf"
    content = create_sample_pdf(pdf_path, "Payment due date is 2026-09-01")
    stored = save_upload_bytes("sample.pdf", "application/pdf", content, tmp_path / "storage", 20)

    document = index_stored_upload(db_session, stored, FakeEmbeddingProvider())

    assert document.status == DocumentStatus.INDEXED
    assert len(document.pages) == 1
    assert len(document.chunks) >= 1
    assert document.chunks[0].embedding is not None


def test_index_stored_upload_defers_image_ocr(db_session, tmp_path):
    stored = save_upload_bytes("scan.png", "image/png", b"image-bytes", tmp_path / "storage", 20)

    document = index_stored_upload(db_session, stored, FakeEmbeddingProvider())

    assert document.status == DocumentStatus.DEFERRED_OCR
    assert document.error_message == "OCR is not enabled in the local-first MVP."
```

Also create `apps/api/tests/conftest.py` for database integration tests:

```python
import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base


@pytest.fixture()
def db_session():
    database_url = os.environ.get(
        "DOCINTEL_TEST_DATABASE_URL",
        "postgresql+psycopg://docintel:docintel@localhost:5432/docintel",
    )
    engine = create_engine(database_url, pool_pre_ping=True)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = session_factory()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
```

- [ ] **Step 3: Start database and run test to verify it fails before service implementation**

Run:

```powershell
cd ..\..
docker compose up -d
cd apps/api
pytest tests/documents/test_service.py -v
```

Expected: tests fail because `app.documents.service` does not exist.

- [ ] **Step 4: Implement document indexing service**

Create `apps/api/app/documents/service.py`:

```python
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, ChunkEmbedding, Document, DocumentStatus, Page
from app.documents.chunker import chunk_pages
from app.documents.parser import DocumentParseError, parse_pdf
from app.documents.storage import StoredUpload
from app.retrieval.embeddings import EmbeddingProvider


def index_stored_upload(db: Session, stored: StoredUpload, embedder: EmbeddingProvider) -> Document:
    document = Document(
        filename=stored.original_filename,
        stored_filename=stored.stored_filename,
        mime_type=stored.mime_type,
        file_path=str(stored.file_path),
        status=DocumentStatus.PROCESSING,
    )
    db.add(document)
    db.flush()

    if stored.kind == "image":
        document.status = DocumentStatus.DEFERRED_OCR
        document.error_message = "OCR is not enabled in the local-first MVP."
        db.commit()
        db.refresh(document)
        return document

    try:
        parsed_pages = parse_pdf(Path(stored.file_path))
        page_models: dict[int, Page] = {}
        for parsed_page in parsed_pages:
            page = Page(
                document_id=document.id,
                page_number=parsed_page.page_number,
                text=parsed_page.text,
                width=parsed_page.width,
                height=parsed_page.height,
            )
            db.add(page)
            db.flush()
            page_models[parsed_page.page_number] = page

        text_chunks = chunk_pages(parsed_pages)
        vectors = embedder.embed_texts([chunk.text for chunk in text_chunks])
        for text_chunk, vector in zip(text_chunks, vectors, strict=True):
            chunk = Chunk(
                document_id=document.id,
                page_id=page_models[text_chunk.page_number].id,
                chunk_index=text_chunk.chunk_index,
                text=text_chunk.text,
                token_estimate=text_chunk.token_estimate,
                layout=text_chunk.layout,
            )
            db.add(chunk)
            db.flush()
            db.add(ChunkEmbedding(chunk_id=chunk.id, model_name=embedder.model_name, embedding=vector))

        document.status = DocumentStatus.INDEXED
        db.commit()
        db.refresh(document)
        return document
    except DocumentParseError as exc:
        document.status = DocumentStatus.FAILED
        document.error_message = str(exc)
        db.commit()
        db.refresh(document)
        return document


def list_documents(db: Session) -> list[Document]:
    return list(db.scalars(select(Document).order_by(Document.created_at.desc())))


def get_document_or_404(db: Session, document_id: str) -> Document:
    document = db.get(Document, document_id)
    if document is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Document not found.")
    return document
```

- [ ] **Step 5: Implement document router**

Create `apps/api/app/documents/router.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.models import Chunk
from app.db.session import get_db
from app.documents.schemas import ChunkRead, DocumentDetail, DocumentRead
from app.documents.service import get_document_or_404, index_stored_upload, list_documents
from app.documents.storage import FileValidationError, save_upload_bytes
from app.retrieval.embeddings import LocalEmbeddingProvider

router = APIRouter(prefix="/documents", tags=["documents"])


def get_embedding_provider(settings: Annotated[Settings, Depends(get_settings)]) -> LocalEmbeddingProvider:
    return LocalEmbeddingProvider(settings.embedding_model_name, settings.embedding_dimension)


@router.post("", response_model=DocumentRead)
async def upload_document(
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
    embedder: Annotated[LocalEmbeddingProvider, Depends(get_embedding_provider)],
) -> DocumentRead:
    content = await file.read()
    try:
        stored = save_upload_bytes(file.filename or "document", file.content_type, content, settings.storage_dir, settings.max_upload_mb)
    except FileValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return index_stored_upload(db, stored, embedder)


@router.get("", response_model=list[DocumentRead])
def documents(db: Annotated[Session, Depends(get_db)]) -> list[DocumentRead]:
    return list_documents(db)


@router.get("/{document_id}", response_model=DocumentDetail)
def document_detail(document_id: str, db: Annotated[Session, Depends(get_db)]) -> DocumentDetail:
    document = get_document_or_404(db, document_id)
    return DocumentDetail(
        id=document.id,
        filename=document.filename,
        mime_type=document.mime_type,
        status=document.status.value,
        error_message=document.error_message,
        created_at=document.created_at,
        updated_at=document.updated_at,
        page_count=len(document.pages),
        chunk_count=len(document.chunks),
    )


@router.get("/{document_id}/chunks", response_model=list[ChunkRead])
def document_chunks(document_id: str, db: Annotated[Session, Depends(get_db)]) -> list[ChunkRead]:
    document = get_document_or_404(db, document_id)
    chunks = sorted(document.chunks, key=lambda item: item.chunk_index)
    return [
        ChunkRead(
            id=chunk.id,
            document_id=chunk.document_id,
            page_number=chunk.page.page_number,
            chunk_index=chunk.chunk_index,
            text=chunk.text,
            token_estimate=chunk.token_estimate,
        )
        for chunk in chunks
        if isinstance(chunk, Chunk)
    ]
```

- [ ] **Step 6: Include document router in FastAPI app**

Modify `apps/api/app/main.py`:

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.init_db import init_db
from app.documents.router import router as documents_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    app.include_router(documents_router)
    return app


app = create_app()
```

- [ ] **Step 7: Run document service tests**

Run:

```powershell
cd apps/api
pytest tests/documents/test_service.py -v
```

Expected: 2 tests pass.

- [ ] **Step 8: Commit document indexing API**

Run:

```powershell
cd ..\..
git add apps/api/app/documents apps/api/app/main.py apps/api/tests/conftest.py apps/api/tests/documents/test_service.py
git commit -m "feat: add document indexing API"
```

---

## Task 7: Semantic Search API

**Files:**
- Create: `apps/api/app/retrieval/router.py`
- Modify: `apps/api/app/retrieval/search.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/retrieval/test_search_api.py`

**Interfaces:**
- Consumes: `EmbeddingProvider`, `ChunkEmbedding`, `Chunk`, `Page`, and `Document`.
- Produces: `SearchRequest(BaseModel)` with `query: str`, `top_k: int = 5`, and `document_id: str | None = None`.
- Produces: `SearchResponse(BaseModel)` with `query: str` and `hits: list[SearchHitRead]`.
- Produces: `search_chunks(db: Session, query_embedding: list[float], top_k: int, document_id: str | None = None) -> list[SearchHit]`.
- Produces: `POST /search`.

- [ ] **Step 1: Write failing search API test**

Create `apps/api/tests/retrieval/test_search_api.py`:

```python
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.documents.router import get_embedding_provider
from app.documents.storage import save_upload_bytes
from app.documents.service import index_stored_upload
from app.main import create_app
from app.retrieval.embeddings import FakeEmbeddingProvider

pytestmark = pytest.mark.integration


def create_sample_pdf(path: Path, text: str) -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    document.save(path)
    document.close()
    return path.read_bytes()


def test_search_endpoint_returns_cited_hits(db_session, tmp_path):
    content = create_sample_pdf(tmp_path / "sample.pdf", "The invoice total is 1250 Malaysian Ringgit.")
    stored = save_upload_bytes("invoice.pdf", "application/pdf", content, tmp_path / "storage", 20)
    index_stored_upload(db_session, stored, FakeEmbeddingProvider())

    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    response = client.post("/search", json={"query": "invoice total", "top_k": 3})

    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "invoice total"
    assert len(body["hits"]) >= 1
    assert body["hits"][0]["document_filename"] == "invoice.pdf"
    assert body["hits"][0]["page_number"] == 1
    assert "invoice" in body["hits"][0]["snippet"].lower()
```

- [ ] **Step 2: Run test to verify it fails before implementation**

Run:

```powershell
cd apps/api
pytest tests/retrieval/test_search_api.py -v
```

Expected: test fails because `/search` is not implemented.

- [ ] **Step 3: Implement vector search function and schemas**

Modify `apps/api/app/retrieval/search.py`:

```python
from dataclasses import dataclass

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Chunk, ChunkEmbedding, Document, Page


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    document_id: str
    document_filename: str
    page_number: int
    chunk_index: int
    text: str
    score: float


class SearchRequest(BaseModel):
    query: str = Field(min_length=1)
    top_k: int = Field(default=5, ge=1, le=20)
    document_id: str | None = None


class SearchHitRead(BaseModel):
    chunk_id: str
    document_id: str
    document_filename: str
    page_number: int
    chunk_index: int
    score: float
    snippet: str


class SearchResponse(BaseModel):
    query: str
    hits: list[SearchHitRead]


def build_snippet(text: str, max_chars: int = 260) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= max_chars:
        return collapsed
    return collapsed[: max_chars - 3].rstrip() + "..."


def cosine_distance_to_score(distance: float) -> float:
    return max(0.0, min(1.0, 1.0 - distance))


def search_chunks(db: Session, query_embedding: list[float], top_k: int, document_id: str | None = None) -> list[SearchHit]:
    distance = ChunkEmbedding.embedding.cosine_distance(query_embedding).label("distance")
    statement = (
        select(Chunk, Page, Document, distance)
        .join(ChunkEmbedding, ChunkEmbedding.chunk_id == Chunk.id)
        .join(Page, Page.id == Chunk.page_id)
        .join(Document, Document.id == Chunk.document_id)
        .order_by(distance)
        .limit(top_k)
    )
    if document_id is not None:
        statement = statement.where(Document.id == document_id)

    hits: list[SearchHit] = []
    for chunk, page, document, raw_distance in db.execute(statement):
        hits.append(
            SearchHit(
                chunk_id=chunk.id,
                document_id=document.id,
                document_filename=document.filename,
                page_number=page.page_number,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                score=cosine_distance_to_score(float(raw_distance)),
            )
        )
    return hits
```

- [ ] **Step 4: Implement search router**

Create `apps/api/app/retrieval/router.py`:

```python
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.documents.router import get_embedding_provider
from app.retrieval.embeddings import EmbeddingProvider
from app.retrieval.search import SearchHitRead, SearchRequest, SearchResponse, build_snippet, search_chunks

router = APIRouter(tags=["search"])


@router.post("/search", response_model=SearchResponse)
def search(
    request: SearchRequest,
    db: Annotated[Session, Depends(get_db)],
    embedder: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
) -> SearchResponse:
    query_embedding = embedder.embed_texts([request.query])[0]
    hits = search_chunks(db, query_embedding, request.top_k, request.document_id)
    return SearchResponse(
        query=request.query,
        hits=[
            SearchHitRead(
                chunk_id=hit.chunk_id,
                document_id=hit.document_id,
                document_filename=hit.document_filename,
                page_number=hit.page_number,
                chunk_index=hit.chunk_index,
                score=hit.score,
                snippet=build_snippet(hit.text),
            )
            for hit in hits
        ],
    )
```

- [ ] **Step 5: Include search router in FastAPI app**

Modify `apps/api/app/main.py`:

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.init_db import init_db
from app.documents.router import router as documents_router
from app.retrieval.router import router as retrieval_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    app.include_router(documents_router)
    app.include_router(retrieval_router)
    return app


app = create_app()
```

- [ ] **Step 6: Run search tests**

Run:

```powershell
cd apps/api
pytest tests/retrieval/test_search_api.py tests/retrieval/test_search_formatting.py -v
```

Expected: search API and formatting tests pass.

- [ ] **Step 7: Commit semantic search API**

Run:

```powershell
cd ..\..
git add apps/api/app/retrieval apps/api/app/main.py apps/api/tests/retrieval
git commit -m "feat: add semantic search API"
```

---

## Task 8: Frontend Foundation and Typed API Client

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/next.config.ts`
- Create: `apps/web/postcss.config.mjs`
- Create: `apps/web/tailwind.config.ts`
- Create: `apps/web/vitest.config.ts`
- Create: `apps/web/app/globals.css`
- Create: `apps/web/app/layout.tsx`
- Create: `apps/web/app/page.tsx`
- Create: `apps/web/components/app-shell.tsx`
- Create: `apps/web/components/status-badge.tsx`
- Create: `apps/web/lib/types.ts`
- Create: `apps/web/lib/api.ts`
- Test setup: `apps/web/tests/setup.ts`
- Test: `apps/web/tests/api-client.test.ts`
- Test: `apps/web/tests/status-badge.test.tsx`

**Interfaces:**
- Consumes backend REST endpoints: `/health`, `/documents`, and `/search`.
- Produces frontend types: `DocumentSummary`, `SearchHit`, `SearchResponse`, `EvalRunSummary`.
- Produces API functions: `getDocuments()`, `uploadDocument(file: File)`, `searchDocuments(query: string, topK?: number, documentId?: string)`.
- Produces `StatusBadge({ status }: { status: string })`.

**Nigel prerequisite:** Install Node.js LTS before this task if `node --version` and `npm --version` are not available in a new PowerShell window.

- [ ] **Step 1: Create frontend package and config files**

Create `apps/web/package.json`:

```json
{
  "name": "docintel-web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "lint": "next lint",
    "test": "vitest run"
  },
  "dependencies": {
    "@vitejs/plugin-react": "^4.3.4",
    "lucide-react": "^0.468.0",
    "next": "^15.1.2",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.6.3",
    "@testing-library/react": "^16.1.0",
    "@types/node": "^22.10.2",
    "@types/react": "^19.0.2",
    "@types/react-dom": "^19.0.2",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.17.0",
    "eslint-config-next": "^15.1.2",
    "jsdom": "^25.0.1",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.17",
    "typescript": "^5.7.2",
    "vitest": "^2.1.8"
  }
}
```

Create `apps/web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "baseUrl": ".",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

Create `apps/web/next.config.ts`:

```typescript
import type { NextConfig } from "next";

const nextConfig: NextConfig = {};

export default nextConfig;
```

Create `apps/web/postcss.config.mjs`:

```javascript
const config = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};

export default config;
```

Create `apps/web/tailwind.config.ts`:

```typescript
import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#172026",
        panel: "#f7f8fa",
        line: "#d8dde3",
        accent: "#256f7a",
      },
    },
  },
  plugins: [],
};

export default config;
```

Create `apps/web/vitest.config.ts`:

```typescript
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
  },
});
```

- [ ] **Step 2: Install frontend dependencies**

Run:

```powershell
cd apps/web
npm install
```

Expected: `node_modules` and `package-lock.json` are created.

- [ ] **Step 3: Write failing API client and component tests**

Create `apps/web/tests/api-client.test.ts`:

```typescript
import { describe, expect, it, vi } from "vitest";

import { getDocuments, searchDocuments } from "@/lib/api";

describe("api client", () => {
  it("fetches documents from the configured backend", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [{ id: "doc-1", filename: "sample.pdf", mime_type: "application/pdf", status: "indexed" }],
    });
    vi.stubGlobal("fetch", fetchMock);

    const documents = await getDocuments();

    expect(fetchMock).toHaveBeenCalledWith("http://localhost:8000/documents", { cache: "no-store" });
    expect(documents[0].filename).toBe("sample.pdf");
  });

  it("posts search requests", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ query: "invoice", hits: [] }),
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await searchDocuments("invoice", 5);

    expect(fetchMock).toHaveBeenCalledWith(
      "http://localhost:8000/search",
      expect.objectContaining({ method: "POST" }),
    );
    expect(result.query).toBe("invoice");
  });
});
```

Create `apps/web/tests/status-badge.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatusBadge } from "@/components/status-badge";

describe("StatusBadge", () => {
  it("renders indexed status text", () => {
    render(<StatusBadge status="indexed" />);

    expect(screen.getByText("Indexed")).toBeInTheDocument();
  });

  it("renders deferred OCR status text", () => {
    render(<StatusBadge status="deferred_ocr" />);

    expect(screen.getByText("OCR deferred")).toBeInTheDocument();
  });
});
```

Create `apps/web/tests/setup.ts`:

```typescript
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 4: Run tests to verify they fail before implementation**

Run:

```powershell
cd apps/web
npm test
```

Expected: tests fail because `@/lib/api` and `@/components/status-badge` do not exist.

- [ ] **Step 5: Implement frontend types and API client**

Create `apps/web/lib/types.ts`:

```typescript
export type DocumentSummary = {
  id: string;
  filename: string;
  mime_type: string;
  status: string;
  error_message?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type SearchHit = {
  chunk_id: string;
  document_id: string;
  document_filename: string;
  page_number: number;
  chunk_index: number;
  score: number;
  snippet: string;
};

export type SearchResponse = {
  query: string;
  hits: SearchHit[];
};

export type EvalRunSummary = {
  id: string;
  name: string;
  model_name: string;
  metrics: Record<string, number>;
  created_at: string;
};
```

Create `apps/web/lib/api.ts`:

```typescript
import type { DocumentSummary, SearchResponse } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

async function parseJsonResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function getDocuments(): Promise<DocumentSummary[]> {
  const response = await fetch(`${API_BASE_URL}/documents`, { cache: "no-store" });
  return parseJsonResponse<DocumentSummary[]>(response);
}

export async function uploadDocument(file: File): Promise<DocumentSummary> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await fetch(`${API_BASE_URL}/documents`, {
    method: "POST",
    body: formData,
  });
  return parseJsonResponse<DocumentSummary>(response);
}

export async function searchDocuments(query: string, topK = 5, documentId?: string): Promise<SearchResponse> {
  const response = await fetch(`${API_BASE_URL}/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, top_k: topK, document_id: documentId }),
  });
  return parseJsonResponse<SearchResponse>(response);
}
```

- [ ] **Step 6: Implement app shell and status badge**

Create `apps/web/components/status-badge.tsx`:

```typescript
const LABELS: Record<string, string> = {
  uploaded: "Uploaded",
  processing: "Processing",
  indexed: "Indexed",
  deferred_ocr: "OCR deferred",
  failed: "Failed",
};

export function StatusBadge({ status }: { status: string }) {
  const label = LABELS[status] ?? status;
  return (
    <span className="inline-flex min-w-24 items-center justify-center rounded border border-line bg-white px-2 py-1 text-xs font-medium text-ink">
      {label}
    </span>
  );
}
```

Create `apps/web/components/app-shell.tsx`:

```typescript
import Link from "next/link";
import type { ReactNode } from "react";
import { Database, FileSearch, Gauge, UploadCloud } from "lucide-react";

const navItems = [
  { href: "/", label: "Dashboard", icon: Database },
  { href: "/documents", label: "Documents", icon: UploadCloud },
  { href: "/search", label: "Search", icon: FileSearch },
  { href: "/evaluation", label: "Evaluation", icon: Gauge },
];

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-panel text-ink">
      <aside className="fixed inset-y-0 left-0 hidden w-64 border-r border-line bg-white p-4 md:block">
        <div className="mb-8">
          <p className="text-sm font-semibold">DocIntel AI</p>
          <p className="mt-1 text-xs text-slate-500">Local document intelligence</p>
        </div>
        <nav className="space-y-1">
          {navItems.map((item) => (
            <Link key={item.href} href={item.href} className="flex items-center gap-2 rounded px-3 py-2 text-sm hover:bg-panel">
              <item.icon className="h-4 w-4" aria-hidden="true" />
              {item.label}
            </Link>
          ))}
        </nav>
      </aside>
      <main className="min-h-screen md:pl-64">
        <div className="mx-auto max-w-6xl p-4 md:p-8">{children}</div>
      </main>
    </div>
  );
}
```

- [ ] **Step 7: Implement global layout and dashboard page**

Create `apps/web/app/globals.css`:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
}
```

Create `apps/web/app/layout.tsx`:

```typescript
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "DocIntel AI",
  description: "Local-first document intelligence",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
```

Create `apps/web/app/page.tsx`:

```typescript
import { AppShell } from "@/components/app-shell";

export default function DashboardPage() {
  return (
    <AppShell>
      <section className="mb-6">
        <h1 className="text-2xl font-semibold">Dashboard</h1>
        <p className="mt-2 text-sm text-slate-600">Upload PDFs, index local embeddings, and search with cited evidence.</p>
      </section>
      <div className="grid gap-4 md:grid-cols-3">
        {["Documents", "Indexed chunks", "Evaluation runs"].map((label) => (
          <div key={label} className="rounded border border-line bg-white p-4">
            <p className="text-sm text-slate-500">{label}</p>
            <p className="mt-3 text-3xl font-semibold">0</p>
          </div>
        ))}
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 8: Run frontend tests**

Run:

```powershell
cd apps/web
npm test
```

Expected: frontend API client and status badge tests pass.

- [ ] **Step 9: Commit frontend foundation**

Run:

```powershell
cd ..\..
git add apps/web
git commit -m "feat: add frontend foundation and api client"
```

---

## Task 9: Frontend Upload, Document List, and Search UI

**Files:**
- Create: `apps/web/components/upload-panel.tsx`
- Create: `apps/web/components/document-list.tsx`
- Create: `apps/web/components/search-results.tsx`
- Create: `apps/web/app/documents/page.tsx`
- Create: `apps/web/app/search/page.tsx`
- Test: `apps/web/tests/search-results.test.tsx`

**Interfaces:**
- Consumes: `DocumentSummary`, `SearchHit`, `getDocuments`, `uploadDocument`, and `searchDocuments`.
- Produces: `UploadPanel({ onUploaded }: { onUploaded?: (document: DocumentSummary) => void })`.
- Produces: `DocumentList({ documents }: { documents: DocumentSummary[] })`.
- Produces: `SearchResults({ hits }: { hits: SearchHit[] })`.
- Produces route `/documents`.
- Produces route `/search`.

- [ ] **Step 1: Write failing search result component test**

Create `apps/web/tests/search-results.test.tsx`:

```typescript
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SearchResults } from "@/components/search-results";

describe("SearchResults", () => {
  it("renders cited evidence", () => {
    render(
      <SearchResults
        hits={[
          {
            chunk_id: "chunk-1",
            document_id: "doc-1",
            document_filename: "invoice.pdf",
            page_number: 2,
            chunk_index: 0,
            score: 0.87,
            snippet: "Invoice total is 1250 Malaysian Ringgit.",
          },
        ]}
      />,
    );

    expect(screen.getByText("invoice.pdf")).toBeInTheDocument();
    expect(screen.getByText("Page 2")).toBeInTheDocument();
    expect(screen.getByText("87%")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run test to verify it fails before implementation**

Run:

```powershell
cd apps/web
npm test -- search-results.test.tsx
```

Expected: test fails because `SearchResults` does not exist.

- [ ] **Step 3: Implement search results component**

Create `apps/web/components/search-results.tsx`:

```typescript
import type { SearchHit } from "@/lib/types";

export function SearchResults({ hits }: { hits: SearchHit[] }) {
  if (hits.length === 0) {
    return <p className="rounded border border-line bg-white p-4 text-sm text-slate-600">No cited evidence found.</p>;
  }

  return (
    <div className="space-y-3">
      {hits.map((hit) => (
        <article key={hit.chunk_id} className="rounded border border-line bg-white p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold">{hit.document_filename}</h2>
              <p className="mt-1 text-xs text-slate-500">Page {hit.page_number}</p>
            </div>
            <span className="rounded border border-line px-2 py-1 text-xs font-medium">{Math.round(hit.score * 100)}%</span>
          </div>
          <p className="mt-3 text-sm leading-6 text-slate-700">{hit.snippet}</p>
        </article>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Implement upload panel and document list**

Create `apps/web/components/upload-panel.tsx`:

```typescript
"use client";

import { useState } from "react";
import { UploadCloud } from "lucide-react";

import { uploadDocument } from "@/lib/api";
import type { DocumentSummary } from "@/lib/types";

export function UploadPanel({ onUploaded }: { onUploaded?: (document: DocumentSummary) => void }) {
  const [message, setMessage] = useState<string>("PDF uploads are indexed; image uploads are stored for deferred OCR.");
  const [isUploading, setIsUploading] = useState(false);

  async function handleFileChange(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    setIsUploading(true);
    setMessage("Uploading and indexing document...");
    try {
      const document = await uploadDocument(file);
      setMessage(`${document.filename} is ${document.status.replace("_", " ")}.`);
      onUploaded?.(document);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Upload failed.");
    } finally {
      setIsUploading(false);
      event.target.value = "";
    }
  }

  return (
    <label className="block rounded border border-dashed border-accent bg-white p-6">
      <div className="flex items-center gap-3">
        <UploadCloud className="h-5 w-5 text-accent" aria-hidden="true" />
        <div>
          <p className="text-sm font-semibold">Upload document</p>
          <p className="mt-1 text-xs text-slate-500">{message}</p>
        </div>
      </div>
      <input className="mt-4 block w-full text-sm" type="file" accept=".pdf,.png,.jpg,.jpeg" onChange={handleFileChange} disabled={isUploading} />
    </label>
  );
}
```

Create `apps/web/components/document-list.tsx`:

```typescript
import { StatusBadge } from "@/components/status-badge";
import type { DocumentSummary } from "@/lib/types";

export function DocumentList({ documents }: { documents: DocumentSummary[] }) {
  if (documents.length === 0) {
    return <p className="rounded border border-line bg-white p-4 text-sm text-slate-600">No documents uploaded.</p>;
  }

  return (
    <div className="overflow-hidden rounded border border-line bg-white">
      <table className="w-full table-fixed text-left text-sm">
        <thead className="border-b border-line bg-panel text-xs uppercase text-slate-500">
          <tr>
            <th className="px-4 py-3">Filename</th>
            <th className="w-36 px-4 py-3">Status</th>
            <th className="w-44 px-4 py-3">Type</th>
          </tr>
        </thead>
        <tbody>
          {documents.map((document) => (
            <tr key={document.id} className="border-b border-line last:border-b-0">
              <td className="truncate px-4 py-3">{document.filename}</td>
              <td className="px-4 py-3"><StatusBadge status={document.status} /></td>
              <td className="truncate px-4 py-3 text-slate-600">{document.mime_type}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 5: Implement documents route**

Create `apps/web/app/documents/page.tsx`:

```typescript
"use client";

import { useEffect, useState } from "react";

import { AppShell } from "@/components/app-shell";
import { DocumentList } from "@/components/document-list";
import { UploadPanel } from "@/components/upload-panel";
import { getDocuments } from "@/lib/api";
import type { DocumentSummary } from "@/lib/types";

export default function DocumentsPage() {
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [message, setMessage] = useState("Loading documents...");

  async function refreshDocuments() {
    try {
      const result = await getDocuments();
      setDocuments(result);
      setMessage("");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Could not load documents.");
    }
  }

  useEffect(() => {
    void refreshDocuments();
  }, []);

  return (
    <AppShell>
      <section className="mb-6">
        <h1 className="text-2xl font-semibold">Documents</h1>
        <p className="mt-2 text-sm text-slate-600">Upload local documents and review indexing status.</p>
      </section>
      <div className="space-y-4">
        <UploadPanel onUploaded={() => void refreshDocuments()} />
        {message ? <p className="text-sm text-slate-600">{message}</p> : <DocumentList documents={documents} />}
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 6: Implement search route**

Create `apps/web/app/search/page.tsx`:

```typescript
"use client";

import { FormEvent, useState } from "react";
import { Search } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { SearchResults } from "@/components/search-results";
import { searchDocuments } from "@/lib/api";
import type { SearchHit } from "@/lib/types";

export default function SearchPage() {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<SearchHit[]>([]);
  const [message, setMessage] = useState("Enter a question or search phrase.");
  const [isSearching, setIsSearching] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) {
      setMessage("Enter a question or search phrase.");
      return;
    }
    setIsSearching(true);
    setMessage("Searching local vector index...");
    try {
      const response = await searchDocuments(query.trim(), 5);
      setHits(response.hits);
      setMessage(response.hits.length === 0 ? "No cited evidence found." : "");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Search failed.");
    } finally {
      setIsSearching(false);
    }
  }

  return (
    <AppShell>
      <section className="mb-6">
        <h1 className="text-2xl font-semibold">Search</h1>
        <p className="mt-2 text-sm text-slate-600">Retrieve cited evidence from local document embeddings.</p>
      </section>
      <form className="mb-4 flex gap-2" onSubmit={handleSubmit}>
        <input
          className="min-w-0 flex-1 rounded border border-line bg-white px-3 py-2 text-sm outline-none focus:border-accent"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          aria-label="Search query"
        />
        <button className="inline-flex items-center gap-2 rounded bg-accent px-4 py-2 text-sm font-medium text-white disabled:opacity-60" disabled={isSearching}>
          <Search className="h-4 w-4" aria-hidden="true" />
          Search
        </button>
      </form>
      {message ? <p className="mb-4 text-sm text-slate-600">{message}</p> : null}
      <SearchResults hits={hits} />
    </AppShell>
  );
}
```

- [ ] **Step 7: Run frontend tests**

Run:

```powershell
cd apps/web
npm test
```

Expected: all frontend tests pass.

- [ ] **Step 8: Commit document and search UI**

Run:

```powershell
cd ..\..
git add apps/web
git commit -m "feat: add document upload and search UI"
```

---

## Task 10: FUNSD Download Script and Retrieval Evaluation

**Files:**
- Create: `apps/api/scripts/download_funsd.py`
- Create: `apps/api/scripts/ingest_funsd.py`
- Create: `apps/api/app/evaluation/__init__.py`
- Create: `apps/api/app/evaluation/metrics.py`
- Create: `apps/api/app/evaluation/router.py`
- Modify: `apps/api/app/main.py`
- Create: `apps/web/components/evaluation-summary.tsx`
- Create: `apps/web/app/evaluation/page.tsx`
- Test: `apps/api/tests/evaluation/test_metrics.py`

**Interfaces:**
- Produces: `download_funsd(target_dir: Path) -> Path`.
- Produces: `hit_rate_at_k(expected_chunk_ids: list[str], ranked_chunk_ids: list[str], k: int) -> float`.
- Produces: `mean_reciprocal_rank(expected_chunk_ids: list[str], ranked_chunk_ids: list[str]) -> float`.
- Produces: `EvalRunRead(BaseModel)` with `id`, `name`, `model_name`, `metrics`, and `created_at`.
- Produces: `POST /eval/runs` and `GET /eval/runs`.

- [ ] **Step 1: Write failing metric tests**

Create `apps/api/tests/evaluation/test_metrics.py`:

```python
from app.evaluation.metrics import hit_rate_at_k, mean_reciprocal_rank


def test_hit_rate_at_k_returns_one_when_expected_id_is_in_top_k():
    assert hit_rate_at_k(["chunk-3"], ["chunk-1", "chunk-3", "chunk-5"], k=2) == 1.0


def test_hit_rate_at_k_returns_zero_when_expected_id_is_outside_top_k():
    assert hit_rate_at_k(["chunk-9"], ["chunk-1", "chunk-3", "chunk-5"], k=3) == 0.0


def test_mean_reciprocal_rank_returns_first_matching_rank_inverse():
    assert mean_reciprocal_rank(["chunk-5"], ["chunk-1", "chunk-3", "chunk-5"]) == 1 / 3
```

- [ ] **Step 2: Run tests to verify they fail before implementation**

Run:

```powershell
cd apps/api
pytest tests/evaluation/test_metrics.py -v
```

Expected: tests fail because evaluation metrics do not exist.

- [ ] **Step 3: Implement deterministic retrieval metrics**

Create `apps/api/app/evaluation/__init__.py` as an empty package file.

Create `apps/api/app/evaluation/metrics.py`:

```python
def hit_rate_at_k(expected_chunk_ids: list[str], ranked_chunk_ids: list[str], k: int) -> float:
    if k <= 0:
        raise ValueError("k must be greater than zero.")
    expected = set(expected_chunk_ids)
    retrieved = set(ranked_chunk_ids[:k])
    return 1.0 if expected.intersection(retrieved) else 0.0


def mean_reciprocal_rank(expected_chunk_ids: list[str], ranked_chunk_ids: list[str]) -> float:
    expected = set(expected_chunk_ids)
    for index, chunk_id in enumerate(ranked_chunk_ids, start=1):
        if chunk_id in expected:
            return 1.0 / index
    return 0.0
```

- [ ] **Step 4: Implement FUNSD downloader**

Create `apps/api/scripts/download_funsd.py`:

```python
from pathlib import Path
import subprocess


def download_funsd(target_dir: Path) -> Path:
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if target_dir.exists():
        return target_dir
    subprocess.run(
        ["git", "clone", "--depth", "1", "https://github.com/crcresearch/FUNSD.git", str(target_dir)],
        check=True,
    )
    return target_dir


if __name__ == "__main__":
    location = download_funsd(Path("data/raw/funsd"))
    print(f"FUNSD repository is available at {location}")
```

Create `apps/api/scripts/ingest_funsd.py`:

```python
from pathlib import Path


def list_funsd_images(dataset_dir: Path) -> list[Path]:
    image_dir = dataset_dir / "data" / "images"
    if not image_dir.exists():
        return []
    return sorted(image_dir.glob("*.png")) + sorted(image_dir.glob("*.jpg"))


if __name__ == "__main__":
    images = list_funsd_images(Path("data/raw/funsd"))
    print(f"Found {len(images)} FUNSD image files.")
```

- [ ] **Step 5: Implement evaluation router**

Create `apps/api/app/evaluation/router.py`:

```python
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import EvalRun
from app.db.session import get_db

router = APIRouter(prefix="/eval", tags=["evaluation"])


class EvalRunRead(BaseModel):
    id: str
    name: str
    model_name: str
    metrics: dict[str, float]
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/runs", response_model=EvalRunRead)
def create_eval_run(db: Annotated[Session, Depends(get_db)]) -> EvalRun:
    settings = get_settings()
    eval_run = EvalRun(
        name="sample-retrieval-eval",
        model_name=settings.embedding_model_name,
        metrics={"hit_rate_at_5": 0.0, "mean_reciprocal_rank": 0.0},
    )
    db.add(eval_run)
    db.commit()
    db.refresh(eval_run)
    return eval_run


@router.get("/runs", response_model=list[EvalRunRead])
def list_eval_runs(db: Annotated[Session, Depends(get_db)]) -> list[EvalRun]:
    return list(db.scalars(select(EvalRun).order_by(EvalRun.created_at.desc())))
```

- [ ] **Step 6: Include evaluation router in FastAPI app**

Modify `apps/api/app/main.py`:

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.db.init_db import init_db
from app.documents.router import router as documents_router
from app.evaluation.router import router as evaluation_router
from app.retrieval.router import router as retrieval_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.backend_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    app.include_router(documents_router)
    app.include_router(retrieval_router)
    app.include_router(evaluation_router)
    return app


app = create_app()
```

- [ ] **Step 7: Add frontend evaluation page**

Create `apps/web/components/evaluation-summary.tsx`:

```typescript
import type { EvalRunSummary } from "@/lib/types";

export function EvaluationSummary({ runs }: { runs: EvalRunSummary[] }) {
  if (runs.length === 0) {
    return <p className="rounded border border-line bg-white p-4 text-sm text-slate-600">No evaluation runs recorded.</p>;
  }

  return (
    <div className="space-y-3">
      {runs.map((run) => (
        <article key={run.id} className="rounded border border-line bg-white p-4">
          <h2 className="text-sm font-semibold">{run.name}</h2>
          <p className="mt-1 text-xs text-slate-500">{run.model_name}</p>
          <dl className="mt-3 grid gap-3 sm:grid-cols-2">
            {Object.entries(run.metrics).map(([key, value]) => (
              <div key={key}>
                <dt className="text-xs uppercase text-slate-500">{key.replaceAll("_", " ")}</dt>
                <dd className="mt-1 text-xl font-semibold">{value.toFixed(2)}</dd>
              </div>
            ))}
          </dl>
        </article>
      ))}
    </div>
  );
}
```

Create `apps/web/app/evaluation/page.tsx`:

```typescript
import { AppShell } from "@/components/app-shell";
import { EvaluationSummary } from "@/components/evaluation-summary";

export default function EvaluationPage() {
  return (
    <AppShell>
      <section className="mb-6">
        <h1 className="text-2xl font-semibold">Evaluation</h1>
        <p className="mt-2 text-sm text-slate-600">Track local retrieval metrics for repeatable project demos.</p>
      </section>
      <EvaluationSummary runs={[]} />
    </AppShell>
  );
}
```

- [ ] **Step 8: Run evaluation tests**

Run:

```powershell
cd apps/api
pytest tests/evaluation/test_metrics.py -v
```

Expected: 3 tests pass.

- [ ] **Step 9: Download FUNSD locally**

Run from the repo root:

```powershell
python apps/api/scripts/download_funsd.py
```

Expected: `data/raw/funsd` exists and remains ignored by Git.

- [ ] **Step 10: Commit evaluation and dataset utilities**

Run:

```powershell
git add apps/api/app/evaluation apps/api/app/main.py apps/api/scripts apps/api/tests/evaluation apps/web/app/evaluation apps/web/components/evaluation-summary.tsx
git commit -m "feat: add retrieval evaluation and FUNSD utilities"
```

---

## Task 11: Local Run Documentation, CI, and Portfolio Polish

**Files:**
- Modify: `README.md`
- Create: `docs/architecture/local-development.md`
- Create: `docs/architecture/system-overview.md`
- Create: `docs/architecture/system-overview.mmd`
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: all implemented backend, frontend, Docker, and script commands.
- Produces: recruiter-readable README with setup, architecture, local-only AI explanation, demo flow, and limitations.
- Produces: CI workflow that runs backend unit tests and frontend checks.

- [ ] **Step 1: Write architecture diagram**

Create `docs/architecture/system-overview.mmd`:

```mermaid
flowchart LR
  Browser[Browser] --> Web[Next.js web app]
  Web --> API[FastAPI backend]
  API --> Storage[Local file storage]
  API --> Parser[PyMuPDF PDF parser]
  Parser --> Chunks[Text chunks]
  Chunks --> Embedder[Local BGE embeddings]
  Embedder --> DB[(PostgreSQL + pgvector)]
  API --> DB
  DB --> Search[Cited retrieval results]
  Search --> Web
```

Create `docs/architecture/system-overview.md`:

````markdown
# System Overview

DocIntel AI is local-first. The frontend calls FastAPI, FastAPI stores uploaded files locally, PyMuPDF extracts PDF text, sentence-transformers creates BGE embeddings, and PostgreSQL with pgvector stores searchable vectors.

No paid AI APIs are required for the MVP.

```mermaid
flowchart LR
  Browser[Browser] --> Web[Next.js web app]
  Web --> API[FastAPI backend]
  API --> Storage[Local file storage]
  API --> Parser[PyMuPDF PDF parser]
  Parser --> Chunks[Text chunks]
  Chunks --> Embedder[Local BGE embeddings]
  Embedder --> DB[(PostgreSQL + pgvector)]
  API --> DB
  DB --> Search[Cited retrieval results]
  Search --> Web
```
````

- [ ] **Step 2: Write local development guide**

Create `docs/architecture/local-development.md`:

````markdown
# Local Development

## Prerequisites

- Docker Desktop with WSL 2 integration enabled.
- Python 3.11 or 3.12.
- Node.js LTS with `node` and `npm` available in PowerShell.

## Start Database

```powershell
docker compose up -d
```

## Start Backend

```powershell
cd apps/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend health check:

```powershell
Invoke-RestMethod http://localhost:8000/health
```

## Start Frontend

```powershell
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`.

## Download FUNSD

```powershell
python apps/api/scripts/download_funsd.py
```

FUNSD is stored under `data/raw/funsd` and is ignored by Git.
````

- [ ] **Step 3: Update README**

Modify `README.md`:

````markdown
# DocIntel AI

DocIntel AI is a local-first multimodal document intelligence platform. It uploads PDFs, extracts text, chunks document content, creates local embeddings, stores vectors in PostgreSQL with pgvector, and returns cited evidence for semantic search.

The MVP does not require OpenAI, Anthropic, hosted vector databases, or paid APIs.

## Why This Project Matters

This project demonstrates full-stack AI engineering:

- FastAPI backend design
- Next.js and TypeScript frontend
- Local embedding models
- PostgreSQL vector search with pgvector
- PDF parsing with PyMuPDF
- Docker-based infrastructure
- Retrieval evaluation metrics
- Portfolio-ready documentation

## Architecture

See [docs/architecture/system-overview.md](docs/architecture/system-overview.md).

## Local Development

See [docs/architecture/local-development.md](docs/architecture/local-development.md).

## Dataset

FUNSD is used for local document understanding experiments:

```powershell
python apps/api/scripts/download_funsd.py
```

Dataset files are stored in `data/raw/funsd` and are not committed.

## Current Scope

Week-one MVP:

- PDF upload and indexing
- Image upload with deferred-OCR status
- Local BGE embeddings
- pgvector semantic search
- Cited evidence UI
- Deterministic retrieval metrics

Out of scope for this MVP:

- Ollama answer generation
- OCR for scanned images
- Authentication
- Cloud deployment
- Fine-tuning
````

- [ ] **Step 4: Add CI workflow**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install backend dependencies
        working-directory: apps/api
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Run backend unit tests
        working-directory: apps/api
        run: pytest -m "not integration" -v

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
          cache: npm
          cache-dependency-path: apps/web/package-lock.json
      - name: Install frontend dependencies
        working-directory: apps/web
        run: npm ci
      - name: Run frontend tests
        working-directory: apps/web
        run: npm test
      - name: Build frontend
        working-directory: apps/web
        run: npm run build
```

- [ ] **Step 5: Run full local checks**

Run:

```powershell
docker compose up -d
cd apps/api
pytest -v
cd ..\web
npm test
npm run build
```

Expected: backend tests, frontend tests, and frontend build pass.

- [ ] **Step 6: Commit documentation and CI**

Run:

```powershell
cd ..\..
git add README.md docs/architecture .github/workflows/ci.yml
git commit -m "docs: add local development guide and ci"
```

---

## Execution Timeline

Day 1:

- Task 1: Backend foundation and Docker infrastructure.
- Task 2: Database models and session management.

Day 2:

- Task 3: Upload validation and local file storage.
- Task 4: PDF parsing and text chunking.

Day 3:

- Task 5: Local embedding provider and search formatting.
- Task 6: Document indexing API.

Day 4:

- Task 7: Semantic search API.
- Task 8: Frontend foundation and typed API client.

Day 5:

- Task 9: Frontend upload, document list, and search UI.

Day 6:

- Task 10: FUNSD download script and retrieval evaluation.

Day 7:

- Task 11: Local run documentation, CI, and portfolio polish.
- Open PR from `feature/local-first-docintel` to `main`.
- Merge only after local verification and user approval.

## What Nigel Needs To Do During Implementation

Before frontend coding:

1. Install Node.js LTS from `https://nodejs.org/`.
2. Open a new PowerShell window.
3. Run `node --version` and `npm --version`.
4. Share the output if either command fails.

During backend/database coding:

1. Keep Docker Desktop running.
2. Let the first `sentence-transformers` model download complete; it may take several minutes.
3. Share any Windows firewall, GitHub auth, or Python package build prompt if it appears.

During final verification:

1. Run browser checks locally when asked.
2. Review screenshots or the live local app.
3. Approve the PR merge after the MVP works.

## Branch and Commit Flow

1. Create branch `feature/local-first-docintel` from `main`.
2. Implement one task at a time.
3. Commit after each task using the commit message listed in that task.
4. Push branch after major milestones or at the end of each development session.
5. Open a PR when the MVP passes verification.
6. Merge after user approval.
