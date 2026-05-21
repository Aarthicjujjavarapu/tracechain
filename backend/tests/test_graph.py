"""Tests for the agent graph endpoint."""


def _setup_run_with_steps(client):
    run = client.post("/runs", json={"workflow_name": "wf", "input_payload": {}}).json()
    run_id = run["id"]

    s1 = client.post(f"/runs/{run_id}/steps", json={
        "step_name": "retrieve", "step_type": "step", "input_payload": {},
    }).json()
    client.post(f"/runs/{run_id}/steps/{s1['id']}/complete", json={"output_payload": {}})

    s2 = client.post(f"/runs/{run_id}/steps", json={
        "step_name": "generate", "step_type": "step", "input_payload": {},
    }).json()
    client.post(f"/runs/{run_id}/llm-calls", json={
        "step_id": s2["id"],
        "model": "gpt-4o", "provider": "openai",
        "prompt": "Q", "input_tokens": 10, "output_tokens": 5, "total_tokens": 15,
    })
    client.post(f"/runs/{run_id}/steps/{s2['id']}/complete", json={"output_payload": {}})
    client.post(f"/runs/{run_id}/complete", json={})
    return run_id


def test_graph_no_spans_falls_back_to_legacy(client):
    run_id = _setup_run_with_steps(client)
    r = client.get(f"/v1/runs/{run_id}/graph")
    assert r.status_code == 200
    body = r.json()
    assert "nodes" in body
    assert "edges" in body
    node_kinds = [n["data"]["kind"] for n in body["nodes"]]
    assert "workflow" in node_kinds
    assert "step" in node_kinds
    assert "llm" in node_kinds


def test_graph_node_count(client):
    run_id = _setup_run_with_steps(client)
    r = client.get(f"/v1/runs/{run_id}/graph")
    body = r.json()
    # 1 workflow + 2 steps + 1 llm = 4 nodes
    assert len(body["nodes"]) == 4
    # workflow→s1, workflow→s2, s2→llm = 3 edges
    assert len(body["edges"]) == 3


def test_graph_run_not_found(client):
    r = client.get("/v1/runs/nonexistent-run/graph")
    assert r.status_code == 404


def test_graph_positions_set(client):
    run_id = _setup_run_with_steps(client)
    r = client.get(f"/v1/runs/{run_id}/graph")
    for node in r.json()["nodes"]:
        pos = node["position"]
        assert "x" in pos and "y" in pos
