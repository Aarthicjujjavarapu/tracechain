"""
Tests for observe_llm() — the observer-pattern LLM context manager.
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import tracechain
from tracechain.observe import _extract_from_response, observe_llm
from tracechain.tracing import set_run_id, reset_run_id


# ── helpers ───────────────────────────────────────────────────────────────────

def _openai_response(text="Hello", in_t=10, out_t=5):
    """Minimal duck-typed OpenAI ChatCompletion."""
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=text))],
        usage=SimpleNamespace(prompt_tokens=in_t, completion_tokens=out_t),
    )


def _anthropic_response(text="Hello", in_t=10, out_t=5):
    """Minimal duck-typed Anthropic Message."""
    return SimpleNamespace(
        content=[SimpleNamespace(text=text)],
        usage=SimpleNamespace(input_tokens=in_t, output_tokens=out_t),
    )


def _mock_client():
    mc = MagicMock()
    mc.log_llm_call.return_value = None
    return mc


def _run_id_context(run_id: str = "run-1"):
    """Context manager that sets/resets run_id."""
    class Ctx:
        def __enter__(self):
            self._token = set_run_id(run_id)
            return self
        def __exit__(self, *_):
            reset_run_id(self._token)
    return Ctx()


# ── _extract_from_response ────────────────────────────────────────────────────

class TestExtract:
    def test_openai_response(self):
        resp = _openai_response("The answer is 42", 15, 8)
        text, in_t, out_t = _extract_from_response(resp)
        assert text == "The answer is 42"
        assert in_t == 15
        assert out_t == 8

    def test_anthropic_response(self):
        resp = _anthropic_response("Sure!", 20, 4)
        text, in_t, out_t = _extract_from_response(resp)
        assert text == "Sure!"
        assert in_t == 20
        assert out_t == 4

    def test_unknown_object_returns_nones(self):
        assert _extract_from_response(SimpleNamespace(foo="bar")) == (None, None, None)

    def test_none_input(self):
        assert _extract_from_response(None) == (None, None, None)

    def test_openai_no_content(self):
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=None))],
            usage=SimpleNamespace(prompt_tokens=5, completion_tokens=3),
        )
        text, in_t, out_t = _extract_from_response(resp)
        assert text is None
        assert in_t == 5


# ── observe_llm basic ─────────────────────────────────────────────────────────

class TestObserveLlm:
    def test_returns_without_run_id(self):
        """Should silently succeed even when called outside a workflow."""
        client = _mock_client()
        with observe_llm("gen", model="gpt-4o", client=client) as obs:
            obs.record(_openai_response())
        client.log_llm_call.assert_not_called()

    def test_logs_llm_call_inside_run(self):
        client = _mock_client()
        with _run_id_context("r1"):
            with observe_llm("gen", model="gpt-4o", client=client) as obs:
                obs.record(_openai_response("hi", 10, 5))

        client.log_llm_call.assert_called_once()
        kw = client.log_llm_call.call_args.kwargs
        assert kw["run_id"] == "r1"
        assert kw["model"] == "gpt-4o"
        assert kw["response"] == "hi"
        assert kw["input_tokens"] == 10
        assert kw["output_tokens"] == 5
        assert kw["total_tokens"] == 15
        assert kw["status"] == "success"
        assert kw["is_stream"] is False

    def test_auto_extracts_anthropic(self):
        client = _mock_client()
        with _run_id_context():
            with observe_llm("gen", model="claude-3-5-sonnet", provider="anthropic",
                             client=client) as obs:
                obs.record(_anthropic_response("Bonjour", 12, 3))

        kw = client.log_llm_call.call_args.kwargs
        assert kw["response"] == "Bonjour"
        assert kw["input_tokens"] == 12
        assert kw["output_tokens"] == 3
        assert kw["provider"] == "anthropic"

    def test_manual_record_kwargs(self):
        """Custom / local LLM — pass explicit values, no response object."""
        client = _mock_client()
        with _run_id_context():
            with observe_llm("ollama", model="llama3", provider="ollama",
                             client=client) as obs:
                obs.record(response="ok", input_tokens=7, output_tokens=3)

        kw = client.log_llm_call.call_args.kwargs
        assert kw["response"] == "ok"
        assert kw["input_tokens"] == 7

    def test_override_auto_extracted_field(self):
        """Pass response_obj AND an override kwarg — kwarg wins."""
        client = _mock_client()
        with _run_id_context():
            with observe_llm("gen", model="gpt-4o", client=client) as obs:
                obs.record(_openai_response("auto", 10, 5), response="manual")

        kw = client.log_llm_call.call_args.kwargs
        assert kw["response"] == "manual"
        assert kw["input_tokens"] == 10  # still auto-extracted

    def test_prompt_and_prompt_version(self):
        client = _mock_client()
        with _run_id_context():
            with observe_llm("gen", model="gpt-4o", client=client,
                             prompt="hello", prompt_version="v3") as obs:
                obs.record(_openai_response())

        kw = client.log_llm_call.call_args.kwargs
        assert kw["prompt"] == "hello"
        assert kw["prompt_version"] == "v3"

    def test_prompt_can_be_passed_to_record(self):
        client = _mock_client()
        with _run_id_context():
            with observe_llm("gen", model="gpt-4o", client=client) as obs:
                obs.record(_openai_response(), prompt="from record")

        kw = client.log_llm_call.call_args.kwargs
        assert kw["prompt"] == "from record"

    def test_status_failed_on_exception(self):
        client = _mock_client()
        with _run_id_context():
            with pytest.raises(RuntimeError):
                with observe_llm("gen", model="gpt-4o", client=client) as obs:
                    raise RuntimeError("api error")

        kw = client.log_llm_call.call_args.kwargs
        assert kw["status"] == "failed"
        assert kw["error_message"] == "api error"

    def test_logs_even_when_record_not_called(self):
        """Timeout / network error — no record(), but we still log the failure."""
        client = _mock_client()
        with _run_id_context():
            with pytest.raises(TimeoutError):
                with observe_llm("gen", model="gpt-4o", client=client):
                    raise TimeoutError("timeout")

        client.log_llm_call.assert_called_once()
        assert client.log_llm_call.call_args.kwargs["status"] == "failed"

    def test_cost_is_estimated_from_tokens(self):
        client = _mock_client()
        with _run_id_context():
            with observe_llm("gen", model="gpt-4o-mini", client=client) as obs:
                obs.record(response="r", input_tokens=1000, output_tokens=500)

        kw = client.log_llm_call.call_args.kwargs
        assert kw["estimated_cost"] is not None
        assert kw["estimated_cost"] > 0

    def test_custom_estimated_cost_overrides_estimate(self):
        client = _mock_client()
        with _run_id_context():
            with observe_llm("gen", model="gpt-4o", client=client) as obs:
                obs.record(response="r", input_tokens=100, output_tokens=50,
                           estimated_cost=0.9999)

        assert client.log_llm_call.call_args.kwargs["estimated_cost"] == 0.9999

    def test_latency_ms_is_positive(self):
        client = _mock_client()
        with _run_id_context():
            with observe_llm("gen", model="gpt-4o", client=client) as obs:
                obs.record(_openai_response())

        assert client.log_llm_call.call_args.kwargs["latency_ms"] >= 0


# ── streaming ─────────────────────────────────────────────────────────────────

class TestStreaming:
    def test_ttft_recorded_on_first_chunk(self):
        client = _mock_client()
        with _run_id_context():
            with observe_llm("s", model="gpt-4o", is_stream=True, client=client) as obs:
                obs.on_chunk()
                obs.record(response="hello world", input_tokens=5, output_tokens=2)

        kw = client.log_llm_call.call_args.kwargs
        assert kw["time_to_first_token_ms"] is not None
        assert kw["time_to_first_token_ms"] >= 0
        assert kw["is_stream"] is True

    def test_ttft_none_if_no_chunks(self):
        client = _mock_client()
        with _run_id_context():
            with observe_llm("s", model="gpt-4o", is_stream=True, client=client) as obs:
                obs.record(response="", input_tokens=5, output_tokens=0)

        assert client.log_llm_call.call_args.kwargs["time_to_first_token_ms"] is None

    def test_on_chunk_is_idempotent(self):
        client = _mock_client()
        with _run_id_context():
            with observe_llm("s", model="gpt-4o", is_stream=True, client=client) as obs:
                obs.on_chunk()
                first_ttft = obs._ttft_ms
                obs.on_chunk()  # should not overwrite
                assert obs._ttft_ms == first_ttft
                obs.record(response="r", input_tokens=5, output_tokens=2)


# ── async ─────────────────────────────────────────────────────────────────────

class TestAsync:
    def test_async_context_manager_logs_call(self):
        client = _mock_client()

        async def run():
            with _run_id_context():
                async with observe_llm("gen", model="gpt-4o", client=client) as obs:
                    obs.record(_openai_response("async result", 8, 4))

        asyncio.run(run())
        kw = client.log_llm_call.call_args.kwargs
        assert kw["response"] == "async result"
        assert kw["status"] == "success"

    def test_async_logs_failure(self):
        client = _mock_client()

        async def run():
            with _run_id_context():
                with pytest.raises(ValueError):
                    async with observe_llm("gen", model="gpt-4o", client=client):
                        raise ValueError("async failure")

        asyncio.run(run())
        assert client.log_llm_call.call_args.kwargs["status"] == "failed"


# ── integration with @workflow + @step ────────────────────────────────────────

class TestIntegration:
    def test_observe_inside_workflow_and_step(self):
        """observe_llm picks up run_id from @workflow context automatically."""
        mock_tc = MagicMock()
        mock_tc.create_run.return_value = "run-integration"
        mock_tc.complete_run.return_value = None
        mock_tc.create_step.return_value = "step-1"
        mock_tc.complete_step.return_value = None
        mock_tc.log_llm_call.return_value = None

        @tracechain.workflow(name="pipe", client=mock_tc)
        def pipe(query: str) -> str:
            return generate(query)

        @tracechain.step(name="gen", client=mock_tc)
        def generate(query: str) -> str:
            with observe_llm("gpt_call", model="gpt-4o", client=mock_tc,
                             prompt=query) as obs:
                obs.record(_openai_response("answer", 20, 10))
            return "answer"

        result = pipe("what is AI?")

        assert result == "answer"
        mock_tc.log_llm_call.assert_called_once()
        kw = mock_tc.log_llm_call.call_args.kwargs
        assert kw["run_id"] == "run-integration"
        assert kw["model"] == "gpt-4o"
        assert kw["prompt"] == "what is AI?"
