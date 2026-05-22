from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import WorkflowRun
from ..schemas import ReliabilityOut
from ..services.reliability import score_run

router = APIRouter(prefix="/runs", tags=["reliability"])


@router.get("/{run_id}/reliability", response_model=ReliabilityOut)
def get_reliability(run_id: str, db: Session = Depends(get_db)):
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if run and run.reliability_score is not None:
        return ReliabilityOut(
            run_id=run_id,
            score=run.reliability_score,
            reasons=run.reliability_reasons or [],
        )
    # Compute on demand if not already cached
    score, reasons = score_run(db, run_id)
    db.commit()
    return ReliabilityOut(run_id=run_id, score=score, reasons=reasons)
