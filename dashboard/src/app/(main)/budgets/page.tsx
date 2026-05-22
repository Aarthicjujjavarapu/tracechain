"use client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import Card from "@/components/ui/Card";
import { api } from "@/lib/api";
import type { BudgetStatusOut, SpendSummary, BudgetPeriod } from "@/types";

// ── helpers ───────────────────────────────────────────────────────────────────

function fmt(n: number) {
  if (n < 0.01) return `$${n.toFixed(5)}`;
  return `$${n.toFixed(4)}`;
}

function statusMeta(s: string) {
  switch (s) {
    case "exceeded": return { label: "Exceeded", cls: "bg-red-500/20 text-red-400 border-red-500/30" };
    case "critical": return { label: "Critical",  cls: "bg-orange-500/20 text-orange-400 border-orange-500/30" };
    case "warning":  return { label: "Warning",   cls: "bg-amber-500/20 text-amber-400 border-amber-500/30" };
    default:         return { label: "OK",         cls: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" };
  }
}

function barColor(s: string) {
  switch (s) {
    case "exceeded": return "bg-red-500";
    case "critical": return "bg-orange-500";
    case "warning":  return "bg-amber-400";
    default:         return "bg-emerald-500";
  }
}

function periodLabel(p: BudgetPeriod) {
  return p === "daily" ? "Daily" : p === "monthly" ? "Monthly" : "All-time";
}

// ── sub-components ────────────────────────────────────────────────────────────

function SpendBar({ pct, status }: { pct: number; status: string }) {
  const w = Math.min(100, Math.round(pct * 100));
  return (
    <div className="w-full bg-[#1e2235] rounded-full h-2 overflow-hidden">
      <div
        className={`h-2 rounded-full transition-all ${barColor(status)}`}
        style={{ width: `${w}%` }}
      />
    </div>
  );
}

function BudgetCard({ b, onDelete, onToggle }: {
  b: BudgetStatusOut;
  onDelete: (id: string) => void;
  onToggle: (id: string, enabled: boolean) => void;
}) {
  const { label, cls } = statusMeta(b.status);

  return (
    <Card padding="none">
      <div className="px-5 py-4 space-y-3">
        {/* Header row */}
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="font-medium text-slate-200 text-sm truncate">{b.name}</span>
              <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${cls}`}>{label}</span>
              {!b.enabled && (
                <span className="text-xs text-slate-600 border border-slate-700 rounded-full px-2 py-0.5">Disabled</span>
              )}
            </div>
            <p className="text-xs text-slate-500 mt-0.5">
              {b.workflow_name ? (
                <>Workflow: <Link href={`/runs?workflow_name=${encodeURIComponent(b.workflow_name)}`} className="text-brand-400 hover:text-brand-300">{b.workflow_name}</Link></>
              ) : "All workflows"} · {periodLabel(b.period)} budget
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <button
              onClick={() => onToggle(b.id, !b.enabled)}
              className="text-xs text-slate-500 hover:text-slate-300 px-2.5 py-1 border border-[#252b3b] rounded-lg transition-colors"
            >
              {b.enabled ? "Disable" : "Enable"}
            </button>
            <button
              onClick={() => onDelete(b.id)}
              className="text-xs text-red-500 hover:text-red-400 px-2.5 py-1 border border-red-900/30 rounded-lg transition-colors"
            >
              Delete
            </button>
          </div>
        </div>

        {/* Spend bar */}
        <div className="space-y-1.5">
          <div className="flex items-center justify-between text-xs">
            <span className="text-slate-300 font-medium font-mono">{fmt(b.spent)}</span>
            <span className="text-slate-500">of {fmt(b.budget_usd)} · {Math.round(b.pct_used * 100)}%</span>
          </div>
          <SpendBar pct={b.pct_used} status={b.status} />
          <div className="flex items-center justify-between text-xs text-slate-600">
            <span>{fmt(b.remaining)} remaining</span>
            {b.projected_monthly_usd != null && (
              <span>
                Projected 30d: <span className={b.projected_monthly_usd > b.budget_usd ? "text-red-400" : "text-slate-400"}>
                  {fmt(b.projected_monthly_usd)}
                </span>
              </span>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

// ── page ──────────────────────────────────────────────────────────────────────

const PERIODS: { value: BudgetPeriod; label: string }[] = [
  { value: "monthly", label: "Monthly" },
  { value: "daily",   label: "Daily" },
  { value: "total",   label: "All-time" },
];

interface Form {
  name: string;
  workflow_name: string;
  budget_usd: string;
  period: BudgetPeriod;
  warning_pct: string;
}

const BLANK: Form = { name: "", workflow_name: "", budget_usd: "", period: "monthly", warning_pct: "75" };

export default function BudgetsPage() {
  const [budgets,  setBudgets]  = useState<BudgetStatusOut[]>([]);
  const [summary,  setSummary]  = useState<SpendSummary | null>(null);
  const [loading,  setLoading]  = useState(true);
  const [form,     setForm]     = useState<Form>(BLANK);
  const [saving,   setSaving]   = useState(false);
  const [err,      setErr]      = useState("");

  const load = useCallback(() => {
    setLoading(true);
    Promise.allSettled([
      api.budgets.list(),
      api.budgets.summary(),
    ]).then(([bRes, sRes]) => {
      if (bRes.status === "fulfilled") setBudgets(bRes.value);
      if (sRes.status === "fulfilled") setSummary(sRes.value);
    }).finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const handleCreate = async () => {
    if (!form.name || !form.budget_usd) return;
    setSaving(true);
    setErr("");
    try {
      await api.budgets.create({
        name:          form.name,
        workflow_name: form.workflow_name || null,
        budget_usd:    parseFloat(form.budget_usd),
        period:        form.period,
        warning_pct:   parseFloat(form.warning_pct) / 100,
        enabled:       true,
      });
      setForm(BLANK);
      load();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to create budget");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    await api.budgets.delete(id).catch(() => {});
    load();
  };

  const handleToggle = async (id: string, enabled: boolean) => {
    await api.budgets.update(id, { enabled }).catch(() => {});
    load();
  };

  const inp = "bg-[#13151f] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-white">Cost Budgets</h1>
        <p className="text-sm text-slate-500 mt-1">Track spend against defined limits per workflow or globally</p>
      </div>

      {/* Spend summary KPIs */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          {[
            { label: "Spent Today",      value: fmt(summary.today_usd),    sub: `${summary.run_count_today} run(s)` },
            { label: "Spent This Month", value: fmt(summary.month_usd),    sub: `${summary.run_count_month} run(s)` },
            { label: "All-time Spend",   value: fmt(summary.all_time_usd), sub: "since first run" },
          ].map(({ label, value, sub }) => (
            <Card key={label} padding="sm">
              <p className="text-xs text-slate-500 uppercase tracking-wider">{label}</p>
              <p className="text-xl font-bold text-white mt-1 font-mono">{value}</p>
              <p className="text-xs text-slate-600 mt-0.5">{sub}</p>
            </Card>
          ))}
        </div>
      )}

      {/* Create form */}
      <Card>
        <h2 className="text-sm font-medium text-slate-300 mb-4">Define Budget</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-3">
          <input
            placeholder="Budget name (e.g. Monthly Cap)"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className={inp}
          />
          <input
            placeholder="Workflow name (leave blank for all)"
            value={form.workflow_name}
            onChange={(e) => setForm({ ...form, workflow_name: e.target.value })}
            className={inp}
          />
          <input
            placeholder="Budget (USD, e.g. 5.00)"
            type="number"
            min="0"
            step="0.01"
            value={form.budget_usd}
            onChange={(e) => setForm({ ...form, budget_usd: e.target.value })}
            className={inp}
          />
          <select
            value={form.period}
            onChange={(e) => setForm({ ...form, period: e.target.value as BudgetPeriod })}
            className={inp}
          >
            {PERIODS.map((p) => (
              <option key={p.value} value={p.value}>{p.label}</option>
            ))}
          </select>
          <div className="flex items-center gap-2">
            <input
              placeholder="Warn at % (e.g. 75)"
              type="number"
              min="1"
              max="99"
              value={form.warning_pct}
              onChange={(e) => setForm({ ...form, warning_pct: e.target.value })}
              className={`${inp} flex-1`}
            />
            <span className="text-slate-500 text-sm">%</span>
          </div>
        </div>
        {err && <p className="text-red-400 text-xs mb-3">{err}</p>}
        <button
          onClick={handleCreate}
          disabled={saving || !form.name || !form.budget_usd || !form.warning_pct}
          className="px-4 py-2 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 text-white text-sm rounded-lg font-medium transition-colors"
        >
          {saving ? "Creating…" : "Create Budget"}
        </button>
      </Card>

      {/* Budget cards */}
      {loading ? (
        <p className="text-slate-500 text-sm">Loading…</p>
      ) : budgets.length === 0 ? (
        <Card>
          <p className="text-slate-500 text-sm text-center py-8">
            No budgets defined yet. Create one above to start tracking spend.
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          <p className="text-xs text-slate-500">{budgets.length} budget(s)</p>
          {budgets.map((b) => (
            <BudgetCard
              key={b.id}
              b={b}
              onDelete={handleDelete}
              onToggle={handleToggle}
            />
          ))}
        </div>
      )}
    </div>
  );
}
