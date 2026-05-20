/**
 * Context propagation via AsyncLocalStorage — the Node.js equivalent of
 * Python's contextvars. Each async call chain (workflow invocation) gets
 * its own isolated context, so concurrent workflows never bleed run IDs.
 */
import { AsyncLocalStorage } from "node:async_hooks";

interface TraceContext {
  runId: string | null;
  stepId: string | null;
  totalCost: number;
  totalTokens: number;
}

const _store = new AsyncLocalStorage<TraceContext>();

function _ctx(): TraceContext {
  return _store.getStore() ?? { runId: null, stepId: null, totalCost: 0, totalTokens: 0 };
}

export function getRunId(): string | null  { return _ctx().runId;  }
export function getStepId(): string | null { return _ctx().stepId; }

/** Run `fn` inside a fresh context with the given runId. */
export function withRunId<T>(runId: string, fn: () => T): T {
  const ctx: TraceContext = { runId, stepId: null, totalCost: 0, totalTokens: 0 };
  return _store.run(ctx, fn);
}

export function setStepId(stepId: string | null): void {
  const ctx = _store.getStore();
  if (ctx) ctx.stepId = stepId;
}

export function addLlmUsage(cost: number, tokens: number): void {
  const ctx = _store.getStore();
  if (ctx) { ctx.totalCost += cost; ctx.totalTokens += tokens; }
}

export function getRunTotals(): { cost: number; tokens: number } {
  const ctx = _ctx();
  return { cost: ctx.totalCost, tokens: ctx.totalTokens };
}
