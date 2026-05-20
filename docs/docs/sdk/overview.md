---
id: overview
title: SDK Overview
sidebar_position: 1
---

# Python SDK Overview

The TraceChain SDK is a zero-friction instrumentation library for Python. It uses **decorators** and **context variables** so you add observability by annotating functions — not by threading IDs through every call.

## Installation

```bash
pip install -e sdk/            # local dev (editable)
pip install tracechain         # PyPI release (coming soon)
```

## Public API

```python
from tracechain import (
    TraceChainConfig,      # configuration dataclass
    TraceChainClient,      # HTTP client (advanced)
    workflow,              # decorator: marks a workflow entry point
    step,                  # decorator: marks a discrete step
    llm_step,             # decorator: marks a step that calls an LLM
    evaluate_run,          # function: attach quality scores to current run
    eval_score,            # alias for evaluate_run
    create_replay_metadata,# helper: build metadata for a replay run
    trigger_replay,        # function: POST /runs/{id}/replay
    get_run_id,            # function: read current run ID from context
    get_step_id,           # function: read current step ID from context
)
```

## Decorator hierarchy

Decorators must follow this nesting order:

```
@workflow          ← outermost; creates the run
  @step            ← one per logical unit of work
    @llm_step      ← innermost; wraps a single LLM API call
```

You can nest as many steps and llm_steps as you like under a workflow.

## Context propagation

The SDK propagates `run_id` and `step_id` using Python's [`contextvars`](https://docs.python.org/3/library/contextvars.html). This means nested functions automatically receive the right IDs **without any plumbing code**:

```python
@workflow(name="pipeline")
def pipeline(query):
    # run_id is set here automatically
    result = retrieve(query)   # step knows the run_id
    return generate(result)    # llm_step knows run_id + step_id

@step(name="retrieve")
def retrieve(query):
    print(get_run_id())   # works — propagated from @workflow
    return [...]

@llm_step(name="generate", model="gpt-4o-mini")
def generate(docs):
    ...
```

Context variables work correctly across threads because each thread gets its own copy.

## Error handling

All SDK decorators catch exceptions, mark the run/step as `failed` in the backend, then **re-raise the original exception**. Your error handling code runs normally:

```python
try:
    result = my_pipeline("query")
except ValueError as e:
    # run is already marked failed in the backend
    handle_error(e)
```

## Non-blocking design

Every backend call is fire-and-forget with a configurable timeout (default 5 seconds). A slow or unreachable backend **never blocks** your workflow.

## Sections

- [`@workflow`](workflow) — run lifecycle management
- [`@step`](step) — step instrumentation with retries
- [`@llm_step`](llm-step) — LLM call tracing with token + cost
- [Evaluations](evaluations) — quality scoring
- [Replay](replay) — re-run past executions
- [Tracing context](tracing) — reading IDs from context
