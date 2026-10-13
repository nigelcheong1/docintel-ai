import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def module_at(name, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    spec = importlib.util.spec_from_file_location(name, ROOT / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_committed_media_and_scoped_baseline_exist(monkeypatch):
    video = module_at("build_walkthrough", monkeypatch)
    demo = module_at("load_demo", monkeypatch)
    demo.validate_files()
    for filename, _title, _caption in video.SCENES:
        image = ROOT.parent / "docs/demo/screenshots" / filename
        assert image.read_bytes().startswith(b"\xff\xd8\xff")
    assert (ROOT.parent / "docs/demo/walkthrough.mp4").stat().st_size > 0
    report = json.loads((ROOT.parent / "docs/demo/evaluation-baseline.json").read_text(encoding="utf-8"))
    assert report["total_cases"] == len(report["cases"]) == 25
    assert report["passed_count"] == sum(case["status"] == "pass" for case in report["cases"])
    assert report["failed_count"] == sum(case["status"] == "fail" for case in report["cases"])
    assert all(case["label_reviewed_at"] for case in report["cases"])
    assert all(case["human_result_assessment"] is None for case in report["cases"])
    assert {case["document"] for case in report["cases"]} == demo.UPLOAD_FILES
    assert report["measurements"]["abstention_match"]["denominator"] == 6


def test_export_rejects_incomplete_runs_and_non_allowlisted_sources(monkeypatch):
    exporter = module_at("export_benchmark", monkeypatch)
    with pytest.raises(ValueError, match="completed"):
        exporter.public_report({"status": "running", "total_cases": 1}, [])
    with pytest.raises(ValueError, match="outside the demo allowlist"):
        exporter.public_report({"status": "completed", "total_cases": 1}, [{"case_snapshot": {"document_filename": "private.pdf"}}])


def test_export_rejects_unreviewed_snapshots(monkeypatch):
    exporter = module_at("export_benchmark", monkeypatch)
    with pytest.raises(ValueError, match="human-reviewed"):
        exporter.public_report({"status": "completed", "total_cases": 1}, [{"case_snapshot": {
            "document_filename": "sample-invoice.pdf", "review_state": "draft",
        }}])


def test_export_allows_repeated_case_and_citation_document_references(monkeypatch):
    exporter = module_at("export_benchmark", monkeypatch)
    baseline = json.loads((ROOT.parent / "docs/demo/evaluation-baseline.json").read_text(encoding="utf-8"))
    results = []
    for case in baseline["cases"]:
        snapshot = {key: case[key] for key in ("question", "expected_outcome", "facts", "anchors", "tags")}
        snapshot.update(document_filename=case["document"], review_state="reviewed", reviewed_at=case["label_reviewed_at"])
        citations = [{"document_filename": citation["document"], "page_number": citation["page_number"]} for citation in case["citations"]]
        results.append({
            "case_snapshot": snapshot, "case_version": case["content_version"], "status": case["status"],
            "failure_reasons": case["failure_reasons"], "measurements": case["measurements"], "human_assessment": None,
            "execution_snapshot": {"raw_trace": "omitted", "response": {"answer": {"summary": case["answer"], "citations": citations + citations}}},
        })
    report = exporter.public_report({**baseline, "status": "completed"}, results)
    assert len(report["cases"]) == 25
    assert report["measurements"] == baseline["measurements"]
    assert len(report["cases"][0]["citations"]) == 2 * len(baseline["cases"][0]["citations"])
    assert "raw_trace" not in json.dumps(report)
