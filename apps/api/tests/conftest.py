import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.db.models import Base


def get_test_database_url() -> str:
    database_url = os.environ.get("DOCINTEL_TEST_DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError(
            "DOCINTEL_TEST_DATABASE_URL is required for integration tests; "
            "configure a disposable PostgreSQL database such as docintel_test."
        )

    parsed_url = make_url(database_url)
    database_name = (parsed_url.database or "").lower()
    if parsed_url.get_backend_name() != "postgresql" or "test" not in database_name or database_name == "docintel":
        raise RuntimeError(
            "DOCINTEL_TEST_DATABASE_URL must target a dedicated test database on PostgreSQL; "
            "the development database name 'docintel' is never allowed."
        )
    return database_url


@pytest.fixture()
def db_session():
    database_url = get_test_database_url()
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
