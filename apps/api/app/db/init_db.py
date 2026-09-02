from app.db.models import Base, DocumentStatus
from app.db.session import engine
from sqlalchemy import Engine, inspect, text


def _ddl_type(bind: Engine, logical_type: str) -> str:
    if bind.dialect.name == "sqlite":
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
    existing = {column["name"] for column in inspect(connection).get_columns(table_name)}
    if column_name not in existing:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {column_sql}"))


def document_status_enum_sync_sql() -> str:
    return f"ALTER TYPE document_status ADD VALUE IF NOT EXISTS '{DocumentStatus.OCR_PROCESSING.value}'"


def sync_local_schema(bind: Engine) -> None:
    table_names = set(inspect(bind).get_table_names())
    if not {"documents", "pages"} <= table_names:
        return

    with bind.begin() as connection:
        if bind.dialect.name == "postgresql":
            connection.execute(text(document_status_enum_sync_sql()))
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


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    sync_local_schema(engine)
