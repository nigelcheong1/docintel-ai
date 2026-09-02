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
    ocr_enabled: bool = True
    ocr_language: str = "eng"
    ocr_dpi: int = 200
    ocr_max_pages: int = 25
    ocr_page_timeout_seconds: int = 20
    tesseract_cmd: str | None = None
    backend_cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001",
            "http://127.0.0.1:3001",
        ]
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
