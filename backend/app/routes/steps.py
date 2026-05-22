from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import StepCreate, StepOut, StepComplete, StepFail
from ..services import steps as step_svc

router = APIRouter(prefix="/runs", tags=["steps"])


@router.post("/{run_id}/steps", response_model=StepOut, status_code=201)
def create_step(run_id: str, data: StepCreate, db: Session = Depends(get_db)):
    return StepOut.from_orm_model(step_svc.create_step(db, run_id, data))


@router.get("/{run_id}/steps/{step_id}", response_model=StepOut)
def get_step(run_id: str, step_id: str, db: Session = Depends(get_db)):
    return StepOut.from_orm_model(step_svc.get_step(db, step_id))


@router.get("/{run_id}/steps", response_model=list[StepOut])
def list_steps(run_id: str, db: Session = Depends(get_db)):
    return [StepOut.from_orm_model(s) for s in step_svc.list_steps(db, run_id)]


@router.post("/{run_id}/steps/{step_id}/complete", response_model=StepOut)
def complete_step(run_id: str, step_id: str, data: StepComplete, db: Session = Depends(get_db)):
    return StepOut.from_orm_model(
        step_svc.complete_step(db, step_id, data.output_payload or {}, data.duration_ms, data.retry_count)
    )


@router.post("/{run_id}/steps/{step_id}/fail", response_model=StepOut)
def fail_step(run_id: str, step_id: str, data: StepFail, db: Session = Depends(get_db)):
    return StepOut.from_orm_model(
        step_svc.fail_step(db, step_id, data.error_message, data.retry_count)
    )
