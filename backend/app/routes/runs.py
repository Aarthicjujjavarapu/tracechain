from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import (
    RunCreate, RunComplete, RunFail,
    RunOut, RunListOut,
)
from ..services import runs as run_svc

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunOut, status_code=201)
def create_run(data: RunCreate, db: Session = Depends(get_db)):
    return RunOut.from_orm_model(run_svc.create_run(db, data))


@router.get("", response_model=RunListOut)
def list_runs(
    status: Optional[str] = Query(None),
    workflow_name: Optional[str] = Query(None),
    is_replay: Optional[bool] = Query(None),
    original_run_id: Optional[str] = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    items, total = run_svc.list_runs(db, status, workflow_name, is_replay, original_run_id, offset, limit)
    return RunListOut(items=[RunOut.from_orm_model(r) for r in items], total=total)


@router.get("/{run_id}", response_model=RunOut)
def get_run(run_id: str, db: Session = Depends(get_db)):
    return RunOut.from_orm_model(run_svc.get_run(db, run_id))


@router.post("/{run_id}/complete", response_model=RunOut)
def complete_run(run_id: str, data: RunComplete, db: Session = Depends(get_db)):
    return RunOut.from_orm_model(run_svc.complete_run(db, run_id, data))


@router.post("/{run_id}/fail", response_model=RunOut)
def fail_run(run_id: str, data: RunFail, db: Session = Depends(get_db)):
    return RunOut.from_orm_model(run_svc.fail_run(db, run_id, data))


@router.post("/{run_id}/replay", response_model=RunOut, status_code=201)
def replay_run(run_id: str, db: Session = Depends(get_db)):
    return RunOut.from_orm_model(run_svc.replay_run(db, run_id))
