"""Cost budget service — compute spend vs. defined limits."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ..models import CostBudget, WorkflowRun
from ..schemas import BudgetCreate, BudgetUpdate


def _normalize(ts: datetime) -> datetime:
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


def _sum_cost(
    db: Session,
    workflow_name: str | None,
    window_start: datetime | None,
) -> tuple[float, int]:
    """Return (total_cost_usd, run_count) for runs in the window."""
    q = db.query(WorkflowRun).filter(
        WorkflowRun.total_cost.isnot(None),
        WorkflowRun.ended_at.isnot(None),
    )
    if workflow_name:
        q = q.filter(WorkflowRun.workflow_name == workflow_name)

    rows = q.all()
    if window_start:
        rows = [r for r in rows if _normalize(r.ended_at) >= window_start]

    total = sum(r.total_cost for r in rows if r.total_cost is not None)
    return round(total, 6), len(rows)


def _window_start(period: str, now: datetime) -> datetime | None:
    if period == "daily":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "monthly":
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return None  # "total" — no window


def get_budget_status(db: Session, budget: CostBudget) -> dict:
    now   = datetime.now(timezone.utc)
    ws    = _window_start(budget.period, now)
    spent, _ = _sum_cost(db, budget.workflow_name, ws)

    pct_used = spent / budget.budget_usd if budget.budget_usd > 0 else 0.0

    if pct_used >= 1.0:
        status = "exceeded"
    elif pct_used >= 0.90:
        status = "critical"
    elif pct_used >= budget.warning_pct:
        status = "warning"
    else:
        status = "ok"

    projected = None
    if ws is not None and spent > 0:
        elapsed_s = (now - ws).total_seconds()
        if elapsed_s > 0:
            if budget.period == "daily":
                projected = round(spent / elapsed_s * 86_400 * 30, 6)
            elif budget.period == "monthly":
                day = now.day
                if day > 1:
                    projected = round(spent / day * 30, 6)

    return {
        "id":                    budget.id,
        "name":                  budget.name,
        "workflow_name":         budget.workflow_name,
        "budget_usd":            budget.budget_usd,
        "period":                budget.period,
        "warning_pct":           budget.warning_pct,
        "enabled":               budget.enabled,
        "created_at":            budget.created_at,
        "spent":                 round(spent, 6),
        "remaining":             round(max(0.0, budget.budget_usd - spent), 6),
        "pct_used":              round(min(1.0, pct_used), 4),
        "status":                status,
        "projected_monthly_usd": projected,
        "window_start":          ws.isoformat() if ws else None,
    }


def get_spend_summary(db: Session) -> dict:
    now         = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    rows = db.query(WorkflowRun).filter(
        WorkflowRun.total_cost.isnot(None),
        WorkflowRun.ended_at.isnot(None),
    ).all()

    def _cost(r: WorkflowRun) -> float:
        return r.total_cost or 0.0

    all_time = [r for r in rows]
    monthly  = [r for r in rows if _normalize(r.ended_at) >= month_start]
    daily    = [r for r in rows if _normalize(r.ended_at) >= today_start]

    return {
        "today_usd":       round(sum(_cost(r) for r in daily),    6),
        "month_usd":       round(sum(_cost(r) for r in monthly),  6),
        "all_time_usd":    round(sum(_cost(r) for r in all_time), 6),
        "run_count_today": len(daily),
        "run_count_month": len(monthly),
    }


# ── CRUD ──────────────────────────────────────────────────────────────────────

def list_budgets(db: Session) -> list[CostBudget]:
    return db.query(CostBudget).order_by(CostBudget.created_at.desc()).all()


def create_budget(db: Session, data: BudgetCreate) -> CostBudget:
    b = CostBudget(
        name=data.name,
        workflow_name=data.workflow_name,
        budget_usd=data.budget_usd,
        period=data.period,
        warning_pct=data.warning_pct,
        enabled=data.enabled,
    )
    db.add(b)
    db.commit()
    db.refresh(b)
    return b


def update_budget(db: Session, budget_id: str, data: BudgetUpdate) -> CostBudget | None:
    b = db.query(CostBudget).filter(CostBudget.id == budget_id).first()
    if not b:
        return None
    for field in ("name", "budget_usd", "period", "warning_pct", "enabled"):
        val = getattr(data, field)
        if val is not None:
            setattr(b, field, val)
    db.commit()
    db.refresh(b)
    return b


def delete_budget(db: Session, budget_id: str) -> bool:
    b = db.query(CostBudget).filter(CostBudget.id == budget_id).first()
    if not b:
        return False
    db.delete(b)
    db.commit()
    return True
