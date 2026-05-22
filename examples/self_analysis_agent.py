"""
TraceChain Example 3 - Self Analysis Agent
===========================================
TraceChain analyzing itself. This workflow queries the live TraceChain backend
for metrics and recent runs, then uses an LLM to answer questions about them.

The run created by this script will itself appear in the dashboard, making it
a fully meta trace: TraceChain observing TraceChain.

Run:
    python examples/self_analysis_agent.py
    python examples/self_analysis_agent.py "Which workflow has the highest cost?"
    OPENAI_API_KEY=sk-... python examples/self_analysis_agent.py
"""
import sys
import os
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

import httpx
from tracechain import workflow, step, llm_step, evaluate_run, get_run_id

BACKEND = os.getenv("TRACECHAIN_BACKEND_URL", "http://localhost:8000")


# -- Steps ---------------------------------------------------------------------

@step(name="fetch_overview_metrics")
def fetch_overview_metrics() -> dict:
    """Pull KPI summary from the live backend."""
    r = httpx.get(f"{BACKEND}/metrics/overview", timeout=5)
    r.raise_for_status()
    data = r.json()
    print(f"  [fetch_overview_metrics] total_runs={data.get('total_runs')} "
          f"success_rate={data.get('success_rate', 0):.1%} "
          f"total_cost=${data.get('total_cost', 0):.5f}")
    return data


@step(name="fetch_failure_metrics")
def fetch_failure_metrics() -> list:
    """Pull per-step failure rates."""
    r = httpx.get(f"{BACKEND}/metrics/failures", timeout=5)
    r.raise_for_status()
    data = r.json()
    print(f"  [fetch_failure_metrics] {len(data)} step(s) with failure data")
    return data


@step(name="fetch_cost_by_model")
def fetch_cost_by_model() -> list:
    """Pull cost breakdown by model."""
    r = httpx.get(f"{BACKEND}/metrics/cost", timeout=5)
    r.raise_for_status()
    data = r.json()
    for item in data:
        print(f"  [fetch_cost_by_model] {item.get('model')}: ${item.get('total_cost', 0):.5f} ({item.get('call_count', 0)} calls)")
    return data


@step(name="fetch_recent_runs")
def fetch_recent_runs(limit: int = 10) -> list:
    """Pull the most recent workflow runs."""
    r = httpx.get(f"{BACKEND}/runs?limit={limit}", timeout=5)
    r.raise_for_status()
    items = r.json()["items"]
    print(f"  [fetch_recent_runs] fetched {len(items)} recent run(s)")
    return items


@llm_step(name="generate_analysis", model="gpt-4o-mini", prompt_version="v1")
def generate_analysis(question: str, overview: dict, failures: list, costs: list, recent_runs: list) -> str:
    """Build a grounded prompt from live TraceChain data."""
    overview_text = json.dumps(overview, indent=2)

    failures_text = "\n".join(
        f"  - {f.get('step_name', '?')}: {f.get('failure_count', 0)} failures "
        f"({f.get('failure_rate', 0):.1%} failure rate, {f.get('total_count', 0)} total)"
        for f in failures
    ) or "  No failure data available."

    costs_text = "\n".join(
        f"  - {c.get('model', '?')}: ${c.get('total_cost', 0):.5f} "
        f"({c.get('call_count', 0)} calls)"
        for c in costs
    ) or "  No cost data available."

    recent_text = "\n".join(
        f"  - [{r.get('status','?').upper()}] {r.get('workflow_name','?')} "
        f"| {r.get('duration_ms','?')}ms "
        f"| ${r.get('total_cost') or 0:.5f}"
        for r in recent_runs[:5]
    )

    return (
        f"You are an AI observability analyst reviewing a live TraceChain deployment.\n"
        f"Answer the question below using only the provided live metrics.\n"
        f"Be specific, cite numbers, and keep the answer under 4 sentences.\n\n"
        f"Question: {question}\n\n"
        f"=== OVERVIEW METRICS ===\n{overview_text}\n\n"
        f"=== FAILURE RATES BY STEP ===\n{failures_text}\n\n"
        f"=== COST BY MODEL ===\n{costs_text}\n\n"
        f"=== 5 MOST RECENT RUNS ===\n{recent_text}\n\n"
        f"Analysis:"
    )


# -- Workflow ------------------------------------------------------------------

@workflow(name="tracechain_self_analysis")
def analyze_tracechain(question: str) -> dict:
    """Fetch live TraceChain metrics and answer a question about them."""
    print(f"\n{'-'*60}")
    print(f"  Question: {question}")
    print(f"{'-'*60}")

    overview  = fetch_overview_metrics()
    failures  = fetch_failure_metrics()
    costs     = fetch_cost_by_model()
    runs      = fetch_recent_runs()
    answer    = generate_analysis(question, overview, failures, costs, runs)

    print(f"\n  [generate_analysis] Answer ({len(answer.split())} words):")
    print(f"  {answer}")

    context_docs = [
        json.dumps(overview),
        " ".join(f"{f.get('label')} {f.get('failure_count')}" for f in failures),
        " ".join(f"{c.get('label')} {c.get('value')}" for c in costs),
    ]
    scores = evaluate_run(answer, question, context_docs)

    print(f"\n  [evaluation]")
    print(f"    relevance:    {scores['relevance_score']:.2%}")
    print(f"    groundedness: {scores['groundedness_score']:.2%}")
    print(f"    hallucination risk: {scores['hallucination_risk']:.2%}")
    print(f"    quality:      {scores['quality_score']:.2%}")

    run_id = get_run_id()
    if run_id:
        print(f"\n  [tracechain] This run's ID: {run_id}")
        print(f"  [tracechain] View trace at: http://localhost:3000/runs/{run_id}")

    return {
        "question": question,
        "answer":   answer,
        "scores":   scores,
        "run_id":   run_id,
    }


# -- Entry point ---------------------------------------------------------------

DEMO_QUESTIONS = [
    "Which workflow has the highest failure rate and what step is failing?",
    "Which model is being used most and what is the total cost so far?",
    "What is the overall success rate and average latency across all workflows?",
]


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else None

    if question:
        questions = [question]
    else:
        questions = DEMO_QUESTIONS
        print("\nNo question provided - running 3 demo questions.")
        print("Usage: python examples/self_analysis_agent.py \"Your question here\"")

    print("\n" + "="*60)
    print("  TraceChain - Self Analysis Agent")
    print("="*60)
    print(f"  Backend:    {BACKEND}")
    print(f"  OpenAI key: {'set (ok)' if os.getenv('OPENAI_API_KEY') else 'not set - using mock responses'}")

    results = []
    for q in questions:
        try:
            result = analyze_tracechain(q)
            results.append({"status": "success", **result})
        except Exception as e:
            print(f"\n  [ERROR] {e}")
            results.append({"question": q, "status": "failed", "error": str(e)})

    print(f"\n{'='*60}")
    print(f"  Completed {len(results)} analysis run(s)")
    print(f"  Successful: {sum(1 for r in results if r['status'] == 'success')}")
    print(f"  Failed:     {sum(1 for r in results if r['status'] == 'failed')}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
