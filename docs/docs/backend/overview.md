---
id: overview
title: Backend Overview
sidebar_position: 1
---

# Backend Overview

The TraceChain backend is a **FastAPI** application that stores all observability data in **PostgreSQL**. It is the central storage and query layer between the SDK and the dashboard.

## Technology stack

| Component | Technology |
|---|---|
| Web framework | FastAPI 0.111 |
| ORM | SQLAlchemy 2.x |
| Migrations | Alembic |
| Database | PostgreSQL 15+ |
| Validation | Pydantic v2 |
| Server | Uvicorn |

## Starting the backend

```bash
# Docker Compose (recommended)
docker compose up -d

# Local
cd backend
uvicorn app.main:app --reload --port 8000
```

## Auto-generated docs

FastAPI generates interactive documentation automatically:

- **Swagger UI** — [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc** — [http://localhost:8000/redoc](http://localhost:8000/redoc)

## Routes summary

| Prefix | Tag | Description |
|---|---|---|
| `/health` | health | Liveness + DB connectivity check |
| `/runs` | runs | Workflow run CRUD + lifecycle |
| `/runs/{id}/steps` | steps | Step records |
| `/runs/{id}/llm-calls` | llm-calls | LLM call records |
| `/runs/{id}/evaluations` | evaluations | Quality scores |
| `/runs/{id}/feedback` | feedback | Human ratings |
| `/runs/{id}/replay` | runs | Trigger a replay |
| `/prompts` | prompts | Prompt version registry |
| `/metrics` | metrics | Aggregate dashboard metrics |

## Database migrations

Migrations are applied automatically on startup via Alembic. To run manually:

```bash
cd backend
alembic upgrade head
```

To create a new migration after editing `app/models.py`:

```bash
alembic revision --autogenerate -m "describe_change"
alembic upgrade head
```

## CORS

CORS is configured to allow all origins by default (`*`). Set `ALLOWED_ORIGINS` in production:

```bash
ALLOWED_ORIGINS=https://app.example.com
```

## Health check

```bash
curl http://localhost:8000/health
# {"status":"ok","db":"connected"}
```

Returns `{"status":"ok","db":"error","detail":"..."}` if the database is unreachable.

## Data model overview

```
workflow_runs
  ├── trace_steps
  │     └── llm_calls (step_id FK, optional)
  ├── llm_calls (run_id FK)
  ├── evaluation_results
  └── human_feedback

prompt_versions (independent table)
```

See [Database](database) for the full schema.
