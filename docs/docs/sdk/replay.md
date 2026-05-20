---
id: replay
title: Replay
sidebar_position: 6
---

# Replay

Replay lets you re-execute a previous workflow run with the same input. The new run is linked to the original so you can compare outputs, costs, and quality scores side by side.

## When to use replay

- Debugging a failed run after a fix
- Comparing prompt versions on the same input
- A/B testing model changes
- Manual QA on production traces

## `trigger_replay`

```python
from tracechain import trigger_replay

new_run_id = trigger_replay(run_id="3f2a8b1c-...")
```

This calls `POST /runs/{run_id}/replay` on the backend, which creates a new run record with `is_replay=true` and `original_run_id` set to the source run.

The function returns the new `run_id` string, or `None` if the backend call failed.

:::note
`trigger_replay` creates the **run record** but does not re-execute your Python function. Re-executing is your responsibility — use the `original_run_id` to look up the input and call your function again.
:::

## Full replay pattern

```python
from tracechain import workflow, create_replay_metadata, trigger_replay
import httpx

def replay_run(original_run_id: str):
    # 1. Fetch the original run's input
    resp = httpx.get(f"http://localhost:8000/runs/{original_run_id}")
    original = resp.json()
    input_payload = original["input_payload"]

    # 2. Create a new run record linked to the original
    new_run_id = trigger_replay(original_run_id)

    # 3. Re-run with replay metadata so the SDK links them
    @workflow(
        name=original["workflow_name"],
        metadata=create_replay_metadata(original_run_id),
    )
    def _replay(**kwargs):
        return rag_pipeline(**kwargs)   # your actual pipeline

    _replay(**input_payload)
    return new_run_id
```

## `create_replay_metadata`

```python
from tracechain import create_replay_metadata

meta = create_replay_metadata(original_run_id="3f2a8b1c-...")
# → {"original_run_id": "3f2a8b1c-...", "is_replay": True}
```

Pass this to the `metadata` parameter of `@workflow` so the SDK stamps the run record correctly.

## Dashboard replay

You can also trigger a replay from the run detail page in the dashboard. Click **Replay** in the top-right corner of any run detail view.

The dashboard will:
1. Call `POST /runs/{id}/replay`
2. Show the new run ID
3. Navigate to the new run once it completes

## Replay chains

Replays can themselves be replayed. The `original_run_id` always points to the **direct parent**, not the root. Use the API to walk the chain:

```bash
# Find all replays of a given run
curl "http://localhost:8000/runs?is_replay=true&workflow_name=rag_pipeline"
```

## Related

- [`@workflow`](workflow) — wrap your pipeline function
- [API reference — replay](../backend/api-reference#replay)
