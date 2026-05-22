"use client";
import Link from "next/link";
import type { WorkflowHealth } from "@/types";

// ── Reliability ring ──────────────────────────────────────────────────────────

function ReliabilityRing({ score }: { score: number | null }) {
  if (score === null) {
    return (
      <div className="w-12 h-12 rounded-full border-2 border-[#252b3b] flex items-center justify-center">
        <span className="text-xs text-slate-600">—</span>
      </div>
    );
  }
  const stroke = score >= 80 ? "#10b981" : score >= 60 ? "#f59e0b" : score >= 40 ? "#f97316" : "#ef4444";
  const r = 18;
  const circ = 2 * Math.PI * r;
  const offset = circ - (score / 100) * circ;

  return (
    <div className="relative w-12 h-12 shrink-0">
      <svg width="48" height="48" viewBox="0 0 48 48">
        <circle cx="24" cy="24" r={r} fill="none" stroke="#1e2130" strokeWidth="5" />
        <circle
          cx="24" cy="24" r={r}
          fill="none" strokeWidth="5" strokeLinecap="round"
          strokeDasharray={circ} strokeDashoffset={offset}
          stroke={stroke}
          transform="rotate(-90 24 24)"
          style={{ transition: "stroke-dashoffset 0.6s ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-[11px] font-bold tabular-nums" style={{ color: stroke }}>
          {Math.round(score)}
        </span>
      </div>
    </div>
  );
}

// ── Trend indicator ───────────────────────────────────────────────────────────

function TrendPill({ trend, delta }: { trend: WorkflowHealth["trend"]; delta: number | null }) {
  if (trend === "insufficient_data") {
    return <span className="text-[10px] text-slate-600">—</span>;
  }
  const cfg = {
    improving: { icon: "↑", cls: "text-emerald-400 bg-emerald-500/10 border-emerald-500/20" },
    degrading:  { icon: "↓", cls: "text-red-400 bg-red-500/10 border-red-500/20"           },
    stable:     { icon: "→", cls: "text-slate-400 bg-slate-500/10 border-slate-500/20"     },
  }[trend];

  return (
    <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium border ${cfg.cls}`}>
      {cfg.icon}
      {delta !== null && ` ${delta > 0 ? "+" : ""}${delta}`}
    </span>
  );
}

// ── Category badge ────────────────────────────────────────────────────────────

function CategoryBadge({ category }: { category: string | null }) {
  if (!category) return null;
  return (
    <span className="text-[10px] text-orange-400 bg-orange-500/10 border border-orange-500/20 px-1.5 py-0.5 rounded truncate max-w-[120px]"
          title={category}>
      {category.replace(/_/g, " ")}
    </span>
  );
}

// ── Main card ─────────────────────────────────────────────────────────────────

export default function WorkflowHealthCard({ wf }: { wf: WorkflowHealth }) {
  const successPct = (wf.success_rate * 100).toFixed(0);
  const srColor = wf.success_rate >= 0.9 ? "text-emerald-400"
                : wf.success_rate >= 0.7 ? "text-amber-400"
                : "text-red-400";

  return (
    <div className="rounded-xl border border-[#1a1d2e] bg-[#0d0f1a] p-4 hover:border-[#252b3b] transition-colors">
      {/* Top row: name + reliability ring */}
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="min-w-0">
          <Link
            href={`/runs?workflow_name=${encodeURIComponent(wf.workflow_name)}`}
            className="text-sm font-semibold text-white hover:text-brand-400 transition-colors truncate block"
          >
            {wf.workflow_name}
          </Link>
          <p className="text-xs text-slate-600 mt-0.5">{wf.run_count} run{wf.run_count !== 1 ? "s" : ""}</p>
        </div>
        <ReliabilityRing score={wf.avg_reliability_score} />
      </div>

      {/* Stats row */}
      <div className="flex items-center gap-3 flex-wrap mb-3">
        <div className="flex items-center gap-1">
          <span className="text-xs text-slate-500">Success</span>
          <span className={`text-xs font-semibold tabular-nums ${srColor}`}>{successPct}%</span>
        </div>

        {wf.open_incidents > 0 && (
          <Link
            href={`/incidents?status=OPEN&workflow_name=${encodeURIComponent(wf.workflow_name)}`}
            className="flex items-center gap-1 text-xs text-red-400 hover:text-red-300 transition-colors"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
            {wf.open_incidents} incident{wf.open_incidents !== 1 ? "s" : ""}
          </Link>
        )}

        <TrendPill trend={wf.trend} delta={wf.trend_delta} />
      </div>

      {/* Top failure category */}
      {wf.top_failure_category && (
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-slate-600 shrink-0">Top failure:</span>
          <CategoryBadge category={wf.top_failure_category} />
        </div>
      )}
    </div>
  );
}
