import pytest


def _create_run(client, name="test_workflow"):
    r = client.post("/runs", json={"workflow_name": name, "input_payload": {"q": "hello"}})
    assert r.status_code == 201
    return r.json()


# ── create ────────────────────────────────────────────────────────────────────

def test_create_run(client):
    run = _create_run(client)
    assert run["workflow_name"] == "test_workflow"
    assert run["status"] == "running"
    assert "id" in run


def test_create_run_minimal(client):
    r = client.post("/runs", json={"workflow_name": "w", "input_payload": {}})
    assert r.status_code == 201


# ── list ──────────────────────────────────────────────────────────────────────

def test_list_runs_empty(client):
    r = client.get("/runs")
    assert r.status_code == 200
    assert r.json() == {"items": [], "total": 0}


def test_list_runs(client):
    _create_run(client, "wf_a")
    _create_run(client, "wf_b")
    r = client.get("/runs")
    assert r.json()["total"] == 2


def test_list_runs_filter_status(client):
    run = _create_run(client)
    client.post(f"/runs/{run['id']}/complete", json={})
    r = client.get("/runs?status=success")
    assert r.json()["total"] == 1
    r2 = client.get("/runs?status=failed")
    assert r2.json()["total"] == 0


def test_list_runs_filter_workflow_name(client):
    _create_run(client, "rag_pipeline")
    _create_run(client, "support_agent")
    r = client.get("/runs?workflow_name=rag_pipeline")
    assert r.json()["total"] == 1


def test_list_runs_pagination(client):
    for _ in range(5):
        _create_run(client)
    r = client.get("/runs?limit=2&offset=0")
    assert len(r.json()["items"]) == 2
    assert r.json()["total"] == 5


# ── get ───────────────────────────────────────────────────────────────────────

def test_get_run(client):
    run = _create_run(client)
    r = client.get(f"/runs/{run['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == run["id"]


def test_get_run_not_found(client):
    r = client.get("/runs/nonexistent-id")
    assert r.status_code == 404


# ── complete / fail ───────────────────────────────────────────────────────────

def test_complete_run(client):
    run = _create_run(client)
    r = client.post(f"/runs/{run['id']}/complete", json={
        "output_payload": {"answer": "42"},
        "total_cost": 0.0012,
        "total_tokens": 150,
    })
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "success"
    assert body["total_cost"] == pytest.approx(0.0012)
    assert body["total_tokens"] == 150
    assert body["duration_ms"] is not None


def test_fail_run(client):
    run = _create_run(client)
    r = client.post(f"/runs/{run['id']}/fail", json={"error_message": "timeout"})
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "failed"
    assert body["error_message"] == "timeout"


# ── replay ────────────────────────────────────────────────────────────────────

def test_replay_run(client):
    run = _create_run(client)
    client.post(f"/runs/{run['id']}/complete", json={})
    r = client.post(f"/runs/{run['id']}/replay", json={})
    assert r.status_code == 201
    replay = r.json()
    assert replay["is_replay"] is True
    assert replay["original_run_id"] == run["id"]
    assert replay["workflow_name"] == run["workflow_name"]
