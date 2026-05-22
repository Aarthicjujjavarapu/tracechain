from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException

from ..models import TraceStep, RunStatus
from ..schemas import StepCreate


def create_step(db: Session, run_id: str, data: StepCreate) -> TraceStep:
    step = TraceStep(
        run_id=run_id,
        step_name=data.step_name,
        step_type=data.step_type,
        status=RunStatus.running,
        input_payload=data.input_payload,
        metadata_=data.metadata,
        started_at=datetime.now(timezone.utc),
    )
    db.add(step)
    db.commit()
    db.refresh(step)
    return step


def get_step(db: Session, step_id: str) -> TraceStep:
    step = db.query(TraceStep).filter(TraceStep.id == step_id).first()
    if not step:
        raise HTTPException(status_code=404, detail=f"Step {step_id} not found")
    return step


def list_steps(db: Session, run_id: str) -> list[TraceStep]:
    return (
        db.query(TraceStep)
        .filter(TraceStep.run_id == run_id)
        .order_by(TraceStep.started_at)
        .all()
    )


def complete_step(db: Session, step_id: str, output_payload: dict, duration_ms: int | None, retry_count: int) -> TraceStep:
    step = get_step(db, step_id)
    now = datetime.now(timezone.utc)
    step.status = RunStatus.success
    step.ended_at = now
    step.output_payload = output_payload
    step.retry_count = retry_count
    started = step.started_at if step.started_at.tzinfo else step.started_at.replace(tzinfo=timezone.utc)
    step.duration_ms = duration_ms or int((now - started).total_seconds() * 1000)
    db.commit()
    db.refresh(step)
    return step


def fail_step(db: Session, step_id: str, error_message: str, retry_count: int) -> TraceStep:
    step = get_step(db, step_id)
    now = datetime.now(timezone.utc)
    step.status = RunStatus.failed
    step.ended_at = now
    step.error_message = error_message
    step.retry_count = retry_count
    started = step.started_at if step.started_at.tzinfo else step.started_at.replace(tzinfo=timezone.utc)
    step.duration_ms = int((now - started).total_seconds() * 1000)
    db.commit()
    db.refresh(step)
    return step
