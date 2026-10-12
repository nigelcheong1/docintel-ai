import pytest
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError

from app.db import models
from app.db.init_db import sync_local_schema


def schema():
    from app.evaluation import document_schemas
    return document_schemas


@pytest.mark.integration
def test_schema_sync_preserves_existing_uploads(db_session):
    document = models.Document(filename="keep.pdf", stored_filename="keep.pdf", mime_type="application/pdf", file_path="keep.pdf")
    page = models.Page(document=document, page_number=1, text="Keep this evidence.")
    chunk = models.Chunk(document=document, page=page, chunk_index=0, text=page.text)
    db_session.add_all([document, page, chunk])
    db_session.commit()
    sync_local_schema(db_session.get_bind())
    assert db_session.get(models.Chunk, chunk.id).text == "Keep this evidence."
    suite = models.DocumentEvalSuite(name="Uploaded documents")
    db_session.add(suite)
    db_session.commit()
    assert suite.id


@pytest.mark.integration
def test_document_delete_retains_case_and_run_snapshots(db_session):
    suite = models.DocumentEvalSuite(name="Sources")
    document = models.Document(filename="keep.pdf", stored_filename="keep.pdf", mime_type="application/pdf", file_path="keep.pdf")
    db_session.add_all([suite, document])
    db_session.flush()
    case = models.DocumentEvalCase(suite_id=suite.id, document_id=document.id, document_filename="keep.pdf", question="What is stated?", expected_outcome="answerable")
    run = models.DocumentEvalRun(suite_id=suite.id, status="completed", suite_snapshot={"name": "Sources"})
    db_session.add_all([case, run])
    db_session.flush()
    result = models.DocumentEvalResult(run_id=run.id, case_id_snapshot=case.id, case_version=1, case_snapshot={"question": "What is stated?"}, status="pass", duration_ms=1)
    db_session.add(result)
    db_session.commit()
    db_session.delete(document)
    db_session.commit()
    db_session.expire_all()
    assert db_session.get(models.DocumentEvalCase, case.id).document_id is None
    assert db_session.get(models.DocumentEvalResult, result.id).case_snapshot["question"] == "What is stated?"
    db_session.delete(suite)
    db_session.commit()
    db_session.expire_all()
    assert db_session.get(models.DocumentEvalRun, run.id).suite_id is None
    assert db_session.get(models.DocumentEvalResult, result.id) is not None


@pytest.mark.integration
def test_only_one_active_slot(db_session):
    db_session.add(models.DocumentEvalRun(status="queued", active_slot=1))
    db_session.commit()
    db_session.add(models.DocumentEvalRun(status="running", active_slot=1))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()
    db_session.add_all([models.DocumentEvalRun(status="completed"), models.DocumentEvalRun(status="cancelled")])
    db_session.commit()


@pytest.mark.parametrize("question", [" ", "x" * 2001])
def test_case_question_limits(question):
    with pytest.raises(ValidationError):
        schema().CaseWrite(document_id="11111111-1111-1111-1111-111111111111", question=question, expected_outcome="answerable")


@pytest.mark.parametrize("name", ["", " ", "x" * 121])
def test_suite_name_limits(name):
    with pytest.raises(ValidationError):
        schema().SuiteWrite(name=name)


def test_bounded_facts_quotes_and_tags():
    with pytest.raises(ValidationError):
        schema().ExpectedFact(pattern=" ")
    with pytest.raises(ValidationError):
        schema().EvidenceAnchor(page_number=0, quote="Source")
    with pytest.raises(ValidationError):
        schema().EvidenceAnchor(page_number=1, quote="x" * 4001)
    with pytest.raises(ValidationError):
        schema().CaseWrite(document_id="11111111-1111-1111-1111-111111111111", question="Question?", expected_outcome="answerable", tags=["x"] * 11)


def test_measurement_contract_preserves_null():
    measurement = schema().Measurement(value=None, numerator=0, denominator=0, unit="ratio", scope="reviewed anchors")
    assert measurement.model_dump()["value"] is None
