from app.db.session import SessionLocal


def test_request_sessions_keep_committed_attributes_loaded():
    assert SessionLocal.kw["expire_on_commit"] is False
