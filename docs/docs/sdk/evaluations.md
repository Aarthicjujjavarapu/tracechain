---
id: evaluations
title: Evaluations
sidebar_position: 5
---

# Evaluations

TraceChain can automatically score the quality of each run. Scores are stored in the database and displayed on the run detail page.

## `evaluate_run`

```python
from tracechain import evaluate_run

evaluate_run(
    answer: str,
    query: str,
    context: list[str],
    client: TraceChainClient | None = None,
) -> None
```

Call this inside a `@workflow` after your pipeline produces an answer:

```python
@workflow(name="rag_pipeline")
def rag_pipeline(query: str) -> str:
    docs   = retrieve_docs(query)
    answer = generate_answer(query, docs)
    evaluate_run(answer, query, docs)   # ← attach scores
    return answer
```

### Scores computed

| Score | Range | Description |
|---|---|---|
| `relevance_score` | 0 – 1 | Does the answer address the query? |
| `groundedness_score` | 0 – 1 | Is the answer supported by the context docs? |
| `hallucination_risk` | 0 – 1 | How likely is the answer to contain fabricated information? |
| `quality_score` | 0 – 1 | Overall composite quality |

Higher is better for all scores except `hallucination_risk`, where lower is better.

### Scoring algorithm

Scores are computed heuristically without calling an LLM:

- **Relevance** — keyword overlap between query terms and the answer
- **Groundedness** — sentence overlap between context and the answer
- **Hallucination risk** — `1 - groundedness` (a fast proxy)
- **Quality** — weighted average: `(relevance × 0.3) + (groundedness × 0.5) + ((1 - hallucination) × 0.2)`

:::note
These are lightweight heuristic scores, not LLM-judge scores. They are intentionally fast and free. For high-fidelity evaluation, integrate an LLM judge and call `eval_score` directly with pre-computed values.
:::

## `eval_score` (advanced)

`eval_score` is an alias that lets you pass pre-computed scores directly:

```python
from tracechain import eval_score

# BYO LLM-judge scores
scores = my_llm_judge(answer, query, context)

eval_score(
    answer=answer,
    query=query,
    context=context,
    relevance_score=scores["relevance"],
    groundedness_score=scores["groundedness"],
    hallucination_risk=scores["hallucination"],
    quality_score=scores["quality"],
)
```

## Accessing evaluation results

Via the REST API:

```bash
curl http://localhost:8000/runs/{run_id}/evaluations
```

Response:

```json
[
  {
    "id": "a1b2c3d4-...",
    "run_id": "3f2a8b1c-...",
    "relevance_score": 0.87,
    "groundedness_score": 0.74,
    "hallucination_risk": 0.26,
    "quality_score": 0.79,
    "failure_reason": null,
    "created_at": "2026-05-19T10:23:45Z"
  }
]
```

## Dashboard

In the run detail view, evaluation scores appear as a score bar under the **Evaluation** section. The runs list shows `quality_score` as a column for quick comparison.

## Related

- [`@workflow`](workflow) — the context in which evaluations run
- [API reference — evaluations](../backend/api-reference#evaluations)
