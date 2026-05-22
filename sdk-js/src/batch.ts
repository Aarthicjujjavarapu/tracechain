import { getDefaultClient, type TraceChainClient } from "./client.js";
import { getRunId, setStepId } from "./tracing.js";
import { _activeSpan } from "./otel.js";

// ── BatchResult ────────────────────────────────────────────────────────────────

export class BatchResult<T> {
  constructor(
    readonly results: (T | null)[],
    readonly errors:  (Error | null)[],
  ) {}

  get successCount(): number { return this.errors.filter((e) => e === null).length; }
  get failedCount():  number { return this.errors.filter((e) => e !== null).length; }

  get successResults(): T[] {
    return this.results.filter((r, i) => this.errors[i] === null) as T[];
  }

  [Symbol.iterator]() { return this.results[Symbol.iterator](); }
}

// ── Options ────────────────────────────────────────────────────────────────────

export interface BatchStepOptions {
  concurrency?: number;
  raiseOnError?: boolean;
  traceItems?: boolean;
  client?: TraceChainClient;
}

// ── batchStep ─────────────────────────────────────────────────────────────────

/**
 * Wrap a single-item async function so it processes a list of items,
 * creating a parent batch step and optional per-item child steps.
 *
 * @example
 * const embedDocs = batchStep("embed_docs", async (doc: string) => embed(doc), { concurrency: 5 });
 * const result = await embedDocs(["doc1", "doc2", "doc3"]);
 * console.log(result.successCount, result.failedCount);
 */
export function batchStep<TItem, TReturn>(
  name: string,
  fn: (item: TItem) => Promise<TReturn>,
  options: BatchStepOptions = {},
): (items: TItem[]) => Promise<BatchResult<TReturn>> {
  const concurrency  = options.concurrency  ?? Infinity;
  const raiseOnError = options.raiseOnError ?? false;
  const traceItems   = options.traceItems   ?? false;

  return async (items: TItem[]): Promise<BatchResult<TReturn>> => {
    const client = options.client ?? getDefaultClient();
    const runId  = getRunId();
    const n      = items.length;

    const batchId = runId
      ? await client.createStep(runId, name, "batch_step", { batch_size: n, concurrency })
      : null;

    if (batchId) setStepId(batchId);

    const results: (TReturn | null)[] = new Array(n).fill(null);
    const errors:  (Error | null)[]   = new Array(n).fill(null);
    const startMs = Date.now();

    return _activeSpan(
      `batch.${name}`,
      { "tracechain.batch.name": name, "tracechain.batch.size": n },
      async () => {
        async function processItem(idx: number): Promise<void> {
          const item = items[idx];

          const itemId = traceItems && runId && batchId
            ? await client.createStep(runId, `${name}[${idx}]`, "batch_item", {
                item: _safeJson(item), index: idx,
              })
            : null;
          if (itemId) setStepId(itemId);

          const t0 = Date.now();
          try {
            const r = await fn(item);
            results[idx] = r;
            if (itemId && runId) {
              await client.completeStep(runId, itemId, { result: _safeJson(r) }, Date.now() - t0);
            }
          } catch (err) {
            const e = err instanceof Error ? err : new Error(String(err));
            errors[idx] = e;
            if (itemId && runId) {
              await client.failStep(runId, itemId, e.message);
            }
          } finally {
            if (itemId) setStepId(batchId);
          }
        }

        // Run with concurrency cap via a semaphore-style queue
        const limit = Math.min(concurrency, n) || n;
        const indices = Array.from({ length: n }, (_, i) => i);
        const chunks: number[][] = [];
        for (let i = 0; i < indices.length; i += limit) {
          chunks.push(indices.slice(i, i + limit));
        }
        for (const chunk of chunks) {
          await Promise.all(chunk.map(processItem));
        }

        const duration = Date.now() - startMs;
        const failed   = errors.filter((e) => e !== null).length;
        const firstErr = errors.find((e) => e !== null) ?? null;

        if (runId && batchId) {
          if (!raiseOnError || firstErr === null) {
            await client.completeStep(runId, batchId, {
              batch_size: n,
              success_count: n - failed,
              failed_count: failed,
            }, duration);
          } else {
            await client.failStep(runId, batchId, `${failed}/${n} items failed`);
          }
          setStepId(null);
        }

        if (raiseOnError && firstErr) throw firstErr;

        return new BatchResult(results, errors);
      },
    );
  };
}

function _safeJson(v: unknown): unknown {
  try {
    JSON.stringify(v);
    return v;
  } catch {
    return String(v);
  }
}
