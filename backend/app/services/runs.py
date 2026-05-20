from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException

from ..models import WorkflowRun, RunStatus
from ..schemas import RunCreate, RunComplete, RunFail


def create_run(db: Session, data: RunCreate) -> WorkflowRun:
    run = WorkflowRun(
        workflow_name=data.workflow_name,
        status=RunStatus.running,
        input_payload=data.input_payload,
        metadata_=data.metadata,
        started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def get_run(db: Session, run_id: str) -> WorkflowRun:
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


def list_runs(
    db: Session,
    status: Optional[str] = None,
    workflow_name: Optional[str] = None,
    is_replay: Optional[bool] = None,
    original_run_id: Optional[str] = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[WorkflowRun], int]:
    q = db.query(WorkflowRun)
    if status:
        q = q.filter(WorkflowRun.status == status)
    if workflow_name:
        q = q.filter(WorkflowRun.workflow_name == workflow_name)
    if is_replay is not None:
        q = q.filter(WorkflowRun.is_replay == is_replay)
    if original_run_id:
        q = q.filter(WorkflowRun.original_run_id == original_run_id)
    total = q.count()
    items = q.order_by(desc(WorkflowRun.started_at)).offset(offset).limit(limit).all()
    return items, total


def complete_run(db: Session, run_id: str, data: RunComplete) -> WorkflowRun:
    run = get_run(db, run_id)
    now = datetime.now(timezone.utc)
    run.status = RunStatus.success
    run.ended_at = now
    run.duration_ms = int((now - run.started_at).total_seconds() * 1000)
    if data.output_payload is not None:
        run.output_payload = data.output_payload
    if data.total_cost is not None:
        run.total_cost = data.total_cost
    if data.total_tokens is not None:
        run.total_tokens = data.total_tokens
    db.commit()
    db.refresh(run)
    return run


def fail_run(db: Session, run_id: str, data: RunFail) -> WorkflowRun:
    run = get_run(db, run_id)
    now = datetime.now(timezone.utc)
    run.status = RunStatus.failed
    run.ended_at = now
    run.duration_ms = int((now - run.started_at).total_seconds() * 1000)
    run.error_message = data.error_message
    db.commit()
    db.refresh(run)
    return run


def replay_run(db: Session, run_id: str) -> WorkflowRun:
    original = get_run(db, run_id)
    replay = WorkflowRun(
        workflow_name=original.workflow_name,
        status=RunStatus.running,
        input_payload=original.input_payload,
        original_run_id=original.id,
        is_replay=True,
        metadata_=original.metadata_,
        started_at=datetime.now(timezone.utc),
    )
    db.add(replay)
    db.commit()
    db.refresh(replay)
    return replay
