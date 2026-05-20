---
id: configuration
title: Configuration
sidebar_position: 3
---

# Configuration

All TraceChain configuration is read from environment variables (with `.env` file support via `python-dotenv`).

## SDK environment variables

| Variable | Default | Description |
|---|---|---|
| `TRACECHAIN_BACKEND_URL` | `http://localhost:8000` | Base URL of the TraceChain backend |
| `TRACECHAIN_ENABLED` | `true` | Set to `false` to disable all tracing (no-ops) |
| `TRACECHAIN_TIMEOUT` | `5` | Seconds before a backend HTTP call times out |

### Example `.env`

```bash
TRACECHAIN_BACKEND_URL=https://tracechain.internal:8000
TRACECHAIN_ENABLED=true
TRACECHAIN_TIMEOUT=3
```

---

## Backend environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | PostgreSQL DSN |
| `ALLOWED_ORIGINS` | No | `*` | CORS allowed origins (comma-separated) |

### Example

```bash
DATABASE_URL=postgresql://tracechain:tracechain@db:5432/tracechain
ALLOWED_ORIGINS=http://localhost:3000,https://app.example.com
```

---

## Dashboard environment variables

Stored in `dashboard/.env.local`:

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL accessed by the browser |

---

## Programmatic configuration

You can also configure the SDK in code, bypassing environment variables:

```python
from tracechain import TraceChainConfig, TraceChainClient, workflow

config = TraceChainConfig(
    base_url="https://tracechain.internal:8000",
    enabled=True,
    timeout=3.0,
)
client = TraceChainClient(config)

@workflow(name="my_pipeline", client=client)
def my_pipeline(query: str):
    ...
```

This is useful when you need different backends for different workflows in the same process, or when writing tests.

---

## Disabling tracing

Set `TRACECHAIN_ENABLED=false` to turn all SDK decorators into pure no-ops. The decorated functions run normally; no HTTP calls are made:

```bash
TRACECHAIN_ENABLED=false python my_pipeline.py
```

This is recommended in unit tests where you don't want a backend dependency.

---

## Timeout behaviour

The `TRACECHAIN_TIMEOUT` setting controls how long the SDK waits for the backend before giving up. **A timeout never raises an exception** — tracing failures are logged as warnings and the workflow continues unaffected.

```
[WARNING] tracechain.client  Backend call failed (timeout): POST /runs/abc/steps
```

Set a shorter timeout (e.g. `2`) in latency-sensitive environments.
