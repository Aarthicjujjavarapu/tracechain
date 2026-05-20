"""
OTEL integration tests using InMemorySpanExporter — no Jaeger required.
Requires: pip install 'tracechain[otel]'

The OTEL SDK forbids overriding a global TracerProvider after first install,
so each test patches get_tracer() on the module object to route to a fresh
per-test provider, bypassing the global entirely.
"""
import asyncio
import pytest
from unittest.mock import patch

pytest.importorskip("opentelemetry", reason="opentelemetry-sdk not installed")

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode

import tracechain
import tracechain.otel as _omod
import tracechain.workflow as _wf_mod
import tracechain.steps as _steps_mod
import tracechain.llm as _llm_mod
from tracechain.otel import configure_otel, _OTEL_AVAILABLE


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def exporter(monkeypatch):
    """
    Fresh in-memory exporter per test.
    Patches otel.py's get_tracer to use a local TracerProvider so tests
    are fully isolated from the global OTEL provider state.
    """
    exp = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exp))
    monkeypatch.setattr(_omod._otel_trace, "get_tracer", provider.get_tracer)
    yield exp
    exp.clear()


def _names(exp: InMemorySpanExporter) -> list[str]:
    return [s.name for s in exp.get_finished_spans()]


def _span(exp: InMemorySpanExporter, name: str):
    return next((s for s in exp.get_finished_spans() if s.name == name), None)


# ── configure_otel ─────────────────────────────────────────────────────────────

def test_otel_available():
    assert _OTEL_AVAILABLE is True


def test_configure_otel_raises_without_api(monkeypatch):
    monkeypatch.setattr(_omod, "_OTEL_AVAILABLE", False)
    with pytest.raises(ImportError, match="opentelemetry-api not installed"):
        configure_otel("svc")


# ── @workflow spans ────────────────────────────────────────────────────────────

def test_workflow_emits_span(exporter):
    @tracechain.workflow(name="test_wf")
    def wf(x):
        return x * 2

    with patch.object(_wf_mod, "get_default_client") as mc:
        mc.return_value.create_run.return_value = None
        wf(3)

    assert "workflow.test_wf" in _names(exporter)


def test_workflow_span_name_attribute(exporter):
    @tracechain.workflow(name="pipe")
    def wf():
        return "ok"

    with patch.object(_wf_mod, "get_default_client") as mc:
        mc.return_value.create_run.return_value = None
        wf()

    span = _span(exporter, "workflow.pipe")
    assert span is not None
    assert span.attributes.get("tracechain.workflow.name") == "pipe"


def test_workflow_status_ok(exporter):
    @tracechain.workflow(name="ok_wf")
    def wf():
        return "done"

    with patch.object(_wf_mod, "get_default_client") as mc:
        mc.return_value.create_run.return_value = None
        wf()

    assert _span(exporter, "workflow.ok_wf").status.status_code == StatusCode.OK


def test_workflow_status_error(exporter):
    @tracechain.workflow(name="fail_wf")
    def wf():
        raise ValueError("boom")

    with patch.object(_wf_mod, "get_default_client") as mc:
        mc.return_value.create_run.return_value = None
        with pytest.raises(ValueError):
            wf()

    assert _span(exporter, "workflow.fail_wf").status.status_code == StatusCode.ERROR


def test_async_workflow_emits_span(exporter):
    @tracechain.workflow(name="async_wf")
    async def wf():
        return "done"

    with patch.object(_wf_mod, "get_default_client") as mc:
        mc.return_value.create_run.return_value = None
        asyncio.run(wf())

    assert "workflow.async_wf" in _names(exporter)


# ── @step spans ────────────────────────────────────────────────────────────────

def test_step_emits_span(exporter):
    @tracechain.step(name="fetch")
    def fetch(q):
        return [q]

    with patch("tracechain.steps.get_default_client") as mc:
        mc.return_value.create_step.return_value = None
        fetch("hi")

    assert "step.fetch" in _names(exporter)


def test_step_span_attributes(exporter):
    @tracechain.step(name="embed")
    def embed():
        return []

    with patch("tracechain.steps.get_default_client") as mc:
        mc.return_value.create_step.return_value = None
        embed()

    span = _span(exporter, "step.embed")
    assert span.attributes.get("tracechain.step.name") == "embed"
    assert span.attributes.get("tracechain.step.type") == "step"


def test_step_error_span(exporter):
    @tracechain.step(name="bad_step")
    def bad():
        raise RuntimeError("step failed")

    with patch("tracechain.steps.get_default_client") as mc:
        mc.return_value.create_step.return_value = None
        with pytest.raises(RuntimeError):
            bad()

    assert _span(exporter, "step.bad_step").status.status_code == StatusCode.ERROR


# ── @llm_step spans ────────────────────────────────────────────────────────────

def test_llm_step_emits_span(exporter):
    @tracechain.llm_step(name="gen", model="gpt-4o-mini", provider="openai")
    def gen(q):
        return f"Answer: {q}"

    with patch("tracechain.llm.get_default_client") as mc:
        mc.return_value.create_step.return_value = None
        mc.return_value.log_llm_call.return_value = None
        gen("hello")

    assert "llm.gen" in _names(exporter)


def test_llm_step_genai_attributes(exporter):
    @tracechain.llm_step(name="ask", model="gpt-4o", provider="openai", temperature=0.5)
    def ask(q):
        return "answer"

    with patch("tracechain.llm.get_default_client") as mc:
        mc.return_value.create_step.return_value = None
        mc.return_value.log_llm_call.return_value = None
        ask("q")

    span = _span(exporter, "llm.ask")
    assert span.attributes.get("gen_ai.system") == "openai"
    assert span.attributes.get("gen_ai.request.model") == "gpt-4o"
    assert span.attributes.get("gen_ai.request.temperature") == 0.5
    assert span.attributes.get("tracechain.llm.is_stream") is False


# ── span nesting (workflow → step → llm) ──────────────────────────────────────

def test_workflow_step_llm_are_nested(exporter):
    """Spans must form a proper parent-child chain in the finished span list."""

    @tracechain.llm_step(name="gen", model="gpt-4o-mini")
    def gen(q):
        return f"Answer: {q}"

    @tracechain.step(name="retrieve")
    def retrieve(q):
        return [q]

    @tracechain.workflow(name="pipeline")
    def pipeline(q):
        retrieve(q)
        return gen(q)

    with patch.object(_wf_mod, "get_default_client") as wf_mc, \
         patch.object(_steps_mod, "get_default_client") as step_mc, \
         patch.object(_llm_mod, "get_default_client") as llm_mc:
        wf_mc.return_value.create_run.return_value = None
        step_mc.return_value.create_step.return_value = None
        llm_mc.return_value.create_step.return_value = None
        llm_mc.return_value.log_llm_call.return_value = None
        pipeline("hi")

    spans = {s.name: s for s in exporter.get_finished_spans()}
    assert set(spans) == {"workflow.pipeline", "step.retrieve", "llm.gen"}

    wf = spans["workflow.pipeline"]
    step = spans["step.retrieve"]
    llm = spans["llm.gen"]

    assert step.parent.span_id == wf.context.span_id
    assert llm.parent.span_id == wf.context.span_id


# ── streaming spans ────────────────────────────────────────────────────────────

def test_streaming_emits_span(exporter):
    @tracechain.llm_step(name="stream_gen", model="gpt-4o-mini", stream=True)
    def gen(q):
        return f"Answer: {q}"

    with patch("tracechain.llm.get_default_client") as mc:
        mc.return_value.create_step.return_value = None
        mc.return_value.log_llm_call.return_value = None
        list(gen("hello"))

    assert "llm.stream_gen" in _names(exporter)


def test_streaming_span_is_stream_true(exporter):
    @tracechain.llm_step(name="s", model="gpt-4o-mini", stream=True)
    def gen(q):
        return q

    with patch("tracechain.llm.get_default_client") as mc:
        mc.return_value.create_step.return_value = None
        mc.return_value.log_llm_call.return_value = None
        list(gen("q"))

    assert _span(exporter, "llm.s").attributes.get("tracechain.llm.is_stream") is True


def test_streaming_span_emitted_on_partial_consume(exporter):
    """Span must be recorded even when the consumer closes the generator early."""

    @tracechain.llm_step(name="partial", model="gpt-4o-mini", stream=True)
    def gen(q):
        return "one two three four five"

    with patch("tracechain.llm.get_default_client") as mc:
        mc.return_value.create_step.return_value = None
        mc.return_value.log_llm_call.return_value = None
        g = gen("q")
        next(g)
        g.close()

    assert "llm.partial" in _names(exporter)
