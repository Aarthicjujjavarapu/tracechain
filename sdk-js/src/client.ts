/**
 * HTTP client — mirrors TraceChainClient from the Python SDK.
 * Every method is silent on failure: backend errors never crash the caller.
 */
import { loadConfig, type TraceChainConfig } from "./config.js";

function safeJson(value: unknown): unknown {
  if (value === null || value === undefined) return value;
  if (typeof value === "string" || typeof value === "number" ||
      typeof value === "boolean") return value;
  if (Array.isArray(value)) return value.map(safeJson);
  if (typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value as Record<string, unknown>).map(([k, v]) => [k, safeJson(v)])
    );
  }
  return String(value);
}

export class TraceChainClient {
  readonly config: TraceChainConfig;

  constructor(config?: Partial<TraceChainConfig>) {
    this.config = loadConfig(config);
  }

  private async post(path: string, body: unknown): Promise<unknown> {
    if (!this.config.enabled) return null;
    try {
      const res = await fetch(`${this.config.baseUrl}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(this.config.timeout),
      });
      if (!res.ok) return null;
      return res.json();
    } catch {
      return null;
    }
  }

  // ── runs ───────────────────────────────────────────────────────────────────

  async createRun(
    workflowName: string,
    inputPayload: Record<string, unknown>,
    metadata?: Record<string, unknown>,
  ): Promise<string | null> {
    const data = await this.post("/runs", {
      workflow_name: workflowName,
      input_payload: inputPayload,
      metadata: metadata ?? {},
    }) as Record<string, string> | null;
    return data?.id ?? null;
  }

  async completeRun(
    runId: string,
    outputPayload: unknown,
    totalCost?: number,
    totalTokens?: number,
  ): Promise<void> {
    const body: Record<string, unknown> = {};
    if (outputPayload !== undefined) body["output_payload"] = safeJson(outputPayload);
    if (totalCost   != null) body["total_cost"]   = totalCost;
    if (totalTokens != null) body["total_tokens"] = totalTokens;
    await this.post(`/runs/${runId}/complete`, body);
  }

  async failRun(runId: string, errorMessage: string): Promise<void> {
    await this.post(`/runs/${runId}/fail`, { error_message: errorMessage });
  }

  // ── steps ──────────────────────────────────────────────────────────────────

  async createStep(
    runId: string,
    stepName: string,
    stepType: string,
    inputPayload: Record<string, unknown>,
  ): Promise<string | null> {
    const data = await this.post(`/runs/${runId}/steps`, {
      step_name: stepName,
      step_type: stepType,
      input_payload: safeJson(inputPayload),
    }) as Record<string, string> | null;
    return data?.id ?? null;
  }

  async completeStep(
    runId: string, stepId: string,
    outputPayload: unknown, durationMs: number, retryCount = 0,
  ): Promise<void> {
    await this.post(`/runs/${runId}/steps/${stepId}/complete`, {
      output_payload: safeJson(outputPayload),
      duration_ms: durationMs,
      retry_count: retryCount,
    });
  }

  async failStep(
    runId: string, stepId: string,
    errorMessage: string, retryCount = 0,
  ): Promise<void> {
    await this.post(`/runs/${runId}/steps/${stepId}/fail`, {
      error_message: errorMessage,
      retry_count: retryCount,
    });
  }

  // ── llm calls ──────────────────────────────────────────────────────────────

  async logLlmCall(params: {
    runId: string; stepId?: string | null;
    provider: string; model: string;
    prompt: string; response?: string | null;
    inputTokens?: number | null; outputTokens?: number | null; totalTokens?: number | null;
    estimatedCost?: number | null; latencyMs: number; temperature: number;
    status: "success" | "failed"; errorMessage?: string | null;
    promptVersion?: string | null;
    timeToFirstTokenMs?: number | null; isStream?: boolean;
  }): Promise<void> {
    await this.post(`/runs/${params.runId}/llm-calls`, {
      step_id:                  params.stepId   ?? null,
      provider:                 params.provider,
      model:                    params.model,
      prompt:                   params.prompt,
      response:                 params.response ?? null,
      input_tokens:             params.inputTokens   ?? null,
      output_tokens:            params.outputTokens  ?? null,
      total_tokens:             params.totalTokens   ?? null,
      estimated_cost:           params.estimatedCost ?? null,
      latency_ms:               params.latencyMs,
      temperature:              params.temperature,
      status:                   params.status,
      error_message:            params.errorMessage      ?? null,
      prompt_version:           params.promptVersion     ?? null,
      time_to_first_token_ms:   params.timeToFirstTokenMs ?? null,
      is_stream:                params.isStream ?? false,
    });
  }
}

// ── default client singleton ──────────────────────────────────────────────────

let _default: TraceChainClient | null = null;

export function getDefaultClient(): TraceChainClient {
  if (!_default) _default = new TraceChainClient();
  return _default;
}
