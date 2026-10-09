from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import DocumentEvalCase, DocumentEvalResult, DocumentEvalRun, DocumentEvalSuite, utc_now
from app.db.session import get_db
from app.documents.router import get_embedding_provider_factory
from app.documents.service import EmbeddingProviderFactory, SessionFactory
from app.evaluation import document_cases, document_runs
from app.evaluation.document_schemas import CaseRead, CaseWrite, ResultAssessmentWrite, ResultRead, ReviewCaseRequest, RunCreate, RunRead, SuiteDetail, SuiteRead, SuiteWrite

router = APIRouter(prefix="/eval", tags=["document benchmarks"])
DB = Annotated[Session, Depends(get_db)]


def get_benchmark_session_factory(db: DB) -> SessionFactory:
    return sessionmaker(bind=db.get_bind(), autoflush=False, expire_on_commit=False)


def _suite(db: Session, suite_id: str) -> DocumentEvalSuite:
    suite = db.get(DocumentEvalSuite, suite_id)
    if suite is None:
        raise HTTPException(404, "Benchmark suite not found.")
    return suite


def _suite_read(db: Session, suite: DocumentEvalSuite) -> SuiteRead:
    cases = list(db.scalars(select(DocumentEvalCase).where(DocumentEvalCase.suite_id == suite.id)))
    return SuiteRead.model_validate(suite).model_copy(update={"case_count": len(cases), "reviewed_count": sum(case.review_state == "reviewed" for case in cases)})


def _owned_case(db: Session, suite_id: str, case_id: str) -> DocumentEvalCase:
    case = db.scalar(select(DocumentEvalCase).where(DocumentEvalCase.id == case_id, DocumentEvalCase.suite_id == suite_id))
    if case is None:
        raise HTTPException(404, "Case not found in this suite.")
    return case


@router.get("/document-suites", response_model=list[SuiteRead])
def list_suites(db: DB) -> list[SuiteRead]:
    return [_suite_read(db, suite) for suite in db.scalars(select(DocumentEvalSuite).order_by(DocumentEvalSuite.updated_at.desc()))]


@router.post("/document-suites", response_model=SuiteRead, status_code=201)
def create_suite(data: SuiteWrite, db: DB) -> SuiteRead:
    suite = DocumentEvalSuite(name=data.name)
    db.add(suite)
    db.commit()
    db.refresh(suite)
    return _suite_read(db, suite)


@router.get("/document-suites/{suite_id}", response_model=SuiteDetail)
def suite_detail(suite_id: UUID, db: DB) -> SuiteDetail:
    suite = _suite(db, str(suite_id))
    cases = list(db.scalars(select(DocumentEvalCase).where(DocumentEvalCase.suite_id == suite.id).order_by(DocumentEvalCase.created_at)))
    return SuiteDetail(**_suite_read(db, suite).model_dump(), cases=[document_cases.read_case(db, case) for case in cases])


@router.put("/document-suites/{suite_id}", response_model=SuiteRead)
def update_suite(suite_id: UUID, data: SuiteWrite, db: DB) -> SuiteRead:
    suite = _suite(db, str(suite_id))
    suite.name = data.name
    db.commit()
    db.refresh(suite)
    return _suite_read(db, suite)


@router.delete("/document-suites/{suite_id}", status_code=204)
def delete_suite(suite_id: UUID, db: DB) -> Response:
    db.delete(_suite(db, str(suite_id)))
    db.commit()
    return Response(status_code=204)


@router.post("/document-suites/{suite_id}/cases", response_model=CaseRead, status_code=201)
def create_case(suite_id: UUID, data: CaseWrite, db: DB) -> CaseRead:
    return document_cases.read_case(db, document_cases.create_case(db, str(suite_id), data))


@router.put("/document-suites/{suite_id}/cases/{case_id}", response_model=CaseRead)
def update_case(suite_id: UUID, case_id: UUID, data: CaseWrite, db: DB) -> CaseRead:
    _owned_case(db, str(suite_id), str(case_id))
    return document_cases.read_case(db, document_cases.update_case(db, str(case_id), data))


@router.delete("/document-suites/{suite_id}/cases/{case_id}", status_code=204)
def delete_case(suite_id: UUID, case_id: UUID, db: DB) -> Response:
    db.delete(_owned_case(db, str(suite_id), str(case_id)))
    _suite(db, str(suite_id)).updated_at = utc_now()
    db.commit()
    return Response(status_code=204)


@router.post("/document-suites/{suite_id}/cases/{case_id}/review", response_model=CaseRead)
def review_case(suite_id: UUID, case_id: UUID, data: ReviewCaseRequest, db: DB) -> CaseRead:
    _owned_case(db, str(suite_id), str(case_id))
    return document_cases.read_case(db, document_cases.review_case(db, str(case_id), data.content_version))


@router.post("/document-runs", response_model=RunRead, status_code=202)
def create_run(data: RunCreate, background_tasks: BackgroundTasks, db: DB,
               session_factory: Annotated[SessionFactory, Depends(get_benchmark_session_factory)],
               embedder_factory: Annotated[EmbeddingProviderFactory, Depends(get_embedding_provider_factory)]) -> RunRead:
    run = document_runs.create_document_run(db, str(data.suite_id), document_runs.pipeline_config())
    response = document_runs.read_run(db, run)
    background_tasks.add_task(document_runs.execute_document_run, run.id, session_factory, embedder_factory)
    return response


@router.get("/document-runs", response_model=list[RunRead])
def list_runs(db: DB, suite_id: UUID | None = None) -> list[RunRead]:
    statement = select(DocumentEvalRun).order_by(DocumentEvalRun.created_at.desc()).limit(100)
    if suite_id is not None:
        statement = statement.where(DocumentEvalRun.suite_id == str(suite_id))
    return [document_runs.read_run(db, run) for run in db.scalars(statement)]


@router.get("/document-runs/{run_id}", response_model=RunRead)
def run_detail(run_id: UUID, db: DB) -> RunRead:
    return document_runs.read_run(db, document_runs.get_run(db, str(run_id)))


@router.get("/document-runs/{run_id}/results", response_model=list[ResultRead])
def run_results(run_id: UUID, db: DB) -> list[ResultRead]:
    document_runs.get_run(db, str(run_id))
    return document_runs.list_results(db, str(run_id))


@router.post("/document-runs/{run_id}/cancel", response_model=RunRead)
def cancel_run(run_id: UUID, db: DB) -> RunRead:
    return document_runs.read_run(db, document_runs.request_run_cancel(db, str(run_id)))


@router.put("/document-runs/{run_id}/results/{result_id}/assessment", response_model=ResultRead)
def assess_result(run_id: UUID, result_id: UUID, data: ResultAssessmentWrite, db: DB) -> ResultRead:
    result = db.scalar(select(DocumentEvalResult).where(DocumentEvalResult.id == str(result_id), DocumentEvalResult.run_id == str(run_id)).with_for_update())
    if result is None:
        raise HTTPException(404, "Result not found in this run.")
    result.human_assessment = data.assessment
    result.assessment_note = data.note
    result.assessed_at = utc_now()
    db.commit()
    db.refresh(result)
    return ResultRead.model_validate(result)
