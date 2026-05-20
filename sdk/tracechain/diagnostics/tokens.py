"""
Token usage propagation and cost attribution.

Answers: total tokens and cost per run, per step, per model, and per provider.
Detects when token usage is anomalously high (potential prompt injection,
context bloat, or runaway agent loops).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# Cost per 1M tokens (input, output) — updated as of mid-2025
# These are fallbacks only; prefer using server-side cost data when available.
_COST_PER_1M: dict[str, tuple[float, float]] = {
    "gpt-4o":            (2.50,  10.00),
    "gpt-4o-mini":       (0.15,   0.60),
    "gpt-4-turbo":       (10.00, 30.00),
    "gpt-4":             (30.00, 60.00),
    "gpt-3.5-turbo":     (0.50,   1.50),
    "claude-3-5-sonnet": (3.00,  15.00),
    "claude-3-5-haiku":  (0.80,   4.00),
    "claude-3-opus":     (15.00, 75.00),
    "claude-sonnet-4":   (3.00,  15.00),
    "claude-haiku-4":    (0.80,   4.00),
    "gemini-1.5-pro":    (1.25,   5.00),
    "gemini-1.5-flash":  (0.075,  0.30),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> Optional[float]:
    """Look up cost for a model; return None if model is unknown."""
    # normalise: strip version suffixes like -20240229
    key = model.lower().split(":")[0]
    for pattern, (in_rate, out_rate) in _COST_PER_1M.items():
        if key.startswith(pattern):
            return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000
    return None


@dataclass
class ModelUsage:
    model:         str
    provider:      str
    call_count:    int   = 0
    input_tokens:  int   = 0
    output_tokens: int   = 0
    cost_usd:      float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict:
        return {
            "model":         self.model,
            "provider":      self.provider,
            "call_count":    self.call_count,
            "input_tokens":  self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens":  self.total_tokens,
            "cost_usd":      round(self.cost_usd, 6),
        }


@dataclass
class TokenReport:
    total_input_tokens:  int
    total_output_tokens: int
    total_tokens:        int
    total_cost_usd:      float
    by_model:            list[ModelUsage]
    anomalies:           list[str]         # human-readable warnings

    def to_dict(self) -> dict:
        return {
            "total_input_tokens":  self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens":        self.total_tokens,
            "total_cost_usd":      round(self.total_cost_usd, 6),
            "by_model":            [m.to_dict() for m in self.by_model],
            "anomalies":           self.anomalies,
        }


class TokenPropagator:
    """
    Aggregates token usage from a flat list of completed span dicts.

    Anomaly detection thresholds (configurable):
    - high_token_warning: warn if any single LLM call exceeds this many tokens
    - high_cost_warning: warn if total cost exceeds this USD amount
    """

    HIGH_TOKEN_WARNING = 50_000
    HIGH_COST_WARNING  = 1.00   # USD

    def analyze(self, spans: list[dict]) -> TokenReport:
        by_model: dict[str, ModelUsage] = {}
        anomalies: list[str] = []

        for span in spans:
            attrs = span.get("attributes", {})
            model    = attrs.get("gen_ai.request.model")
            provider = attrs.get("gen_ai.system", "unknown")
            if not model:
                continue

            in_tok  = attrs.get("gen_ai.usage.input_tokens",  0) or 0
            out_tok = attrs.get("gen_ai.usage.output_tokens", 0) or 0
            cost    = attrs.get("tracechain.llm.cost_usd")

            if cost is None:
                cost = estimate_cost_usd(model, in_tok, out_tok) or 0.0

            key = f"{provider}/{model}"
            if key not in by_model:
                by_model[key] = ModelUsage(model=model, provider=provider)

            usage = by_model[key]
            usage.call_count    += 1
            usage.input_tokens  += in_tok
            usage.output_tokens += out_tok
            usage.cost_usd      += cost

            call_total = in_tok + out_tok
            if call_total > self.HIGH_TOKEN_WARNING:
                anomalies.append(
                    f"High token usage in span '{span.get('name', span['span_id'])}': "
                    f"{call_total:,} tokens (threshold: {self.HIGH_TOKEN_WARNING:,})"
                )

        total_input  = sum(m.input_tokens  for m in by_model.values())
        total_output = sum(m.output_tokens for m in by_model.values())
        total_cost   = sum(m.cost_usd      for m in by_model.values())

        if total_cost > self.HIGH_COST_WARNING:
            anomalies.append(
                f"High total cost: ${total_cost:.4f} "
                f"(threshold: ${self.HIGH_COST_WARNING:.2f})"
            )

        return TokenReport(
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            total_tokens=total_input + total_output,
            total_cost_usd=total_cost,
            by_model=sorted(by_model.values(), key=lambda m: m.cost_usd, reverse=True),
            anomalies=anomalies,
        )
