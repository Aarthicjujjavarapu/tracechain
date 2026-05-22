"""
observe_retrieval() — context manager for tracing RAG retrieval steps.

Usage
─────
With relevance scores:
    from tracechain import observe_retrieval

    with observe_retrieval("docs", query=query, k=5) as obs:
        docs, scores = vector_store.similarity_search_with_score(query, k=5)
        obs.record(docs, relevance_scores=scores)

Without scores:
    with observe_retrieval("knowledge_base", query=query) as obs:
        docs = vector_store.similarity_search(query)
        obs.record(docs)

Async:
    async with observe_retrieval("docs", query=query, k=3) as obs:
        docs, scores = await async_search(query, k=3)
        obs.record(docs, relevance_scores=scores)

How it integrates with the failure classifier
─────────────────────────────────────────────
The step is named "retrieve:<name>" which contains "retriev" — the classifier
picks this up automatically for RETRIEVAL_FAILURE detection on step errors.

When relevance_scores are provided, the mean score is posted as the run's
relevance_score evaluation. Scores below 0.3 trigger LOW_RELEVANCE_CONTEXT
classification, giving you automatic alerts when retrieval quality drops.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from .client import get_default_client, _safe_json
from .tracing import get_run_id, set_step_id, reset_step_id
from .otel import _otel_start_span, _otel_end_span


def _now_ms() -> int:
    return int(time.monotonic() * 1000)


# ── Public factory ────────────────────────────────────────────────────────────

def observe_retrieval(
    name: str = "",
    *,
    query: str,
    k: Optional[int] = None,
    client: Any = None,
) -> "_RetrievalObserver":
    """
    Return a context manager (sync or async) that traces a retrieval step.

    Args:
        name:   Label for this retrieval source (e.g. "docs", "knowledge_base").
                The step is named "retrieve:<name>" — contains "retriev" so the
                RETRIEVAL_FAILURE classifier detects it automatically.
        query:  The search query or embedding input text.
        k:      Expected number of results. Stored in step metadata.
        client: Override the default TraceChainClient.

    Inside the context call obs.record(docs, relevance_scores=...):
        docs:             Retrieved documents (list of strings, dicts, or objects).
        relevance_scores: Per-document similarity scores (0.0–1.0). When provided,
                          the mean score is posted as the run's relevance evaluation
                          so the LOW_RELEVANCE_CONTEXT classifier can fire.
    """
    return _RetrievalObserver(name=name, query=query, k=k, client=client)


# ── Internal context manager ──────────────────────────────────────────────────

class _RetrievalObserver:
    def __init__(
        self,
        *,
        name: str,
        query: str,
        k: Optional[int],
        client: Any,
    ) -> None:
        self._name    = name
        self._query   = query
        self._k       = k
        self._client_override = client

        self._docs:       list                  = []
        self._scores:     Optional[list[float]] = None
        self._error:      Optional[str]         = None
        self._start_ms:   int                   = 0

        self._tc:         Any           = None
        self._run_id:     Optional[str] = None
        self._step_id:    Optional[str] = None
        self._step_token: Any           = None
        self._span:       Any           = None
        self._otel_token: Any           = None

    def _step_name(self) -> str:
        return f"retrieve:{self._name}" if self._name else "retrieve"

    # ── shared enter/exit body ────────────────────────────────────────────────

    def _begin(self) -> "_RetrievalObserver":
        self._start_ms = _now_ms()
        self._tc       = self._client_override or get_default_client()
        self._run_id   = get_run_id()

        self._span, self._otel_token = _otel_start_span(
            f"retrieval.{self._name or 'default'}",
            {"tracechain.retrieval.query": self._query[:200]},
        )

        if self._run_id:
            meta: dict = {"tracechain.kind": "retrieval", "query": self._query[:500]}
            if self._k is not None:
                meta["k"] = self._k
            step_id = self._tc.create_step(
                run_id=self._run_id,
                step_name=self._step_name(),
                step_type="step",
                input_payload={"query": self._query, "k": self._k},
                metadata=meta,
            )
            self._step_id = step_id
            if step_id:
                self._step_token = set_step_id(step_id)

        return self

    def _end(self, exc: Optional[BaseException]) -> None:
        latency = _now_ms() - self._start_ms
        if exc is not None:
            self._error = str(exc)

        _otel_end_span(self._span, self._otel_token, error=exc)

        if self._run_id and self._step_id:
            if self._error:
                self._tc.fail_step(
                    run_id=self._run_id,
                    step_id=self._step_id,
                    error_message=self._error,
                )
            else:
                output: dict = {"result_count": len(self._docs)}
                # Cap stored docs to avoid huge payloads
                output["docs"] = _safe_json(self._docs[:5])
                if self._scores is not None:
                    output["relevance_scores"] = self._scores[:10]
                    output["avg_relevance"] = (
                        round(sum(self._scores) / len(self._scores), 4)
                        if self._scores else 0.0
                    )
                self._tc.complete_step(
                    run_id=self._run_id,
                    step_id=self._step_id,
                    output_payload=output,
                    duration_ms=latency,
                )

        # Post evaluation when relevance scores are available so the classifier
        # can detect LOW_RELEVANCE_CONTEXT on low-quality retrieval.
        if self._run_id and self._scores and not self._error:
            avg = sum(self._scores) / len(self._scores)
            self._tc.post_evaluation(self._run_id, {
                "relevance_score":    round(avg, 4),
                "groundedness_score": 0.5,
                "hallucination_risk": 0.5,
                "quality_score":      round(avg, 4),
            })

        if self._step_token is not None:
            reset_step_id(self._step_token)

    # ── public API ────────────────────────────────────────────────────────────

    def record(
        self,
        docs: list,
        relevance_scores: Optional[list[float]] = None,
    ) -> None:
        """
        Record retrieval results.

        Args:
            docs:             Retrieved documents.
            relevance_scores: Per-document similarity scores (0.0–1.0).
                              Scores are clamped to [0, 1] automatically.
        """
        self._docs = docs if isinstance(docs, list) else [docs]
        if relevance_scores is not None:
            self._scores = [max(0.0, min(1.0, float(s))) for s in relevance_scores]

    # ── sync context manager ──────────────────────────────────────────────────

    def __enter__(self) -> "_RetrievalObserver":
        return self._begin()

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._end(exc_val)
        return False

    # ── async context manager ─────────────────────────────────────────────────

    async def __aenter__(self) -> "_RetrievalObserver":
        return self._begin()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._end(exc_val)
        return False
