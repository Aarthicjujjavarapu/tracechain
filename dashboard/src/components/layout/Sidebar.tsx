"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import clsx from "clsx";
import { useBackendStatus } from "@/lib/useFetch";

const NAV = [
  { href: "/dashboard", label: "Dashboard",    icon: IconDashboard },
  { href: "/runs",      label: "Runs",         icon: IconRuns      },
  { href: "/prompts",   label: "Prompts",      icon: IconPrompts   },
  { href: "/metrics",   label: "Metrics",      icon: IconMetrics   },
  { href: "/examples",  label: "Examples",     icon: IconExamples  },
];

export default function Sidebar() {
  const path   = usePathname();
  const online = useBackendStatus();
  return (
    <aside className="fixed left-0 top-0 h-full w-56 bg-[#13151f] border-r border-[#1e2235] flex flex-col z-40">
      {/* Brand */}
      <div className="px-5 py-5 border-b border-[#1e2235]">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-brand-500 flex items-center justify-center">
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
              <path d="M2 8h12M8 2v12M4 4l8 8M12 4l-8 8" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
            </svg>
          </div>
          <span className="font-semibold text-white text-sm tracking-tight">TraceChain</span>
        </div>
        <p className="text-[11px] text-slate-500 mt-1 ml-9">LLM Observability</p>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5">
        {NAV.map(({ href, label, icon: Icon }) => {
          const active = path === href || path.startsWith(href + "/");
          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all",
                active
                  ? "bg-brand-500/10 text-brand-400 font-medium"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
              )}
            >
              <Icon active={active} />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-[#1e2235]">
        <div className="flex items-center gap-2">
          <span className={`w-1.5 h-1.5 rounded-full ${
            online === null ? "bg-slate-600" :
            online ? "bg-emerald-500" : "bg-red-500"
          }`}/>
          <p className="text-[11px] text-slate-600">
            {online === null ? "checking…" : online ? "backend online" : "backend offline"}
          </p>
        </div>
        <p className="text-[11px] text-slate-700 mt-1">v0.1.0</p>
      </div>
    </aside>
  );
}

function IconDashboard({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={active ? "text-brand-400" : "text-slate-500"}>
      <rect x="1" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="9" y="1" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="1" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <rect x="9" y="9" width="6" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
    </svg>
  );
}
function IconRuns({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={active ? "text-brand-400" : "text-slate-500"}>
      <path d="M2 4h12M2 8h8M2 12h10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  );
}
function IconPrompts({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={active ? "text-brand-400" : "text-slate-500"}>
      <rect x="2" y="2" width="12" height="12" rx="2" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M5 6h6M5 8.5h4" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  );
}
function IconMetrics({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={active ? "text-brand-400" : "text-slate-500"}>
      <path d="M2 13L5.5 8.5L8.5 11L12 5L14 7" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}
function IconExamples({ active }: { active: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" className={active ? "text-brand-400" : "text-slate-500"}>
      <path d="M5 4L2 8l3 4M11 4l3 4-3 4M9 3l-2 10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}
