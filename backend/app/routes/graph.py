"""
Agent execution graph endpoint.

GET /v1/runs/{run_id}/graph  →  ReactFlow-compatible node/edge payload
GET /v1/runs/{run_id}/diagnostics  →  retry chains, latency, tokens, context warnings
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import SpanEvent, WorkflowRun, TraceStep, LLMCall

router = APIRouter(prefix="/v1/runs", tags=["graph"])


@router.get("/{run_id}/graph")
def get_run_graph(run_id: str, db: Session = Depends(get_db)) -> dict:
    spans = db.query(SpanEvent).filter(SpanEvent.run_id == run_id).all()

    # ── prefer span-based graph; fall back to legacy tables ──────────────────
    if not spans:
        return _build_graph_from_legacy(run_id, db)

    try:
        from tracechain.core.graph import ExecutionGraph, GraphNode
        from tracechain.core.events import SpanKind
    except ImportError:
        return _build_graph_without_sdk(spans)

    graph = ExecutionGraph(run_id=run_id, trace_id=spans[0].trace_id or run_id)

    for s in sorted(spans, key=lambda s: s.timestamp_ns or 0):
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
        raise HTTPException(status_code=404, detail="No span diagnostics available for this run")

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
            "run_id":         run_id,
            "retry_chains":   [c.to_dict() for c in retry_chains],
            "retry_summary":  RetryChainAnalyzer().summary(retry_chains),
            "latency":        latency.to_dict(),
            "tokens":         tokens.to_dict(),
            "context_window": ContextWindowAnalyzer().to_dict(ctx_warnings),
        }
    except ImportError:
        return {
            "run_id": run_id,
            "error":  "tracechain SDK not installed in backend environment",
            "spans":  len(span_dicts),
        }


# ── legacy graph builder (trace_steps + llm_calls) ────────────────────────────

def _build_graph_from_legacy(run_id: str, db: Session) -> dict:
    """Build a ReactFlow graph from the old-style tables when no SpanEvents exist."""
    run = db.query(WorkflowRun).filter(WorkflowRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    steps    = db.query(TraceStep).filter(TraceStep.run_id == run_id).order_by(TraceStep.started_at).all()
    run_llms = db.query(LLMCall).filter(LLMCall.run_id == run_id, LLMCall.step_id.is_(None)).all()

    nodes: list[dict] = []
    edges: list[dict] = []

    # workflow root node
    wf_id = f"wf-{run_id}"
    nodes.append({
        "id":   wf_id,
        "type": "workflow",
        "position": {"x": 0, "y": 0},
        "data": {
            "label":       run.workflow_name,
            "kind":        "workflow",
            "status":      _run_status(run.status),
            "duration_ms": run.duration_ms,
            "attributes":  {},
            "retry_count": 0,
        },
    })

    step_x_positions: dict[str, int] = {}
    x_step = 0

    for step in steps:
        s_id   = step.id
        status = _run_status(step.status)
        nodes.append({
            "id":   s_id,
            "type": "step",
            "position": {"x": 0, "y": 0},
            "data": {
                "label":       step.step_name,
                "kind":        "step",
                "status":      status,
                "duration_ms": step.duration_ms,
                "retry_count": step.retry_count or 0,
                "attributes":  {"error.message": step.error_message} if step.error_message else {},
            },
        })
        edges.append({"id": f"{wf_id}-{s_id}", "source": wf_id, "target": s_id, "type": "default"})
        step_x_positions[s_id] = x_step

        llms = db.query(LLMCall).filter(LLMCall.step_id == step.id).all()
        x_llm = x_step
        for llm in llms:
            nodes.append(_llm_node(llm))
            edges.append({"id": f"{s_id}-{llm.id}", "source": s_id, "target": llm.id, "type": "default"})
            x_step += 1
            x_llm = x_step

        x_step = max(x_step, x_llm) + 1

    for llm in run_llms:
        nodes.append(_llm_node(llm))
        edges.append({"id": f"{wf_id}-{llm.id}", "source": wf_id, "target": llm.id, "type": "default"})

    _apply_layout(nodes, edges)
    return {"nodes": nodes, "edges": edges}


def _llm_node(llm: LLMCall) -> dict:
    return {
        "id":   llm.id,
        "type": "llm",
        "position": {"x": 0, "y": 0},
        "data": {
            "label":         llm.model,
            "kind":          "llm",
            "status":        "error" if llm.status and llm.status.value == "failed" else "ok",
            "duration_ms":   llm.latency_ms,
            "input_tokens":  llm.input_tokens,
            "output_tokens": llm.output_tokens,
            "cost_usd":      llm.estimated_cost,
            "retry_count":   0,
            "attributes":    {},
        },
    }


def _run_status(status) -> str:
    if status is None:
        return "ok"
    v = status.value if hasattr(status, "value") else str(status)
    return "error" if v == "failed" else "ok" if v == "success" else v


def _apply_layout(nodes: list[dict], edges: list[dict]) -> None:
    """Simple top-down hierarchical layout."""
    # Build parent→children map
    children: dict[str, list[str]] = {}
    node_ids = {n["id"] for n in nodes}
    for e in edges:
        if e["source"] in node_ids and e["target"] in node_ids:
            children.setdefault(e["source"], []).append(e["target"])

    visited: set[str] = set()
    x_counter = [0]
    X_GAP, Y_GAP = 260, 160

    def place(node_id: str, depth: int) -> int:
        if node_id in visited:
            return x_counter[0]
        visited.add(node_id)
        kids = children.get(node_id, [])
        if not kids:
            x = x_counter[0]
            x_counter[0] += 1
        else:
            start = x_counter[0]
            for kid in kids:
                place(kid, depth + 1)
            x = (start + x_counter[0] - 1) / 2
        node_map[node_id]["position"] = {"x": int(x * X_GAP), "y": depth * Y_GAP}
        return int(x)

    node_map = {n["id"]: n for n in nodes}
    roots = [n["id"] for n in nodes if not any(e["target"] == n["id"] for e in edges)]
    for root in roots:
        place(root, 0)

    # place anything not yet visited (disconnected nodes)
    for n in nodes:
        if n["id"] not in visited:
            n["position"] = {"x": x_counter[0] * X_GAP, "y": 0}
            x_counter[0] += 1


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
                "label":       s.name,
                "status":      s.status or "ok",
                "kind":        s.kind,
                "attributes":  {},
                "retry_count": 0,
            },
        })
        if s.parent_span_id:
            edges.append({
                "id":     f"{s.parent_span_id}-{s.span_id}",
                "source": s.parent_span_id,
                "target": s.span_id,
                "type":   "default",
            })
    _apply_layout(nodes, edges)
    return {"nodes": nodes, "edges": edges}
