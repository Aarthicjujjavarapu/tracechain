---
id: database
title: Database Schema
sidebar_position: 3
---

# Database Schema

TraceChain uses PostgreSQL with five tables. All primary keys are UUID strings.

## ERD (simplified)

```
workflow_runs (id PK)
├── trace_steps (run_id FK)
│     └── llm_calls (step_id FK, nullable)
├── llm_calls (run_id FK)
├── evaluation_results (run_id FK)
└── human_feedback (run_id FK)

prompt_versions (id PK, standalone)
```

---

## `workflow_runs`

Stores one record per execution of a `@workflow`-decorated function.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | No | Primary key |
| `workflow_name` | VARCHAR(255) | No | Name from `@workflow(name=...)` |
| `status` | ENUM | No | `pending`, `running`, `success`, `failed` |
| `input_payload` | JSONB | No | Function arguments as JSON |
| `output_payload` | JSONB | Yes | Return value |
| `error_message` | TEXT | Yes | Exception message on failure |
| `started_at` | TIMESTAMPTZ | No | Run start time |
| `ended_at` | TIMESTAMPTZ | Yes | Run end time |
| `duration_ms` | INT | Yes | `ended_at - started_at` in ms |
| `total_cost` | FLOAT | Yes | Sum of all LLM call costs |
| `total_tokens` | INT | Yes | Sum of all LLM token counts |
| `is_replay` | BOOLEAN | No | `true` for replay runs |
| `original_run_id` | UUID FK | Yes | Source run for replays |
| `metadata` | JSONB | Yes | Arbitrary extra fields |

**Indexes:** `workflow_name`

---

## `trace_steps`

One record per `@step` or `@llm_step` invocation.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | No | Primary key |
| `run_id` | UUID FK | No | Parent workflow run |
| `step_name` | VARCHAR(255) | No | Name from decorator |
| `step_type` | ENUM | No | `step` or `llm_step` |
| `status` | ENUM | No | `pending`, `running`, `success`, `failed` |
| `input_payload` | JSONB | No | Step arguments |
| `output_payload` | JSONB | Yes | Return value |
| `error_message` | TEXT | Yes | Exception on failure |
| `started_at` | TIMESTAMPTZ | No | Step start |
| `ended_at` | TIMESTAMPTZ | Yes | Step end |
| `duration_ms` | INT | Yes | Step duration |
| `retry_count` | INT | No | Retries used (0 if none) |
| `metadata` | JSONB | Yes | Extra fields |

**Indexes:** `run_id`

---

## `llm_calls`

One record per LLM API call made inside an `@llm_step`.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | No | Primary key |
| `run_id` | UUID FK | No | Parent run |
| `step_id` | UUID FK | Yes | Parent step (if inside `@llm_step`) |
| `provider` | VARCHAR(100) | No | `openai` |
| `model` | VARCHAR(100) | No | Model name |
| `prompt` | TEXT | No | First user message |
| `response` | TEXT | Yes | Model reply |
| `input_tokens` | INT | Yes | Prompt token count |
| `output_tokens` | INT | Yes | Completion token count |
| `total_tokens` | INT | Yes | `input + output` |
| `estimated_cost` | FLOAT | Yes | Cost in USD |
| `latency_ms` | INT | Yes | Call latency |
| `temperature` | FLOAT | Yes | Sampling temperature |
| `status` | ENUM | No | `success` or `failed` |
| `error_message` | TEXT | Yes | Error on failure |
| `prompt_version` | VARCHAR(50) | Yes | Links to `PromptVersion` |
| `created_at` | TIMESTAMPTZ | No | Record creation time |

**Indexes:** `run_id`

---

## `evaluation_results`

Quality scores attached to a run by `evaluate_run`.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | No | Primary key |
| `run_id` | UUID FK | No | Parent run |
| `relevance_score` | FLOAT | No | 0–1 |
| `groundedness_score` | FLOAT | No | 0–1 |
| `hallucination_risk` | FLOAT | No | 0–1 |
| `quality_score` | FLOAT | No | 0–1 composite |
| `failure_reason` | TEXT | Yes | Why scoring failed (if any) |
| `created_at` | TIMESTAMPTZ | No | Creation time |

**Indexes:** `run_id`

---

## `human_feedback`

Human ratings submitted from the dashboard or API.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | No | Primary key |
| `run_id` | UUID FK | No | Rated run |
| `rating` | INT | No | 1–5 stars |
| `comment` | TEXT | Yes | Free-text comment |
| `created_at` | TIMESTAMPTZ | No | Submission time |

**Indexes:** `run_id`

---

## `prompt_versions`

Versioned prompt text registry.

| Column | Type | Nullable | Description |
|---|---|---|---|
| `id` | UUID | No | Primary key |
| `prompt_name` | VARCHAR(255) | No | Logical prompt name |
| `version` | VARCHAR(50) | No | Version tag |
| `prompt_text` | TEXT | No | Full prompt text |
| `is_active` | BOOLEAN | No | Whether this is the current version |
| `metadata` | JSONB | Yes | Author, notes, etc. |
| `created_at` | TIMESTAMPTZ | No | Creation time |

**Indexes:** `prompt_name`

---

## Migrations

Managed by Alembic. The initial migration (`0001_initial_schema.py`) creates all five tables.

```bash
# apply all migrations
cd backend && alembic upgrade head

# roll back one migration
alembic downgrade -1

# generate a new migration
alembic revision --autogenerate -m "add_column_x"
```
