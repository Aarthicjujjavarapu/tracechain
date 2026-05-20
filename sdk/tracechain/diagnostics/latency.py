"""
Latency bottleneck diagnostics.

Answers: which spans consumed the most wall-clock time in a run,
what percentage of total run time each span accounts for,
and whether any span exceeded a configurable threshold.

Critical insight: the "bottleneck" in an agent graph is not always the
slowest absolute span — it's the span on the critical path (longest chain
of sequential dependencies). This analyzer computes both.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BottleneckSpan:
    span_id:         str
    name:            str
    kind:            str
    duration_ms:     float
    pct_of_run:      float      # 0–100
    is_critical_path: bool
    parent_id:       Optional[str]
    depth:           int

    def to_dict(self) -> dict:
        return {
            "span_id":           self.span_id,
            "name":              self.name,
            "kind":              self.kind,
            "duration_ms":       round(self.duration_ms, 2),
            "pct_of_run":        round(self.pct_of_run, 1),
            "is_critical_path":  self.is_critical_path,
            "parent_id":         self.parent_id,
            "depth":             self.depth,
        }


@dataclass
class LatencyReport:
    total_run_ms:    float
    bottlenecks:     list[BottleneckSpan]    # sorted by duration desc
    critical_path:   list[str]              # span_ids forming the longest path
    p50_ms:          float
    p95_ms:          float
    p99_ms:          float
    slow_threshold_ms: float
    slow_spans:      list[str]              # span_ids exceeding threshold

    def to_dict(self) -> dict:
        return {
            "total_run_ms":      round(self.total_run_ms, 2),
            "p50_ms":            round(self.p50_ms, 2),
            "p95_ms":            round(self.p95_ms, 2),
            "p99_ms":            round(self.p99_ms, 2),
            "slow_threshold_ms": self.slow_threshold_ms,
            "slow_spans":        self.slow_spans,
            "critical_path":     self.critical_path,
            "bottlenecks":       [b.to_dict() for b in self.bottlenecks],
        }


class LatencyAnalyzer:
    """
    Computes latency diagnostics from a flat list of completed span dicts.

    Algorithm:
    1. Build a parent→children adjacency map.
    2. Find the root span (no parent) — its duration is total_run_ms.
    3. For each span, compute pct_of_run relative to root duration.
    4. Critical path = DFS from root, always following the longest-duration child.
    5. Percentiles over all leaf-level span durations.
    """

    DEFAULT_SLOW_THRESHOLD_MS = 2_000.0

    def analyze(
        self,
        spans: list[dict],
        slow_threshold_ms: float = DEFAULT_SLOW_THRESHOLD_MS,
    ) -> LatencyReport:
        if not spans:
            return LatencyReport(
                total_run_ms=0, bottlenecks=[], critical_path=[],
                p50_ms=0, p95_ms=0, p99_ms=0,
                slow_threshold_ms=slow_threshold_ms, slow_spans=[],
            )

        # index spans
        by_id:    dict[str, dict]       = {s["span_id"]: s for s in spans}
        children: dict[str, list[str]]  = {s["span_id"]: [] for s in spans}
        root_id:  Optional[str]         = None

        for span in spans:
            pid = span.get("parent_span_id")
            if pid and pid in children:
                children[pid].append(span["span_id"])
            elif pid is None or pid not in by_id:
                root_id = span["span_id"]

        total_run_ms = self._duration_ms(by_id.get(root_id, {})) if root_id else 1.0
        if total_run_ms == 0:
            total_run_ms = 1.0

        # build BottleneckSpan list
        bottlenecks: list[BottleneckSpan] = []
        depths = self._compute_depths(root_id, children)

        for span in spans:
            dur = self._duration_ms(span)
            if dur is None:
                continue
            bottlenecks.append(BottleneckSpan(
                span_id=span["span_id"],
                name=span.get("name", ""),
                kind=span.get("kind", "step"),
                duration_ms=dur,
                pct_of_run=dur / total_run_ms * 100,
                is_critical_path=False,   # set below
                parent_id=span.get("parent_span_id"),
                depth=depths.get(span["span_id"], 0),
            ))

        bottlenecks.sort(key=lambda b: b.duration_ms, reverse=True)

        # critical path
        critical_path = self._find_critical_path(root_id, children, by_id) if root_id else []
        critical_set  = set(critical_path)
        for b in bottlenecks:
            if b.span_id in critical_set:
                b.is_critical_path = True

        # percentiles (over all spans' durations)
        durations = sorted(b.duration_ms for b in bottlenecks)
        slow_spans = [b.span_id for b in bottlenecks if b.duration_ms >= slow_threshold_ms]

        return LatencyReport(
            total_run_ms=total_run_ms,
            bottlenecks=bottlenecks,
            critical_path=critical_path,
            p50_ms=self._percentile(durations, 50),
            p95_ms=self._percentile(durations, 95),
            p99_ms=self._percentile(durations, 99),
            slow_threshold_ms=slow_threshold_ms,
            slow_spans=slow_spans,
        )

    # ── helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _duration_ms(span: dict) -> Optional[float]:
        dur_ns = span.get("duration_ns")
        if dur_ns is not None:
            return dur_ns / 1_000_000
        start = span.get("start_ns") or span.get("timestamp_ns")
        end   = span.get("end_ns")
        if start and end:
            return (end - start) / 1_000_000
        return None

    @staticmethod
    def _compute_depths(root_id: Optional[str], children: dict[str, list[str]]) -> dict[str, int]:
        depths: dict[str, int] = {}
        stack = [(root_id, 0)] if root_id else []
        while stack:
            node_id, depth = stack.pop()
            depths[node_id] = depth
            for child_id in children.get(node_id, []):
                stack.append((child_id, depth + 1))
        return depths

    @staticmethod
    def _find_critical_path(
        root_id:  str,
        children: dict[str, list[str]],
        by_id:    dict[str, dict],
    ) -> list[str]:
        """DFS always choosing the longest-duration child."""
        path: list[str] = []
        node_id = root_id
        visited: set[str] = set()
        while node_id and node_id not in visited:
            visited.add(node_id)
            path.append(node_id)
            kids = children.get(node_id, [])
            if not kids:
                break
            # pick child with longest duration
            def _dur(sid: str) -> float:
                span = by_id.get(sid, {})
                dur_ns = span.get("duration_ns")
                if dur_ns:
                    return dur_ns
                start = span.get("timestamp_ns", 0)
                end   = span.get("end_ns", start)
                return end - start
            node_id = max(kids, key=_dur)
        return path

    @staticmethod
    def _percentile(sorted_vals: list[float], pct: int) -> float:
        if not sorted_vals:
            return 0.0
        idx = int(len(sorted_vals) * pct / 100)
        idx = min(idx, len(sorted_vals) - 1)
        return sorted_vals[idx]
