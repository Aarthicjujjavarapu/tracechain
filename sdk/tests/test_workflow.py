import pytest
from tracechain.workflow import workflow
from tracechain.tracing import get_run_id, reset_run_id, set_run_id
from .conftest import MockClient, FailingClient


# ── basic execution ───────────────────────────────────────────────────────────

def test_workflow_calls_fn_and_returns_result():
    mc = MockClient()

    @workflow(name="test_wf", client=mc)
    def my_wf(x):
        return x * 2

    assert my_wf(21) == 42


def test_workflow_creates_run_before_fn():
    mc = MockClient()
    order = []

    @workflow(name="test_wf", client=mc)
    def my_wf():
        order.append("fn")
        return "done"

    my_wf()
    assert mc.called("create_run")
    # create_run fires before fn body executes — fn appended after client recorded
    assert order == ["fn"]


def test_workflow_completes_run_on_success():
    mc = MockClient()

    @workflow(name="test_wf", client=mc)
    def my_wf():
        return {"answer": "hello"}

    my_wf()

    assert mc.called("complete_run")
    args = mc.call_args("complete_run")
    assert args["run_id"] == mc._run_id
    assert args["output_payload"] == {"answer": "hello"}


def test_workflow_fails_run_on_exception_and_reraises():
    mc = MockClient()

    @workflow(name="test_wf", client=mc)
    def my_wf():
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        my_wf()

    assert mc.called("fail_run")
    assert not mc.called("complete_run")
    args = mc.call_args("fail_run")
    assert "boom" in args["error_message"]


# ── context propagation ───────────────────────────────────────────────────────

def test_run_id_available_inside_fn():
    mc = MockClient(run_id="ctx-run-id")
    captured = {}

    @workflow(name="test_wf", client=mc)
    def my_wf():
        captured["run_id"] = get_run_id()

    my_wf()
    assert captured["run_id"] == "ctx-run-id"


def test_run_id_cleared_after_fn():
    mc = MockClient()

    @workflow(name="test_wf", client=mc)
    def my_wf():
        pass

    my_wf()
    assert get_run_id() is None


def test_run_id_cleared_even_after_exception():
    mc = MockClient()

    @workflow(name="test_wf", client=mc)
    def my_wf():
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError):
        my_wf()

    assert get_run_id() is None


# ── input payload capture ─────────────────────────────────────────────────────

def test_input_payload_captures_positional_args():
    mc = MockClient()

    @workflow(name="test_wf", client=mc)
    def my_wf(query, limit=10):
        return query

    my_wf("hello", limit=5)

    args = mc.call_args("create_run")
    assert args["input_payload"]["query"] == "hello"
    assert args["input_payload"]["limit"] == 5


def test_input_payload_uses_defaults_when_not_provided():
    mc = MockClient()

    @workflow(name="test_wf", client=mc)
    def my_wf(query, limit=10):
        return query

    my_wf("test")

    args = mc.call_args("create_run")
    assert args["input_payload"]["limit"] == 10


# ── resilience when backend is down ──────────────────────────────────────────

def test_workflow_still_runs_when_backend_unreachable():
    """Even if create_run returns None, the user's fn must still execute."""
    fc = FailingClient()
    ran = []

    @workflow(name="test_wf", client=fc)
    def my_wf():
        ran.append(True)
        return "result"

    result = my_wf()
    assert result == "result"
    assert ran == [True]
