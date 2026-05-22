"use client";

import type { LatencyReport } from "@/types";

interface Props { report: LatencyReport }

export default function LatencyPanel({ report }: Props) {
  const maxDur = report.bottlenecks[0]?.duration_ms ?? 1;

  return (
    <div className="space-y-5">
      {/* Percentiles */}
      <div className="grid grid-cols-4 gap-4">
        {[
          ["Total",  `${Math.round(report.total_run_ms)}ms`],
          ["p50",    `${Math.round(report.p50_ms)}ms`],
          ["p95",    `${Math.round(report.p95_ms)}ms`],
          ["p99",    `${Math.round(report.p99_ms)}ms`],
        ].map(([label, value]) => (
          <div key={label} className="bg-[#13151f] rounded-lg p-3 text-center">
            <p className="text-[11px] text-slate-500 uppercase tracking-wider">{label}</p>
            <p className="text-base font-bold text-sky-400 mt-1">{value}</p>
          </div>
        ))}
      </div>

      {/* Critical path indicator */}
      {report.critical_path.length > 0 && (
        <div className="flex items-center gap-2 text-xs text-slate-500 bg-[#13151f] rounded-lg px-3 py-2">
          <span className="text-sky-400 font-medium">Critical path:</span>
          <span className="text-slate-400">{report.critical_path.length} spans</span>
          {report.slow_spans.length > 0 && (
            <>
              <span className="text-slate-700">·</span>
              <span className="text-amber-400">{report.slow_spans.length} slow spans</span>
              <span className="text-slate-600">(≥{Math.round(report.slow_threshold_ms)}ms)</span>
            </>
          )}
        </div>
      )}

      {/* Bottleneck bars */}
      <div className="space-y-2">
        <p className="text-xs text-slate-500 uppercase tracking-wider">Top Spans by Duration</p>
        {report.bottlenecks.slice(0, 8).map((span) => (
          <div key={span.span_id} className="flex items-center gap-3">
            <div className="w-3 shrink-0">
              {span.is_critical_path && (
                <span className="text-sky-400 text-[10px]" title="On critical path">●</span>
              )}
            </div>
            <div className="w-36 shrink-0 truncate">
              <span className="text-xs text-slate-300">{span.name}</span>
            </div>
            <div className="flex-1 h-4 bg-[#13151f] rounded overflow-hidden">
              <div
                className="h-full rounded transition-all"
                style={{
                  width: `${(span.duration_ms / maxDur) * 100}%`,
                  background: span.is_critical_path
                    ? "linear-gradient(90deg, #0ea5e9, #4f6ef7)"
                    : span.duration_ms >= report.slow_threshold_ms
                    ? "#f59e0b44"
                    : "#334155",
                }}
              />
            </div>
            <span className="text-xs text-slate-400 tabular-nums w-20 text-right shrink-0">
              {Math.round(span.duration_ms)}ms
              <span className="text-slate-600 ml-1">({Math.round(span.pct_of_run)}%)</span>
            </span>
            <span className={`text-[10px] w-16 text-right shrink-0 ${
              span.duration_ms >= report.slow_threshold_ms ? "text-amber-400" : "text-slate-700"
            }`}>
              {span.kind}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
