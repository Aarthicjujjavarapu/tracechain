"use client";

import type { RunDiagnostics } from "@/types";
import Card from "@/components/ui/Card";
import RetryChainView from "./RetryChainView";
import LatencyPanel from "./LatencyPanel";
import TokenPanel from "./TokenPanel";
import ContextPanel from "./ContextPanel";

interface Props {
  diagnostics: RunDiagnostics;
}

export default function DiagnosticsPanel({ diagnostics }: Props) {
  const hasRetries  = diagnostics.retry_chains.length > 0;
  const hasWarnings = diagnostics.context_window.warning_count > 0;
  const hasCritical = diagnostics.context_window.critical_count > 0;
  const hasAnomalies= diagnostics.tokens.anomalies.length > 0;

  return (
    <div className="space-y-6">

      {/* Summary bar */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <DiagStat
          label="Retry Chains"
          value={diagnostics.retry_summary.total_chains.toString()}
          sub={`${diagnostics.retry_summary.total_attempts} attempts`}
          accent={hasRetries ? "amber" : "green"}
        />
        <DiagStat
          label="Bottleneck"
          value={diagnostics.latency.bottlenecks[0]?.name ?? "—"}
          sub={diagnostics.latency.bottlenecks[0] ? `${Math.round(diagnostics.latency.bottlenecks[0].duration_ms)}ms` : "none"}
          accent="blue"
        />
        <DiagStat
          label="Total Cost"
          value={`$${diagnostics.tokens.total_cost_usd.toFixed(5)}`}
          sub={`${diagnostics.tokens.total_tokens.toLocaleString()} tokens`}
          accent={hasAnomalies ? "amber" : "green"}
        />
        <DiagStat
          label="Context Warnings"
          value={diagnostics.context_window.warning_count.toString()}
          sub={hasCritical ? `${diagnostics.context_window.critical_count} critical` : "none critical"}
          accent={hasCritical ? "red" : hasWarnings ? "amber" : "green"}
        />
      </div>

      {/* Retry chains */}
      <Card>
        <h2 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
          Retry Chain Analysis
          {hasRetries && (
            <span className="text-[10px] text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
              {diagnostics.retry_summary.total_chains} retried
            </span>
          )}
        </h2>
        {hasRetries
          ? <RetryChainView chains={diagnostics.retry_chains} />
          : <p className="text-slate-500 text-sm">No retries in this run.</p>
        }
      </Card>

      {/* Latency */}
      <Card>
        <h2 className="text-sm font-medium text-slate-300 mb-4">Latency Breakdown</h2>
        <LatencyPanel report={diagnostics.latency} />
      </Card>

      {/* Tokens */}
      <Card>
        <h2 className="text-sm font-medium text-slate-300 mb-4">Token Usage &amp; Cost</h2>
        <TokenPanel report={diagnostics.tokens} />
      </Card>

      {/* Context window */}
      {hasWarnings && (
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-4 flex items-center gap-2">
            Context Window Diagnostics
            {hasCritical && (
              <span className="text-[10px] text-red-400 bg-red-500/10 px-2 py-0.5 rounded border border-red-500/20">
                {diagnostics.context_window.critical_count} critical
              </span>
            )}
          </h2>
          <ContextPanel warnings={diagnostics.context_window.warnings} />
        </Card>
      )}
    </div>
  );
}

function DiagStat({
  label, value, sub, accent,
}: {
  label: string; value: string; sub: string;
  accent: "green" | "amber" | "red" | "blue" | "default";
}) {
  const colors = {
    green:   "text-emerald-400",
    amber:   "text-amber-400",
    red:     "text-red-400",
    blue:    "text-sky-400",
    default: "text-white",
  };
  return (
    <Card padding="sm">
      <p className="text-[11px] text-slate-500 uppercase tracking-wider mb-1">{label}</p>
      <p className={`text-lg font-bold truncate ${colors[accent]}`}>{value}</p>
      <p className="text-[11px] text-slate-600 mt-0.5">{sub}</p>
    </Card>
  );
}
