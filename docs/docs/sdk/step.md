---
id: step
title: "@step"
sidebar_position: 3
---

# `@step`

The `@step` decorator instruments a discrete unit of work inside a workflow. It records timing, input, output, errors, and optionally retries on failure.

## Signature

```python
def step(
    name: str,
    retries: int = 0,
    metadata: dict | None = None,
    client: TraceChainClient | None = None,
) -> Callable:
    ...
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | — | Display name for the step |
| `retries` | `int` | `0` | Number of additional attempts on exception |
| `metadata` | `dict` | `None` | Extra JSON attached to the step record |
| `client` | `TraceChainClient` | `None` | Override default client |

## Basic usage

```python
from tracechain import step

@step(name="retrieve_docs")
def retrieve_docs(query: str) -> list[str]:
    # your retrieval logic
    return vector_store.search(query, top_k=5)
```

Must be called inside a `@workflow`:

```python
@workflow(name="rag")
def rag(query: str):
    docs = retrieve_docs(query)   # ← step is automatically linked to the run
    ...
```

## What it records

For each invocation, TraceChain records:

| Field | Value |
|---|---|
| `step_name` | The `name` parameter |
| `step_type` | `"step"` |
| `status` | `success` or `failed` |
| `input_payload` | Function arguments as JSON |
| `output_payload` | Return value as JSON |
| `error_message` | Exception message on failure |
| `started_at` | Wall-clock timestamp |
| `duration_ms` | End-to-end time including retries |
| `retry_count` | How many retries were used |

## Retries

Set `retries` to automatically retry a failing step:

```python
@step(name="call_external_api", retries=3)
def call_external_api(url: str) -> dict:
    return requests.get(url, timeout=10).json()
```

TraceChain will attempt the function **1 + retries** times total. On each retry, `retry_count` is incremented in the step record. If all attempts fail, the original exception is re-raised.

:::note
Retries are immediate with no backoff. For exponential backoff, use `tenacity` inside your function and leave `retries=0`.
:::

## Step type vs LLM step

Use `@step` for non-LLM work:

```python
@step(name="retrieve")   # ← vector store, database, API calls
def retrieve(query): ...

@llm_step(name="generate", model="gpt-4o-mini")   # ← LLM calls
def generate(query, docs): ...
```

Both record the same fields; `@llm_step` additionally captures tokens, cost, and the raw prompt/response.

## Nested steps

Steps can be nested — each creates its own record with the same `run_id`:

```python
@workflow(name="pipeline")
def pipeline(query):
    results = retrieve(query)
    ranked  = rerank(results, query)   # another @step
    return generate(query, ranked)
```

Step records are not hierarchically linked to each other, only to the run.

## Standalone steps (outside a workflow)

If you call a `@step`-decorated function outside of a `@workflow`, the step is recorded with no `run_id`. This is valid but unusual — the step will appear unlinked in the database.

## Related

- [`@workflow`](workflow) — create the run context
- [`@llm_step`](llm-step) — step variant for LLM calls
