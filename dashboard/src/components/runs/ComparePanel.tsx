"use client";
import Link from "next/link";
import Card from "@/components/ui/Card";
import ScoreBar from "@/components/ui/ScoreBar";
import { StatusBadge } from "@/components/ui/Badge";
import type { WorkflowRun, EvaluationResult } from "@/types";

interface RunSnapshot {
  run: WorkflowRun;
  eval: EvaluationResult | null;
}

interface Props {
  original: RunSnapshot;
  replay: RunSnapshot;
}

function delta(a: number | null, b: number | null): React.ReactNode {
  if (a == null || b == null) return null;
  const diff = b - a;
  if (Math.abs(diff) < 0.001) return <span className="text-slate-600 text-xs">±0</span>;
  const positive = diff > 0;
  return (
    <span className={`text-xs font-medium ${positive ? "text-emerald-400" : "text-red-400"}`}>
      {positive ? "+" : ""}{(diff * 100).toFixed(1)}%
    </span>
  );
}

function numDelta(a: number | null, b: number | null, lowerBetter = false): React.ReactNode {
  if (a == null || b == null) return null;
  const diff = b - a;
  if (Math.abs(diff) < 0.0001) return <span className="text-slate-600 text-xs">same</span>;
  const improved = lowerBetter ? diff < 0 : diff > 0;
  const sign = diff > 0 ? "+" : "";
  return (
    <span className={`text-xs font-medium ${improved ? "text-emerald-400" : "text-red-400"}`}>
      {sign}{diff.toFixed(diff < 1 ? 5 : 0)}
    </span>
  );
}

export default function ComparePanel({ original, replay }: Props) {
  const o = original.run;
  const r = replay.run;
  const oe = original.eval;
  const re = replay.eval;

  const rows = [
    {
      label: "Status",
      orig:  <StatusBadge status={o.status} />,
      rep:   <StatusBadge status={r.status} />,
      diff:  null,
    },
    {
      label: "Duration",
      orig:  o.duration_ms != null ? `${o.duration_ms.toLocaleString()}ms` : "—",
      rep:   r.duration_ms != null ? `${r.duration_ms.toLocaleString()}ms` : "—",
      diff:  numDelta(o.duration_ms, r.duration_ms, true),
    },
    {
      label: "Cost",
      orig:  o.total_cost != null ? `$${o.total_cost.toFixed(5)}` : "—",
      rep:   r.total_cost != null ? `$${r.total_cost.toFixed(5)}` : "—",
      diff:  numDelta(o.total_cost, r.total_cost, true),
    },
    {
      label: "Tokens",
      orig:  o.total_tokens != null ? o.total_tokens.toLocaleString() : "—",
      rep:   r.total_tokens != null ? r.total_tokens.toLocaleString() : "—",
      diff:  numDelta(o.total_tokens, r.total_tokens, true),
    },
  ];

  return (
    <Card>
      <h2 className="text-sm font-medium text-slate-300 mb-5">Compare — Original vs This Replay</h2>

      {/* Header */}
      <div className="grid grid-cols-[1fr_1fr_1fr_80px] gap-3 mb-2 px-1">
        <p className="text-xs text-slate-600 uppercase tracking-wider">Metric</p>
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wider">Original</p>
          <Link href={`/runs/${o.id}`} className="text-[11px] text-brand-400 hover:text-brand-300 font-mono">
            {o.id.slice(0, 8)}… →
          </Link>
        </div>
        <div>
          <p className="text-xs text-violet-400 uppercase tracking-wider">This Replay</p>
          <span className="text-[11px] text-slate-600 font-mono">{r.id.slice(0, 8)}…</span>
        </div>
        <p className="text-xs text-slate-600 uppercase tracking-wider">Δ</p>
      </div>

      {/* Rows */}
      <div className="space-y-1">
        {rows.map(({ label, orig, rep, diff }) => (
          <div key={label} className="grid grid-cols-[1fr_1fr_1fr_80px] gap-3 items-center px-1 py-2 rounded-lg hover:bg-white/[0.02]">
            <p className="text-xs text-slate-500">{label}</p>
            <p className="text-sm text-slate-300">{orig}</p>
            <p className="text-sm text-slate-300">{rep}</p>
            <div>{diff}</div>
          </div>
        ))}
      </div>

      {/* Eval scores side by side */}
      {(oe || re) && (
        <div className="mt-5 pt-5 border-t border-[#252b3b]">
          <p className="text-xs text-slate-500 uppercase tracking-wider mb-4">Evaluation Scores</p>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Original */}
            <div>
              <p className="text-[11px] text-slate-600 mb-3">Original</p>
              {oe ? (
                <div className="space-y-3">
                  <ScoreBar label="Relevance"          value={oe.relevance_score}    />
                  <ScoreBar label="Groundedness"       value={oe.groundedness_score} />
                  <ScoreBar label="Hallucination Risk" value={oe.hallucination_risk} invert />
                  <ScoreBar label="Quality"            value={oe.quality_score}      />
                </div>
              ) : (
                <p className="text-xs text-slate-600">No evaluation</p>
              )}
            </div>

            {/* Replay */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <p className="text-[11px] text-slate-600">This Replay</p>
                {oe && re && (
                  <span className="text-xs">
                    {delta(oe.quality_score, re.quality_score)} quality
                  </span>
                )}
              </div>
              {re ? (
                <div className="space-y-3">
                  <ScoreBar label="Relevance"          value={re.relevance_score}    />
                  <ScoreBar label="Groundedness"       value={re.groundedness_score} />
                  <ScoreBar label="Hallucination Risk" value={re.hallucination_risk} invert />
                  <ScoreBar label="Quality"            value={re.quality_score}      />
                </div>
              ) : (
                <p className="text-xs text-slate-600">No evaluation</p>
              )}
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
