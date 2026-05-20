"""
@workflow decorator — wraps a function and creates a full workflow run record.

Usage:
    @workflow(name="my_pipeline")
    def my_pipeline(query: str):          # sync
        ...

    @workflow(name="my_pipeline")
    async def my_pipeline(query: str):    # async — works identically
        ...
"""
import functools
import inspect
import logging
from typing import Any, Callable, Optional

from .client import get_default_client, _safe_json
from .tracing import (
    set_run_id, reset_run_id,
    reset_run_totals, get_run_totals,
)
from .otel import _otel_span, _otel_set_ok, _otel_set_error

logger = logging.getLogger("tracechain.workflow")


def workflow(
    name: str,
    metadata: Optional[dict] = None,
    client=None,
):
    """
    Decorator that instruments a function as a TraceChain workflow.
    Supports both sync and async functions transparently.
    """
    def decorator(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs) -> Any:
                tc = client or get_default_client()
                input_payload = _build_input_payload(fn, args, kwargs)
                run_id = tc.create_run(
                    workflow_name=name,
                    input_payload=input_payload,
                    metadata=metadata,
                )
                token = set_run_id(run_id) if run_id else None
                reset_run_totals()
                with _otel_span(f"workflow.{name}", {"tracechain.workflow.name": name}) as _span:
                    try:
                        result = await fn(*args, **kwargs)
                        if run_id:
                            total_cost, total_tokens = get_run_totals()
                            tc.complete_run(
                                run_id=run_id,
                                output_payload=result,
                                total_cost=total_cost if total_cost > 0 else None,
                                total_tokens=total_tokens if total_tokens > 0 else None,
                            )
                        _otel_set_ok(_span)
                        return result
                    except Exception as exc:
                        if run_id:
                            tc.fail_run(run_id=run_id, error_message=str(exc))
                        _otel_set_error(_span, exc)
                        raise
                    finally:
                        if token is not None:
                            reset_run_id(token)
            return async_wrapper

        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs) -> Any:
                tc = client or get_default_client()
                input_payload = _build_input_payload(fn, args, kwargs)
                run_id = tc.create_run(
                    workflow_name=name,
                    input_payload=input_payload,
                    metadata=metadata,
                )
                token = set_run_id(run_id) if run_id else None
                reset_run_totals()
                with _otel_span(f"workflow.{name}", {"tracechain.workflow.name": name}) as _span:
                    try:
                        result = fn(*args, **kwargs)
                        if run_id:
                            total_cost, total_tokens = get_run_totals()
                            tc.complete_run(
                                run_id=run_id,
                                output_payload=result,
                                total_cost=total_cost if total_cost > 0 else None,
                                total_tokens=total_tokens if total_tokens > 0 else None,
                            )
                        _otel_set_ok(_span)
                        return result
                    except Exception as exc:
                        if run_id:
                            tc.fail_run(run_id=run_id, error_message=str(exc))
                        _otel_set_error(_span, exc)
                        raise
                    finally:
                        if token is not None:
                            reset_run_id(token)
            return sync_wrapper

    return decorator


def _build_input_payload(fn: Callable, args: tuple, kwargs: dict) -> dict:
    """Safely map positional/keyword args to a JSON-serialisable dict."""
    try:
        sig = inspect.signature(fn)
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        return {k: _safe_json(v) for k, v in bound.arguments.items()}
    except Exception:
        return {"args": _safe_json(list(args)), "kwargs": _safe_json(kwargs)}
