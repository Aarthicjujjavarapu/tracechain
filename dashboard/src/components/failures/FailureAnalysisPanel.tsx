"use client";
import type { FailureClassification } from "@/types";
import { SeverityBadge } from "./SeverityBadge";

const CATEGORY_ICONS: Record<string, string> = {
  RETRY_LOOP:            "↻",
  MODEL_TIMEOUT:         "⏱",
  MODEL_RATE_LIMIT:      "🚦",
  OUTPUT_TRUNCATION:     "✂",
  CONTEXT_WINDOW_RISK:   "📏",
  RETRIEVAL_FAILURE:     "🔍",
  LOW_RELEVANCE_CONTEXT: "📉",
  HALLUCINATION_RISK:    "🌀",
  TOOL_CALL_FAILURE:     "🔧",
  TOOL_ARGUMENT_ERROR:   "⚠",
  VALIDATION_FAILURE:    "✗",
  LATENCY_SPIKE:         "⚡",
  COST_SPIKE:            "$",
  PROMPT_REGRESSION:     "📝",
  UNKNOWN_FAILURE:       "?",
};

function EvidenceRow({ label, value }: { label: string; value: unknown }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div className="flex gap-2 text-xs">
      <span className="text-slate-500 shrink-0 w-36">{label}</span>
      <span className="text-slate-300 font-mono break-all">{String(value)}</span>
    </div>
  );
}

function ClassificationCard({ fc }: { fc: FailureClassification }) {
  const icon = CATEGORY_ICONS[fc.category] ?? "?";
  const label = fc.category.replace(/_/g, " ");

  return (
    <div className="rounded-xl border border-[#252b3b] bg-[#0f1119] p-4 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2">
          <span className="text-lg leading-none">{icon}</span>
          <span className="text-sm font-semibold text-white">{label}</span>
        </div>
        <SeverityBadge severity={fc.severity} />
      </div>

      {fc.evidence && Object.keys(fc.evidence).length > 0 && (
        <div className="bg-[#0d0f1a] rounded-lg p-3 space-y-1.5">
          {Object.entries(fc.evidence).map(([k, v]) => (
            <EvidenceRow key={k} label={k.replace(/_/g, " ")} value={v} />
          ))}
        </div>
      )}

      {fc.recommendation && (
        <div className="flex gap-2 items-start">
          <span className="text-emerald-500 shrink-0 text-xs mt-0.5">→</span>
          <p className="text-xs text-slate-400 leading-relaxed">{fc.recommendation}</p>
        </div>
      )}
    </div>
  );
}

interface Props {
  classifications: FailureClassification[];
  loading?: boolean;
}

export default function FailureAnalysisPanel({ classifications, loading }: Props) {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-32">
        <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  if (classifications.length === 0) {
    return (
      <div className="rounded-xl border border-[#252b3b] bg-[#0f1119] p-8 text-center">
        <p className="text-slate-500 text-sm">No failure patterns detected for this run.</p>
        <p className="text-slate-600 text-xs mt-1">Classifications are generated automatically when a run completes or fails.</p>
      </div>
    );
  }

  const criticalCount = classifications.filter(c => c.severity === "CRITICAL").length;
  const highCount     = classifications.filter(c => c.severity === "HIGH").length;

  return (
    <div className="space-y-4">
      {/* Summary bar */}
      <div className="flex items-center gap-3 flex-wrap">
        <span className="text-sm text-slate-400">
          {classifications.length} issue{classifications.length !== 1 ? "s" : ""} detected
        </span>
        {criticalCount > 0 && (
          <span className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 px-2 py-0.5 rounded">
            {criticalCount} CRITICAL
          </span>
        )}
        {highCount > 0 && (
          <span className="text-xs text-orange-400 bg-orange-500/10 border border-orange-500/20 px-2 py-0.5 rounded">
            {highCount} HIGH
          </span>
        )}
      </div>

      {/* Cards — most severe first */}
      {[...classifications]
        .sort((a, b) => {
          const rank: Record<string, number> = { CRITICAL: 3, HIGH: 2, MEDIUM: 1, LOW: 0 };
          return (rank[b.severity] ?? 0) - (rank[a.severity] ?? 0);
        })
        .map(fc => <ClassificationCard key={fc.id} fc={fc} />)}
    </div>
  );
}
