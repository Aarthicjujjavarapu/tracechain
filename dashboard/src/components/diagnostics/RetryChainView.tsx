"use client";

import { useState } from "react";
import type { RetryChain } from "@/types";

interface Props { chains: RetryChain[] }

export default function RetryChainView({ chains }: Props) {
  const [expanded, setExpanded] = useState<string | null>(null);

  return (
    <div className="space-y-3">
      {chains.map((chain) => (
        <div key={chain.span_id}
          className="border border-[#252b3b] rounded-lg overflow-hidden">

          {/* header */}
          <button
            className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-white/[0.02] transition-colors"
            onClick={() => setExpanded(expanded === chain.span_id ? null : chain.span_id)}
          >
            <span className={`w-2 h-2 rounded-full shrink-0 ${chain.exhausted ? "bg-red-500" : "bg-amber-400"}`} />
            <span className="text-sm text-slate-200 font-medium flex-1 truncate">{chain.span_name}</span>

            <div className="flex items-center gap-4 shrink-0">
              <Pill label={`${chain.attempt_count}× retried`} color="amber" />
              {chain.exhausted && <Pill label="EXHAUSTED" color="red" />}
              {chain.final_status === "ok" && <Pill label="RECOVERED" color="green" />}
              <span className="text-slate-600 text-xs tabular-nums">
                +{Math.round(chain.total_delay_ms)}ms delay
              </span>
              <span className="text-slate-600 text-xs">{expanded === chain.span_id ? "▲" : "▼"}</span>
            </div>
          </button>

          {/* expanded attempt list */}
          {expanded === chain.span_id && (
            <div className="border-t border-[#252b3b] bg-[#0d0f1a] px-4 py-3 space-y-2">
              {/* error types */}
              {chain.unique_errors.length > 0 && (
                <div className="flex gap-2 flex-wrap mb-3">
                  {chain.unique_errors.map((err) => (
                    <span key={err}
                      className="text-[10px] text-red-400 bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded font-mono">
                      {err}
                    </span>
                  ))}
                </div>
              )}

              {/* timeline */}
              <div className="relative pl-4">
                <div className="absolute left-[7px] top-2 bottom-2 w-px bg-[#252b3b]" />
                {chain.attempts.map((att, i) => (
                  <div key={i} className="relative flex items-start gap-3 pb-3 last:pb-0">
                    <span className="absolute left-[-9px] w-2 h-2 rounded-full bg-amber-500 border-2 border-[#0d0f1a] mt-1 shrink-0" />
                    <div className="min-w-0">
                      <p className="text-xs text-slate-400">
                        <span className="text-amber-400 font-medium">Attempt {att.attempt}</span>
                        <span className="text-slate-600 mx-2">·</span>
                        <span className="text-slate-500">{att.error_type}</span>
                        <span className="text-slate-600 mx-2">·</span>
                        <span className="text-slate-600">+{Math.round(att.delay_ms)}ms</span>
                      </p>
                      <p className="text-[11px] text-slate-600 mt-0.5 truncate">{att.error_message}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

function Pill({ label, color }: { label: string; color: "amber" | "red" | "green" }) {
  const cls = {
    amber: "text-amber-400 bg-amber-500/10 border-amber-500/20",
    red:   "text-red-400 bg-red-500/10 border-red-500/20",
    green: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20",
  }[color];
  return (
    <span className={`text-[10px] px-2 py-0.5 rounded border font-medium ${cls}`}>{label}</span>
  );
}
