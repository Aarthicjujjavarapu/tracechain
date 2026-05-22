"use client";

import type { ContextWarning } from "@/types";

interface Props { warnings: ContextWarning[] }

export default function ContextPanel({ warnings }: Props) {
  return (
    <div className="space-y-3">
      {warnings.map((w, i) => (
        <div
          key={i}
          className={`flex items-start gap-3 rounded-lg px-4 py-3 border text-sm ${
            w.severity === "critical"
              ? "bg-red-500/5 border-red-500/20 text-red-300"
              : "bg-amber-500/5 border-amber-500/20 text-amber-300"
          }`}
        >
          <span className="text-lg shrink-0 mt-0.5">
            {w.severity === "critical" ? "🔴" : "⚠️"}
          </span>
          <div className="min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="font-medium truncate">{w.span_name}</span>
              <span className={`text-[10px] px-1.5 py-0.5 rounded border font-medium shrink-0 ${
                w.kind === "truncation_risk" ? "text-red-400 bg-red-500/10 border-red-500/20" :
                w.kind === "output_truncated" ? "text-amber-400 bg-amber-500/10 border-amber-500/20" :
                "text-violet-400 bg-violet-500/10 border-violet-500/20"
              }`}>
                {w.kind.replace(/_/g, " ")}
              </span>
              <span className="text-[11px] text-slate-500 font-mono shrink-0">{w.model}</span>
            </div>
            <p className="text-xs opacity-80 leading-relaxed">{w.message}</p>
          </div>
        </div>
      ))}
    </div>
  );
}
