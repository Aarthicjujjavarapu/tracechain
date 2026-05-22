import { getDefaultClient, type TraceChainClient } from "./client.js";
import { getRunId, getStepId, addLlmUsage } from "./tracing.js";
import { _activeSpan } from "./otel.js";

export interface LlmStepOptions {
  model?: string;
  provider?: string;
  temperature?: number;
  promptVersion?: string;
  client?: TraceChainClient;
}

export interface LlmCallResult<T> {
  result: T;
  inputTokens?: number;
  outputTokens?: number;
  estimatedCost?: number;
}

export function llmStep<TReturn extends string>(
  name: string,
  fn: (prompt: string) => Promise<TReturn | LlmCallResult<TReturn>>,
  options: LlmStepOptions = {},
): (prompt: string) => Promise<TReturn> {
  const model = options.model ?? "unknown";
  const provider = options.provider ?? "unknown";
  const temperature = options.temperature ?? 1.0;

  return (prompt: string): Promise<TReturn> =>
    _activeSpan(
      `llm.${name}`,
      {
        "gen_ai.system": provider,
        "gen_ai.request.model": model,
        "gen_ai.request.temperature": temperature,
        "tracechain.llm.is_stream": false,
      },
      async () => {
        const client = options.client ?? getDefaultClient();
        const runId = getRunId();
        const stepId = getStepId();
        const start = Date.now();

        try {
          const raw = await fn(prompt);
          const latencyMs = Date.now() - start;

          let response: TReturn;
          let inputTokens: number | null = null;
          let outputTokens: number | null = null;
          let totalTokens: number | null = null;
          let estimatedCost: number | null = null;

          if (typeof raw === "string") {
            response = raw as TReturn;
          } else {
            response = raw.result;
            inputTokens = raw.inputTokens ?? null;
            outputTokens = raw.outputTokens ?? null;
            estimatedCost = raw.estimatedCost ?? null;
            if (inputTokens != null && outputTokens != null) {
              totalTokens = inputTokens + outputTokens;
            }
          }

          if (estimatedCost != null || totalTokens != null) {
            addLlmUsage(estimatedCost ?? 0, totalTokens ?? 0);
          }

          if (runId) {
            await client.logLlmCall({
              runId,
              stepId: stepId ?? null,
              provider,
              model,
              prompt,
              response,
              inputTokens,
              outputTokens,
              totalTokens,
              estimatedCost,
              latencyMs,
              temperature,
              status: "success",
              promptVersion: options.promptVersion ?? null,
              isStream: false,
            });
          }

          return response;
        } catch (err) {
          const latencyMs = Date.now() - start;
          const errorMessage = err instanceof Error ? err.message : String(err);

          if (runId) {
            await client.logLlmCall({
              runId,
              stepId: stepId ?? null,
              provider,
              model,
              prompt,
              response: null,
              inputTokens: null,
              outputTokens: null,
              totalTokens: null,
              estimatedCost: null,
              latencyMs,
              temperature,
              status: "failed",
              errorMessage,
              promptVersion: options.promptVersion ?? null,
              isStream: false,
            });
          }

          throw err;
        }
      },
    );
}
