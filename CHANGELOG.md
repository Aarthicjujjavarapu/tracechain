# Changelog

All notable changes to TraceChain are documented here.
Versions follow [Semantic Versioning](https://semver.org/).

---

## [0.2.0] — 2026-05-21

### Python SDK (`tracechain`)

#### Added
- **`@batch_step` decorator** — trace a list of items through a single-item function with a parent batch step and optional per-item child steps. Supports sync/async, `concurrency` (ThreadPoolExecutor / asyncio semaphore), partial-failure collection (`raise_on_error=False`), and per-item tracing (`trace_items=True`). Returns `BatchResult` with `.success_count`, `.failed_count`, `.success_results`, `.errors`.
- **`tracechain init` CLI** — `tracechain init [directory]` scaffolds `.env`, `docker-compose.yml`, and a starter `pipeline.py`. Registered as a console script; available immediately after `pip install tracechain`.
- **Async context propagation** — `run_id`, `step_id`, and cost accumulators are fully isolated across concurrent `asyncio.gather` tasks. Child tasks spawned with `asyncio.create_task()` inherit the parent's `run_id` without bleeding mutations back.

#### Tests
- 5 tests for `tracechain init` CLI
- 7 tests for async context propagation (run_id chain, step_id isolation, cost accumulator isolation, `create_task` inheritance)
- 19 tests for `@batch_step` (sync/async, concurrency, partial failures, trace_items, BatchResult interface)

---

### Dashboard

#### Added
- **Cost budget alerts** — per-run and daily cost budgets saved to `localStorage`. Metrics page shows a red reference line on the cost-per-day chart and an amber alert banner when days exceed the budget. Runs page highlights over-budget cost cells red with a warning icon.
- **Prompt diff view** — side-by-side (split) and unified diff between any two prompt versions using a pure LCS algorithm (no external dependencies). Compare button on each multi-version prompt group opens an inline panel with version selectors and live diff.
- **Live event feed** — WebSocket `ws://backend/ws/live?run_id=<id>` streams events into a "Live Feed" tab on the run detail page.

---

### Infrastructure

#### Added
- **Helm chart** (`helm/tracechain/`) — Kubernetes deployment for backend + dashboard. Supports SQLite (PVC) or external PostgreSQL, optional HPA, dual-host Ingress, chart-managed or existing Secrets.
- **CI** — GitHub Actions matrix (Python 3.9–3.12), JS SDK tests, dashboard typecheck, backend lint, backend API tests (30 tests), all-green gate.
- **`publish.yml`** — automated PyPI + npm publish on `v*` tags.

---

## [0.1.0] — 2026-05-19

Initial release.

### Python SDK
- `@workflow`, `@step`, `@llm_step` decorators
- Sync + async support with exponential-backoff retries
- `evaluate_run()` — relevance, groundedness, hallucination scoring
- `trigger_replay()` — re-run a workflow from its stored input
- `configure_otel()` — OpenTelemetry export (console, OTLP, Jaeger)
- `observe_llm()` — wrap any LLM call with streaming support
- `LocalClient` — file-based store for offline development

### JavaScript SDK (`@tracechain/sdk`)
- `TraceChainClient` with `createRun`, `completeRun`, `failRun`, `createStep`, `completeStep`, `failStep`, `logLlmCall`
- Full TypeScript support with `.d.ts` declarations

### Backend (FastAPI)
- `/runs`, `/runs/{id}/steps`, `/runs/{id}/llm-calls` REST API
- `/runs/{id}/replay`, `/runs/{id}/evaluations`, `/runs/{id}/feedback`
- `/v1/runs/{id}/graph`, `/v1/runs/{id}/diagnostics`
- `/ws/live` WebSocket for real-time event streaming
- `/prompts` CRUD + metrics
- `/metrics/overview`, `/metrics/timeseries/*`
- PostgreSQL (production) / SQLite (development) via SQLAlchemy

### Dashboard (Next.js)
- Dashboard, Runs, Prompts, Metrics, Examples pages
- Agent execution graph (ReactFlow)
- Trace timeline, diagnostics panel, LLM call cards
- Eval scores, human feedback, replay history
- Compare panel for side-by-side run comparison

### Deployment
- `docker-compose.yml` (SQLite dev), `docker-compose.prod.yml` (PostgreSQL)
- Docusaurus docs site with Getting Started, SDK reference, OTel guide
- PyPI: `pip install tracechain`
- npm: `npm install @tracechain/sdk`
