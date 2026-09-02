from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.core.config import Settings, get_settings
from app.db.models import Document, DocumentStatus
from app.db.session import get_db
from app.documents import router
from app.documents.ocr import OcrPageResult
from app.documents.service import index_stored_upload
from app.documents.storage import save_upload_bytes
from app.main import create_app
from app.retrieval.embeddings import FakeEmbeddingProvider


def create_pdf_bytes(path: Path, text: str) -> bytes:
    import fitz

    pdf = fitz.open()
    page = pdf.new_page()
    page.insert_text((72, 72), text)
    pdf.save(path)
    pdf.close()
    return path.read_bytes()


def create_image_bytes(path: Path) -> bytes:
    Image.new("RGB", (120, 60), "white").save(path)
    return path.read_bytes()


class FakeOcrProvider:
    engine_name = "fake-ocr"

    def __init__(self, available: bool = True, text: str = "OCR searchable content from scanned document") -> None:
        self.available = available
        self.text = text

    def is_available(self) -> bool:
        return self.available

    def ocr_image(self, image: Image.Image, *, language: str) -> OcrPageResult:
        return OcrPageResult(text=self.text, confidence=88.0, engine_name=self.engine_name, duration_ms=5)


def test_embedding_provider_is_cached_by_model_settings(monkeypatch):
    created = []

    class StubEmbeddingProvider:
        def __init__(self, model_name: str, dimension: int) -> None:
            created.append((model_name, dimension))

    monkeypatch.setattr(router, "LocalEmbeddingProvider", StubEmbeddingProvider)
    router.get_cached_embedding_provider.cache_clear()

    try:
        first = router.get_cached_embedding_provider("BAAI/bge-small-en-v1.5", 384)
        second = router.get_cached_embedding_provider("BAAI/bge-small-en-v1.5", 384)
    finally:
        router.get_cached_embedding_provider.cache_clear()

    assert first is second
    assert created == [("BAAI/bge-small-en-v1.5", 384)]


@pytest.mark.integration
def test_document_read_endpoints_include_parse_quality(db_session, tmp_path):
    stored = save_upload_bytes(
        "invoice.pdf",
        "application/pdf",
        create_pdf_bytes(tmp_path / "invoice.pdf", "Invoice total due is RM 1,200.00 " * 20),
        tmp_path / "storage",
        20,
    )
    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())
    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    list_response = client.get("/documents")
    detail_response = client.get(f"/documents/{document.id}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    assert list_response.json()[0]["parse_quality"]["scanned_likelihood"] == "low"
    assert "ocr_page_count" in list_response.json()[0]["parse_quality"]
    assert detail_response.json()["parse_quality"]["page_count"] == 1
    assert "text_source_summary" in detail_response.json()["parse_quality"]


@pytest.mark.integration
def test_image_upload_indexes_image_when_ocr_is_available(db_session, tmp_path):
    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: Settings(storage_dir=tmp_path / "storage")
    app.dependency_overrides[router.get_embedding_provider_factory] = lambda: lambda: FakeEmbeddingProvider()
    app.dependency_overrides[router.get_ocr_provider_factory] = lambda: lambda: FakeOcrProvider()
    client = TestClient(app)

    response = client.post(
        "/documents",
        files={"file": ("scan.png", create_image_bytes(tmp_path / "scan.png"), "image/png")},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "indexed"


@pytest.mark.integration
def test_image_upload_defers_ocr_without_initializing_embedding_provider(db_session, tmp_path):
    app = create_app()

    def override_db():
        yield db_session

    def unexpected_provider_factory():
        def unexpected_provider():
            raise AssertionError("image uploads must not initialize an embedding provider")

        return unexpected_provider

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: Settings(storage_dir=tmp_path / "storage")
    app.dependency_overrides[router.get_embedding_provider_factory] = unexpected_provider_factory
    app.dependency_overrides[router.get_ocr_provider_factory] = lambda: lambda: FakeOcrProvider(available=False)
    client = TestClient(app)

    response = client.post("/documents", files={"file": ("scan.png", b"image-bytes", "image/png")})

    assert response.status_code == 200
    assert response.json()["status"] == "deferred_ocr"


@pytest.mark.integration
def test_oversized_upload_returns_413_and_removes_partial_file(db_session, tmp_path):
    storage_dir = tmp_path / "storage"
    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_settings] = lambda: Settings(storage_dir=storage_dir, max_upload_mb=1)
    client = TestClient(app)

    response = client.post(
        "/documents",
        files={"file": ("large.pdf", b"x" * (1024 * 1024 + 1), "application/pdf")},
    )

    assert response.status_code == 413
    assert list(storage_dir.glob("*")) == []


@pytest.mark.integration
def test_delete_document_endpoint_removes_document_and_stored_file(db_session, tmp_path):
    stored = save_upload_bytes("scan.png", "image/png", b"image-bytes", tmp_path / "storage", 20)
    document = index_stored_upload(db_session, stored, None)
    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    response = client.delete(f"/documents/{document.id}")

    assert response.status_code == 204
    assert db_session.get(Document, document.id) is None
    assert not stored.file_path.exists()


@pytest.mark.integration
def test_delete_document_endpoint_surfaces_file_removal_failure(db_session, tmp_path, monkeypatch):
    stored = save_upload_bytes("scan.png", "image/png", b"image-bytes", tmp_path / "storage", 20)
    document = index_stored_upload(db_session, stored, None)
    app = create_app()

    def override_db():
        yield db_session

    def fail_unlink(self, missing_ok=False):
        raise OSError("storage is unavailable")

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(Path, "unlink", fail_unlink)
    client = TestClient(app)

    response = client.delete(f"/documents/{document.id}")

    assert response.status_code == 503
    assert response.json()["detail"] == "Could not remove the document file."
    assert db_session.get(Document, document.id) is not None
    assert stored.file_path.exists()


@pytest.mark.integration
def test_reindex_document_endpoint_returns_reindexed_document(db_session, tmp_path):
    original_pdf = tmp_path / "original.pdf"
    stored = save_upload_bytes(
        "resume.pdf",
        "application/pdf",
        create_pdf_bytes(original_pdf, "Reindex endpoint fixture contains searchable PDF text for testing."),
        tmp_path / "storage",
        20,
    )
    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())
    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[router.get_embedding_provider_factory] = lambda: lambda: FakeEmbeddingProvider()
    client = TestClient(app)

    response = client.post(f"/documents/{document.id}/reindex")

    assert response.status_code == 200
    assert response.json()["id"] == document.id
    assert response.json()["status"] == DocumentStatus.INDEXED.value


@pytest.mark.integration
def test_reindex_document_endpoint_surfaces_failure_and_preserves_prior_index(db_session, tmp_path):
    original_pdf = tmp_path / "original.pdf"
    stored = save_upload_bytes(
        "resume.pdf",
        "application/pdf",
        create_pdf_bytes(original_pdf, "Original searchable content includes enough useful PDF words for reindexing."),
        tmp_path / "storage",
        20,
    )
    document = index_stored_upload(db_session, stored, lambda: FakeEmbeddingProvider())
    old_chunk_ids = [chunk.id for chunk in document.chunks]
    app = create_app()

    def override_db():
        yield db_session

    def failing_embedder():
        raise RuntimeError("local model could not be loaded")

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[router.get_embedding_provider_factory] = lambda: failing_embedder
    client = TestClient(app)

    response = client.post(f"/documents/{document.id}/reindex")

    assert response.status_code == 400
    assert response.json()["detail"] == "Indexing failed: local model could not be loaded"
    db_session.expire_all()
    persisted = db_session.get(Document, document.id)
    assert persisted is not None
    assert persisted.status == DocumentStatus.INDEXED
    assert [chunk.id for chunk in persisted.chunks] == old_chunk_ids


@pytest.mark.integration
def test_reindex_document_endpoint_accepts_images_when_ocr_is_available(db_session, tmp_path):
    stored = save_upload_bytes(
        "scan.png",
        "image/png",
        create_image_bytes(tmp_path / "scan.png"),
        tmp_path / "storage",
        20,
    )
    document = index_stored_upload(
        db_session,
        stored,
        lambda: FakeEmbeddingProvider(),
        ocr_provider_factory=lambda: FakeOcrProvider(available=False),
    )
    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[router.get_embedding_provider_factory] = lambda: lambda: FakeEmbeddingProvider()
    app.dependency_overrides[router.get_ocr_provider_factory] = lambda: lambda: FakeOcrProvider()
    client = TestClient(app)

    response = client.post(f"/documents/{document.id}/reindex")

    assert response.status_code == 200
    assert response.json()["status"] == DocumentStatus.INDEXED.value


@pytest.mark.integration
def test_document_action_endpoints_return_404_for_unknown_document(db_session):
    app = create_app()

    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    assert client.delete("/documents/00000000-0000-0000-0000-000000000000").status_code == 404
    assert client.post("/documents/00000000-0000-0000-0000-000000000000/reindex").status_code == 404
