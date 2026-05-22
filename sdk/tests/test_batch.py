"""Tests for @batch_step decorator."""
import asyncio
import pytest

from tracechain.batch import batch_step, BatchResult
from tracechain.tracing import set_run_id, reset_run_id
from .conftest import MockClient


def run(coro):
    return asyncio.run(coro)


# ── fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture
def run_context():
    token = set_run_id("run-batch-test")
    yield
    reset_run_id(token)


class CountingClient(MockClient):
    """Records every create_step call with its step_name for assertion."""

    def __init__(self):
        super().__init__(run_id="run-batch-test", step_id="step-batch")
        self._step_counter = 0

    def create_step(self, run_id, step_name, step_type, input_payload, metadata=None):
        self._step_counter += 1
        step_id = f"step-{self._step_counter}"
        self._record(
            "create_step",
            run_id=run_id, step_name=step_name, step_type=step_type,
            input_payload=input_payload, step_id=step_id,
        )
        return step_id

    def complete_step(self, run_id, step_id, output_payload, duration_ms, retry_count=0):
        self._record("complete_step", run_id=run_id, step_id=step_id,
                     output_payload=output_payload, duration_ms=duration_ms)

    def fail_step(self, run_id, step_id, error_message, retry_count=0):
        self._record("fail_step", run_id=run_id, step_id=step_id,
                     error_message=error_message)

    def create_step_calls(self):
        return [(n, k) for n, k in self.calls if n == "create_step"]

    def complete_step_calls(self):
        return [(n, k) for n, k in self.calls if n == "complete_step"]

    def fail_step_calls(self):
        return [(n, k) for n, k in self.calls if n == "fail_step"]


# ── sync: basic ────────────────────────────────────────────────────────────────

def test_sync_returns_batch_result(run_context):
    mc = CountingClient()

    @batch_step(name="double", client=mc)
    def double(x):
        return x * 2

    result = double([1, 2, 3])
    assert isinstance(result, BatchResult)
    assert list(result) == [2, 4, 6]
    assert result.success_count == 3
    assert result.failed_count == 0


def test_sync_empty_list(run_context):
    mc = CountingClient()

    @batch_step(name="noop", client=mc)
    def noop(x):
        return x

    result = noop([])
    assert result.success_count == 0
    assert result.failed_count == 0
    assert len(result) == 0


def test_sync_creates_one_batch_step(run_context):
    mc = CountingClient()

    @batch_step(name="embed", client=mc)
    def embed(doc):
        return doc.upper()

    embed(["a", "b", "c"])
    step_calls = mc.create_step_calls()
    assert len(step_calls) == 1
    _, kwargs = step_calls[0]
    assert kwargs["step_type"] == "batch_step"
    assert kwargs["input_payload"]["batch_size"] == 3


def test_sync_completes_batch_step_with_summary(run_context):
    mc = CountingClient()

    @batch_step(name="embed", client=mc)
    def embed(doc):
        return doc.upper()

    embed(["a", "b", "c"])
    complete_calls = mc.complete_step_calls()
    assert len(complete_calls) == 1
    _, kwargs = complete_calls[0]
    assert kwargs["output_payload"]["success_count"] == 3
    assert kwargs["output_payload"]["failed_count"] == 0


def test_sync_partial_failures_collected(run_context):
    mc = CountingClient()

    @batch_step(name="risky", raise_on_error=False, client=mc)
    def risky(x):
        if x == "bad":
            raise ValueError("bad item")
        return x.upper()

    result = risky(["ok", "bad", "fine"])
    assert result.results == ["OK", None, "FINE"]
    assert result.failed_count == 1
    assert result.success_count == 2
    assert isinstance(result.errors[1], ValueError)
    assert result.success_results == ["OK", "FINE"]


def test_sync_raise_on_error_stops_early(run_context):
    mc = CountingClient()
    processed = []

    @batch_step(name="strict", raise_on_error=True, client=mc)
    def strict(x):
        processed.append(x)
        if x == "bad":
            raise RuntimeError("stop!")
        return x

    with pytest.raises(RuntimeError, match="stop!"):
        strict(["a", "bad", "c"])

    # sequential: "c" should not have been processed
    assert "c" not in processed


def test_sync_trace_items_creates_per_item_steps(run_context):
    mc = CountingClient()

    @batch_step(name="embed", trace_items=True, client=mc)
    def embed(doc):
        return doc

    embed(["x", "y"])
    step_calls = mc.create_step_calls()
    # 1 batch parent + 2 item children
    assert len(step_calls) == 3
    types = [k["step_type"] for _, k in step_calls]
    assert types.count("batch_step") == 1
    assert types.count("batch_item") == 2


def test_sync_concurrent(run_context):
    mc = CountingClient()
    import threading
    threads_seen: set = set()

    @batch_step(name="para", concurrency=3, client=mc)
    def para(x):
        threads_seen.add(threading.get_ident())
        return x * 10

    result = para([1, 2, 3, 4, 5])
    assert sorted(result.success_results) == [10, 20, 30, 40, 50]


# ── async: basic ───────────────────────────────────────────────────────────────

def test_async_returns_batch_result(run_context):
    mc = CountingClient()

    @batch_step(name="double", client=mc)
    async def double(x):
        return x * 2

    result = run(double([1, 2, 3]))
    assert list(result) == [2, 4, 6]
    assert result.success_count == 3


def test_async_partial_failures(run_context):
    mc = CountingClient()

    @batch_step(name="risky", raise_on_error=False, client=mc)
    async def risky(x):
        if x < 0:
            raise ValueError("negative")
        return x * 2

    result = run(risky([1, -1, 2]))
    assert result.results[0] == 2
    assert result.results[1] is None
    assert result.results[2] == 4
    assert result.failed_count == 1


def test_async_raise_on_error(run_context):
    mc = CountingClient()

    @batch_step(name="strict", raise_on_error=True, client=mc)
    async def strict(x):
        if x == "fail":
            raise KeyError("fail")
        return x

    with pytest.raises(KeyError):
        run(strict(["ok", "fail", "ok2"]))


def test_async_concurrency_semaphore(run_context):
    mc = CountingClient()
    concurrent = []
    peak = []

    @batch_step(name="para", concurrency=2, client=mc)
    async def para(x):
        concurrent.append(x)
        peak.append(len(concurrent))
        await asyncio.sleep(0)
        concurrent.remove(x)
        return x

    run(para([1, 2, 3, 4]))
    assert max(peak) <= 2


def test_async_creates_one_batch_step(run_context):
    mc = CountingClient()

    @batch_step(name="embed", client=mc)
    async def embed(doc):
        return doc

    run(embed(["a", "b"]))
    step_calls = mc.create_step_calls()
    assert len(step_calls) == 1
    assert step_calls[0][1]["step_type"] == "batch_step"


def test_async_trace_items(run_context):
    mc = CountingClient()

    @batch_step(name="embed", trace_items=True, client=mc)
    async def embed(doc):
        return doc

    run(embed(["x", "y", "z"]))
    step_calls = mc.create_step_calls()
    # 1 parent + 3 items
    assert len(step_calls) == 4


# ── BatchResult interface ──────────────────────────────────────────────────────

def test_batch_result_indexing():
    r = BatchResult(results=[10, 20, 30], errors=[None, None, None])
    assert r[1] == 20


def test_batch_result_success_results_filters_failures():
    r = BatchResult(results=[1, None, 3], errors=[None, ValueError("x"), None])
    assert r.success_results == [1, 3]


def test_batch_result_counts():
    r = BatchResult(results=[1, None], errors=[None, RuntimeError()])
    assert r.success_count == 1
    assert r.failed_count == 1


# ── no run_id — still works (gracefully skips backend) ────────────────────────

def test_sync_no_run_id():
    mc = CountingClient()

    @batch_step(name="noop", client=mc)
    def noop(x):
        return x + 1

    result = noop([10, 20])
    assert list(result) == [11, 21]
    assert not mc.called("create_step")


def test_async_no_run_id():
    mc = CountingClient()

    @batch_step(name="noop", client=mc)
    async def noop(x):
        return x + 1

    result = run(noop([10, 20]))
    assert list(result) == [11, 21]
    assert not mc.called("create_step")
