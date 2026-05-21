"""
Agent execution graph endpoint.

GET /v1/runs/{run_id}/graph  →  ReactFlow-compatible node/edge payload
GET /v1/runs/{run_id}/diagnostics  →  retry chains, latency, tokens, context warnings
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SpanEvent

router = APIRouter(prefix="/v1/runs", tags=["graph"])


@router.get("/{run_id}/graph")
def get_run_graph(run_id: str, db: Session = Depends(get_db)) -> dict:
    spans = db.query(SpanEvent).filter(SpanEvent.run_id == run_id).all()
    if not spans:
        raise HTTPException(status_code=404, detail=f"No spans found for run {run_id}")

    # lazy import to avoid circular deps if sdk isn't installed in backend venv
    try:
        from tracechain.core.graph import ExecutionGraph, GraphNode
        from tracechain.core.events import SpanKind
    except ImportError:
        return _build_graph_without_sdk(spans)

    graph = ExecutionGraph(run_id=run_id, trace_id=spans[0].trace_id or run_id)

    # sort by timestamp so parents arrive before children
    sorted_spans = sorted(spans, key=lambda s: s.timestamp_ns or 0)
    for s in sorted_spans:
        try:
            kind = SpanKind(s.kind)
        except ValueError:
            kind = SpanKind.STEP

        node = GraphNode(
            span_id=s.span_id,
            name=s.name,
            kind=kind,
            start_ns=s.timestamp_ns or 0,
            end_ns=(s.timestamp_ns or 0) + (s.duration_ns or 0) if s.duration_ns else None,
            status=s.status or "ok",
            parent_id=s.parent_span_id,
            attributes=s.attributes or {},
            retry_count=s.attributes.get("tracechain.retry.attempt", 0) if s.attributes else 0,
        )
        graph.add_node(node)

    return graph.to_react_flow()


@router.get("/{run_id}/diagnostics")
def get_run_diagnostics(run_id: str, db: Session = Depends(get_db)) -> dict:
    spans = db.query(SpanEvent).filter(SpanEvent.run_id == run_id).all()
    if not spans:
        raise HTTPException(status_code=404, detail=f"No spans found for run {run_id}")

    span_dicts = [_span_to_dict(s) for s in spans]

    try:
        from tracechain.diagnostics import (
            RetryChainAnalyzer, LatencyAnalyzer,
            TokenPropagator, ContextWindowAnalyzer,
        )
        retry_chains = RetryChainAnalyzer().analyze(span_dicts)
        latency      = LatencyAnalyzer().analyze(span_dicts)
        tokens       = TokenPropagator().analyze(span_dicts)
        ctx_warnings = ContextWindowAnalyzer().analyze(span_dicts)

        return {
            "run_id":          run_id,
            "retry_chains":    [c.to_dict() for c in retry_chains],
            "retry_summary":   RetryChainAnalyzer().summary(retry_chains),
            "latency":         latency.to_dict(),
            "tokens":          tokens.to_dict(),
            "context_window":  ContextWindowAnalyzer().to_dict(ctx_warnings),
        }
    except ImportError:
        return {
            "run_id":  run_id,
            "error":   "tracechain SDK not installed in backend environment",
            "spans":   len(span_dicts),
        }


# ── helpers ────────────────────────────────────────────────────────────────────

def _span_to_dict(s: SpanEvent) -> dict:
    return {
        "span_id":        s.span_id,
        "trace_id":       s.trace_id,
        "parent_span_id": s.parent_span_id,
        "run_id":         s.run_id,
        "name":           s.name,
        "kind":           s.kind,
        "event_type":     s.event_type,
        "status":         s.status,
        "error_message":  s.error_message,
        "attributes":     s.attributes or {},
        "timestamp_ns":   s.timestamp_ns,
        "duration_ns":    s.duration_ns,
    }


def _build_graph_without_sdk(spans) -> dict:
    """Fallback graph builder when SDK isn't importable in the backend venv."""
    nodes = []
    edges = []

    for s in sorted(spans, key=lambda x: x.timestamp_ns or 0):
        nodes.append({
            "id":   s.span_id,
            "type": s.kind or "step",
            "position": {"x": 0, "y": 0},
            "data": {
                "label":  s.name,
                "status": s.status or "ok",
                "kind":   s.kind,
            },
        })
        if s.parent_span_id:
            edges.append({
                "id":     f"{s.parent_span_id}-{s.span_id}",
                "source": s.parent_span_id,
                "target": s.span_id,
                "type":   "default",
            })

    return {"nodes": nodes, "edges": edges}
