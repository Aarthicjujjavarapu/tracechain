"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import Card from "@/components/ui/Card";
import PromptDiff from "@/components/prompts/PromptDiff";
import { api } from "@/lib/api";
import type { PromptVersion, PromptCompareOut } from "@/types";
import { format } from "date-fns";

type DiffState = { leftId: string; rightId: string };

// ── Metrics comparison panel ──────────────────────────────────────────────────

function WinBadge({ side, winner }: { side: "a" | "b"; winner: "a" | "b" | null }) {
  if (winner !== side) return null;
  return (
    <span className="ml-1.5 text-[10px] font-semibold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-1.5 py-0.5 rounded-full">
      WIN
    </span>
  );
}

function MetricsCompare({ leftId, rightId, leftPv, rightPv }: {
  leftId: string; rightId: string;
  leftPv: PromptVersion; rightPv: PromptVersion;
}) {
  const [data, setData]   = useState<PromptCompareOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setData(null);
    setLoading(true);
    api.prompts.compare(leftId, rightId)
      .then(setData)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [leftId, rightId]);

  if (loading) return <p className="text-slate-500 text-xs py-2">Loading metrics…</p>;
  if (!data)   return <p className="text-slate-600 text-xs py-2">Metrics unavailable</p>;

  const { a, b, winner } = data;

  const fmtMs   = (v: number | null) => v != null ? `${Math.round(v).toLocaleString()}ms` : "—";
  const fmtCost = (v: number | null) => v != null ? `$${v.toFixed(5)}` : "—";
  const fmtPct  = (v: number)        => `${(v * 100).toFixed(1)}%`;
  const fmtQ    = (v: number | null) => v != null ? v.toFixed(3) : "—";

  const rows: { label: string; aVal: string; bVal: string; win: "a" | "b" | null }[] = [
    { label: "Usage Count",   aVal: a.usage_count.toLocaleString(), bVal: b.usage_count.toLocaleString(), win: null },
    { label: "Success Rate",  aVal: fmtPct(a.success_rate),         bVal: fmtPct(b.success_rate),         win: winner.success_rate },
    { label: "Avg Latency",   aVal: fmtMs(a.avg_latency_ms),        bVal: fmtMs(b.avg_latency_ms),        win: winner.latency },
    { label: "Avg Cost/call", aVal: fmtCost(a.avg_cost),            bVal: fmtCost(b.avg_cost),            win: winner.cost },
    { label: "Quality Score", aVal: fmtQ(a.avg_quality_score),      bVal: fmtQ(b.avg_quality_score),      win: winner.quality },
  ];

  return (
    <div className="space-y-2">
      <p className="text-xs font-medium text-slate-400 uppercase tracking-wider">Performance Comparison</p>
      <div className="rounded-lg border border-[#252b3b] overflow-hidden">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[#252b3b] bg-[#0d0f1a]">
              <th className="text-left px-4 py-2.5 text-slate-500 font-medium w-1/3">Metric</th>
              <th className="text-left px-4 py-2.5 text-slate-400 font-medium w-1/3">
                <span className="font-mono bg-[#252b3b] px-1.5 py-0.5 rounded text-slate-300">{leftPv.version}</span>
                <span className="text-slate-600 ml-1.5">A</span>
              </th>
              <th className="text-left px-4 py-2.5 text-slate-400 font-medium w-1/3">
                <span className="font-mono bg-[#252b3b] px-1.5 py-0.5 rounded text-slate-300">{rightPv.version}</span>
                <span className="text-slate-600 ml-1.5">B</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map(({ label, aVal, bVal, win }) => (
              <tr key={label} className="border-b border-[#1e2235] last:border-0 hover:bg-white/[0.015]">
                <td className="px-4 py-2.5 text-slate-500">{label}</td>
                <td className={`px-4 py-2.5 font-mono ${win === "a" ? "text-emerald-400 font-semibold" : "text-slate-300"}`}>
                  {aVal}
                  <WinBadge side="a" winner={win} />
                </td>
                <td className={`px-4 py-2.5 font-mono ${win === "b" ? "text-emerald-400 font-semibold" : "text-slate-300"}`}>
                  {bVal}
                  <WinBadge side="b" winner={win} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default function PromptsPage() {
  const [prompts, setPrompts] = useState<PromptVersion[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState({ prompt_name: "", version: "", prompt_text: "" });
  // promptName → { leftId, rightId }
  const [diffs, setDiffs] = useState<Record<string, DiffState>>({});

  const load = () => {
    setLoading(true);
    (api.prompts.list() as Promise<any>)
      .then((d) => setPrompts(Array.isArray(d) ? d : []))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(load, []);

  const handleCreate = async () => {
    if (!form.prompt_name || !form.version || !form.prompt_text) return;
    setCreating(true);
    try {
      await api.prompts.create(form);
      setForm({ prompt_name: "", version: "", prompt_text: "" });
      load();
    } catch {} finally { setCreating(false); }
  };

  // group by prompt_name
  const grouped = prompts.reduce<Record<string, PromptVersion[]>>((acc, p) => {
    (acc[p.prompt_name] ||= []).push(p);
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold text-white">Prompt Versions</h1>
        <p className="text-sm text-slate-500 mt-1">{prompts.length} versions across {Object.keys(grouped).length} prompts</p>
      </div>

      {/* Create form */}
      <Card>
        <h2 className="text-sm font-medium text-slate-300 mb-4">Create Prompt Version</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3 mb-3">
          <input
            placeholder="Prompt name (e.g. support_answer_prompt)"
            value={form.prompt_name}
            onChange={(e) => setForm({ ...form, prompt_name: e.target.value })}
            className="bg-[#13151f] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500"
          />
          <input
            placeholder="Version (e.g. v3)"
            value={form.version}
            onChange={(e) => setForm({ ...form, version: e.target.value })}
            className="bg-[#13151f] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500"
          />
        </div>
        <textarea
          placeholder="Prompt text — use {variable} placeholders..."
          value={form.prompt_text}
          onChange={(e) => setForm({ ...form, prompt_text: e.target.value })}
          rows={5}
          className="w-full bg-[#13151f] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500 resize-none font-mono mb-3"
        />
        <button
          onClick={handleCreate}
          disabled={creating || !form.prompt_name || !form.version || !form.prompt_text}
          className="px-4 py-2 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 text-white text-sm rounded-lg font-medium transition-colors"
        >
          {creating ? "Creating…" : "Create Version"}
        </button>
      </Card>

      {/* Grouped list */}
      {loading ? (
        <p className="text-slate-500 text-sm">Loading…</p>
      ) : Object.keys(grouped).length === 0 ? (
        <Card>
          <p className="text-slate-500 text-sm text-center py-6">No prompt versions yet. Create one above.</p>
        </Card>
      ) : (
        Object.entries(grouped).map(([name, rawVersions]) => {
          const versions = [...rawVersions].sort((a, b) => a.version.localeCompare(b.version));
          const diff = diffs[name];
          const canCompare = versions.length >= 2;

          function openDiff() {
            setDiffs((prev) => ({
              ...prev,
              [name]: {
                leftId:  versions[0].id,
                rightId: versions[1].id,
              },
            }));
          }
          function closeDiff() {
            setDiffs((prev) => { const n = { ...prev }; delete n[name]; return n; });
          }

          const leftPv  = diff ? versions.find((v) => v.id === diff.leftId)  ?? versions[0] : null;
          const rightPv = diff ? versions.find((v) => v.id === diff.rightId) ?? versions[1] : null;

          return (
            <Card key={name} padding="none">
              {/* Header */}
              <div className="px-5 py-3.5 border-b border-[#252b3b] flex items-center justify-between gap-4">
                <div>
                  <h3 className="font-medium text-slate-200 text-sm">{name}</h3>
                  <p className="text-xs text-slate-500 mt-0.5">{versions.length} version(s)</p>
                </div>
                {canCompare && (
                  diff ? (
                    <button
                      onClick={closeDiff}
                      className="text-xs text-slate-500 hover:text-slate-300 px-3 py-1.5 border border-[#252b3b] rounded-lg transition-colors"
                    >
                      Close diff
                    </button>
                  ) : (
                    <button
                      onClick={openDiff}
                      className="text-xs text-brand-400 hover:text-brand-300 px-3 py-1.5 border border-brand-500/30 rounded-lg transition-colors flex items-center gap-1.5"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 14 14">
                        <rect x="1" y="2" width="5" height="10" rx="1" stroke="currentColor" strokeWidth="1.2"/>
                        <rect x="8" y="2" width="5" height="10" rx="1" stroke="currentColor" strokeWidth="1.2"/>
                        <line x1="3.5" y1="5" x2="3.5" y2="5" stroke="#ef4444" strokeWidth="1.5" strokeLinecap="round"/>
                        <line x1="10.5" y1="5" x2="10.5" y2="5" stroke="#22c55e" strokeWidth="1.5" strokeLinecap="round"/>
                      </svg>
                      Compare
                    </button>
                  )
                )}
              </div>

              {/* Version table */}
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#1e2235]">
                    {["Version", "Status", "Created", "Preview", ""].map((h) => (
                      <th key={h} className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {versions.map((p) => (
                    <tr key={p.id} className="border-b border-[#1e2235] hover:bg-white/[0.02] transition-colors">
                      <td className="px-5 py-3.5">
                        <span className="font-mono text-xs bg-[#252b3b] px-2 py-1 rounded text-slate-300">{p.version}</span>
                      </td>
                      <td className="px-5 py-3.5">
                        <span className={`text-xs font-medium ${p.is_active ? "text-emerald-400" : "text-slate-600"}`}>
                          {p.is_active ? "Active" : "Inactive"}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-slate-500 text-xs">
                        {format(new Date(p.created_at), "MMM d, yyyy")}
                      </td>
                      <td className="px-5 py-3.5 text-slate-500 text-xs max-w-xs truncate">
                        {p.prompt_text.slice(0, 80)}{p.prompt_text.length > 80 ? "…" : ""}
                      </td>
                      <td className="px-5 py-3.5">
                        <Link href={`/prompts/${p.id}`} className="text-brand-400 text-xs hover:text-brand-300 font-medium">
                          View →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              {/* Inline diff + metrics panel */}
              {diff && leftPv && rightPv && (
                <div className="border-t border-[#252b3b] px-5 py-5 space-y-5">
                  {/* Version selectors */}
                  <div className="flex items-center gap-4 flex-wrap">
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500">A</span>
                      <select
                        value={diff.leftId}
                        onChange={(e) => setDiffs((prev) => ({ ...prev, [name]: { ...prev[name], leftId: e.target.value } }))}
                        className="bg-[#13151f] border border-[#252b3b] text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-brand-500"
                      >
                        {versions.map((v) => (
                          <option key={v.id} value={v.id}>{v.version}</option>
                        ))}
                      </select>
                    </div>
                    <span className="text-slate-600 text-xs">vs</span>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-slate-500">B</span>
                      <select
                        value={diff.rightId}
                        onChange={(e) => setDiffs((prev) => ({ ...prev, [name]: { ...prev[name], rightId: e.target.value } }))}
                        className="bg-[#13151f] border border-[#252b3b] text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-brand-500"
                      >
                        {versions.map((v) => (
                          <option key={v.id} value={v.id}>{v.version}</option>
                        ))}
                      </select>
                    </div>
                  </div>

                  {/* Metrics comparison */}
                  <MetricsCompare
                    leftId={diff.leftId}
                    rightId={diff.rightId}
                    leftPv={leftPv}
                    rightPv={rightPv}
                  />

                  {/* Text diff */}
                  <div>
                    <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-2">Prompt Diff</p>
                    <PromptDiff left={leftPv} right={rightPv} />
                  </div>
                </div>
              )}
            </Card>
          );
        })
      )}
    </div>
  );
}
