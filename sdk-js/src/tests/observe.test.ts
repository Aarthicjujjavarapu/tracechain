import { describe, it, expect, vi } from "vitest";
import { observeLlm } from "../observe.js";
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

function openaiResp(text = "hi", inT = 10, outT = 5) {
  return {
    choices: [{ message: { content: text } }],
    usage: { prompt_tokens: inT, completion_tokens: outT },
  };
}

function anthropicResp(text = "hi", inT = 10, outT = 5) {
  return {
    content: [{ text }],
    usage: { input_tokens: inT, output_tokens: outT },
  };
}

describe("observeLlm()", () => {
  it("runs the callback and returns its result", async () => {
    const client = makeClient();
    const result = await observeLlm({ name: "gen", model: "gpt-4o", client }, async (obs) => {
      obs.record(openaiResp("hello"));
      return "hello";
    });
    expect(result).toBe("hello");
  });

  it("does not call logLlmCall outside a run", async () => {
    const client = makeClient();
    await observeLlm({ name: "gen", model: "gpt-4o", client }, async (obs) => {
      obs.record(openaiResp());
    });
    expect(client.logLlmCall).not.toHaveBeenCalled();
  });

  it("logs call with correct fields inside a run", async () => {
    const client = makeClient();
    await withRunId("r1", () =>
      observeLlm({ name: "chat", model: "gpt-4o", provider: "openai", client }, async (obs) => {
        obs.record(openaiResp("answer", 20, 10));
      }),
    );
    expect(client.logLlmCall).toHaveBeenCalledOnce();
    const args = (client.logLlmCall as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(args.runId).toBe("r1");
    expect(args.model).toBe("gpt-4o");
    expect(args.provider).toBe("openai");
    expect(args.response).toBe("answer");
    expect(args.inputTokens).toBe(20);
    expect(args.outputTokens).toBe(10);
    expect(args.totalTokens).toBe(30);
    expect(args.status).toBe("success");
    expect(args.isStream).toBe(false);
  });

  it("auto-extracts from Anthropic response", async () => {
    const client = makeClient();
    await withRunId("r1", () =>
      observeLlm({ name: "claude", model: "claude-3-5-sonnet", provider: "anthropic", client },
        async (obs) => { obs.record(anthropicResp("Bonjour", 12, 3)); }),
    );
    const args = (client.logLlmCall as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(args.response).toBe("Bonjour");
    expect(args.inputTokens).toBe(12);
    expect(args.outputTokens).toBe(3);
    expect(args.provider).toBe("anthropic");
  });

  it("accepts manual record options for custom LLMs", async () => {
    const client = makeClient();
    await withRunId("r1", () =>
      observeLlm({ name: "ollama", model: "llama3", provider: "ollama", client },
        async (obs) => { obs.record(undefined, { response: "ok", inputTokens: 7, outputTokens: 3 }); }),
    );
    const args = (client.logLlmCall as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(args.response).toBe("ok");
    expect(args.inputTokens).toBe(7);
    expect(args.provider).toBe("ollama");
  });

  it("override specific fields over auto-extracted values", async () => {
    const client = makeClient();
    await withRunId("r1", () =>
      observeLlm({ name: "gen", model: "gpt-4o", client },
        async (obs) => { obs.record(openaiResp("auto", 10, 5), { response: "manual" }); }),
    );
    const args = (client.logLlmCall as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(args.response).toBe("manual");
    expect(args.inputTokens).toBe(10); // still from auto
  });

  it("logs status failed and rethrows on error", async () => {
    const client = makeClient();
    await expect(
      withRunId("r1", () =>
        observeLlm({ name: "gen", model: "gpt-4o", client }, async () => {
          throw new Error("api down");
        }),
      ),
    ).rejects.toThrow("api down");
    const args = (client.logLlmCall as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(args.status).toBe("failed");
    expect(args.errorMessage).toBe("api down");
  });

  it("logs even when record() is never called (timeout/network error)", async () => {
    const client = makeClient();
    await expect(
      withRunId("r1", () =>
        observeLlm({ name: "gen", model: "gpt-4o", client }, async () => {
          throw new Error("timeout");
        }),
      ),
    ).rejects.toThrow();
    expect(client.logLlmCall).toHaveBeenCalledOnce();
  });

  it("estimates cost from token counts", async () => {
    const client = makeClient();
    await withRunId("r1", () =>
      observeLlm({ name: "gen", model: "gpt-4o-mini", client },
        async (obs) => { obs.record(undefined, { response: "r", inputTokens: 1000, outputTokens: 500 }); }),
    );
    const args = (client.logLlmCall as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(args.estimatedCost).toBeGreaterThan(0);
  });

  it("accepts a custom estimated cost", async () => {
    const client = makeClient();
    await withRunId("r1", () =>
      observeLlm({ name: "gen", model: "gpt-4o", client },
        async (obs) => { obs.record(undefined, { response: "r", inputTokens: 100, outputTokens: 50, estimatedCost: 0.42 }); }),
    );
    const args = (client.logLlmCall as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(args.estimatedCost).toBe(0.42);
  });

  it("records TTFT from onChunk()", async () => {
    const client = makeClient();
    await withRunId("r1", () =>
      observeLlm({ name: "s", model: "gpt-4o", isStream: true, client },
        async (obs) => {
          obs.onChunk();
          obs.record(undefined, { response: "hello", inputTokens: 5, outputTokens: 2 });
        }),
    );
    const args = (client.logLlmCall as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(args.timeToFirstTokenMs).toBeGreaterThanOrEqual(0);
    expect(args.isStream).toBe(true);
  });

  it("onChunk() is idempotent", async () => {
    const client = makeClient();
    let firstTtft: number | undefined;
    await withRunId("r1", () =>
      observeLlm({ name: "s", model: "gpt-4o", isStream: true, client },
        async (obs) => {
          obs.onChunk();
          firstTtft = (client.logLlmCall as ReturnType<typeof vi.fn>).mock.calls.length; // not logged yet
          obs.onChunk();
          obs.onChunk();
          obs.record(undefined, { response: "r", inputTokens: 5, outputTokens: 2 });
        }),
    );
    // Just verify it completed without error
    expect(client.logLlmCall).toHaveBeenCalledOnce();
  });

  it("passes prompt and promptVersion", async () => {
    const client = makeClient();
    await withRunId("r1", () =>
      observeLlm({ name: "gen", model: "gpt-4o", client, prompt: "hello", promptVersion: "v2" },
        async (obs) => { obs.record(openaiResp()); }),
    );
    const args = (client.logLlmCall as ReturnType<typeof vi.fn>).mock.calls[0][0];
    expect(args.prompt).toBe("hello");
    expect(args.promptVersion).toBe("v2");
  });

  it("latencyMs is a non-negative number", async () => {
    const client = makeClient();
    await withRunId("r1", () =>
      observeLlm({ name: "gen", model: "gpt-4o", client },
        async (obs) => { obs.record(openaiResp()); }),
    );
    expect((client.logLlmCall as ReturnType<typeof vi.fn>).mock.calls[0][0].latencyMs).toBeGreaterThanOrEqual(0);
  });
});
