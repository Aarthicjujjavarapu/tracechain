import { getDefaultClient, type TraceChainClient } from "./client.js";
import { withRunId, getRunTotals } from "./tracing.js";
import { _activeSpan } from "./otel.js";

export interface WorkflowOptions {
  client?: TraceChainClient;
  metadata?: Record<string, unknown>;
}

export function workflow<TArgs extends unknown[], TReturn>(
  name: string,
  fn: (...args: TArgs) => Promise<TReturn>,
  options: WorkflowOptions = {},
): (...args: TArgs) => Promise<TReturn> {
  return async (...args: TArgs): Promise<TReturn> => {
    const client = options.client ?? getDefaultClient();
    const runId = await client.createRun(name, { args }, options.metadata);

    if (!runId) {
      // Backend unavailable — run without tracing
      return fn(...args);
    }

    return _activeSpan(
      `workflow.${name}`,
      { "tracechain.workflow.name": name },
      () =>
        withRunId(runId, async () => {
          try {
            const result = await fn(...args);
            const { cost, tokens } = getRunTotals();
            await client.completeRun(
              runId,
              result as Record<string, unknown>,
              cost > 0 ? cost : undefined,
              tokens > 0 ? tokens : undefined,
            );
            return result;
          } catch (err) {
            await client.failRun(runId, err instanceof Error ? err.message : String(err));
            throw err;
          }
        }),
    );
  };
}
