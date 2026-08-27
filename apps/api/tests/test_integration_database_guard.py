import pytest

import conftest


def test_test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DOCINTEL_TEST_DATABASE_URL", raising=False)
    get_test_database_url = getattr(conftest, "get_test_database_url", None)

    assert get_test_database_url is not None, "integration database guard is missing"
    with pytest.raises(RuntimeError, match="DOCINTEL_TEST_DATABASE_URL is required"):
        get_test_database_url()


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://docintel:docintel@localhost:5432/docintel",
        "postgresql+psycopg://other:secret@localhost:5432/docintel",
    ],
)
def test_development_database_name_is_rejected(monkeypatch, database_url):
    monkeypatch.setenv("DOCINTEL_TEST_DATABASE_URL", database_url)
    get_test_database_url = getattr(conftest, "get_test_database_url", None)

    assert get_test_database_url is not None, "integration database guard is missing"
    with pytest.raises(RuntimeError, match="dedicated test database"):
        get_test_database_url()


def test_dedicated_test_database_url_is_accepted(monkeypatch):
    database_url = "postgresql+psycopg://docintel:docintel@localhost:5432/docintel_test"
    monkeypatch.setenv("DOCINTEL_TEST_DATABASE_URL", database_url)
    get_test_database_url = getattr(conftest, "get_test_database_url", None)

    assert get_test_database_url is not None, "integration database guard is missing"
    assert get_test_database_url() == database_url
