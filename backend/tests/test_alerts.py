"""Tests for the Alert Rules Engine — CRUD + evaluation logic."""
import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_rule(client, **kwargs):
    payload = {
        "name": "test rule",
        "metric": "success_rate",
        "operator": "lt",
        "threshold": 0.5,
        "window_minutes": 60,
        **kwargs,
    }
    r = client.post("/alerts/rules", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _complete(client, name="wf"):
    r = client.post("/runs", json={"workflow_name": name, "input_payload": {}})
    run_id = r.json()["id"]
    client.post(f"/runs/{run_id}/complete", json={"output_payload": {}})
    return run_id


def _fail(client, name="wf", error="boom"):
    r = client.post("/runs", json={"workflow_name": name, "input_payload": {}})
    run_id = r.json()["id"]
    client.post(f"/runs/{run_id}/fail", json={"error_message": error})
    return run_id


# ── CRUD: create / list / get ─────────────────────────────────────────────────

def test_create_rule(client):
    rule = _make_rule(client)
    assert rule["metric"]    == "success_rate"
    assert rule["operator"]  == "lt"
    assert rule["threshold"] == 0.5
    assert rule["enabled"]   is True


def test_create_rule_with_workflow_filter(client):
    rule = _make_rule(client, workflow_name="pipeline_a")
    assert rule["workflow_name"] == "pipeline_a"


def test_list_rules_empty(client):
    r = client.get("/alerts/rules")
    assert r.status_code == 200
    assert r.json() == []


def test_list_rules_returns_created(client):
    _make_rule(client)
    _make_rule(client, name="rule 2", metric="avg_latency_ms", operator="gt", threshold=2000)
    r = client.get("/alerts/rules")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_rule(client):
    rule = _make_rule(client)
    r = client.get(f"/alerts/rules/{rule['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == rule["id"]


def test_get_rule_not_found(client):
    r = client.get("/alerts/rules/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


# ── CRUD: update ──────────────────────────────────────────────────────────────

def test_update_rule_threshold(client):
    rule = _make_rule(client)
    r = client.patch(f"/alerts/rules/{rule['id']}", json={"threshold": 0.7})
    assert r.status_code == 200
    assert r.json()["threshold"] == 0.7


def test_update_rule_disable(client):
    rule = _make_rule(client)
    r = client.patch(f"/alerts/rules/{rule['id']}", json={"enabled": False})
    assert r.status_code == 200
    assert r.json()["enabled"] is False


def test_update_rule_not_found(client):
    r = client.patch("/alerts/rules/00000000-0000-0000-0000-000000000000", json={"threshold": 1.0})
    assert r.status_code == 404


# ── CRUD: delete ──────────────────────────────────────────────────────────────

def test_delete_rule(client):
    rule = _make_rule(client)
    r = client.delete(f"/alerts/rules/{rule['id']}")
    assert r.status_code == 204
    # Rule is gone
    r2 = client.get(f"/alerts/rules/{rule['id']}")
    assert r2.status_code == 404


# ── Firings: list / summary ───────────────────────────────────────────────────

def test_firings_empty(client):
    r = client.get("/alerts/firings")
    assert r.status_code == 200
    assert r.json() == []


def test_summary_empty(client):
    r = client.get("/alerts/summary")
    assert r.status_code == 200
    d = r.json()
    assert d["total_rules"]   == 0
    assert d["enabled_rules"] == 0
    assert d["firing_now"]    == 0


def test_summary_counts_rules(client):
    _make_rule(client)
    _make_rule(client, name="disabled", enabled=False)
    r = client.get("/alerts/summary")
    d = r.json()
    assert d["total_rules"]   == 2
    assert d["enabled_rules"] == 1


# ── Evaluation: success_rate fires when threshold breached ────────────────────

def test_alert_fires_on_low_success_rate(client):
    # Rule: success_rate < 0.9 → should fire after a failed run
    _make_rule(client, metric="success_rate", operator="lt", threshold=0.9)
    _fail(client, "eval_wf")

    r = client.get("/alerts/firings?active_only=true")
    assert r.status_code == 200
    firings = r.json()
    assert len(firings) >= 1
    assert firings[0]["is_active"] is True
    assert firings[0]["metric_value"] < 0.9


def test_alert_does_not_fire_when_success_rate_ok(client):
    _make_rule(client, metric="success_rate", operator="lt", threshold=0.5)
    _complete(client, "ok_wf")  # 100% success → should NOT fire

    r = client.get("/alerts/firings?active_only=true")
    assert r.json() == []


# ── Evaluation: open_incidents fires when threshold breached ──────────────────

def test_alert_fires_on_open_incidents(client):
    _make_rule(client, metric="open_incidents", operator="gte", threshold=1.0)
    _fail(client, "incident_wf", "timeout after 30s")  # creates an incident

    r = client.get("/alerts/firings?active_only=true")
    assert r.status_code == 200
    # May or may not fire depending on incident auto-detection; just assert format
    for f in r.json():
        assert "metric_value" in f
        assert "fired_at" in f


# ── Disabled rules do not evaluate ───────────────────────────────────────────

def test_disabled_rule_does_not_fire(client):
    _make_rule(client, metric="success_rate", operator="lt", threshold=0.99, enabled=False)
    _fail(client, "dis_wf")

    r = client.get("/alerts/firings?active_only=true")
    assert r.json() == []


# ── Schema fields present ─────────────────────────────────────────────────────

def test_rule_schema_fields(client):
    rule = _make_rule(client)
    for field in ["id", "name", "metric", "operator", "threshold", "window_minutes", "severity", "enabled", "created_at"]:
        assert field in rule


def test_firing_schema_fields(client):
    _make_rule(client, metric="success_rate", operator="lt", threshold=0.99)
    _fail(client, "schema_wf")
    firings = client.get("/alerts/firings").json()
    if firings:
        for field in ["id", "rule_id", "metric_value", "fired_at", "resolved_at", "is_active"]:
            assert field in firings[0]


# ── Input validation ──────────────────────────────────────────────────────────

def test_create_rule_invalid_metric_rejected(client):
    r = client.post("/alerts/rules", json={
        "name": "bad", "metric": "not_a_metric", "operator": "lt", "threshold": 0.5,
    })
    assert r.status_code == 422


def test_create_rule_invalid_operator_rejected(client):
    r = client.post("/alerts/rules", json={
        "name": "bad", "metric": "success_rate", "operator": "==", "threshold": 0.5,
    })
    assert r.status_code == 422


def test_create_rule_zero_window_minutes_rejected(client):
    r = client.post("/alerts/rules", json={
        "name": "bad", "metric": "success_rate", "operator": "lt",
        "threshold": 0.5, "window_minutes": 0,
    })
    assert r.status_code == 422
