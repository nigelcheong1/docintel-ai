from types import SimpleNamespace

import pytest

from app.db.models import Chunk, Document, DocumentEvalCase, DocumentStatus, Page
from app.evaluation import document_cases as cases
from app.evaluation.document_cases import CaseReadiness


def test_line_wrapped_page_quote_resolves_in_existing_collapsed_chunks():
    page = Page(id="page", page_number=1, text="The multi-\nmodal approach uses visual inputs.")
    chunk = Chunk(id="chunk", chunk_index=0, text="The multi- modal approach uses visual inputs.")
    responses = iter([[page], [chunk]])
    db = SimpleNamespace(scalars=lambda _query: next(responses))
    case = DocumentEvalCase(document_id="doc", review_state="draft", anchors=[{"page_number": 1, "quote": "The multimodal approach uses visual inputs."}])
    readiness = cases._resolve_sources(db, case)
    assert readiness.availability == "ready"
    assert readiness.anchors[0].chunk_ids == ("chunk",)


@pytest.mark.parametrize("operation", ["readiness", "review"])
def test_legacy_relative_upload_path_uses_configured_storage(tmp_path, monkeypatch, operation):
    storage = tmp_path / "uploads"
    storage.mkdir()
    (storage / "legacy.pdf").touch()
    document = Document(id="doc", filename="legacy.pdf", stored_filename="legacy.pdf", file_path="storage/legacy.pdf", status=DocumentStatus.INDEXED)
    case = DocumentEvalCase(id="case", document_id="doc", question="What GPU?", expected_outcome="insufficient_evidence", facts=[], anchors=[], review_rationale="Checked the whole document.", review_state="draft", content_version=1)
    page = Page(page_number=1, text="A literature review.")
    scalar_results = iter([case, "chunk"])
    db = SimpleNamespace(get=lambda *_args: document, scalar=lambda _query: next(scalar_results), scalars=lambda _query: [page], commit=lambda: None, refresh=lambda _item: None)
    monkeypatch.setattr(cases, "get_settings", lambda: SimpleNamespace(storage_dir=storage), raising=False)
    monkeypatch.setattr(cases, "_resolve_sources", lambda *_args: CaseReadiness("ready"))
    if operation == "readiness":
        assert cases.check_case_readiness(db, case).availability == "draft"
    else:
        assert cases.review_case(db, case.id, 1).review_state == "reviewed"
