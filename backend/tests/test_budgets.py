"""Tests for Cost Budget CRUD and spend computation."""
import pytest


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_budget(client, **kwargs):
    payload = {"name": "test budget", "budget_usd": 1.0, **kwargs}
    r = client.post("/budgets", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _complete_run(client, cost: float, workflow: str = "wf"):
    r = client.post("/runs", json={"workflow_name": workflow, "input_payload": {}})
    run_id = r.json()["id"]
    client.post(f"/runs/{run_id}/complete", json={"total_cost": cost})
    return run_id


# ── CRUD ──────────────────────────────────────────────────────────────────────

def test_list_budgets_empty(client):
    r = client.get("/budgets")
    assert r.status_code == 200
    assert r.json() == []


def test_create_budget(client):
    b = _make_budget(client)
    assert b["name"] == "test budget"
    assert b["budget_usd"] == 1.0
    assert b["period"] == "monthly"
    assert b["warning_pct"] == 0.75
    assert b["enabled"] is True
    assert "id" in b


def test_create_budget_with_workflow_scope(client):
    b = _make_budget(client, name="scoped", workflow_name="my_wf", budget_usd=0.5, period="daily")
    assert b["workflow_name"] == "my_wf"
    assert b["period"] == "daily"


def test_list_budgets_returns_created(client):
    _make_budget(client, name="a")
    _make_budget(client, name="b")
    r = client.get("/budgets")
    assert len(r.json()) == 2


def test_get_budget(client):
    b = _make_budget(client)
    r = client.get(f"/budgets/{b['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == b["id"]


def test_get_budget_not_found(client):
    r = client.get("/budgets/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_update_budget_amount(client):
    b = _make_budget(client)
    r = client.patch(f"/budgets/{b['id']}", json={"budget_usd": 5.0})
    assert r.status_code == 200
    assert r.json()["budget_usd"] == 5.0


def test_disable_budget(client):
    b = _make_budget(client)
    r = client.patch(f"/budgets/{b['id']}", json={"enabled": False})
    assert r.json()["enabled"] is False


def test_update_budget_not_found(client):
    r = client.patch("/budgets/00000000-0000-0000-0000-000000000000", json={"budget_usd": 5.0})
    assert r.status_code == 404


def test_delete_budget(client):
    b = _make_budget(client)
    r = client.delete(f"/budgets/{b['id']}")
    assert r.status_code == 204
    assert client.get(f"/budgets/{b['id']}").status_code == 404


def test_delete_budget_not_found(client):
    r = client.delete("/budgets/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


# ── Status / spend computation ─────────────────────────────────────────────────

def test_budget_status_zero_spend(client):
    b = _make_budget(client, budget_usd=1.0)
    s = client.get(f"/budgets/{b['id']}").json()
    assert s["spent"] == 0.0
    assert s["remaining"] == 1.0
    assert s["pct_used"] == 0.0
    assert s["status"] == "ok"


def test_budget_status_ok(client):
    b = _make_budget(client, budget_usd=1.0, warning_pct=0.75)
    _complete_run(client, cost=0.50)
    s = client.get(f"/budgets/{b['id']}").json()
    assert s["spent"] == pytest.approx(0.50, abs=1e-4)
    assert s["status"] == "ok"


def test_budget_status_warning(client):
    b = _make_budget(client, budget_usd=1.0, warning_pct=0.75)
    _complete_run(client, cost=0.80)
    s = client.get(f"/budgets/{b['id']}").json()
    assert s["status"] == "warning"
    assert s["pct_used"] >= 0.75


def test_budget_status_critical(client):
    b = _make_budget(client, budget_usd=1.0, warning_pct=0.75)
    _complete_run(client, cost=0.92)
    s = client.get(f"/budgets/{b['id']}").json()
    assert s["status"] == "critical"


def test_budget_status_exceeded(client):
    b = _make_budget(client, budget_usd=0.50)
    _complete_run(client, cost=0.75)
    s = client.get(f"/budgets/{b['id']}").json()
    assert s["status"] == "exceeded"
    assert s["pct_used"] == 1.0
    assert s["remaining"] == 0.0


def test_budget_status_workflow_scope(client):
    b = _make_budget(client, budget_usd=1.0, workflow_name="wf_a")
    _complete_run(client, cost=0.30, workflow="wf_a")
    _complete_run(client, cost=0.80, workflow="wf_b")  # different workflow — not counted
    s = client.get(f"/budgets/{b['id']}").json()
    assert s["spent"] == pytest.approx(0.30, abs=1e-4)
    assert s["status"] == "ok"


def test_budget_status_schema_fields(client):
    b = _make_budget(client)
    s = client.get(f"/budgets/{b['id']}").json()
    for field in ["id", "name", "budget_usd", "period", "spent", "remaining", "pct_used", "status"]:
        assert field in s


def test_budget_list_includes_status(client):
    _make_budget(client, name="x", budget_usd=1.0)
    _complete_run(client, cost=0.50)
    items = client.get("/budgets").json()
    assert len(items) == 1
    s = items[0]
    assert "spent" in s
    assert "status" in s


# ── Spend summary ──────────────────────────────────────────────────────────────

def test_spend_summary_empty(client):
    r = client.get("/budgets/spend-summary")
    assert r.status_code == 200
    d = r.json()
    assert d["today_usd"] == 0.0
    assert d["month_usd"] == 0.0
    assert d["all_time_usd"] == 0.0
    assert d["run_count_today"] == 0
    assert d["run_count_month"] == 0


def test_spend_summary_with_runs(client):
    _complete_run(client, cost=0.10)
    _complete_run(client, cost=0.25)
    r = client.get("/budgets/spend-summary").json()
    assert r["all_time_usd"] == pytest.approx(0.35, abs=1e-4)
    assert r["today_usd"] == pytest.approx(0.35, abs=1e-4)
    assert r["run_count_today"] == 2


# ── Input validation ──────────────────────────────────────────────────────────

def test_create_budget_zero_amount_rejected(client):
    r = client.post("/budgets", json={"name": "bad", "budget_usd": 0.0})
    assert r.status_code == 422


def test_create_budget_negative_amount_rejected(client):
    r = client.post("/budgets", json={"name": "bad", "budget_usd": -5.0})
    assert r.status_code == 422


def test_create_budget_invalid_period_rejected(client):
    r = client.post("/budgets", json={"name": "bad", "budget_usd": 1.0, "period": "weekly"})
    assert r.status_code == 422


def test_create_budget_warning_pct_out_of_range_rejected(client):
    r = client.post("/budgets", json={"name": "bad", "budget_usd": 1.0, "warning_pct": 1.5})
    assert r.status_code == 422


def test_update_budget_zero_amount_rejected(client):
    b = _make_budget(client)
    r = client.patch(f"/budgets/{b['id']}", json={"budget_usd": 0.0})
    assert r.status_code == 422
