import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.documents import router
from app.main import create_app


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
