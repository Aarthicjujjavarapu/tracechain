---
id: prompt-versioning
title: Prompt Versioning
sidebar_position: 3
---

# Prompt Versioning

TraceChain includes a **prompt registry** — a versioned store of prompt templates. Link each `@llm_step` to a stored version and see per-version quality metrics in the dashboard.

## Why version prompts?

- Track which prompt was active during a production incident
- Compare quality scores across prompt changes (A/B)
- Roll back to a previous prompt without redeploying code
- See how cost and token usage change as prompts evolve

## Creating a prompt version

Via the API:

```bash
curl -X POST http://localhost:8000/prompts \
  -H "Content-Type: application/json" \
  -d '{
    "prompt_name": "rag-system",
    "version": "v3",
    "prompt_text": "You are a helpful assistant. Answer the question using ONLY the context provided. If the context does not contain the answer, say \"I don'\''t know\".",
    "is_active": true,
    "metadata": {
      "author": "alice",
      "pr": "42",
      "notes": "Added I-don'\''t-know instruction"
    }
  }'
```

Via Python:

```python
import httpx

httpx.post("http://localhost:8000/prompts", json={
    "prompt_name": "rag-system",
    "version": "v3",
    "prompt_text": "You are a helpful assistant...",
    "is_active": True,
})
```

## Linking a step to a version

Pass `prompt_version` to `@llm_step`:

```python
@llm_step(name="generate", model="gpt-4o-mini", prompt_version="v3")
def generate(query: str, docs: list[str]) -> str:
    from openai import OpenAI
    client = OpenAI()

    # Load the active prompt from the registry at runtime
    prompt_text = get_active_prompt("rag-system")

    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt_text},
            {"role": "user",   "content": f"Context: {docs}\n\nQ: {query}"},
        ],
    )
    return resp.choices[0].message.content
```

The `prompt_version` tag is stored with the LLM call record. It does not have to match the `version` field in `prompt_versions` exactly — it is a free-form string.

## Loading the active prompt at runtime

```python
import httpx
import functools

@functools.lru_cache(maxsize=None)
def get_active_prompt(prompt_name: str) -> str:
    """Fetch all versions and return the active one's text."""
    resp = httpx.get("http://localhost:8000/prompts")
    resp.raise_for_status()
    for p in resp.json():
        if p["prompt_name"] == prompt_name and p["is_active"]:
            return p["prompt_text"]
    raise ValueError(f"No active prompt found for '{prompt_name}'")
```

:::tip
Cache the prompt text with `lru_cache` for the process lifetime, or reload it on each deployment. Avoid a database round-trip on every LLM call in production.
:::

## Per-version metrics

The API exposes aggregated metrics per prompt version:

```bash
curl http://localhost:8000/prompts/{prompt_id}/metrics
```

Response:

```json
{
  "prompt_id": "...",
  "total_runs": 87,
  "avg_quality_score": 0.82,
  "avg_cost": 0.0031,
  "total_tokens": 152400
}
```

In the dashboard, the **Prompts** page shows these metrics as a table, making it easy to compare versions.

## Version naming conventions

There is no enforced convention. Common patterns:

| Pattern | Example |
|---|---|
| Semantic | `v1`, `v2`, `v3` |
| Date-based | `2026-05-19` |
| Git SHA | `a3f8b21` |
| Descriptive | `rag-with-citations` |

## Activating a version

Only one version per `prompt_name` should have `is_active=true`. To switch:

```bash
# Deactivate old
curl -X PATCH http://localhost:8000/prompts/{old_id} \
  -d '{"is_active": false}'

# Activate new
curl -X PATCH http://localhost:8000/prompts/{new_id} \
  -d '{"is_active": true}'
```

## Related

- [`@llm_step`](../sdk/llm-step) — the `prompt_version` parameter
- [API reference — prompts](../backend/api-reference#prompts)
- [Dashboard — Prompts page](../dashboard/overview#prompts---prompts)
