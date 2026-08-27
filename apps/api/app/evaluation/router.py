from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import EvalRun
from app.db.session import get_db

router = APIRouter(prefix="/eval", tags=["evaluation"])


class EvalRunRead(BaseModel):
    id: str
    name: str
    model_name: str
    metrics: dict[str, float]
    created_at: datetime

    model_config = {"from_attributes": True}


@router.post("/runs", response_model=EvalRunRead)
def create_eval_run(db: Annotated[Session, Depends(get_db)]) -> EvalRun:
    settings = get_settings()
    eval_run = EvalRun(
        name="sample-retrieval-eval",
        model_name=settings.embedding_model_name,
        metrics={"hit_rate_at_5": 0.0, "mean_reciprocal_rank": 0.0},
    )
    db.add(eval_run)
    db.commit()
    db.refresh(eval_run)
    return eval_run


@router.get("/runs", response_model=list[EvalRunRead])
def list_eval_runs(db: Annotated[Session, Depends(get_db)]) -> list[EvalRun]:
    return list(db.scalars(select(EvalRun).order_by(EvalRun.created_at.desc())))
