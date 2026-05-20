interface ScoreBarProps {
  label: string;
  value: number; // 0–1
  invert?: boolean; // true = high is bad (hallucination risk)
}

export default function ScoreBar({ label, value, invert = false }: ScoreBarProps) {
  const pct = Math.round(value * 100);
  const color = invert
    ? pct > 50 ? "bg-red-500" : pct > 25 ? "bg-amber-500" : "bg-emerald-500"
    : pct >= 70 ? "bg-emerald-500" : pct >= 40 ? "bg-amber-500" : "bg-red-500";

  return (
    <div>
      <div className="flex justify-between mb-1">
        <span className="text-xs text-slate-400">{label}</span>
        <span className="text-xs font-semibold text-slate-300">{pct}%</span>
      </div>
      <div className="h-1.5 rounded-full bg-[#252b3b]">
        <div className={`h-full rounded-full transition-all ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}
