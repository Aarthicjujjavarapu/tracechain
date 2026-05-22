import logging
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from fastapi import HTTPException

from ..models import WorkflowRun, RunStatus
from ..schemas import RunCreate, RunComplete, RunFail
from ..ws.manager import manager as ws_manager

logger = logging.getLogger("tracechain")


def _broadcast(event_type: str, run: WorkflowRun, **extra: object) -> None:
    ts = (run.ended_at or run.started_at)
    payload: dict = {
        "event_type":    event_type,
        "run_id":        run.id,
        "workflow_name": run.workflow_name,
        "status":        run.status.value if hasattr(run.status, "value") else str(run.status),
        "timestamp":     ts.isoformat() if ts else None,
        **extra,
    }
    ws_manager.fire_event_sync(payload)


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
    _broadcast("run.created", run)
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
    started = run.started_at if run.started_at.tzinfo else run.started_at.replace(tzinfo=timezone.utc)
    run.duration_ms = int((now - started).total_seconds() * 1000)
    if data.output_payload is not None:
        run.output_payload = data.output_payload
    if data.total_cost is not None:
        run.total_cost = data.total_cost
    if data.total_tokens is not None:
        run.total_tokens = data.total_tokens
    db.commit()
    db.refresh(run)
    _post_run_analysis(db, run)
    _broadcast("run.completed", run,
               duration_ms=run.duration_ms,
               reliability_score=run.reliability_score)
    return run


def fail_run(db: Session, run_id: str, data: RunFail) -> WorkflowRun:
    run = get_run(db, run_id)
    now = datetime.now(timezone.utc)
    run.status = RunStatus.failed
    run.ended_at = now
    started = run.started_at if run.started_at.tzinfo else run.started_at.replace(tzinfo=timezone.utc)
    run.duration_ms = int((now - started).total_seconds() * 1000)
    run.error_message = data.error_message
    db.commit()
    db.refresh(run)
    _post_run_analysis(db, run)
    _broadcast("run.failed", run,
               error_message=run.error_message,
               reliability_score=run.reliability_score)
    return run


def _post_run_analysis(db: Session, run: WorkflowRun) -> None:
    """
    Run classification, reliability scoring, and incident grouping after a run completes.

    Uses a nested transaction (savepoint) so that failures don't corrupt the
    outer session, and expire_on_commit=False on a temporary session so that
    objects loaded by the outer request are not expired by inner commits.
    """
    try:
        from .classification import run_classification
        from .reliability import score_run
        from .incidents import group_incident

        run_id = run.id  # capture before any potential expiry

        # Re-query in a sub-transaction so expiry doesn't affect the outer request's objects
        with db.begin_nested():
            classifications = run_classification(db, run_id)

        with db.begin_nested():
            score_run(db, run_id)

        with db.begin_nested():
            fresh_run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            if fresh_run:
                group_incident(db, fresh_run, classifications)

        new_firings:      list = []
        resolved_firings: list = []
        with db.begin_nested():
            from .alerts import evaluate_alert_rules
            fresh_run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
            wf_name = fresh_run.workflow_name if fresh_run else None
            new_firings, resolved_firings = evaluate_alert_rules(db, wf_name)

        db.commit()

        # Deliver webhooks after the commit so firings are visible in DB
        if new_firings or resolved_firings:
            try:
                from .webhooks import deliver_alert_events
                deliver_alert_events(db, new_firings, resolved_firings)
            except Exception:
                logger.exception("webhook delivery failed for run %s", run.id)

    except Exception:
        logger.exception("post-run analysis failed for run %s", run.id)
        try:
            db.rollback()
        except Exception:
            pass


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
    _broadcast("run.replayed", replay, original_run_id=original.id)
    return replay
