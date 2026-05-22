"""Tests for webhook destinations CRUD and delivery logic."""
import json
import hashlib
import hmac
from unittest.mock import MagicMock, patch
import pytest

from app.services.webhooks import _sign, _build_payload, deliver_alert_events
from app.models import AlertFiring, AlertRule


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_dest(client, **kwargs):
    payload = {"name": "test hook", "url": "https://hooks.example.com/recv", **kwargs}
    r = client.post("/webhooks", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _make_alert_rule(client, **kwargs):
    payload = {
        "name": "rule", "metric": "success_rate",
        "operator": "lt", "threshold": 0.5,
        **kwargs,
    }
    r = client.post("/alerts/rules", json=payload)
    assert r.status_code == 201, r.text
    return r.json()


def _fail_run(client, name="wf"):
    r = client.post("/runs", json={"workflow_name": name, "input_payload": {}})
    run_id = r.json()["id"]
    client.post(f"/runs/{run_id}/fail", json={"error_message": "boom"})
    return run_id


# ── signing ───────────────────────────────────────────────────────────────────

def test_sign_produces_hmac_sha256():
    sig = _sign(b"hello", "secret")
    assert sig.startswith("sha256=")
    expected = hmac.new(b"secret", b"hello", hashlib.sha256).hexdigest()
    assert sig == f"sha256={expected}"


def test_sign_different_secrets_different_sigs():
    s1 = _sign(b"data", "secret1")
    s2 = _sign(b"data", "secret2")
    assert s1 != s2


# ── CRUD: create / list / get ─────────────────────────────────────────────────

def test_create_webhook(client):
    d = _make_dest(client)
    assert d["name"] == "test hook"
    assert d["enabled"] is True
    assert "id" in d


def test_create_webhook_with_secret(client):
    d = _make_dest(client, secret="mysecret")
    assert d["secret"] == "mysecret"


def test_list_webhooks_empty(client):
    r = client.get("/webhooks")
    assert r.status_code == 200
    assert r.json() == []


def test_list_webhooks_returns_created(client):
    _make_dest(client)
    _make_dest(client, name="second")
    r = client.get("/webhooks")
    assert len(r.json()) == 2


def test_get_webhook(client):
    d = _make_dest(client)
    r = client.get(f"/webhooks/{d['id']}")
    assert r.status_code == 200
    assert r.json()["id"] == d["id"]


def test_get_webhook_not_found(client):
    r = client.get("/webhooks/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


# ── CRUD: update / delete ─────────────────────────────────────────────────────

def test_update_webhook_url(client):
    d = _make_dest(client)
    r = client.patch(f"/webhooks/{d['id']}", json={"url": "https://new.example.com"})
    assert r.status_code == 200
    assert r.json()["url"] == "https://new.example.com"


def test_disable_webhook(client):
    d = _make_dest(client)
    r = client.patch(f"/webhooks/{d['id']}", json={"enabled": False})
    assert r.json()["enabled"] is False


def test_delete_webhook(client):
    d = _make_dest(client)
    r = client.delete(f"/webhooks/{d['id']}")
    assert r.status_code == 204
    assert client.get(f"/webhooks/{d['id']}").status_code == 404


# ── Deliveries endpoint ───────────────────────────────────────────────────────

def test_deliveries_empty(client):
    r = client.get("/webhooks/deliveries/recent")
    assert r.status_code == 200
    assert r.json() == []


# ── Delivery logic (mocked httpx) ─────────────────────────────────────────────

def _mock_response(status_code=200):
    mock = MagicMock()
    mock.status_code = status_code
    mock.text = "ok"
    return mock


def test_delivery_records_success(client, db_session):
    _make_dest(client, url="https://hooks.test/ok")
    _make_alert_rule(client, metric="success_rate", operator="lt", threshold=0.99)

    with patch("app.services.webhooks.httpx.Client") as mock_cls:
        mock_ctx = MagicMock()
        mock_cls.return_value.__enter__ = lambda s: mock_ctx
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ctx.post.return_value = _mock_response(200)

        _fail_run(client, "hook_wf")

    deliveries = client.get("/webhooks/deliveries/recent").json()
    assert len(deliveries) >= 1
    assert deliveries[0]["success"] is True
    assert deliveries[0]["status_code"] == 200
    assert deliveries[0]["event_type"] == "alert.fired"


def test_delivery_records_http_error(client, db_session):
    _make_dest(client, url="https://hooks.test/bad")
    _make_alert_rule(client, metric="success_rate", operator="lt", threshold=0.99)

    with patch("app.services.webhooks.httpx.Client") as mock_cls:
        mock_ctx = MagicMock()
        mock_cls.return_value.__enter__ = lambda s: mock_ctx
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ctx.post.return_value = _mock_response(503)

        _fail_run(client, "bad_hook_wf")

    deliveries = client.get("/webhooks/deliveries/recent").json()
    assert len(deliveries) >= 1
    assert deliveries[0]["success"] is False
    assert deliveries[0]["status_code"] == 503


def test_delivery_records_connection_error(client, db_session):
    _make_dest(client, url="https://hooks.test/unreachable")
    _make_alert_rule(client, metric="success_rate", operator="lt", threshold=0.99)

    with patch("app.services.webhooks.httpx.Client") as mock_cls:
        mock_ctx = MagicMock()
        mock_cls.return_value.__enter__ = lambda s: mock_ctx
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ctx.post.side_effect = Exception("Connection refused")

        _fail_run(client, "unreachable_wf")

    deliveries = client.get("/webhooks/deliveries/recent").json()
    assert len(deliveries) >= 1
    assert deliveries[0]["success"] is False
    assert deliveries[0]["status_code"] is None
    assert "Connection refused" in (deliveries[0]["error_message"] or "")


def test_disabled_destination_not_called(client, db_session):
    _make_dest(client, url="https://hooks.test/disabled", enabled=False)
    _make_alert_rule(client, metric="success_rate", operator="lt", threshold=0.99)

    with patch("app.services.webhooks.httpx.Client") as mock_cls:
        mock_ctx = MagicMock()
        mock_cls.return_value.__enter__ = lambda s: mock_ctx
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)

        _fail_run(client, "disabled_dest_wf")
        mock_ctx.post.assert_not_called()

    deliveries = client.get("/webhooks/deliveries/recent").json()
    assert deliveries == []


def test_signature_header_sent_when_secret(client, db_session):
    _make_dest(client, url="https://hooks.test/signed", secret="topsecret")
    _make_alert_rule(client, metric="success_rate", operator="lt", threshold=0.99)

    captured_headers = {}

    def fake_post(url, content, headers):
        captured_headers.update(headers)
        return _mock_response(200)

    with patch("app.services.webhooks.httpx.Client") as mock_cls:
        mock_ctx = MagicMock()
        mock_cls.return_value.__enter__ = lambda s: mock_ctx
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ctx.post.side_effect = fake_post

        _fail_run(client, "signed_wf")

    assert "X-TraceChain-Signature" in captured_headers
    assert captured_headers["X-TraceChain-Signature"].startswith("sha256=")


def test_no_signature_header_without_secret(client, db_session):
    _make_dest(client, url="https://hooks.test/unsigned")  # no secret
    _make_alert_rule(client, metric="success_rate", operator="lt", threshold=0.99)

    captured_headers = {}

    def fake_post(url, content, headers):
        captured_headers.update(headers)
        return _mock_response(200)

    with patch("app.services.webhooks.httpx.Client") as mock_cls:
        mock_ctx = MagicMock()
        mock_cls.return_value.__enter__ = lambda s: mock_ctx
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ctx.post.side_effect = fake_post

        _fail_run(client, "unsigned_wf")

    assert "X-TraceChain-Signature" not in captured_headers


def test_delivery_schema_fields(client, db_session):
    _make_dest(client)
    _make_alert_rule(client, metric="success_rate", operator="lt", threshold=0.99)

    with patch("app.services.webhooks.httpx.Client") as mock_cls:
        mock_ctx = MagicMock()
        mock_cls.return_value.__enter__ = lambda s: mock_ctx
        mock_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_ctx.post.return_value = _mock_response(200)

        _fail_run(client, "schema_wf")

    deliveries = client.get("/webhooks/deliveries/recent").json()
    if deliveries:
        d = deliveries[0]
        for field in ["id", "destination_id", "event_type", "payload", "status_code", "success", "attempted_at"]:
            assert field in d
        assert "rule" in d["payload"]
        assert "firing" in d["payload"]
