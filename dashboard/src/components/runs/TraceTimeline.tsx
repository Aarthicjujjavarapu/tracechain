import clsx from "clsx";
import { StatusBadge } from "@/components/ui/Badge";
import type { TraceStep } from "@/types";

export default function TraceTimeline({ steps }: { steps: TraceStep[] }) {
  if (!steps.length) return <p className="text-sm text-slate-500">No steps recorded.</p>;

  const firstMs = new Date(steps[0].started_at).getTime();
  const lastEnd = steps.reduce((m, s) => Math.max(m, s.ended_at ? new Date(s.ended_at).getTime() : 0), 0);
  const totalSpan = lastEnd - firstMs || 1;

  return (
    <div className="space-y-2">
      {/* ruler */}
      <div className="flex justify-between text-[10px] text-slate-600 px-1 mb-3">
        <span>0ms</span>
        <span>{Math.round(totalSpan)}ms</span>
      </div>

      {steps.map((step) => {
        const start = new Date(step.started_at).getTime() - firstMs;
        const end   = step.ended_at ? new Date(step.ended_at).getTime() - firstMs : start + 50;
        const left  = (start / totalSpan) * 100;
        const width = Math.max(((end - start) / totalSpan) * 100, 2);

        const barColor =
          step.status === "success" ? "bg-emerald-500"
          : step.status === "failed" ? "bg-red-500"
          : "bg-blue-500";

        return (
          <div key={step.id} className="group">
            <div className="flex items-center gap-3 mb-1">
              <span className="text-xs text-slate-400 w-36 truncate font-mono">{step.step_name}</span>
              <StatusBadge status={step.status} />
              <span className="text-[11px] text-slate-600 ml-auto">
                {step.duration_ms != null ? `${step.duration_ms}ms` : "—"}
              </span>
              {step.retry_count > 0 && (
                <span className="text-[11px] text-amber-500">{step.retry_count} retry</span>
              )}
            </div>

            {/* bar track */}
            <div className="relative h-5 bg-[#1e2235] rounded-md overflow-hidden">
              <div
                className={clsx("absolute h-full rounded-md opacity-80", barColor)}
                style={{ left: `${left}%`, width: `${width}%`, minWidth: 4 }}
              />
            </div>

            {/* error tooltip */}
            {step.error_message && (
              <p className="text-[11px] text-red-400 mt-1 pl-1 truncate max-w-lg">
                {step.error_message}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
