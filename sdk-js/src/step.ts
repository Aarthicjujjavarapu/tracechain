import { getDefaultClient, type TraceChainClient } from "./client.js";
import { getRunId, setStepId } from "./tracing.js";
import { _activeSpan } from "./otel.js";

export interface StepOptions {
  stepType?: string;
  client?: TraceChainClient;
  retries?: number;
  backoffMs?: number;
}

export function step<TArgs extends unknown[], TReturn>(
  name: string,
  fn: (...args: TArgs) => Promise<TReturn>,
  options: StepOptions = {},
): (...args: TArgs) => Promise<TReturn> {
  const stepType = options.stepType ?? "generic";
  const maxRetries = options.retries ?? 0;
  const backoffMs = options.backoffMs ?? 500;

  return async (...args: TArgs): Promise<TReturn> => {
    const client = options.client ?? getDefaultClient();
    const runId = getRunId();
    const stepId = runId
      ? await client.createStep(runId, name, stepType, { args })
      : null;

    if (stepId) setStepId(stepId);

    return _activeSpan(
      `step.${name}`,
      { "tracechain.step.name": name, "tracechain.step.type": stepType },
      async () => {
        let attempt = 0;
        const start = Date.now();

        while (true) {
          try {
            const result = await fn(...args);
            if (runId && stepId) {
              await client.completeStep(runId, stepId, result as Record<string, unknown>, Date.now() - start, attempt);
              setStepId(null);
            }
            return result;
          } catch (err) {
            if (attempt < maxRetries) {
              attempt++;
              await new Promise(r => setTimeout(r, backoffMs * attempt));
              continue;
            }
            const msg = err instanceof Error ? err.message : String(err);
            if (runId && stepId) {
              await client.failStep(runId, stepId, msg, attempt);
              setStepId(null);
            }
            throw err;
          }
        }
      },
    );
  };
}
