import importlib.util
from pathlib import Path

import pytest
import httpx

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("load_demo", ROOT / "load_demo.py")
demo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(demo)


@pytest.mark.parametrize("url", ["http://localhost:8000", "https://example.com", "http://127.0.0.1:8001/search", "http://user:secret@127.0.0.1:8001"])
def test_rejects_non_demo_target(url):
    with pytest.raises(ValueError):
        demo.validate_api_url(url)


def test_accepts_explicit_isolated_target():
    assert demo.validate_api_url("http://127.0.0.1:8001/") == "http://127.0.0.1:8001"


def test_cases_are_drafts_with_coverage():
    data = demo.read_cases()
    assert data["review_status"] == "draft"
    assert len(data["cases"]) == 25
    assert len({case["document"] for case in data["cases"]}) == 6
    assert not any("review_state" in case or "reviewed_at" in case for case in data["cases"])
    assert {"table", "ocr", "multi-part", "abstention"} <= {tag for case in data["cases"] for tag in case["tags"]}


def test_refuses_workspace_with_non_allowlisted_uploads():
    with pytest.raises(ValueError, match="outside the demo allowlist"):
        demo.validate_workspace([{"filename": "personal.pdf"}], {"sample-invoice.pdf"})


def test_receipt_source_is_not_in_upload_allowlist():
    assert "sample-receipt-source.pdf" not in demo.UPLOAD_FILES
    assert "sample-receipt.png" in demo.UPLOAD_FILES


def test_refuses_duplicate_demo_filenames():
    with pytest.raises(ValueError, match="Duplicate"):
        demo.validate_workspace([{"filename": "sample-resume.pdf"}, {"filename": "sample-resume.pdf"}])


def test_substituted_existing_file_is_rejected_before_any_write(monkeypatch):
    calls = []
    catalog = demo.json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    invoice_hash = next(item["sha256"] for item in catalog["documents"] if item["file"] == "sample-invoice.pdf")

    def handler(request):
        calls.append(request.method)
        assert request.method == "GET", "No writes are permitted before existing files are verified"
        if request.url.path == "/health":
            payload = {"service": "DocIntel AI Demo API"}
        elif request.url.path == "/documents":
            payload = [{"id": "invoice", "filename": "sample-invoice.pdf"}, {"id": "resume", "filename": "sample-resume.pdf"}]
        elif request.url.path == "/documents/invoice/checksum":
            payload = {"sha256": invoice_hash}
        elif request.url.path == "/documents/resume/checksum":
            payload = {"sha256": "0" * 64}
        else:
            raise AssertionError(request.url.path)
        return httpx.Response(200, json=payload)

    client = httpx.Client
    monkeypatch.setattr(demo.httpx, "Client", lambda **kwargs: client(**kwargs, transport=httpx.MockTransport(handler)))
    with pytest.raises(ValueError, match="Checksum mismatch"):
        demo.load_demo("http://127.0.0.1:8001")
    assert calls and set(calls) == {"GET"}
