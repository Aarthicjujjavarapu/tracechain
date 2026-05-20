"""
Context propagation for TraceChain.

Manages the active trace_id, span_id stack, and run_id via threading.local
so that concurrent sync threads and async tasks each see isolated context.

Async note: contextvars.ContextVar propagates automatically into asyncio Tasks
created with asyncio.create_task() / TaskGroup, giving correct async isolation
without any special handling in user code.
"""
from __future__ import annotations

import threading
from contextvars import ContextVar
from typing import Optional

# ── async-safe context vars (propagate into asyncio.Task automatically) ────────

_trace_id:      ContextVar[Optional[str]] = ContextVar("trace_id",      default=None)
_span_id:       ContextVar[Optional[str]] = ContextVar("span_id",       default=None)
_run_id:        ContextVar[Optional[str]] = ContextVar("run_id",        default=None)

# ── token sum for cost propagation within a run ────────────────────────────────
_run_input_tokens:  ContextVar[int]   = ContextVar("run_input_tokens",  default=0)
_run_output_tokens: ContextVar[int]   = ContextVar("run_output_tokens", default=0)
_run_cost_usd:      ContextVar[float] = ContextVar("run_cost_usd",      default=0.0)


class TraceContext:
    """
    Namespace for reading and mutating the active trace context.
    All methods are safe to call from sync or async code.
    """

    # ── getters ──────────────────────────────────────────────────────────────

    @staticmethod
    def get_trace_id() -> Optional[str]:
        return _trace_id.get()

    @staticmethod
    def get_span_id() -> Optional[str]:
        return _span_id.get()

    @staticmethod
    def get_run_id() -> Optional[str]:
        return _run_id.get()

    # ── setters — return tokens so callers can restore previous values ─────────

    @staticmethod
    def set_trace_id(value: str):
        return _trace_id.set(value)

    @staticmethod
    def set_span_id(value: Optional[str]):
        return _span_id.set(value)

    @staticmethod
    def set_run_id(value: Optional[str]):
        return _run_id.set(value)

    # ── token/cost accumulation ───────────────────────────────────────────────

    @staticmethod
    def add_tokens(input_tokens: int = 0, output_tokens: int = 0, cost_usd: float = 0.0) -> None:
        _run_input_tokens.set(_run_input_tokens.get() + input_tokens)
        _run_output_tokens.set(_run_output_tokens.get() + output_tokens)
        _run_cost_usd.set(_run_cost_usd.get() + cost_usd)

    @staticmethod
    def get_run_totals() -> dict:
        return {
            "input_tokens":  _run_input_tokens.get(),
            "output_tokens": _run_output_tokens.get(),
            "total_tokens":  _run_input_tokens.get() + _run_output_tokens.get(),
            "cost_usd":      _run_cost_usd.get(),
        }

    @staticmethod
    def reset_run_totals() -> None:
        _run_input_tokens.set(0)
        _run_output_tokens.set(0)
        _run_cost_usd.set(0.0)
