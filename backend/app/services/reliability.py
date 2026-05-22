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

    # ── Latency ────────────────────────────────────────────────────────────────
    if run.duration_ms:
        if run.duration_ms > 60_000:
            score -= 15
            reasons.append(f"Severe latency spike ({run.duration_ms / 1000:.1f}s)")
        elif run.duration_ms > 30_000:
            score -= 10
            reasons.append(f"High latency ({run.duration_ms / 1000:.1f}s)")
        elif run.duration_ms > 10_000:
            score -= 5
            reasons.append(f"Elevated latency ({run.duration_ms / 1000:.1f}s)")

    # ── Cost ───────────────────────────────────────────────────────────────────
    if run.total_cost:
        if run.total_cost > 1.0:
            score -= 10
            reasons.append(f"Cost spike (${run.total_cost:.4f} per run)")
        elif run.total_cost > 0.25:
            score -= 5
            reasons.append(f"Elevated cost (${run.total_cost:.4f} per run)")

    # ── Evaluation scores ──────────────────────────────────────────────────────
    for ev in evals:
        if ev.hallucination_risk is not None:
            if ev.hallucination_risk > 0.9:
                score -= 20
                reasons.append(f"Critical hallucination risk ({ev.hallucination_risk:.0%})")
            elif ev.hallucination_risk > 0.7:
                score -= 10
                reasons.append(f"High hallucination risk ({ev.hallucination_risk:.0%})")
            elif ev.hallucination_risk > 0.5:
                score -= 5
                reasons.append(f"Elevated hallucination risk ({ev.hallucination_risk:.0%})")

        if ev.relevance_score is not None:
            if ev.relevance_score < 0.2:
                score -= 10
                reasons.append(f"Very low retrieval relevance ({ev.relevance_score:.0%})")
            elif ev.relevance_score < 0.4:
                score -= 5
                reasons.append(f"Low retrieval relevance ({ev.relevance_score:.0%})")

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
