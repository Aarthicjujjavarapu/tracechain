---
id: quickstart
title: Quickstart
sidebar_position: 2
---

# 5-minute Quickstart

This guide takes you from zero to a fully traced LLM workflow. By the end you will see your first run in the dashboard.

## Step 1 — Start the backend

```bash
docker compose up -d
```

Wait for the health check to pass:

```bash
curl http://localhost:8000/health
# {"status":"ok","db":"connected"}
```

## Step 2 — Configure the SDK

Create a `.env` file in your project root (or export variables):

```bash
TRACECHAIN_BACKEND_URL=http://localhost:8000
OPENAI_API_KEY=sk-...          # only needed if you use @llm_step
```

## Step 3 — Instrument your first workflow

```python
from tracechain import workflow, step, llm_step, evaluate_run

# ── Steps ────────────────────────────────────────────────────────────────────

@step(name="retrieve_docs")
def retrieve_docs(query: str) -> list[str]:
    """Simulate a vector-store retrieval."""
    return [
        f"Doc about '{query}': TraceChain is an observability framework.",
        f"Doc about '{query}': It tracks every LLM call automatically.",
    ]


@llm_step(name="generate_answer", model="gpt-4o-mini", prompt_version="v1")
def generate_answer(query: str, docs: list[str]) -> str:
    """Call the LLM and return its answer."""
    from openai import OpenAI
    client = OpenAI()
    joined = "\n".join(docs)
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "Answer the question using only the provided context."},
            {"role": "user",   "content": f"Context:\n{joined}\n\nQuestion: {query}"},
        ],
    )
    return resp.choices[0].message.content


# ── Workflow ─────────────────────────────────────────────────────────────────

@workflow(name="rag_pipeline")
def rag_pipeline(query: str) -> str:
    docs   = retrieve_docs(query)
    answer = generate_answer(query, docs)
    evaluate_run(answer, query, docs)
    return answer


# ── Run it ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    result = rag_pipeline("What is TraceChain?")
    print(result)
```

## Step 4 — Run the script

```bash
python my_pipeline.py
```

You will see structured logs from TraceChain:

```
INFO  tracechain.workflow  Run created: 3f2a8b1c-...
INFO  tracechain.step      Step retrieve_docs started
INFO  tracechain.step      Step retrieve_docs completed (42 ms)
INFO  tracechain.llm       LLM call gpt-4o-mini: 312 tokens, $0.0002
INFO  tracechain.workflow  Run completed (1.4 s)
```

## Step 5 — Open the dashboard

Navigate to [http://localhost:3000](http://localhost:3000).

You will see your `rag_pipeline` run with:

- Full trace timeline (retrieve → generate)
- Token and cost breakdown
- Evaluation scores (relevance, groundedness, hallucination risk, quality)

## What just happened

| Decorator | What TraceChain did |
|---|---|
| `@workflow` | Created a run record, set context, recorded input + output |
| `@step` | Recorded step timing, input, output |
| `@llm_step` | Intercepted the LLM call, recorded tokens + cost |
| `evaluate_run` | Computed quality scores and persisted them |

## Next steps

- [Configuration reference →](configuration)
- [Full `@workflow` API →](../sdk/workflow)
- [Full `@llm_step` API →](../sdk/llm-step)
- [Replay a run →](../sdk/replay)

## Runnable examples

All examples work without an OpenAI API key — a built-in mock LLM generates realistic responses.

| File | What it shows |
|------|--------------|
| `examples/01_rag_pipeline.py` | `@step`, `@llm_step`, `evaluate_run` |
| `examples/02_support_agent.py` | Multi-step agent, retries, multiple runs |
| `examples/03_streaming_llm.py` | `observe_llm()` with streaming TTFT + tool calling |
| `examples/04_opentelemetry.py` | `configure_otel()` → Jaeger / console export |

```bash
pip install -e sdk/
python examples/01_rag_pipeline.py
```
