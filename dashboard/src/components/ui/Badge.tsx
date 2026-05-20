import clsx from "clsx";

type Variant = "success" | "failed" | "running" | "pending" | "replay" | "default";

const STYLES: Record<Variant, string> = {
  success: "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
  failed:  "bg-red-500/10    text-red-400    border-red-500/20",
  running: "bg-blue-500/10   text-blue-400   border-blue-500/20",
  pending: "bg-slate-500/10  text-slate-400  border-slate-500/20",
  replay:  "bg-violet-500/10 text-violet-400 border-violet-500/20",
  default: "bg-slate-500/10  text-slate-400  border-slate-500/20",
};

export default function Badge({ variant = "default", children }: { variant?: Variant; children: React.ReactNode }) {
  return (
    <span className={clsx("inline-flex items-center px-2 py-0.5 rounded-md text-xs font-medium border", STYLES[variant])}>
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const variant = (["success","failed","running","pending"].includes(status) ? status : "default") as Variant;
  return <Badge variant={variant}>{status}</Badge>;
}
