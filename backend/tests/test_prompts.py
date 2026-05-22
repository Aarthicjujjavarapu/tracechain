"""Tests for prompt version registry."""


def _prompt(client, name="my_prompt", version="v1"):
    r = client.post("/prompts", json={
        "prompt_name": name,
        "version": version,
        "prompt_text": "Answer concisely: {query}",
        "is_active": True,
    })
    assert r.status_code == 201
    return r.json()


def test_create_prompt(client):
    p = _prompt(client)
    assert p["prompt_name"] == "my_prompt"
    assert p["version"] == "v1"
    assert p["is_active"] is True


def test_list_prompts(client):
    _prompt(client, "p1", "v1")
    _prompt(client, "p2", "v1")
    r = client.get("/prompts")
    assert r.status_code == 200
    assert len(r.json()) == 2


def test_get_prompt(client):
    p = _prompt(client)
    r = client.get(f"/prompts/{p['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == p["id"]


def test_get_prompt_not_found(client):
    r = client.get("/prompts/nonexistent")
    assert r.status_code == 404


def test_prompt_versions(client):
    _prompt(client, "rag_prompt", "v1")
    _prompt(client, "rag_prompt", "v2")
    r = client.get("/prompts")
    names = [p["prompt_name"] for p in r.json()]
    assert names.count("rag_prompt") == 2


# ── Compare endpoint ──────────────────────────────────────────────────────────

def _make_run_with_llm(client, workflow: str, prompt_version: str, latency_ms: int, cost: float, success: bool = True):
    r = client.post("/runs", json={"workflow_name": workflow, "input_payload": {}})
    run_id = r.json()["id"]
    client.post(f"/runs/{run_id}/llm-calls", json={
        "model": "gpt-4",
        "prompt": "Hello",
        "prompt_version": prompt_version,
        "latency_ms": latency_ms,
        "estimated_cost": cost,
        "status": "success" if success else "failed",
    })
    if success:
        client.post(f"/runs/{run_id}/complete", json={})
    else:
        client.post(f"/runs/{run_id}/fail", json={"error_message": "err"})
    return run_id


def test_compare_returns_metrics(client):
    a = _prompt(client, "qa_prompt", "v1")
    b = _prompt(client, "qa_prompt", "v2")
    _make_run_with_llm(client, "wf", "v1", latency_ms=1000, cost=0.01)
    _make_run_with_llm(client, "wf", "v2", latency_ms=500,  cost=0.005)

    r = client.get(f"/prompts/compare?a={a['id']}&b={b['id']}")
    assert r.status_code == 200
    d = r.json()
    assert "a" in d and "b" in d and "winner" in d
    assert d["a"]["version"] == "v1"
    assert d["b"]["version"] == "v2"


def test_compare_winner_lower_latency(client):
    a = _prompt(client, "lat_prompt", "v1")
    b = _prompt(client, "lat_prompt", "v2")
    _make_run_with_llm(client, "wf", "v1", latency_ms=2000, cost=0.01)
    _make_run_with_llm(client, "wf", "v2", latency_ms=500,  cost=0.01)

    r = client.get(f"/prompts/compare?a={a['id']}&b={b['id']}").json()
    assert r["winner"]["latency"] == "b"


def test_compare_winner_lower_cost(client):
    a = _prompt(client, "cost_prompt", "v1")
    b = _prompt(client, "cost_prompt", "v2")
    _make_run_with_llm(client, "wf", "v1", latency_ms=500, cost=0.02)
    _make_run_with_llm(client, "wf", "v2", latency_ms=500, cost=0.005)

    r = client.get(f"/prompts/compare?a={a['id']}&b={b['id']}").json()
    assert r["winner"]["cost"] == "b"


def test_compare_winner_higher_success_rate(client):
    a = _prompt(client, "sr_prompt", "v1")
    b = _prompt(client, "sr_prompt", "v2")
    _make_run_with_llm(client, "wf", "v1", latency_ms=500, cost=0.01, success=True)
    _make_run_with_llm(client, "wf", "v2", latency_ms=500, cost=0.01, success=False)

    r = client.get(f"/prompts/compare?a={a['id']}&b={b['id']}").json()
    assert r["winner"]["success_rate"] == "a"


def test_compare_no_usage_returns_zero(client):
    a = _prompt(client, "empty_prompt", "v1")
    b = _prompt(client, "empty_prompt", "v2")
    r = client.get(f"/prompts/compare?a={a['id']}&b={b['id']}")
    assert r.status_code == 200
    d = r.json()
    assert d["a"]["usage_count"] == 0
    assert d["b"]["usage_count"] == 0
    assert d["winner"]["latency"] is None


def test_compare_cross_name_rejected(client):
    a = _prompt(client, "prompt_x", "v1")
    b = _prompt(client, "prompt_y", "v1")
    r = client.get(f"/prompts/compare?a={a['id']}&b={b['id']}")
    assert r.status_code == 422


def test_compare_not_found(client):
    a = _prompt(client, "exist_prompt", "v1")
    r = client.get(f"/prompts/compare?a={a['id']}&b=00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404
