import { describe, it, expect, vi, beforeEach } from "vitest";
import { TraceChainClient, getDefaultClient } from "../client.js";

const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

function okJson(body: unknown) {
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve(body),
  });
}

beforeEach(() => {
  mockFetch.mockReset();
});

describe("TraceChainClient", () => {
  it("createRun returns run id from response", async () => {
    mockFetch.mockResolvedValueOnce(okJson({ id: "run-123" }));
    const client = new TraceChainClient({ baseUrl: "http://test" });
    const id = await client.createRun("wf", { x: 1 });
    expect(id).toBe("run-123");
  });

  it("createRun returns null on network error", async () => {
    mockFetch.mockRejectedValueOnce(new Error("network"));
    const client = new TraceChainClient({ baseUrl: "http://test" });
    const id = await client.createRun("wf", {});
    expect(id).toBeNull();
  });

  it("createRun returns null on non-ok response", async () => {
    mockFetch.mockResolvedValueOnce({ ok: false });
    const client = new TraceChainClient({ baseUrl: "http://test" });
    const id = await client.createRun("wf", {});
    expect(id).toBeNull();
  });

  it("createRun is silent when disabled", async () => {
    const client = new TraceChainClient({ baseUrl: "http://test", enabled: false });
    const id = await client.createRun("wf", {});
    expect(id).toBeNull();
    expect(mockFetch).not.toHaveBeenCalled();
  });

  it("completeRun posts to correct path", async () => {
    mockFetch.mockResolvedValueOnce(okJson({}));
    const client = new TraceChainClient({ baseUrl: "http://test" });
    await client.completeRun("run-1", { answer: 42 });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://test/runs/run-1/complete",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("failRun posts to correct path", async () => {
    mockFetch.mockResolvedValueOnce(okJson({}));
    const client = new TraceChainClient({ baseUrl: "http://test" });
    await client.failRun("run-1", "oops");
    expect(mockFetch).toHaveBeenCalledWith(
      "http://test/runs/run-1/fail",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("createStep returns step id", async () => {
    mockFetch.mockResolvedValueOnce(okJson({ id: "step-99" }));
    const client = new TraceChainClient({ baseUrl: "http://test" });
    const id = await client.createStep("run-1", "search", "generic", {});
    expect(id).toBe("step-99");
  });

  it("logLlmCall posts to correct path", async () => {
    mockFetch.mockResolvedValueOnce(okJson({}));
    const client = new TraceChainClient({ baseUrl: "http://test" });
    await client.logLlmCall({
      runId: "run-1", provider: "openai", model: "gpt-4o",
      prompt: "hi", latencyMs: 100, temperature: 1, status: "success",
    });
    expect(mockFetch).toHaveBeenCalledWith(
      "http://test/runs/run-1/llm-calls",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("baseUrl trailing slash is stripped", () => {
    const client = new TraceChainClient({ baseUrl: "http://test/" });
    expect(client.config.baseUrl).toBe("http://test");
  });

  it("getDefaultClient returns a singleton", () => {
    const a = getDefaultClient();
    const b = getDefaultClient();
    expect(a).toBe(b);
  });
});
