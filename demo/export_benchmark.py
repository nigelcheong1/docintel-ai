"""Export scoped results from the isolated demo, without local IDs or raw traces."""

import argparse
import json
from pathlib import Path
from uuid import UUID

import httpx

from load_demo import ROOT, request, validate_api_url, validate_existing_files, validate_workspace


def public_report(run, results):
    if run["status"] != "completed" or len(results) != run["total_cases"]:
        raise ValueError("Only completed runs with all result records can be published.")
    validate_workspace([{"filename": name} for name in {item["case_snapshot"]["document_filename"] for item in results}])
    cases = []
    for item in results:
        case = item["case_snapshot"]
        if case["review_state"] != "reviewed":
            raise ValueError("Every published case must have a human-reviewed snapshot.")
        response = item["execution_snapshot"].get("response", {})
        answer = response.get("answer") or {}
        citations = answer.get("citations", [])
        validate_workspace([{"filename": name} for name in {citation["document_filename"] for citation in citations}])
        cases.append({
            "document": case["document_filename"], "question": case["question"],
            "expected_outcome": case["expected_outcome"], "facts": case["facts"],
            "anchors": case["anchors"], "tags": case["tags"],
            "content_version": item["case_version"], "label_reviewed_at": case["reviewed_at"],
            "status": item["status"], "answer": answer.get("summary"),
            "citations": [{"document": value["document_filename"], "page_number": value["page_number"]} for value in citations],
            "failure_reasons": item["failure_reasons"], "measurements": item["measurements"],
            "human_result_assessment": item["human_assessment"],
        })
    return {
        "scope": "Independently source-reviewed cases from public/fictional demo documents; not representative accuracy",
        "started_at": run["started_at"], "finished_at": run["finished_at"],
        "implementation_note": "Recorded on the portfolio-v1 working tree; pipeline revision identifies its base HEAD, not uncommitted changes.",
        "pipeline_config": run["pipeline_config"], "total_cases": run["total_cases"],
        "passed_count": run["passed_count"], "failed_count": run["failed_count"],
        "error_count": run["error_count"], "unavailable_count": run["unavailable_count"],
        "mode_counts": run["mode_counts"], "fallback_count": run["fallback_count"],
        "measurements": run["measurements"], "cases": cases,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", type=UUID)
    parser.add_argument("--api", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    with httpx.Client(base_url=validate_api_url(args.api), timeout=30) as client:
        if request(client, "GET", "/health").get("service") != "DocIntel AI Demo API":
            raise ValueError("Refusing a non-demo workspace.")
        validate_existing_files(client, request(client, "GET", "/documents"))
        run = request(client, "GET", f"/eval/document-runs/{args.run_id}")
        results = request(client, "GET", f"/eval/document-runs/{args.run_id}/results")
    destination = ROOT.parent / "docs/demo/evaluation-baseline.json"
    destination.write_text(json.dumps(public_report(run, results), indent=2) + "\n", encoding="utf-8")
    print(f"Exported {len(results)} scoped results to {destination}")


if __name__ == "__main__":
    main()
