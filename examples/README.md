# TraceChain Examples

Both examples work **without an OpenAI API key** — a built-in mock LLM generates realistic responses so you can see full traces in the dashboard immediately.

## Setup

```bash
# From the repo root
pip install -e sdk/
docker compose up -d   # starts Postgres + FastAPI backend
```

## Example 1 — RAG Pipeline

A retrieval-augmented generation workflow: retrieve → rerank → generate → evaluate.

```bash
python examples/01_rag_pipeline.py
# or with a custom query:
python examples/01_rag_pipeline.py "How does replay work?"
```

**What it demonstrates:**
- `@step` for retrieval and reranking
- `@llm_step` for answer generation
- `evaluate_run` for automatic quality scoring

## Example 2 — Customer Support Agent

A multi-step agent that classifies intent, fetches KB articles, drafts a response, and formats it.

```bash
python examples/02_support_agent.py
# runs all 5 sample tickets to populate the dashboard

# or with a custom message:
python examples/02_support_agent.py "How do I cancel my subscription?"
```

**What it demonstrates:**
- Two `@llm_step` calls in one workflow (classify + respond)
- `@step` with `retries=2` for resilient KB lookup
- Multiple runs to compare quality scores in the dashboard

## Example 3 — Streaming LLM with Tool Calling

A two-step agent that plans a tool call (streaming), executes it, then synthesises the result into a final answer (non-streaming).

```bash
python examples/03_streaming_llm.py
```

**What it demonstrates:**
- `observe_llm()` in streaming mode with `is_stream=True`
- `obs.on_chunk()` for time-to-first-token (TTFT) tracking
- Tool call attributes recorded in span metadata
- Two chained LLM calls in one workflow showing streaming vs. non-streaming contrast

## Viewing traces

Open [http://localhost:3000](http://localhost:3000) after running either example.
