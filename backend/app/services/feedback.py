from sqlalchemy.orm import Session
from fastapi import HTTPException

from ..models import HumanFeedback
from ..schemas import FeedbackCreate


def create_feedback(db: Session, run_id: str, data: FeedbackCreate) -> HumanFeedback:
    if not (1 <= data.rating <= 5):
        raise HTTPException(status_code=422, detail="Rating must be between 1 and 5")
    fb = HumanFeedback(
        run_id=run_id,
        rating=data.rating,
        comment=data.comment,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)
    return fb


def list_feedback(db: Session, run_id: str) -> list[HumanFeedback]:
    return (
        db.query(HumanFeedback)
        .filter(HumanFeedback.run_id == run_id)
        .order_by(HumanFeedback.created_at)
        .all()
    )
