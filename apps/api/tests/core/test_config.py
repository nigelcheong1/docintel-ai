from pathlib import Path

from app.core.config import Settings


def test_settings_have_local_only_defaults():
    settings = Settings()
    expected_storage_dir = Path(__file__).resolve().parents[2] / "storage"

    assert settings.app_name == "DocIntel AI API"
    assert settings.embedding_model_name == "BAAI/bge-small-en-v1.5"
    assert settings.embedding_dimension == 384
    assert settings.storage_dir == expected_storage_dir
    assert "localhost:5432/docintel" in settings.database_url


def test_relative_storage_dir_is_api_root_relative():
    settings = Settings(storage_dir=Path("custom-storage"))
    expected_storage_dir = Path(__file__).resolve().parents[2] / "custom-storage"

    assert settings.storage_dir == expected_storage_dir


def test_ocr_settings_have_local_defaults(monkeypatch):
    monkeypatch.delenv("DOCINTEL_TESSERACT_CMD", raising=False)

    settings = Settings()

    assert settings.ocr_enabled is True
    assert settings.ocr_language == "eng"
    assert settings.ocr_dpi == 200
    assert settings.ocr_max_pages == 25
    assert settings.ocr_page_timeout_seconds == 20
    assert settings.tesseract_cmd is None
