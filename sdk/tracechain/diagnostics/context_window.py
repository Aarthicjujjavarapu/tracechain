"""
Context window diagnostics.

Detects:
1. Context truncation risk — input tokens approaching model's context limit.
2. Context bloat — input tokens growing across consecutive calls (agent loops
   accumulating context without trimming).
3. Output truncation — response cut off at max_tokens limit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Known context limits per model (in tokens)
_CONTEXT_LIMITS: dict[str, int] = {
    "gpt-4o":            128_000,
    "gpt-4o-mini":       128_000,
    "gpt-4-turbo":       128_000,
    "gpt-4":               8_192,
    "gpt-3.5-turbo":      16_385,
    "claude-3-5-sonnet": 200_000,
    "claude-3-5-haiku":  200_000,
    "claude-3-opus":     200_000,
    "claude-sonnet-4":   200_000,
    "claude-haiku-4":    200_000,
    "gemini-1.5-pro":  1_000_000,
    "gemini-1.5-flash":1_000_000,
}

_TRUNCATION_WARNING_PCT = 0.80   # warn at 80% of context limit


def _get_limit(model: str) -> Optional[int]:
    model_lower = model.lower()
    for pattern, limit in _CONTEXT_LIMITS.items():
        if model_lower.startswith(pattern):
            return limit
    return None


@dataclass
class ContextWarning:
    span_id:    str
    span_name:  str
    model:      str
    kind:       str   # truncation_risk | output_truncated | context_bloat
    message:    str
    severity:   str   # warning | critical

    def to_dict(self) -> dict:
        return {
            "span_id":   self.span_id,
            "span_name": self.span_name,
            "model":     self.model,
            "kind":      self.kind,
            "message":   self.message,
            "severity":  self.severity,
        }


class ContextWindowAnalyzer:
    """
    Scans a run's LLM spans for context window issues.
    Returns a list of ContextWarnings sorted by severity.
    """

    def analyze(self, spans: list[dict]) -> list[ContextWarning]:
        warnings: list[ContextWarning] = []
        llm_calls_by_model: dict[str, list[dict]] = {}

        for span in spans:
            attrs = span.get("attributes", {})
            model = attrs.get("gen_ai.request.model")
            if not model:
                continue

            in_tok     = attrs.get("gen_ai.usage.input_tokens",  0) or 0
            out_tok    = attrs.get("gen_ai.usage.output_tokens",  0) or 0
            max_tokens = attrs.get("gen_ai.request.max_tokens")
            limit      = _get_limit(model)

            # truncation risk
            if limit and in_tok > 0:
                pct = in_tok / limit
                if pct >= 1.0:
                    warnings.append(ContextWarning(
                        span_id=span["span_id"],
                        span_name=span.get("name", ""),
                        model=model,
                        kind="truncation_risk",
                        message=(
                            f"Input tokens ({in_tok:,}) exceed model context limit "
                            f"({limit:,}) — request likely failed or was auto-truncated."
                        ),
                        severity="critical",
                    ))
                elif pct >= _TRUNCATION_WARNING_PCT:
                    warnings.append(ContextWarning(
                        span_id=span["span_id"],
                        span_name=span.get("name", ""),
                        model=model,
                        kind="truncation_risk",
                        message=(
                            f"Input tokens ({in_tok:,}) at {pct*100:.0f}% of "
                            f"{model} context limit ({limit:,})."
                        ),
                        severity="warning",
                    ))

            # output truncation (response ended exactly at max_tokens)
            if max_tokens and out_tok and out_tok >= max_tokens:
                warnings.append(ContextWarning(
                    span_id=span["span_id"],
                    span_name=span.get("name", ""),
                    model=model,
                    kind="output_truncated",
                    message=(
                        f"Output tokens ({out_tok:,}) hit max_tokens limit ({max_tokens:,}) "
                        f"— response was likely truncated."
                    ),
                    severity="warning",
                ))

            # accumulate for bloat detection
            llm_calls_by_model.setdefault(model, []).append({
                "span": span,
                "in_tok": in_tok,
            })

        # context bloat: detect monotonically growing input across calls
        for model, calls in llm_calls_by_model.items():
            if len(calls) < 3:
                continue
            tokens = [c["in_tok"] for c in calls]
            if all(tokens[i] < tokens[i + 1] for i in range(len(tokens) - 1)):
                growth = tokens[-1] - tokens[0]
                last_span = calls[-1]["span"]
                warnings.append(ContextWarning(
                    span_id=last_span["span_id"],
                    span_name=last_span.get("name", ""),
                    model=model,
                    kind="context_bloat",
                    message=(
                        f"Input tokens for {model} grew monotonically across "
                        f"{len(calls)} calls (+{growth:,} tokens). "
                        f"Agent may be accumulating context without trimming."
                    ),
                    severity="warning",
                ))

        warnings.sort(key=lambda w: 0 if w.severity == "critical" else 1)
        return warnings

    def to_dict(self, warnings: list[ContextWarning]) -> dict:
        return {
            "warning_count":  len(warnings),
            "critical_count": sum(1 for w in warnings if w.severity == "critical"),
            "warnings":       [w.to_dict() for w in warnings],
        }
