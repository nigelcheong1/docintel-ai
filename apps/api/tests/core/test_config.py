from pathlib import Path

from app.core.config import Settings


def test_settings_have_local_only_defaults():
    settings = Settings()

    assert settings.app_name == "DocIntel AI API"
    assert settings.embedding_model_name == "BAAI/bge-small-en-v1.5"
    assert settings.embedding_dimension == 384
    assert settings.storage_dir == Path("storage")
    assert "localhost:5432/docintel" in settings.database_url
