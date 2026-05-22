"""
Rule-based failure classification for workflow runs.

Each rule inspects the run + its steps/llm_calls/evaluations and returns
zero or more FailureClassification records. Rules are additive — a single run
can have multiple classifications (e.g. RETRY_LOOP + LATENCY_SPIKE).
"""
from __future__ import annotations
from typing import Any
from sqlalchemy.orm import Session

from ..models import (
    WorkflowRun, TraceStep, LLMCall, EvaluationResult,
    FailureClassification, FailureCategory, FailureSeverity, RunStatus,
)

# Model token limits used for CONTEXT_WINDOW_RISK detection
_MODEL_MAX_TOKENS: dict[str, int] = {
    "gpt-4o":              128_000,
    "gpt-4o-mini":         128_000,
    "gpt-4-turbo":         128_000,
    "gpt-4":                8_192,
    "gpt-3.5-turbo":       16_385,
    "claude-opus-4":       200_000,
    "claude-opus-4-5":     200_000,
    "claude-3-5-sonnet":   200_000,
    "claude-3-5-haiku":    200_000,
    "claude-sonnet-4-6":   200_000,
    "claude-haiku-4-5":    200_000,
}

_LATENCY_HIGH_MS   = 30_000
_LATENCY_MEDIUM_MS = 10_000
_COST_HIGH         = 1.00
_COST_MEDIUM       = 0.25


def _make(
    run_id: str,
    category: FailureCategory,
    severity: FailureSeverity,
    evidence: dict[str, Any],
    recommendation: str,
    step_id: str | None = None,
) -> FailureClassification:
    return FailureClassification(
        run_id=run_id,
        step_id=step_id,
        category=category.value,
        severity=severity.value,
        evidence=evidence,
        recommendation=recommendation,
    )


def classify_run(db: Session, run: WorkflowRun) -> list[FailureClassification]:
    steps: list[TraceStep]       = run.steps      or []
    calls: list[LLMCall]         = run.llm_calls  or []
    evals: list[EvaluationResult] = run.evaluations or []

    results: list[FailureClassification] = []

    # ── RETRY_LOOP ─────────────────────────────────────────────────────────────
    for step in steps:
        if step.retry_count and step.retry_count >= 3:
            sev = FailureSeverity.HIGH if step.retry_count >= 5 else FailureSeverity.MEDIUM
            results.append(_make(
                run.id, FailureCategory.RETRY_LOOP, sev,
                {"step_name": step.step_name, "retry_count": step.retry_count},
                "Add exponential backoff and investigate the root cause of repeated failures.",
                step_id=step.id,
            ))

    # ── MODEL_TIMEOUT ──────────────────────────────────────────────────────────
    _timeout_keywords = ("timeout", "timed out", "read timeout", "connect timeout")
    for step in steps:
        if step.error_message and any(k in step.error_message.lower() for k in _timeout_keywords):
            results.append(_make(
                run.id, FailureCategory.MODEL_TIMEOUT, FailureSeverity.MEDIUM,
                {"step_name": step.step_name, "error": step.error_message[:300]},
                "Increase request timeout or switch to a lower-latency model/endpoint.",
                step_id=step.id,
            ))
    for call in calls:
        if call.error_message and any(k in call.error_message.lower() for k in _timeout_keywords):
            results.append(_make(
                run.id, FailureCategory.MODEL_TIMEOUT, FailureSeverity.MEDIUM,
                {"model": call.model, "error": call.error_message[:300]},
                "Increase request timeout or switch to a lower-latency model/endpoint.",
            ))

    # ── MODEL_RATE_LIMIT ───────────────────────────────────────────────────────
    _rate_keywords = ("rate limit", "ratelimit", "429", "too many requests", "quota")
    for step in steps:
        if step.error_message and any(k in step.error_message.lower() for k in _rate_keywords):
            results.append(_make(
                run.id, FailureCategory.MODEL_RATE_LIMIT, FailureSeverity.HIGH,
                {"step_name": step.step_name, "error": step.error_message[:300]},
                "Implement request queuing with exponential backoff and respect provider rate limits.",
                step_id=step.id,
            ))
    for call in calls:
        if call.error_message and any(k in call.error_message.lower() for k in _rate_keywords):
            results.append(_make(
                run.id, FailureCategory.MODEL_RATE_LIMIT, FailureSeverity.HIGH,
                {"model": call.model, "error": call.error_message[:300]},
                "Implement request queuing with exponential backoff and respect provider rate limits.",
            ))

    # ── OUTPUT_TRUNCATION ──────────────────────────────────────────────────────
    for call in calls:
        if call.output_tokens:
            # If output_tokens equals the model's max_tokens parameter it's likely truncated
            max_out = _MODEL_MAX_TOKENS.get(call.model, 4096)
            if call.output_tokens >= min(4096, max_out * 0.95):
                results.append(_make(
                    run.id, FailureCategory.OUTPUT_TRUNCATION, FailureSeverity.MEDIUM,
                    {"model": call.model, "output_tokens": call.output_tokens},
                    "Increase max_tokens or redesign the prompt to produce shorter outputs.",
                ))

    # ── CONTEXT_WINDOW_RISK ────────────────────────────────────────────────────
    for call in calls:
        if call.total_tokens and call.model in _MODEL_MAX_TOKENS:
            ratio = call.total_tokens / _MODEL_MAX_TOKENS[call.model]
            if ratio >= 0.8:
                sev = FailureSeverity.CRITICAL if ratio >= 0.95 else FailureSeverity.HIGH
                results.append(_make(
                    run.id, FailureCategory.CONTEXT_WINDOW_RISK, sev,
                    {
                        "model": call.model,
                        "total_tokens": call.total_tokens,
                        "max_tokens": _MODEL_MAX_TOKENS[call.model],
                        "utilization_pct": round(ratio * 100, 1),
                    },
                    "Reduce context size, add summarization, or switch to a model with a larger context window.",
                ))

    # ── RETRIEVAL_FAILURE ──────────────────────────────────────────────────────
    _retrieval_keywords = ("retriev", "vector", "embed", "search", "fetch_context", "rag")
    for step in steps:
        if (step.status == RunStatus.failed and step.step_name and
                any(k in step.step_name.lower() for k in _retrieval_keywords)):
            results.append(_make(
                run.id, FailureCategory.RETRIEVAL_FAILURE, FailureSeverity.HIGH,
                {"step_name": step.step_name, "error": step.error_message or ""},
                "Check retrieval system availability, index health, and query format.",
                step_id=step.id,
            ))

    # ── LOW_RELEVANCE_CONTEXT ──────────────────────────────────────────────────
    for ev in evals:
        if ev.relevance_score is not None and ev.relevance_score < 0.3:
            results.append(_make(
                run.id, FailureCategory.LOW_RELEVANCE_CONTEXT, FailureSeverity.HIGH,
                {"relevance_score": round(ev.relevance_score, 3)},
                "Review retrieval configuration, improve embedding quality, and tune top-k selection.",
            ))

    # ── HALLUCINATION_RISK ─────────────────────────────────────────────────────
    for ev in evals:
        if ev.hallucination_risk is not None and ev.hallucination_risk > 0.7:
            sev = FailureSeverity.CRITICAL if ev.hallucination_risk > 0.9 else FailureSeverity.HIGH
            results.append(_make(
                run.id, FailureCategory.HALLUCINATION_RISK, sev,
                {"hallucination_risk": round(ev.hallucination_risk, 3)},
                "Add output validation, grounding checks, and consider retrieval-augmented generation.",
            ))

    # ── TOOL_CALL_FAILURE ──────────────────────────────────────────────────────
    _tool_keywords = ("tool", "function_call", "action", "execute")
    for step in steps:
        if (step.status == RunStatus.failed and step.step_name and
                any(k in step.step_name.lower() for k in _tool_keywords)):
            results.append(_make(
                run.id, FailureCategory.TOOL_CALL_FAILURE, FailureSeverity.MEDIUM,
                {"step_name": step.step_name, "error": step.error_message or ""},
                "Validate tool arguments before calling and add schema enforcement.",
                step_id=step.id,
            ))

    # ── TOOL_ARGUMENT_ERROR ────────────────────────────────────────────────────
    _arg_keywords = ("argument", "invalid argument", "typeerror", "unexpected keyword", "missing required")
    for step in steps:
        if step.error_message and any(k in step.error_message.lower() for k in _arg_keywords):
            results.append(_make(
                run.id, FailureCategory.TOOL_ARGUMENT_ERROR, FailureSeverity.MEDIUM,
                {"step_name": step.step_name, "error": step.error_message[:300]},
                "Add Pydantic/JSON Schema validation for tool arguments before execution.",
                step_id=step.id,
            ))

    # ── VALIDATION_FAILURE ─────────────────────────────────────────────────────
    _val_keywords = ("validation", "validationerror", "schema", "invalid json", "parse error", "pydantic")
    for step in steps:
        if step.error_message and any(k in step.error_message.lower() for k in _val_keywords):
            results.append(_make(
                run.id, FailureCategory.VALIDATION_FAILURE, FailureSeverity.MEDIUM,
                {"step_name": step.step_name, "error": step.error_message[:300]},
                "Enforce structured output with response_format or output parsers.",
                step_id=step.id,
            ))

    # ── LATENCY_SPIKE ──────────────────────────────────────────────────────────
    if run.duration_ms and run.duration_ms > _LATENCY_MEDIUM_MS:
        sev = FailureSeverity.HIGH if run.duration_ms > _LATENCY_HIGH_MS else FailureSeverity.MEDIUM
        # Find the slowest step
        slowest = max(steps, key=lambda s: s.duration_ms or 0) if steps else None
        results.append(_make(
            run.id, FailureCategory.LATENCY_SPIKE, sev,
            {
                "duration_ms": run.duration_ms,
                "slowest_step": slowest.step_name if slowest else None,
                "slowest_step_ms": slowest.duration_ms if slowest else None,
            },
            "Profile the slowest steps, add caching layers, and consider async execution.",
        ))

    # ── COST_SPIKE ─────────────────────────────────────────────────────────────
    if run.total_cost and run.total_cost > _COST_MEDIUM:
        sev = FailureSeverity.HIGH if run.total_cost > _COST_HIGH else FailureSeverity.MEDIUM
        most_expensive_model = None
        if calls:
            model_costs: dict[str, float] = {}
            for c in calls:
                model_costs[c.model] = model_costs.get(c.model, 0) + (c.estimated_cost or 0)
            most_expensive_model = max(model_costs, key=lambda m: model_costs[m])
        results.append(_make(
            run.id, FailureCategory.COST_SPIKE, sev,
            {"total_cost_usd": round(run.total_cost, 5), "most_expensive_model": most_expensive_model},
            "Switch to a more cost-effective model for simpler tasks or add prompt caching.",
        ))

    # ── PROMPT_REGRESSION ─────────────────────────────────────────────────────
    # Compares current run quality against the rolling average of the last 30
    # successful runs for the same workflow.  Requires a live DB session.
    if db is not None and run.workflow_name and evals:
        current_quality_scores = [e.quality_score for e in evals if e.quality_score is not None]
        if current_quality_scores:
            current_quality = sum(current_quality_scores) / len(current_quality_scores)
            historical_evals = (
                db.query(EvaluationResult)
                .join(WorkflowRun, EvaluationResult.run_id == WorkflowRun.id)
                .filter(
                    WorkflowRun.workflow_name == run.workflow_name,
                    WorkflowRun.id            != run.id,
                    WorkflowRun.status        == RunStatus.success,
                )
                .order_by(WorkflowRun.started_at.desc())
                .limit(30)
                .all()
            )
            if len(historical_evals) >= 5:
                hist_scores = [e.quality_score for e in historical_evals if e.quality_score is not None]
                if hist_scores:
                    hist_avg = sum(hist_scores) / len(hist_scores)
                    delta = hist_avg - current_quality
                    if delta >= 0.2:
                        sev = FailureSeverity.CRITICAL if delta >= 0.4 else FailureSeverity.HIGH
                        results.append(_make(
                            run.id, FailureCategory.PROMPT_REGRESSION, sev,
                            {
                                "current_quality":     round(current_quality, 3),
                                "historical_avg":      round(hist_avg, 3),
                                "delta":               round(delta, 3),
                                "history_sample_size": len(hist_scores),
                            },
                            "Review recent prompt changes and roll back if quality dropped. "
                            "Compare prompt versions to identify the regression source.",
                        ))

    # ── UNKNOWN_FAILURE ────────────────────────────────────────────────────────
    if run.status == RunStatus.failed and not results:
        results.append(_make(
            run.id, FailureCategory.UNKNOWN_FAILURE, FailureSeverity.MEDIUM,
            {"error_message": run.error_message or ""},
            "Review application logs for the root cause and add specific error handling.",
        ))

    return results


def run_classification(db: Session, run_id: str) -> list[FailureClassification]:
    """Classify a run and persist results. Idempotent — deletes prior results first."""
    run = (
        db.query(WorkflowRun)
        .filter(WorkflowRun.id == run_id)
        .first()
    )
    if not run:
        return []

    # Clear stale classifications (synchronize_session=False avoids identity map corruption)
    db.query(FailureClassification).filter(
        FailureClassification.run_id == run_id
    ).delete(synchronize_session=False)
    db.flush()

    classifications = classify_run(db, run)
    for c in classifications:
        db.add(c)

    db.flush()

    return classifications
