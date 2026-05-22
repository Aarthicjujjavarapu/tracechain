"""
Incident grouping engine.

Groups failure classifications into incidents by (category, workflow_name).
If an open incident already exists for that group, increments its count.
Otherwise creates a new OPEN incident.
"""
from __future__ import annotations
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from ..models import (
    WorkflowRun, FailureClassification, FailureSeverity,
    Incident, IncidentStatus, incident_runs,
)

_SEVERITY_RANK = {
    FailureSeverity.LOW.value:      0,
    FailureSeverity.MEDIUM.value:   1,
    FailureSeverity.HIGH.value:     2,
    FailureSeverity.CRITICAL.value: 3,
}

_RECOMMENDATIONS: dict[str, str] = {
    "RETRY_LOOP":             "Investigate recurring failure sources and add circuit breakers.",
    "MODEL_TIMEOUT":          "Review timeout configuration and model SLA.",
    "MODEL_RATE_LIMIT":       "Implement request queuing and rate limit back-off.",
    "OUTPUT_TRUNCATION":      "Increase max_tokens or break outputs into smaller chunks.",
    "CONTEXT_WINDOW_RISK":    "Add summarization or switch to a larger-context model.",
    "RETRIEVAL_FAILURE":      "Check retrieval system health and index availability.",
    "LOW_RELEVANCE_CONTEXT":  "Tune embedding model and retrieval top-k selection.",
    "HALLUCINATION_RISK":     "Add grounding checks and output validation.",
    "TOOL_CALL_FAILURE":      "Add tool availability checks and argument validation.",
    "TOOL_ARGUMENT_ERROR":    "Enforce tool argument schemas before execution.",
    "VALIDATION_FAILURE":     "Enforce structured output via response_format or parsers.",
    "LATENCY_SPIKE":          "Profile slowest steps and add caching.",
    "COST_SPIKE":             "Use cheaper models for simpler tasks and add prompt caching.",
    "PROMPT_REGRESSION":      "Review recent prompt changes and roll back if quality dropped.",
    "UNKNOWN_FAILURE":        "Review application logs and add specific error handling.",
}


def _incident_title(category: str, workflow_name: str | None) -> str:
    label = category.replace("_", " ").title()
    if workflow_name:
        return f"{label} in {workflow_name}"
    return label


def group_incident(db: Session, run: WorkflowRun, classifications: list[FailureClassification]) -> list[Incident]:
    if not classifications:
        return []

    now = datetime.now(timezone.utc)
    touched: list[Incident] = []

    # Group classifications by category so we create at most one incident per category per run
    by_category: dict[str, FailureClassification] = {}
    for fc in classifications:
        existing = by_category.get(fc.category)
        if existing is None or _SEVERITY_RANK.get(fc.severity, 0) > _SEVERITY_RANK.get(existing.severity, 0):
            by_category[fc.category] = fc

    for category, fc in by_category.items():
        # Look for an open incident with matching (category, workflow_name)
        incident = (
            db.query(Incident)
            .filter(
                Incident.category      == category,
                Incident.workflow_name == run.workflow_name,
                Incident.status        != IncidentStatus.RESOLVED.value,
            )
            .order_by(Incident.last_seen_at.desc())
            .first()
        )

        if incident:
            incident.occurrence_count += 1
            incident.last_seen_at      = now
            # Escalate severity if necessary
            if _SEVERITY_RANK.get(fc.severity, 0) > _SEVERITY_RANK.get(incident.severity, 0):
                incident.severity = fc.severity
        else:
            incident = Incident(
                title              = _incident_title(category, run.workflow_name),
                category           = category,
                severity           = fc.severity,
                status             = IncidentStatus.OPEN.value,
                workflow_name      = run.workflow_name,
                occurrence_count   = 1,
                first_seen_at      = now,
                last_seen_at       = now,
                evidence           = fc.evidence,
                recommended_action = _RECOMMENDATIONS.get(category, fc.recommendation or ""),
            )
            db.add(incident)
            db.flush()

        # Link run to incident (ignore duplicate links)
        already_linked = db.execute(
            incident_runs.select().where(
                incident_runs.c.incident_id == incident.id,
                incident_runs.c.run_id      == run.id,
            )
        ).first()
        if not already_linked:
            db.execute(incident_runs.insert().values(incident_id=incident.id, run_id=run.id, linked_at=now))

        touched.append(incident)

    db.flush()
    return touched


def get_incidents(
    db: Session,
    status: str | None = None,
    severity: str | None = None,
    workflow_name: str | None = None,
    category: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> tuple[list[Incident], int]:
    q = db.query(Incident)
    if status:
        q = q.filter(Incident.status == status)
    if severity:
        q = q.filter(Incident.severity == severity)
    if workflow_name:
        q = q.filter(Incident.workflow_name == workflow_name)
    if category:
        q = q.filter(Incident.category == category)
    total = q.count()
    items = q.order_by(Incident.last_seen_at.desc()).offset(offset).limit(limit).all()
    return items, total


def acknowledge_incident(db: Session, incident_id: str) -> Incident | None:
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if inc and inc.status == IncidentStatus.OPEN.value:
        inc.status = IncidentStatus.ACKNOWLEDGED.value
        db.commit()
        db.refresh(inc)
    return inc


def resolve_incident(db: Session, incident_id: str) -> Incident | None:
    now = datetime.now(timezone.utc)
    inc = db.query(Incident).filter(Incident.id == incident_id).first()
    if inc and inc.status != IncidentStatus.RESOLVED.value:
        inc.status      = IncidentStatus.RESOLVED.value
        inc.resolved_at = now
        db.commit()
        db.refresh(inc)
    return inc
