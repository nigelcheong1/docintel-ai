import pytest
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import sessionmaker

from app.db.models import Chunk, Document, DocumentEvalCase, DocumentEvalResult, DocumentEvalRun, DocumentEvalSuite, DocumentStatus, Page
from app.evaluation.document_cases import create_case, review_case, update_case
from app.evaluation.document_schemas import CaseWrite

pytestmark = pytest.mark.integration


def service():
    from app.evaluation import document_runs
    return document_runs


class BrokenEmbedder:
    def embed_texts(self, texts):
        raise RuntimeError("Test provider unavailable")


@pytest.fixture
def source(db_session, tmp_path):
    path = tmp_path / "source.pdf"
    path.touch()
    document = Document(filename="source.pdf", stored_filename="source.pdf", mime_type="application/pdf", file_path=str(path), status=DocumentStatus.INDEXED)
    page = Page(document=document, page_number=1, text="From Scopus, an aggregate of 2366 results were obtained.")
    chunk = Chunk(document=document, page=page, chunk_index=0, text=page.text)
    suite = DocumentEvalSuite(name="Counts")
    db_session.add_all([document, page, chunk, suite])
    db_session.commit()
    return document, suite, sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)


def add_case(db, source, *, negative=False, reviewed=True):
    data = CaseWrite(document_id=source[0].id, question="What private GPU cluster was used?" if negative else "How many results were initially obtained from Scopus?", expected_outcome="insufficient_evidence" if negative else "answerable", facts=[] if negative else [{"pattern": "From Scopus, an aggregate of 2366 results were obtained"}], anchors=[] if negative else [{"page_number": 1, "quote": "From Scopus, an aggregate of 2366 results were obtained."}], review_rationale="Reviewed complete document; it contains literature screening, not GPU hardware." if negative else "")
    case = create_case(db, source[1].id, data)
    return review_case(db, case.id, case.content_version) if reviewed else case


def run_results(db, run):
    db.expire_all()
    return list(db.scalars(select(DocumentEvalResult).where(DocumentEvalResult.run_id == run.id)))


def test_drafts_excluded_and_snapshots_immutable(db_session, source):
    case = add_case(db_session, source)
    add_case(db_session, source, reviewed=False)
    run = service().create_document_run(db_session, source[1].id, {"embedding_model": "local"})
    assert run.total_cases == 1
    update_case(db_session, case.id, CaseWrite(document_id=source[0].id, question="Changed later?", expected_outcome="answerable"))
    service().execute_document_run(run.id, source[2], lambda: BrokenEmbedder())
    result = run_results(db_session, run)[0]
    assert result.case_snapshot["question"] == "How many results were initially obtained from Scopus?"
    assert result.case_version == 1
    assert result.execution_snapshot["response"]["query"] == "How many results were initially obtained from Scopus?"


def test_empty_or_oversized_reviewed_suite_rejected(db_session, source):
    with pytest.raises(HTTPException) as error:
        service().create_document_run(db_session, source[1].id, {})
    assert error.value.status_code == 422
    for index in range(101):
        db_session.add(DocumentEvalCase(suite_id=source[1].id, document_id=source[0].id, document_filename="source.pdf", question=f"Question {index}?", expected_outcome="insufficient_evidence", review_state="reviewed"))
    db_session.commit()
    with pytest.raises(HTTPException) as error:
        service().create_document_run(db_session, source[1].id, {})
    assert error.value.status_code == 422


def test_two_sessions_cannot_reserve_active_run(db_session, source):
    add_case(db_session, source)
    first = service().create_document_run(db_session, source[1].id, {})
    with source[2]() as second_db:
        with pytest.raises(HTTPException) as error:
            service().create_document_run(second_db, source[1].id, {})
        assert error.value.status_code == 409
    assert first.status == "queued"


def test_provider_fallback_records_lexical_mode(db_session, source):
    add_case(db_session, source)
    run = service().create_document_run(db_session, source[1].id, {})
    service().execute_document_run(run.id, source[2], lambda: BrokenEmbedder())
    results = run_results(db_session, run)
    assert results[0].status == "pass"
    assert results[0].execution_snapshot["response"]["retrieval_mode"] == "lexical"
    assert "Test provider unavailable" in results[0].execution_snapshot["response"]["retrieval_fallback_reason"]
    assert db_session.get(DocumentEvalRun, run.id).active_slot is None


def test_missing_file_is_unavailable_not_abstention(db_session, source):
    add_case(db_session, source, negative=True)
    run = service().create_document_run(db_session, source[1].id, {})
    source[0].file_path = "not-a-real-file.pdf"
    db_session.commit()
    service().execute_document_run(run.id, source[2], lambda: BrokenEmbedder())
    results = run_results(db_session, run)
    assert results[0].status == "unavailable"
    assert results[0].measurements == {}
    assert db_session.get(DocumentEvalRun, run.id).measurements["abstention_match"]["value"] is None


def test_worker_exception_is_error_not_negative_pass(db_session, source, monkeypatch):
    from app.retrieval import service as search_service
    add_case(db_session, source, negative=True)
    run = service().create_document_run(db_session, source[1].id, {})
    def fail(*_args, **_kwargs):
        raise RuntimeError("Request execution failed")
    monkeypatch.setattr(search_service, "execute_search", fail)
    service().execute_document_run(run.id, source[2], lambda: BrokenEmbedder())
    assert run_results(db_session, run)[0].status == "error"
    assert db_session.get(DocumentEvalRun, run.id).completed_cases == 1
    assert db_session.get(DocumentEvalRun, run.id).measurements["abstention_match"]["value"] is None


def test_cancel_keeps_finished_results(db_session, source, monkeypatch):
    from app.retrieval import service as search_service
    add_case(db_session, source)
    add_case(db_session, source, negative=True)
    run = service().create_document_run(db_session, source[1].id, {})
    original = search_service.execute_search
    def cancel_after_execution(*args, **kwargs):
        result = original(*args, **kwargs)
        with source[2]() as cancel_db:
            service().request_run_cancel(cancel_db, run.id)
        return result
    monkeypatch.setattr(search_service, "execute_search", cancel_after_execution)
    service().execute_document_run(run.id, source[2], lambda: BrokenEmbedder())
    assert len(run_results(db_session, run)) == 1
    assert db_session.get(DocumentEvalRun, run.id).status == "cancelled"
    assert db_session.get(DocumentEvalRun, run.id).completed_cases == 1


def test_startup_interrupts_without_rerun(db_session, source):
    add_case(db_session, source)
    run = service().create_document_run(db_session, source[1].id, {})
    assert service().interrupt_abandoned_runs(db_session) == 1
    assert db_session.get(DocumentEvalRun, run.id).status == "interrupted"
    assert db_session.get(DocumentEvalRun, run.id).active_slot is None
    assert run_results(db_session, run) == []
    assert service().interrupt_abandoned_runs(db_session) == 0


def test_removed_index_is_unavailable_not_negative_pass(db_session, source):
    add_case(db_session, source, negative=True)
    run = service().create_document_run(db_session, source[1].id, {})
    db_session.execute(delete(Chunk).where(Chunk.document_id == source[0].id))
    db_session.commit()
    service().execute_document_run(run.id, source[2], lambda: BrokenEmbedder())
    assert run_results(db_session, run)[0].status == "unavailable"


def test_changed_source_is_unavailable(db_session, source):
    add_case(db_session, source)
    run = service().create_document_run(db_session, source[1].id, {})
    page = db_session.scalar(select(Page).where(Page.document_id == source[0].id))
    page.text = "Scopus count changed."
    db_session.commit()
    service().execute_document_run(run.id, source[2], lambda: BrokenEmbedder())
    assert run_results(db_session, run)[0].status == "unavailable"
