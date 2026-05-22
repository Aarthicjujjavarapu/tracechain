"use client";
import Link from "next/link";
import { formatDistanceToNow } from "date-fns";
import { StatusBadge } from "@/components/ui/Badge";
import type { WorkflowRun } from "@/types";

interface Props {
  replays: WorkflowRun[];
  currentId: string;
}

export default function ReplayHistory({ replays, currentId }: Props) {
  if (replays.length === 0) return null;

  return (
    <div className="space-y-2">
      <p className="text-xs text-slate-500 uppercase tracking-wider font-medium mb-3">
        {replays.length} Replay{replays.length !== 1 ? "s" : ""}
      </p>
      {replays.map((r) => {
        const isCurrent = r.id === currentId;
        return (
          <div
            key={r.id}
            className={`flex items-center gap-3 px-3 py-2.5 rounded-lg border transition-colors ${
              isCurrent
                ? "bg-violet-500/10 border-violet-500/20"
                : "bg-[#13151f] border-[#1e2235] hover:border-[#252b3b]"
            }`}
          >
            {/* status dot */}
            <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
              r.status === "success" ? "bg-emerald-500" :
              r.status === "failed"  ? "bg-red-500"     :
              r.status === "running" ? "bg-blue-500 animate-pulse" :
              "bg-slate-600"
            }`} />

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-slate-400">{r.id.slice(0, 8)}…</span>
                <StatusBadge status={r.status} />
                {isCurrent && (
                  <span className="text-[10px] text-violet-400 font-medium">current</span>
                )}
              </div>
              <p className="text-[11px] text-slate-600 mt-0.5">
                {formatDistanceToNow(new Date(r.started_at), { addSuffix: true })}
                {r.duration_ms != null && ` · ${r.duration_ms.toLocaleString()}ms`}
                {r.total_cost  != null && ` · $${r.total_cost.toFixed(5)}`}
              </p>
            </div>

            {!isCurrent && (
              <Link
                href={`/runs/${r.id}`}
                className="text-xs text-brand-400 hover:text-brand-300 font-medium shrink-0"
              >
                View →
              </Link>
            )}
          </div>
        );
      })}
    </div>
  );
}
