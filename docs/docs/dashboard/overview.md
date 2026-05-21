---
id: overview
title: Dashboard Overview
sidebar_position: 1
---

# Dashboard

The TraceChain dashboard is a **Next.js 14** application (App Router, Tailwind CSS, Recharts) that gives you a visual interface over all your workflow observability data.

## Starting the dashboard

```bash
cd dashboard
npm install
npm run dev     # http://localhost:3000
```

For production:

```bash
npm run build
npm start
```

---

## Pages

### Runs List — `/`

The home page lists all workflow runs. Each row shows:

| Column | Description |
|---|---|
| Workflow | `workflow_name` |
| Status | Color-coded badge: success / failed / running |
| Duration | End-to-end time in ms |
| Tokens | Total tokens consumed |
| Cost | Estimated USD cost |
| Quality | Quality score bar (0–1) |
| Started | Relative time |
| Replay | Whether this is a replay |

**Filtering** — use the top bar to filter by status, workflow name, or date range.

---

### Run Detail — `/runs/[id]`

Full trace view for a single run.

#### Summary card

- Status, duration, cost, tokens
- Input payload (collapsible JSON)
- Output payload (collapsible JSON)
- Error message (if failed)
- Replay button

#### Trace Timeline

Horizontal bar chart showing every step and LLM call in chronological order. Each bar shows:
- Step name
- Start offset and duration
- Status colour (green / red)

Hover a bar to see the full input/output.

#### LLM Calls

Card list of every LLM call in the run:

- Model, tokens, cost, latency
- Prompt and response (expandable)
- Prompt version tag

#### Evaluations

Score bars for relevance, groundedness, hallucination risk, and quality.

#### Human Feedback

Star rating widget — submit 1–5 stars with an optional comment. Existing ratings shown below.

---

### Prompts — `/prompts` {#prompts}

Table of all prompt versions:

| Column | Description |
|---|---|
| Name | Logical prompt name |
| Version | Version tag |
| Active | Whether marked active |
| Avg Quality | Average quality score across runs using this version |
| Total Runs | Number of LLM calls referencing this version |
| Created | Creation timestamp |

Click a row to see the full prompt text and metrics.

---

### Prompt Detail — `/prompts/[id]`

- Full prompt text in a code block
- Usage metrics: avg quality score, total runs, avg cost, total tokens
- History of all LLM calls using this prompt version

---

### Examples — `/examples`

Sample workflow code snippets demonstrating how to instrument common patterns:

- Basic RAG pipeline
- Multi-step agent
- Retry pattern
- Replay usage

---

## Component library

The dashboard ships a small set of reusable components in `src/components/`:

| Component | Path | Description |
|---|---|---|
| `Card` | `ui/Card.tsx` | Base white/dark card with optional header |
| `Badge` | `ui/Badge.tsx` | Status badge (success / failed / running / pending) |
| `StatCard` | `ui/StatCard.tsx` | Metric tile with label + value |
| `ScoreBar` | `ui/ScoreBar.tsx` | Horizontal progress bar for 0–1 scores |
| `CodeBlock` | `ui/CodeBlock.tsx` | Syntax-highlighted code with copy button |
| `AreaChart` | `charts/AreaChart.tsx` | Recharts area chart wrapper |
| `HBarChart` | `charts/HBarChart.tsx` | Horizontal bar chart (trace timeline) |
| `TraceTimeline` | `runs/TraceTimeline.tsx` | Full trace visualization |
| `LLMCallCard` | `runs/LLMCallCard.tsx` | Single LLM call detail card |

---

## Environment

Set `NEXT_PUBLIC_API_URL` in `dashboard/.env.local`:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

The dashboard uses this to call the TraceChain backend API from the browser.

---

## Data fetching

All data is fetched client-side using the native `fetch` API. There is no server-side rendering of run data. Pages use React state + `useEffect` for loading states.
