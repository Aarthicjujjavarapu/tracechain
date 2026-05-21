"""Tests for trace steps and LLM calls endpoints."""


def _run(client):
    r = client.post("/runs", json={"workflow_name": "wf", "input_payload": {}})
    assert r.status_code == 201
    return r.json()["id"]


def _step(client, run_id, name="step_one"):
    r = client.post(f"/runs/{run_id}/steps", json={
        "step_name": name,
        "step_type": "step",
        "input_payload": {},
    })
    assert r.status_code == 201, r.text
    return r.json()


def _llm(client, run_id, step_id=None):
    r = client.post(f"/runs/{run_id}/llm-calls", json={
        "step_id": step_id,
        "model": "gpt-4o",
        "provider": "openai",
        "prompt": "Hello",
        "response": "Hi!",
        "input_tokens": 10,
        "output_tokens": 5,
        "total_tokens": 15,
        "estimated_cost": 0.00045,
        "latency_ms": 320,
    })
    assert r.status_code == 201, r.text
    return r.json()


# ── steps ─────────────────────────────────────────────────────────────────────

def test_create_step(client):
    run_id = _run(client)
    step = _step(client, run_id)
    assert step["step_name"] == "step_one"
    assert step["status"] == "running"


def test_list_steps(client):
    run_id = _run(client)
    _step(client, run_id, "s1")
    _step(client, run_id, "s2")
    r = client.get(f"/runs/{run_id}/steps")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_complete_step(client):
    run_id = _run(client)
    step = _step(client, run_id)
    r = client.post(f"/runs/{run_id}/steps/{step['id']}/complete", json={"output_payload": {"x": 1}})
    assert r.status_code == 200
    assert r.json()["status"] == "success"
    assert r.json()["duration_ms"] is not None


def test_fail_step(client):
    run_id = _run(client)
    step = _step(client, run_id)
    r = client.post(f"/runs/{run_id}/steps/{step['id']}/fail", json={"error_message": "timeout"})
    assert r.status_code == 200
    assert r.json()["status"] == "failed"


# ── llm calls ─────────────────────────────────────────────────────────────────

def test_create_llm_call(client):
    run_id = _run(client)
    llm = _llm(client, run_id)
    assert llm["model"] == "gpt-4o"
    assert llm["input_tokens"] == 10
    assert llm["estimated_cost"] == 0.00045


def test_list_llm_calls(client):
    run_id = _run(client)
    _llm(client, run_id)
    _llm(client, run_id)
    r = client.get(f"/runs/{run_id}/llm-calls")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_llm_call_linked_to_step(client):
    run_id = _run(client)
    step = _step(client, run_id)
    llm = _llm(client, run_id, step_id=step["id"])
    assert llm["step_id"] == step["id"]
