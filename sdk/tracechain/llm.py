"""
@llm_step decorator — instruments a function that returns a prompt string,
calls the LLM, and logs tokens/cost/latency/TTFT to the backend.

Non-streaming (default):
    @llm_step(name="gen", model="gpt-4o-mini")
    def gen(query: str) -> str:
        return f"Answer: {query}"
    answer = gen(query)           # returns str

Streaming (sync):
    @llm_step(name="gen", model="gpt-4o-mini", stream=True)
    def gen(query: str) -> str:
        return f"Answer: {query}"
    for token in gen(query):      # yields str tokens
        print(token, end="", flush=True)

Streaming (async):
    @llm_step(name="gen", model="gpt-4o-mini", stream=True)
    async def gen(query: str) -> str:
        return f"Answer: {query}"
    async for token in gen(query):
        print(token, end="", flush=True)
"""
import functools
import inspect
import logging
import time
from typing import Any, Callable, Generator, Optional

from .client import get_default_client, _safe_json
from .tracing import get_run_id, set_step_id, reset_step_id, add_llm_usage
from .workflow import _build_input_payload
from .otel import (
    _otel_span, _otel_set_ok, _otel_set_error,
    _otel_start_span, _otel_end_span,
)

logger = logging.getLogger("tracechain.llm")

# ── cost table: USD per 1K tokens (in, out) ───────────────────────────────────
_COST_TABLE: dict[str, tuple[float, float]] = {
    "gpt-4o":            (0.005,   0.015),
    "gpt-4o-mini":       (0.00015, 0.00060),
    "gpt-4-turbo":       (0.01,    0.03),
    "gpt-4":             (0.03,    0.06),
    "gpt-3.5-turbo":     (0.0005,  0.0015),
    "claude-opus-4":     (0.015,   0.075),
    "claude-sonnet-4":   (0.003,   0.015),
    "claude-haiku-4":    (0.0008,  0.004),
    "claude-3-5-sonnet": (0.003,   0.015),
    "claude-3-5-haiku":  (0.0008,  0.004),
    "claude-3-opus":     (0.015,   0.075),
    "claude-3-sonnet":   (0.003,   0.015),
    "claude-3-haiku":    (0.00025, 0.00125),
}


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    for key, (in_rate, out_rate) in sorted(_COST_TABLE.items(), key=lambda x: -len(x[0])):
        if model.startswith(key):
            return round((input_tokens / 1000 * in_rate) + (output_tokens / 1000 * out_rate), 8)
    return round((input_tokens + output_tokens) / 1000 * 0.002, 8)


# ── decorator ─────────────────────────────────────────────────────────────────

def llm_step(
    name: str,
    model: str = "gpt-4o-mini",
    prompt_version: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 1024,
    provider: str = "openai",
    stream: bool = False,
    client=None,
):
    """
    Decorator that instruments an LLM-powered function.

    The decorated function must return a prompt string. With stream=False
    (default) the decorator returns the full response string. With stream=True
    it returns a Generator (sync fn) or AsyncGenerator (async fn) that yields
    tokens as they arrive; all metrics are logged after the stream is exhausted.
    """
    def decorator(fn: Callable) -> Callable:
        is_async_fn = inspect.iscoroutinefunction(fn)

        # ── streaming paths ───────────────────────────────────────────────────
        if stream:
            if is_async_fn:
                @functools.wraps(fn)
                async def async_stream_wrapper(*args, **kwargs):
                    prompt = await fn(*args, **kwargs)
                    if not isinstance(prompt, str):
                        prompt = str(prompt)
                    input_payload = _build_input_payload(fn, args, kwargs)
                    tc = client or get_default_client()
                    run_id = get_run_id()
                    step_id = None
                    if run_id:
                        step_id = tc.create_step(
                            run_id=run_id, step_name=name, step_type="llm_step",
                            input_payload=input_payload,
                        )
                    ctx_token = set_step_id(step_id) if step_id else None

                    accumulated: list[str] = []
                    ttft_ms: Optional[int] = None
                    in_tokens = out_tokens = 0
                    start = _now_ms()
                    error_msg: Optional[str] = None

                    _span, _token = _otel_start_span(f"llm.{name}", {
                        "gen_ai.system": provider,
                        "gen_ai.request.model": model,
                        "gen_ai.request.temperature": temperature,
                        "tracechain.llm.is_stream": True,
                    })
                    _span_exc: Optional[Exception] = None

                    try:
                        async for chunk, in_t, out_t in _stream_llm_async(
                            provider, model, prompt, temperature, max_tokens
                        ):
                            if chunk:
                                if ttft_ms is None:
                                    ttft_ms = _now_ms() - start
                                accumulated.append(chunk)
                                yield chunk
                            if in_t:
                                in_tokens, out_tokens = in_t, out_t
                    except Exception as exc:
                        error_msg = str(exc)
                        _span_exc = exc
                        raise
                    finally:
                        _otel_end_span(_span, _token, error=_span_exc)
                        _log_stream_completion(
                            tc=tc, run_id=run_id, step_id=step_id, ctx_token=ctx_token,
                            name=name, model=model, provider=provider, prompt=prompt,
                            full_response="".join(accumulated),
                            in_tokens=in_tokens, out_tokens=out_tokens,
                            start=start, ttft_ms=ttft_ms, temperature=temperature,
                            prompt_version=prompt_version, error_msg=error_msg,
                        )
                return async_stream_wrapper

            else:
                @functools.wraps(fn)
                def sync_stream_wrapper(*args, **kwargs) -> Generator[str, None, None]:
                    prompt = fn(*args, **kwargs)
                    if not isinstance(prompt, str):
                        prompt = str(prompt)
                    input_payload = _build_input_payload(fn, args, kwargs)
                    return _sync_streaming_gen(
                        tc_or_none=client, name=name, model=model, provider=provider,
                        prompt=prompt, input_payload=input_payload,
                        temperature=temperature, max_tokens=max_tokens,
                        prompt_version=prompt_version,
                    )
                return sync_stream_wrapper

        # ── non-streaming paths (original behaviour) ──────────────────────────
        _otel_attrs = {
            "gen_ai.system": provider,
            "gen_ai.request.model": model,
            "gen_ai.request.temperature": temperature,
            "tracechain.llm.is_stream": False,
        }

        if is_async_fn:
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs) -> str:
                with _otel_span(f"llm.{name}", _otel_attrs) as _span:
                    try:
                        result = await _run_llm_step(
                            fn, args, kwargs, name=name, model=model,
                            prompt_version=prompt_version, temperature=temperature,
                            max_tokens=max_tokens, provider=provider, client=client,
                        )
                        _otel_set_ok(_span)
                        return result
                    except Exception as exc:
                        _otel_set_error(_span, exc)
                        raise
            return async_wrapper

        @functools.wraps(fn)
        def sync_wrapper(*args, **kwargs) -> str:
            with _otel_span(f"llm.{name}", _otel_attrs) as _span:
                try:
                    result = _run_llm_step_sync(
                        fn, args, kwargs, name=name, model=model,
                        prompt_version=prompt_version, temperature=temperature,
                        max_tokens=max_tokens, provider=provider, client=client,
                    )
                    _otel_set_ok(_span)
                    return result
                except Exception as exc:
                    _otel_set_error(_span, exc)
                    raise
        return sync_wrapper

    return decorator


# ── non-streaming internals ───────────────────────────────────────────────────

def _run_llm_step_sync(fn, args, kwargs, *, name, model, prompt_version,
                       temperature, max_tokens, provider, client):
    tc = client or get_default_client()
    run_id = get_run_id()
    input_payload = _build_input_payload(fn, args, kwargs)

    step_id = None
    if run_id:
        step_id = tc.create_step(
            run_id=run_id, step_name=name, step_type="llm_step",
            input_payload=input_payload,
        )

    ctx_token = set_step_id(step_id) if step_id else None
    start_ms = _now_ms()

    prompt = response_text = ""
    in_tokens = out_tokens = total_tokens = None
    cost: Optional[float] = None
    llm_status = "success"
    error_msg: Optional[str] = None

    try:
        prompt = fn(*args, **kwargs)
        if not isinstance(prompt, str):
            prompt = str(prompt)
        response_text, in_tokens, out_tokens = _call_llm(
            provider=provider, model=model, prompt=prompt,
            temperature=temperature, max_tokens=max_tokens,
        )
        total_tokens = (in_tokens or 0) + (out_tokens or 0)
        cost = _estimate_cost(model, in_tokens or 0, out_tokens or 0)
    except Exception as exc:
        llm_status = "failed"
        error_msg = str(exc)
        logger.error(f"[TraceChain] LLM call failed in step '{name}': {exc}")

    return _finalise_llm_step(
        tc=tc, run_id=run_id, step_id=step_id, ctx_token=ctx_token,
        name=name, model=model, provider=provider, prompt=prompt,
        response_text=response_text, in_tokens=in_tokens, out_tokens=out_tokens,
        total_tokens=total_tokens, cost=cost, start_ms=start_ms,
        temperature=temperature, prompt_version=prompt_version,
        llm_status=llm_status, error_msg=error_msg,
    )


async def _run_llm_step(fn, args, kwargs, *, name, model, prompt_version,
                        temperature, max_tokens, provider, client):
    tc = client or get_default_client()
    run_id = get_run_id()
    input_payload = _build_input_payload(fn, args, kwargs)

    step_id = None
    if run_id:
        step_id = tc.create_step(
            run_id=run_id, step_name=name, step_type="llm_step",
            input_payload=input_payload,
        )

    ctx_token = set_step_id(step_id) if step_id else None
    start_ms = _now_ms()

    prompt = response_text = ""
    in_tokens = out_tokens = total_tokens = None
    cost: Optional[float] = None
    llm_status = "success"
    error_msg: Optional[str] = None

    try:
        prompt = await fn(*args, **kwargs)
        if not isinstance(prompt, str):
            prompt = str(prompt)
        response_text, in_tokens, out_tokens = await _call_llm_async(
            provider=provider, model=model, prompt=prompt,
            temperature=temperature, max_tokens=max_tokens,
        )
        total_tokens = (in_tokens or 0) + (out_tokens or 0)
        cost = _estimate_cost(model, in_tokens or 0, out_tokens or 0)
    except Exception as exc:
        llm_status = "failed"
        error_msg = str(exc)
        logger.error(f"[TraceChain] LLM call failed in step '{name}': {exc}")

    return _finalise_llm_step(
        tc=tc, run_id=run_id, step_id=step_id, ctx_token=ctx_token,
        name=name, model=model, provider=provider, prompt=prompt,
        response_text=response_text, in_tokens=in_tokens, out_tokens=out_tokens,
        total_tokens=total_tokens, cost=cost, start_ms=start_ms,
        temperature=temperature, prompt_version=prompt_version,
        llm_status=llm_status, error_msg=error_msg,
    )


def _finalise_llm_step(*, tc, run_id, step_id, ctx_token, name, model, provider,
                       prompt, response_text, in_tokens, out_tokens, total_tokens,
                       cost, start_ms, temperature, prompt_version, llm_status, error_msg):
    latency = _now_ms() - start_ms
    add_llm_usage(cost or 0.0, total_tokens or 0)

    if run_id:
        tc.log_llm_call(
            run_id=run_id, step_id=step_id, provider=provider, model=model,
            prompt=prompt, response=response_text, input_tokens=in_tokens,
            output_tokens=out_tokens, total_tokens=total_tokens,
            estimated_cost=cost, latency_ms=latency, temperature=temperature,
            status=llm_status, error_message=error_msg, prompt_version=prompt_version,
            time_to_first_token_ms=None, is_stream=False,
        )
        if step_id:
            if llm_status == "success":
                tc.complete_step(
                    run_id=run_id, step_id=step_id,
                    output_payload={"response": response_text}, duration_ms=latency,
                )
            else:
                tc.fail_step(
                    run_id=run_id, step_id=step_id,
                    error_message=error_msg or "LLM call failed",
                )

    if ctx_token is not None:
        reset_step_id(ctx_token)

    if llm_status == "failed":
        raise RuntimeError(error_msg)

    return response_text


# ── non-streaming provider calls ──────────────────────────────────────────────

def _call_llm(provider, model, prompt, temperature, max_tokens) -> tuple[str, int, int]:
    if provider == "anthropic":
        return _call_anthropic(model, prompt, temperature, max_tokens)
    return _call_openai(model, prompt, temperature, max_tokens)


async def _call_llm_async(provider, model, prompt, temperature, max_tokens) -> tuple[str, int, int]:
    if provider == "anthropic":
        return await _call_anthropic_async(model, prompt, temperature, max_tokens)
    return await _call_openai_async(model, prompt, temperature, max_tokens)


def _call_openai(model, prompt, temperature, max_tokens) -> tuple[str, int, int]:
    import os
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("[TraceChain] OPENAI_API_KEY not set — using mock LLM response.")
        return _mock_response(prompt, max_tokens)
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai not installed. Run: pip install 'tracechain[openai]'")
    oc = OpenAI()
    completion = oc.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature, max_tokens=max_tokens,
    )
    text = completion.choices[0].message.content or ""
    usage = completion.usage
    return text, (usage.prompt_tokens if usage else 0), (usage.completion_tokens if usage else 0)


async def _call_openai_async(model, prompt, temperature, max_tokens) -> tuple[str, int, int]:
    import os
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("[TraceChain] OPENAI_API_KEY not set — using mock LLM response.")
        return _mock_response(prompt, max_tokens)
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise RuntimeError("openai not installed. Run: pip install 'tracechain[openai]'")
    oc = AsyncOpenAI()
    completion = await oc.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature, max_tokens=max_tokens,
    )
    text = completion.choices[0].message.content or ""
    usage = completion.usage
    return text, (usage.prompt_tokens if usage else 0), (usage.completion_tokens if usage else 0)


def _call_anthropic(model, prompt, temperature, max_tokens) -> tuple[str, int, int]:
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("[TraceChain] ANTHROPIC_API_KEY not set — using mock LLM response.")
        return _mock_response(prompt, max_tokens)
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic not installed. Run: pip install 'tracechain[anthropic]'")
    ac = anthropic.Anthropic()
    msg = ac.messages.create(
        model=model, max_tokens=max_tokens, temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text, msg.usage.input_tokens, msg.usage.output_tokens


async def _call_anthropic_async(model, prompt, temperature, max_tokens) -> tuple[str, int, int]:
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("[TraceChain] ANTHROPIC_API_KEY not set — using mock LLM response.")
        return _mock_response(prompt, max_tokens)
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic not installed. Run: pip install 'tracechain[anthropic]'")
    ac = anthropic.AsyncAnthropic()
    msg = await ac.messages.create(
        model=model, max_tokens=max_tokens, temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text, msg.usage.input_tokens, msg.usage.output_tokens


# ── streaming internals ───────────────────────────────────────────────────────

def _sync_streaming_gen(*, tc_or_none, name, model, provider, prompt, input_payload,
                        temperature, max_tokens, prompt_version) -> Generator[str, None, None]:
    """Sync generator: yields str tokens; logs to backend in finally block."""
    tc = tc_or_none or get_default_client()
    run_id = get_run_id()
    step_id = None
    if run_id:
        step_id = tc.create_step(
            run_id=run_id, step_name=name, step_type="llm_step",
            input_payload=input_payload,
        )
    ctx_token = set_step_id(step_id) if step_id else None

    accumulated: list[str] = []
    ttft_ms: Optional[int] = None
    in_tokens = out_tokens = 0
    start = _now_ms()
    error_msg: Optional[str] = None

    _span, _token = _otel_start_span(f"llm.{name}", {
        "gen_ai.system": provider,
        "gen_ai.request.model": model,
        "gen_ai.request.temperature": temperature,
        "tracechain.llm.is_stream": True,
    })
    _span_exc: Optional[Exception] = None

    try:
        for chunk, in_t, out_t in _stream_llm_sync(provider, model, prompt, temperature, max_tokens):
            if chunk:
                if ttft_ms is None:
                    ttft_ms = _now_ms() - start
                accumulated.append(chunk)
                yield chunk
            if in_t:
                in_tokens, out_tokens = in_t, out_t
    except Exception as exc:
        error_msg = str(exc)
        _span_exc = exc
        raise
    finally:
        _otel_end_span(_span, _token, error=_span_exc)
        _log_stream_completion(
            tc=tc, run_id=run_id, step_id=step_id, ctx_token=ctx_token,
            name=name, model=model, provider=provider, prompt=prompt,
            full_response="".join(accumulated),
            in_tokens=in_tokens, out_tokens=out_tokens,
            start=start, ttft_ms=ttft_ms, temperature=temperature,
            prompt_version=prompt_version, error_msg=error_msg,
        )


def _log_stream_completion(*, tc, run_id, step_id, ctx_token, name, model, provider,
                           prompt, full_response, in_tokens, out_tokens, start,
                           ttft_ms, temperature, prompt_version, error_msg):
    """Persist streaming metrics to the backend. Called in generator finally blocks."""
    latency = _now_ms() - start
    total_tokens = in_tokens + out_tokens
    cost = _estimate_cost(model, in_tokens, out_tokens) if not error_msg else None
    add_llm_usage(cost or 0.0, total_tokens)
    status = "failed" if error_msg else "success"

    if run_id:
        tc.log_llm_call(
            run_id=run_id, step_id=step_id, provider=provider, model=model,
            prompt=prompt,
            response=full_response if not error_msg else None,
            input_tokens=in_tokens or None,
            output_tokens=out_tokens or None,
            total_tokens=total_tokens or None,
            estimated_cost=cost,
            latency_ms=latency,
            temperature=temperature,
            status=status,
            error_message=error_msg,
            prompt_version=prompt_version,
            time_to_first_token_ms=ttft_ms,
            is_stream=True,
        )
        if step_id:
            if error_msg:
                tc.fail_step(run_id=run_id, step_id=step_id, error_message=error_msg)
            else:
                tc.complete_step(
                    run_id=run_id, step_id=step_id,
                    output_payload={"response": full_response}, duration_ms=latency,
                )

    if ctx_token is not None:
        reset_step_id(ctx_token)


# ── streaming provider calls — sync ───────────────────────────────────────────
# Each generator yields (chunk: str, in_tokens: int, out_tokens: int).
# Tokens are 0 on every chunk except the final usage-only sentinel yield.

def _stream_llm_sync(provider, model, prompt, temperature, max_tokens):
    if provider == "anthropic":
        yield from _stream_anthropic_sync(model, prompt, temperature, max_tokens)
    else:
        yield from _stream_openai_sync(model, prompt, temperature, max_tokens)


def _stream_openai_sync(model, prompt, temperature, max_tokens):
    import os
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("[TraceChain] OPENAI_API_KEY not set — streaming mock response.")
        yield from _mock_stream(prompt, max_tokens)
        return
    try:
        from openai import OpenAI
    except ImportError:
        raise RuntimeError("openai not installed. Run: pip install 'tracechain[openai]'")
    oc = OpenAI()
    stream = oc.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        stream_options={"include_usage": True},
        temperature=temperature, max_tokens=max_tokens,
    )
    for chunk in stream:
        text = ""
        in_t = out_t = 0
        if chunk.choices and chunk.choices[0].delta.content:
            text = chunk.choices[0].delta.content
        if chunk.usage:
            in_t  = chunk.usage.prompt_tokens     or 0
            out_t = chunk.usage.completion_tokens  or 0
        yield text, in_t, out_t


def _stream_anthropic_sync(model, prompt, temperature, max_tokens):
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("[TraceChain] ANTHROPIC_API_KEY not set — streaming mock response.")
        yield from _mock_stream(prompt, max_tokens)
        return
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic not installed. Run: pip install 'tracechain[anthropic]'")
    ac = anthropic.Anthropic()
    with ac.messages.stream(
        model=model, max_tokens=max_tokens, temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            yield text, 0, 0
        final = stream.get_final_message()
        yield "", final.usage.input_tokens, final.usage.output_tokens


# ── streaming provider calls — async ─────────────────────────────────────────

async def _stream_llm_async(provider, model, prompt, temperature, max_tokens):
    if provider == "anthropic":
        async for item in _stream_anthropic_async(model, prompt, temperature, max_tokens):
            yield item
    else:
        async for item in _stream_openai_async(model, prompt, temperature, max_tokens):
            yield item


async def _stream_openai_async(model, prompt, temperature, max_tokens):
    import os
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("[TraceChain] OPENAI_API_KEY not set — streaming mock response.")
        async for item in _mock_stream_async(prompt, max_tokens):
            yield item
        return
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise RuntimeError("openai not installed. Run: pip install 'tracechain[openai]'")
    oc = AsyncOpenAI()
    stream = await oc.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
        stream_options={"include_usage": True},
        temperature=temperature, max_tokens=max_tokens,
    )
    async for chunk in stream:
        text = ""
        in_t = out_t = 0
        if chunk.choices and chunk.choices[0].delta.content:
            text = chunk.choices[0].delta.content
        if chunk.usage:
            in_t  = chunk.usage.prompt_tokens     or 0
            out_t = chunk.usage.completion_tokens  or 0
        yield text, in_t, out_t


async def _stream_anthropic_async(model, prompt, temperature, max_tokens):
    import os
    if not os.getenv("ANTHROPIC_API_KEY"):
        logger.warning("[TraceChain] ANTHROPIC_API_KEY not set — streaming mock response.")
        async for item in _mock_stream_async(prompt, max_tokens):
            yield item
        return
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic not installed. Run: pip install 'tracechain[anthropic]'")
    ac = anthropic.AsyncAnthropic()
    async with ac.messages.stream(
        model=model, max_tokens=max_tokens, temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        async for text in stream.text_stream:
            yield text, 0, 0
        final = await stream.get_final_message()
        yield "", final.usage.input_tokens, final.usage.output_tokens


# ── mock stream (no API key) ──────────────────────────────────────────────────

def _mock_stream(prompt: str, max_tokens: int):
    """Yield the mock response word-by-word, then a final usage sentinel."""
    response, in_t, out_t = _mock_response(prompt, max_tokens)
    words = response.split()
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        yield chunk, 0, 0
    yield "", in_t, out_t


async def _mock_stream_async(prompt: str, max_tokens: int):
    response, in_t, out_t = _mock_response(prompt, max_tokens)
    words = response.split()
    for i, word in enumerate(words):
        chunk = word + (" " if i < len(words) - 1 else "")
        yield chunk, 0, 0
    yield "", in_t, out_t


# ── mock response (context-aware) ────────────────────────────────────────────

def _mock_response(prompt: str, max_tokens: int) -> tuple[str, int, int]:
    import re
    bullet_docs  = re.findall(r"^\s+- (.+)$", prompt, re.MULTILINE)
    section_docs = re.findall(r"\[[^\]]+\]\n(.+?)(?=\n\n|\Z)", prompt, re.DOTALL)
    docs_text = " ".join(bullet_docs[:3]) if bullet_docs else " ".join(
        s.strip().replace("\n", " ") for s in section_docs[:2]
    )
    if docs_text:
        sentences = re.split(r"(?<=[.!?])\s+", docs_text.strip())
        meaningful = [s.strip() for s in sentences if len(s.split()) > 6][:2]
        response = " ".join(meaningful) if meaningful else docs_text[:220]
        if not response.endswith("."):
            response = response.rstrip(",;") + "."
    else:
        import hashlib
        seed = int(hashlib.md5(prompt.encode()).hexdigest()[:8], 16)
        fallbacks = [
            "Please follow the documented procedure outlined in the support materials.",
            "Refer to the relevant section of the documentation for step-by-step instructions.",
        ]
        response = fallbacks[seed % len(fallbacks)]

    in_t  = max(10, len(prompt.split()) + 20)
    out_t = max(10, len(response.split()) + 5)
    return response, in_t, out_t


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
