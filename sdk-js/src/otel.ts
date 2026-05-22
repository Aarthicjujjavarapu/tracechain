/**
 * Optional OpenTelemetry integration for @tracechain/sdk.
 *
 * Install:
 *   npm install @opentelemetry/api @opentelemetry/sdk-trace-node
 *
 * Usage (batteries-included):
 *   import { configureOtel } from "@tracechain/sdk";
 *   configureOtel({ serviceName: "my-service" });           // console
 *   configureOtel({ serviceName: "my-service", exporter: "otlp" });
 *
 * Bring your own tracer (preferred for production):
 *   import { trace } from "@opentelemetry/api";
 *   import { configureOtelTracer } from "@tracechain/sdk";
 *   configureOtelTracer(trace.getTracer("my-service"));
 *
 * Span hierarchy and GenAI semantic-convention attributes
 * ────────────────────────────────────────────────────────
 *   workflow.<name>           tracechain.workflow.name
 *     └─ step.<name>         tracechain.step.name / .type
 *          └─ llm.<name>     gen_ai.system / gen_ai.request.model
 *                            gen_ai.request.temperature
 *                            tracechain.llm.is_stream
 */

// Minimal structural interface — compatible with @opentelemetry/api Span
export interface OtelSpan {
  setAttribute(key: string, value: string | number | boolean): void;
  setAttributes(attrs: Record<string, string | number | boolean>): void;
  setStatus(status: { code: number; message?: string }): void;
  recordException(error: Error | { message: string }): void;
  end(): void;
}

// Minimal structural interface — compatible with @opentelemetry/api Tracer
export interface OtelTracer {
  startActiveSpan<T>(name: string, fn: (span: OtelSpan) => T): T;
}

export interface ConfigureOtelOptions {
  serviceName?: string;
  exporter?: "console" | "otlp";
  endpoint?: string;
}

const _STATUS_OK = 1;    // SpanStatusCode.OK
const _STATUS_ERROR = 2; // SpanStatusCode.ERROR

let _tracer: OtelTracer | null = null;

/**
 * Configure OTEL using the Node.js SDK. Synchronous — no awaiting needed.
 * Requires @opentelemetry/sdk-trace-node to be installed.
 */
export function configureOtel(options: ConfigureOtelOptions = {}): void {
  // eslint-disable-next-line @typescript-eslint/no-require-imports
  let api: any;
  try {
    api = require("@opentelemetry/api");
  } catch {
    throw new Error(
      "@opentelemetry/api not installed. Run: npm install @opentelemetry/api @opentelemetry/sdk-trace-node",
    );
  }

  let sdkBase: any;
  try {
    sdkBase = require("@opentelemetry/sdk-trace-base");
  } catch {
    throw new Error(
      "@opentelemetry/sdk-trace-base not installed. Run: npm install @opentelemetry/sdk-trace-node",
    );
  }

  let sdkNode: any;
  try {
    sdkNode = require("@opentelemetry/sdk-trace-node");
  } catch {
    throw new Error(
      "@opentelemetry/sdk-trace-node not installed. Run: npm install @opentelemetry/sdk-trace-node",
    );
  }

  const { NodeTracerProvider } = sdkNode;
  const { SimpleSpanProcessor, ConsoleSpanExporter } = sdkBase;

  const provider = new NodeTracerProvider();

  if (options.exporter === "otlp") {
    let otlpExporter: any;
    try {
      otlpExporter = require("@opentelemetry/exporter-trace-otlp-http");
    } catch {
      throw new Error(
        "@opentelemetry/exporter-trace-otlp-http not installed. " +
          "Run: npm install @opentelemetry/exporter-trace-otlp-http",
      );
    }
    provider.addSpanProcessor(
      new SimpleSpanProcessor(
        new otlpExporter.OTLPTraceExporter({
          url: options.endpoint ?? "http://localhost:4318/v1/traces",
        }),
      ),
    );
  } else {
    provider.addSpanProcessor(new SimpleSpanProcessor(new ConsoleSpanExporter()));
  }

  provider.register();
  _tracer = api.trace.getTracer("tracechain", "0.1.0") as OtelTracer;
}

/**
 * Wire in a pre-built tracer (e.g. from @opentelemetry/api directly).
 * This is the preferred approach in production — let your app own the
 * TracerProvider, and pass the tracer here.
 */
export function configureOtelTracer(tracer: OtelTracer): void {
  _tracer = tracer;
}

// ── internal helpers used by workflow / step / llm ────────────────────────────

/**
 * Run `fn` inside an active OTEL span, or call it with `null` if OTEL is not
 * configured. The span is always ended in a finally block.
 *
 * Works for both sync and async callbacks — OTEL's startActiveSpan propagates
 * the span context through async continuations via AsyncLocalStorage.
 */
export function _activeSpan<T>(
  name: string,
  attributes: Record<string, string | number | boolean>,
  fn: (span: OtelSpan | null) => T,
): T {
  if (!_tracer) return fn(null);

  return _tracer.startActiveSpan(name, (span: OtelSpan) => {
    span.setAttributes(attributes);
    let result: T;
    try {
      result = fn(span);
    } catch (err) {
      _spanError(span, err);
      span.end();
      throw err;
    }
    // For async callbacks result is a Promise — attach finally to end span
    if (result instanceof Promise) {
      return result.then(
        (v) => { span.end(); return v; },
        (err) => { _spanError(span, err); span.end(); throw err; },
      ) as unknown as T;
    }
    span.end();
    return result;
  });
}

export function _spanOk(span: OtelSpan | null): void {
  span?.setStatus({ code: _STATUS_OK });
}

export function _spanError(span: OtelSpan | null, err: unknown): void {
  const msg = err instanceof Error ? err.message : String(err);
  span?.recordException(err instanceof Error ? err : new Error(msg));
  span?.setStatus({ code: _STATUS_ERROR, message: msg });
}
