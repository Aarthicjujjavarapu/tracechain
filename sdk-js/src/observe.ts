/**
 * observeLlm() — observer-pattern for LLM calls.
 *
 * The user owns the LLM call; TraceChain just watches. This unlocks the full
 * API surface of any client: multi-turn, tool calling, vision, JSON mode, etc.
 *
 * Usage:
 *   import { observeLlm, step } from "@tracechain/sdk";
 *
 *   const generate = step("generate", async (messages: Message[]) => {
 *     return observeLlm(
 *       { name: "gpt_call", model: "gpt-4o", provider: "openai",
 *         prompt: messages.at(-1)?.content },
 *       async (obs) => {
 *         const resp = await openai.chat.completions.create({
 *           model: "gpt-4o",
 *           messages,
 *           tools: [searchTool],        // full API — no restrictions
 *         });
 *         obs.record(resp);             // auto-extracts tokens, cost, text
 *         return resp.choices[0].message.content!;
 *       },
 *     );
 *   });
 *
 * Auto-extraction supports:
 *   - OpenAI ChatCompletion  (.choices + .usage.prompt_tokens)
 *   - Anthropic Message      (.content + .usage.input_tokens)
 *
 * Custom / local LLM:
 *   obs.record({
 *     response: result.text,
 *     inputTokens: result.promptTokens,
 *     outputTokens: result.completionTokens,
 *   });
 */

import { getDefaultClient, type TraceChainClient } from "./client.js";
import { getRunId, getStepId, addLlmUsage } from "./tracing.js";
import { _activeSpan } from "./otel.js";

export interface ObserveLlmOptions {
  name: string;
  model: string;
  provider?: string;
  temperature?: number;
  prompt?: string;
  promptVersion?: string;
  isStream?: boolean;
  client?: TraceChainClient;
}

export interface RecordOptions {
  response?: string;
  inputTokens?: number;
  outputTokens?: number;
  estimatedCost?: number;
  prompt?: string;
}

export interface LlmObserver {
  /** Record the LLM result — pass an OpenAI/Anthropic response object, or explicit options. */
  record(responseObj?: unknown, opts?: RecordOptions): void;
  /** Call on first non-empty streaming token to capture TTFT. Idempotent. */
  onChunk(): void;
}

/**
 * Run `fn` inside a traced LLM observation. The observer is passed to `fn`;
 * call `obs.record()` with the model response before `fn` returns.
 */
export async function observeLlm<T>(
  options: ObserveLlmOptions,
  fn: (obs: LlmObserver) => Promise<T>,
): Promise<T> {
  const provider = options.provider ?? "openai";
  const temperature = options.temperature ?? 1.0;

  return _activeSpan(
    `llm.${options.name}`,
    {
      "gen_ai.system": provider,
      "gen_ai.request.model": options.model,
      "gen_ai.request.temperature": temperature,
      "tracechain.llm.is_stream": options.isStream ?? false,
    },
    async () => {
      const client = options.client ?? getDefaultClient();
      const runId = getRunId();
      const stepId = getStepId();
      const start = Date.now();

      let response: string | null = null;
      let inputTokens: number | null = null;
      let outputTokens: number | null = null;
      let totalTokens: number | null = null;
      let estimatedCost: number | null = null;
      let ttftMs: number | null = null;
      let chunkSeen = false;
      let prompt = options.prompt ?? null;
      let error: string | null = null;

      const obs: LlmObserver = {
        record(responseObj?: unknown, opts: RecordOptions = {}) {
          if (responseObj != null && typeof responseObj === "object") {
            const extracted = extractFromResponse(responseObj as Record<string, unknown>);
            response   = opts.response    ?? extracted.response    ?? null;
            inputTokens  = opts.inputTokens  ?? extracted.inputTokens  ?? null;
            outputTokens = opts.outputTokens ?? extracted.outputTokens ?? null;
          } else {
            response     = opts.response    ?? null;
            inputTokens  = opts.inputTokens  ?? null;
            outputTokens = opts.outputTokens ?? null;
          }

          if (inputTokens != null && outputTokens != null) {
            totalTokens = inputTokens + outputTokens;
          }

          estimatedCost = opts.estimatedCost ??
            (inputTokens != null && outputTokens != null
              ? estimateCost(options.model, inputTokens, outputTokens)
              : null);

          if (opts.prompt != null) prompt = opts.prompt;
        },

        onChunk() {
          if (!chunkSeen) {
            ttftMs = Date.now() - start;
            chunkSeen = true;
          }
        },
      };

      try {
        const result = await fn(obs);
        const latencyMs = Date.now() - start;

        if (estimatedCost != null || totalTokens != null) {
          addLlmUsage(estimatedCost ?? 0, totalTokens ?? 0);
        }

        if (runId) {
          await client.logLlmCall({
            runId,
            stepId: stepId ?? null,
            provider,
            model: options.model,
            prompt: prompt ?? "",
            response,
            inputTokens,
            outputTokens,
            totalTokens,
            estimatedCost,
            latencyMs,
            temperature,
            status: "success",
            promptVersion: options.promptVersion ?? null,
            timeToFirstTokenMs: ttftMs,
            isStream: options.isStream ?? false,
          });
        }

        return result;
      } catch (err) {
        const latencyMs = Date.now() - start;
        error = err instanceof Error ? err.message : String(err);

        if (runId) {
          await client.logLlmCall({
            runId,
            stepId: stepId ?? null,
            provider,
            model: options.model,
            prompt: prompt ?? "",
            response: null,
            inputTokens: null,
            outputTokens: null,
            totalTokens: null,
            estimatedCost: null,
            latencyMs,
            temperature,
            status: "failed",
            errorMessage: error,
            promptVersion: options.promptVersion ?? null,
            timeToFirstTokenMs: null,
            isStream: options.isStream ?? false,
          });
        }

        throw err;
      }
    },
  );
}

// ── auto-extraction ────────────────────────────────────────────────────────────

function extractFromResponse(obj: Record<string, unknown>): {
  response?: string;
  inputTokens?: number;
  outputTokens?: number;
} {
  // OpenAI ChatCompletion: .choices[].message.content + .usage.prompt_tokens
  if (Array.isArray(obj["choices"]) && obj["usage"] != null) {
    const choices = obj["choices"] as Array<Record<string, unknown>>;
    const usage = obj["usage"] as Record<string, unknown>;
    const msg = choices[0]?.["message"] as Record<string, unknown> | undefined;
    return {
      response: typeof msg?.["content"] === "string" ? msg["content"] : undefined,
      inputTokens: typeof usage["prompt_tokens"] === "number" ? usage["prompt_tokens"] : undefined,
      outputTokens: typeof usage["completion_tokens"] === "number" ? usage["completion_tokens"] : undefined,
    };
  }

  // Anthropic Message: .content[].text + .usage.input_tokens
  if (Array.isArray(obj["content"]) && obj["usage"] != null) {
    const content = obj["content"] as Array<Record<string, unknown>>;
    const usage = obj["usage"] as Record<string, unknown>;
    return {
      response: typeof content[0]?.["text"] === "string" ? content[0]["text"] : undefined,
      inputTokens: typeof usage["input_tokens"] === "number" ? usage["input_tokens"] : undefined,
      outputTokens: typeof usage["output_tokens"] === "number" ? usage["output_tokens"] : undefined,
    };
  }

  return {};
}

// ── cost estimation ────────────────────────────────────────────────────────────

const COST_TABLE: Record<string, [number, number]> = {
  "gpt-4o":            [0.005,   0.015],
  "gpt-4o-mini":       [0.00015, 0.00060],
  "gpt-4-turbo":       [0.01,    0.03],
  "gpt-4":             [0.03,    0.06],
  "gpt-3.5-turbo":     [0.0005,  0.0015],
  "claude-opus-4":     [0.015,   0.075],
  "claude-sonnet-4":   [0.003,   0.015],
  "claude-haiku-4":    [0.0008,  0.004],
  "claude-3-5-sonnet": [0.003,   0.015],
  "claude-3-5-haiku":  [0.0008,  0.004],
  "claude-3-opus":     [0.015,   0.075],
  "claude-3-sonnet":   [0.003,   0.015],
  "claude-3-haiku":    [0.00025, 0.00125],
};

function estimateCost(model: string, inputTokens: number, outputTokens: number): number {
  const entry = Object.entries(COST_TABLE)
    .sort((a, b) => b[0].length - a[0].length)
    .find(([key]) => model.startsWith(key));
  if (entry) {
    const [, [inRate, outRate]] = entry;
    return Math.round(((inputTokens / 1000) * inRate + (outputTokens / 1000) * outRate) * 1e8) / 1e8;
  }
  return Math.round(((inputTokens + outputTokens) / 1000) * 0.002 * 1e8) / 1e8;
}
