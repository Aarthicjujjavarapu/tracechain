"""
Async context propagation tests.

Verifies that run_id, step_id, and cost accumulators are properly isolated
across concurrent async tasks so parallel workflows never bleed into each other.
"""
import asyncio
import pytest

from tracechain.workflow import workflow
from tracechain.steps import step
from tracechain.tracing import (
    get_run_id,
    get_step_id,
    set_run_id,
    reset_run_id,
    add_llm_usage,
    get_run_totals,
    reset_run_totals,
)
from .conftest import MockClient


def run(coro):
    return asyncio.run(coro)


# ── helpers ────────────────────────────────────────────────────────────────────

class IdClient(MockClient):
    """MockClient that returns a caller-specified run_id and step_id."""
    def __init__(self, run_id, step_id="step-1"):
        super().__init__(run_id=run_id, step_id=step_id)

    def create_run(self, workflow_name, input_payload, metadata=None):
        super().create_run(workflow_name, input_payload, metadata)
        return self._run_id

    def create_step(self, run_id, step_name, step_type, input_payload, metadata=None):
        super().create_step(run_id, step_name, step_type, input_payload, metadata)
        return self._step_id


# ── 1. Full workflow → step chain propagates run_id ───────────────────────────

def test_run_id_visible_inside_step():
    captured = {}
    mc = IdClient(run_id="run-chain")

    @step(name="inner", client=mc)
    async def inner():
        captured["run_id"] = get_run_id()
        return "ok"

    @workflow(name="outer", client=mc)
    async def outer():
        await inner()

    run(outer())
    assert captured["run_id"] == "run-chain"


# ── 2. step_id is set during step and cleared after ───────────────────────────

def test_step_id_set_during_step_cleared_after():
    during: list[str | None] = []
    after:  list[str | None] = []
    mc = IdClient(run_id="run-sid", step_id="step-abc")

    @step(name="probe", client=mc)
    async def probe():
        during.append(get_step_id())
        return "done"

    @workflow(name="wf", client=mc)
    async def wf():
        await probe()
        after.append(get_step_id())

    run(wf())
    assert during == ["step-abc"]
    assert after  == [None]   # cleared after step completes


# ── 3. Concurrent steps within the same workflow see their own step_ids ────────

def test_concurrent_steps_have_isolated_step_ids():
    """
    Two steps running concurrently (via asyncio.gather) must not see each
    other's step_id, even though they share the same workflow / run_id.
    """
    seen: dict[str, str | None] = {}
    mc_a = IdClient(run_id="run-shared", step_id="step-A")
    mc_b = IdClient(run_id="run-shared", step_id="step-B")

    @step(name="step_a", client=mc_a)
    async def step_a():
        await asyncio.sleep(0)        # yield to let step_b start
        seen["a"] = get_step_id()
        return "a"

    @step(name="step_b", client=mc_b)
    async def step_b():
        await asyncio.sleep(0)
        seen["b"] = get_step_id()
        return "b"

    mc_wf = IdClient(run_id="run-shared")

    @workflow(name="wf", client=mc_wf)
    async def wf():
        await asyncio.gather(step_a(), step_b())

    run(wf())
    assert seen["a"] == "step-A"
    assert seen["b"] == "step-B"


# ── 4. asyncio.create_task() child inherits parent run_id ─────────────────────

def test_create_task_inherits_run_id():
    """
    Tasks spawned with asyncio.create_task() copy the parent's context
    (Python 3.7+ semantics), so the child should see the same run_id.
    """
    child_run_id: list[str | None] = []

    async def child_task():
        child_run_id.append(get_run_id())

    mc = IdClient(run_id="run-inherit")

    @workflow(name="wf", client=mc)
    async def wf():
        t = asyncio.create_task(child_task())
        await t

    run(wf())
    assert child_run_id == ["run-inherit"]


# ── 5. Child task mutations don't bleed back to parent ─────────────────────────

def test_create_task_mutation_does_not_affect_parent():
    """
    ContextVar semantics: mutations inside a child task are local to that task's
    context copy; the parent's context must remain unchanged.
    """
    parent_before: list[str | None] = []
    parent_after:  list[str | None] = []

    async def mutating_child():
        set_run_id("child-run-mutated")

    async def driver():
        token = set_run_id("parent-run")
        parent_before.append(get_run_id())
        t = asyncio.create_task(mutating_child())
        await t
        parent_after.append(get_run_id())
        reset_run_id(token)

    run(driver())
    assert parent_before == ["parent-run"]
    assert parent_after  == ["parent-run"]   # child mutation didn't bleed back


# ── 6. Cost accumulators are isolated between concurrent workflows ─────────────

def test_concurrent_runs_cost_accumulators_isolated():
    """
    add_llm_usage() inside one concurrent workflow must not affect the totals
    visible to a sibling workflow running in the same event loop.
    """
    totals: dict[str, tuple[float, int]] = {}
    mc_a = IdClient(run_id="run-cost-A")
    mc_b = IdClient(run_id="run-cost-B")

    @workflow(name="wf_a", client=mc_a)
    async def wf_a():
        reset_run_totals()
        add_llm_usage(cost=0.01, tokens=100)
        await asyncio.sleep(0)
        totals["a"] = get_run_totals()

    @workflow(name="wf_b", client=mc_b)
    async def wf_b():
        reset_run_totals()
        add_llm_usage(cost=0.05, tokens=500)
        await asyncio.sleep(0)
        totals["b"] = get_run_totals()

    async def driver():
        await asyncio.gather(wf_a(), wf_b())

    run(driver())
    cost_a, tokens_a = totals["a"]
    cost_b, tokens_b = totals["b"]
    assert abs(cost_a - 0.01) < 1e-9
    assert tokens_a == 100
    assert abs(cost_b - 0.05) < 1e-9
    assert tokens_b == 500


# ── 7. run_id is None after failed concurrent workflow ─────────────────────────

def test_run_id_cleared_after_failed_concurrent_workflow():
    """run_id must be reset to None even when the workflow raises mid-execution."""
    mc_ok  = IdClient(run_id="run-ok")
    mc_bad = IdClient(run_id="run-bad")
    run_ids_after: list[str | None] = []

    @workflow(name="good", client=mc_ok)
    async def good():
        await asyncio.sleep(0)

    @workflow(name="bad", client=mc_bad)
    async def bad():
        await asyncio.sleep(0)
        raise RuntimeError("explode")

    async def driver():
        results = await asyncio.gather(good(), bad(), return_exceptions=True)
        run_ids_after.append(get_run_id())
        return results

    run(driver())
    assert run_ids_after == [None]
