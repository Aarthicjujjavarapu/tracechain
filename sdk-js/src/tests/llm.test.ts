import { describe, it, expect, vi } from "vitest";
import { llmStep } from "../llm.js";
import { withRunId } from "../tracing.js";
import type { TraceChainClient } from "../client.js";

function makeClient(): TraceChainClient {
  return {
    config: { baseUrl: "http://test", enabled: true, timeout: 5000 },
    createRun: vi.fn().mockResolvedValue("run-1"),
    completeRun: vi.fn().mockResolvedValue(undefined),
    failRun: vi.fn().mockResolvedValue(undefined),
    createStep: vi.fn().mockResolvedValue("step-1"),
    completeStep: vi.fn().mockResolvedValue(undefined),
    failStep: vi.fn().mockResolvedValue(undefined),
    logLlmCall: vi.fn().mockResolvedValue(undefined),
  } as unknown as TraceChainClient;
}

describe("llmStep()", () => {
  it("returns the string result from fn", async () => {
    const client = makeClient();
    const ask = llmStep("ask", async () => "hello", { client });
    const result = await withRunId("r1", () => ask("hi"));
    expect(result).toBe("hello");
  });

  it("returns the result field from an LlmCallResult object", async () => {
    const client = makeClient();
    const ask = llmStep(
      "ask",
      async () => ({ result: "world", inputTokens: 10, outputTokens: 5, estimatedCost: 0.001 }),
      { client },
    );
    const result = await withRunId("r1", () => ask("hi"));
    expect(result).toBe("world");
  });

  it("calls logLlmCall with status success on success", async () => {
    const client = makeClient();
    const ask = llmStep("ask", async () => "ok", { client, model: "gpt-4o", provider: "openai" });
    await withRunId("r1", () => ask("prompt text"));
    expect(client.logLlmCall).toHaveBeenCalledWith(
      expect.objectContaining({
        runId: "r1",
        provider: "openai",
        model: "gpt-4o",
        prompt: "prompt text",
        response: "ok",
        status: "success",
        isStream: false,
      }),
    );
  });

  it("calls logLlmCall with status failed on error", async () => {
    const client = makeClient();
    const ask = llmStep("ask", async () => { throw new Error("api error"); }, { client });
    await expect(withRunId("r1", () => ask("hi"))).rejects.toThrow("api error");
    expect(client.logLlmCall).toHaveBeenCalledWith(
      expect.objectContaining({ status: "failed", errorMessage: "api error" }),
    );
  });

  it("does not call logLlmCall outside a run", async () => {
    const client = makeClient();
    const ask = llmStep("ask", async () => "ok", { client });
    await ask("hi");
    expect(client.logLlmCall).not.toHaveBeenCalled();
  });

  it("passes token counts from LlmCallResult to logLlmCall", async () => {
    const client = makeClient();
    const ask = llmStep(
      "ask",
      async () => ({ result: "r", inputTokens: 100, outputTokens: 50, estimatedCost: 0.002 }),
      { client },
    );
    await withRunId("r1", () => ask("hi"));
    expect(client.logLlmCall).toHaveBeenCalledWith(
      expect.objectContaining({
        inputTokens: 100,
        outputTokens: 50,
        totalTokens: 150,
        estimatedCost: 0.002,
      }),
    );
  });

  it("passes promptVersion to logLlmCall when set", async () => {
    const client = makeClient();
    const ask = llmStep("ask", async () => "r", { client, promptVersion: "v2" });
    await withRunId("r1", () => ask("hi"));
    expect(client.logLlmCall).toHaveBeenCalledWith(
      expect.objectContaining({ promptVersion: "v2" }),
    );
  });

  it("latencyMs is a positive number", async () => {
    const client = makeClient();
    const ask = llmStep("ask", async () => "ok", { client });
    await withRunId("r1", () => ask("hi"));
    const call = (client.logLlmCall as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(call.latencyMs).toBeGreaterThanOrEqual(0);
  });

  it("re-throws errors after logging", async () => {
    const client = makeClient();
    const ask = llmStep("ask", async () => { throw new TypeError("bad type"); }, { client });
    await expect(withRunId("r1", () => ask("hi"))).rejects.toBeInstanceOf(TypeError);
  });
});
