---
id: opentelemetry
title: OpenTelemetry
sidebar_position: 4
---

# OpenTelemetry

TraceChain can emit properly-nested OTEL spans following the [GenAI semantic conventions](https://opentelemetry.io/docs/specs/semconv/gen-ai/). Connect to Jaeger, Grafana Tempo, or any OTLP-compatible backend.

## Installation

```bash
pip install 'tracechain[otel]'
```

## Quick setup

```python
from tracechain import configure_otel

# Console exporter — prints spans to stdout
configure_otel("my-service")

# OTLP exporter — sends to Jaeger / Tempo / Grafana
configure_otel("my-service", exporter="otlp", endpoint="http://localhost:4317")
```

Call `configure_otel()` **before** any `@workflow` / `@step` / `observe_llm` calls.

## Span hierarchy

```
workflow.<name>
  └─ step.<name>
       └─ llm.<name>
```

| Span | Key attributes |
|------|---------------|
| `workflow.<name>` | `tracechain.workflow.name` |
| `step.<name>` | `tracechain.step.name`, `tracechain.step.type` |
| `llm.<name>` | `gen_ai.system`, `gen_ai.request.model`, `gen_ai.usage.input_tokens`, `gen_ai.usage.output_tokens`, `tracechain.llm.is_stream`, `tracechain.llm.ttft_ms` |

## Jaeger quickstart

```bash
# Start Jaeger (all-in-one)
docker run -d --name jaeger \
  -p 16686:16686 \
  -p 4317:4317 \
  jaegertracing/all-in-one

# Run with OTLP export
OTEL_EXPORTER=otlp python examples/04_opentelemetry.py

# View traces at http://localhost:16686
# Service name: tracechain-example
```

## Bring your own TracerProvider

```python
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

exporter  = InMemorySpanExporter()
provider  = TracerProvider()
provider.add_span_processor(BatchSpanProcessor(exporter))

from tracechain import configure_otel
configure_otel("my-service", tracer_provider=provider)
```

## Configuration reference

| Parameter | Default | Description |
|---|---|---|
| `service_name` | `"tracechain"` | `service.name` on all spans |
| `exporter` | `"console"` | `"console"` or `"otlp"` |
| `endpoint` | `"http://localhost:4317"` | OTLP gRPC endpoint |
| `tracer_provider` | `None` | Pre-built provider; ignores other args |
