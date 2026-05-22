"""Tests for the failure classification engine."""
import pytest
from unittest.mock import MagicMock
from app.models import (
    WorkflowRun, TraceStep, LLMCall, EvaluationResult,
    FailureCategory, FailureSeverity, RunStatus,
)
from app.services.classification import classify_run


def _run(**kwargs) -> WorkflowRun:
    defaults = dict(
        id="run-1", workflow_name="test_wf", status=RunStatus.failed,
        steps=[], llm_calls=[], evaluations=[],
        duration_ms=None, total_cost=None, error_message=None,
    )
    defaults.update(kwargs)
    run = MagicMock(spec=WorkflowRun)
    for k, v in defaults.items():
        setattr(run, k, v)
    return run


def _step(**kwargs) -> TraceStep:
    defaults = dict(
        id="step-1", step_name="my_step", status=RunStatus.failed,
        retry_count=0, duration_ms=None, error_message=None,
    )
    defaults.update(kwargs)
    s = MagicMock(spec=TraceStep)
    for k, v in defaults.items():
        setattr(s, k, v)
    return s


def _call(**kwargs) -> LLMCall:
    defaults = dict(
        model="gpt-4o-mini", input_tokens=100, output_tokens=50,
        total_tokens=150, estimated_cost=0.001, error_message=None,
    )
    defaults.update(kwargs)
    c = MagicMock(spec=LLMCall)
    for k, v in defaults.items():
        setattr(c, k, v)
    return c


def _eval(**kwargs) -> EvaluationResult:
    defaults = dict(relevance_score=0.8, hallucination_risk=0.1)
    defaults.update(kwargs)
    e = MagicMock(spec=EvaluationResult)
    for k, v in defaults.items():
        setattr(e, k, v)
    return e


# ── RETRY_LOOP ────────────────────────────────────────────────────────────────

def test_retry_loop_medium():
    step = _step(retry_count=3)
    run  = _run(steps=[step], status=RunStatus.failed)
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.RETRY_LOOP.value in cats


def test_retry_loop_high_severity():
    step = _step(retry_count=6)
    run  = _run(steps=[step], status=RunStatus.failed)
    results = classify_run(None, run)
    retry = next(c for c in results if c.category == FailureCategory.RETRY_LOOP.value)
    assert retry.severity == FailureSeverity.HIGH.value


def test_no_retry_loop_below_threshold():
    step = _step(retry_count=2)
    run  = _run(steps=[step], status=RunStatus.failed)
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.RETRY_LOOP.value not in cats


# ── MODEL_TIMEOUT ─────────────────────────────────────────────────────────────

def test_model_timeout_from_step_error():
    step = _step(error_message="Read timeout after 30s")
    run  = _run(steps=[step])
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.MODEL_TIMEOUT.value in cats


def test_model_timeout_from_llm_error():
    call = _call(error_message="Request timed out")
    run  = _run(llm_calls=[call])
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.MODEL_TIMEOUT.value in cats


# ── MODEL_RATE_LIMIT ──────────────────────────────────────────────────────────

def test_rate_limit_detected():
    step = _step(error_message="RateLimitError: 429 too many requests")
    run  = _run(steps=[step])
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.MODEL_RATE_LIMIT.value in cats


# ── CONTEXT_WINDOW_RISK ───────────────────────────────────────────────────────

def test_context_window_risk_high():
    # gpt-4o-mini has 128k context; 110k tokens = 85.9%
    call = _call(model="gpt-4o-mini", total_tokens=110_000)
    run  = _run(llm_calls=[call])
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.CONTEXT_WINDOW_RISK.value in cats


def test_context_window_no_risk():
    call = _call(model="gpt-4o-mini", total_tokens=1_000)
    run  = _run(llm_calls=[call])
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.CONTEXT_WINDOW_RISK.value not in cats


# ── RETRIEVAL_FAILURE ─────────────────────────────────────────────────────────

def test_retrieval_failure():
    step = _step(step_name="retrieve_docs", status=RunStatus.failed)
    run  = _run(steps=[step])
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.RETRIEVAL_FAILURE.value in cats


# ── LOW_RELEVANCE_CONTEXT ─────────────────────────────────────────────────────

def test_low_relevance():
    ev  = _eval(relevance_score=0.1)
    run = _run(evaluations=[ev])
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.LOW_RELEVANCE_CONTEXT.value in cats


# ── HALLUCINATION_RISK ────────────────────────────────────────────────────────

def test_hallucination_risk_critical():
    ev  = _eval(hallucination_risk=0.95)
    run = _run(evaluations=[ev])
    results = classify_run(None, run)
    hall = next(c for c in results if c.category == FailureCategory.HALLUCINATION_RISK.value)
    assert hall.severity == FailureSeverity.CRITICAL.value


# ── LATENCY_SPIKE ─────────────────────────────────────────────────────────────

def test_latency_spike_medium():
    run = _run(duration_ms=15_000)
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.LATENCY_SPIKE.value in cats


def test_latency_spike_high():
    run = _run(duration_ms=45_000)
    results = classify_run(None, run)
    lat = next(c for c in results if c.category == FailureCategory.LATENCY_SPIKE.value)
    assert lat.severity == FailureSeverity.HIGH.value


# ── COST_SPIKE ────────────────────────────────────────────────────────────────

def test_cost_spike():
    run = _run(total_cost=1.50)
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.COST_SPIKE.value in cats


# ── UNKNOWN_FAILURE ───────────────────────────────────────────────────────────

def test_unknown_failure_fallback():
    run = _run(status=RunStatus.failed, error_message="something weird happened")
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.UNKNOWN_FAILURE.value in cats


def test_no_unknown_when_classified():
    step = _step(error_message="Read timeout after 30s")
    run  = _run(steps=[step], status=RunStatus.failed)
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.UNKNOWN_FAILURE.value not in cats


# ── Multiple classifications ──────────────────────────────────────────────────

def test_multiple_classifications():
    step = _step(retry_count=4, error_message="timeout")
    run  = _run(steps=[step], duration_ms=45_000, total_cost=0.30, status=RunStatus.failed)
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.RETRY_LOOP.value   in cats
    assert FailureCategory.MODEL_TIMEOUT.value in cats
    assert FailureCategory.LATENCY_SPIKE.value in cats
    assert FailureCategory.COST_SPIKE.value    in cats
