# CLI Reference

The `tracechain` CLI ships with the Python SDK and gives you a fast way to scaffold new projects.

## Installation

```bash
pip install tracechain
```

The `tracechain` command is available immediately after install.

## Commands

### `tracechain init [directory]`

Scaffold a new TraceChain project with a `.env`, `docker-compose.yml`, and a starter `pipeline.py`.

```bash
tracechain init              # scaffold in the current directory
tracechain init my-project   # create and scaffold my-project/
tracechain init . --overwrite  # regenerate files, overwriting existing ones
```

**Generated files**

| File | Purpose |
|---|---|
| `.env` | Backend URL and LLM provider keys |
| `docker-compose.yml` | Backend + dashboard services, ready to `docker compose up` |
| `pipeline.py` | Starter workflow with `@workflow`, `@step`, and `@llm_step` |

**Flags**

| Flag | Description |
|---|---|
| `--overwrite` | Replace existing files instead of skipping them |

**Example output**

```
Created directory my-project
  create my-project/.env
  create my-project/docker-compose.yml
  create my-project/pipeline.py

TraceChain project ready!

  Next steps:
    1. Start the stack:   docker compose up -d
    2. Open dashboard:    http://localhost:3000
    3. Run your pipeline: python pipeline.py
```

## Quick start with the CLI

```bash
pip install tracechain
tracechain init my-agent
cd my-agent

# Fill in your API keys
$EDITOR .env

# Start backend + dashboard
docker compose up -d

# Run your first traced workflow
python pipeline.py
```

Open [http://localhost:3000](http://localhost:3000) to see the run appear in the dashboard.
