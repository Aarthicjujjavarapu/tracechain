"""
Optional OpenTelemetry integration for TraceChain.

Install extras:
    pip install 'tracechain[otel]'

Quick setup:
    from tracechain.otel import configure_otel
    configure_otel("my-service")                   # console exporter
    configure_otel("my-service", exporter="otlp")  # Jaeger / Tempo / Grafana

Bring your own TracerProvider:
    from opentelemetry.sdk.trace import TracerProvider
    configure_otel("my-service", tracer_provider=my_provider)

Span hierarchy and GenAI semantic-convention attributes
────────────────────────────────────────────────────────
  workflow.<name>               tracechain.workflow.name
    └─ step.<name>              tracechain.step.name / .type
         └─ llm.<name>         gen_ai.system / gen_ai.request.model
                                gen_ai.request.temperature
                                gen_ai.usage.input_tokens
                                gen_ai.usage.output_tokens
                                tracechain.llm.estimated_cost
                                tracechain.llm.latency_ms
                                tracechain.llm.is_stream
                                tracechain.llm.ttft_ms  (streaming only)
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator, Optional, Tuple

try:
    from opentelemetry import trace as _otel_trace
    from opentelemetry import context as _otel_context
    from opentelemetry.trace import StatusCode as _StatusCode
    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False  # type: ignore[assignment]

_TRACER_NAME = "tracechain"


def configure_otel(
    service_name: str = "tracechain",
    *,
    exporter: Optional[str] = "console",
    endpoint: str = "http://localhost:4317",
    tracer_provider: Any = None,
) -> None:
    """
    Install a TracerProvider so TraceChain decorators emit OTEL spans.

    Args:
        service_name:    ``service.name`` resource attribute on all spans.
        exporter:        ``"console"`` (default) or ``"otlp"``.
                         Ignored when *tracer_provider* is given.
        endpoint:        OTLP gRPC endpoint (only used when ``exporter="otlp"``).
        tracer_provider: Pre-configured provider; all other args are ignored.
    """
    if not _OTEL_AVAILABLE:
        raise ImportError(
            "opentelemetry-api not installed. "
            "Run: pip install 'tracechain[otel]'"
        )

    if tracer_provider is not None:
        _otel_trace.set_tracer_provider(tracer_provider)
        return

    try:
        from opentelemetry.sdk.resources import Resource, SERVICE_NAME
        from opentelemetry.sdk.trace import TracerProvider as _SdkTracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        raise ImportError(
            "opentelemetry-sdk not installed. "
            "Run: pip install 'tracechain[otel]'"
        ) from None

    resource = Resource.create({SERVICE_NAME: service_name})
    provider = _SdkTracerProvider(resource=resource)

    if exporter == "otlp":
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        except ImportError:
            raise ImportError(
                "OTLP exporter not installed. "
                "Run: pip install opentelemetry-exporter-otlp-proto-grpc"
            ) from None
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint)))
    else:
        from opentelemetry.sdk.trace.export import ConsoleSpanExporter
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    _otel_trace.set_tracer_provider(provider)


# ── internal helpers used by workflow / step / llm ────────────────────────────

@contextmanager
def _otel_span(
    name: str,
    attributes: Optional[dict[str, Any]] = None,
) -> Generator[Any, None, None]:
    """Open an active OTEL span for the block duration; yields None when OTEL is absent."""
    if not _OTEL_AVAILABLE:
        yield None
        return
    tracer = _otel_trace.get_tracer(_TRACER_NAME)
    with tracer.start_as_current_span(name) as span:
        _set_attrs(span, attributes)
        yield span


def _otel_set_ok(span: Any) -> None:
    if span is None or not _OTEL_AVAILABLE:
        return
    span.set_status(_StatusCode.OK)  # type: ignore[arg-type]


def _otel_set_error(span: Any, exc: Exception) -> None:
    if span is None or not _OTEL_AVAILABLE:
        return
    span.record_exception(exc)
    span.set_status(_StatusCode.ERROR, str(exc))  # type: ignore[arg-type]


def _otel_start_span(
    name: str,
    attributes: Optional[dict[str, Any]] = None,
) -> Tuple[Any, Any]:
    """
    Start a span and attach it as the active context for the current async chain.
    Returns (span, context_token) — pass both to _otel_end_span.
    Using context.attach/detach means child spans created inside a generator
    will correctly appear as children of this span in Jaeger/Grafana.
    """
    if not _OTEL_AVAILABLE:
        return None, None
    tracer = _otel_trace.get_tracer(_TRACER_NAME)
    span = tracer.start_span(name)
    _set_attrs(span, attributes)
    ctx = _otel_trace.set_span_in_context(span)
    token = _otel_context.attach(ctx)
    return span, token


def _otel_end_span(
    span: Any,
    token: Any,
    *,
    error: Optional[Exception] = None,
) -> None:
    """Detach context and end a manually-started span (call in finally block)."""
    if span is None or not _OTEL_AVAILABLE:
        return
    if token is not None:
        _otel_context.detach(token)
    if error is not None:
        span.record_exception(error)
        span.set_status(_StatusCode.ERROR, str(error))  # type: ignore[arg-type]
    else:
        span.set_status(_StatusCode.OK)  # type: ignore[arg-type]
    span.end()


def _set_attrs(span: Any, attributes: Optional[dict[str, Any]]) -> None:
    if not attributes or span is None:
        return
    for k, v in attributes.items():
        if v is not None:
            try:
                span.set_attribute(k, v)
            except Exception:
                pass
