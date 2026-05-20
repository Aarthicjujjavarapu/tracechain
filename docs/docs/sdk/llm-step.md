---
id: llm-step
title: "@llm_step"
sidebar_position: 4
---

# `@llm_step`

The `@llm_step` decorator wraps a function that makes a single LLM API call. It records the prompt, response, token counts, estimated cost, and latency — and accumulates cost/tokens toward the run total.

## Signature

```python
def llm_step(
    name: str,
    model: str,
    prompt_version: str | None = None,
    metadata: dict | None = None,
    client: TraceChainClient | None = None,
) -> Callable:
    ...
```

### Parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | `str` | Yes | Display name for the LLM step |
| `model` | `str` | Yes | Model identifier (e.g. `"gpt-4o-mini"`, `"claude-3-haiku"`) |
| `prompt_version` | `str` | No | Tag linking this call to a stored `PromptVersion` |
| `metadata` | `dict` | No | Extra JSON stored with the LLM call record |
| `client` | `TraceChainClient` | No | Override default client |

## Basic usage

```python
from tracechain import llm_step
from openai import OpenAI

openai_client = OpenAI()

@llm_step(name="generate_answer", model="gpt-4o-mini", prompt_version="v1")
def generate_answer(query: str, context: list[str]) -> str:
    joined = "\n".join(context)
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Answer using only the context."},
            {"role": "user",   "content": f"Context:\n{joined}\n\nQ: {query}"},
        ],
    )
    return resp.choices[0].message.content
```

## What it records

| Field | Description |
|---|---|
| `provider` | Always `"openai"` in current version |
| `model` | From the decorator parameter |
| `prompt` | The first user-role message content |
| `response` | The model's reply text |
| `input_tokens` | From `usage.prompt_tokens` |
| `output_tokens` | From `usage.completion_tokens` |
| `total_tokens` | `input + output` |
| `estimated_cost` | Calculated from known per-token pricing |
| `latency_ms` | Time from call start to response |
| `status` | `"success"` or `"failed"` |
| `prompt_version` | From the decorator parameter |

## Token and cost accumulation

Every `@llm_step` invocation adds its tokens and cost to the **run-level accumulators**. When the `@workflow` completes, it writes the totals to the run record:

```
run.total_tokens = sum of all @llm_step tokens in this run
run.total_cost   = sum of all @llm_step estimated costs
```

This means the runs list and dashboard cost charts reflect real per-run spend.

## Supported models and pricing

TraceChain uses a built-in pricing table:

| Model | Input ($/1K tokens) | Output ($/1K tokens) |
|---|---|---|
| `gpt-4o` | $0.005 | $0.015 |
| `gpt-4o-mini` | $0.00015 | $0.0006 |
| `gpt-4-turbo` | $0.01 | $0.03 |
| `gpt-3.5-turbo` | $0.0005 | $0.0015 |
| Others | `0` (tracked, not priced) | — |

Cost is an **estimate** — actual billing may differ based on batching, caching, or API plan.

## Prompt version linking

When you pass `prompt_version`, the LLM call is linked to that version tag. You can then see per-version metrics in the Prompts section of the dashboard:

```python
@llm_step(name="generate", model="gpt-4o-mini", prompt_version="rag-v3")
def generate(query, docs):
    ...
```

Create the prompt version in the backend first:

```bash
curl -X POST http://localhost:8000/prompts \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_name": "rag",
    "version": "v3",
    "prompt_text": "Answer using only the context provided below..."
  }'
```

## Error handling

If the LLM call raises (network error, rate limit, etc.), `@llm_step`:

1. Records an LLM call with `status="failed"` and the error message
2. Records a step with `status="failed"`
3. Re-raises the exception

The parent `@workflow` then catches it and marks the run as `failed`.

## Provider support

Currently `@llm_step` is designed for the **OpenAI SDK** response shape. Other providers are supported if their response includes:

- `usage.prompt_tokens`
- `usage.completion_tokens`
- `choices[0].message.content`

Future versions will add native support for Anthropic, Cohere, and Google.

## Related

- [`@step`](step) — for non-LLM steps
- [`@workflow`](workflow) — the run entry point
- [Prompt versioning](../advanced/prompt-versioning) — storing and comparing prompts
