"use client";
import { useState, useEffect, useCallback, useMemo } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { StatusBadge } from "@/components/ui/Badge";
import Card from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { WorkflowRun } from "@/types";
import { formatDistanceToNow } from "date-fns";

// ── types ─────────────────────────────────────────────────────────────────────

type SortKey = "started_at" | "duration_ms" | "total_cost" | "total_tokens";
type SortDir = "asc" | "desc";

// ── small components ──────────────────────────────────────────────────────────

function FilterChip({ label, onRemove }: { label: string; onRemove: () => void }) {
  return (
    <span className="flex items-center gap-1.5 px-2.5 py-1 bg-brand-500/10 border border-brand-500/20 text-brand-400 text-xs rounded-full">
      {label}
      <button onClick={onRemove} className="hover:text-white transition-colors leading-none">✕</button>
    </span>
  );
}

function SortTh({
  label, sortKey: key, active, dir,
  onSort, className = "",
}: {
  label: string; sortKey: SortKey; active: boolean; dir: SortDir;
  onSort: (k: SortKey) => void; className?: string;
}) {
  return (
    <th
      onClick={() => onSort(key)}
      className={`text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider whitespace-nowrap cursor-pointer select-none group hover:text-slate-300 transition-colors ${className}`}
    >
      <span className="flex items-center gap-1">
        {label}
        <span className={`text-[10px] transition-colors ${active ? "text-brand-400" : "text-slate-700 group-hover:text-slate-500"}`}>
          {active ? (dir === "asc" ? "↑" : "↓") : "↕"}
        </span>
      </span>
    </th>
  );
}

// ── main page ─────────────────────────────────────────────────────────────────

export default function RunsPage() {
  const router       = useRouter();
  const searchParams = useSearchParams();

  // ── filter state (initialised from URL) ────────────────────────────────────
  const [status,        setStatus]        = useState(searchParams.get("status")    ?? "");
  const [workflow,      setWorkflow]      = useState(searchParams.get("workflow")  ?? "");
  const [isReplay,      setIsReplay]      = useState(searchParams.get("is_replay") ?? "");
  // raw input value — debounced into `workflow`
  const [workflowInput, setWorkflowInput] = useState(searchParams.get("workflow")  ?? "");

  // ── sort state ──────────────────────────────────────────────────────────────
  const [sortKey, setSortKey] = useState<SortKey>("started_at");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  // ── pagination + data ───────────────────────────────────────────────────────
  const [runs,    setRuns]    = useState<WorkflowRun[]>([]);
  const [total,   setTotal]   = useState(0);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState<string | null>(null);
  const [offset,  setOffset]  = useState(0);
  const LIMIT = 50;

  // ── debounce workflow text input (300 ms) ───────────────────────────────────
  useEffect(() => {
    const t = setTimeout(() => setWorkflow(workflowInput), 300);
    return () => clearTimeout(t);
  }, [workflowInput]);

  // ── sync active filters → URL (shareable / survives refresh) ───────────────
  useEffect(() => {
    const p = new URLSearchParams();
    if (status)   p.set("status",    status);
    if (workflow)  p.set("workflow",  workflow);
    if (isReplay)  p.set("is_replay", isReplay);
    router.replace(`/runs${p.size ? `?${p}` : ""}`, { scroll: false });
  }, [status, workflow, isReplay, router]);

  // ── reset page when filters change ─────────────────────────────────────────
  useEffect(() => { setOffset(0); }, [status, workflow, isReplay]);

  // ── fetch ───────────────────────────────────────────────────────────────────
  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    const params: Record<string, string> = { limit: String(LIMIT), offset: String(offset) };
    if (status)        params.status        = status;
    if (workflow)      params.workflow_name = workflow;
    if (isReplay !== "") params.is_replay   = isReplay;

    api.runs.list(params)
      .then((d) => { setRuns(d.items); setTotal(d.total); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [status, workflow, isReplay, offset]);

  useEffect(() => { load(); }, [load]);

  // ── client-side sort on the current page ───────────────────────────────────
  const sortedRuns = useMemo(() => {
    return [...runs].sort((a, b) => {
      const av = a[sortKey] ?? (sortKey === "started_at" ? "" : -Infinity);
      const bv = b[sortKey] ?? (sortKey === "started_at" ? "" : -Infinity);
      if (typeof av === "string" && typeof bv === "string")
        return sortDir === "asc" ? av.localeCompare(bv) : bv.localeCompare(av);
      return sortDir === "asc"
        ? (av as number) - (bv as number)
        : (bv as number) - (av as number);
    });
  }, [runs, sortKey, sortDir]);

  function handleSort(key: SortKey) {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else { setSortKey(key); setSortDir("desc"); }
  }

  function clearAll() {
    setStatus(""); setWorkflow(""); setWorkflowInput(""); setIsReplay("");
  }

  const hasFilters = !!(status || workflow || isReplay);
  const pages = Math.ceil(total / LIMIT);
  const page  = Math.floor(offset / LIMIT);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Runs</h1>
          <p className="text-sm text-slate-500 mt-1">
            {loading ? "Loading…" : `${total.toLocaleString()} workflow execution${total !== 1 ? "s" : ""}`}
          </p>
        </div>
        <button onClick={load}
          className="text-xs text-slate-500 hover:text-slate-300 px-3 py-1.5 border border-[#252b3b] rounded-lg transition-colors">
          Refresh
        </button>
      </div>

      {/* Filter bar */}
      <Card padding="sm">
        <div className="space-y-3">
          <div className="flex flex-wrap gap-3 items-center">
            {/* Status */}
            <select value={status} onChange={(e) => setStatus(e.target.value)}
              className="bg-[#13151f] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500">
              <option value="">All statuses</option>
              {["success", "failed", "running", "pending"].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>

            {/* Workflow search — debounced */}
            <div className="relative">
              <input
                type="text"
                placeholder="Search workflows…"
                value={workflowInput}
                onChange={(e) => setWorkflowInput(e.target.value)}
                className="bg-[#13151f] border border-[#252b3b] text-slate-300 text-sm rounded-lg pl-8 pr-3 py-2 focus:outline-none focus:border-brand-500 min-w-56"
              />
              <span className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-600 text-xs pointer-events-none">⌕</span>
              {workflowInput && (
                <button onClick={() => { setWorkflowInput(""); setWorkflow(""); }}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-600 hover:text-slate-400 text-xs">✕</button>
              )}
            </div>

            {/* Replay filter */}
            <select value={isReplay} onChange={(e) => setIsReplay(e.target.value)}
              className="bg-[#13151f] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500">
              <option value="">All runs</option>
              <option value="false">Originals only</option>
              <option value="true">Replays only</option>
            </select>

            {hasFilters && (
              <button onClick={clearAll}
                className="text-xs text-slate-500 hover:text-red-400 transition-colors ml-auto">
                Clear all
              </button>
            )}
          </div>

          {/* Active filter chips */}
          {hasFilters && (
            <div className="flex gap-2 flex-wrap pt-1">
              {status && (
                <FilterChip label={`status: ${status}`} onRemove={() => setStatus("")} />
              )}
              {workflow && (
                <FilterChip label={`workflow: ${workflow}`} onRemove={() => { setWorkflow(""); setWorkflowInput(""); }} />
              )}
              {isReplay === "true" && (
                <FilterChip label="replays only" onRemove={() => setIsReplay("")} />
              )}
              {isReplay === "false" && (
                <FilterChip label="originals only" onRemove={() => setIsReplay("")} />
              )}
            </div>
          )}
        </div>
      </Card>

      {/* Table */}
      <Card padding="none">
        {error ? (
          <div className="p-8 text-center">
            <p className="text-red-400 text-sm">{error}</p>
            <p className="text-slate-600 text-xs mt-2">
              Make sure the backend is running:{" "}
              <code className="text-slate-500">uvicorn app.main:app --reload</code>
            </p>
          </div>
        ) : loading ? (
          <div className="p-12 text-center">
            <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-slate-600 text-sm">Loading runs…</p>
          </div>
        ) : runs.length === 0 ? (
          <div className="p-12 text-center space-y-2">
            <p className="text-slate-400 text-sm">
              {hasFilters ? "No runs match the active filters." : "No runs found."}
            </p>
            {!hasFilters && (
              <p className="text-slate-600 text-xs">
                Run an example:{" "}
                <code className="text-slate-500">python examples/02_support_agent.py</code>
              </p>
            )}
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#252b3b]">
                    <th className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">Workflow</th>
                    <th className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">Status</th>
                    <SortTh label="Duration"  sortKey="duration_ms"   active={sortKey === "duration_ms"}   dir={sortDir} onSort={handleSort} />
                    <SortTh label="Cost"      sortKey="total_cost"    active={sortKey === "total_cost"}    dir={sortDir} onSort={handleSort} />
                    <SortTh label="Tokens"    sortKey="total_tokens"  active={sortKey === "total_tokens"}  dir={sortDir} onSort={handleSort} />
                    <SortTh label="Started"   sortKey="started_at"    active={sortKey === "started_at"}    dir={sortDir} onSort={handleSort} />
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {sortedRuns.map((run) => (
                    <tr key={run.id}
                      className="border-b border-[#1e2235] hover:bg-white/[0.02] transition-colors group">
                      <td className="px-5 py-3.5">
                        <div className="font-medium text-slate-200 group-hover:text-white transition-colors">
                          {run.workflow_name}
                        </div>
                        {run.is_replay && (
                          <span className="text-[10px] text-violet-400 font-medium">REPLAY</span>
                        )}
                      </td>
                      <td className="px-5 py-3.5"><StatusBadge status={run.status} /></td>
                      <td className="px-5 py-3.5 text-slate-400 tabular-nums">
                        {run.duration_ms != null ? `${run.duration_ms.toLocaleString()}ms` : "—"}
                      </td>
                      <td className="px-5 py-3.5 text-emerald-400 text-xs tabular-nums">
                        {run.total_cost != null ? `$${run.total_cost.toFixed(5)}` : "—"}
                      </td>
                      <td className="px-5 py-3.5 text-slate-400 text-xs tabular-nums">
                        {run.total_tokens != null ? run.total_tokens.toLocaleString() : "—"}
                      </td>
                      <td className="px-5 py-3.5 text-slate-500 text-xs whitespace-nowrap">
                        {formatDistanceToNow(new Date(run.started_at), { addSuffix: true })}
                      </td>
                      <td className="px-5 py-3.5">
                        <Link href={`/runs/${run.id}`}
                          className="text-brand-400 text-xs hover:text-brand-300 font-medium opacity-0 group-hover:opacity-100 transition-opacity">
                          View →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {pages > 1 && (
              <div className="flex items-center justify-between px-5 py-3 border-t border-[#1e2235]">
                <p className="text-xs text-slate-500">
                  Showing {offset + 1}–{Math.min(offset + LIMIT, total)} of {total.toLocaleString()}
                </p>
                <div className="flex gap-2">
                  <button onClick={() => setOffset(Math.max(0, offset - LIMIT))}
                    disabled={page === 0}
                    className="text-xs px-3 py-1.5 border border-[#252b3b] rounded-lg text-slate-400 hover:text-slate-200 disabled:opacity-30 transition-colors">
                    ← Prev
                  </button>
                  <button onClick={() => setOffset(offset + LIMIT)}
                    disabled={page >= pages - 1}
                    className="text-xs px-3 py-1.5 border border-[#252b3b] rounded-lg text-slate-400 hover:text-slate-200 disabled:opacity-30 transition-colors">
                    Next →
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
