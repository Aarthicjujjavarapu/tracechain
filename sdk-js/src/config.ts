export interface TraceChainConfig {
  baseUrl: string;
  enabled: boolean;
  timeout: number; // ms
}

export function loadConfig(overrides?: Partial<TraceChainConfig>): TraceChainConfig {
  return {
    baseUrl: (
      overrides?.baseUrl ??
      process.env["TRACECHAIN_BACKEND_URL"] ??
      "http://localhost:8000"
    ).replace(/\/$/, ""),
    enabled:
      overrides?.enabled ??
      (process.env["TRACECHAIN_ENABLED"] ?? "true").toLowerCase() !== "false",
    timeout:
      overrides?.timeout ??
      Number(process.env["TRACECHAIN_TIMEOUT"] ?? "5000"),
  };
}
