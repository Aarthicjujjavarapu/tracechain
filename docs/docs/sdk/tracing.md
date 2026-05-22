---
id: tracing
title: Tracing Context
sidebar_position: 7
---

# Tracing Context

TraceChain propagates `run_id` and `step_id` through Python's `contextvars` module. You rarely need to interact with these directly, but they are useful for custom logging, manual backend calls, or advanced integrations.

## API

```python
from tracechain import get_run_id, get_step_id
```

### `get_run_id() -> str | None`

Returns the run ID of the currently active `@workflow`, or `None` if called outside one.

```python
from tracechain import workflow, get_run_id

@workflow(name="pipeline")
def pipeline(query):
    print(get_run_id())   # prints "3f2a8b1c-..."
    return process(query)

print(get_run_id())   # prints None — outside workflow
```

### `get_step_id() -> str | None`

Returns the step ID of the currently executing `@step` or `@llm_step`, or `None` if outside a step.

```python
@step(name="retrieve")
def retrieve(query):
    print(get_step_id())   # prints the step UUID
    ...
```

## Use cases

### Custom structured logging

Attach TraceChain IDs to your log records for correlation:

```python
import logging
from tracechain import workflow, step, get_run_id, get_step_id

logger = logging.getLogger(__name__)

@step(name="process")
def process(data):
    logger.info(
        "Processing data",
        extra={"run_id": get_run_id(), "step_id": get_step_id()},
    )
    ...
```

### Custom backend calls

Make raw HTTP calls to the TraceChain backend using the current run context:

```python
import httpx
from tracechain import get_run_id

def record_custom_event(event_type: str, payload: dict):
    run_id = get_run_id()
    if not run_id:
        return
    httpx.post(
        f"http://localhost:8000/runs/{run_id}/feedback",
        json={"rating": 5, "comment": f"Custom: {event_type}"},
        timeout=3,
    )
```

### Passing IDs to sub-processes

Context variables do **not** cross process boundaries. If you spawn subprocesses or use async frameworks, pass the IDs explicitly:

```python
run_id = get_run_id()
step_id = get_step_id()

# pass to subprocess via env or args
subprocess.run(["worker.py", "--run-id", run_id, "--step-id", step_id])
```

## Thread safety

`contextvars` are thread-safe. Each thread that is spawned from within a `@workflow` inherits a **copy** of the context at spawn time. Writes inside the thread do not affect the parent context.

```python
@workflow(name="parallel_pipeline")
def pipeline(queries):
    from concurrent.futures import ThreadPoolExecutor

    with ThreadPoolExecutor() as exe:
        # each thread inherits run_id from this workflow
        results = list(exe.map(process_query, queries))
    return results
```

## How context resets

`@workflow` uses `ContextVar.set()` and saves the reset token. When the workflow exits (success or error), the token is used to reset the variable to its previous value. This ensures that nested or concurrent workflows do not bleed context into each other.

## Related

- [`@workflow`](workflow) — sets the run context
- [`@step`](step) — sets the step context
- [Advanced: context propagation](../advanced/context-propagation)
