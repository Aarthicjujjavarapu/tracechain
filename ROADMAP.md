# TraceChain Roadmap

This is a living document. Items move between milestones as priorities shift.

## v0.1.x — Foundation (current)

- [x] `@workflow`, `@step`, `@llm_step`, `observe_llm` decorators
- [x] Sync and async support
- [x] Streaming with time-to-first-token tracking
- [x] Retry with exponential backoff and jitter
- [x] OpenTelemetry integration (spans, GenAI semconv)
- [x] Local mode (SQLite, zero infrastructure)
- [x] Python SDK on PyPI
- [x] TypeScript SDK on npm
- [x] FastAPI backend
- [x] CI across Python 3.9–3.12

## v0.2 — Reliability Diagnostics

- [ ] Batch ingestion endpoint (`POST /v1/ingest/batch`)
- [ ] Agent execution graph API (`GET /v1/runs/{id}/graph`)
- [ ] Diagnostics API (`GET /v1/runs/{id}/diagnostics`)
  - Retry chain visualization
  - Latency bottleneck analysis
  - Token usage propagation and cost attribution
  - Context window truncation detection
- [ ] WebSocket real-time streaming (`/ws/live`)
- [ ] Async ring buffer in SDK (non-blocking export)
- [ ] Docker Compose self-hosted stack

## v0.3 — Dashboard

- [ ] React dashboard with ReactFlow agent graph
- [ ] Span timeline view
- [ ] Reliability diagnostics panels
- [ ] Real-time run feed
- [ ] Cost and token dashboards
- [ ] Dark mode

## v0.4 — Integrations

- [ ] LangChain auto-instrumentation
- [ ] LangGraph agent tracing
- [ ] LlamaIndex tracing
- [ ] CrewAI tracing
- [ ] OpenAI Agents SDK tracing
- [ ] Vercel AI SDK (TypeScript)

## v0.5 — Evaluations

- [ ] Evaluation runner (run evals against stored traces)
- [ ] Custom scorer API
- [ ] LLM-as-judge integration
- [ ] Dataset management (store input/output pairs for regression testing)

## v1.0 — Production Hardening

- [ ] PostgreSQL storage with proper indexing and migrations
- [ ] Rate limiting on ingest endpoint
- [ ] API key authentication
- [ ] Multi-tenant support (project isolation)
- [ ] Hosted cloud option
- [ ] Prometheus metrics endpoint
- [ ] Alerting rules (cost spikes, error rate, latency p99)

## What we will NOT build

- Prompt management (use Langfuse or PromptLayer)
- Model gateway / proxy (use LiteLLM or Helicone)
- Fine-tuning pipelines
- A/B testing infrastructure
- Annotation/labeling UI

These are adjacent products with established competitors. We stay focused on reliability and observability depth for agent systems.

## How to influence the roadmap

Open a GitHub issue with the label `roadmap` describing:
1. The problem you're trying to solve
2. How you're working around it today
3. Why TraceChain is the right place to solve it

Issues with clear problem statements and real use cases move faster.
