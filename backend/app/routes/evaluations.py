from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import EvalCreate, EvalOut
from ..services import evaluations as eval_svc

router = APIRouter(prefix="/runs", tags=["evaluations"])


@router.post("/{run_id}/evaluations", response_model=EvalOut, status_code=201)
def create_evaluation(run_id: str, data: EvalCreate, db: Session = Depends(get_db)):
    return eval_svc.create_evaluation(db, run_id, data)


@router.get("/{run_id}/evaluations", response_model=list[EvalOut])
def list_evaluations(run_id: str, db: Session = Depends(get_db)):
    return eval_svc.list_evaluations(db, run_id)
