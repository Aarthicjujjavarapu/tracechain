import Card from "./Card";

interface StatCardProps {
  label: string;
  value: string | number;
  sub?: string;
  accent?: "green" | "red" | "blue" | "violet" | "amber" | "default";
  icon?: React.ReactNode;
}

const ACCENT_COLORS = {
  green:   "text-emerald-400",
  red:     "text-red-400",
  blue:    "text-blue-400",
  violet:  "text-violet-400",
  amber:   "text-amber-400",
  default: "text-white",
};

export default function StatCard({ label, value, sub, accent = "default", icon }: StatCardProps) {
  return (
    <Card>
      <div className="flex items-start justify-between">
        <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">{label}</p>
        {icon && <span className="text-slate-600">{icon}</span>}
      </div>
      <p className={`text-2xl font-bold mt-2 ${ACCENT_COLORS[accent]}`}>{value}</p>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </Card>
  );
}
