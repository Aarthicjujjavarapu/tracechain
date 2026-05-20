"""
Agent execution graph builder.

Constructs a DAG from TraceEvents as they arrive, then serialises
to a ReactFlow-compatible payload for the dashboard.

Node layout algorithm: hierarchical top-down grouping by depth,
siblings spread horizontally. Deterministic — same events always
produce the same layout.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .events import SpanKind


# ── node / edge data models ────────────────────────────────────────────────────

@dataclass
class GraphNode:
    span_id:        str
    name:           str
    kind:           SpanKind
    start_ns:       int
    end_ns:         Optional[int]  = None
    status:         str            = "running"   # running | ok | error | retrying
    parent_id:      Optional[str]  = None
    attributes:     dict           = field(default_factory=dict)
    retry_count:    int            = 0

    @property
    def duration_ms(self) -> Optional[float]:
        if self.end_ns is None:
            return None
        return (self.end_ns - self.start_ns) / 1_000_000

    @property
    def input_tokens(self) -> Optional[int]:
        return self.attributes.get("gen_ai.usage.input_tokens")

    @property
    def output_tokens(self) -> Optional[int]:
        return self.attributes.get("gen_ai.usage.output_tokens")

    @property
    def cost_usd(self) -> Optional[float]:
        return self.attributes.get("tracechain.llm.cost_usd")

    def to_react_flow_node(self, position: dict) -> dict:
        return {
            "id":       self.span_id,
            "type":     self.kind.value,
            "position": position,
            "data": {
                "label":        self.name,
                "status":       self.status,
                "duration_ms":  self.duration_ms,
                "input_tokens": self.input_tokens,
                "output_tokens":self.output_tokens,
                "cost_usd":     self.cost_usd,
                "retry_count":  self.retry_count,
                "kind":         self.kind.value,
                "attributes":   self.attributes,
            },
        }


@dataclass
class GraphEdge:
    source: str
    target: str
    kind:   str = "default"   # default | retry | tool_call | retrieval | error


# ── graph ─────────────────────────────────────────────────────────────────────

class ExecutionGraph:
    """
    Incrementally built as events arrive. Thread-safe enough for
    single-process use (the buffer serialises writes).
    """

    def __init__(self, run_id: str, trace_id: str) -> None:
        self.run_id   = run_id
        self.trace_id = trace_id
        self.nodes:   dict[str, GraphNode] = {}
        self.edges:   list[GraphEdge]      = []
        self.root_id: Optional[str]        = None

    def add_node(self, node: GraphNode) -> None:
        self.nodes[node.span_id] = node
        if node.parent_id is None:
            self.root_id = node.span_id
        elif node.parent_id in self.nodes:
            self.edges.append(GraphEdge(
                source=node.parent_id,
                target=node.span_id,
                kind=self._edge_kind(node.kind),
            ))

    def update_node(
        self,
        span_id:       str,
        status:        Optional[str]   = None,
        end_ns:        Optional[int]   = None,
        attributes:    Optional[dict]  = None,
        retry_count:   Optional[int]   = None,
        error_message: Optional[str]   = None,
    ) -> None:
        node = self.nodes.get(span_id)
        if node is None:
            return
        if status is not None:
            node.status = status
        if end_ns is not None:
            node.end_ns = end_ns
        if attributes:
            node.attributes.update(attributes)
        if retry_count is not None:
            node.retry_count = retry_count
        if error_message is not None:
            node.attributes["error.message"] = error_message

    def to_react_flow(self) -> dict:
        depths    = self._compute_depths()
        positions = self._layout(depths)
        return {
            "run_id":   self.run_id,
            "trace_id": self.trace_id,
            "nodes": [
                n.to_react_flow_node(positions.get(n.span_id, {"x": 0, "y": 0}))
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "id":     f"{e.source}-{e.target}",
                    "source": e.source,
                    "target": e.target,
                    "type":   e.kind,
                }
                for e in self.edges
            ],
        }

    def to_summary(self) -> dict:
        """Lightweight summary used for the run list view."""
        total_cost   = sum(n.cost_usd or 0 for n in self.nodes.values())
        total_tokens = sum((n.input_tokens or 0) + (n.output_tokens or 0) for n in self.nodes.values())
        error_nodes  = [n.span_id for n in self.nodes.values() if n.status == "error"]
        retry_nodes  = [n.span_id for n in self.nodes.values() if n.retry_count > 0]
        return {
            "node_count":   len(self.nodes),
            "edge_count":   len(self.edges),
            "total_cost":   round(total_cost, 6),
            "total_tokens": total_tokens,
            "error_count":  len(error_nodes),
            "retry_count":  sum(n.retry_count for n in self.nodes.values()),
            "has_errors":   len(error_nodes) > 0,
        }

    # ── internal helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _edge_kind(kind: SpanKind) -> str:
        return {
            SpanKind.TOOL:      "tool_call",
            SpanKind.RETRIEVER: "retrieval",
            SpanKind.RERANKER:  "retrieval",
        }.get(kind, "default")

    def _compute_depths(self) -> dict[str, int]:
        depths: dict[str, int] = {}
        visited: set[str] = set()

        def dfs(node_id: str, depth: int) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            depths[node_id] = depth
            for edge in self.edges:
                if edge.source == node_id:
                    dfs(edge.target, depth + 1)

        if self.root_id:
            dfs(self.root_id, 0)
        # orphaned nodes (parent not yet arrived) get depth 0
        for node_id in self.nodes:
            if node_id not in depths:
                depths[node_id] = 0
        return depths

    def _layout(self, depths: dict[str, int]) -> dict[str, dict]:
        by_depth: dict[int, list[str]] = defaultdict(list)
        for span_id, depth in depths.items():
            by_depth[depth].append(span_id)

        x_gap, y_gap = 240, 130
        positions: dict[str, dict] = {}
        for depth, ids in sorted(by_depth.items()):
            count = len(ids)
            for i, span_id in enumerate(ids):
                positions[span_id] = {
                    "x": (i - (count - 1) / 2) * x_gap,
                    "y": depth * y_gap,
                }
        return positions
