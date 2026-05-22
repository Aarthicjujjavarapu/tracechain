"""
Example 1: RAG Pipeline
=======================
A retrieval-augmented generation workflow that demonstrates:
  - @workflow   — run lifecycle
  - @step       — retrieval + reranking steps
  - @llm_step   — answer generation
  - evaluate_run — automatic quality scoring

Run:
    cd TraceChain
    pip install -e sdk/
    python examples/01_rag_pipeline.py

Works without OPENAI_API_KEY (uses built-in mock LLM).
Set OPENAI_API_KEY to use the real model.
"""
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(name)s  %(message)s",
    stream=sys.stdout,
)

from tracechain import workflow, step, llm_step, evaluate_run

# ── Fake document corpus ─────────────────────────────────────────────────────
CORPUS = {
    "tracechain-intro": (
        "TraceChain is a reliability-first observability framework for LLM workflows. "
        "It automatically traces every step, every LLM call, every token spent, "
        "and every failure without changing how you write pipeline logic."
    ),
    "tracechain-decorators": (
        "TraceChain provides three decorators: @workflow marks the entry point and "
        "creates a run record; @step instruments a discrete unit of work; @llm_step "
        "wraps a function that builds a prompt and records tokens, cost, and latency."
    ),
    "tracechain-evals": (
        "The evaluate_run function scores answers for relevance, groundedness, "
        "hallucination risk, and overall quality. Scores are stored per run and "
        "displayed on the dashboard for comparison across prompt versions."
    ),
    "tracechain-replay": (
        "TraceChain replay lets you re-execute any previous workflow run with the "
        "same input. The new run is linked to the original so you can compare "
        "outputs, costs, and quality scores side by side."
    ),
    "tracechain-config": (
        "Configuration is read from environment variables. TRACECHAIN_BACKEND_URL "
        "sets the backend address, TRACECHAIN_ENABLED can disable tracing entirely "
        "for unit tests, and TRACECHAIN_TIMEOUT controls the HTTP timeout."
    ),
}


# ── Steps ─────────────────────────────────────────────────────────────────────

@step(name="retrieve_docs")
def retrieve_docs(query: str, top_k: int = 3) -> list[dict]:
    """Keyword-based retrieval over the in-memory corpus."""
    query_words = set(query.lower().split())

    scored = []
    for doc_id, text in CORPUS.items():
        doc_words = set(text.lower().split())
        overlap = len(query_words & doc_words)
        if overlap > 0:
            scored.append({"id": doc_id, "text": text, "score": overlap})

    scored.sort(key=lambda d: d["score"], reverse=True)
    results = scored[:top_k]

    print(f"  Retrieved {len(results)} docs for: '{query}'")
    for r in results:
        print(f"    [{r['id']}] score={r['score']}")

    return results


@step(name="rerank_docs")
def rerank_docs(docs: list[dict], query: str) -> list[str]:
    """
    Rerank by doc length × overlap score (simulates a cross-encoder).
    Returns plain text strings for the LLM context.
    """
    query_words = set(query.lower().split())

    def rerank_score(doc: dict) -> float:
        text_words = set(doc["text"].lower().split())
        overlap = len(query_words & text_words)
        length_bonus = min(1.0, len(doc["text"]) / 300)
        return overlap * (1 + length_bonus)

    docs_sorted = sorted(docs, key=rerank_score, reverse=True)
    texts = [d["text"] for d in docs_sorted]

    print(f"  Reranked {len(texts)} docs")
    return texts


@llm_step(name="generate_answer", model="gpt-4o-mini", prompt_version="rag-v1")
def generate_answer(query: str, context_docs: list[str]) -> str:
    """Build the prompt. The decorator calls the LLM and returns its response."""
    context = "\n\n".join(
        f"[Doc {i + 1}]\n{doc}" for i, doc in enumerate(context_docs)
    )
    return (
        f"You are a helpful assistant. Answer the question using ONLY the context "
        f"provided below. If the context does not contain the answer, say "
        f"'I don't know based on the available information.'\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        f"Answer:"
    )


# ── Workflow ──────────────────────────────────────────────────────────────────

@workflow(name="rag_pipeline")
def rag_pipeline(query: str, top_k: int = 3) -> dict:
    print(f"\n{'='*60}")
    print(f" RAG Pipeline — query: '{query}'")
    print(f"{'='*60}")

    docs    = retrieve_docs(query, top_k=top_k)
    ranked  = rerank_docs(docs, query=query)
    answer  = generate_answer(query, context_docs=ranked)

    scores  = evaluate_run(answer, question=query, context_docs=ranked)

    print(f"\n  Answer: {answer[:200]}...")
    print(f"\n  Scores:")
    for k, v in scores.items():
        if v is not None:
            print(f"    {k}: {v}")

    return {"answer": answer, "scores": scores, "docs_used": len(ranked)}


# ── Entry point ───────────────────────────────────────────────────────────────

QUERIES = [
    "What is TraceChain and how does it work?",
    "How do I configure TraceChain for production?",
    "What evaluation scores does TraceChain compute?",
    "How does replay work in TraceChain?",
]

if __name__ == "__main__":
    query = sys.argv[1] if len(sys.argv) > 1 else QUERIES[0]
    result = rag_pipeline(query)
    print(f"\nDone. Docs used: {result['docs_used']}")
    print("Open http://localhost:3000 to see the trace.")
