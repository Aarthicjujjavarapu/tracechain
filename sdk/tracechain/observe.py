"""
observe_llm() — observer-pattern context manager for LLM calls.

The user owns the LLM call. TraceChain just watches: it starts a timer,
records whatever you hand it, and logs to the backend on exit.

This unlocks the full API surface of any LLM client:
  - System prompts, multi-turn history
  - Tool / function calling
  - Vision, structured output, JSON mode
  - Custom models, local models, proxies

Usage
─────
Non-streaming:
    from tracechain import observe_llm, step

    @step(name="generate")
    def generate(messages: list[dict]) -> str:
        with observe_llm("chat", model="gpt-4o", provider="openai",
                         prompt=messages[-1]["content"]) as obs:
            resp = openai_client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=[search_tool],
            )
            obs.record(resp)            # auto-extracts tokens, cost, text
        return resp.choices[0].message.content

Async:
    async with observe_llm("chat", model="claude-3-5-sonnet") as obs:
        resp = await async_client.messages.create(...)
        obs.record(resp)               # auto-extracts from Anthropic Message

Streaming:
    with observe_llm("stream", model="gpt-4o", is_stream=True) as obs:
        response_text = ""
        for chunk in client.chat.completions.create(..., stream=True):
            token = chunk.choices[0].delta.content or ""
            if token:
                obs.on_chunk()         # captures TTFT on first non-empty chunk
                response_text += token
        obs.record(response=response_text, input_tokens=in_t, output_tokens=out_t)

Custom / local LLM:
    with observe_llm("ollama", model="llama3", provider="ollama") as obs:
        result = requests.post("http://localhost:11434/api/generate", ...).json()
        obs.record(
            response=result["response"],
            input_tokens=result["prompt_eval_count"],
            output_tokens=result["eval_count"],
        )

Auto-extraction supports:
    - openai.types.chat.ChatCompletion  (checks .choices + .usage.prompt_tokens)
    - anthropic.types.Message          (checks .content + .usage.input_tokens)
"""
from __future__ import annotations

import time
from typing import Any, Optional

from .client import get_default_client
from .tracing import get_run_id, get_step_id, add_llm_usage
from .otel import _otel_start_span, _otel_end_span
from .llm import _estimate_cost, _now_ms


def observe_llm(
    name: str,
    *,
    model: str,
    provider: str = "openai",
    temperature: float = 1.0,
    prompt: Optional[str] = None,
    prompt_version: Optional[str] = None,
    is_stream: bool = False,
    client: Any = None,
) -> "_LlmObserver":
    """
    Return a context manager (sync or async) that records an LLM call you own.

    Args:
        name:           Label for this call in the dashboard.
        model:          Model identifier sent to the LLM (e.g. "gpt-4o").
        provider:       "openai", "anthropic", or any custom string.
        temperature:    Request temperature — for metadata only, not enforced.
        prompt:         The human turn / last user message, for the trace log.
                        Can also be passed to obs.record().
        prompt_version: Optional version tag for your prompt template.
        is_stream:      Set True when consuming a streaming response.
        client:         Override the default TraceChainClient.
    """
    return _LlmObserver(
        name=name, model=model, provider=provider, temperature=temperature,
        prompt=prompt, prompt_version=prompt_version, is_stream=is_stream,
        client=client,
    )


class _LlmObserver:
    """Internal context manager returned by observe_llm()."""

    def __init__(self, *, name, model, provider, temperature,
                 prompt, prompt_version, is_stream, client):
        self._name = name
        self._model = model
        self._provider = provider
        self._temperature = temperature
        self._prompt = prompt
        self._prompt_version = prompt_version
        self._is_stream = is_stream
        self._client_override = client

        self._response: Optional[str] = None
        self._input_tokens: Optional[int] = None
        self._output_tokens: Optional[int] = None
        self._total_tokens: Optional[int] = None
        self._estimated_cost: Optional[float] = None
        self._ttft_ms: Optional[int] = None
        self._error: Optional[str] = None
        self._chunk_seen: bool = False
        self._start_ms: int = 0

        self._tc: Any = None
        self._run_id: Optional[str] = None
        self._step_id: Optional[str] = None
        self._span: Any = None
        self._otel_token: Any = None

    # ── context manager (sync + async share the same body) ────────────────────

    def _begin(self) -> "_LlmObserver":
        self._start_ms = _now_ms()
        self._tc = self._client_override or get_default_client()
        self._run_id = get_run_id()
        self._step_id = get_step_id()
        self._span, self._otel_token = _otel_start_span(f"llm.{self._name}", {
            "gen_ai.system": self._provider,
            "gen_ai.request.model": self._model,
            "gen_ai.request.temperature": self._temperature,
            "tracechain.llm.is_stream": self._is_stream,
        })
        return self

    def _end(self, exc: Optional[BaseException]) -> None:
        if exc is not None:
            self._error = str(exc)
        self._flush()

    def __enter__(self) -> "_LlmObserver":
        return self._begin()

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._end(exc_val)
        return False

    async def __aenter__(self) -> "_LlmObserver":
        return self._begin()

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> bool:
        self._end(exc_val)
        return False

    # ── public API ─────────────────────────────────────────────────────────────

    def record(
        self,
        response_obj: Any = None,
        *,
        response: Optional[str] = None,
        input_tokens: Optional[int] = None,
        output_tokens: Optional[int] = None,
        estimated_cost: Optional[float] = None,
        prompt: Optional[str] = None,
    ) -> None:
        """
        Record the result of the LLM call.

        Pass either:
        • An OpenAI ``ChatCompletion`` or Anthropic ``Message`` object — fields
          are extracted automatically.
        • Explicit keyword args — for custom/local models or when you want to
          override the auto-extracted values.

        Both can be combined: pass the response object *and* override specific
        fields you want to set manually.
        """
        if response_obj is not None:
            auto_text, auto_in, auto_out = _extract_from_response(response_obj)
            self._response = auto_text if response is None else response
            self._input_tokens = auto_in if input_tokens is None else input_tokens
            self._output_tokens = auto_out if output_tokens is None else output_tokens
        else:
            self._response = response
            self._input_tokens = input_tokens
            self._output_tokens = output_tokens

        if self._input_tokens is not None and self._output_tokens is not None:
            self._total_tokens = self._input_tokens + self._output_tokens
            if estimated_cost is None:
                self._estimated_cost = _estimate_cost(
                    self._model, self._input_tokens, self._output_tokens
                )

        if estimated_cost is not None:
            self._estimated_cost = estimated_cost

        if prompt is not None:
            self._prompt = prompt

    def on_chunk(self) -> None:
        """Call on the first non-empty streaming token to record TTFT. Idempotent."""
        if not self._chunk_seen:
            self._ttft_ms = _now_ms() - self._start_ms
            self._chunk_seen = True

    # ── internals ─────────────────────────────────────────────────────────────

    def _flush(self) -> None:
        latency = _now_ms() - self._start_ms
        status = "failed" if self._error else "success"

        add_llm_usage(self._estimated_cost or 0.0, self._total_tokens or 0)
        _otel_end_span(
            self._span,
            self._otel_token,
            error=Exception(self._error) if self._error else None,
        )

        if not self._run_id:
            return

        self._tc.log_llm_call(
            run_id=self._run_id,
            step_id=self._step_id,
            provider=self._provider,
            model=self._model,
            prompt=self._prompt or "",
            response=self._response,
            input_tokens=self._input_tokens,
            output_tokens=self._output_tokens,
            total_tokens=self._total_tokens,
            estimated_cost=self._estimated_cost,
            latency_ms=latency,
            temperature=self._temperature,
            status=status,
            error_message=self._error,
            prompt_version=self._prompt_version,
            time_to_first_token_ms=self._ttft_ms,
            is_stream=self._is_stream,
        )


# ── auto-extraction ────────────────────────────────────────────────────────────

def _extract_from_response(
    obj: Any,
) -> tuple[Optional[str], Optional[int], Optional[int]]:
    """
    Duck-typed extraction — no hard import of openai or anthropic required.

    Supports:
      openai.types.chat.ChatCompletion  → .choices[0].message.content + .usage
      anthropic.types.Message           → .content[0].text + .usage
    Returns (response_text, input_tokens, output_tokens), any may be None.
    """
    if obj is None or not hasattr(obj, "__class__"):
        return None, None, None

    # OpenAI: has .choices (list) and .usage.prompt_tokens
    if hasattr(obj, "choices") and hasattr(obj, "usage") and obj.usage is not None:
        text: Optional[str] = None
        choices = obj.choices
        if choices:
            msg = getattr(choices[0], "message", None)
            if msg is not None:
                text = getattr(msg, "content", None) or None
        usage = obj.usage
        in_t: Optional[int] = getattr(usage, "prompt_tokens", None)
        out_t: Optional[int] = getattr(usage, "completion_tokens", None)
        return text, in_t, out_t

    # Anthropic: has .content (list) and .usage.input_tokens
    if (
        hasattr(obj, "content")
        and hasattr(obj, "usage")
        and hasattr(obj.usage, "input_tokens")
    ):
        text = None
        content = obj.content
        if content:
            text = getattr(content[0], "text", None) or None
        return text, obj.usage.input_tokens, obj.usage.output_tokens

    return None, None, None
