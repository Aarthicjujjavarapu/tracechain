"""
Reliability scoring for workflow runs.

Produces a 0–100 score with an explanation list.
Score starts at 100 and penalties are subtracted based on observed signals.
"""
from __future__ import annotations
from sqlalchemy.orm import Session

from ..models import WorkflowRun, FailureClassification, FailureSeverity, RunStatus

_SEVERITY_PENALTY = {
    FailureSeverity.CRITICAL.value: 15,
    FailureSeverity.HIGH.value:     10,
    FailureSeverity.MEDIUM.value:    5,
    FailureSeverity.LOW.value:       2,
}


def compute_reliability(db: Session, run: WorkflowRun) -> tuple[int, list[str]]:
    score   = 100
    reasons: list[str] = []

    steps = run.steps     or []
    calls = run.llm_calls or []
    evals = run.evaluations or []

    # ── Run-level failure ──────────────────────────────────────────────────────
    if run.status == RunStatus.failed:
        score -= 20
        reasons.append("Run ended in failure")

    # ── Step failures ──────────────────────────────────────────────────────────
    failed_steps = [s for s in steps if s.status == RunStatus.failed]
    if failed_steps:
        penalty = min(5 * len(failed_steps), 20)
        score -= penalty
        reasons.append(f"{len(failed_steps)} step(s) failed")

    # ── Retry loops ────────────────────────────────────────────────────────────
    retried = [(s.step_name, s.retry_count) for s in steps if s.retry_count and s.retry_count > 0]
    if retried:
        total_retries = sum(r for _, r in retried)
        penalty = min(3 * total_retries, 15)
        score -= penalty
        reasons.append(f"High retry count ({total_retries} total retries across {len(retried)} step(s))")

    # ── Failure classifications ────────────────────────────────────────────────
    classifications: list[FailureClassification] = run.classifications or []
    for fc in classifications:
        penalty = _SEVERITY_PENALTY.get(fc.severity, 5)
        score -= penalty
        reasons.append(f"{fc.category.replace('_', ' ').title()} detected ({fc.severity})")

    score = max(0, min(100, score))
    return score, reasons


def score_run(db: Session, run_id: str) -> tuple[int, list[str]]:
    """Compute and persist reliability score. Returns (score, reasons)."""
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        return 0, []

    score, reasons = compute_reliability(db, run)

    run.reliability_score   = score
    run.reliability_reasons = reasons
    db.flush()

    return score, reasons
