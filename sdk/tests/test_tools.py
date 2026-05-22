"""Tests for observe_tool() — tool call tracing context manager."""
import asyncio
from unittest.mock import MagicMock

import pytest

from tracechain.tools import observe_tool, _validate_schema
from tracechain.tracing import set_run_id, reset_run_id


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_client(step_id="step-1"):
    mc = MagicMock()
    mc.create_step.return_value  = step_id
    mc.complete_step.return_value = None
    mc.fail_step.return_value     = None
    return mc


def _run_ctx(run_id="run-1"):
    class _Ctx:
        def __enter__(self):
            self._tok = set_run_id(run_id)
            return self
        def __exit__(self, *_):
            reset_run_id(self._tok)
    return _Ctx()


SCHEMA = {
    "type": "object",
    "properties": {
        "query":       {"type": "string"},
        "max_results": {"type": "integer"},
        "threshold":   {"type": "number"},
        "enabled":     {"type": "boolean"},
        "tags":        {"type": "array"},
    },
    "required": ["query"],
}


# ── _validate_schema ──────────────────────────────────────────────────────────

class TestValidateSchema:
    def test_valid_args_no_errors(self):
        errs = _validate_schema({"query": "hello", "max_results": 5}, SCHEMA)
        assert errs == []

    def test_missing_required(self):
        errs = _validate_schema({}, SCHEMA)
        assert any("query" in e for e in errs)

    def test_wrong_type_string(self):
        errs = _validate_schema({"query": 123}, SCHEMA)
        assert any("query" in e for e in errs)

    def test_wrong_type_integer(self):
        errs = _validate_schema({"query": "hi", "max_results": "five"}, SCHEMA)
        assert any("max_results" in e for e in errs)

    def test_bool_rejected_for_integer(self):
        errs = _validate_schema({"query": "hi", "max_results": True}, SCHEMA)
        assert any("max_results" in e for e in errs)

    def test_float_accepted_for_number(self):
        errs = _validate_schema({"query": "hi", "threshold": 0.5}, SCHEMA)
        assert errs == []

    def test_int_accepted_for_number(self):
        errs = _validate_schema({"query": "hi", "threshold": 1}, SCHEMA)
        assert errs == []

    def test_boolean_type(self):
        errs = _validate_schema({"query": "hi", "enabled": True}, SCHEMA)
        assert errs == []

    def test_array_type(self):
        errs = _validate_schema({"query": "hi", "tags": ["a", "b"]}, SCHEMA)
        assert errs == []

    def test_non_object_schema_returns_no_errors(self):
        errs = _validate_schema({"x": 1}, {"type": "string"})
        assert errs == []

    def test_optional_property_missing_is_ok(self):
        errs = _validate_schema({"query": "hello"}, SCHEMA)
        assert errs == []


# ── observe_tool basic ────────────────────────────────────────────────────────

class TestObserveTool:
    def test_no_op_outside_workflow(self):
        """Should not create a step when there's no active run_id."""
        mc = _mock_client()
        with observe_tool("search", args={"query": "test"}, client=mc) as obs:
            obs.record({"results": []})
        mc.create_step.assert_not_called()

    def test_creates_step_inside_run(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_tool("web_search", args={"query": "AI"}, client=mc) as obs:
                obs.record(["result1"])
        mc.create_step.assert_called_once()
        kw = mc.create_step.call_args.kwargs
        assert kw["step_name"] == "tool:web_search"
        assert kw["run_id"] == "run-1"

    def test_step_name_contains_tool_prefix(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_tool("send_email", args={}, client=mc) as obs:
                obs.record(True)
        assert mc.create_step.call_args.kwargs["step_name"] == "tool:send_email"

    def test_complete_step_called_on_success(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_tool("calc", args={"x": 1}, client=mc) as obs:
                obs.record(42)
        mc.complete_step.assert_called_once()
        mc.fail_step.assert_not_called()

    def test_fail_step_called_on_exception(self):
        mc = _mock_client()
        with _run_ctx():
            with pytest.raises(RuntimeError):
                with observe_tool("search", args={}, client=mc):
                    raise RuntimeError("api down")
        mc.fail_step.assert_called_once()
        assert "api down" in mc.fail_step.call_args.kwargs["error_message"]
        mc.complete_step.assert_not_called()

    def test_input_args_captured_in_step_payload(self):
        mc = _mock_client()
        args = {"query": "hello", "max_results": 10}
        with _run_ctx():
            with observe_tool("search", args=args, client=mc) as obs:
                obs.record([])
        payload = mc.create_step.call_args.kwargs["input_payload"]
        assert payload["query"] == "hello"
        assert payload["max_results"] == 10

    def test_result_passed_to_complete_step(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_tool("lookup", args={}, client=mc) as obs:
                obs.record({"found": True, "data": "xyz"})
        out = mc.complete_step.call_args.kwargs["output_payload"]
        assert out["found"] is True

    def test_duration_ms_non_negative(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_tool("noop", args={}, client=mc) as obs:
                obs.record(None)
        assert mc.complete_step.call_args.kwargs["duration_ms"] >= 0


# ── schema validation via observe_tool ───────────────────────────────────────

class TestSchemaValidation:
    def test_valid_schema_passes(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_tool("search", args={"query": "test"}, schema=SCHEMA, client=mc) as obs:
                obs.record([])
        mc.create_step.assert_called_once()

    def test_missing_required_raises_before_step(self):
        mc = _mock_client()
        with _run_ctx():
            with pytest.raises(ValueError, match="Missing required argument"):
                with observe_tool("search", args={}, schema=SCHEMA, client=mc):
                    pass
        mc.create_step.assert_not_called()

    def test_wrong_type_raises_before_step(self):
        mc = _mock_client()
        with _run_ctx():
            with pytest.raises(ValueError, match="expected string"):
                with observe_tool("search", args={"query": 99}, schema=SCHEMA, client=mc):
                    pass
        mc.create_step.assert_not_called()

    def test_error_message_contains_argument(self):
        """Error message must contain 'argument' so TOOL_ARGUMENT_ERROR classifier fires."""
        with pytest.raises(ValueError) as exc_info:
            with observe_tool("search", args={}, schema=SCHEMA) as obs:
                obs.record(None)
        assert "argument" in str(exc_info.value).lower()

    def test_no_schema_no_validation(self):
        mc = _mock_client()
        with _run_ctx():
            with observe_tool("any", args={"anything": object()}, client=mc) as obs:
                obs.record(None)
        mc.create_step.assert_called_once()


# ── async ────────────────────────────────────────────────────────────────────

class TestAsync:
    def test_async_context_manager_success(self):
        mc = _mock_client()

        async def run():
            with _run_ctx():
                async with observe_tool("async_search", args={"query": "q"}, client=mc) as obs:
                    obs.record(["r1", "r2"])

        asyncio.run(run())
        mc.complete_step.assert_called_once()

    def test_async_context_manager_failure(self):
        mc = _mock_client()

        async def run():
            with _run_ctx():
                with pytest.raises(IOError):
                    async with observe_tool("async_tool", args={}, client=mc):
                        raise IOError("network error")

        asyncio.run(run())
        mc.fail_step.assert_called_once()
        assert "network error" in mc.fail_step.call_args.kwargs["error_message"]
