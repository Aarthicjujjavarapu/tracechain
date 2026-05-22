from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import FailureClassification
from ..schemas import FailureClassificationOut
from ..services.classification import run_classification

router = APIRouter(prefix="/runs", tags=["classifications"])


@router.get("/{run_id}/classifications", response_model=list[FailureClassificationOut])
def get_classifications(run_id: str, db: Session = Depends(get_db)):
    return (
        db.query(FailureClassification)
        .filter(FailureClassification.run_id == run_id)
        .order_by(FailureClassification.created_at)
        .all()
    )


@router.post("/{run_id}/classifications/refresh", response_model=list[FailureClassificationOut])
def refresh_classifications(run_id: str, db: Session = Depends(get_db)):
    """Re-run the classifier and return fresh results."""
    results = run_classification(db, run_id)
    db.commit()
    return results
