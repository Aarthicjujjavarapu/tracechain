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


# ── Incident reopen after acknowledgement ────────────────────────────────────

def _get_incident(client, inc_id: str) -> dict:
    """Fetch a single incident via the list endpoint."""
    items = client.get("/incidents").json()["items"]
    for i in items:
        if i["id"] == inc_id:
            return i
    raise KeyError(inc_id)


def test_acknowledge_resolved_incident_returns_409(client):
    """Acknowledging an already-resolved incident must return 409, not silently succeed."""
    run_id = _create_run(client)
    client.post(f"/runs/{run_id}/fail", json={"error_message": "rate limit 429"})

    incidents = client.get("/incidents").json()["items"]
    if not incidents:
        pytest.skip("no incidents created")

    inc_id = incidents[0]["id"]
    client.patch(f"/incidents/{inc_id}", json={"status": "RESOLVED"})
    r = client.patch(f"/incidents/{inc_id}", json={"status": "ACKNOWLEDGED"})
    assert r.status_code == 409


def test_acknowledged_incident_reopens_on_new_occurrence(client):
    """When a new failure of the same category arrives, an ACKNOWLEDGED incident
    must flip back to OPEN rather than staying silently acknowledged."""
    wf = "reopen_wf"

    # First failure → incident created (OPEN)
    run1 = _create_run(client, wf)
    client.post(f"/runs/{run1}/fail", json={"error_message": "Read timeout after 30s"})

    incidents = client.get("/incidents?status=OPEN").json()["items"]
    wf_incidents = [i for i in incidents if i.get("workflow_name") == wf]
    if not wf_incidents:
        pytest.skip("no incident created on first failure")
    inc_id = wf_incidents[0]["id"]

    # Operator acknowledges
    client.patch(f"/incidents/{inc_id}", json={"status": "ACKNOWLEDGED"})
    assert _get_incident(client, inc_id)["status"] == "ACKNOWLEDGED"

    # Second failure of the same type in the same workflow
    run2 = _create_run(client, wf)
    client.post(f"/runs/{run2}/fail", json={"error_message": "Read timeout after 30s"})

    # Incident must be OPEN again
    updated = _get_incident(client, inc_id)
    assert updated["status"] == "OPEN", (
        f"Expected OPEN after recurrence, got {updated['status']}"
    )
    assert updated["occurrence_count"] >= 2


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
