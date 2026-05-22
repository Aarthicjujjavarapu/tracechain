import { describe, it, expect, vi, beforeEach } from "vitest";
import { workflow } from "../workflow.js";
import { getRunId } from "../tracing.js";
import type { TraceChainClient } from "../client.js";

function makeClient(runId = "run-1"): TraceChainClient {
  return {
    config: { baseUrl: "http://test", enabled: true, timeout: 5000 },
    createRun: vi.fn().mockResolvedValue(runId),
    completeRun: vi.fn().mockResolvedValue(undefined),
    failRun: vi.fn().mockResolvedValue(undefined),
    createStep: vi.fn().mockResolvedValue("step-1"),
    completeStep: vi.fn().mockResolvedValue(undefined),
    failStep: vi.fn().mockResolvedValue(undefined),
    logLlmCall: vi.fn().mockResolvedValue(undefined),
  } as unknown as TraceChainClient;
}

describe("workflow()", () => {
  it("calls createRun and completeRun on success", async () => {
    const client = makeClient();
    const fn = workflow("wf", async (x: number) => x * 2, { client });
    const result = await fn(5);
    expect(result).toBe(10);
    expect(client.createRun).toHaveBeenCalledWith("wf", { args: [5] }, undefined);
    expect(client.completeRun).toHaveBeenCalledWith("run-1", 10, undefined, undefined);
  });

  it("calls failRun on thrown error and re-throws", async () => {
    const client = makeClient();
    const fn = workflow("wf", async () => { throw new Error("boom"); }, { client });
    await expect(fn()).rejects.toThrow("boom");
    expect(client.failRun).toHaveBeenCalledWith("run-1", "boom");
    expect(client.completeRun).not.toHaveBeenCalled();
  });

  it("runId is visible inside the callback", async () => {
    const client = makeClient("my-run");
    let seenId: string | null = null;
    const fn = workflow("wf", async () => { seenId = getRunId(); }, { client });
    await fn();
    expect(seenId).toBe("my-run");
  });

  it("runId is null after the workflow exits", async () => {
    const client = makeClient();
    const fn = workflow("wf", async () => {}, { client });
    await fn();
    expect(getRunId()).toBeNull();
  });

  it("runs the function without tracing when createRun returns null", async () => {
    const client = makeClient();
    (client.createRun as ReturnType<typeof vi.fn>).mockResolvedValue(null);
    const fn = workflow("wf", async () => 42, { client });
    const result = await fn();
    expect(result).toBe(42);
    expect(client.completeRun).not.toHaveBeenCalled();
  });

  it("passes metadata to createRun", async () => {
    const client = makeClient();
    const meta = { env: "test" };
    const fn = workflow("wf", async () => {}, { client, metadata: meta });
    await fn();
    expect(client.createRun).toHaveBeenCalledWith("wf", expect.anything(), meta);
  });

  it("returns the function's result unchanged", async () => {
    const client = makeClient();
    const fn = workflow("wf", async () => ({ foo: "bar" }), { client });
    const result = await fn();
    expect(result).toEqual({ foo: "bar" });
  });
});
