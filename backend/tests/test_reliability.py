"""Tests for the reliability scoring service."""
import pytest
from unittest.mock import MagicMock
from app.models import WorkflowRun, TraceStep, EvaluationResult, FailureClassification, RunStatus
from app.services.reliability import compute_reliability


def _run(**kwargs) -> WorkflowRun:
    defaults = dict(
        id="run-1", status=RunStatus.success,
        steps=[], llm_calls=[], evaluations=[], classifications=[],
        duration_ms=None, total_cost=None, error_message=None,
    )
    defaults.update(kwargs)
    run = MagicMock(spec=WorkflowRun)
    for k, v in defaults.items():
        setattr(run, k, v)
    return run


def _step(**kwargs) -> TraceStep:
    defaults = dict(id="s-1", step_name="step", status=RunStatus.success, retry_count=0)
    defaults.update(kwargs)
    s = MagicMock(spec=TraceStep)
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


def _eval(**kwargs) -> EvaluationResult:
    defaults = dict(relevance_score=0.8, hallucination_risk=0.1)
    defaults.update(kwargs)
    e = MagicMock(spec=EvaluationResult)
    for k, v in defaults.items():
        setattr(e, k, v)
    return e


def _cls(severity: str) -> FailureClassification:
    c = MagicMock(spec=FailureClassification)
    c.severity = severity
    c.category = "LATENCY_SPIKE"
    return c


# ── Perfect run ───────────────────────────────────────────────────────────────

def test_perfect_run_scores_100():
    run = _run(status=RunStatus.success)
    score, reasons = compute_reliability(None, run)
    assert score == 100
    assert reasons == []


# ── Failed run ────────────────────────────────────────────────────────────────

def test_failed_run_penalty():
    run = _run(status=RunStatus.failed)
    score, _ = compute_reliability(None, run)
    assert score <= 80


def test_failed_steps_penalty():
    steps = [_step(status=RunStatus.failed), _step(status=RunStatus.failed)]
    run   = _run(steps=steps)
    score, reasons = compute_reliability(None, run)
    assert score < 100
    assert any("failed" in r for r in reasons)


# ── Retries ───────────────────────────────────────────────────────────────────

def test_retry_penalty():
    step = _step(retry_count=5)
    run  = _run(steps=[step])
    score, reasons = compute_reliability(None, run)
    assert score < 100
    assert any("retry" in r.lower() for r in reasons)


# ── No direct-signal double-penalty ───────────────────────────────────────────
# Latency, cost, hallucination, and relevance are captured by classifications.
# Without a matching classification the raw signal alone must NOT reduce the score.

def test_latency_alone_no_penalty():
    """High duration_ms without a classification must not subtract points."""
    run = _run(duration_ms=90_000)
    score, _ = compute_reliability(None, run)
    assert score == 100


def test_cost_alone_no_penalty():
    run = _run(total_cost=5.0)
    score, _ = compute_reliability(None, run)
    assert score == 100


def test_hallucination_alone_no_penalty():
    ev  = _eval(hallucination_risk=0.99)
    run = _run(evaluations=[ev])
    score, _ = compute_reliability(None, run)
    assert score == 100


def test_low_relevance_alone_no_penalty():
    ev  = _eval(relevance_score=0.01)
    run = _run(evaluations=[ev])
    score, _ = compute_reliability(None, run)
    assert score == 100


def test_no_double_penalty_hallucination_with_classification():
    """A hallucination signal covered by a CRITICAL classification should only
    subtract the classification penalty (15 pts), not 15 + 20."""
    cls = _cls("CRITICAL")
    cls.category = "HALLUCINATION_RISK"
    ev  = _eval(hallucination_risk=0.99)
    run = _run(evaluations=[ev], classifications=[cls])
    score, _ = compute_reliability(None, run)
    assert score == 85  # 100 - 15 (CRITICAL), not 100 - 15 - 20


# ── Severity penalties ────────────────────────────────────────────────────────

def test_critical_classification_penalty():
    cls = _cls("CRITICAL")
    run = _run(classifications=[cls])
    score, _ = compute_reliability(None, run)
    assert score <= 85


def test_score_never_below_zero():
    step = _step(status=RunStatus.failed, retry_count=10)
    ev   = _eval(hallucination_risk=0.99, relevance_score=0.01)
    clss = [_cls("CRITICAL")] * 5
    run  = _run(
        status=RunStatus.failed,
        steps=[step] * 5,
        evaluations=[ev],
        classifications=clss,
        duration_ms=90_000,
        total_cost=5.0,
    )
    score, _ = compute_reliability(None, run)
    assert score >= 0


def test_score_never_above_100():
    run = _run()
    score, _ = compute_reliability(None, run)
    assert score <= 100
