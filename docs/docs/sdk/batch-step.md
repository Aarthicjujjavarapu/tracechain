---
id: batch-step
title: "@batch_step"
sidebar_position: 8
---

# `@batch_step`

`@batch_step` instruments a single-item function so it processes a **list of items** as a traced batch. It creates one parent step for the batch and, optionally, per-item child steps.

## Signature

```python
def batch_step(
    name: str,
    concurrency: int = 1,
    raise_on_error: bool = False,
    trace_items: bool = False,
    metadata: dict | None = None,
    client: TraceChainClient | None = None,
) -> Callable[[list], BatchResult]:
    ...
```

### Parameters

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | — | Batch step name shown in the dashboard |
| `concurrency` | `int` | `1` | Max parallel workers. Async: asyncio semaphore. Sync: ThreadPoolExecutor |
| `raise_on_error` | `bool` | `False` | Re-raise the first item error. When `False`, failures are collected in `BatchResult.errors` |
| `trace_items` | `bool` | `False` | Create a backend step per item. Useful for small batches; keep off for >50 items |
| `metadata` | `dict` | `None` | Extra JSON stored on the batch step record |
| `client` | `TraceChainClient` | `None` | Override default client |

## Basic usage

```python
from tracechain import workflow, batch_step

@batch_step(name="embed_docs")
def embed_doc(doc: str) -> list[float]:
    return model.embed(doc)

@workflow(name="index_pipeline")
def index_pipeline(docs: list[str]):
    result = embed_doc(docs)        # called with a list
    print(result.success_count)     # → 3
    return result.success_results   # → [[0.1, ...], [0.2, ...], ...]
```

The decorated function must accept **one positional argument** (the item). Call the wrapper with a **list**; it returns a [`BatchResult`](#batchresult).

## Async + concurrency

```python
@batch_step(name="embed_docs", concurrency=10)
async def embed_doc(doc: str) -> list[float]:
    return await async_model.embed(doc)

result = await embed_doc(documents)
```

For async functions, `concurrency` maps to an `asyncio.Semaphore`. For sync functions it maps to a `ThreadPoolExecutor`.

## Partial failures

By default (`raise_on_error=False`) errors are collected per item — the batch continues even when individual items fail:

```python
@batch_step(name="risky", raise_on_error=False)
def process(item: str) -> str:
    if item == "bad":
        raise ValueError("bad item")
    return item.upper()

result = process(["ok", "bad", "fine"])
print(result.results)        # → ["OK", None, "FINE"]
print(result.failed_count)   # → 1
print(result.errors[1])      # → ValueError("bad item")
print(result.success_results)# → ["OK", "FINE"]
```

To stop on first failure instead:

```python
@batch_step(name="strict", raise_on_error=True)
def process(item): ...
```

## Per-item tracing

```python
@batch_step(name="embed", trace_items=True)
def embed(doc: str) -> list[float]:
    ...

embed(["doc1", "doc2", "doc3"])
# Creates: 1 batch_step + 3 batch_item steps in the dashboard
```

Keep `trace_items=False` (default) for large batches to avoid dashboard noise.

## `BatchResult`

| Attribute | Type | Description |
|---|---|---|
| `.results` | `list[T \| None]` | Per-item return values; `None` for failed items |
| `.errors` | `list[Exception \| None]` | Per-item exceptions; `None` for succeeded items |
| `.success_count` | `int` | Number of items that succeeded |
| `.failed_count` | `int` | Number of items that raised |
| `.success_results` | `list[T]` | Only the results that didn't fail |

`BatchResult` is iterable and indexable:

```python
for embedding in result:       # iterates over .results
    ...

result[0]                      # first item result
```

## What is recorded

| Field | Value |
|---|---|
| `step_name` | The `name` parameter |
| `step_type` | `"batch_step"` |
| `input_payload` | `{ batch_size, concurrency }` |
| `output_payload` | `{ batch_size, success_count, failed_count }` |
| `duration_ms` | Total wall-clock time for the batch |

Each per-item step (`trace_items=True`) records `index` and `item` in `input_payload`.

## JavaScript / TypeScript

```typescript
import { batchStep } from "@tracechain/sdk";

const embedDocs = batchStep(
  "embed_docs",
  async (doc: string) => model.embed(doc),
  { concurrency: 5 },
);

const result = await embedDocs(documents);
console.log(result.successCount, result.failedCount);
```

## Related

- [`@step`](step) — single-item step
- [`@workflow`](workflow) — creates the run context
- [`@llm_step`](llm-step) — step variant for LLM calls
