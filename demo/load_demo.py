"""Load only the public demo allowlist into an explicitly isolated workspace."""

import argparse
import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx

ROOT = Path(__file__).resolve().parent
UPLOAD_FILES = frozenset({"colpali-paper.pdf", "nist-ai-rmf-1.0.pdf",
    "sample-invoice.pdf", "sample-contract.pdf", "sample-resume.pdf", "sample-receipt.png"})


def validate_api_url(url):
    parsed = urlsplit(url)
    if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}
        or parsed.port != 8001 or parsed.username or parsed.password
        or parsed.path not in {"", "/"} or parsed.query or parsed.fragment):
        raise ValueError("Use the isolated demo API on localhost port 8001, never the personal workspace API.")
    return url.rstrip("/")


def validate_workspace(documents, allowlist=UPLOAD_FILES):
    if any(document["filename"] not in allowlist for document in documents):
        raise ValueError("Target workspace contains documents outside the demo allowlist; refusing to load or capture it.")
    names = [document["filename"] for document in documents]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate demo filenames; refusing ambiguous source reuse.")


def read_cases():
    data = json.loads((ROOT / "cases.json").read_text(encoding="utf-8"))
    if data.get("review_status") != "draft":
        raise ValueError("Pack labels must remain draft pending human review.")
    if any(case["document"] not in UPLOAD_FILES or "review_state" in case or "reviewed_at" in case for case in data["cases"]):
        raise ValueError("Case pack contains a non-allowlisted document or an automatic review label.")
    return data


def validate_files():
    catalog = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    if {entry["file"] for entry in catalog["documents"]} != UPLOAD_FILES:
        raise ValueError("Source catalog does not match the fixed upload allowlist.")
    for entry in catalog["documents"]:
        path = ROOT / "documents" / entry["file"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Checksum mismatch for {entry['file']}; do not substitute private uploads.")


def request(client, method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def validate_existing_files(client, documents):
    validate_workspace(documents)
    catalog = json.loads((ROOT / "sources.json").read_text(encoding="utf-8"))
    hashes = {entry["file"]: entry["sha256"] for entry in catalog["documents"]}
    for document in documents:
        checksum = request(client, "GET", f"/documents/{document['id']}/checksum")
        if checksum.get("sha256") != hashes[document["filename"]]:
            raise ValueError(f"Checksum mismatch for existing {document['filename']}; refusing substituted sources.")


def load_demo(api_url, timeout=300):
    api_url = validate_api_url(api_url)
    validate_files()
    pack = read_cases()
    with httpx.Client(base_url=api_url, timeout=timeout) as client:
        health = request(client, "GET", "/health")
        if health.get("service") != "DocIntel AI Demo API":
            raise ValueError("Target must identify itself as DocIntel AI Demo API; refusing to write to a normal workspace.")
        documents = request(client, "GET", "/documents")
        validate_existing_files(client, documents)
        by_name = {document["filename"]: document for document in documents}
        for filename in sorted(UPLOAD_FILES):
            if filename not in by_name:
                path = ROOT / "documents" / filename
                mime = "image/png" if path.suffix == ".png" else "application/pdf"
                with path.open("rb") as file:
                    document = request(client, "POST", "/documents", files={"file": (filename, file, mime)})
                by_name[filename] = document
            deadline = time.monotonic() + timeout
            while True:
                document = request(client, "GET", f"/documents/{by_name[filename]['id']}")
                if document["status"] == "indexed":
                    by_name[filename] = document
                    break
                if document["status"] in {"failed", "ocr_required"} or time.monotonic() >= deadline:
                    raise RuntimeError(f"{filename} is not indexed: {document['status']}. Check local embedding/OCR prerequisites.")
                time.sleep(1)
            print(f"Indexed {filename}: {document['page_count']} pages, {document['chunk_count']} chunks", flush=True)
        suites = request(client, "GET", "/eval/document-suites")
        suite = next((value for value in suites if value["name"] == pack["suite_name"]), None)
        if suite is None:
            suite = request(client, "POST", "/eval/document-suites", json={"name": pack["suite_name"]})
        current = request(client, "GET", f"/eval/document-suites/{suite['id']}")
        existing = {(value["document_filename"], value["question"]) for value in current["cases"]}
        for case in pack["cases"]:
            if (case["document"], case["question"]) in existing:
                continue
            payload = {key: case[key] for key in ("question", "expected_outcome", "facts", "anchors", "tags", "review_rationale")}
            payload["document_id"] = by_name[case["document"]]["id"]
            request(client, "POST", f"/eval/document-suites/{suite['id']}/cases", json=payload)
        print("Prepared 25 candidate cases. No cases were marked reviewed; inspect sources in Evaluation Lab.")
        return {"api": api_url, "suite_id": suite["id"], "documents": {name: value["id"] for name, value in by_name.items()}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://127.0.0.1:8001")
    args = parser.parse_args()
    loaded = load_demo(args.api)
    destination = ROOT / ".local"
    destination.mkdir(exist_ok=True)
    (destination / "workspace.json").write_text(json.dumps(loaded, indent=2) + "\n", encoding="utf-8")
