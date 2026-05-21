"use client";

import type { TokenReport } from "@/types";

interface Props { report: TokenReport }

export default function TokenPanel({ report }: Props) {
  const maxCost = Math.max(...report.by_model.map((m) => m.cost_usd), 0.000001);

  return (
    <div className="space-y-5">
      {/* Summary row */}
      <div className="grid grid-cols-3 gap-4">
        <Metric label="Input Tokens"  value={report.total_input_tokens.toLocaleString()}  color="text-slate-300" />
        <Metric label="Output Tokens" value={report.total_output_tokens.toLocaleString()} color="text-violet-400" />
        <Metric label="Total Cost"    value={`$${report.total_cost_usd.toFixed(5)}`}      color="text-emerald-400" />
      </div>

      {/* Per-model breakdown */}
      {report.by_model.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-slate-500 uppercase tracking-wider">By Model</p>
          {report.by_model.map((model) => (
            <div key={`${model.provider}/${model.model}`} className="space-y-1">
              <div className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2">
                  <span className="text-slate-300 font-medium">{model.model}</span>
                  <span className="text-slate-600">{model.provider}</span>
                  <span className="text-slate-600">·</span>
                  <span className="text-slate-500">{model.call_count} call{model.call_count !== 1 ? "s" : ""}</span>
                </div>
                <div className="flex items-center gap-4 tabular-nums">
                  <span className="text-slate-500">{model.total_tokens.toLocaleString()} tok</span>
                  <span className="text-emerald-400 font-medium">${model.cost_usd.toFixed(5)}</span>
                </div>
              </div>
              <div className="h-1.5 bg-[#13151f] rounded overflow-hidden">
                <div
                  className="h-full rounded"
                  style={{
                    width: `${(model.cost_usd / maxCost) * 100}%`,
                    background: "linear-gradient(90deg, #8b5cf6, #4f6ef7)",
                  }}
                />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Anomalies */}
      {report.anomalies.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-slate-500 uppercase tracking-wider">Anomalies</p>
          {report.anomalies.map((msg, i) => (
            <div key={i}
              className="flex items-start gap-2 text-xs text-amber-400 bg-amber-500/5 border border-amber-500/15 rounded-lg px-3 py-2">
              <span className="shrink-0 mt-0.5">⚠</span>
              <span>{msg}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <div className="bg-[#13151f] rounded-lg p-3">
      <p className="text-[11px] text-slate-500 uppercase tracking-wider">{label}</p>
      <p className={`text-base font-bold mt-1 tabular-nums ${color}`}>{value}</p>
    </div>
  );
}
