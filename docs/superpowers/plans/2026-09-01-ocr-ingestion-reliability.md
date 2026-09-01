# OCR Ingestion Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add local OCR ingestion for scanned PDFs and document images while keeping normal text PDFs fast and searchable.

**Architecture:** Keep the current FastAPI + SQLAlchemy + PyMuPDF + pgvector pipeline. Add a small OCR provider boundary, OCR-aware extraction results, additive metadata columns, and UI quality reporting without creating a background worker service.

**Tech Stack:** FastAPI, SQLAlchemy, PostgreSQL/pgvector, PyMuPDF, Pillow, Tesseract CLI, sentence-transformers, Next.js, React, Vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-09-01-ocr-ingestion-reliability-design.md`

## Global Constraints

- Local-first only; no paid OCR APIs.
- No authentication, cloud storage, layout-aware form extraction, table reconstruction, bounding-box overlays, model training, or FUNSD fine-tuning.
- No background worker service in this phase; indexing remains request-driven with persisted status updates.
- Normal text PDFs must not run OCR unless pages have sparse native text.
- OCR tests must use test doubles so the suite does not require Tesseract to be installed.
- OCR defaults: enabled `true`, language `eng`, render DPI `200`, max OCR pages `25`, page timeout `20` seconds.
- API keeps returning document `status` as a string; web displays `ocr_processing` as `OCR running`.

---

## File Structure

- `apps/api/app/core/config.py`: add OCR settings.
- `apps/api/app/db/models.py`: add `ocr_processing` status and OCR/processing metadata columns.
- `apps/api/app/db/init_db.py`: keep `create_all()` and add a small additive schema synchronizer for local databases that already exist.
- `apps/api/app/documents/parser.py`: return sparse/empty PDF pages instead of rejecting before OCR.
- `apps/api/app/documents/ocr.py`: new OCR provider protocol, fake-friendly result dataclass, Tesseract CLI provider, and availability errors.
- `apps/api/app/documents/extraction.py`: new PDF/image extraction coordinator that combines native text and OCR text.
- `apps/api/app/documents/parse_quality.py`: compute OCR-aware quality fields from persisted pages.
- `apps/api/app/documents/schemas.py`: expose OCR-aware parse quality fields.
- `apps/api/app/documents/router.py`: inject OCR provider/settings and return new fields.
- `apps/api/app/documents/service.py`: wire hybrid PDF and image OCR into indexing/reindexing.
- `apps/api/app/retrieval/router.py`: keep search stable and return clear insufficient-evidence diagnostics for scoped non-indexed documents.
- `apps/api/app/evaluation/golden.py`: add OCR readiness cases.
- `apps/web/lib/types.ts`: add OCR quality fields.
- `apps/web/components/status-badge.tsx`: show `ocr_processing`.
- `apps/web/components/document-list.tsx`: show OCR quality and allow retry/reindex for images and weak PDFs.
- `apps/web/app/documents/page.tsx`: call reindex for image documents too once the backend accepts it.
- `apps/web/app/search/page.tsx`: show selected-document OCR guidance when the document is not indexed.
- Tests listed in each task below.

---

### Task 1: OCR Settings, Status, and Additive Schema Foundation

**Files:**
- Modify: `apps/api/app/core/config.py`
- Modify: `apps/api/app/db/models.py`
- Modify: `apps/api/app/db/init_db.py`
- Modify: `apps/api/tests/core/test_config.py`
- Modify: `apps/api/tests/db/test_models.py`
- Create: `apps/api/tests/db/test_init_db.py`

**Interfaces:**
- Produces: `Settings.ocr_enabled: bool`, `ocr_language: str`, `ocr_dpi: int`, `ocr_max_pages: int`, `ocr_page_timeout_seconds: int`, `tesseract_cmd: str | None`.
- Produces: `DocumentStatus.OCR_PROCESSING`.
- Produces: `Page.text_source`, `ocr_engine`, `ocr_confidence`, `ocr_duration_ms`.
- Produces: `Document.processing_started_at`, `processing_completed_at`, `processing_duration_ms`.
- Produces: `sync_local_schema(engine) -> None`, called by `init_db()`.
- Produces: `document_status_enum_sync_sql() -> str` for additive PostgreSQL enum updates.

- [x] **Step 1: Write failing config and model tests**

Add to `apps/api/tests/core/test_config.py`:

```python
def test_ocr_settings_have_local_defaults():
    settings = Settings()

    assert settings.ocr_enabled is True
    assert settings.ocr_language == "eng"
    assert settings.ocr_dpi == 200
    assert settings.ocr_max_pages == 25
    assert settings.ocr_page_timeout_seconds == 20
    assert settings.tesseract_cmd is None
```

Add to `apps/api/tests/db/test_models.py`:

```python
def test_document_status_includes_ocr_processing():
    assert DocumentStatus.OCR_PROCESSING.value == "ocr_processing"


def test_page_ocr_metadata_columns_are_declared():
    columns = Page.__table__.columns

    assert columns["text_source"].nullable is False
    assert columns["ocr_engine"].nullable is True
    assert columns["ocr_confidence"].nullable is True
    assert columns["ocr_duration_ms"].nullable is True


def test_document_processing_metadata_columns_are_declared():
    columns = Document.__table__.columns

    assert columns["processing_started_at"].nullable is True
    assert columns["processing_completed_at"].nullable is True
    assert columns["processing_duration_ms"].nullable is True
```

Add imports in `apps/api/tests/db/test_models.py`:

```python
from app.db.models import ChunkEmbedding, Document, DocumentStatus, Page
```

- [x] **Step 2: Write failing schema sync test**

Create `apps/api/tests/db/test_init_db.py`:

```python
from sqlalchemy import create_engine, inspect, text

from app.db.init_db import sync_local_schema


def test_sync_local_schema_adds_missing_ocr_columns(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'schema.db'}")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE documents (id TEXT PRIMARY KEY)"))
        connection.execute(text("CREATE TABLE pages (id TEXT PRIMARY KEY)"))

    sync_local_schema(engine)

    inspector = inspect(engine)
    document_columns = {column["name"] for column in inspector.get_columns("documents")}
    page_columns = {column["name"] for column in inspector.get_columns("pages")}

    assert {"processing_started_at", "processing_completed_at", "processing_duration_ms"} <= document_columns
    assert {"text_source", "ocr_engine", "ocr_confidence", "ocr_duration_ms"} <= page_columns
```

- [x] **Step 3: Run Task 1 tests to verify red**

Run:

```powershell
pytest apps/api/tests/core/test_config.py apps/api/tests/db/test_models.py apps/api/tests/db/test_init_db.py -q
```

Expected: failures mention missing OCR settings, missing `OCR_PROCESSING`, missing metadata columns, and missing `sync_local_schema`.

- [x] **Step 4: Implement settings and model columns**

In `apps/api/app/core/config.py`, add:

```python
    ocr_enabled: bool = True
    ocr_language: str = "eng"
    ocr_dpi: int = 200
    ocr_max_pages: int = 25
    ocr_page_timeout_seconds: int = 20
    tesseract_cmd: str | None = None
```

In `apps/api/app/db/models.py`, add `Float` to imports and add:

```python
    OCR_PROCESSING = "ocr_processing"
```

Add to `Document`:

```python
    processing_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    processing_duration_ms: Mapped[int | None] = mapped_column(Integer)
```

Add to `Page`:

```python
    text_source: Mapped[str] = mapped_column(String(20), nullable=False, default="native")
    ocr_engine: Mapped[str | None] = mapped_column(String(100))
    ocr_confidence: Mapped[float | None] = mapped_column(Float)
    ocr_duration_ms: Mapped[int | None] = mapped_column(Integer)
```

- [x] **Step 5: Implement additive schema sync**

In `apps/api/app/db/init_db.py`, add:

```python
from sqlalchemy import Engine, inspect, text


def _ddl_type(engine: Engine, logical_type: str) -> str:
    if engine.dialect.name == "sqlite":
        return {
            "timestamp": "DATETIME",
            "integer": "INTEGER",
            "string": "VARCHAR",
            "float": "FLOAT",
        }[logical_type]
    return {
        "timestamp": "TIMESTAMP WITH TIME ZONE",
        "integer": "INTEGER",
        "string": "VARCHAR",
        "float": "DOUBLE PRECISION",
    }[logical_type]


def _add_column_if_missing(connection, table_name: str, column_name: str, column_sql: str) -> None:
    inspector = inspect(connection)
    existing = {column["name"] for column in inspector.get_columns(table_name)}
    if column_name not in existing:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))


def sync_local_schema(bind: Engine) -> None:
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())
    if not {"documents", "pages"} <= table_names:
        return

    with bind.begin() as connection:
        timestamp_type = _ddl_type(bind, "timestamp")
        integer_type = _ddl_type(bind, "integer")
        string_type = _ddl_type(bind, "string")
        float_type = _ddl_type(bind, "float")
        _add_column_if_missing(connection, "documents", "processing_started_at", f"processing_started_at {timestamp_type}")
        _add_column_if_missing(connection, "documents", "processing_completed_at", f"processing_completed_at {timestamp_type}")
        _add_column_if_missing(connection, "documents", "processing_duration_ms", f"processing_duration_ms {integer_type}")
        _add_column_if_missing(connection, "pages", "text_source", f"text_source {string_type}(20) DEFAULT 'native' NOT NULL")
        _add_column_if_missing(connection, "pages", "ocr_engine", f"ocr_engine {string_type}(100)")
        _add_column_if_missing(connection, "pages", "ocr_confidence", f"ocr_confidence {float_type}")
        _add_column_if_missing(connection, "pages", "ocr_duration_ms", f"ocr_duration_ms {integer_type}")
```

Update `init_db()`:

```python
def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    sync_local_schema(engine)
```

- [x] **Step 6: Run Task 1 tests to verify green**

Run:

```powershell
pytest apps/api/tests/core/test_config.py apps/api/tests/db/test_models.py apps/api/tests/db/test_init_db.py -q
```

Expected: all selected tests pass.

- [x] **Step 7: Commit Task 1**

Run:

```powershell
git add apps/api/app/core/config.py apps/api/app/db/models.py apps/api/app/db/init_db.py apps/api/tests/core/test_config.py apps/api/tests/db/test_models.py apps/api/tests/db/test_init_db.py
git commit -m "feat: add ocr ingestion schema foundation"
```

---

### Task 2: OCR Provider and Hybrid Extraction Primitives

**Files:**
- Modify: `apps/api/requirements.txt`
- Modify: `apps/api/app/documents/parser.py`
- Create: `apps/api/app/documents/ocr.py`
- Create: `apps/api/app/documents/extraction.py`
- Modify: `apps/api/tests/documents/test_parser.py`
- Create: `apps/api/tests/documents/test_ocr.py`
- Create: `apps/api/tests/documents/test_extraction.py`

**Interfaces:**
- Consumes: OCR settings from Task 1.
- Produces: `ParsedPage` no longer raises for all-empty PDFs.
- Produces: `OcrPageResult`, `OcrUnavailableError`, `OcrProvider`, `TesseractOcrProvider`.
- Produces: `ExtractedPage`, `ExtractionResult`, `extract_pdf_pages()`, `extract_image_pages()`.

- [x] **Step 1: Write failing parser test for empty scanned PDFs**

Change `test_parse_pdf_rejects_empty_pdf` in `apps/api/tests/documents/test_parser.py` to:

```python
def test_parse_pdf_returns_empty_text_pages_for_scanned_pdf(tmp_path):
    pdf_path = tmp_path / "empty.pdf"
    document = fitz.open()
    document.new_page(width=300, height=200)
    document.save(pdf_path)
    document.close()

    pages = parse_pdf(pdf_path)

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].text == ""
    assert pages[0].width == 300
    assert pages[0].height == 200
```

- [x] **Step 2: Write failing OCR provider tests**

Create `apps/api/tests/documents/test_ocr.py`:

```python
from PIL import Image

from app.documents.ocr import TesseractOcrProvider


def test_tesseract_provider_reports_unavailable_when_disabled():
    provider = TesseractOcrProvider(enabled=False, tesseract_cmd=None, timeout_seconds=20)

    assert provider.is_available() is False


def test_tesseract_provider_reports_unavailable_when_command_is_missing():
    provider = TesseractOcrProvider(enabled=True, tesseract_cmd="missing-tesseract-command", timeout_seconds=20)

    assert provider.is_available() is False


def test_tesseract_provider_does_not_run_when_unavailable():
    provider = TesseractOcrProvider(enabled=False, tesseract_cmd=None, timeout_seconds=20)
    image = Image.new("RGB", (50, 20), "white")

    result = provider.ocr_image(image, language="eng")

    assert result.text == ""
    assert result.confidence is None
    assert result.engine_name == "tesseract-unavailable"
```

- [x] **Step 3: Write failing extraction tests**

Create `apps/api/tests/documents/test_extraction.py`:

```python
from pathlib import Path

import fitz
from PIL import Image

from app.documents.extraction import extract_image_pages, extract_pdf_pages
from app.documents.ocr import OcrPageResult


class FakeOcrProvider:
    engine_name = "fake-ocr"

    def __init__(self, text: str = "OCR text from scanned page") -> None:
        self.text = text
        self.calls = 0

    def is_available(self) -> bool:
        return True

    def ocr_image(self, image: Image.Image, *, language: str) -> OcrPageResult:
        self.calls += 1
        return OcrPageResult(text=self.text, confidence=91.5, engine_name=self.engine_name, duration_ms=7)


def create_pdf(path: Path, page_texts: list[str]) -> bytes:
    document = fitz.open()
    for text in page_texts:
        page = document.new_page(width=300, height=200)
        if text:
            page.insert_text((36, 72), text)
    document.save(path)
    document.close()
    return path.read_bytes()


def test_extract_pdf_pages_ocr_only_sparse_pages(tmp_path):
    pdf_path = tmp_path / "mixed.pdf"
    create_pdf(pdf_path, ["Native text with enough words " * 8, ""])
    provider = FakeOcrProvider()

    result = extract_pdf_pages(pdf_path, ocr_provider=provider, language="eng", dpi=120, max_ocr_pages=25)

    assert provider.calls == 1
    assert [page.text_source for page in result.pages] == ["native", "ocr"]
    assert "Native text" in result.pages[0].text
    assert result.pages[1].text == "OCR text from scanned page"
    assert result.ocr_page_count == 1


def test_extract_image_pages_uses_ocr_as_page_one(tmp_path):
    image_path = tmp_path / "scan.png"
    Image.new("RGB", (120, 60), "white").save(image_path)
    provider = FakeOcrProvider("Receipt total is RM 42.00")

    result = extract_image_pages(image_path, ocr_provider=provider, language="eng")

    assert provider.calls == 1
    assert len(result.pages) == 1
    assert result.pages[0].page_number == 1
    assert result.pages[0].text == "Receipt total is RM 42.00"
    assert result.pages[0].text_source == "ocr"
```

- [x] **Step 4: Run Task 2 tests to verify red**

Run:

```powershell
pytest apps/api/tests/documents/test_parser.py apps/api/tests/documents/test_ocr.py apps/api/tests/documents/test_extraction.py -q
```

Expected: failures mention missing OCR/extraction modules and parser still raising on empty PDFs.

- [x] **Step 5: Implement parser relaxation**

Remove this block from `parse_pdf()`:

```python
    if not any(page.text for page in pages):
        raise DocumentParseError("No extractable text found in this PDF.")
```

Keep malformed PDF wrapping unchanged.

- [x] **Step 6: Implement OCR provider**

Add `Pillow==12.1.0` to `apps/api/requirements.txt`.

Create `apps/api/app/documents/ocr.py` with a Tesseract CLI provider that:

- uses `shutil.which("tesseract")` when `tesseract_cmd` is not provided;
- returns `False` from `is_available()` when disabled or command is missing;
- returns `OcrPageResult(text="", confidence=None, engine_name="tesseract-unavailable", duration_ms=0)` when unavailable;
- writes the PIL image to a temporary PNG;
- runs `tesseract <image> stdout -l <language> --psm 6 tsv`;
- parses TSV rows into text and average confidence for non-empty words.

- [x] **Step 7: Implement extraction coordinator**

Create `apps/api/app/documents/extraction.py` with:

```python
@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    text: str
    width: float | None
    height: float | None
    text_source: str
    ocr_engine: str | None = None
    ocr_confidence: float | None = None
    ocr_duration_ms: int | None = None


@dataclass(frozen=True)
class ExtractionResult:
    pages: list[ExtractedPage]
    ocr_page_count: int
    ocr_duration_ms: int
```

Implement:

```python
def extract_pdf_pages(
    file_path: Path,
    *,
    ocr_provider: OcrProvider | None,
    language: str,
    dpi: int,
    max_ocr_pages: int,
) -> ExtractionResult:
    ...
```

and:

```python
def extract_image_pages(file_path: Path, *, ocr_provider: OcrProvider | None, language: str) -> ExtractionResult:
    ...
```

Use the same sparse threshold as parse quality by importing a public helper added in `parse_quality.py`:

```python
def normalized_text_length(text: str) -> int:
    return len(" ".join(text.split()))
```

- [x] **Step 8: Run Task 2 tests to verify green**

Run:

```powershell
pytest apps/api/tests/documents/test_parser.py apps/api/tests/documents/test_ocr.py apps/api/tests/documents/test_extraction.py -q
```

Expected: all selected tests pass.

- [x] **Step 9: Commit Task 2**

Run:

```powershell
git add apps/api/requirements.txt apps/api/app/documents/parser.py apps/api/app/documents/ocr.py apps/api/app/documents/extraction.py apps/api/app/documents/parse_quality.py apps/api/tests/documents/test_parser.py apps/api/tests/documents/test_ocr.py apps/api/tests/documents/test_extraction.py
git commit -m "feat: add local ocr extraction primitives"
```

---

### Task 3: Wire OCR Into Upload and Reindex Services

**Files:**
- Modify: `apps/api/app/documents/service.py`
- Modify: `apps/api/app/documents/router.py`
- Modify: `apps/api/tests/documents/test_service.py`
- Modify: `apps/api/tests/documents/test_router.py`

**Interfaces:**
- Consumes: `OcrProvider`, `ExtractionResult`, OCR settings.
- Produces: image upload indexing when OCR is available.
- Produces: PDF hybrid indexing when sparse pages are OCR candidates.
- Produces: reindex support for PDFs and images.

- [x] **Step 1: Write failing service tests**

Add fake OCR provider to `apps/api/tests/documents/test_service.py`:

```python
from PIL import Image

from app.documents.ocr import OcrPageResult


class FakeOcrProvider:
    engine_name = "fake-ocr"

    def __init__(self, available: bool = True, text: str = "OCR searchable content from scanned document") -> None:
        self.available = available
        self.text = text

    def is_available(self) -> bool:
        return self.available

    def ocr_image(self, image: Image.Image, *, language: str) -> OcrPageResult:
        return OcrPageResult(text=self.text, confidence=88.0, engine_name=self.engine_name, duration_ms=5)
```

Replace `test_index_stored_upload_defers_image_ocr` with:

```python
def test_index_stored_upload_indexes_image_with_available_ocr(db_session, tmp_path):
    image_path = tmp_path / "scan.png"
    Image.new("RGB", (120, 60), "white").save(image_path)
    stored = save_upload_bytes("scan.png", "image/png", image_path.read_bytes(), tmp_path / "storage", 20)

    document = index_stored_upload(
        db_session,
        stored,
        lambda: FakeEmbeddingProvider(),
        ocr_provider_factory=lambda: FakeOcrProvider(),
        ocr_language="eng",
        ocr_dpi=200,
        ocr_max_pages=25,
    )

    assert document.status == DocumentStatus.INDEXED
    assert document.pages[0].text_source == "ocr"
    assert "OCR searchable content" in document.chunks[0].text
```

Add:

```python
def test_index_stored_upload_defers_image_when_ocr_is_unavailable(db_session, tmp_path):
    stored = save_upload_bytes("scan.png", "image/png", b"image-bytes", tmp_path / "storage", 20)

    document = index_stored_upload(
        db_session,
        stored,
        lambda: FakeEmbeddingProvider(),
        ocr_provider_factory=lambda: FakeOcrProvider(available=False),
        ocr_language="eng",
        ocr_dpi=200,
        ocr_max_pages=25,
    )

    assert document.status == DocumentStatus.DEFERRED_OCR
    assert "Local OCR is not available" in (document.error_message or "")
```

- [x] **Step 2: Write failing router tests**

Update `apps/api/tests/documents/test_router.py` so image upload with a fake OCR provider returns `indexed`, and add a reindex image acceptance test:

```python
def test_reindex_document_endpoint_accepts_images_when_ocr_is_available(db_session, tmp_path):
    image_path = tmp_path / "scan.png"
    Image.new("RGB", (120, 60), "white").save(image_path)
    stored = save_upload_bytes("scan.png", "image/png", image_path.read_bytes(), tmp_path / "storage", 20)
    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider(), ocr_provider_factory=lambda: FakeOcrProvider(available=False))
    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[router.get_embedding_provider_factory] = lambda: lambda: FakeEmbeddingProvider()
    app.dependency_overrides[router.get_ocr_provider_factory] = lambda: lambda: FakeOcrProvider()
    client = TestClient(app)

    response = client.post(f"/documents/{document.id}/reindex")

    assert response.status_code == 200
    assert response.json()["status"] == "indexed"
```

- [x] **Step 3: Run Task 3 tests to verify red**

Run:

```powershell
pytest apps/api/tests/documents/test_service.py apps/api/tests/documents/test_router.py -q
```

Expected: failures mention unexpected `index_stored_upload` keyword arguments and missing `get_ocr_provider_factory`.

- [x] **Step 4: Update service signatures and extraction storage**

Change `index_stored_upload()` and `reindex_document()` to accept:

```python
ocr_provider_factory: OcrProviderFactory | None = None
ocr_language: str = "eng"
ocr_dpi: int = 200
ocr_max_pages: int = 25
```

Replace `_add_pdf_index_records()` with a generic `_add_index_records_from_pages()` that accepts `list[ExtractedPage]`.

Persist `Page` metadata:

```python
Page(
    document_id=document.id,
    page_number=extracted_page.page_number,
    text=extracted_page.text,
    width=extracted_page.width,
    height=extracted_page.height,
    text_source=extracted_page.text_source,
    ocr_engine=extracted_page.ocr_engine,
    ocr_confidence=extracted_page.ocr_confidence,
    ocr_duration_ms=extracted_page.ocr_duration_ms,
)
```

- [x] **Step 5: Implement status and duration tracking**

Set:

```python
document.processing_started_at = utc_now()
document.status = DocumentStatus.OCR_PROCESSING
```

before OCR work when image upload or PDF sparse pages require OCR. On success, set:

```python
document.processing_completed_at = utc_now()
document.processing_duration_ms = int((document.processing_completed_at - document.processing_started_at).total_seconds() * 1000)
```

- [x] **Step 6: Update router dependencies**

In `apps/api/app/documents/router.py`, add:

```python
def get_ocr_provider_factory(settings: Annotated[Settings, Depends(get_settings)]) -> OcrProviderFactory:
    return lambda: TesseractOcrProvider(
        enabled=settings.ocr_enabled,
        tesseract_cmd=settings.tesseract_cmd,
        timeout_seconds=settings.ocr_page_timeout_seconds,
    )
```

Pass OCR settings into upload and reindex service calls.

- [x] **Step 7: Run Task 3 tests to verify green**

Run:

```powershell
pytest apps/api/tests/documents/test_service.py apps/api/tests/documents/test_router.py -q
```

Expected: all selected tests pass.

- [x] **Step 8: Commit Task 3**

Run:

```powershell
git add apps/api/app/documents/service.py apps/api/app/documents/router.py apps/api/tests/documents/test_service.py apps/api/tests/documents/test_router.py
git commit -m "feat: index documents with local ocr"
```

---

### Task 4: OCR Quality Reporting and Search Guidance

**Files:**
- Modify: `apps/api/app/documents/parse_quality.py`
- Modify: `apps/api/app/documents/schemas.py`
- Modify: `apps/api/app/documents/router.py`
- Modify: `apps/api/app/retrieval/router.py`
- Modify: `apps/api/tests/documents/test_parse_quality.py`
- Modify: `apps/api/tests/documents/test_router.py`
- Modify: `apps/api/tests/retrieval/test_search_api.py`

**Interfaces:**
- Consumes: page OCR metadata from Task 3.
- Produces: OCR-aware parse quality fields in API responses.
- Produces: scoped search response with insufficient evidence when selected document has no indexed chunks.

- [x] **Step 1: Write failing parse quality test**

Add to `apps/api/tests/documents/test_parse_quality.py`:

```python
class OcrPage:
    def __init__(self, text: str, text_source: str, confidence: float | None, duration_ms: int | None) -> None:
        self.text = text
        self.text_source = text_source
        self.ocr_confidence = confidence
        self.ocr_duration_ms = duration_ms


def test_parse_quality_reports_ocr_metadata():
    profile = build_parse_quality_from_pages(
        [
            OcrPage("Native searchable text " * 8, "native", None, None),
            OcrPage("OCR searchable text " * 8, "ocr", 91.0, 15),
            OcrPage("Hybrid searchable text " * 8, "hybrid", 81.0, 25),
        ]
    )

    assert profile.native_text_page_count == 1
    assert profile.ocr_page_count == 1
    assert profile.hybrid_page_count == 1
    assert profile.ocr_confidence_average == 86.0
    assert profile.ocr_duration_ms == 40
    assert profile.text_source_summary == {"native": 1, "ocr": 1, "hybrid": 1}
```

- [x] **Step 2: Write failing API/search tests**

Add assertions to existing document read tests:

```python
assert "ocr_page_count" in list_response.json()[0]["parse_quality"]
assert "text_source_summary" in detail_response.json()["parse_quality"]
```

Add to `apps/api/tests/retrieval/test_search_api.py`:

```python
def test_scoped_search_on_deferred_ocr_document_returns_insufficient_evidence(db_session, tmp_path):
    stored = save_upload_bytes("scan.png", "image/png", b"image-bytes", tmp_path / "storage", 20)
    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider(), ocr_provider_factory=lambda: FakeOcrProvider(available=False))
    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_embedding_provider] = lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    response = client.post("/search", json={"query": "What is in this scan?", "document_id": document.id})

    assert response.status_code == 200
    payload = response.json()
    assert payload["quality"]["status"] == "insufficient_evidence"
    assert "OCR" in payload["quality"]["reason"]
```

- [x] **Step 3: Run Task 4 tests to verify red**

Run:

```powershell
pytest apps/api/tests/documents/test_parse_quality.py apps/api/tests/documents/test_router.py apps/api/tests/retrieval/test_search_api.py -q
```

Expected: failures mention missing parse quality fields and missing scoped OCR guidance.

- [x] **Step 4: Extend schemas and parse quality**

In `ParseQualityRead`, add defaults:

```python
    ocr_page_count: int = 0
    native_text_page_count: int = 0
    hybrid_page_count: int = 0
    ocr_confidence_average: float | None = None
    ocr_duration_ms: int = 0
    text_source_summary: dict[str, int] = {}
```

Update `build_parse_quality_from_pages()` to read optional attributes with `getattr(page, "text_source", "native")`.

- [x] **Step 5: Add scoped non-indexed document guard**

In `apps/api/app/retrieval/router.py`, before embedding/search when `document_id` is provided and the document exists with no chunks, return a `SearchResponse` with:

- `hits=[]`
- `answer=None`
- `quality.status="insufficient_evidence"`
- `quality.confidence="weak"`
- `quality.reason` containing OCR guidance when `document.status == DocumentStatus.DEFERRED_OCR`
- `diagnostics.related_result_count=0`

- [x] **Step 6: Run Task 4 tests to verify green**

Run:

```powershell
pytest apps/api/tests/documents/test_parse_quality.py apps/api/tests/documents/test_router.py apps/api/tests/retrieval/test_search_api.py -q
```

Expected: all selected tests pass.

- [x] **Step 7: Commit Task 4**

Run:

```powershell
git add apps/api/app/documents/parse_quality.py apps/api/app/documents/schemas.py apps/api/app/documents/router.py apps/api/app/retrieval/router.py apps/api/tests/documents/test_parse_quality.py apps/api/tests/documents/test_router.py apps/api/tests/retrieval/test_search_api.py
git commit -m "feat: report ocr quality in document search"
```

---

### Task 5: Frontend OCR Status, Quality, and Retry UX

**Files:**
- Modify: `apps/web/lib/types.ts`
- Modify: `apps/web/components/status-badge.tsx`
- Modify: `apps/web/components/document-list.tsx`
- Modify: `apps/web/app/documents/page.tsx`
- Modify: `apps/web/app/search/page.tsx`
- Modify: `apps/web/tests/status-badge.test.tsx`
- Modify: `apps/web/tests/document-list.test.tsx`
- Modify: `apps/web/tests/documents-page.test.tsx`
- Modify: `apps/web/tests/search-page.test.tsx`

**Interfaces:**
- Consumes: OCR-aware `parse_quality` fields from Task 4.
- Produces: visible OCR status, quality report, and retry/reindex controls for PDFs and images.

- [ ] **Step 1: Write failing frontend tests**

Add to `apps/web/tests/status-badge.test.tsx`:

```tsx
it("renders OCR processing status text", () => {
  render(<StatusBadge status="ocr_processing" />);

  expect(screen.getByText("OCR running")).toHaveClass("bg-teal-50");
});
```

Add to `apps/web/tests/document-list.test.tsx`:

```tsx
it("shows OCR quality details and retry action for image documents", () => {
  render(
    <DocumentList
      documents={[
        {
          id: "doc-image",
          filename: "scan.png",
          mime_type: "image/png",
          status: "deferred_ocr",
          parse_quality: {
            page_count: 1,
            text_page_count: 0,
            empty_page_count: 1,
            total_characters: 0,
            average_characters_per_page: 0,
            low_text_page_ratio: 1,
            scanned_likelihood: "high",
            warnings: ["Local OCR is not available."],
            ocr_page_count: 0,
            native_text_page_count: 0,
            hybrid_page_count: 0,
            ocr_confidence_average: null,
            ocr_duration_ms: 0,
            text_source_summary: {},
          },
        },
      ]}
      onReindex={vi.fn().mockResolvedValue(undefined)}
    />,
  );

  expect(screen.getAllByText("OCR recommended").length).toBeGreaterThan(0);
  expect(screen.getAllByRole("button", { name: "Retry OCR scan.png" })).toHaveLength(2);
});
```

- [ ] **Step 2: Run Task 5 tests to verify red**

Run:

```powershell
npm --prefix apps/web test -- status-badge.test.tsx document-list.test.tsx documents-page.test.tsx search-page.test.tsx
```

Expected: failures mention missing `ocr_processing`, missing OCR fields in types, and image retry button absence.

- [ ] **Step 3: Extend frontend types and status badge**

In `apps/web/lib/types.ts`, add OCR fields to `ParseQuality`.

In `apps/web/components/status-badge.tsx`, add:

```tsx
ocr_processing: "OCR running"
```

with teal styling.

- [ ] **Step 4: Update document actions and quality display**

In `DocumentActions`, change reindex label:

```tsx
const isImage = document.mime_type.startsWith("image/");
const reindexLabel = isImage || document.status === "deferred_ocr" ? "Retry OCR" : "Reindex";
```

Allow reindex when:

```tsx
const canReindex = Boolean(onReindex) && (
  document.mime_type === "application/pdf" ||
  document.mime_type.startsWith("image/")
);
```

Show OCR quality rows:

- OCR pages: `${quality.ocr_page_count}/${quality.page_count}`
- Text source: join `Object.entries(quality.text_source_summary)` as `native 1, ocr 2`
- OCR confidence: `${quality.ocr_confidence_average}%` when present

- [ ] **Step 5: Update documents page and search guidance**

Keep `reindexDocument()` as the action name in `apps/web/app/documents/page.tsx`, but let it call the same endpoint for images.

In `apps/web/app/search/page.tsx`, when a selected document status is `deferred_ocr`, `ocr_processing`, or `failed`, display a compact warning above search results using the document `error_message` when present.

- [ ] **Step 6: Run Task 5 tests to verify green**

Run:

```powershell
npm --prefix apps/web test -- status-badge.test.tsx document-list.test.tsx documents-page.test.tsx search-page.test.tsx
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit Task 5**

Run:

```powershell
git add apps/web/lib/types.ts apps/web/components/status-badge.tsx apps/web/components/document-list.tsx apps/web/app/documents/page.tsx apps/web/app/search/page.tsx apps/web/tests/status-badge.test.tsx apps/web/tests/document-list.test.tsx apps/web/tests/documents-page.test.tsx apps/web/tests/search-page.test.tsx
git commit -m "feat: surface ocr status in web workspace"
```

---

### Task 6: OCR Evaluation Cases and Full Verification

**Files:**
- Modify: `apps/api/app/evaluation/golden.py`
- Modify: `apps/api/tests/evaluation/test_golden_eval.py`
- Modify: `apps/web/tests/evaluation-summary.test.tsx`
- Modify: `docs/superpowers/plans/2026-09-01-ocr-ingestion-reliability.md`

**Interfaces:**
- Consumes: OCR quality/search behavior from Tasks 1-5.
- Produces: visible OCR cases in the golden evaluation suite.

- [ ] **Step 1: Write failing golden evaluation tests**

Add assertions in `apps/api/tests/evaluation/test_golden_eval.py`:

```python
def test_golden_eval_includes_ocr_quality_cases():
    result = run_golden_evaluation()

    case_ids = {case.case_id for case in result.cases}

    assert "ocr-image-deferred-guidance" in case_ids
    assert "ocr-sparse-pdf-guidance" in case_ids
```

- [ ] **Step 2: Run Task 6 evaluation test to verify red**

Run:

```powershell
pytest apps/api/tests/evaluation/test_golden_eval.py -q
```

Expected: missing OCR case IDs.

- [ ] **Step 3: Add OCR evaluation cases**

In `apps/api/app/evaluation/golden.py`, add two deterministic cases:

- `ocr-image-deferred-guidance`: verifies image documents without OCR availability produce an actionable OCR message.
- `ocr-sparse-pdf-guidance`: verifies sparse PDFs are identified as OCR candidates.

Both cases should be deterministic and should not require Tesseract.

- [ ] **Step 4: Run full backend and frontend verification**

Run:

```powershell
pytest apps/api/tests
npm --prefix apps/web test
npm --prefix apps/web run lint
npm --prefix apps/web run build
git diff --check
```

Expected: every command exits 0.

- [ ] **Step 5: Commit Task 6**

Run:

```powershell
git add apps/api/app/evaluation/golden.py apps/api/tests/evaluation/test_golden_eval.py apps/web/tests/evaluation-summary.test.tsx docs/superpowers/plans/2026-09-01-ocr-ingestion-reliability.md
git commit -m "test: add ocr ingestion evaluation coverage"
```
