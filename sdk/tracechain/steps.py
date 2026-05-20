"""
@step decorator — instruments any function as a named, traced workflow step.

Usage:
    @step(name="fetch_data", retries=3, retry_delay=1.0)
    def fetch_data(url: str) -> dict:        # sync
        ...

    @step(name="fetch_data", retries=3, retry_delay=1.0)
    async def fetch_data(url: str) -> dict:  # async — works identically
        ...

Retry backoff:
    Attempt 1 → wait  retry_delay * 2^0  (+ jitter)
    Attempt 2 → wait  retry_delay * 2^1  (+ jitter)
    Attempt 3 → wait  retry_delay * 2^2  (+ jitter)
    ...capped at retry_max_delay.
"""
import asyncio
import functools
import inspect
import logging
import random
import time
from typing import Any, Callable, Optional

from .client import get_default_client
from .tracing import get_run_id, set_step_id, reset_step_id
from .workflow import _build_input_payload
from .otel import _otel_span, _otel_set_ok, _otel_set_error

logger = logging.getLogger("tracechain.step")


def step(
    name: str,
    retries: int = 0,
    retry_delay: float = 0.5,
    retry_max_delay: float = 30.0,
    retry_jitter: bool = True,
    metadata: Optional[dict] = None,
    client=None,
):
    """
    Decorator that instruments a function as a traced workflow step.

    Args:
        name:            Step name shown in the dashboard trace timeline.
        retries:         Number of retry attempts after the first failure (0 = no retries).
        retry_delay:     Base delay in seconds before the first retry. Doubles each attempt.
        retry_max_delay: Hard cap on delay between retries (seconds).
        retry_jitter:    Add a random offset up to retry_delay to spread concurrent retries.
        metadata:        Arbitrary key/value dict stored on the step record.
        client:          Custom TraceChainClient; uses the module-level default when omitted.
    """
    def decorator(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs) -> Any:
                tc = client or get_default_client()
                run_id = get_run_id()
                input_payload = _build_input_payload(fn, args, kwargs)

                step_id = None
                if run_id:
                    step_id = tc.create_step(
                        run_id=run_id,
                        step_name=name,
                        step_type="step",
                        input_payload=input_payload,
                        metadata=metadata,
                    )

                token = set_step_id(step_id) if step_id else None
                attempt = 0
                last_exc: Optional[Exception] = None
                start_ms = _now_ms()

                with _otel_span(f"step.{name}", {
                    "tracechain.step.name": name,
                    "tracechain.step.type": "step",
                }) as _span:
                    while attempt <= retries:
                        try:
                            result = await fn(*args, **kwargs)
                            duration = _now_ms() - start_ms
                            if run_id and step_id:
                                tc.complete_step(
                                    run_id=run_id,
                                    step_id=step_id,
                                    output_payload=result,
                                    duration_ms=duration,
                                    retry_count=attempt,
                                )
                            if token is not None:
                                reset_step_id(token)
                            _otel_set_ok(_span)
                            return result
                        except Exception as exc:
                            last_exc = exc
                            attempt += 1
                            if attempt <= retries:
                                delay = _backoff_delay(attempt, retry_delay, retry_max_delay, retry_jitter)
                                logger.warning(
                                    f"[TraceChain] Step '{name}' attempt {attempt}/{retries} "
                                    f"failed: {exc} — retrying in {delay:.2f}s"
                                )
                                await asyncio.sleep(delay)

                    duration = _now_ms() - start_ms
                    if run_id and step_id:
                        tc.fail_step(
                            run_id=run_id,
                            step_id=step_id,
                            error_message=str(last_exc),
                            retry_count=retries,
                        )
                    if token is not None:
                        reset_step_id(token)
                    _otel_set_error(_span, last_exc)  # type: ignore[arg-type]
                    raise last_exc  # type: ignore[misc]

            return async_wrapper

        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs) -> Any:
                tc = client or get_default_client()
                run_id = get_run_id()
                input_payload = _build_input_payload(fn, args, kwargs)

                step_id = None
                if run_id:
                    step_id = tc.create_step(
                        run_id=run_id,
                        step_name=name,
                        step_type="step",
                        input_payload=input_payload,
                        metadata=metadata,
                    )

                token = set_step_id(step_id) if step_id else None
                attempt = 0
                last_exc: Optional[Exception] = None
                start_ms = _now_ms()

                with _otel_span(f"step.{name}", {
                    "tracechain.step.name": name,
                    "tracechain.step.type": "step",
                }) as _span:
                    while attempt <= retries:
                        try:
                            result = fn(*args, **kwargs)
                            duration = _now_ms() - start_ms
                            if run_id and step_id:
                                tc.complete_step(
                                    run_id=run_id,
                                    step_id=step_id,
                                    output_payload=result,
                                    duration_ms=duration,
                                    retry_count=attempt,
                                )
                            if token is not None:
                                reset_step_id(token)
                            _otel_set_ok(_span)
                            return result
                        except Exception as exc:
                            last_exc = exc
                            attempt += 1
                            if attempt <= retries:
                                delay = _backoff_delay(attempt, retry_delay, retry_max_delay, retry_jitter)
                                logger.warning(
                                    f"[TraceChain] Step '{name}' attempt {attempt}/{retries} "
                                    f"failed: {exc} — retrying in {delay:.2f}s"
                                )
                                time.sleep(delay)

                    duration = _now_ms() - start_ms
                    if run_id and step_id:
                        tc.fail_step(
                            run_id=run_id,
                            step_id=step_id,
                            error_message=str(last_exc),
                            retry_count=retries,
                        )
                    if token is not None:
                        reset_step_id(token)
                    _otel_set_error(_span, last_exc)  # type: ignore[arg-type]
                    raise last_exc  # type: ignore[misc]

            return sync_wrapper

    return decorator


def _backoff_delay(attempt: int, base: float, max_delay: float, jitter: bool) -> float:
    """
    Exponential backoff with optional jitter.

    attempt  — 1-indexed retry number (1 = first retry, 2 = second, …)
    base     — base delay in seconds
    max_delay — hard cap
    jitter   — if True, adds a uniform random offset in [0, base) to spread load
    """
    delay = min(base * (2 ** (attempt - 1)), max_delay)
    if jitter:
        delay += random.uniform(0, base)
    return delay


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
