"""
observe_tool() — context manager for tracing tool / function calls.

Usage
─────
Basic:
    from tracechain import observe_tool

    with observe_tool("web_search", args={"query": query}) as obs:
        result = web_search(query)
        obs.record(result)

With JSON Schema validation:
    SCHEMA = {
        "type": "object",
        "properties": {
            "query":       {"type": "string"},
            "max_results": {"type": "integer"},
        },
        "required": ["query"],
    }

    with observe_tool("web_search", args={"query": query, "max_results": 5},
                      schema=SCHEMA) as obs:
        result = web_search(query, max_results=5)
        obs.record(result)

Async:
    async with observe_tool("web_search", args={"query": query}) as obs:
        result = await async_web_search(query)
        obs.record(result)

The step is named "tool:<name>" so the failure classifier automatically
detects TOOL_CALL_FAILURE and TOOL_ARGUMENT_ERROR patterns.
Schema validation errors are raised as ValueError before the tool runs,
producing an error message containing "argument" so the classifier can
detect TOOL_ARGUMENT_ERROR from the error text.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from .client import get_default_client, _safe_json
from .tracing import get_run_id, set_step_id, reset_step_id
from .otel import _otel_start_span, _otel_end_span


# ── Lightweight JSON Schema validator ─────────────────────────────────────────

_JSON_TYPE_MAP: dict[str, Any] = {
    "string":  str,
    "integer": int,
    "number":  (int, float),
    "boolean": bool,
    "array":   list,
    "object":  dict,
}


def _validate_schema(args: dict, schema: dict) -> list[str]:
    """
    Validate args against a JSON Schema object definition.
    Supports: required, properties with type checks (one level deep).
    Returns a list of human-readable violation messages.
    """
    errors: list[str] = []
    if not isinstance(schema, dict) or schema.get("type") != "object":
        return errors

    for key in schema.get("required", []):
        if key not in args:
            errors.append(f"Missing required argument: '{key}'")

    for key, prop in schema.get("properties", {}).items():
        if key not in args:
            continue
        expected = prop.get("type")
        if expected not in _JSON_TYPE_MAP:
            continue
        val = args[key]
        py_type = _JSON_TYPE_MAP[expected]
        # bool is a subclass of int — guard explicitly for integer type
        if expected == "integer" and isinstance(val, bool):
            errors.append(f"Argument '{key}': expected integer, got boolean")
        elif not isinstance(val, py_type):
            errors.append(
                f"Argument '{key}': expected {expected}, got {type(val).__name__}"
            )
    return errors


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


# ── Public factory ────────────────────────────────────────────────────────────

def observe_tool(
    name: str,
    *,
    args: Optional[dict] = None,
    schema: Optional[dict] = None,
    client: Any = None,
) -> "_ToolObserver":
    """
    Return a context manager (sync or async) that traces a tool/function call.

    Args:
        name:   Tool name (e.g. "web_search", "send_email").
        args:   Input arguments as a dict. Captured in the step payload.
        schema: Optional JSON Schema for the args object. Validation fires
                before the tool runs — failures raise ValueError immediately
                so the wrapping step records the error correctly.
        client: Override the default TraceChainClient.
    """
    return _ToolObserver(name=name, args=args or {}, schema=schema, client=client)


# ── Internal context manager ──────────────────────────────────────────────────

class _ToolObserver:
    def __init__(
        self,
        *,
        name: str,
        args: dict,
        schema: Optional[dict],
        client: Any,
    ) -> None:
        self._name         = name
        self._args         = args
        self._schema       = schema
        self._client_override = client

        self._result:     Any           = None
        self._error:      Optional[str] = None
        self._start_ms:   int           = 0

        self._tc:         Any           = None
        self._run_id:     Optional[str] = None
        self._step_id:    Optional[str] = None
        self._step_token: Any           = None
        self._span:       Any           = None
        self._otel_token: Any           = None

    # ── shared enter/exit body ────────────────────────────────────────────────

    def _begin(self) -> "_ToolObserver":
        # Validate before creating the step so invalid args never show as a
        # "running" step — the error surfaces at the callsite.
        if self._schema:
            violations = _validate_schema(self._args, self._schema)
            if violations:
                raise ValueError(
                    f"Invalid arguments for tool '{self._name}': "
                    + "; ".join(violations)
                )

        self._start_ms = _now_ms()
        self._tc       = self._client_override or get_default_client()
        self._run_id   = get_run_id()

        self._span, self._otel_token = _otel_start_span(
            f"tool.{self._name}",
            {"tracechain.tool.name": self._name},
        )

        if self._run_id:
            step_id = self._tc.create_step(
                run_id=self._run_id,
                step_name=f"tool:{self._name}",
                step_type="step",
                input_payload=_safe_json(self._args),
                metadata={"tracechain.kind": "tool"},
            )
            self._step_id = step_id
            if step_id:
                self._step_token = set_step_id(step_id)

        return self

    def _end(self, exc: Optional[BaseException]) -> None:
        latency = _now_ms() - self._start_ms
        if exc is not None:
            self._error = str(exc)

        _otel_end_span(self._span, self._otel_token, error=exc)

        if self._run_id and self._step_id:
            if self._error:
                self._tc.fail_step(
                    run_id=self._run_id,
                    step_id=self._step_id,
                    error_message=self._error,
                )
            else:
                self._tc.complete_step(
                    run_id=self._run_id,
                    step_id=self._step_id,
                    output_payload=_safe_json(self._result),
                    duration_ms=latency,
                )

        if self._step_token is not None:
            reset_step_id(self._step_token)

    # ── public API ────────────────────────────────────────────────────────────

    def record(self, result: Any) -> None:
        """Capture the tool's return value. Call inside the context block."""
        self._result = result

    # ── sync context manager ──────────────────────────────────────────────────

    def __enter__(self) -> "_ToolObserver":
        return self._begin()

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._end(exc_val)
        return False

    # ── async context manager ─────────────────────────────────────────────────

    async def __aenter__(self) -> "_ToolObserver":
        return self._begin()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._end(exc_val)
        return False
