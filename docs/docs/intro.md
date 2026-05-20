---
id: intro
slug: /
title: What is TraceChain?
sidebar_position: 1
---

# What is TraceChain?

**TraceChain** is a reliability-first observability framework for LLM workflows. It gives you full visibility into every step, every LLM call, every token spent, and every failure — without changing how you write your pipeline logic.

## The problem it solves

LLM applications fail in ways that are hard to reproduce:

- A retrieval step returns stale data
- A prompt changes silently between deploys
- A model hallucinates on a specific input pattern
- Cost spikes appear with no clear source

Traditional APM tools were not built for these failure modes. TraceChain was.

## Core concepts

| Concept | What it is |
|---|---|
| **Workflow Run** | One end-to-end execution of your pipeline |
| **Step** | A discrete unit of work inside a run (retrieval, generation, etc.) |
| **LLM Call** | A single API call to a language model, with tokens + cost tracked |
| **Evaluation** | Automated quality scores attached to a run (relevance, groundedness, hallucination risk) |
| **Feedback** | Human 1–5 star rating attached to a run |
| **Replay** | Re-execute a previous run with the same input, linked in the database |
| **Prompt Version** | A named, versioned prompt text stored and compared over time |

## How it works

```
Your Code                TraceChain SDK           TraceChain Backend
─────────────────────    ────────────────────    ─────────────────────
@workflow("rag-pipeline")                        POST /runs
  @step("retrieve")   ──► context propagation ──► POST /runs/{id}/steps
  @llm_step("gen")    ──► token + cost track  ──► POST /runs/{id}/llm-calls
  evaluate_run(...)   ──► quality scores      ──► POST /runs/{id}/evaluations
```

The SDK decorators are **non-blocking** — a backend timeout or failure never interrupts your workflow. Observability is always best-effort.

## Architecture

```
┌──────────────────────────────────────────────────┐
│  Your Application                                │
│  ┌─────────────────────────────────────────────┐ │
│  │  @workflow  @step  @llm_step  evaluate_run  │ │
│  │           TraceChain Python SDK             │ │
│  └─────────────────┬───────────────────────────┘ │
└────────────────────┼─────────────────────────────┘
                     │ HTTP (non-blocking, 5s timeout)
                     ▼
┌──────────────────────────────────────────────────┐
│  TraceChain Backend (FastAPI + PostgreSQL)        │
│  /runs  /steps  /llm-calls  /prompts  /metrics   │
└──────────────────────┬───────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────┐
│  TraceChain Dashboard (Next.js 14)               │
│  Runs list · Trace timeline · Cost charts ·      │
│  Prompt registry · Replay · Human feedback       │
└──────────────────────────────────────────────────┘
```

## What you get

- **Full trace timeline** — every step with latency, input, output, errors
- **Token & cost tracking** — per-call and per-run aggregates
- **Quality evaluation** — relevance, groundedness, hallucination risk, quality score
- **Prompt registry** — version your prompts and see per-version metrics
- **Replay** — re-run any previous execution from the dashboard
- **Human feedback** — 1–5 star ratings from end users, correlated with evals

## Next steps

- [Install TraceChain →](getting-started/installation)
- [5-minute quickstart →](getting-started/quickstart)
- [SDK reference →](sdk/overview)
