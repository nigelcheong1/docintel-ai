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
