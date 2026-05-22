interface Props {
  score: number;
  reasons?: string[];
  compact?: boolean;
}

function scoreColor(score: number): string {
  if (score >= 80) return "text-emerald-400";
  if (score >= 60) return "text-amber-400";
  if (score >= 40) return "text-orange-400";
  return "text-red-400";
}

function scoreRingColor(score: number): string {
  if (score >= 80) return "stroke-emerald-400";
  if (score >= 60) return "stroke-amber-400";
  if (score >= 40) return "stroke-orange-400";
  return "stroke-red-400";
}

function scoreLabel(score: number): string {
  if (score >= 90) return "Excellent";
  if (score >= 75) return "Good";
  if (score >= 60) return "Fair";
  if (score >= 40) return "Poor";
  return "Critical";
}

export default function ReliabilityScore({ score, reasons = [], compact = false }: Props) {
  const circumference = 2 * Math.PI * 30;
  const offset = circumference - (score / 100) * circumference;

  if (compact) {
    return (
      <div className="flex items-center gap-2">
        <span className={`text-lg font-bold tabular-nums ${scoreColor(score)}`}>{score}</span>
        <span className="text-xs text-slate-500">/ 100</span>
      </div>
    );
  }

  return (
    <div className="flex items-start gap-6">
      {/* Circular gauge */}
      <div className="relative shrink-0">
        <svg width="80" height="80" viewBox="0 0 80 80">
          {/* Background ring */}
          <circle cx="40" cy="40" r="30" fill="none" stroke="#1e2130" strokeWidth="7" />
          {/* Score arc */}
          <circle
            cx="40" cy="40" r="30"
            fill="none"
            strokeWidth="7"
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            className={`${scoreRingColor(score)} transition-all duration-700`}
            transform="rotate(-90 40 40)"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-xl font-bold tabular-nums leading-none ${scoreColor(score)}`}>{score}</span>
          <span className="text-[9px] text-slate-500 leading-none mt-0.5">{scoreLabel(score)}</span>
        </div>
      </div>

      {/* Reason list */}
      {reasons.length > 0 && (
        <div className="space-y-1.5 pt-1 min-w-0">
          <p className="text-xs text-slate-500 font-medium uppercase tracking-wider mb-2">Score factors</p>
          {reasons.map((r, i) => (
            <div key={i} className="flex items-start gap-1.5 text-xs text-slate-400">
              <span className="text-red-400 shrink-0 mt-px">↓</span>
              <span>{r}</span>
            </div>
          ))}
        </div>
      )}

      {reasons.length === 0 && (
        <div className="pt-3">
          <p className="text-xs text-emerald-400">No reliability issues detected.</p>
        </div>
      )}
    </div>
  );
}
