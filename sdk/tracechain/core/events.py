"""
Core event schema — the single wire format for everything TraceChain records.

All SDK instrumentation produces TraceEvents. The exporter layer
(HTTP, SQLite, OTel) consumes them. Nothing else crosses the boundary.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    RUN_START        = "run.start"
    RUN_END          = "run.end"
    RUN_ERROR        = "run.error"
    SPAN_START       = "span.start"
    SPAN_END         = "span.end"
    SPAN_ERROR       = "span.error"
    LLM_START        = "llm.start"
    LLM_END          = "llm.end"
    LLM_CHUNK        = "llm.chunk"        # streaming chunk
    TOOL_START       = "tool.start"
    TOOL_END         = "tool.end"
    RETRIEVAL_START  = "retrieval.start"
    RETRIEVAL_END    = "retrieval.end"
    RETRY_ATTEMPT    = "retry.attempt"
    RETRY_EXHAUSTED  = "retry.exhausted"
    EVAL_SCORE       = "eval.score"


class SpanKind(str, Enum):
    WORKFLOW  = "workflow"
    STEP      = "step"
    LLM       = "llm"
    TOOL      = "tool"
    RETRIEVER = "retriever"
    RERANKER  = "reranker"
    MEMORY    = "memory"
    VALIDATOR = "validator"
    AGENT     = "agent"
    EMBEDDING = "embedding"


@dataclass
class TraceEvent:
    """
    Immutable event record. One TraceEvent per state transition in the workflow.

    Design constraints:
    - Must be serialisable to JSON with no external deps.
    - timestamp_ns uses monotonic wall-clock (time.time_ns) for cross-process ordering.
    - span_id is local; trace_id groups all spans in one workflow invocation.
    """
    event_type:     EventType
    trace_id:       str
    span_id:        str
    name:           str
    kind:           SpanKind
    timestamp_ns:   int                    = field(default_factory=time.time_ns)
    parent_span_id: Optional[str]          = None
    run_id:         Optional[str]          = None
    attributes:     dict[str, Any]         = field(default_factory=dict)
    status:         str                    = "unset"   # unset | ok | error
    error_message:  Optional[str]          = None
    duration_ns:    Optional[int]          = None

    @staticmethod
    def new_id() -> str:
        return uuid.uuid4().hex

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type":     self.event_type.value,
            "trace_id":       self.trace_id,
            "span_id":        self.span_id,
            "name":           self.name,
            "kind":           self.kind.value,
            "timestamp_ns":   self.timestamp_ns,
            "parent_span_id": self.parent_span_id,
            "run_id":         self.run_id,
            "attributes":     self.attributes,
            "status":         self.status,
            "error_message":  self.error_message,
            "duration_ns":    self.duration_ns,
        }

    @property
    def duration_ms(self) -> Optional[float]:
        if self.duration_ns is None:
            return None
        return self.duration_ns / 1_000_000


@dataclass
class LLMAttributes:
    """
    Typed attribute bag for LLM spans.
    Maps to OpenTelemetry GenAI semantic conventions where possible.
    """
    model:                   str
    provider:                str
    input_tokens:            Optional[int]   = None
    output_tokens:           Optional[int]   = None
    total_tokens:            Optional[int]   = None
    cost_usd:                Optional[float] = None
    temperature:             Optional[float] = None
    max_tokens:              Optional[int]   = None
    is_stream:               bool            = False
    ttft_ms:                 Optional[float] = None   # time-to-first-token
    prompt_tokens_estimated: bool            = False
    finish_reason:           Optional[str]   = None
    tool_calls_count:        Optional[int]   = None

    def to_attributes(self) -> dict[str, Any]:
        """Merge OTel GenAI semconv attrs with tracechain-specific attrs."""
        attrs: dict[str, Any] = {
            "gen_ai.system":             self.provider,
            "gen_ai.request.model":      self.model,
            "tracechain.llm.is_stream":  self.is_stream,
            "tracechain.llm.tokens_estimated": self.prompt_tokens_estimated,
        }
        if self.input_tokens is not None:
            attrs["gen_ai.usage.input_tokens"]  = self.input_tokens
        if self.output_tokens is not None:
            attrs["gen_ai.usage.output_tokens"] = self.output_tokens
        if self.total_tokens is not None:
            attrs["gen_ai.usage.total_tokens"]  = self.total_tokens
        if self.cost_usd is not None:
            attrs["tracechain.llm.cost_usd"]    = self.cost_usd
        if self.temperature is not None:
            attrs["gen_ai.request.temperature"] = self.temperature
        if self.max_tokens is not None:
            attrs["gen_ai.request.max_tokens"]  = self.max_tokens
        if self.ttft_ms is not None:
            attrs["tracechain.llm.ttft_ms"]     = self.ttft_ms
        if self.finish_reason is not None:
            attrs["gen_ai.response.finish_reasons"] = [self.finish_reason]
        if self.tool_calls_count is not None:
            attrs["tracechain.llm.tool_calls_count"] = self.tool_calls_count
        return attrs


@dataclass
class RetryAttributes:
    """Captured on every retry attempt for retry-chain diagnostics."""
    attempt:       int
    max_attempts:  int
    delay_ms:      float
    error_type:    str
    error_message: str
    span_id:       str   # the span being retried

    def to_attributes(self) -> dict[str, Any]:
        return {
            "tracechain.retry.attempt":       self.attempt,
            "tracechain.retry.max_attempts":  self.max_attempts,
            "tracechain.retry.delay_ms":      self.delay_ms,
            "tracechain.retry.error_type":    self.error_type,
            "tracechain.retry.error_message": self.error_message,
            "tracechain.retry.span_id":       self.span_id,
        }


@dataclass
class RetrievalAttributes:
    """Diagnostics for retrieval steps — enables retrieval quality analysis."""
    query:           str
    num_results:     int
    top_score:       Optional[float] = None
    avg_score:       Optional[float] = None
    source:          Optional[str]   = None    # vector DB name
    collection:      Optional[str]   = None
    reranked:        bool            = False
    results_dropped: int             = 0       # filtered below threshold

    def to_attributes(self) -> dict[str, Any]:
        attrs: dict[str, Any] = {
            "tracechain.retrieval.num_results":     self.num_results,
            "tracechain.retrieval.reranked":        self.reranked,
            "tracechain.retrieval.results_dropped": self.results_dropped,
        }
        if self.top_score is not None:
            attrs["tracechain.retrieval.top_score"] = self.top_score
        if self.avg_score is not None:
            attrs["tracechain.retrieval.avg_score"] = self.avg_score
        if self.source:
            attrs["tracechain.retrieval.source"] = self.source
        if self.collection:
            attrs["tracechain.retrieval.collection"] = self.collection
        return attrs
