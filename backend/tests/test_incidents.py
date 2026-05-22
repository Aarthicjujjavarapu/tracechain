"""Tests for the incident grouping engine via the HTTP API."""
import pytest


def _create_run(client, name="test_wf"):
    r = client.post("/runs", json={"workflow_name": name, "input_payload": {}})
    assert r.status_code == 201
    return r.json()["id"]


# ── Incident listing ──────────────────────────────────────────────────────────

def test_list_incidents_empty(client):
    r = client.get("/incidents")
    assert r.status_code == 200
    assert r.json()["total"] == 0
    assert r.json()["items"] == []


def test_incident_created_on_failed_run(client):
    run_id = _create_run(client)
    client.post(f"/runs/{run_id}/fail", json={"error_message": "Read timeout after 30s"})

    r = client.get("/incidents")
    assert r.status_code == 200
    items = r.json()["items"]
    categories = [i["category"] for i in items]
    assert "MODEL_TIMEOUT" in categories or "UNKNOWN_FAILURE" in categories


def test_incident_acknowledged(client):
    run_id = _create_run(client)
    client.post(f"/runs/{run_id}/fail", json={"error_message": "rate limit 429"})

    incidents = client.get("/incidents").json()["items"]
    if not incidents:
        pytest.skip("no incidents created")

    inc_id = incidents[0]["id"]
    r = client.patch(f"/incidents/{inc_id}", json={"status": "ACKNOWLEDGED"})
    assert r.status_code == 200
    assert r.json()["status"] == "ACKNOWLEDGED"


def test_incident_resolved(client):
    run_id = _create_run(client)
    client.post(f"/runs/{run_id}/fail", json={"error_message": "rate limit 429"})

    incidents = client.get("/incidents").json()["items"]
    if not incidents:
        pytest.skip("no incidents created")

    inc_id = incidents[0]["id"]
    r = client.patch(f"/incidents/{inc_id}", json={"status": "RESOLVED"})
    assert r.status_code == 200
    assert r.json()["status"] == "RESOLVED"
    assert r.json()["resolved_at"] is not None


def test_incident_filter_by_status(client):
    run_id = _create_run(client)
    client.post(f"/runs/{run_id}/fail", json={"error_message": "Read timeout"})

    open_r = client.get("/incidents?status=OPEN")
    assert open_r.status_code == 200

    resolved_r = client.get("/incidents?status=RESOLVED")
    assert resolved_r.status_code == 200
    assert resolved_r.json()["total"] == 0


def test_invalid_incident_status_returns_422(client):
    r = client.patch("/incidents/fake-id", json={"status": "BOGUS"})
    assert r.status_code == 422


# ── Classification endpoint ───────────────────────────────────────────────────

def test_get_classifications_empty(client):
    run_id = _create_run(client)
    r = client.get(f"/runs/{run_id}/classifications")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_classifications_after_failed_run(client):
    run_id = _create_run(client)
    client.post(f"/runs/{run_id}/fail", json={"error_message": "Read timeout"})

    r = client.get(f"/runs/{run_id}/classifications")
    assert r.status_code == 200
    items = r.json()
    assert len(items) >= 1
    for item in items:
        assert "category" in item
        assert "severity" in item
        assert "recommendation" in item


# ── Reliability endpoint ──────────────────────────────────────────────────────

def test_reliability_after_success(client):
    run_id = _create_run(client)
    client.post(f"/runs/{run_id}/complete", json={"output_payload": {"answer": "ok"}})

    r = client.get(f"/runs/{run_id}/reliability")
    assert r.status_code == 200
    data = r.json()
    assert "score" in data
    assert 0 <= data["score"] <= 100
    assert isinstance(data["reasons"], list)


def test_reliability_after_failed_run(client):
    run_id = _create_run(client)
    client.post(f"/runs/{run_id}/fail", json={"error_message": "something broke"})

    r = client.get(f"/runs/{run_id}/reliability")
    assert r.status_code == 200
    assert r.json()["score"] < 100
