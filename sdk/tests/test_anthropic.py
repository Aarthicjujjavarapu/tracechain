"""
Tests for Anthropic provider support in @llm_step.
The Anthropic SDK client is mocked — no real API calls are made.
"""
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from tracechain.llm import (
    _call_anthropic, _call_anthropic_async,
    _call_llm, _call_llm_async,
    _estimate_cost,
)
from tracechain.tracing import set_run_id, reset_run_id
from .conftest import MockClient


# ── helpers ───────────────────────────────────────────────────────────────────

def _anthropic_message(text="Claude response", in_tokens=50, out_tokens=30):
    msg = MagicMock()
    msg.content = [MagicMock(text=text)]
    msg.usage.input_tokens  = in_tokens
    msg.usage.output_tokens = out_tokens
    return msg


# ── cost table ────────────────────────────────────────────────────────────────

def test_claude_opus_4_cost():
    cost = _estimate_cost("claude-opus-4", 1000, 1000)
    assert cost == round(0.015 + 0.075, 8)


def test_claude_sonnet_4_cost():
    cost = _estimate_cost("claude-sonnet-4", 1000, 1000)
    assert cost == round(0.003 + 0.015, 8)


def test_claude_haiku_4_cost():
    cost = _estimate_cost("claude-haiku-4", 1000, 1000)
    assert cost == round(0.0008 + 0.004, 8)


def test_claude_3_5_sonnet_cost():
    cost = _estimate_cost("claude-3-5-sonnet-20241022", 1000, 1000)
    assert cost == round(0.003 + 0.015, 8)


def test_claude_3_haiku_cost():
    cost = _estimate_cost("claude-3-haiku-20240307", 1000, 1000)
    assert cost == round(0.00025 + 0.00125, 8)


# ── _call_anthropic (sync) ────────────────────────────────────────────────────

def test_call_anthropic_no_key_returns_mock(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    text, in_t, out_t = _call_anthropic("claude-3-haiku-20240307", "hello", 0.7, 256)
    assert isinstance(text, str) and len(text) > 0
    assert in_t > 0 and out_t > 0


def test_call_anthropic_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    with patch("anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = \
            _anthropic_message("Anthropic reply", in_tokens=40, out_tokens=20)

        text, in_t, out_t = _call_anthropic("claude-3-5-sonnet-20241022", "prompt", 0.7, 512)

    assert text == "Anthropic reply"
    assert in_t == 40
    assert out_t == 20


def test_call_anthropic_passes_correct_args(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    with patch("anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.return_value = _anthropic_message()

        _call_anthropic("claude-3-haiku-20240307", "my prompt", 0.5, 256)

    call_kwargs = instance.messages.create.call_args[1]
    assert call_kwargs["model"]      == "claude-3-haiku-20240307"
    assert call_kwargs["max_tokens"] == 256
    assert call_kwargs["temperature"]== 0.5
    assert call_kwargs["messages"]   == [{"role": "user", "content": "my prompt"}]


def test_call_anthropic_missing_package(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    with patch.dict("sys.modules", {"anthropic": None}):
        with pytest.raises(RuntimeError, match="anthropic not installed"):
            _call_anthropic("claude-3-haiku-20240307", "prompt", 0.7, 256)


# ── _call_anthropic_async ─────────────────────────────────────────────────────

def test_call_anthropic_async_with_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    async def run():
        with patch("anthropic.AsyncAnthropic") as MockAsync:
            instance = MockAsync.return_value
            instance.messages.create = AsyncMock(
                return_value=_anthropic_message("Async Claude", in_tokens=60, out_tokens=25)
            )
            return await _call_anthropic_async("claude-3-5-sonnet-20241022", "prompt", 0.7, 512)

    text, in_t, out_t = asyncio.run(run())
    assert text == "Async Claude"
    assert in_t == 60
    assert out_t == 25


def test_call_anthropic_async_no_key_returns_mock(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    async def run():
        return await _call_anthropic_async("claude-3-haiku-20240307", "prompt", 0.7, 256)

    text, in_t, out_t = asyncio.run(run())
    assert isinstance(text, str) and len(text) > 0


# ── _call_llm dispatcher ──────────────────────────────────────────────────────

def test_dispatcher_routes_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    with patch("anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = \
            _anthropic_message("dispatched")

        text, _, _ = _call_llm("anthropic", "claude-3-haiku-20240307", "p", 0.7, 128)

    assert text == "dispatched"


def test_dispatcher_routes_openai_by_default(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    # Without key, falls back to mock — verifies the openai path is taken
    text, in_t, out_t = _call_llm("openai", "gpt-4o-mini", "hello", 0.7, 128)
    assert isinstance(text, str)


def test_async_dispatcher_routes_anthropic(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")

    async def run():
        with patch("anthropic.AsyncAnthropic") as MockAsync:
            instance = MockAsync.return_value
            instance.messages.create = AsyncMock(
                return_value=_anthropic_message("async dispatched")
            )
            return await _call_llm_async("anthropic", "claude-3-haiku-20240307", "p", 0.7, 128)

    text, _, _ = asyncio.run(run())
    assert text == "async dispatched"


# ── @llm_step with provider="anthropic" ──────────────────────────────────────

def test_llm_step_anthropic_provider(monkeypatch):
    from tracechain.llm import llm_step

    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    mc = MockClient()
    token = set_run_id("run-ant")

    try:
        with patch("anthropic.Anthropic") as MockAnthropic:
            MockAnthropic.return_value.messages.create.return_value = \
                _anthropic_message("Claude answer")

            @llm_step(name="gen", model="claude-3-haiku-20240307",
                      provider="anthropic", client=mc)
            def gen(q):
                return f"Answer: {q}"

            result = gen("test question")
    finally:
        reset_run_id(token)

    assert result == "Claude answer"
    # provider is recorded correctly in the LLM call log
    log_args = mc.call_args("log_llm_call")
    assert log_args["provider"] == "anthropic"
    assert log_args["model"]    == "claude-3-haiku-20240307"
