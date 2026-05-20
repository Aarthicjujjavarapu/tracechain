from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas import FeedbackCreate, FeedbackOut
from ..services import feedback as fb_svc

router = APIRouter(prefix="/runs", tags=["feedback"])


@router.post("/{run_id}/feedback", response_model=FeedbackOut, status_code=201)
def create_feedback(run_id: str, data: FeedbackCreate, db: Session = Depends(get_db)):
    return fb_svc.create_feedback(db, run_id, data)


@router.get("/{run_id}/feedback", response_model=list[FeedbackOut])
def list_feedback(run_id: str, db: Session = Depends(get_db)):
    return fb_svc.list_feedback(db, run_id)
