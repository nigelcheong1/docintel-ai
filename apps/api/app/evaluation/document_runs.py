from collections import Counter
from dataclasses import asdict
from pathlib import Path
import subprocess
from time import perf_counter

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import DocumentEvalCase, DocumentEvalResult, DocumentEvalRun, DocumentEvalSuite, utc_now
from app.documents.service import EmbeddingProviderFactory, SessionFactory
from app.evaluation.document_cases import check_case_readiness, read_case
from app.evaluation.document_metrics import aggregate_case_measurements, case_failure_reasons, score_case
from app.evaluation.document_schemas import CaseWrite, ResultRead, RunRead
from app.retrieval import service as search_service
from app.retrieval.search import SearchRequest

ACTIVE_STATES = {"queued", "running"}


def pipeline_config() -> dict[str, object]:
    settings = get_settings()
    revision = None
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[4], capture_output=True, text=True, timeout=2, check=True).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return {"embedding_model": settings.embedding_model_name, "embedding_device": settings.embedding_device, "embedding_dimension": settings.embedding_dimension, "top_k": 5, "answer_mode": "verified", "revision": revision}


def get_run(db: Session, run_id: str, *, lock: bool = False) -> DocumentEvalRun:
    statement = select(DocumentEvalRun).where(DocumentEvalRun.id == run_id)
    if lock:
        statement = statement.with_for_update()
    run = db.scalar(statement.execution_options(populate_existing=True))
    if run is None:
        raise HTTPException(404, "Document benchmark run not found.")
    return run


def create_document_run(db: Session, suite_id: str, pipeline_config: dict[str, object]) -> DocumentEvalRun:
    suite = db.get(DocumentEvalSuite, suite_id)
    if suite is None:
        raise HTTPException(404, "Benchmark suite not found.")
    cases = list(db.scalars(select(DocumentEvalCase).where(DocumentEvalCase.suite_id == suite_id, DocumentEvalCase.review_state == "reviewed").order_by(DocumentEvalCase.created_at)))
    if not cases or len(cases) > 100:
        raise HTTPException(422, "A run requires between 1 and 100 reviewed cases; drafts are excluded.")
    run = DocumentEvalRun(suite_id=suite_id, suite_snapshot={"id": suite.id, "name": suite.name}, case_snapshots=[read_case(db, case).model_dump(mode="json") for case in cases], pipeline_config={**pipeline_config, "top_k": 5, "answer_mode": "verified"}, total_cases=len(cases), active_slot=1, status="queued")
    db.add(run)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Another document benchmark is active; wait or cancel it first.") from exc
    db.refresh(run)
    return run


def _finish(run: DocumentEvalRun, status: str, error: str | None = None) -> None:
    run.status = status
    run.active_slot = None
    run.finished_at = utc_now()
    run.error = error


def request_run_cancel(db: Session, run_id: str) -> DocumentEvalRun:
    run = get_run(db, run_id, lock=True)
    if run.status in ACTIVE_STATES:
        run.cancel_requested = True
        if run.status == "queued":
            _finish(run, "cancelled")
    db.commit()
    db.refresh(run)
    return run


def interrupt_abandoned_runs(db: Session) -> int:
    runs = list(db.scalars(select(DocumentEvalRun).where(DocumentEvalRun.status.in_(ACTIVE_STATES)).with_for_update()))
    for run in runs:
        _finish(run, "interrupted", "Backend restarted before this run finished; completed results were retained.")
    db.commit()
    return len(runs)


def list_results(db: Session, run_id: str) -> list[ResultRead]:
    return [ResultRead.model_validate(result) for result in db.scalars(select(DocumentEvalResult).where(DocumentEvalResult.run_id == run_id).order_by(DocumentEvalResult.created_at))]


def read_run(db: Session, run: DocumentEvalRun) -> RunRead:
    results = list_results(db, run.id)
    modes = Counter(result.execution_snapshot.get("response", {}).get("retrieval_mode") for result in results if result.status in {"pass", "fail"})
    return RunRead.model_validate(run).model_copy(update={
        "mode_counts": {key: count for key, count in modes.items() if key},
        "fallback_count": sum(bool(result.execution_snapshot.get("response", {}).get("retrieval_fallback_reason")) for result in results),
        "error_count": sum(result.status == "error" for result in results),
        "unavailable_count": sum(result.status == "unavailable" for result in results),
        "passed_count": sum(result.status == "pass" for result in results),
        "failed_count": sum(result.status == "fail" for result in results),
    })


def _execute_case(db: Session, run_id: str, snapshot: dict, embedder_factory: EmbeddingProviderFactory) -> DocumentEvalResult:
    result = DocumentEvalResult(run_id=run_id, case_id_snapshot=snapshot["id"], case_version=snapshot["content_version"], case_snapshot=snapshot, status="error", duration_ms=0, failure_reasons=[], measurements={}, execution_snapshot={})
    start = perf_counter()
    try:
        case = DocumentEvalCase(**{key: snapshot[key] for key in ("document_id", "document_filename", "question", "expected_outcome", "facts", "anchors", "tags", "review_rationale", "review_state", "review_page_hashes", "content_version")})
        readiness = check_case_readiness(db, case)
        if readiness.availability != "ready":
            result.status = "unavailable"
            result.failure_reasons = list(readiness.reasons)
        else:
            # Scoring labels never cross the production execution boundary.
            execution = search_service.execute_search(SearchRequest(query=case.question, document_id=case.document_id, top_k=5, answer_mode="verified"), db, embedder_factory)
            measurements = score_case(CaseWrite.model_validate(snapshot), readiness.anchors, execution, (perf_counter() - start) * 1000)
            result.failure_reasons = case_failure_reasons(CaseWrite.model_validate(snapshot), measurements)
            result.status = "fail" if result.failure_reasons else "pass"
            result.measurements = {key: value.model_dump(mode="json") for key, value in measurements.items()}
            result.execution_snapshot = {"response": execution.response.model_dump(mode="json"), "candidates_by_subquery": {query: [asdict(hit) for hit in hits] for query, hits in execution.candidates_by_subquery.items()}, "selected_evidence": [asdict(hit) for hit in execution.selected_evidence], "resolved_anchors": [asdict(anchor) for anchor in readiness.anchors]}
    except Exception as exc:
        db.rollback()
        result.status = "error"
        result.failure_reasons = [f"Execution error: {str(exc).strip() or type(exc).__name__}"]
    result.duration_ms = (perf_counter() - start) * 1000
    return result


def execute_document_run(run_id: str, session_factory: SessionFactory, embedder_factory: EmbeddingProviderFactory) -> None:
    try:
        with session_factory() as db:
            run = get_run(db, run_id, lock=True)
            if run.status != "queued":
                return
            run.status = "running"
            run.started_at = utc_now()
            snapshots = run.case_snapshots
            db.commit()
        for snapshot in snapshots:
            with session_factory() as db:
                run = get_run(db, run_id)
                if run.status != "running":
                    return
                if run.cancel_requested:
                    _finish(run, "cancelled")
                    db.commit()
                    return
                result = _execute_case(db, run_id, snapshot, embedder_factory)
                run = get_run(db, run_id, lock=True)
                if run.status != "running":
                    return
                db.add(result)
                db.flush()
                run.completed_cases += 1
                run.measurements = {key: value.model_dump(mode="json") for key, value in aggregate_case_measurements(list_results(db, run.id)).items()}
                if run.cancel_requested:
                    _finish(run, "cancelled")
                elif run.completed_cases == run.total_cases:
                    _finish(run, "completed")
                db.commit()
        return
    except Exception as exc:
        with session_factory() as db:
            run = get_run(db, run_id, lock=True)
            if run.status in ACTIVE_STATES:
                _finish(run, "failed", f"Benchmark worker failed: {str(exc).strip() or type(exc).__name__}")
                db.commit()
