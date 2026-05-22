"""
Tests for streaming support in @llm_step.

All tests use the mock-stream path (no API key set) unless explicitly testing
a mocked OpenAI/Anthropic client, so no real network calls are made.
"""
import asyncio
import inspect
import pytest
from types import SimpleNamespace

from tracechain.llm import llm_step
from tracechain.tracing import set_run_id, reset_run_id
from .conftest import MockClient


def run(coro):
    return asyncio.run(coro)


def _oai_chunk(content=None, in_tokens=0, out_tokens=0):
    """Build a minimal fake OpenAI streaming chunk."""
    delta   = SimpleNamespace(content=content)
    choices = [SimpleNamespace(delta=delta)] if content is not None else []
    usage   = SimpleNamespace(prompt_tokens=in_tokens, completion_tokens=out_tokens) \
              if (in_tokens or out_tokens) else None
    return SimpleNamespace(choices=choices, usage=usage)


@pytest.fixture(autouse=True)
def run_context():
    token = set_run_id("run-stream-test")
    yield
    reset_run_id(token)


@pytest.fixture
def no_key(monkeypatch):
    """Ensure no LLM API keys are set so the mock stream path is used."""
    monkeypatch.delenv("OPENAI_API_KEY",    raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)


# ── sync streaming ─────────────────────────────────────────────────────────────

def test_sync_stream_returns_generator(no_key):
    import types
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    def gen():
        return "hello"

    assert isinstance(gen(), types.GeneratorType)


def test_sync_stream_yields_tokens(no_key):
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    def gen():
        return "Tell me something interesting"

    tokens = list(gen())
    assert len(tokens) > 0
    assert all(isinstance(t, str) and t for t in tokens)


def test_sync_stream_tokens_reconstruct_response(no_key):
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    def gen():
        return "Tell me something"

    tokens = list(gen())
    full   = "".join(tokens)
    assert mc.called("log_llm_call")
    assert mc.call_args("log_llm_call")["response"] == full


def test_sync_stream_is_stream_flag_true(no_key):
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    def gen():
        return "hello"

    list(gen())
    assert mc.call_args("log_llm_call")["is_stream"] is True


def test_non_stream_is_stream_flag_false(no_key):
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=False, client=mc)
    def gen():
        return "hello"

    gen()
    assert mc.call_args("log_llm_call")["is_stream"] is False


def test_sync_stream_create_step_called(no_key):
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    def gen():
        return "hello"

    list(gen())
    assert mc.called("create_step")
    assert mc.call_args("create_step")["step_name"] == "gen"
    assert mc.call_args("create_step")["step_type"] == "llm_step"


def test_sync_stream_complete_step_called(no_key):
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    def gen():
        return "hello"

    tokens = list(gen())
    assert mc.called("complete_step")
    args = mc.call_args("complete_step")
    assert args["output_payload"]["response"] == "".join(tokens)


def test_sync_stream_ttft_is_non_negative(no_key):
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    def gen():
        return "hello"

    list(gen())
    ttft = mc.call_args("log_llm_call")["time_to_first_token_ms"]
    assert ttft is not None
    assert ttft >= 0


def test_sync_stream_ttft_less_than_total_latency(no_key):
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    def gen():
        return "hello"

    list(gen())
    args  = mc.call_args("log_llm_call")
    assert args["time_to_first_token_ms"] <= args["latency_ms"]


def test_sync_stream_logs_on_partial_consume(no_key):
    """Closing the generator early must still trigger the finally block."""
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    def gen():
        return "multi word response here for testing"

    g = gen()
    next(g)   # consume one token
    g.close() # force-close
    assert mc.called("log_llm_call")


def test_sync_stream_outside_workflow_yields(no_key):
    """Stream works with no active run_id; backend is not called."""
    token = set_run_id(None)  # type: ignore[arg-type]
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    def gen():
        return "hello"

    try:
        tokens = list(gen())
        assert len(tokens) > 0
        assert not mc.called("log_llm_call")
    finally:
        reset_run_id(token)


def test_sync_stream_anthropic_provider(no_key):
    """Anthropic provider falls through to mock stream when key is absent."""
    mc = MockClient()

    @llm_step(name="gen", model="claude-3-haiku", provider="anthropic",
              stream=True, client=mc)
    def gen():
        return "hello"

    tokens = list(gen())
    assert len(tokens) > 0
    assert mc.call_args("log_llm_call")["provider"] == "anthropic"


# ── async streaming ────────────────────────────────────────────────────────────

def test_async_stream_is_async_gen_function(no_key):
    @llm_step(name="gen", model="gpt-4o-mini", stream=True)
    async def gen():
        return "hello"

    assert inspect.isasyncgenfunction(gen)


def test_async_stream_yields_tokens(no_key):
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    async def gen():
        return "Tell me something"

    async def collect():
        return [t async for t in gen()]

    tokens = run(collect())
    assert len(tokens) > 0


def test_async_stream_complete_step_called(no_key):
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    async def gen():
        return "hello"

    async def collect():
        return [t async for t in gen()]

    run(collect())
    assert mc.called("complete_step")


def test_async_stream_ttft_measured(no_key):
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    async def gen():
        return "hello"

    async def collect():
        return [t async for t in gen()]

    run(collect())
    assert mc.call_args("log_llm_call")["time_to_first_token_ms"] is not None


def test_async_stream_is_stream_flag(no_key):
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    async def gen():
        return "hello"

    async def collect():
        return [t async for t in gen()]

    run(collect())
    assert mc.call_args("log_llm_call")["is_stream"] is True


def test_async_stream_tokens_reconstruct_response(no_key):
    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    async def gen():
        return "Tell me something"

    async def collect():
        return [t async for t in gen()]

    tokens = run(collect())
    full   = "".join(tokens)
    assert mc.call_args("log_llm_call")["response"] == full


# ── OpenAI mocked streaming ────────────────────────────────────────────────────

def test_openai_stream_yields_real_chunks(mocker, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    chunks = [_oai_chunk("Hello"), _oai_chunk(" world"), _oai_chunk(in_tokens=10, out_tokens=5)]

    mock_oa = mocker.MagicMock()
    mock_oa.chat.completions.create.return_value = iter(chunks)
    mocker.patch("openai.OpenAI", return_value=mock_oa)

    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    def gen():
        return "What is 2+2?"

    tokens = list(gen())
    assert tokens == ["Hello", " world"]


def test_openai_stream_token_counts_from_usage_chunk(mocker, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    chunks = [_oai_chunk("A"), _oai_chunk("B"), _oai_chunk(in_tokens=20, out_tokens=8)]

    mock_oa = mocker.MagicMock()
    mock_oa.chat.completions.create.return_value = iter(chunks)
    mocker.patch("openai.OpenAI", return_value=mock_oa)

    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    def gen():
        return "hello"

    list(gen())
    args = mc.call_args("log_llm_call")
    assert args["input_tokens"]  == 20
    assert args["output_tokens"] == 8
    assert args["total_tokens"]  == 28


def test_openai_stream_cost_estimated(mocker, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    chunks = [_oai_chunk("hi"), _oai_chunk(in_tokens=100, out_tokens=50)]

    mock_oa = mocker.MagicMock()
    mock_oa.chat.completions.create.return_value = iter(chunks)
    mocker.patch("openai.OpenAI", return_value=mock_oa)

    mc = MockClient()

    @llm_step(name="gen", model="gpt-4o-mini", stream=True, client=mc)
    def gen():
        return "hello"

    list(gen())
    cost = mc.call_args("log_llm_call")["estimated_cost"]
    assert cost is not None
    assert cost > 0
