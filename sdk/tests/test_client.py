from unittest.mock import MagicMock, patch
import httpx
import pytest

from tracechain.client import TraceChainClient, _safe_json
from tracechain.config import TraceChainConfig


# ── helpers ───────────────────────────────────────────────────────────────────

def _client(enabled=True, base_url="http://localhost:8000") -> TraceChainClient:
    return TraceChainClient(TraceChainConfig(base_url=base_url, enabled=enabled, timeout=1.0))


def _mock_response(json_data: dict, status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.raise_for_status = MagicMock(
        side_effect=None if status_code < 400
        else httpx.HTTPStatusError("error", request=MagicMock(), response=resp)
    )
    return resp


# ── disabled client ───────────────────────────────────────────────────────────

def test_disabled_client_skips_http():
    """When enabled=False, _post must not make any HTTP calls."""
    c = _client(enabled=False)
    with patch("httpx.post") as mock_post:
        result = c._post("/runs", {"workflow_name": "test"})
    mock_post.assert_not_called()
    assert result is None


def test_disabled_create_run_returns_none():
    c = _client(enabled=False)
    run_id = c.create_run("wf", {})
    assert run_id is None


# ── network failures are swallowed ────────────────────────────────────────────

def test_connect_error_returns_none():
    c = _client()
    with patch("httpx.post", side_effect=httpx.ConnectError("refused")):
        result = c._post("/runs", {})
    assert result is None


def test_timeout_returns_none():
    c = _client()
    with patch("httpx.post", side_effect=httpx.TimeoutException("timed out")):
        result = c._post("/runs", {})
    assert result is None


def test_http_500_returns_none():
    c = _client()
    with patch("httpx.post", return_value=_mock_response({}, status_code=500)):
        result = c._post("/runs", {})
    assert result is None


# ── successful calls ──────────────────────────────────────────────────────────

def test_successful_post_returns_json():
    c = _client()
    payload = {"id": "abc-123", "status": "running"}
    with patch("httpx.post", return_value=_mock_response(payload)):
        result = c._post("/runs", {"workflow_name": "wf"})
    assert result == payload


def test_create_run_returns_id():
    c = _client()
    with patch("httpx.post", return_value=_mock_response({"id": "run-999"})):
        run_id = c.create_run("my_workflow", {"query": "hello"})
    assert run_id == "run-999"


def test_create_run_returns_none_on_failure():
    c = _client()
    with patch("httpx.post", side_effect=httpx.ConnectError("down")):
        run_id = c.create_run("my_workflow", {})
    assert run_id is None


def test_complete_run_posts_to_correct_path():
    c = _client()
    with patch("httpx.post", return_value=_mock_response({})) as mock_post:
        c.complete_run("run-1", {"answer": "hello"}, total_cost=0.001, total_tokens=50)
    url = mock_post.call_args[0][0]
    assert "/runs/run-1/complete" in url
    body = mock_post.call_args[1]["json"]
    assert body["total_cost"] == 0.001
    assert body["total_tokens"] == 50


def test_fail_run_posts_error_message():
    c = _client()
    with patch("httpx.post", return_value=_mock_response({})) as mock_post:
        c.fail_run("run-1", "Something went wrong")
    body = mock_post.call_args[1]["json"]
    assert body["error_message"] == "Something went wrong"


# ── _safe_json ────────────────────────────────────────────────────────────────

def test_safe_json_primitives():
    assert _safe_json(None)  is None
    assert _safe_json(42)    == 42
    assert _safe_json(3.14)  == 3.14
    assert _safe_json(True)  is True
    assert _safe_json("hi")  == "hi"


def test_safe_json_dict():
    assert _safe_json({"a": 1, "b": [2, 3]}) == {"a": 1, "b": [2, 3]}


def test_safe_json_nested():
    result = _safe_json({"x": {"y": (1, 2)}})
    assert result == {"x": {"y": [1, 2]}}


def test_safe_json_non_serialisable_falls_back_to_str():
    class Custom:
        def __str__(self): return "custom-repr"

    result = _safe_json(Custom())
    assert result == "custom-repr"
