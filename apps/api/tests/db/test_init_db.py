from sqlalchemy import create_engine, inspect, text

from app.db.init_db import document_status_enum_sync_sql, sync_local_schema


def test_document_status_enum_sync_adds_ocr_processing():
    assert document_status_enum_sync_sql() == "ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'ocr_processing'"


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
