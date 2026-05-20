from sqlalchemy.orm import Session

from ..models import EvaluationResult
from ..schemas import EvalCreate


def create_evaluation(db: Session, run_id: str, data: EvalCreate) -> EvaluationResult:
    ev = EvaluationResult(
        run_id=run_id,
        relevance_score=data.relevance_score,
        groundedness_score=data.groundedness_score,
        hallucination_risk=data.hallucination_risk,
        quality_score=data.quality_score,
        failure_reason=data.failure_reason,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


def list_evaluations(db: Session, run_id: str) -> list[EvaluationResult]:
    return (
        db.query(EvaluationResult)
        .filter(EvaluationResult.run_id == run_id)
        .order_by(EvaluationResult.created_at)
        .all()
    )
