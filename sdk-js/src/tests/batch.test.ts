import { describe, it, expect, vi } from "vitest";
import { batchStep, BatchResult } from "../batch.js";
import { withRunId } from "../tracing.js";
import type { TraceChainClient } from "../client.js";

// ── helpers ────────────────────────────────────────────────────────────────────

let stepCounter = 0;

function makeClient(): TraceChainClient {
  stepCounter = 0;
  return {
    config: { baseUrl: "http://test", enabled: true, timeout: 5000 },
    createRun:    vi.fn().mockResolvedValue("run-1"),
    completeRun:  vi.fn().mockResolvedValue(undefined),
    failRun:      vi.fn().mockResolvedValue(undefined),
    createStep:   vi.fn().mockImplementation(() => Promise.resolve(`step-${++stepCounter}`)),
    completeStep: vi.fn().mockResolvedValue(undefined),
    failStep:     vi.fn().mockResolvedValue(undefined),
    logLlmCall:   vi.fn().mockResolvedValue(undefined),
  } as unknown as TraceChainClient;
}

// ── BatchResult interface ──────────────────────────────────────────────────────

describe("BatchResult", () => {
  it("counts successes and failures", () => {
    const r = new BatchResult([1, null, 3], [null, new Error("x"), null]);
    expect(r.successCount).toBe(2);
    expect(r.failedCount).toBe(1);
  });

  it("successResults filters out failed items", () => {
    const r = new BatchResult([1, null, 3], [null, new Error(), null]);
    expect(r.successResults).toEqual([1, 3]);
  });

  it("is iterable", () => {
    const r = new BatchResult([10, 20], [null, null]);
    expect([...r]).toEqual([10, 20]);
  });
});

// ── batchStep: basic ──────────────────────────────────────────────────────────

describe("batchStep()", () => {
  it("processes all items and returns BatchResult", async () => {
    const client = makeClient();
    const double = batchStep("double", async (x: number) => x * 2, { client });
    const result = await withRunId("r1", () => double([1, 2, 3]));
    expect(result.results).toEqual([2, 4, 6]);
    expect(result.successCount).toBe(3);
    expect(result.failedCount).toBe(0);
  });

  it("works outside a run (no backend calls)", async () => {
    const client = makeClient();
    const fn = batchStep("noop", async (x: number) => x + 1, { client });
    const result = await fn([10, 20]);
    expect(result.results).toEqual([11, 21]);
    expect(client.createStep).not.toHaveBeenCalled();
  });

  it("empty list returns empty BatchResult", async () => {
    const client = makeClient();
    const fn = batchStep("noop", async (x: number) => x, { client });
    const result = await withRunId("r1", () => fn([]));
    expect(result.successCount).toBe(0);
    expect(result.failedCount).toBe(0);
  });

  // ── backend integration ──────────────────────────────────────────────────

  it("creates one batch_step and one completeStep call", async () => {
    const client = makeClient();
    const fn = batchStep("embed", async (s: string) => s.toUpperCase(), { client });
    await withRunId("r1", () => fn(["a", "b"]));

    expect(client.createStep).toHaveBeenCalledTimes(1);
    expect(client.createStep).toHaveBeenCalledWith(
      "r1", "embed", "batch_step", expect.objectContaining({ batch_size: 2 }),
    );
    expect(client.completeStep).toHaveBeenCalledTimes(1);
    const [, , payload] = (client.completeStep as ReturnType<typeof vi.fn>).mock.calls[0];
    expect(payload).toMatchObject({ batch_size: 2, success_count: 2, failed_count: 0 });
  });

  it("traceItems creates N+1 steps", async () => {
    const client = makeClient();
    const fn = batchStep("embed", async (s: string) => s, { client, traceItems: true });
    await withRunId("r1", () => fn(["x", "y"]));
    expect(client.createStep).toHaveBeenCalledTimes(3); // 1 batch + 2 items
  });

  // ── error handling ────────────────────────────────────────────────────────

  it("collects partial failures when raiseOnError=false (default)", async () => {
    const client = makeClient();
    const fn = batchStep("risky", async (x: number) => {
      if (x < 0) throw new Error("negative");
      return x * 2;
    }, { client });
    const result = await withRunId("r1", () => fn([1, -1, 2]));
    expect(result.results[0]).toBe(2);
    expect(result.results[1]).toBeNull();
    expect(result.results[2]).toBe(4);
    expect(result.failedCount).toBe(1);
    expect(result.errors[1]).toBeInstanceOf(Error);
  });

  it("calls failStep for the batch when raiseOnError=true and a failure occurs", async () => {
    const client = makeClient();
    const fn = batchStep("strict", async (x: number) => {
      if (x === 2) throw new Error("boom");
      return x;
    }, { client, raiseOnError: true });
    await expect(withRunId("r1", () => fn([1, 2, 3]))).rejects.toThrow("boom");
    expect(client.failStep).toHaveBeenCalledTimes(1);
  });

  // ── concurrency ───────────────────────────────────────────────────────────

  it("respects concurrency cap", async () => {
    const client = makeClient();
    let active = 0;
    let peak   = 0;

    const fn = batchStep("para", async (_: number) => {
      active++;
      peak = Math.max(peak, active);
      await new Promise(r => setTimeout(r, 5));
      active--;
      return true;
    }, { client, concurrency: 2 });

    await withRunId("r1", () => fn([1, 2, 3, 4, 5]));
    expect(peak).toBeLessThanOrEqual(2);
  });
});
