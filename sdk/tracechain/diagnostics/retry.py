"""
Retry chain diagnostics.

Answers: which steps retried, how many times, what errors caused them,
and whether retries ultimately succeeded or exhausted.

This is a pure data-analysis module — it takes a list of TraceEvents
and produces structured diagnostics. No I/O, no side effects.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RetryEvent:
    attempt:       int
    delay_ms:      float
    error_type:    str
    error_message: str
    timestamp_ns:  int


@dataclass
class RetryChain:
    span_id:       str
    span_name:     str
    max_attempts:  int
    attempts:      list[RetryEvent] = field(default_factory=list)
    exhausted:     bool             = False
    final_status:  str              = "unknown"   # ok | error | exhausted

    @property
    def total_delay_ms(self) -> float:
        return sum(e.delay_ms for e in self.attempts)

    @property
    def attempt_count(self) -> int:
        return len(self.attempts)

    @property
    def unique_error_types(self) -> list[str]:
        return list(dict.fromkeys(e.error_type for e in self.attempts))

    def to_dict(self) -> dict:
        return {
            "span_id":          self.span_id,
            "span_name":        self.span_name,
            "max_attempts":     self.max_attempts,
            "attempt_count":    self.attempt_count,
            "exhausted":        self.exhausted,
            "final_status":     self.final_status,
            "total_delay_ms":   self.total_delay_ms,
            "unique_errors":    self.unique_error_types,
            "attempts": [
                {
                    "attempt":       e.attempt,
                    "delay_ms":      e.delay_ms,
                    "error_type":    e.error_type,
                    "error_message": e.error_message,
                    "timestamp_ns":  e.timestamp_ns,
                }
                for e in self.attempts
            ],
        }


class RetryChainAnalyzer:
    """
    Builds retry chains from a flat list of TraceEvent dicts.

    Call `analyze(events)` once you have the full run's events;
    returns a list of RetryChain objects sorted by attempt count desc.

    Algorithm:
    1. Scan for retry.attempt events, group by span_id.
    2. Scan for retry.exhausted events, mark chains as exhausted.
    3. Join span start/end events to get final status.
    """

    def analyze(self, events: list[dict]) -> list[RetryChain]:
        chains: dict[str, RetryChain] = {}

        for evt in events:
            etype = evt.get("event_type", "")
            attrs = evt.get("attributes", {})

            if etype == "retry.attempt":
                span_id = attrs.get("tracechain.retry.span_id", evt["span_id"])
                if span_id not in chains:
                    chains[span_id] = RetryChain(
                        span_id=span_id,
                        span_name=evt.get("name", span_id),
                        max_attempts=attrs.get("tracechain.retry.max_attempts", 0),
                    )
                chains[span_id].attempts.append(RetryEvent(
                    attempt=attrs.get("tracechain.retry.attempt", 0),
                    delay_ms=attrs.get("tracechain.retry.delay_ms", 0),
                    error_type=attrs.get("tracechain.retry.error_type", "unknown"),
                    error_message=attrs.get("tracechain.retry.error_message", ""),
                    timestamp_ns=evt.get("timestamp_ns", 0),
                ))

            elif etype == "retry.exhausted":
                span_id = attrs.get("tracechain.retry.span_id", evt["span_id"])
                if span_id in chains:
                    chains[span_id].exhausted      = True
                    chains[span_id].final_status   = "exhausted"

            elif etype == "span.end":
                span_id = evt.get("span_id", "")
                if span_id in chains and chains[span_id].final_status == "unknown":
                    chains[span_id].final_status = evt.get("status", "ok")

        result = sorted(chains.values(), key=lambda c: c.attempt_count, reverse=True)
        return result

    def summary(self, chains: list[RetryChain]) -> dict:
        if not chains:
            return {"total_chains": 0, "total_attempts": 0, "exhausted": 0}
        return {
            "total_chains":        len(chains),
            "total_attempts":      sum(c.attempt_count for c in chains),
            "exhausted":           sum(1 for c in chains if c.exhausted),
            "total_delay_ms":      sum(c.total_delay_ms for c in chains),
            "most_retried_span":   chains[0].span_name if chains else None,
            "unique_error_types":  list({e for c in chains for e in c.unique_error_types}),
        }
