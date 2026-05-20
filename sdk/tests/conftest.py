"""Shared fixtures for TraceChain SDK tests."""
import pytest


class MockClient:
    """Drop-in replacement for TraceChainClient that records calls and never hits HTTP."""

    def __init__(self, run_id="run-abc", step_id="step-xyz"):
        self._run_id  = run_id
        self._step_id = step_id
        self.calls: list[tuple[str, dict]] = []

    def _record(self, method: str, **kwargs):
        self.calls.append((method, kwargs))

    def called(self, method: str) -> bool:
        return any(name == method for name, _ in self.calls)

    def call_args(self, method: str) -> dict:
        for name, kwargs in self.calls:
            if name == method:
                return kwargs
        raise AssertionError(f"'{method}' was never called")

    # ── runs ──────────────────────────────────────────────────────────────────
    def create_run(self, workflow_name, input_payload, metadata=None):
        self._record("create_run", workflow_name=workflow_name,
                     input_payload=input_payload, metadata=metadata)
        return self._run_id

    def complete_run(self, run_id, output_payload, total_cost=None, total_tokens=None):
        self._record("complete_run", run_id=run_id, output_payload=output_payload,
                     total_cost=total_cost, total_tokens=total_tokens)

    def fail_run(self, run_id, error_message):
        self._record("fail_run", run_id=run_id, error_message=error_message)

    # ── steps ─────────────────────────────────────────────────────────────────
    def create_step(self, run_id, step_name, step_type, input_payload, metadata=None):
        self._record("create_step", run_id=run_id, step_name=step_name,
                     step_type=step_type, input_payload=input_payload)
        return self._step_id

    def complete_step(self, run_id, step_id, output_payload, duration_ms, retry_count=0):
        self._record("complete_step", run_id=run_id, step_id=step_id,
                     output_payload=output_payload, duration_ms=duration_ms,
                     retry_count=retry_count)

    def fail_step(self, run_id, step_id, error_message, retry_count=0):
        self._record("fail_step", run_id=run_id, step_id=step_id,
                     error_message=error_message, retry_count=retry_count)

    # ── misc ──────────────────────────────────────────────────────────────────
    def log_llm_call(self, **kwargs):
        self._record("log_llm_call", **kwargs)

    def post_evaluation(self, run_id, scores):
        self._record("post_evaluation", run_id=run_id, scores=scores)

    def trigger_replay(self, run_id):
        self._record("trigger_replay", run_id=run_id)
        return "new-run-id"


@pytest.fixture
def mock_client():
    return MockClient()


class FailingClient(MockClient):
    """MockClient whose create_run always returns None (backend unreachable)."""

    def create_run(self, **kwargs):
        self._record("create_run", **kwargs)
        return None
