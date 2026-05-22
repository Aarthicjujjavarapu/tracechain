import { describe, it, expect, vi } from "vitest";
import { step } from "../step.js";
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

describe("step()", () => {
  it("returns the function result", async () => {
    const client = makeClient();
    const fn = step("my_step", async (x: number) => x + 1, { client });
    const result = await withRunId("r1", () => fn(5));
    expect(result).toBe(6);
  });

  it("calls createStep and completeStep inside a run", async () => {
    const client = makeClient();
    const fn = step("my_step", async () => "ok", { client });
    await withRunId("r1", () => fn());
    expect(client.createStep).toHaveBeenCalledWith("r1", "my_step", "generic", expect.anything());
    expect(client.completeStep).toHaveBeenCalledWith("r1", "step-1", "ok", expect.any(Number), 0);
  });

  it("does not call createStep outside a run", async () => {
    const client = makeClient();
    const fn = step("my_step", async () => "ok", { client });
    await fn();
    expect(client.createStep).not.toHaveBeenCalled();
  });

  it("calls failStep on error and re-throws", async () => {
    const client = makeClient();
    const fn = step("my_step", async () => { throw new Error("step failed"); }, { client });
    await expect(withRunId("r1", () => fn())).rejects.toThrow("step failed");
    expect(client.failStep).toHaveBeenCalledWith("r1", "step-1", "step failed", 0);
  });

  it("uses custom stepType", async () => {
    const client = makeClient();
    const fn = step("fetch_data", async () => {}, { client, stepType: "retrieval" });
    await withRunId("r1", () => fn());
    expect(client.createStep).toHaveBeenCalledWith("r1", "fetch_data", "retrieval", expect.anything());
  });

  it("retries on failure up to retries limit", async () => {
    const client = makeClient();
    let calls = 0;
    const fn = step(
      "flaky_step",
      async () => {
        calls++;
        if (calls < 3) throw new Error("transient");
        return "ok";
      },
      { client, retries: 3, backoffMs: 1 },
    );
    const result = await withRunId("r1", () => fn());
    expect(result).toBe("ok");
    expect(calls).toBe(3);
    expect(client.completeStep).toHaveBeenCalled();
  });

  it("throws after exhausting retries and calls failStep", async () => {
    const client = makeClient();
    const fn = step(
      "always_fails",
      async () => { throw new Error("permanent"); },
      { client, retries: 2, backoffMs: 1 },
    );
    await expect(withRunId("r1", () => fn())).rejects.toThrow("permanent");
    expect(client.failStep).toHaveBeenCalledWith("r1", "step-1", "permanent", 2);
  });
});
