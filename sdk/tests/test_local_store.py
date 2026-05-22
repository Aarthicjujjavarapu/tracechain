"""
Tests for LocalClient — the zero-infrastructure SQLite backend.
Each test gets a fresh DB via the tmp_path fixture.
"""
import os
import pytest

from tracechain.local_store import LocalClient
from tracechain.workflow import workflow
from tracechain.steps import step
from tracechain.tracing import set_run_id, reset_run_id


@pytest.fixture
def db(tmp_path):
    return LocalClient(db_path=str(tmp_path / "test.db"))


# ── DB initialisation ──────────────────────────────────────────────────────────

def test_db_file_created(tmp_path):
    path = str(tmp_path / "traces.db")
    LocalClient(db_path=path)
    assert os.path.exists(path)


def test_tables_exist(db):
    tables = {
        row[0] for row in
        db._conn().execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"workflow_runs", "trace_steps", "llm_calls", "evaluation_results"} <= tables


# ── runs ───────────────────────────────────────────────────────────────────────

def test_create_run_returns_id(db):
    run_id = db.create_run("my_wf", {"x": 1})
    assert isinstance(run_id, str) and len(run_id) == 36  # UUID


def test_create_run_status_is_running(db):
    run_id = db.create_run("my_wf", {})
    row = db.get_run(run_id)
    assert row["status"] == "running"


def test_complete_run_sets_success(db):
    run_id = db.create_run("my_wf", {})
    db.complete_run(run_id, output_payload={"answer": 42})
    row = db.get_run(run_id)
    assert row["status"] == "success"


def test_complete_run_stores_output(db):
    import json
    run_id = db.create_run("my_wf", {})
    db.complete_run(run_id, output_payload={"answer": 42})
    row = db.get_run(run_id)
    assert json.loads(row["output_payload"]) == {"answer": 42}


def test_complete_run_records_duration(db):
    run_id = db.create_run("my_wf", {})
    db.complete_run(run_id, output_payload=None)
    row = db.get_run(run_id)
    assert row["duration_ms"] is not None
    assert row["duration_ms"] >= 0


def test_complete_run_stores_cost_and_tokens(db):
    run_id = db.create_run("my_wf", {})
    db.complete_run(run_id, output_payload=None, total_cost=0.00123, total_tokens=500)
    row = db.get_run(run_id)
    assert abs(row["total_cost"] - 0.00123) < 1e-9
    assert row["total_tokens"] == 500


def test_fail_run_sets_failed(db):
    run_id = db.create_run("my_wf", {})
    db.fail_run(run_id, "something broke")
    row = db.get_run(run_id)
    assert row["status"] == "failed"
    assert row["error_message"] == "something broke"


def test_get_runs_returns_all(db):
    db.create_run("wf_a", {})
    db.create_run("wf_b", {})
    runs = db.get_runs()
    assert len(runs) == 2


# ── steps ──────────────────────────────────────────────────────────────────────

def test_create_step_returns_id(db):
    run_id = db.create_run("wf", {})
    step_id = db.create_step(run_id, "fetch", "step", {})
    assert isinstance(step_id, str) and len(step_id) == 36


def test_complete_step_sets_success(db):
    run_id  = db.create_run("wf", {})
    step_id = db.create_step(run_id, "fetch", "step", {})
    db.complete_step(run_id, step_id, output_payload=["doc1"], duration_ms=123)
    steps = db.get_steps(run_id)
    assert steps[0]["status"] == "success"
    assert steps[0]["duration_ms"] == 123


def test_fail_step_sets_failed(db):
    run_id  = db.create_run("wf", {})
    step_id = db.create_step(run_id, "fetch", "step", {})
    db.fail_step(run_id, step_id, "timeout", retry_count=2)
    steps = db.get_steps(run_id)
    assert steps[0]["status"] == "failed"
    assert steps[0]["retry_count"] == 2


# ── llm calls ──────────────────────────────────────────────────────────────────

def test_log_llm_call_stored(db):
    run_id = db.create_run("wf", {})
    db.log_llm_call(
        run_id=run_id, step_id=None,
        provider="openai", model="gpt-4o-mini",
        prompt="Hello", response="Hi",
        input_tokens=10, output_tokens=5, total_tokens=15,
        estimated_cost=0.000005, latency_ms=320, temperature=0.7,
        status="success",
    )
    calls = db.get_llm_calls(run_id)
    assert len(calls) == 1
    c = calls[0]
    assert c["model"] == "gpt-4o-mini"
    assert c["total_tokens"] == 15
    assert c["is_stream"] == 0


def test_log_llm_call_stream_fields(db):
    run_id = db.create_run("wf", {})
    db.log_llm_call(
        run_id=run_id, step_id=None,
        provider="openai", model="gpt-4o-mini",
        prompt="Hi", response="Hello!",
        input_tokens=10, output_tokens=5, total_tokens=15,
        estimated_cost=0.000005, latency_ms=800, temperature=0.7,
        status="success",
        time_to_first_token_ms=42, is_stream=True,
    )
    c = db.get_llm_calls(run_id)[0]
    assert c["is_stream"] == 1
    assert c["time_to_first_token_ms"] == 42


# ── evaluations ────────────────────────────────────────────────────────────────

def test_post_evaluation_stored(db):
    run_id = db.create_run("wf", {})
    db.post_evaluation(run_id, {
        "relevance_score": 0.9,
        "groundedness_score": 0.8,
        "hallucination_risk": 0.1,
        "quality_score": 0.85,
    })
    row = db._conn().execute(
        "SELECT * FROM evaluation_results WHERE run_id=?", (run_id,)
    ).fetchone()
    assert row is not None
    assert abs(row["quality_score"] - 0.85) < 1e-9


# ── replay ─────────────────────────────────────────────────────────────────────

def test_trigger_replay_creates_new_run(db):
    run_id = db.create_run("wf", {"q": "hello"})
    new_id = db.trigger_replay(run_id)
    assert new_id is not None
    assert new_id != run_id


def test_trigger_replay_sets_is_replay(db):
    run_id = db.create_run("wf", {})
    new_id = db.trigger_replay(run_id)
    row = db.get_run(new_id)
    assert row["is_replay"] == 1
    assert row["original_run_id"] == run_id


def test_trigger_replay_unknown_run_returns_none(db):
    assert db.trigger_replay("nonexistent-id") is None


# ── decorator integration ──────────────────────────────────────────────────────

def test_workflow_decorator_writes_to_local_db(tmp_path):
    lc = LocalClient(db_path=str(tmp_path / "int.db"))

    @workflow(name="integration_wf", client=lc)
    def my_wf(x):
        return x * 2

    result = my_wf(21)
    assert result == 42

    runs = lc.get_runs()
    assert len(runs) == 1
    assert runs[0]["workflow_name"] == "integration_wf"
    assert runs[0]["status"] == "success"


def test_step_decorator_writes_to_local_db(tmp_path):
    lc = LocalClient(db_path=str(tmp_path / "int.db"))
    token = set_run_id("local-run-1")
    try:
        @step(name="compute", client=lc)
        def compute(a, b):
            return a + b

        result = compute(3, 4)
        assert result == 7

        # step was recorded
        steps = lc.get_steps("local-run-1")
        assert len(steps) == 1
        assert steps[0]["step_name"] == "compute"
        assert steps[0]["status"] == "success"
    finally:
        reset_run_id(token)


def test_workflow_failure_recorded(tmp_path):
    lc = LocalClient(db_path=str(tmp_path / "fail.db"))

    @workflow(name="broken_wf", client=lc)
    def broken():
        raise ValueError("oops")

    with pytest.raises(ValueError):
        broken()

    runs = lc.get_runs()
    assert runs[0]["status"] == "failed"
    assert "oops" in runs[0]["error_message"]


# ── env-var activation ─────────────────────────────────────────────────────────

def test_get_default_client_returns_local_client(tmp_path, monkeypatch):
    import tracechain.client as client_mod
    # Reset the cached global so get_default_client re-evaluates
    client_mod._default_client = None
    monkeypatch.setenv("TRACECHAIN_MODE", "local")
    monkeypatch.setenv("TRACECHAIN_DB_PATH", str(tmp_path / "env.db"))

    from tracechain.client import get_default_client
    c = get_default_client()
    assert isinstance(c, LocalClient)

    # Clean up global so other tests aren't affected
    client_mod._default_client = None
