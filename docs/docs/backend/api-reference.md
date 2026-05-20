---
id: api-reference
title: API Reference
sidebar_position: 2
---

# API Reference

All endpoints return JSON. Error responses follow the FastAPI default shape: `{"detail": "message"}`.

Base URL: `http://localhost:8000`

---

## Health

### `GET /health`

Check backend and database connectivity.

**Response 200**

```json
{"status": "ok", "db": "connected"}
```

---

## Runs

### `POST /runs`

Create a new workflow run.

**Request body**

```json
{
  "workflow_name": "rag_pipeline",
  "input_payload": {"query": "What is TraceChain?"},
  "metadata": {"env": "prod"}
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `workflow_name` | string | Yes | Name of the workflow |
| `input_payload` | object | No | Arbitrary JSON input |
| `metadata` | object | No | Arbitrary JSON metadata |

**Response 201** — `RunOut`

```json
{
  "id": "3f2a8b1c-...",
  "workflow_name": "rag_pipeline",
  "status": "running",
  "input_payload": {"query": "What is TraceChain?"},
  "output_payload": null,
  "error_message": null,
  "started_at": "2026-05-19T10:00:00Z",
  "ended_at": null,
  "duration_ms": null,
  "total_cost": null,
  "total_tokens": null,
  "is_replay": false,
  "original_run_id": null,
  "metadata": {"env": "prod"}
}
```

---

### `GET /runs`

List workflow runs with optional filters.

**Query parameters**

| Parameter | Type | Description |
|---|---|---|
| `status` | string | Filter by `pending`, `running`, `success`, `failed` |
| `workflow_name` | string | Filter by workflow name |
| `is_replay` | boolean | Filter replays (`true`) or originals (`false`) |
| `offset` | int (≥0) | Pagination offset (default: `0`) |
| `limit` | int (1–200) | Page size (default: `50`) |

**Response 200**

```json
{
  "items": [ ...RunOut... ],
  "total": 142
}
```

---

### `GET /runs/{run_id}`

Get a single run by ID.

**Response 200** — `RunOut`

**Response 404** — run not found

---

### `POST /runs/{run_id}/complete`

Mark a run as successful.

**Request body**

```json
{
  "output_payload": {"answer": "TraceChain is..."},
  "total_cost": 0.0024,
  "total_tokens": 512
}
```

**Response 200** — `RunOut` with `status: "success"`

---

### `POST /runs/{run_id}/fail`

Mark a run as failed.

**Request body**

```json
{
  "error_message": "Connection refused"
}
```

**Response 200** — `RunOut` with `status: "failed"`

---

### `POST /runs/{run_id}/replay` {#replay}

Create a new run linked to `run_id` as a replay.

**Response 201** — new `RunOut` with `is_replay: true`

---

## Steps

### `POST /runs/{run_id}/steps`

Record a step execution.

**Request body**

```json
{
  "step_name": "retrieve_docs",
  "step_type": "step",
  "status": "success",
  "input_payload": {"query": "What is TraceChain?"},
  "output_payload": ["doc1", "doc2"],
  "duration_ms": 42,
  "retry_count": 0
}
```

**Response 201** — `StepOut`

---

### `GET /runs/{run_id}/steps`

List all steps for a run (ordered by `started_at`).

**Response 200** — `list[StepOut]`

---

## LLM Calls

### `POST /runs/{run_id}/llm-calls`

Record an LLM API call.

**Request body**

```json
{
  "step_id": "abc123-...",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "prompt": "Answer using only the context...",
  "response": "TraceChain is a reliability-first...",
  "input_tokens": 248,
  "output_tokens": 64,
  "total_tokens": 312,
  "estimated_cost": 0.000215,
  "latency_ms": 1240,
  "temperature": 0.7,
  "status": "success",
  "prompt_version": "v1"
}
```

**Response 201** — `LLMCallOut`

---

### `GET /runs/{run_id}/llm-calls`

List all LLM calls for a run.

**Response 200** — `list[LLMCallOut]`

---

## Evaluations {#evaluations}

### `POST /runs/{run_id}/evaluations`

Attach quality scores to a run.

**Request body**

```json
{
  "relevance_score": 0.87,
  "groundedness_score": 0.74,
  "hallucination_risk": 0.26,
  "quality_score": 0.79,
  "failure_reason": null
}
```

All score fields are `float` in `[0, 1]`.

**Response 201** — `EvalOut`

---

### `GET /runs/{run_id}/evaluations`

List evaluations for a run.

**Response 200** — `list[EvalOut]`

---

## Feedback

### `POST /runs/{run_id}/feedback`

Attach human feedback to a run.

**Request body**

```json
{
  "rating": 4,
  "comment": "Good answer but slightly verbose."
}
```

| Field | Type | Constraints |
|---|---|---|
| `rating` | int | 1 – 5 |
| `comment` | string | Optional |

**Response 201** — `FeedbackOut`

---

### `GET /runs/{run_id}/feedback`

List all feedback for a run.

**Response 200** — `list[FeedbackOut]`

---

## Prompts

### `POST /prompts`

Create a new prompt version.

**Request body**

```json
{
  "prompt_name": "rag-system",
  "version": "v3",
  "prompt_text": "Answer the question using only the context provided...",
  "is_active": true,
  "metadata": {"author": "alice"}
}
```

**Response 201** — `PromptOut`

---

### `GET /prompts`

List all prompt versions.

**Response 200** — `list[PromptOut]`

---

### `GET /prompts/{prompt_id}`

Get a prompt version by ID.

**Response 200** — `PromptOut`

---

### `GET /prompts/{prompt_id}/metrics`

Get aggregated metrics for a prompt version: average quality score, total runs, total cost.

**Response 200**

```json
{
  "prompt_id": "...",
  "total_runs": 87,
  "avg_quality_score": 0.82,
  "avg_cost": 0.0031,
  "total_tokens": 152400
}
```

---

## Metrics

### `GET /metrics`

Return aggregate numbers for the dashboard overview.

**Response 200**

```json
{
  "total_runs": 1420,
  "success_rate": 0.94,
  "avg_duration_ms": 1840,
  "total_cost": 12.47,
  "total_tokens": 5820000,
  "runs_by_status": {
    "success": 1335,
    "failed": 85,
    "running": 0
  }
}
```
