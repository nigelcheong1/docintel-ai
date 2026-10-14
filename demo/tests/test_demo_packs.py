import importlib.util
import json
from pathlib import Path

import fitz
import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "00000000-0000-0000-0000-000000000001"


def module_at(name, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_unseen_pack_contains_eight_new_draft_questions_on_existing_documents():
    path = ROOT / "unseen-cases.json"
    assert path.is_file()
    pack = json.loads(path.read_text(encoding="utf-8"))
    original = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))

    assert pack["review_status"] == "draft"
    assert pack["suite_name"] != original["suite_name"]
    assert "not new-document generalization" in pack["notice"]
    assert len(pack["cases"]) == len({case["id"] for case in pack["cases"]}) == 8
    assert {case["document"] for case in pack["cases"]} <= {case["document"] for case in original["cases"]}
    assert not {case["question"] for case in pack["cases"]} & {case["question"] for case in original["cases"]}
    assert not any("review_state" in case or "reviewed_at" in case for case in pack["cases"])
    facts = {case["id"]: [fact["pattern"] for fact in case["facts"]] for case in pack["cases"]}
    assert facts == {
        "unseen-invoice-subtotal": ["USD 500.00"],
        "unseen-invoice-tax": ["USD 50.00"],
        "unseen-contract-fee": ["USD 500.00", "excluding tax"],
        "unseen-contract-term-end": ["31 December 2026"],
        "unseen-resume-university": ["Example University"],
        "unseen-receipt-payment": ["cash"],
        "unseen-receipt-number": ["DEMO-R-007"],
        "unseen-framework-password": [],
    }
    negative = next(case for case in pack["cases"] if case["id"] == "unseen-framework-password")
    assert negative["document"] == "nist-ai-rmf-1.0.pdf"
    assert negative["expected_outcome"] == "insufficient_evidence"
    assert negative["anchors"] == []
    assert "administrator password" in negative["question"]
    assert all(case["expected_outcome"] == "answerable" for case in pack["cases"] if case is not negative)


def test_unseen_positive_anchors_match_static_safe_sources():
    path = ROOT / "unseen-cases.json"
    assert path.is_file()
    pack = json.loads(path.read_text(encoding="utf-8"))
    for case in pack["cases"]:
        if case["expected_outcome"] != "answerable":
            continue
        source = "sample-receipt-source.pdf" if case["document"] == "sample-receipt.png" else case["document"]
        with fitz.open(ROOT / "documents" / source) as document:
            assert case["anchors"]
            for anchor in case["anchors"]:
                text = " ".join(document[anchor["page_number"] - 1].get_text().split())
                assert anchor["quote"] in text
            for fact in case["facts"]:
                assert any(fact["pattern"] in anchor["quote"] for anchor in case["anchors"])


def test_case_pack_choices_default_to_original_and_accept_only_fixed_names(monkeypatch):
    demo = module_at("load_demo", monkeypatch)
    assert demo.parse_args([]).case_pack == "cases.json"
    assert demo.parse_args(["--case-pack", "unseen-cases.json"]).case_pack == "unseen-cases.json"
    assert len(demo.read_cases()["cases"]) == 25
    assert len(demo.read_cases("unseen-cases.json")["cases"]) == 8


@pytest.mark.parametrize("case_pack", ["../cases.json", "/tmp/private.json", "personal.json"])
def test_case_pack_paths_are_rejected_at_cli_and_programmatic_boundaries(monkeypatch, case_pack):
    demo = module_at("load_demo", monkeypatch)
    with pytest.raises(SystemExit) as error:
        demo.parse_args(["--case-pack", case_pack])
    assert error.value.code == 2
    with pytest.raises(ValueError, match="case pack"):
        demo.read_cases(case_pack)


@pytest.mark.parametrize("case_pack", ["cases.json", "unseen-cases.json"])
@pytest.mark.parametrize("violation", ["review_status", "review_state", "reviewed_at", "document"])
def test_both_case_packs_reject_review_labels_and_private_sources(monkeypatch, tmp_path, case_pack, violation):
    demo = module_at("load_demo", monkeypatch)
    pack = {"review_status": "draft", "cases": [{"document": "sample-invoice.pdf"}]}
    if violation == "review_status":
        pack["review_status"] = "reviewed"
    else:
        pack["cases"][0][violation] = "private.pdf" if violation == "document" else "reviewed"
    (tmp_path / case_pack).write_text(json.dumps(pack), encoding="utf-8")
    monkeypatch.setattr(demo, "ROOT", tmp_path)
    with pytest.raises(ValueError):
        demo.read_cases(case_pack)


@pytest.mark.parametrize(
    ("case_pack", "suite_name", "count"),
    [
        ("cases.json", "Portfolio source-review candidates", 25),
        ("unseen-cases.json", "Portfolio unseen-question source-review candidates", 8),
    ],
)
def test_loader_selects_separate_suite_reports_dynamic_count_and_never_reviews(monkeypatch, capsys, case_pack, suite_name, count):
    demo = module_at("load_demo", monkeypatch)
    catalog = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    hashes = {entry["file"]: entry["sha256"] for entry in catalog["documents"]}
    documents = [{"id": filename, "filename": filename, "status": "indexed", "page_count": 1, "chunk_count": 1}
                 for filename in sorted(demo.UPLOAD_FILES)]
    posted_cases = []

    def handler(request):
        path = request.url.path
        if request.method == "GET" and path == "/health":
            payload = {"service": "DocIntel AI Demo API"}
        elif request.method == "GET" and path == "/documents":
            payload = documents
        elif request.method == "GET" and path.endswith("/checksum"):
            payload = {"sha256": hashes[path.split("/")[-2]]}
        elif request.method == "GET" and path.startswith("/documents/"):
            payload = next(document for document in documents if document["id"] == path.split("/")[-1])
        elif request.method == "GET" and path == "/eval/document-suites":
            payload = []
        elif request.method == "POST" and path == "/eval/document-suites":
            assert json.loads(request.content) == {"name": suite_name}
            payload = {"id": "selected-suite"}
        elif request.method == "GET" and path == "/eval/document-suites/selected-suite":
            payload = {"cases": []}
        elif request.method == "POST" and path == "/eval/document-suites/selected-suite/cases":
            case = json.loads(request.content)
            assert case["document_id"] in demo.UPLOAD_FILES
            assert "review_state" not in case and "reviewed_at" not in case
            posted_cases.append(case)
            payload = {"id": f"candidate-{len(posted_cases)}"}
        else:
            raise AssertionError(f"Unexpected request: {request.method} {path}")
        return httpx.Response(200, json=payload)

    client = httpx.Client
    monkeypatch.setattr(demo.httpx, "Client", lambda **kwargs: client(**kwargs, transport=httpx.MockTransport(handler)))
    demo.load_demo("http://127.0.0.1:8001", case_pack=case_pack)
    assert len(posted_cases) == count
    assert f"Prepared {count} candidate cases. No cases were marked reviewed" in capsys.readouterr().out


def test_loader_cli_keeps_case_pack_workspace_files_separate(monkeypatch, tmp_path):
    demo = module_at("load_demo", monkeypatch)
    monkeypatch.setattr(demo, "ROOT", tmp_path)

    def load(api_url, timeout=300, case_pack="cases.json"):
        assert api_url == "http://127.0.0.1:8001"
        return {"api": api_url, "suite_id": case_pack, "documents": {}}

    monkeypatch.setattr(demo, "load_demo", load)
    demo.main([])
    original = (tmp_path / ".local/workspace.json").read_text(encoding="utf-8")
    demo.main(["--case-pack", "unseen-cases.json"])
    assert (tmp_path / ".local/workspace.json").read_text(encoding="utf-8") == original
    assert json.loads(original)["suite_id"] == "cases.json"
    assert json.loads((tmp_path / ".local/workspace-unseen.json").read_text(encoding="utf-8"))["suite_id"] == "unseen-cases.json"


def test_export_report_choices_and_destinations_are_fixed_without_running_export(monkeypatch):
    exporter = module_at("export_benchmark", monkeypatch)
    assert exporter.parse_args([RUN_ID]).report_kind == "baseline"
    assert exporter.parse_args([RUN_ID, "--report-kind", "hardening"]).report_kind == "hardening"
    assert exporter.report_destination() == ROOT.parent / "docs/demo/evaluation-baseline.json"
    assert exporter.report_destination("hardening") == ROOT.parent / "docs/demo/evaluation-hardening.json"


@pytest.mark.parametrize("report_kind", ["../private", "unseen", "evaluation-custom.json"])
def test_export_rejects_arbitrary_report_destinations(monkeypatch, report_kind):
    exporter = module_at("export_benchmark", monkeypatch)
    with pytest.raises(SystemExit) as error:
        exporter.parse_args([RUN_ID, "--report-kind", report_kind])
    assert error.value.code == 2
    with pytest.raises(ValueError, match="report kind"):
        exporter.report_destination(report_kind)


@pytest.mark.parametrize("report_kind", ["baseline", "hardening"])
def test_export_review_and_allowlist_guards_apply_to_both_report_kinds(monkeypatch, report_kind):
    exporter = module_at("export_benchmark", monkeypatch)
    with pytest.raises(ValueError, match="completed"):
        exporter.public_report({"status": "running", "total_cases": 1}, [], report_kind=report_kind)
    with pytest.raises(ValueError, match="outside the demo allowlist"):
        exporter.public_report({"status": "completed", "total_cases": 1},
                               [{"case_snapshot": {"document_filename": "private.pdf"}}], report_kind=report_kind)
    with pytest.raises(ValueError, match="human-reviewed"):
        exporter.public_report({"status": "completed", "total_cases": 1},
                               [{"case_snapshot": {"document_filename": "sample-invoice.pdf", "review_state": "draft"}}],
                               report_kind=report_kind)


def test_hardening_note_describes_committed_code_and_keeps_run_revision(monkeypatch):
    exporter = module_at("export_benchmark", monkeypatch)
    run = {
        "status": "completed", "total_cases": 1, "started_at": "2026-10-14T00:00:00Z",
        "finished_at": "2026-10-14T00:00:01Z", "pipeline_config": {"revision": "evaluated-commit"},
        "passed_count": 1, "failed_count": 0, "error_count": 0, "unavailable_count": 0,
        "mode_counts": {"lexical": 1}, "fallback_count": 0, "measurements": {},
    }
    result = {
        "case_snapshot": {
            "document_filename": "sample-invoice.pdf", "question": "What is the subtotal?",
            "expected_outcome": "answerable", "facts": [{"pattern": "USD 500.00", "alternatives": []}],
            "anchors": [{"page_number": 1, "quote": "Subtotal: USD 500.00."}], "tags": ["fictional"],
            "review_state": "reviewed", "reviewed_at": "2026-10-14T00:00:00Z",
        },
        "case_version": 1, "status": "pass", "failure_reasons": [], "measurements": {}, "human_assessment": None,
        "execution_snapshot": {"response": {"answer": {"summary": "USD 500.00", "citations": []}}},
    }
    baseline = exporter.public_report(run, [result])
    hardening = exporter.public_report(run, [result], report_kind="hardening")
    assert baseline["implementation_note"] == (
        "Recorded on the portfolio-v1 working tree; pipeline revision identifies its base HEAD, not uncommitted changes."
    )
    assert hardening["implementation_note"] == (
        "Recorded after committed answer-quality hardening; pipeline_config.revision identifies the evaluated commit."
    )
    assert hardening["pipeline_config"] == {"revision": "evaluated-commit"}
    assert hardening["cases"] == baseline["cases"]
