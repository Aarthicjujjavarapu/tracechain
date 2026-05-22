"""Tests for reliability analytics endpoints and PROMPT_REGRESSION detection."""
import pytest
from unittest.mock import MagicMock
from app.models import WorkflowRun, EvaluationResult, FailureCategory, FailureSeverity, RunStatus
from app.services.classification import classify_run


# ── Helpers ───────────────────────────────────────────────────────────────────

def _create_run(client, name="wf"):
    r = client.post("/runs", json={"workflow_name": name, "input_payload": {}})
    assert r.status_code == 201
    return r.json()["id"]


def _run(**kwargs):
    defaults = dict(
        id="run-1", workflow_name="wf", status=RunStatus.success,
        steps=[], llm_calls=[], evaluations=[],
        duration_ms=None, total_cost=None, error_message=None,
    )
    defaults.update(kwargs)
    run = MagicMock(spec=WorkflowRun)
    for k, v in defaults.items():
        setattr(run, k, v)
    return run


def _eval(**kwargs):
    defaults = dict(relevance_score=0.8, hallucination_risk=0.1, quality_score=0.9)
    defaults.update(kwargs)
    e = MagicMock(spec=EvaluationResult)
    for k, v in defaults.items():
        setattr(e, k, v)
    return e


# ── /metrics/timeseries/reliability ──────────────────────────────────────────

def test_reliability_timeseries_empty(client):
    r = client.get("/metrics/timeseries/reliability?days=7")
    assert r.status_code == 200
    assert r.json() == []


def test_reliability_timeseries_has_data(client):
    run_id = _create_run(client)
    client.post(f"/runs/{run_id}/complete", json={"output_payload": {}})

    r = client.get("/metrics/timeseries/reliability?days=7")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert "date" in data[0]
    assert 0 <= data[0]["value"] <= 100


def test_reliability_timeseries_workflow_filter(client):
    run_a = _create_run(client, "workflow_a")
    run_b = _create_run(client, "workflow_b")
    client.post(f"/runs/{run_a}/complete", json={"output_payload": {}})
    client.post(f"/runs/{run_b}/complete", json={"output_payload": {}})

    r = client.get("/metrics/timeseries/reliability?workflow_name=workflow_a")
    assert r.status_code == 200
    # Only workflow_a runs should contribute — data non-empty
    assert len(r.json()) >= 1


# ── /metrics/failures/classification ─────────────────────────────────────────

def test_classification_breakdown_empty(client):
    r = client.get("/metrics/failures/classification?days=7")
    assert r.status_code == 200
    assert r.json() == []


def test_classification_breakdown_has_categories(client):
    run_id = _create_run(client)
    # Timeout error → MODEL_TIMEOUT classification
    client.post(f"/runs/{run_id}/fail", json={"error_message": "Read timeout after 30s"})

    r = client.get("/metrics/failures/classification?days=7")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    categories = [d["category"] for d in data]
    assert "MODEL_TIMEOUT" in categories or "UNKNOWN_FAILURE" in categories

    for item in data:
        assert "category" in item
        assert "count" in item
        assert "pct" in item
        assert 0.0 <= item["pct"] <= 100.0


def test_classification_breakdown_pct_sums_to_100(client):
    run_id = _create_run(client)
    client.post(f"/runs/{run_id}/fail", json={"error_message": "rate limit 429"})

    r = client.get("/metrics/failures/classification?days=7")
    data = r.json()
    if data:
        total_pct = sum(d["pct"] for d in data)
        assert abs(total_pct - 100.0) < 1.0  # allow rounding


# ── /metrics/incidents/summary ────────────────────────────────────────────────

def test_incident_summary_empty(client):
    r = client.get("/metrics/incidents/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["open"] == 0
    assert data["acknowledged"] == 0
    assert data["resolved"] == 0
    assert data["total"] == 0


def test_incident_summary_counts(client):
    run_id = _create_run(client)
    client.post(f"/runs/{run_id}/fail", json={"error_message": "Read timeout"})

    r = client.get("/metrics/incidents/summary")
    assert r.status_code == 200
    data = r.json()
    assert data["open"] >= 1
    assert data["total"] == data["open"] + data["acknowledged"] + data["resolved"]


# ── PROMPT_REGRESSION detection ───────────────────────────────────────────────

def test_prompt_regression_not_fired_without_history():
    """Fewer than 5 historical runs → no PROMPT_REGRESSION."""
    ev = _eval(quality_score=0.2)
    run = _run(evaluations=[ev])

    mock_db = MagicMock()
    # Simulate 3 historical evals (below threshold of 5)
    hist_evals = [_eval(quality_score=0.9) for _ in range(3)]
    mock_db.query.return_value.join.return_value.filter.return_value.filter.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = hist_evals

    cats = [c.category for c in classify_run(mock_db, run)]
    assert FailureCategory.PROMPT_REGRESSION.value not in cats


def test_prompt_regression_not_fired_without_db():
    """Passing None for db → rule is skipped entirely."""
    ev = _eval(quality_score=0.1)
    run = _run(evaluations=[ev])
    cats = [c.category for c in classify_run(None, run)]
    assert FailureCategory.PROMPT_REGRESSION.value not in cats


def test_prompt_regression_not_fired_without_evals():
    """No evaluations on the current run → rule is skipped."""
    run = _run(evaluations=[])
    mock_db = MagicMock()
    cats = [c.category for c in classify_run(mock_db, run)]
    assert FailureCategory.PROMPT_REGRESSION.value not in cats


def _mock_db_with_history(hist_evals):
    """Build a MagicMock DB whose historical eval query returns hist_evals."""
    mock_db = MagicMock()
    (mock_db.query.return_value
        .join.return_value
        .filter.return_value
        .order_by.return_value
        .limit.return_value
        .all.return_value) = hist_evals
    return mock_db


def test_prompt_regression_fired_on_quality_drop():
    """Quality drops 0.65 below historical avg → PROMPT_REGRESSION CRITICAL."""
    ev = _eval(quality_score=0.2)
    run = _run(evaluations=[ev])
    hist_evals = [_eval(quality_score=0.85) for _ in range(10)]

    results = classify_run(_mock_db_with_history(hist_evals), run)
    cats = [c.category for c in results]
    assert FailureCategory.PROMPT_REGRESSION.value in cats

    reg = next(c for c in results if c.category == FailureCategory.PROMPT_REGRESSION.value)
    assert reg.severity == FailureSeverity.CRITICAL.value


def test_prompt_regression_high_severity_on_moderate_drop():
    """Quality drops 0.25 below historical avg → PROMPT_REGRESSION HIGH."""
    ev = _eval(quality_score=0.6)
    run = _run(evaluations=[ev])
    hist_evals = [_eval(quality_score=0.85) for _ in range(10)]

    results = classify_run(_mock_db_with_history(hist_evals), run)
    cats = [c.category for c in results]
    assert FailureCategory.PROMPT_REGRESSION.value in cats

    reg = next(c for c in results if c.category == FailureCategory.PROMPT_REGRESSION.value)
    assert reg.severity == FailureSeverity.HIGH.value


def test_prompt_regression_not_fired_when_quality_ok():
    """Current quality close to historical avg → no regression."""
    ev = _eval(quality_score=0.82)
    run = _run(evaluations=[ev])
    hist_evals = [_eval(quality_score=0.85) for _ in range(10)]

    cats = [c.category for c in classify_run(_mock_db_with_history(hist_evals), run)]
    assert FailureCategory.PROMPT_REGRESSION.value not in cats
