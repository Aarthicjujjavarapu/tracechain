"""
@batch_step decorator — trace a list of items with per-item spans.

Usage (sync):
    @batch_step(name="embed_docs")
    def embed_doc(doc: str) -> list[float]:
        return model.embed(doc)

    result = embed_doc(["doc1", "doc2", "doc3"])
    print(result.success_count, result.failed_count)
    for embedding in result:          # iterates over per-item results
        ...

Usage (async, with concurrency cap):
    @batch_step(name="embed_docs", concurrency=10)
    async def embed_doc(doc: str) -> list[float]:
        return await model.embed(doc)

    result = await embed_doc(["doc1", "doc2", "doc3"])

Partial failures (default):
    @batch_step(name="risky", raise_on_error=False)   # default
    def risky(item): ...

    result = risky(items)
    ok   = result.success_results          # items that succeeded
    errs = [(i, e) for i, e in enumerate(result.errors) if e]

Fail fast:
    @batch_step(name="strict", raise_on_error=True)
    def strict(item): ...
"""
from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable, Generic, Optional, TypeVar

from .client import get_default_client, _safe_json
from .tracing import get_run_id, set_step_id, reset_step_id
from .otel import _otel_span, _otel_set_ok, _otel_set_error

logger = logging.getLogger("tracechain.batch")

T = TypeVar("T")


@dataclass
class BatchResult(Generic[T]):
    """
    Holds per-item results and errors from a @batch_step invocation.

    Iterating or indexing yields per-item results (None for failed items).
    Check `.errors[i]` to distinguish a None result from a failure.
    """
    results: list[Optional[T]]
    errors: list[Optional[Exception]]

    def __iter__(self):
        return iter(self.results)

    def __len__(self):
        return len(self.results)

    def __getitem__(self, idx):
        return self.results[idx]

    @property
    def success_count(self) -> int:
        return sum(1 for e in self.errors if e is None)

    @property
    def failed_count(self) -> int:
        return sum(1 for e in self.errors if e is not None)

    @property
    def success_results(self) -> list[T]:
        """Results for items that did not raise."""
        return [r for r, e in zip(self.results, self.errors) if e is None]


def batch_step(
    name: str,
    concurrency: int = 1,
    raise_on_error: bool = False,
    trace_items: bool = False,
    metadata: Optional[dict] = None,
    client=None,
):
    """
    Decorator that instruments a single-item function to process a list of items.

    The decorated function must accept one positional argument (the item).
    Call the wrapper with a list; it returns a BatchResult.

    Args:
        name:           Step name shown in the dashboard trace timeline.
        concurrency:    Max parallel workers (async: asyncio semaphore;
                        sync: ThreadPoolExecutor). 1 = sequential.
        raise_on_error: Re-raise the first item error after processing.
                        When False (default), failures are collected and
                        returned in BatchResult.errors.
        trace_items:    Create an individual backend step per item.
                        Useful for small batches; disable for >50 items.
        metadata:       Arbitrary key/value dict stored on the batch step.
        client:         Custom TraceChainClient; uses default when omitted.
    """
    def decorator(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(items: list, **kwargs) -> BatchResult:
                return await _run_async(
                    fn, items, kwargs,
                    name=name, concurrency=concurrency,
                    raise_on_error=raise_on_error, trace_items=trace_items,
                    metadata=metadata, client=client,
                )
            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(items: list, **kwargs) -> BatchResult:
            return _run_sync(
                fn, items, kwargs,
                name=name, concurrency=concurrency,
                raise_on_error=raise_on_error, trace_items=trace_items,
                metadata=metadata, client=client,
            )
        return sync_wrapper

    return decorator


# ── sync implementation ────────────────────────────────────────────────────────

def _run_sync(fn, items, kwargs, *, name, concurrency, raise_on_error,
              trace_items, metadata, client):
    tc = client or get_default_client()
    run_id = get_run_id()
    n = len(items)

    batch_id = None
    if run_id:
        batch_id = tc.create_step(
            run_id=run_id,
            step_name=name,
            step_type="batch_step",
            input_payload={"batch_size": n, "concurrency": concurrency},
            metadata=metadata,
        )

    batch_token = set_step_id(batch_id) if batch_id else None
    start_ms = _now_ms()
    results: list[Any] = [None] * n
    errors: list[Any]  = [None] * n

    def _process(idx_item):
        idx, item = idx_item
        item_id = None
        if trace_items and run_id and batch_id:
            item_id = tc.create_step(
                run_id=run_id,
                step_name=f"{name}[{idx}]",
                step_type="batch_item",
                input_payload={"item": _safe_item(item), "index": idx},
            )
        item_token = set_step_id(item_id) if item_id else None
        t0 = _now_ms()
        try:
            r = fn(item, **kwargs)
            if item_id and run_id:
                tc.complete_step(
                    run_id=run_id, step_id=item_id,
                    output_payload={"result": _safe_item(r)},
                    duration_ms=_now_ms() - t0,
                )
            return idx, r, None
        except Exception as exc:
            if item_id and run_id:
                tc.fail_step(run_id=run_id, step_id=item_id, error_message=str(exc))
            return idx, None, exc
        finally:
            if item_token is not None:
                reset_step_id(item_token)

    with _otel_span(f"batch.{name}", {
        "tracechain.batch.name": name,
        "tracechain.batch.size": n,
    }) as _span:
        first_error = None

        if concurrency > 1:
            with ThreadPoolExecutor(max_workers=concurrency) as pool:
                futs = {pool.submit(_process, (i, item)): i for i, item in enumerate(items)}
                for fut in as_completed(futs):
                    idx, r, exc = fut.result()
                    results[idx] = r
                    errors[idx]  = exc
                    if exc and raise_on_error and first_error is None:
                        first_error = exc
        else:
            for i, item in enumerate(items):
                idx, r, exc = _process((i, item))
                results[idx] = r
                errors[idx]  = exc
                if exc and raise_on_error:
                    first_error = exc
                    break

        duration = _now_ms() - start_ms
        failed   = sum(1 for e in errors if e is not None)

        if run_id and batch_id:
            if first_error is None:
                tc.complete_step(
                    run_id=run_id, step_id=batch_id,
                    output_payload={
                        "batch_size": n,
                        "success_count": n - failed,
                        "failed_count": failed,
                    },
                    duration_ms=duration,
                )
            else:
                tc.fail_step(
                    run_id=run_id, step_id=batch_id,
                    error_message=f"{failed}/{n} items failed",
                )

        if batch_token is not None:
            reset_step_id(batch_token)

        if first_error is not None:
            _otel_set_error(_span, first_error)
            raise first_error

        _otel_set_ok(_span)

    return BatchResult(results=results, errors=errors)


# ── async implementation ───────────────────────────────────────────────────────

async def _run_async(fn, items, kwargs, *, name, concurrency, raise_on_error,
                     trace_items, metadata, client):
    tc = client or get_default_client()
    run_id = get_run_id()
    n = len(items)

    batch_id = None
    if run_id:
        batch_id = tc.create_step(
            run_id=run_id,
            step_name=name,
            step_type="batch_step",
            input_payload={"batch_size": n, "concurrency": concurrency},
            metadata=metadata,
        )

    batch_token = set_step_id(batch_id) if batch_id else None
    start_ms = _now_ms()
    results: list[Any] = [None] * n
    errors: list[Any]  = [None] * n
    sem = asyncio.Semaphore(concurrency)

    async def _process(idx, item):
        async with sem:
            item_id = None
            if trace_items and run_id and batch_id:
                item_id = tc.create_step(
                    run_id=run_id,
                    step_name=f"{name}[{idx}]",
                    step_type="batch_item",
                    input_payload={"item": _safe_item(item), "index": idx},
                )
            item_token = set_step_id(item_id) if item_id else None
            t0 = _now_ms()
            try:
                r = await fn(item, **kwargs)
                if item_id and run_id:
                    tc.complete_step(
                        run_id=run_id, step_id=item_id,
                        output_payload={"result": _safe_item(r)},
                        duration_ms=_now_ms() - t0,
                    )
                return idx, r, None
            except Exception as exc:
                if item_id and run_id:
                    tc.fail_step(run_id=run_id, step_id=item_id, error_message=str(exc))
                return idx, None, exc
            finally:
                if item_token is not None:
                    reset_step_id(item_token)

    with _otel_span(f"batch.{name}", {
        "tracechain.batch.name": name,
        "tracechain.batch.size": n,
    }) as _span:
        tasks = [asyncio.create_task(_process(i, item)) for i, item in enumerate(items)]
        gathered = await asyncio.gather(*tasks)

        first_error = None
        for idx, r, exc in gathered:
            results[idx] = r
            errors[idx]  = exc
            if exc and raise_on_error and first_error is None:
                first_error = exc

        duration = _now_ms() - start_ms
        failed   = sum(1 for e in errors if e is not None)

        if run_id and batch_id:
            if first_error is None:
                tc.complete_step(
                    run_id=run_id, step_id=batch_id,
                    output_payload={
                        "batch_size": n,
                        "success_count": n - failed,
                        "failed_count": failed,
                    },
                    duration_ms=duration,
                )
            else:
                tc.fail_step(
                    run_id=run_id, step_id=batch_id,
                    error_message=f"{failed}/{n} items failed",
                )

        if batch_token is not None:
            reset_step_id(batch_token)

        if first_error is not None:
            _otel_set_error(_span, first_error)
            raise first_error

        _otel_set_ok(_span)

    return BatchResult(results=results, errors=errors)


def _safe_item(value: Any) -> Any:
    try:
        return _safe_json(value)
    except Exception:
        return str(value)


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
