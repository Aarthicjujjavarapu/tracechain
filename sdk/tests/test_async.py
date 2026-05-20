"""
Tests for async support in @workflow and @step decorators.
Uses asyncio.run() so no extra pytest plugins are needed.
"""
import asyncio
import pytest

from tracechain.workflow import workflow
from tracechain.steps import step
from tracechain.tracing import get_run_id, set_run_id, reset_run_id
from .conftest import MockClient, FailingClient


def run(coro):
    """Helper: run a coroutine in a fresh event loop."""
    return asyncio.run(coro)


# ── @workflow async ────────────────────────────────────────────────────────────

def test_async_workflow_calls_fn_and_returns_result():
    mc = MockClient()

    @workflow(name="async_wf", client=mc)
    async def my_wf(x):
        return x * 3

    assert run(my_wf(7)) == 21


def test_async_workflow_creates_and_completes_run():
    mc = MockClient()

    @workflow(name="async_wf", client=mc)
    async def my_wf():
        return {"ok": True}

    run(my_wf())

    assert mc.called("create_run")
    assert mc.called("complete_run")
    assert mc.call_args("complete_run")["output_payload"] == {"ok": True}


def test_async_workflow_fails_run_on_exception():
    mc = MockClient()

    @workflow(name="async_wf", client=mc)
    async def my_wf():
        raise ValueError("async boom")

    with pytest.raises(ValueError, match="async boom"):
        run(my_wf())

    assert mc.called("fail_run")
    assert not mc.called("complete_run")


def test_async_workflow_run_id_propagated():
    mc = MockClient(run_id="async-run-id")
    captured = {}

    @workflow(name="async_wf", client=mc)
    async def my_wf():
        captured["run_id"] = get_run_id()

    run(my_wf())
    assert captured["run_id"] == "async-run-id"


def test_async_workflow_run_id_cleared_after_completion():
    mc = MockClient()

    @workflow(name="async_wf", client=mc)
    async def my_wf():
        pass

    run(my_wf())
    assert get_run_id() is None


def test_async_workflow_run_id_cleared_after_exception():
    mc = MockClient()

    @workflow(name="async_wf", client=mc)
    async def my_wf():
        raise RuntimeError("fail")

    with pytest.raises(RuntimeError):
        run(my_wf())

    assert get_run_id() is None


def test_async_workflow_still_runs_when_backend_unreachable():
    fc = FailingClient()
    ran = []

    @workflow(name="async_wf", client=fc)
    async def my_wf():
        ran.append(True)
        return "result"

    result = run(my_wf())
    assert result == "result"
    assert ran == [True]


# ── @step async ────────────────────────────────────────────────────────────────

@pytest.fixture
def run_context():
    token = set_run_id("async-run-test")
    yield
    reset_run_id(token)


def test_async_step_calls_fn_and_returns_result(run_context):
    mc = MockClient()

    @step(name="my_step", client=mc)
    async def compute(a, b):
        return a + b

    assert run(compute(10, 5)) == 15


def test_async_step_creates_and_completes_step(run_context):
    mc = MockClient()

    @step(name="my_step", client=mc)
    async def do_work():
        return "done"

    run(do_work())

    assert mc.called("create_step")
    assert mc.called("complete_step")
    assert mc.call_args("complete_step")["output_payload"] == "done"


def test_async_step_fails_on_exception(run_context):
    mc = MockClient()

    @step(name="my_step", client=mc)
    async def fail():
        raise KeyError("missing key")

    with pytest.raises(KeyError):
        run(fail())

    assert mc.called("fail_step")
    assert not mc.called("complete_step")


def test_async_step_retries_on_failure(run_context):
    mc = MockClient()
    call_count = 0

    @step(name="flaky", retries=2, retry_delay=0, client=mc)
    async def flaky():
        nonlocal call_count
        call_count += 1
        raise IOError("not ready")

    with pytest.raises(IOError):
        run(flaky())

    assert call_count == 3  # 1 initial + 2 retries


def test_async_step_succeeds_after_retry(run_context):
    mc = MockClient()
    call_count = 0

    @step(name="flaky", retries=3, retry_delay=0, client=mc)
    async def flaky():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ConnectionError("retry")
        return "recovered"

    result = run(flaky())
    assert result == "recovered"
    assert mc.called("complete_step")
    assert not mc.called("fail_step")


# ── concurrent async workflows ─────────────────────────────────────────────────

def test_concurrent_workflows_have_isolated_run_ids():
    """Two concurrent @workflow tasks must not share run_id context."""
    ids_seen: dict[str, str] = {}

    class TaggedClient(MockClient):
        def __init__(self, tag, run_id):
            super().__init__(run_id=run_id)
            self.tag = tag

        def create_run(self, workflow_name, input_payload, metadata=None):
            super().create_run(workflow_name, input_payload, metadata)
            return self._run_id

    client_a = TaggedClient("a", "run-A")
    client_b = TaggedClient("b", "run-B")

    @workflow(name="wf_a", client=client_a)
    async def wf_a():
        await asyncio.sleep(0)   # yield to let wf_b start
        ids_seen["a"] = get_run_id()

    @workflow(name="wf_b", client=client_b)
    async def wf_b():
        await asyncio.sleep(0)
        ids_seen["b"] = get_run_id()

    async def run_both():
        await asyncio.gather(wf_a(), wf_b())

    run(run_both())

    assert ids_seen["a"] == "run-A"
    assert ids_seen["b"] == "run-B"
