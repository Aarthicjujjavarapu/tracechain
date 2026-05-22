"""Tests for GET /metrics/workflows — workflow health matrix endpoint."""
import pytest


def _create_and_complete(client, name="wf"):
    r = client.post("/runs", json={"workflow_name": name, "input_payload": {}})
    assert r.status_code == 201
    run_id = r.json()["id"]
    client.post(f"/runs/{run_id}/complete", json={"output_payload": {}})
    return run_id


def _create_and_fail(client, name="wf", error="something broke"):
    r = client.post("/runs", json={"workflow_name": name, "input_payload": {}})
    assert r.status_code == 201
    run_id = r.json()["id"]
    client.post(f"/runs/{run_id}/fail", json={"error_message": error})
    return run_id


# ── empty state ───────────────────────────────────────────────────────────────

def test_workflow_health_empty(client):
    r = client.get("/metrics/workflows")
    assert r.status_code == 200
    assert r.json() == []


# ── basic population ──────────────────────────────────────────────────────────

def test_workflow_health_returns_workflow_entry(client):
    _create_and_complete(client, "pipeline_a")
    r = client.get("/metrics/workflows")
    assert r.status_code == 200
    data = r.json()
    names = [w["workflow_name"] for w in data]
    assert "pipeline_a" in names


def test_workflow_health_schema_fields(client):
    _create_and_complete(client, "wf_schema")
    r = client.get("/metrics/workflows")
    wf = next(w for w in r.json() if w["workflow_name"] == "wf_schema")
    assert "run_count"             in wf
    assert "avg_reliability_score" in wf
    assert "success_rate"          in wf
    assert "open_incidents"        in wf
    assert "top_failure_category"  in wf
    assert "trend"                 in wf
    assert "trend_delta"           in wf


def test_workflow_health_run_count(client):
    for _ in range(3):
        _create_and_complete(client, "counted_wf")
    r = client.get("/metrics/workflows")
    wf = next(w for w in r.json() if w["workflow_name"] == "counted_wf")
    assert wf["run_count"] == 3


def test_workflow_health_success_rate_all_success(client):
    for _ in range(4):
        _create_and_complete(client, "all_good")
    r = client.get("/metrics/workflows")
    wf = next(w for w in r.json() if w["workflow_name"] == "all_good")
    assert wf["success_rate"] == 1.0


def test_workflow_health_success_rate_mixed(client):
    _create_and_complete(client, "mixed")
    _create_and_fail(client, "mixed")
    r = client.get("/metrics/workflows")
    wf = next(w for w in r.json() if w["workflow_name"] == "mixed")
    assert abs(wf["success_rate"] - 0.5) < 0.01


def test_workflow_health_reliability_score_present(client):
    _create_and_complete(client, "scored_wf")
    r = client.get("/metrics/workflows")
    wf = next(w for w in r.json() if w["workflow_name"] == "scored_wf")
    if wf["avg_reliability_score"] is not None:
        assert 0 <= wf["avg_reliability_score"] <= 100


# ── open incidents ────────────────────────────────────────────────────────────

def test_workflow_health_open_incidents_zero_when_no_failures(client):
    _create_and_complete(client, "healthy_wf")
    r = client.get("/metrics/workflows")
    wf = next(w for w in r.json() if w["workflow_name"] == "healthy_wf")
    assert wf["open_incidents"] == 0


def test_workflow_health_open_incidents_counted(client):
    _create_and_fail(client, "incident_wf", "Read timeout after 30s")
    r = client.get("/metrics/workflows")
    wf = next(w for w in r.json() if w["workflow_name"] == "incident_wf")
    assert wf["open_incidents"] >= 1


# ── top failure category ──────────────────────────────────────────────────────

def test_workflow_health_top_failure_category_on_timeout(client):
    _create_and_fail(client, "timeout_wf", "Read timeout after 30s")
    r = client.get("/metrics/workflows")
    wf = next(w for w in r.json() if w["workflow_name"] == "timeout_wf")
    assert wf["top_failure_category"] is not None


def test_workflow_health_top_failure_category_none_when_no_failures(client):
    _create_and_complete(client, "clean_wf")
    r = client.get("/metrics/workflows")
    wf = next(w for w in r.json() if w["workflow_name"] == "clean_wf")
    # successful run with no classifications → top_failure_category is None
    assert wf["top_failure_category"] is None


# ── multiple workflows ────────────────────────────────────────────────────────

def test_workflow_health_multiple_workflows(client):
    for name in ["alpha", "beta", "gamma"]:
        _create_and_complete(client, name)
    r = client.get("/metrics/workflows")
    names = [w["workflow_name"] for w in r.json()]
    for n in ["alpha", "beta", "gamma"]:
        assert n in names


def test_workflow_health_sorted_by_run_count_desc(client):
    _create_and_complete(client, "busy")
    _create_and_complete(client, "busy")
    _create_and_complete(client, "busy")
    _create_and_complete(client, "quiet")
    r = client.get("/metrics/workflows")
    data = r.json()
    busy_idx  = next(i for i, w in enumerate(data) if w["workflow_name"] == "busy")
    quiet_idx = next(i for i, w in enumerate(data) if w["workflow_name"] == "quiet")
    assert busy_idx < quiet_idx


# ── trend ─────────────────────────────────────────────────────────────────────

def test_workflow_health_trend_is_valid_value(client):
    _create_and_complete(client, "trend_wf")
    r = client.get("/metrics/workflows")
    wf = next(w for w in r.json() if w["workflow_name"] == "trend_wf")
    assert wf["trend"] in ("improving", "degrading", "stable", "insufficient_data")


def test_workflow_health_days_filter(client):
    _create_and_complete(client, "recent_wf")
    r = client.get("/metrics/workflows?days=1")
    assert r.status_code == 200
    # The run was just created so it should appear within 1-day window
    names = [w["workflow_name"] for w in r.json()]
    assert "recent_wf" in names
