"use client";
import { useState } from "react";
import Card from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/Badge";
import type { LLMCall } from "@/types";

export default function LLMCallCard({ call }: { call: LLMCall }) {
  const [open, setOpen] = useState(false);
  const showTTFT = call.is_stream && call.time_to_first_token_ms != null;

  return (
    <Card padding="sm" className="text-sm">
      <div
        className="flex items-center gap-3 cursor-pointer"
        onClick={() => setOpen(!open)}
      >
        {/* Left — model, status, badges */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs bg-[#252b3b] px-2 py-0.5 rounded text-slate-300">
              {call.model}
            </span>
            <StatusBadge status={call.status} />
            {call.is_stream && (
              <span className="text-[11px] text-cyan-400 bg-cyan-500/10 px-2 py-0.5 rounded border border-cyan-500/20">
                STREAM
              </span>
            )}
            {call.prompt_version && (
              <span className="text-[11px] text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded border border-violet-500/20">
                {call.prompt_version}
              </span>
            )}
          </div>
          <p className="text-slate-500 text-xs mt-1.5 truncate">{call.prompt.slice(0, 120)}…</p>
        </div>

        {/* Right — metrics summary */}
        <div className="text-right shrink-0 space-y-1">
          {call.total_tokens != null && (
            <p className="text-xs text-slate-400">{call.total_tokens.toLocaleString()} tokens</p>
          )}
          {call.estimated_cost != null && (
            <p className="text-xs text-emerald-400">${call.estimated_cost.toFixed(5)}</p>
          )}
          {call.latency_ms != null && (
            <p className="text-xs text-slate-500">{call.latency_ms.toLocaleString()}ms total</p>
          )}
          {showTTFT && (
            <p className="text-xs text-cyan-400">
              TTFT {call.time_to_first_token_ms!.toLocaleString()}ms
            </p>
          )}
        </div>

        {/* Chevron */}
        <svg
          width="14" height="14" viewBox="0 0 16 16" fill="none"
          className={`text-slate-600 transition-transform shrink-0 ${open ? "rotate-180" : ""}`}
        >
          <path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
      </div>

      {/* Expanded detail */}
      {open && (
        <div className="mt-4 space-y-3 border-t border-[#252b3b] pt-4">
          <div>
            <p className="text-[11px] text-slate-500 uppercase tracking-wider mb-1.5">Prompt</p>
            <pre className="text-xs text-slate-300 bg-[#0d0f1a] rounded-lg p-3 whitespace-pre-wrap overflow-auto max-h-48 font-mono leading-relaxed">
              {call.prompt}
            </pre>
          </div>

          {call.response && (
            <div>
              <p className="text-[11px] text-slate-500 uppercase tracking-wider mb-1.5">Response</p>
              <pre className="text-xs text-slate-300 bg-[#0d0f1a] rounded-lg p-3 whitespace-pre-wrap overflow-auto max-h-48 font-mono leading-relaxed">
                {call.response}
              </pre>
            </div>
          )}

          {/* Stats grid — expands to 4 cols when TTFT is present */}
          <div className={`grid gap-3 ${showTTFT ? "grid-cols-2 sm:grid-cols-4" : "grid-cols-3"}`}>
            {[
              ["Input tokens",  call.input_tokens  != null ? call.input_tokens.toLocaleString()  : null],
              ["Output tokens", call.output_tokens != null ? call.output_tokens.toLocaleString() : null],
              ["Temperature",   call.temperature   != null ? String(call.temperature)             : null],
            ].map(([k, v]) => v != null && (
              <div key={k as string} className="bg-[#13151f] rounded-lg p-2.5">
                <p className="text-[10px] text-slate-600 uppercase">{k}</p>
                <p className="text-sm font-semibold text-slate-300 mt-0.5">{v}</p>
              </div>
            ))}

            {showTTFT && (
              <div className="bg-[#13151f] rounded-lg p-2.5">
                <p className="text-[10px] text-slate-600 uppercase">Time to first token</p>
                <p className="text-sm font-semibold text-cyan-400 mt-0.5">
                  {call.time_to_first_token_ms!.toLocaleString()}ms
                </p>
              </div>
            )}
          </div>

          {/* Error */}
          {call.error_message && (
            <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-3">
              <p className="text-[10px] text-red-500 uppercase tracking-wider mb-1">Error</p>
              <p className="text-xs text-red-400 font-mono">{call.error_message}</p>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}
