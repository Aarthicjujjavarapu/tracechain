---
id: environment-variables
title: Environment Variables
sidebar_position: 2
---

# Environment Variables

Complete reference for all environment variables across all three TraceChain components.

## SDK

Set in your application's `.env` file or shell environment.

| Variable | Default | Required | Description |
|---|---|---|---|
| `TRACECHAIN_BACKEND_URL` | `http://localhost:8000` | No | Full URL of the TraceChain backend |
| `TRACECHAIN_ENABLED` | `true` | No | `false` disables all SDK tracing (no-ops) |
| `TRACECHAIN_TIMEOUT` | `5` | No | Backend HTTP timeout in seconds |
| `OPENAI_API_KEY` | — | If using OpenAI | Required by `@llm_step` when calling OpenAI |

### Example `.env`

```bash
TRACECHAIN_BACKEND_URL=http://localhost:8000
TRACECHAIN_ENABLED=true
TRACECHAIN_TIMEOUT=5
OPENAI_API_KEY=sk-...
```

---

## Backend

Set in `docker-compose.yml`, shell, or a `.env` file in the `backend/` directory.

| Variable | Default | Required | Description |
|---|---|---|---|
| `DATABASE_URL` | — | **Yes** | PostgreSQL DSN |
| `ALLOWED_ORIGINS` | `*` | No | Comma-separated CORS allowed origins |

### `DATABASE_URL` formats

```bash
# Standard DSN
DATABASE_URL=postgresql://user:password@host:5432/dbname

# With SSL (production)
DATABASE_URL=postgresql://user:password@host:5432/dbname?sslmode=require

# Docker Compose internal network
DATABASE_URL=postgresql://tracechain:tracechain@db:5432/tracechain
```

### Example (production)

```bash
DATABASE_URL=postgresql://tracechain:s3cr3t@prod-db.internal:5432/tracechain?sslmode=require
ALLOWED_ORIGINS=https://dashboard.example.com
```

---

## Dashboard

Set in `dashboard/.env.local` (development) or in your hosting provider's UI (production).

| Variable | Default | Required | Description |
|---|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | No | Backend URL, accessible from the **browser** |

:::caution
`NEXT_PUBLIC_API_URL` is embedded in the browser bundle at build time. It must be the URL that end users' browsers can reach, not an internal Docker network name.
:::

### Example

```bash
# dashboard/.env.local (development)
NEXT_PUBLIC_API_URL=http://localhost:8000

# Vercel / production
NEXT_PUBLIC_API_URL=https://api.tracechain.example.com
```

---

## `.env.example`

The repo root contains a `.env.example` with all variables pre-filled with defaults:

```bash
cp .env.example .env
# edit .env with your values
```

---

## Variable precedence

The SDK uses `python-dotenv` which follows this precedence (highest first):

1. Shell environment (`export VAR=x`)
2. `.env` file in the current working directory
3. Default values in `TraceChainConfig`

For the dashboard, Next.js follows its standard [env var loading order](https://nextjs.org/docs/basic-features/environment-variables).
