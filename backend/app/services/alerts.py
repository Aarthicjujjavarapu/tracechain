"""Alert rule evaluation service.

Evaluates enabled alert rules and fires/resolves AlertFiring records.
Called from _post_run_analysis after every run completion.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ..models import (
    AlertFiring, AlertRule,
    Incident, IncidentStatus,
    WorkflowRun, RunStatus,
)

logger = logging.getLogger("tracechain.alerts")

VALID_METRICS   = {"success_rate", "avg_latency_ms", "avg_cost", "open_incidents", "reliability_score"}
VALID_OPERATORS = {"lt", "lte", "gt", "gte"}


def _check(value: float, operator: str, threshold: float) -> bool:
    if operator == "lt":  return value <  threshold
    if operator == "lte": return value <= threshold
    if operator == "gt":  return value >  threshold
    if operator == "gte": return value >= threshold
    return False


def _compute_metric(db: Session, rule: AlertRule, now: datetime) -> float | None:
    cutoff = now - timedelta(minutes=rule.window_minutes)
    wf     = rule.workflow_name

    def _normalize(ts: datetime) -> datetime:
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)

    if rule.metric == "success_rate":
        q = db.query(WorkflowRun).filter(WorkflowRun.started_at >= cutoff)
        if wf:
            q = q.filter(WorkflowRun.workflow_name == wf)
        rows = q.all()
        if not rows:
            return None
        rows = [r for r in rows if _normalize(r.started_at) >= cutoff]
        if not rows:
            return None
        return sum(1 for r in rows if r.status == RunStatus.success) / len(rows)

    if rule.metric == "avg_latency_ms":
        q = db.query(WorkflowRun).filter(
            WorkflowRun.started_at >= cutoff,
            WorkflowRun.duration_ms.isnot(None),
        )
        if wf:
            q = q.filter(WorkflowRun.workflow_name == wf)
        rows = [r for r in q.all() if _normalize(r.started_at) >= cutoff]
        if not rows:
            return None
        return sum(r.duration_ms for r in rows) / len(rows)

    if rule.metric == "avg_cost":
        q = db.query(WorkflowRun).filter(
            WorkflowRun.started_at >= cutoff,
            WorkflowRun.total_cost.isnot(None),
        )
        if wf:
            q = q.filter(WorkflowRun.workflow_name == wf)
        rows = [r for r in q.all() if _normalize(r.started_at) >= cutoff]
        if not rows:
            return None
        return sum(r.total_cost for r in rows) / len(rows)

    if rule.metric == "open_incidents":
        q = db.query(Incident).filter(Incident.status == IncidentStatus.OPEN.value)
        if wf:
            q = q.filter(Incident.workflow_name == wf)
        return float(q.count())

    if rule.metric == "reliability_score":
        q = db.query(WorkflowRun).filter(
            WorkflowRun.started_at >= cutoff,
            WorkflowRun.reliability_score.isnot(None),
        )
        if wf:
            q = q.filter(WorkflowRun.workflow_name == wf)
        rows = (
            [r for r in q.order_by(WorkflowRun.started_at.desc()).limit(10).all()
             if _normalize(r.started_at) >= cutoff]
        )
        if not rows:
            return None
        return sum(r.reliability_score for r in rows) / len(rows)

    return None


def evaluate_alert_rules(db: Session, workflow_name: str | None = None) -> None:
    """Evaluate all enabled rules (optionally scoped to a workflow) and update firings."""
    now = datetime.now(timezone.utc)

    q = db.query(AlertRule).filter(AlertRule.enabled == True)  # noqa: E712
    if workflow_name:
        from sqlalchemy import or_
        q = q.filter(
            or_(AlertRule.workflow_name == workflow_name, AlertRule.workflow_name.is_(None))
        )
    rules = q.all()

    for rule in rules:
        if rule.metric not in VALID_METRICS or rule.operator not in VALID_OPERATORS:
            continue
        try:
            value = _compute_metric(db, rule, now)
            if value is None:
                continue

            condition_met = _check(value, rule.operator, rule.threshold)

            active_firing = (
                db.query(AlertFiring)
                  .filter(AlertFiring.rule_id == rule.id, AlertFiring.is_active == True)  # noqa: E712
                  .first()
            )

            if condition_met and not active_firing:
                db.add(AlertFiring(rule_id=rule.id, metric_value=value, fired_at=now))
            elif not condition_met and active_firing:
                active_firing.resolved_at = now
                active_firing.is_active   = False

        except Exception:
            logger.exception("alert rule %s (%s) evaluation failed", rule.id, rule.name)

    db.flush()
