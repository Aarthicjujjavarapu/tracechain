from datetime import datetime, timezone, timedelta
from collections import defaultdict
from sqlalchemy.orm import Session
from sqlalchemy import func

from collections import defaultdict as _defaultdict
from sqlalchemy import desc
from ..models import WorkflowRun, TraceStep, LLMCall, EvaluationResult, FailureClassification, Incident, IncidentStatus, RunStatus
from ..schemas import (
    OverviewMetrics, LatencyPoint, CostPoint,
    FailurePoint, TimeSeriesPoint,
    ClassificationBreakdownPoint, IncidentSummary, WorkflowHealth,
)


def get_overview(db: Session) -> OverviewMetrics:
    total_runs = db.query(func.count(WorkflowRun.id)).scalar() or 0
    success_count = (
        db.query(func.count(WorkflowRun.id))
        .filter(WorkflowRun.status == RunStatus.success)
        .scalar() or 0
    )
    failure_count = (
        db.query(func.count(WorkflowRun.id))
        .filter(WorkflowRun.status == RunStatus.failed)
        .scalar() or 0
    )

    avg_latency = (
        db.query(func.avg(WorkflowRun.duration_ms))
        .filter(WorkflowRun.duration_ms.isnot(None))
        .scalar() or 0.0
    )

    total_cost = (
        db.query(func.sum(WorkflowRun.total_cost))
        .filter(WorkflowRun.total_cost.isnot(None))
        .scalar() or 0.0
    )

    total_tokens = (
        db.query(func.sum(WorkflowRun.total_tokens))
        .filter(WorkflowRun.total_tokens.isnot(None))
        .scalar() or 0
    )

    success_rate = round(success_count / total_runs, 4) if total_runs > 0 else 0.0

    return OverviewMetrics(
        total_runs=total_runs,
        success_rate=success_rate,
        avg_latency_ms=round(float(avg_latency), 1),
        total_cost=round(float(total_cost), 4),
        total_tokens=int(total_tokens),
        failure_count=failure_count,
    )


def get_latency(db: Session, days: int = 30) -> list[LatencyPoint]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(WorkflowRun.workflow_name, WorkflowRun.duration_ms)
        .filter(WorkflowRun.duration_ms.isnot(None))
        .filter(WorkflowRun.started_at >= cutoff)
        .all()
    )

    by_wf: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        by_wf[row.workflow_name].append(float(row.duration_ms))

    result = []
    for wf_name, durations in by_wf.items():
        durations.sort()
        n   = len(durations)
        avg = sum(durations) / n
        p95 = durations[min(int(n * 0.95), n - 1)]
        result.append(
            LatencyPoint(
                workflow_name=wf_name,
                avg_latency_ms=round(avg, 1),
                p95_latency_ms=round(p95, 1),
                run_count=n,
            )
        )
    return result


def get_cost(db: Session, days: int = 30) -> list[CostPoint]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = (
        db.query(
            LLMCall.model,
            func.sum(LLMCall.estimated_cost).label("total_cost"),
            func.count(LLMCall.id).label("call_count"),
        )
        .filter(LLMCall.estimated_cost.isnot(None))
        .filter(LLMCall.created_at >= cutoff)
        .group_by(LLMCall.model)
        .order_by(func.sum(LLMCall.estimated_cost).desc())
        .all()
    )
    return [
        CostPoint(
            model=row.model,
            total_cost=round(float(row.total_cost or 0), 6),
            call_count=row.call_count,
        )
        for row in rows
    ]


def get_failures(db: Session, days: int = 30) -> list[FailurePoint]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    total_q = (
        db.query(
            TraceStep.step_name,
            func.count(TraceStep.id).label("total"),
        )
        .filter(TraceStep.started_at >= cutoff)
        .group_by(TraceStep.step_name)
        .subquery()
    )

    failed_q = (
        db.query(
            TraceStep.step_name,
            func.count(TraceStep.id).label("failures"),
        )
        .filter(TraceStep.status == RunStatus.failed)
        .filter(TraceStep.started_at >= cutoff)
        .group_by(TraceStep.step_name)
        .subquery()
    )

    rows = (
        db.query(
            total_q.c.step_name,
            total_q.c.total,
            func.coalesce(failed_q.c.failures, 0).label("failures"),
        )
        .outerjoin(failed_q, total_q.c.step_name == failed_q.c.step_name)
        .order_by(func.coalesce(failed_q.c.failures, 0).desc())
        .all()
    )

    return [
        FailurePoint(
            step_name=row.step_name,
            failure_count=row.failures,
            total_count=row.total,
            failure_rate=round(row.failures / row.total, 4) if row.total > 0 else 0.0,
        )
        for row in rows
    ]


def get_success_rate_timeseries(db: Session, days: int = 14) -> list[TimeSeriesPoint]:
    """Returns daily success rate for the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    runs = (
        db.query(WorkflowRun.started_at, WorkflowRun.status)
        .filter(WorkflowRun.started_at >= cutoff)
        .all()
    )

    daily: dict[str, dict] = defaultdict(lambda: {"success": 0, "total": 0})
    for run in runs:
        day = run.started_at.strftime("%Y-%m-%d")
        daily[day]["total"] += 1
        if run.status == RunStatus.success:
            daily[day]["success"] += 1

    return [
        TimeSeriesPoint(
            date=day,
            value=round(v["success"] / v["total"], 4) if v["total"] > 0 else 0.0,
        )
        for day, v in sorted(daily.items())
    ]


def get_cost_timeseries(db: Session, days: int = 14) -> list[TimeSeriesPoint]:
    """Returns daily total cost for the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    calls = (
        db.query(LLMCall.created_at, LLMCall.estimated_cost)
        .filter(LLMCall.created_at >= cutoff)
        .filter(LLMCall.estimated_cost.isnot(None))
        .all()
    )

    daily: dict[str, float] = defaultdict(float)
    for call in calls:
        day = call.created_at.strftime("%Y-%m-%d")
        daily[day] += call.estimated_cost or 0

    return [
        TimeSeriesPoint(date=day, value=round(v, 6))
        for day, v in sorted(daily.items())
    ]


def get_latency_timeseries(db: Session, days: int = 14) -> list[TimeSeriesPoint]:
    """Returns daily average latency for the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    runs = (
        db.query(WorkflowRun.started_at, WorkflowRun.duration_ms)
        .filter(WorkflowRun.started_at >= cutoff)
        .filter(WorkflowRun.duration_ms.isnot(None))
        .all()
    )

    daily: dict[str, list] = defaultdict(list)
    for run in runs:
        day = run.started_at.strftime("%Y-%m-%d")
        daily[day].append(run.duration_ms)

    return [
        TimeSeriesPoint(date=day, value=round(sum(v) / len(v), 1))
        for day, v in sorted(daily.items())
    ]


def get_runs_timeseries(db: Session, days: int = 14) -> list[TimeSeriesPoint]:
    """Returns daily run count for the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    runs = (
        db.query(WorkflowRun.started_at)
        .filter(WorkflowRun.started_at >= cutoff)
        .all()
    )

    daily: dict[str, int] = defaultdict(int)
    for run in runs:
        day = run.started_at.strftime("%Y-%m-%d")
        daily[day] += 1

    return [
        TimeSeriesPoint(date=day, value=float(count))
        for day, count in sorted(daily.items())
    ]


def get_quality_timeseries(db: Session, days: int = 14) -> list[TimeSeriesPoint]:
    """Returns daily average quality score for the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    evals = (
        db.query(EvaluationResult.created_at, EvaluationResult.quality_score)
        .filter(EvaluationResult.created_at >= cutoff)
        .all()
    )

    daily: dict[str, list] = defaultdict(list)
    for ev in evals:
        day = ev.created_at.strftime("%Y-%m-%d")
        daily[day].append(ev.quality_score)

    return [
        TimeSeriesPoint(date=day, value=round(sum(v) / len(v), 4))
        for day, v in sorted(daily.items())
    ]


def get_tokens_timeseries(db: Session, days: int = 14) -> list[TimeSeriesPoint]:
    """Returns daily total token usage for the last N days."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    calls = (
        db.query(LLMCall.created_at, LLMCall.total_tokens)
        .filter(LLMCall.created_at >= cutoff)
        .filter(LLMCall.total_tokens.isnot(None))
        .all()
    )

    daily: dict[str, int] = defaultdict(int)
    for call in calls:
        day = call.created_at.strftime("%Y-%m-%d")
        daily[day] += call.total_tokens or 0

    return [
        TimeSeriesPoint(date=day, value=float(total))
        for day, total in sorted(daily.items())
    ]


def get_reliability_timeseries(
    db: Session,
    days: int = 14,
    workflow_name: str | None = None,
) -> list[TimeSeriesPoint]:
    """Daily average reliability score, optionally filtered by workflow."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    runs = (
        db.query(WorkflowRun.started_at, WorkflowRun.reliability_score)
        .filter(
            WorkflowRun.started_at >= cutoff,
            WorkflowRun.reliability_score.isnot(None),
        )
    )
    if workflow_name:
        runs = runs.filter(WorkflowRun.workflow_name == workflow_name)
    runs = runs.all()

    daily: dict[str, list[int]] = defaultdict(list)
    for run in runs:
        day = run.started_at.strftime("%Y-%m-%d")
        daily[day].append(run.reliability_score)

    return [
        TimeSeriesPoint(date=day, value=round(sum(scores) / len(scores), 1))
        for day, scores in sorted(daily.items())
    ]


def get_classification_breakdown(
    db: Session,
    days: int = 14,
    workflow_name: str | None = None,
) -> list[ClassificationBreakdownPoint]:
    """Count of each failure category over the last N days, ordered by frequency."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q = (
        db.query(
            FailureClassification.category,
            func.count(FailureClassification.id).label("cnt"),
        )
        .join(WorkflowRun, FailureClassification.run_id == WorkflowRun.id)
        .filter(WorkflowRun.started_at >= cutoff)
    )
    if workflow_name:
        q = q.filter(WorkflowRun.workflow_name == workflow_name)
    rows = q.group_by(FailureClassification.category).order_by(desc("cnt")).all()

    total = sum(r.cnt for r in rows) or 1
    return [
        ClassificationBreakdownPoint(
            category=r.category,
            count=r.cnt,
            pct=round(r.cnt / total * 100, 1),
        )
        for r in rows
    ]


def get_workflow_health(db: Session, days: int = 30) -> list[WorkflowHealth]:
    """
    Per-workflow health summary: reliability score, success rate, open incidents,
    top failure category, and a 7-day trend direction.
    """
    now       = datetime.now(timezone.utc)
    cutoff    = now - timedelta(days=days)
    cutoff_7  = now - timedelta(days=7)
    cutoff_14 = now - timedelta(days=14)

    # ── 1. All runs in the window ─────────────────────────────────────────────
    run_rows = (
        db.query(
            WorkflowRun.workflow_name,
            WorkflowRun.status,
            WorkflowRun.reliability_score,
            WorkflowRun.started_at,
        )
        .filter(WorkflowRun.started_at >= cutoff)
        .all()
    )

    by_wf: dict[str, dict] = {}
    for row in run_rows:
        wf = row.workflow_name
        if wf not in by_wf:
            by_wf[wf] = {
                "run_count": 0, "success_count": 0,
                "scores": [], "recent_scores": [], "prior_scores": [],
            }
        d = by_wf[wf]
        d["run_count"] += 1
        if row.status == RunStatus.success:
            d["success_count"] += 1
        if row.reliability_score is not None:
            d["scores"].append(row.reliability_score)
            # Normalise to UTC-aware for comparison (SQLite returns naive datetimes)
            ts = row.started_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if ts >= cutoff_7:
                d["recent_scores"].append(row.reliability_score)
            elif ts >= cutoff_14:
                d["prior_scores"].append(row.reliability_score)

    # ── 2. Open incidents per workflow ────────────────────────────────────────
    inc_rows = (
        db.query(Incident.workflow_name, func.count(Incident.id).label("cnt"))
        .filter(
            Incident.status == IncidentStatus.OPEN.value,
            Incident.workflow_name.isnot(None),
        )
        .group_by(Incident.workflow_name)
        .all()
    )
    open_incidents: dict[str, int] = {r.workflow_name: r.cnt for r in inc_rows}

    # ── 3. Top failure category per workflow (last 14 days) ───────────────────
    cls_rows = (
        db.query(
            WorkflowRun.workflow_name,
            FailureClassification.category,
            func.count(FailureClassification.id).label("cnt"),
        )
        .join(FailureClassification, FailureClassification.run_id == WorkflowRun.id)
        .filter(WorkflowRun.started_at >= cutoff_14)
        .group_by(WorkflowRun.workflow_name, FailureClassification.category)
        .order_by(desc("cnt"))
        .all()
    )
    top_category: dict[str, str] = {}
    for row in cls_rows:
        if row.workflow_name not in top_category:
            top_category[row.workflow_name] = row.category

    # ── 4. Assemble results ───────────────────────────────────────────────────
    results: list[WorkflowHealth] = []
    for wf, d in sorted(by_wf.items()):
        scores        = d["scores"]
        recent_scores = d["recent_scores"]
        prior_scores  = d["prior_scores"]

        avg_rel = round(sum(scores) / len(scores), 1) if scores else None
        sr      = round(d["success_count"] / d["run_count"], 4) if d["run_count"] else 0.0

        # Trend
        if recent_scores and prior_scores:
            recent_avg = sum(recent_scores) / len(recent_scores)
            prior_avg  = sum(prior_scores)  / len(prior_scores)
            delta = round(recent_avg - prior_avg, 1)
            trend = "improving" if delta > 5 else ("degrading" if delta < -5 else "stable")
        else:
            delta = None
            trend = "insufficient_data"

        results.append(WorkflowHealth(
            workflow_name=wf,
            run_count=d["run_count"],
            avg_reliability_score=avg_rel,
            success_rate=sr,
            open_incidents=open_incidents.get(wf, 0),
            top_failure_category=top_category.get(wf),
            trend=trend,
            trend_delta=delta,
        ))

    # Sort: most runs first, then by name
    results.sort(key=lambda w: (-w.run_count, w.workflow_name))
    return results


def get_incident_summary(db: Session) -> IncidentSummary:
    """Count of incidents by status."""
    open_count = db.query(func.count(Incident.id)).filter(Incident.status == IncidentStatus.OPEN.value).scalar() or 0
    ack_count  = db.query(func.count(Incident.id)).filter(Incident.status == IncidentStatus.ACKNOWLEDGED.value).scalar() or 0
    res_count  = db.query(func.count(Incident.id)).filter(Incident.status == IncidentStatus.RESOLVED.value).scalar() or 0
    return IncidentSummary(
        open=open_count,
        acknowledged=ack_count,
        resolved=res_count,
        total=open_count + ack_count + res_count,
    )
