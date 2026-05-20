"""
TraceChain Example 2 — Document QA Agent
=========================================
A question-answering agent that searches a small in-memory document
corpus, generates an answer, and evaluates groundedness — all fully traced.

Run:
    # from the repo root
    pip install -e sdk/
    python examples/document_qa_agent.py

    # with a specific question
    python examples/document_qa_agent.py "What are the system requirements?"

    # with a real OpenAI key
    OPENAI_API_KEY=sk-... python examples/document_qa_agent.py
"""
import sys
import os
import math
import re
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from tracechain import workflow, step, llm_step, evaluate_run, get_run_id

# -- Document corpus -----------------------------------------------------------
# A small but realistic product documentation corpus.

DOCUMENTS = [
    {
        "id": "doc_001",
        "title": "System Requirements",
        "content": (
            "TraceChain requires Python 3.9 or higher. The backend requires PostgreSQL 14+ "
            "and runs on Linux, macOS, and Windows via Docker. Minimum 2 GB RAM is recommended "
            "for the backend service. The dashboard requires Node.js 18+ and runs in any modern browser."
        ),
        "tags": ["system", "requirements", "install", "setup", "python", "node"],
    },
    {
        "id": "doc_002",
        "title": "Getting Started",
        "content": (
            "Install the SDK with pip install tracechain. Set your TRACECHAIN_BACKEND_URL "
            "environment variable to point to your backend. Start the backend with docker-compose up. "
            "Decorate your workflow function with @workflow and individual steps with @step or @llm_step."
        ),
        "tags": ["install", "setup", "quickstart", "getting started", "sdk"],
    },
    {
        "id": "doc_003",
        "title": "LLM Cost Tracking",
        "content": (
            "TraceChain automatically tracks tokens and cost for every LLM call. "
            "Supported models include gpt-4o, gpt-4o-mini, gpt-4-turbo, and gpt-3.5-turbo. "
            "Cost is calculated using the current OpenAI pricing table. Costs aggregate at the "
            "run level and are visible in the dashboard under Metrics > Cost."
        ),
        "tags": ["cost", "tokens", "llm", "openai", "pricing", "tracking"],
    },
    {
        "id": "doc_004",
        "title": "Prompt Versioning",
        "content": (
            "Use the prompt_version parameter on @llm_step to tag each LLM call with a version label. "
            "Create prompt versions via POST /prompts or the dashboard. "
            "The Prompt Versions page shows usage count, average latency, average cost, and quality scores "
            "per version so you can compare performance across prompt iterations."
        ),
        "tags": ["prompt", "version", "versioning", "experiment", "compare"],
    },
    {
        "id": "doc_005",
        "title": "Replay System",
        "content": (
            "Any failed or historical run can be replayed via POST /runs/{run_id}/replay or "
            "the Replay button on the Run Detail page. Replay creates a new run linked to the "
            "original via original_run_id. The new run uses the same workflow name and input "
            "payload. Replays are marked with is_replay=true in the runs table."
        ),
        "tags": ["replay", "rerun", "retry", "failed", "debug"],
    },
    {
        "id": "doc_006",
        "title": "Evaluation Scores",
        "content": (
            "TraceChain computes four evaluation scores automatically: relevance (0-1), "
            "groundedness (0-1), hallucination risk (0-1), and quality (0-1). "
            "Scores are rule-based and require no additional LLM calls. "
            "Call evaluate_run(answer, question, docs) inside a @workflow to store scores. "
            "Scores are visible on the Run Detail page and the Metrics dashboard."
        ),
        "tags": ["evaluation", "eval", "score", "quality", "hallucination", "grounding"],
    },
    {
        "id": "doc_007",
        "title": "Dashboard Overview",
        "content": (
            "The TraceChain dashboard provides six pages: Dashboard Home (KPI cards and charts), "
            "Runs (filterable run table), Run Detail (trace timeline and LLM call inspector), "
            "Prompt Versions, Metrics (cost/latency/failure charts), and Examples. "
            "The dashboard connects to the backend via NEXT_PUBLIC_API_URL."
        ),
        "tags": ["dashboard", "ui", "frontend", "pages", "charts"],
    },
    {
        "id": "doc_008",
        "title": "Failure Handling",
        "content": (
            "Use retries=N on @step to automatically retry a step on failure. "
            "The SDK catches exceptions, records the error message and retry count, and re-raises "
            "after all attempts are exhausted. Failed runs are queryable via GET /runs?status=failed. "
            "The Metrics page shows failure rate per step name."
        ),
        "tags": ["retry", "failure", "error", "exception", "resilience"],
    },
]


# -- BM25-style keyword search -------------------------------------------------

def _tokenize(text: str) -> list[str]:
    return re.findall(r"\b[a-z]{2,}\b", text.lower())


def _bm25_score(query_tokens: list[str], doc_tokens: list[str], corpus_size: int, avg_dl: float) -> float:
    """Simplified BM25 scoring (k1=1.5, b=0.75)."""
    k1, b = 1.5, 0.75
    dl = len(doc_tokens)
    tf_map = Counter(doc_tokens)
    idf_map = {t: math.log((corpus_size + 1) / (1 + sum(1 for d in DOCUMENTS if t in _tokenize(d["content"])))) for t in set(query_tokens)}
    score = 0.0
    for term in query_tokens:
        tf = tf_map.get(term, 0)
        idf = idf_map.get(term, 0)
        score += idf * (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * dl / avg_dl))
    return score


# Pre-compute average doc length
_avg_dl = sum(len(_tokenize(d["content"])) for d in DOCUMENTS) / len(DOCUMENTS)


def _search(query: str, top_k: int = 3) -> list[dict]:
    query_tokens = _tokenize(query)
    scored = []
    for doc in DOCUMENTS:
        doc_tokens = _tokenize(doc["content"] + " " + " ".join(doc["tags"]))
        sc = _bm25_score(query_tokens, doc_tokens, len(DOCUMENTS), _avg_dl)
        scored.append((sc, doc))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [doc for _, doc in scored[:top_k] if _ > 0]


# -- Workflow steps -------------------------------------------------------------

@step(name="search_documents", retries=0)
def search_documents(question: str) -> list[dict]:
    """Search the document corpus using BM25 ranking."""
    results = _search(question, top_k=3)
    if not results:
        # fall back to first 2 docs if no match
        results = DOCUMENTS[:2]
    print(f"  [search_documents] Matched {len(results)} document(s):")
    for r in results:
        print(f"    * {r['title']}")
    return results


@llm_step(name="generate_answer", model="gpt-4o-mini", prompt_version="v1")
def generate_answer(question: str, search_results: list[dict]) -> str:
    """Build a grounded prompt from the search results."""
    context_blocks = []
    for doc in search_results:
        context_blocks.append(f"[{doc['title']}]\n{doc['content']}")
    context = "\n\n".join(context_blocks)

    return (
        f"You are a technical documentation assistant. Answer the question accurately "
        f"and concisely using only the provided documentation.\n\n"
        f"Question: {question}\n\n"
        f"Documentation:\n{context}\n\n"
        f"Answer (be specific and cite the relevant section):"
    )


@step(name="format_response")
def format_response(question: str, answer: str, search_results: list[dict], scores: dict) -> dict:
    """Package the final response with metadata."""
    sources = [{"id": d["id"], "title": d["title"]} for d in search_results]
    return {
        "question": question,
        "answer":   answer,
        "sources":  sources,
        "evaluation": {
            "relevance":          scores["relevance_score"],
            "groundedness":       scores["groundedness_score"],
            "hallucination_risk": scores["hallucination_risk"],
            "quality":            scores["quality_score"],
        },
        "grounded": scores["groundedness_score"] > 0.4,
    }


# -- Main workflow --------------------------------------------------------------

@workflow(name="document_qa_agent")
def qa_agent(question: str) -> dict:
    """Full QA pipeline: search → generate → evaluate → format."""
    print(f"\n{'-'*60}")
    print(f"  Question: {question}")
    print(f"{'-'*60}")

    search_results = search_documents(question)
    answer         = generate_answer(question, search_results)

    print(f"  [generate_answer] Answer ({len(answer.split())} words):")
    print(f"  {answer[:250]}{'...' if len(answer) > 250 else ''}")

    context_texts = [d["content"] for d in search_results]
    scores = evaluate_run(answer, question, context_texts)

    print(f"\n  [evaluation]")
    grounding_bar = "#" * int(scores["groundedness_score"] * 20) + "." * (20 - int(scores["groundedness_score"] * 20))
    quality_bar   = "#" * int(scores["quality_score"] * 20) + "." * (20 - int(scores["quality_score"] * 20))
    print(f"    Groundedness [{grounding_bar}] {scores['groundedness_score']:.0%}")
    print(f"    Quality      [{quality_bar}] {scores['quality_score']:.0%}")
    print(f"    Hallucination risk: {scores['hallucination_risk']:.0%}")

    response = format_response(question, answer, search_results, scores)

    run_id = get_run_id()
    if run_id:
        print(f"\n  [tracechain] Run ID: {run_id}")
        print(f"  [tracechain] View at: http://localhost:3000/runs/{run_id}")

    response["run_id"] = run_id
    return response


# -- Entry point ---------------------------------------------------------------

DEMO_QUESTIONS = [
    "What are the system requirements for TraceChain?",
    "How does prompt versioning work?",
    "How do I replay a failed workflow run?",
    "What evaluation scores does TraceChain compute?",
    "How is LLM cost tracked?",
]


def main():
    question = sys.argv[1] if len(sys.argv) > 1 else None

    if question:
        questions = [question]
    else:
        questions = DEMO_QUESTIONS[:3]
        print("\nNo question provided - running 3 demo questions.")
        print("Usage: python examples/document_qa_agent.py \"Your question here\"")

    print("\n" + "="*60)
    print("  TraceChain - Document QA Agent")
    print("="*60)

    backend_url = os.getenv("TRACECHAIN_BACKEND_URL", "http://localhost:8000")
    openai_key  = os.getenv("OPENAI_API_KEY", "")
    print(f"  Backend:    {backend_url}")
    print(f"  OpenAI key: {'set (ok)' if openai_key else 'not set - using mock responses'}")
    print(f"  Corpus:     {len(DOCUMENTS)} documents")

    results = []
    for q in questions:
        try:
            result = qa_agent(q)
            results.append({"status": "success", **result})
        except Exception as e:
            print(f"\n  [ERROR] Workflow failed: {e}")
            results.append({"question": q, "status": "failed", "error": str(e)})

    print(f"\n{'='*60}")
    print(f"  Completed {len(results)} run(s)")
    successful = [r for r in results if r["status"] == "success"]
    if successful:
        avg_quality = sum(r["evaluation"]["quality"] for r in successful) / len(successful)
        avg_ground  = sum(r["evaluation"]["groundedness"] for r in successful) / len(successful)
        print(f"  Successful:       {len(successful)}")
        print(f"  Avg quality:      {avg_quality:.0%}")
        print(f"  Avg groundedness: {avg_ground:.0%}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
