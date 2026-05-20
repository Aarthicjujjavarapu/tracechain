---
id: workflow
title: "@workflow"
sidebar_position: 2
---

# `@workflow`

The `@workflow` decorator is the entry point for TraceChain instrumentation. It wraps your pipeline function and manages the full lifecycle of a **workflow run** record.

## Signature

```python
def workflow(
    name: str,
    metadata: dict | None = None,
    client: TraceChainClient | None = None,
) -> Callable:
    ...
```

### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | `str` | Yes | Display name for this workflow in the dashboard |
| `metadata` | `dict` | No | Arbitrary JSON attached to the run record |
| `client` | `TraceChainClient` | No | Override the default client (useful for tests) |

## Basic usage

```python
from tracechain import workflow

@workflow(name="rag_pipeline")
def rag_pipeline(query: str) -> str:
    docs   = retrieve(query)
    answer = generate(query, docs)
    return answer
```

Call it like a normal function — the decorator is transparent:

```python
answer = rag_pipeline("What is the capital of France?")
```

## What it does

When the decorated function is called, `@workflow`:

1. **Creates a run record** via `POST /runs` with:
   - `workflow_name` — the `name` parameter
   - `input_payload` — your function's arguments as JSON
   - `metadata` — any extra data you pass
2. **Sets `run_id`** in the current Python context so all nested `@step` and `@llm_step` calls can find it automatically
3. **Resets cost + token accumulators** for the new run
4. **Calls your function**
5. On success: **completes the run** via `POST /runs/{id}/complete` with output, total cost, total tokens
6. On exception: **fails the run** via `POST /runs/{id}/fail` with the error message, then re-raises

## Run lifecycle states

```
pending  →  running  →  success
                    ↘  failed
```

The `pending → running` transition happens during run creation. `running → success/failed` happens when your function returns or raises.

## Attaching metadata

Use `metadata` for any run-level context you want to query in the dashboard:

```python
@workflow(name="rag_pipeline", metadata={"version": "2.1", "env": "prod"})
def rag_pipeline(query: str) -> str:
    ...
```

Metadata is stored as JSONB and is searchable.

## Replay runs

When re-running a previous workflow, pass replay metadata:

```python
from tracechain import workflow, create_replay_metadata

@workflow(
    name="rag_pipeline",
    metadata=create_replay_metadata(original_run_id="3f2a8b1c-..."),
)
def rag_pipeline(query: str) -> str:
    ...
```

This links the new run to the original in the database and sets `is_replay=true`.

## Using a custom client

```python
from tracechain import TraceChainConfig, TraceChainClient, workflow

config = TraceChainConfig(base_url="http://staging-backend:8000")
client = TraceChainClient(config)

@workflow(name="pipeline", client=client)
def pipeline(query: str) -> str:
    ...
```

## Input payload serialisation

Arguments are captured by inspecting the function signature and binding positional and keyword arguments. Non-JSON-serialisable values (e.g. custom objects) are converted to their `str()` representation.

```python
@workflow(name="pipeline")
def pipeline(query: str, top_k: int = 5, filters: dict | None = None):
    ...

pipeline("hello", top_k=3)
# input_payload: {"query": "hello", "top_k": 3, "filters": null}
```

## Failure behaviour

If the backend is unreachable, `@workflow` **still calls your function**. The run won't appear in the dashboard, but your application continues normally:

```
WARNING tracechain.client  Backend call failed: POST /runs — ConnectError
```

## Related

- [`@step`](step) — annotate a step inside a workflow
- [`@llm_step`](llm-step) — annotate an LLM call inside a workflow
- [Replay](replay) — trigger a replay programmatically
