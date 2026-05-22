import { describe, it, expect } from "vitest";
import {
  getRunId, getStepId, withRunId, setStepId,
  addLlmUsage, getRunTotals,
} from "../tracing.js";

describe("tracing context", () => {
  it("getRunId returns null outside a run", () => {
    expect(getRunId()).toBeNull();
  });

  it("getStepId returns null outside a run", () => {
    expect(getStepId()).toBeNull();
  });

  it("withRunId exposes runId inside the callback", async () => {
    let seen: string | null = null;
    await withRunId("abc", async () => { seen = getRunId(); });
    expect(seen).toBe("abc");
  });

  it("runId is null after withRunId exits", async () => {
    await withRunId("abc", async () => {});
    expect(getRunId()).toBeNull();
  });

  it("setStepId is visible inside the same run context", async () => {
    let seen: string | null = null;
    await withRunId("r1", async () => {
      setStepId("s1");
      seen = getStepId();
    });
    expect(seen).toBe("s1");
  });

  it("addLlmUsage accumulates and getRunTotals returns them", async () => {
    let totals = { cost: 0, tokens: 0 };
    await withRunId("r2", async () => {
      addLlmUsage(0.001, 100);
      addLlmUsage(0.002, 200);
      totals = getRunTotals();
    });
    expect(totals.cost).toBeCloseTo(0.003);
    expect(totals.tokens).toBe(300);
  });

  it("concurrent runs have isolated contexts", async () => {
    const results: string[] = [];
    await Promise.all([
      withRunId("run-A", async () => {
        await new Promise(r => setTimeout(r, 10));
        results.push(getRunId()!);
      }),
      withRunId("run-B", async () => {
        results.push(getRunId()!);
      }),
    ]);
    expect(results).toContain("run-A");
    expect(results).toContain("run-B");
    // neither should see the other's id
    expect(results.filter(r => r === "run-A").length).toBe(1);
    expect(results.filter(r => r === "run-B").length).toBe(1);
  });
});
