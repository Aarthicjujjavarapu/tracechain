---
id: context-propagation
title: Context Propagation
sidebar_position: 2
---

# Context Propagation

Understanding how TraceChain propagates `run_id` and `step_id` through your code helps you write correct, observable workflows — especially in async or multi-threaded environments.

## The mechanism

TraceChain uses Python's [`contextvars`](https://docs.python.org/3/library/contextvars.html) module. Each variable lives in a `ContextVar`:

```python
_current_run_id:  ContextVar[str | None] = ContextVar("tracechain_run_id",  default=None)
_current_step_id: ContextVar[str | None] = ContextVar("tracechain_step_id", default=None)
```

When `@workflow` starts, it calls `ContextVar.set(run_id)` and saves the returned reset token. On exit, it calls `ContextVar.reset(token)` to restore the previous value. This makes nesting safe.

## Synchronous code

Works automatically — no configuration needed:

```python
@workflow(name="pipeline")
def pipeline(query):
    return process(query)          # inherits run_id

@step(name="process")
def process(query):
    return summarise(query)        # inherits run_id + step_id

@llm_step(name="summarise", model="gpt-4o-mini")
def summarise(query):
    ...                            # inherits run_id + step_id
```

## Multi-threading

Python threads **inherit a copy** of the context at the time they are created. Writes inside a thread are local to that thread and do not affect the parent.

```python
@workflow(name="parallel")
def parallel(queries: list[str]):
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as exe:
        # each thread starts with run_id set to the current value
        results = list(exe.map(process_one, queries))
    return results

@step(name="process_one")
def process_one(query: str):
    print(get_run_id())   # correct — inherited from parent thread
    ...
```

Each `process_one` call records its step under the correct `run_id`.

## `asyncio`

`contextvars` work correctly with `asyncio`. Each `Task` inherits a copy of the context:

```python
import asyncio
from tracechain import workflow, step, get_run_id

@workflow(name="async_pipeline")
async def async_pipeline(queries: list[str]):
    tasks = [asyncio.create_task(process(q)) for q in queries]
    return await asyncio.gather(*tasks)

@step(name="process")
async def process(query: str):
    print(get_run_id())   # correct
    ...
```

:::note
The TraceChain SDK itself is synchronous (uses `httpx` in non-async mode). For async workflows, the decorator wraps the `async def` function transparently. The backend HTTP calls happen in the event loop — keep `TRACECHAIN_TIMEOUT` short (2–3 s) to avoid blocking the loop.
:::

For true async HTTP, use `httpx.AsyncClient` inside your own `TraceChainClient` subclass.

## Subprocess boundaries

Context does **not** cross process boundaries. Pass IDs explicitly:

```python
import subprocess
from tracechain import get_run_id, get_step_id

run_id = get_run_id()
subprocess.run(
    ["python", "worker.py", "--run-id", run_id],
    check=True,
)
```

In `worker.py`, read the ID from args and pass it as `client.create_step(run_id=run_id, ...)`.

## Context isolation between runs

Each `@workflow` call is isolated. Parallel workflows in the same process (e.g. a web server handling multiple requests simultaneously) get separate contexts:

```python
# Flask / FastAPI — each request runs in its own context
@app.post("/ask")
async def ask(request: Request):
    result = rag_pipeline(request.query)   # isolated run_id per request
    return result
```

## Debugging context issues

If `get_run_id()` returns `None` where you expect a value:

1. Ensure the function is called inside (not before) the `@workflow` call
2. Check that you haven't spawned a new `multiprocessing.Process` — those lose context
3. Confirm the `@workflow` decorator is applied (not just defined)

```python
# Wrong — decorator defined but not applied
def pipeline(query):
    ...
pipeline = workflow(name="p")(pipeline)   # ← this is fine actually

# Also fine
@workflow(name="p")
def pipeline(query):
    ...
```
