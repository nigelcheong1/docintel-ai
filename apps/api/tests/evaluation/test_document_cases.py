import pytest
from fastapi import HTTPException

from app.db.models import Chunk, Document, DocumentEvalSuite, DocumentStatus, Page
from app.evaluation.document_schemas import CaseWrite

pytestmark = pytest.mark.integration


def service():
    from app.evaluation import document_cases
    return document_cases


@pytest.fixture
def source(db_session, tmp_path):
    path = tmp_path / "source.pdf"
    path.touch()
    document = Document(filename="source.pdf", stored_filename="source.pdf", mime_type="application/pdf", file_path=str(path), status=DocumentStatus.INDEXED)
    page = Page(document=document, page_number=1, text="Scopus returned 2366 records. After removal, 2092 remained.")
    chunk = Chunk(document=document, page=page, chunk_index=0, text=page.text)
    suite = DocumentEvalSuite(name="Counts")
    db_session.add_all([document, page, chunk, suite])
    db_session.commit()
    return document, page, chunk, suite


def data(source, **updates):
    values = dict(document_id=source[0].id, question="How many Scopus records?", expected_outcome="answerable", facts=[{"pattern": "Scopus returned 2366"}], anchors=[{"page_number": 1, "quote": "Scopus returned 2366 records."}])
    values.update(updates)
    return CaseWrite(**values)


def reviewed(db_session, source, **updates):
    case = service().create_case(db_session, source[3].id, data(source, **updates))
    return service().review_case(db_session, case.id, 1)


def test_case_starts_draft_and_edit_invalidates_review(db_session, source):
    case = service().create_case(db_session, source[3].id, data(source))
    assert case.review_state == "draft"
    assert service().check_case_readiness(db_session, case).availability == "draft"
    service().review_case(db_session, case.id, 1)
    service().update_case(db_session, case.id, data(source, question="What was the count?"))
    assert case.content_version == 2
    assert case.review_state == "draft"
    assert case.reviewed_at is None
    assert case.review_page_hashes == {}


def test_review_old_version_conflicts(db_session, source):
    case = service().create_case(db_session, source[3].id, data(source))
    with pytest.raises(HTTPException) as error:
        service().review_case(db_session, case.id, 2)
    assert error.value.status_code == 409


@pytest.mark.parametrize("updates", [{"facts": []}, {"anchors": []}, {"expected_outcome": "insufficient_evidence", "facts": [], "anchors": [], "review_rationale": " "}, {"expected_outcome": "insufficient_evidence", "review_rationale": "Reviewed scope."}])
def test_review_requires_valid_expectations(db_session, source, updates):
    case = service().create_case(db_session, source[3].id, data(source, **updates))
    with pytest.raises(HTTPException) as error:
        service().review_case(db_session, case.id, 1)
    assert error.value.status_code == 422
    assert case.review_state == "draft"


def test_unchanged_reindex_reresolves_new_chunk_ids(db_session, source):
    case = reviewed(db_session, source)
    old_id = source[2].id
    db_session.delete(source[2])
    db_session.flush()
    replacement = Chunk(document_id=source[0].id, page_id=source[1].id, chunk_index=0, text=source[1].text)
    db_session.add(replacement)
    db_session.commit()
    readiness = service().check_case_readiness(db_session, case)
    assert readiness.availability == "ready"
    assert readiness.anchors[0].chunk_ids == (replacement.id,)
    assert old_id != replacement.id


def test_anchor_crosses_adjacent_chunk_boundary(db_session, source):
    source[2].text = "Scopus returned"
    second = Chunk(document_id=source[0].id, page_id=source[1].id, chunk_index=1, text="2366 records. After removal, 2092 remained.")
    db_session.add(second)
    db_session.commit()
    case = reviewed(db_session, source)
    assert service().check_case_readiness(db_session, case).anchors[0].chunk_ids == (source[2].id, second.id)


@pytest.mark.parametrize("change", ["modify", "remove"])
def test_changed_or_removed_page_requires_review(db_session, source, change):
    case = reviewed(db_session, source)
    if change == "modify":
        source[1].text += " Another sentence."
    else:
        db_session.delete(source[1])
    db_session.commit()
    assert service().check_case_readiness(db_session, case).availability == "stale"


def test_negative_scope_change_requires_review(db_session, source):
    case = reviewed(db_session, source, expected_outcome="insufficient_evidence", question="What GPU was used?", facts=[], anchors=[], review_rationale="Entire document reviewed; it describes literature screening, not computation hardware.")
    assert service().check_case_readiness(db_session, case).availability == "ready"
    db_session.add(Page(document_id=source[0].id, page_number=2, text="Additional scope."))
    db_session.commit()
    assert service().check_case_readiness(db_session, case).availability == "stale"


def test_missing_file_is_unavailable(db_session, source):
    case = reviewed(db_session, source)
    source[0].file_path = "not-a-real-file.pdf"
    db_session.commit()
    assert service().check_case_readiness(db_session, case).availability == "unavailable"


def test_unresolved_quote_rejects_review(db_session, source):
    case = service().create_case(db_session, source[3].id, data(source, anchors=[{"page_number": 1, "quote": "Not in this document"}]))
    with pytest.raises(HTTPException) as error:
        service().review_case(db_session, case.id, 1)
    assert error.value.status_code == 409
