"""
Example 4: OpenTelemetry Export
================================
Demonstrates configure_otel() — TraceChain decorators emit properly-nested
OTEL spans that can be viewed in Jaeger, Grafana Tempo, or any OTLP backend.

Run with console exporter (no extra services needed):
    pip install 'tracechain[otel]'
    python examples/04_opentelemetry.py

Run with Jaeger (start Jaeger first):
    docker run -d --name jaeger -p 16686:16686 -p 4317:4317 jaegertracing/all-in-one
    OTEL_EXPORTER=otlp python examples/04_opentelemetry.py
    # then open http://localhost:16686

Span hierarchy emitted:
    workflow.qa_pipeline
      └─ step.retrieve_docs
      └─ step.generate_answer
           └─ llm.gpt_call   (gen_ai.* semantic conventions)
"""
import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(name)s  %(message)s",
    stream=sys.stdout,
)

from tracechain import workflow, step, observe_llm

# ── Configure OpenTelemetry before decorators run ─────────────────────────────

try:
    from tracechain import configure_otel

    exporter = os.getenv("OTEL_EXPORTER", "console")
    endpoint = os.getenv("OTEL_ENDPOINT", "http://localhost:4317")

    configure_otel(
        service_name="tracechain-example",
        exporter=exporter,
        endpoint=endpoint,
    )

    if exporter == "otlp":
        logging.info("OTEL → OTLP at %s  (view in Jaeger: http://localhost:16686)", endpoint)
    else:
        logging.info("OTEL → console  (set OTEL_EXPORTER=otlp to send to Jaeger)")

except ImportError:
    logging.warning(
        "opentelemetry-sdk not installed — install with: pip install 'tracechain[otel]'"
    )

# ── Steps ─────────────────────────────────────────────────────────────────────

DOCS = {
    "retrieval-augmented generation": [
        "RAG combines retrieval and generation for grounded answers.",
        "Vector databases store embeddings for semantic search.",
    ],
    "opentelemetry": [
        "OpenTelemetry is a CNCF observability framework.",
        "It defines traces, metrics, and logs with a vendor-neutral API.",
    ],
}


@step(name="retrieve_docs")
def retrieve_docs(query: str) -> list[str]:
    time.sleep(0.05)
    for topic, docs in DOCS.items():
        if topic in query.lower():
            return docs
    return ["No relevant documents found."]


@step(name="generate_answer")
def generate_answer(query: str, docs: list[str]) -> str:
    context = " ".join(docs)
    with observe_llm(
        "gpt_call",
        model="gpt-4o",
        provider="openai",
        prompt=f"Context: {context}\nQuestion: {query}",
    ) as obs:
        time.sleep(0.1)
        answer = f"Based on the retrieved context: {context[:80]}…"
        obs.record(response=answer, input_tokens=len(context.split()), output_tokens=20)
    return answer


# ── Workflow ──────────────────────────────────────────────────────────────────

@workflow(name="qa_pipeline")
def qa_pipeline(query: str) -> str:
    docs   = retrieve_docs(query)
    answer = generate_answer(query, docs)
    return answer


# ── Main ──────────────────────────────────────────────────────────────────────

QUERIES = [
    "What is retrieval-augmented generation?",
    "How does OpenTelemetry work?",
    "What are embeddings used for?",
]

if __name__ == "__main__":
    print("\n=== TraceChain Example 4: OpenTelemetry Export ===\n")
    for q in QUERIES:
        print(f"Q: {q}")
        answer = qa_pipeline(q)
        print(f"A: {answer[:100]}\n")

    print("Done.")
    if os.getenv("OTEL_EXPORTER") == "otlp":
        print("View traces at http://localhost:16686 → Service: tracechain-example")
    else:
        print("Tip: set OTEL_EXPORTER=otlp and start Jaeger to view in a real UI.")
