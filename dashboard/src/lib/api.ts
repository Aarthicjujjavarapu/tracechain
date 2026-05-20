import type {
  WorkflowRun, TraceStep, LLMCall, PromptVersion,
  EvaluationResult, HumanFeedback, OverviewMetrics,
} from "@/types";

const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

// ── core fetch ────────────────────────────────────────────────────────────────

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error((body as any).detail ?? "Request failed");
  }
  return res.json() as Promise<T>;
}

// ── public API surface ────────────────────────────────────────────────────────

export const api = {
  health: () => req<{ status: string; version: string }>("/health"),

  // ── runs ──────────────────────────────────────────────────────────────────
  runs: {
    list: (params?: Record<string, string>) => {
      const qs = params && Object.keys(params).length
        ? "?" + new URLSearchParams(params).toString()
        : "";
      return req<{ items: WorkflowRun[]; total: number }>(`/runs${qs}`);
    },
    get:     (id: string) => req<WorkflowRun>(`/runs/${id}`),
    complete:(id: string, body: { output_payload?: unknown; total_cost?: number; total_tokens?: number }) =>
      req<WorkflowRun>(`/runs/${id}/complete`, { method: "POST", body: JSON.stringify(body) }),
    fail:    (id: string, error_message: string) =>
      req<WorkflowRun>(`/runs/${id}/fail`, { method: "POST", body: JSON.stringify({ error_message }) }),
    replay:  (id: string) =>
      req<WorkflowRun>(`/runs/${id}/replay`, { method: "POST", body: JSON.stringify({}) }),
    replays: (id: string) =>
      req<{ items: WorkflowRun[]; total: number }>(`/runs?original_run_id=${id}&limit=50`),
    steps:       (id: string) => req<TraceStep[]>(`/runs/${id}/steps`),
    llmCalls:    (id: string) => req<LLMCall[]>(`/runs/${id}/llm-calls`),
    evaluations: (id: string) => req<EvaluationResult[]>(`/runs/${id}/evaluations`),
    feedback:    (id: string) => req<HumanFeedback[]>(`/runs/${id}/feedback`),
    submitFeedback: (id: string, body: { rating: number; comment?: string }) =>
      req<HumanFeedback>(`/runs/${id}/feedback`, { method: "POST", body: JSON.stringify(body) }),
  },

  // ── prompts ───────────────────────────────────────────────────────────────
  prompts: {
    list:    ()           => req<PromptVersion[]>("/prompts"),
    get:     (id: string) => req<PromptVersion>(`/prompts/${id}`),
    metrics: (id: string) => req<{
      prompt_id: string; prompt_name: string; version: string;
      usage_count: number; avg_latency_ms: number | null;
      avg_cost: number | null; success_rate: number; avg_quality_score: number | null;
    }>(`/prompts/${id}/metrics`),
    create: (body: { prompt_name: string; version: string; prompt_text: string; is_active?: boolean }) =>
      req<PromptVersion>("/prompts", { method: "POST", body: JSON.stringify(body) }),
  },

  // ── metrics ───────────────────────────────────────────────────────────────
  metrics: {
    overview: () => req<OverviewMetrics>("/metrics/overview"),

    latency: (days = 30) => req<{ workflow_name: string; avg_latency_ms: number; p95_latency_ms: number; run_count: number }[]>(
      `/metrics/latency?days=${days}`
    ),
    cost: (days = 30) => req<{ model: string; total_cost: number; call_count: number }[]>(
      `/metrics/cost?days=${days}`
    ),
    failures: (days = 30) => req<{ step_name: string; failure_count: number; total_count: number; failure_rate: number }[]>(
      `/metrics/failures?days=${days}`
    ),

    timeseries: {
      latency:     (days = 14) => req<{ date: string; value: number }[]>(`/metrics/timeseries/latency?days=${days}`),
      cost:        (days = 14) => req<{ date: string; value: number }[]>(`/metrics/timeseries/cost?days=${days}`),
      successRate: (days = 14) => req<{ date: string; value: number }[]>(`/metrics/timeseries/success-rate?days=${days}`),
      runs:        (days = 14) => req<{ date: string; value: number }[]>(`/metrics/timeseries/runs?days=${days}`),
      quality:     (days = 14) => req<{ date: string; value: number }[]>(`/metrics/timeseries/quality?days=${days}`),
      tokens:      (days = 14) => req<{ date: string; value: number }[]>(`/metrics/timeseries/tokens?days=${days}`),
    },
  },
} as const;
