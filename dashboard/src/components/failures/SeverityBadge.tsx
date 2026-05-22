import type { FailureSeverity } from "@/types";

const STYLES: Record<FailureSeverity, string> = {
  LOW:      "bg-slate-500/15 text-slate-400 border-slate-500/20",
  MEDIUM:   "bg-amber-500/15  text-amber-400  border-amber-500/20",
  HIGH:     "bg-orange-500/15 text-orange-400 border-orange-500/20",
  CRITICAL: "bg-red-500/15    text-red-400    border-red-500/20",
};

export function SeverityBadge({ severity }: { severity: FailureSeverity }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold border ${STYLES[severity]}`}>
      {severity}
    </span>
  );
}
