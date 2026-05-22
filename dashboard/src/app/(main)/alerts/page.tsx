"use client";
import { useEffect, useState } from "react";
import Card from "@/components/ui/Card";
import StatCard from "@/components/ui/StatCard";
import { api } from "@/lib/api";
import type { AlertFiring, AlertRule, AlertMetric, AlertOperator, WebhookDestination, WebhookDelivery } from "@/types";
import { format } from "date-fns";

// ── helpers ───────────────────────────────────────────────────────────────────

const METRIC_LABELS: Record<AlertMetric, string> = {
  success_rate:      "Success Rate",
  avg_latency_ms:    "Avg Latency (ms)",
  avg_cost:          "Avg Cost ($)",
  open_incidents:    "Open Incidents",
  reliability_score: "Reliability Score",
};

const OPERATOR_LABELS: Record<AlertOperator, string> = {
  lt:  "<",
  lte: "≤",
  gt:  ">",
  gte: "≥",
};

const SEVERITY_COLORS: Record<string, string> = {
  LOW:      "text-slate-400 bg-slate-500/10 border-slate-500/20",
  MEDIUM:   "text-amber-400 bg-amber-500/10 border-amber-500/20",
  HIGH:     "text-orange-400 bg-orange-500/10 border-orange-500/20",
  CRITICAL: "text-red-400 bg-red-500/10 border-red-500/20",
};

function formatThreshold(metric: AlertMetric, value: number): string {
  if (metric === "success_rate")      return `${(value * 100).toFixed(0)}%`;
  if (metric === "avg_latency_ms")    return `${Math.round(value)}ms`;
  if (metric === "avg_cost")          return `$${value.toFixed(5)}`;
  if (metric === "reliability_score") return `${value.toFixed(0)}`;
  return String(value);
}

function formatMetricValue(metric: AlertMetric, value: number): string {
  if (metric === "success_rate")      return `${(value * 100).toFixed(1)}%`;
  if (metric === "avg_latency_ms")    return `${Math.round(value)}ms`;
  if (metric === "avg_cost")          return `$${value.toFixed(5)}`;
  if (metric === "reliability_score") return value.toFixed(1);
  return value.toFixed(0);
}

// ── blank form ────────────────────────────────────────────────────────────────

const BLANK = {
  name: "", metric: "success_rate" as AlertMetric,
  operator: "lt" as AlertOperator, threshold: "",
  window_minutes: "60", severity: "MEDIUM", workflow_name: "",
};

const BLANK_WEBHOOK = { name: "", url: "", secret: "" };

// ── component ─────────────────────────────────────────────────────────────────

export default function AlertsPage() {
  const [rules,      setRules]      = useState<AlertRule[]>([]);
  const [firings,    setFirings]    = useState<AlertFiring[]>([]);
  const [summary,    setSummary]    = useState({ total_rules: 0, enabled_rules: 0, firing_now: 0 });
  const [webhooks,   setWebhooks]   = useState<WebhookDestination[]>([]);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [loading,    setLoading]    = useState(true);
  const [form,       setForm]       = useState(BLANK);
  const [wForm,      setWForm]      = useState(BLANK_WEBHOOK);
  const [saving,     setSaving]     = useState(false);
  const [wSaving,    setWSaving]    = useState(false);
  const [err,        setErr]        = useState("");
  const [wErr,       setWErr]       = useState("");

  const load = () => {
    setLoading(true);
    Promise.allSettled([
      api.alerts.rules.list(),
      api.alerts.firings(false, 50),
      api.alerts.summary(),
      api.webhooks.list(),
      api.webhooks.deliveries(20),
    ]).then(([r, f, s, wh, dl]) => {
      if (r.status  === "fulfilled") setRules(r.value);
      if (f.status  === "fulfilled") setFirings(f.value);
      if (s.status  === "fulfilled") setSummary(s.value);
      if (wh.status === "fulfilled") setWebhooks(wh.value);
      if (dl.status === "fulfilled") setDeliveries(dl.value);
      setLoading(false);
    });
  };

  useEffect(load, []);

  const handleCreate = async () => {
    if (!form.name || !form.threshold) { setErr("Name and threshold are required."); return; }
    const t = parseFloat(form.threshold);
    if (isNaN(t)) { setErr("Threshold must be a number."); return; }
    setSaving(true); setErr("");
    try {
      await api.alerts.rules.create({
        name:           form.name,
        metric:         form.metric,
        operator:       form.operator,
        threshold:      t,
        window_minutes: parseInt(form.window_minutes) || 60,
        severity:       form.severity,
        workflow_name:  form.workflow_name || null,
        enabled:        true,
      } as any);
      setForm(BLANK);
      load();
    } catch (e: any) {
      setErr(e.message ?? "Failed to create rule.");
    } finally {
      setSaving(false);
    }
  };

  const toggleEnabled = async (rule: AlertRule) => {
    await api.alerts.rules.update(rule.id, { enabled: !rule.enabled });
    load();
  };

  const deleteRule = async (id: string) => {
    await api.alerts.rules.delete(id);
    load();
  };

  const handleCreateWebhook = async () => {
    if (!wForm.name || !wForm.url) { setWErr("Name and URL are required."); return; }
    setWSaving(true); setWErr("");
    try {
      await api.webhooks.create({ name: wForm.name, url: wForm.url, secret: wForm.secret || undefined });
      setWForm(BLANK_WEBHOOK);
      load();
    } catch (e: any) {
      setWErr(e.message ?? "Failed to create webhook.");
    } finally {
      setWSaving(false);
    }
  };

  const toggleWebhook = async (wh: WebhookDestination) => {
    await api.webhooks.update(wh.id, { enabled: !wh.enabled });
    load();
  };

  const deleteWebhook = async (id: string) => {
    await api.webhooks.delete(id);
    load();
  };

  const activeFirings  = firings.filter((f) => f.is_active);
  const resolvedFiring = firings.filter((f) => !f.is_active);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-semibold text-white">Alert Rules</h1>
        <p className="text-sm text-slate-500 mt-1">Define thresholds — alerts fire and resolve automatically after each run</p>
      </div>

      {/* Summary KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        <StatCard label="Total Rules"   value={String(summary.total_rules)}   accent="default" />
        <StatCard label="Enabled Rules" value={String(summary.enabled_rules)} accent="blue"    />
        <StatCard label="Firing Now"    value={String(summary.firing_now)}    accent={summary.firing_now > 0 ? "red" : "green"} />
      </div>

      {/* Active firings banner */}
      {activeFirings.length > 0 && (
        <div className="flex items-start gap-3 px-4 py-3 bg-red-500/10 border border-red-500/25 rounded-xl">
          <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse shrink-0 mt-1" />
          <div>
            <p className="text-red-300 font-medium text-sm">
              {activeFirings.length} alert{activeFirings.length !== 1 ? "s" : ""} firing
            </p>
            <p className="text-red-500/80 text-xs mt-0.5">
              Check the firing alerts below and review your workflow metrics.
            </p>
          </div>
        </div>
      )}

      {/* Create rule */}
      <Card>
        <h2 className="text-sm font-medium text-slate-300 mb-4">Create Alert Rule</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3 mb-3">
          <input
            placeholder="Rule name (e.g. Low success rate)"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="bg-[#0d0f1a] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500"
          />
          <select
            value={form.metric}
            onChange={(e) => setForm({ ...form, metric: e.target.value as AlertMetric })}
            className="bg-[#0d0f1a] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500"
          >
            {(Object.entries(METRIC_LABELS) as [AlertMetric, string][]).map(([k, v]) => (
              <option key={k} value={k}>{v}</option>
            ))}
          </select>
          <div className="flex gap-2">
            <select
              value={form.operator}
              onChange={(e) => setForm({ ...form, operator: e.target.value as AlertOperator })}
              className="bg-[#0d0f1a] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500 w-20"
            >
              {(Object.entries(OPERATOR_LABELS) as [AlertOperator, string][]).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            <input
              placeholder="Threshold"
              type="number"
              step="any"
              value={form.threshold}
              onChange={(e) => setForm({ ...form, threshold: e.target.value })}
              className="flex-1 bg-[#0d0f1a] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500"
            />
          </div>
          <select
            value={form.severity}
            onChange={(e) => setForm({ ...form, severity: e.target.value })}
            className="bg-[#0d0f1a] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500"
          >
            {["LOW", "MEDIUM", "HIGH", "CRITICAL"].map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
          <input
            placeholder="Window (minutes, default 60)"
            type="number"
            value={form.window_minutes}
            onChange={(e) => setForm({ ...form, window_minutes: e.target.value })}
            className="bg-[#0d0f1a] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500"
          />
          <input
            placeholder="Workflow name (optional — leave blank for all)"
            value={form.workflow_name}
            onChange={(e) => setForm({ ...form, workflow_name: e.target.value })}
            className="bg-[#0d0f1a] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500"
          />
        </div>
        {err && <p className="text-red-400 text-xs mb-3">{err}</p>}
        <button
          onClick={handleCreate}
          disabled={saving}
          className="px-4 py-2 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 text-white text-sm rounded-lg font-medium transition-colors"
        >
          {saving ? "Creating…" : "Create Rule"}
        </button>
      </Card>

      {/* Rules table */}
      {loading ? (
        <p className="text-slate-500 text-sm">Loading…</p>
      ) : rules.length === 0 ? (
        <Card>
          <p className="text-slate-500 text-sm text-center py-6">No alert rules yet. Create one above.</p>
        </Card>
      ) : (
        <Card padding="none">
          <div className="px-5 py-3.5 border-b border-[#252b3b]">
            <h2 className="text-sm font-medium text-slate-300">Configured Rules</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e2235]">
                {["Rule", "Condition", "Window", "Severity", "Workflow", "Status", ""].map((h) => (
                  <th key={h} className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => {
                const isFiring = activeFirings.some((f) => f.rule_id === rule.id);
                return (
                  <tr key={rule.id} className="border-b border-[#1e2235] hover:bg-white/[0.02] transition-colors">
                    <td className="px-5 py-3.5">
                      <div className="flex items-center gap-2">
                        {isFiring && <span className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse shrink-0" />}
                        <span className="text-slate-300 font-medium text-sm">{rule.name}</span>
                      </div>
                      <p className="text-xs text-slate-600 mt-0.5">{METRIC_LABELS[rule.metric]}</p>
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="font-mono text-xs bg-[#1e2235] px-2 py-1 rounded text-slate-400">
                        {METRIC_LABELS[rule.metric]} {OPERATOR_LABELS[rule.operator]} {formatThreshold(rule.metric, rule.threshold)}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-slate-500 text-xs">{rule.window_minutes}m</td>
                    <td className="px-5 py-3.5">
                      <span className={`text-[10px] font-medium border px-1.5 py-0.5 rounded ${SEVERITY_COLORS[rule.severity] ?? SEVERITY_COLORS.MEDIUM}`}>
                        {rule.severity}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-slate-500 text-xs">
                      {rule.workflow_name ?? <span className="text-slate-700">all</span>}
                    </td>
                    <td className="px-5 py-3.5">
                      <button
                        onClick={() => toggleEnabled(rule)}
                        className={`text-xs font-medium ${rule.enabled ? "text-emerald-400" : "text-slate-600"} hover:text-slate-300 transition-colors`}
                      >
                        {rule.enabled ? "Enabled" : "Disabled"}
                      </button>
                    </td>
                    <td className="px-5 py-3.5">
                      <button
                        onClick={() => deleteRule(rule.id)}
                        className="text-slate-600 hover:text-red-400 transition-colors text-xs"
                        title="Delete rule"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}

      {/* Active firings */}
      {activeFirings.length > 0 && (
        <div>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Active Firings</h2>
          <div className="space-y-3">
            {activeFirings.map((f) => {
              const rule = rules.find((r) => r.id === f.rule_id);
              return (
                <div key={f.id} className="flex items-center justify-between gap-4 px-4 py-3 rounded-xl border border-red-500/25 bg-red-500/5">
                  <div className="flex items-center gap-3">
                    <span className="w-2 h-2 rounded-full bg-red-500 animate-pulse shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-red-300">{rule?.name ?? f.rule_id}</p>
                      <p className="text-xs text-red-500/70 mt-0.5">
                        {rule ? `${METRIC_LABELS[rule.metric]} = ${formatMetricValue(rule.metric, f.metric_value)}` : `value: ${f.metric_value}`}
                      </p>
                    </div>
                  </div>
                  <p className="text-xs text-slate-600 shrink-0">{format(new Date(f.fired_at), "MMM d, HH:mm")}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Recent resolved firings */}
      {resolvedFiring.length > 0 && (
        <Card padding="none">
          <div className="px-5 py-3.5 border-b border-[#252b3b]">
            <h2 className="text-sm font-medium text-slate-300">Recent Resolved</h2>
          </div>
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-[#1e2235]">
                {["Rule", "Metric Value", "Fired", "Resolved"].map((h) => (
                  <th key={h} className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {resolvedFiring.slice(0, 20).map((f) => {
                const rule = rules.find((r) => r.id === f.rule_id);
                return (
                  <tr key={f.id} className="border-b border-[#1e2235] hover:bg-white/[0.02]">
                    <td className="px-5 py-3 text-slate-400 text-xs">{rule?.name ?? f.rule_id}</td>
                    <td className="px-5 py-3 text-slate-500 text-xs font-mono">
                      {rule ? formatMetricValue(rule.metric, f.metric_value) : f.metric_value}
                    </td>
                    <td className="px-5 py-3 text-slate-600 text-xs">{format(new Date(f.fired_at), "MMM d, HH:mm")}</td>
                    <td className="px-5 py-3 text-emerald-600 text-xs">
                      {f.resolved_at ? format(new Date(f.resolved_at), "MMM d, HH:mm") : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}

      {/* ── Webhook Destinations ─────────────────────────────────────────── */}
      <div className="border-t border-[#1e2235] pt-8">
        <div className="mb-6">
          <h2 className="text-base font-semibold text-white">Webhook Destinations</h2>
          <p className="text-sm text-slate-500 mt-1">
            Receive signed HTTP POST notifications when alerts fire or resolve.
            Include a secret to verify requests with <code className="text-slate-400 bg-[#1e2235] px-1 rounded text-xs">X-TraceChain-Signature</code>.
          </p>
        </div>

        {/* Create webhook form */}
        <Card>
          <h3 className="text-sm font-medium text-slate-300 mb-4">Add Destination</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-3">
            <input
              placeholder="Name (e.g. Slack #alerts)"
              value={wForm.name}
              onChange={(e) => setWForm({ ...wForm, name: e.target.value })}
              className="bg-[#0d0f1a] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500"
            />
            <input
              placeholder="https://hooks.example.com/recv"
              value={wForm.url}
              onChange={(e) => setWForm({ ...wForm, url: e.target.value })}
              className="bg-[#0d0f1a] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500"
            />
            <input
              placeholder="Secret (optional — for HMAC signing)"
              type="password"
              value={wForm.secret}
              onChange={(e) => setWForm({ ...wForm, secret: e.target.value })}
              className="bg-[#0d0f1a] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500"
            />
          </div>
          {wErr && <p className="text-red-400 text-xs mb-3">{wErr}</p>}
          <button
            onClick={handleCreateWebhook}
            disabled={wSaving}
            className="px-4 py-2 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 text-white text-sm rounded-lg font-medium transition-colors"
          >
            {wSaving ? "Adding…" : "Add Destination"}
          </button>
        </Card>

        {/* Destinations table */}
        {webhooks.length > 0 && (
          <Card padding="none" className="mt-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-[#1e2235]">
                  {["Destination", "URL", "Signing", "Status", ""].map((h) => (
                    <th key={h} className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {webhooks.map((wh) => (
                  <tr key={wh.id} className="border-b border-[#1e2235] hover:bg-white/[0.02]">
                    <td className="px-5 py-3.5 text-slate-300 font-medium text-sm">{wh.name}</td>
                    <td className="px-5 py-3.5">
                      <span className="font-mono text-xs text-slate-500 truncate max-w-[260px] block">{wh.url}</span>
                    </td>
                    <td className="px-5 py-3.5">
                      {wh.secret
                        ? <span className="text-xs text-emerald-500">HMAC-SHA256</span>
                        : <span className="text-xs text-slate-600">none</span>}
                    </td>
                    <td className="px-5 py-3.5">
                      <button
                        onClick={() => toggleWebhook(wh)}
                        className={`text-xs font-medium ${wh.enabled ? "text-emerald-400" : "text-slate-600"} hover:text-slate-300 transition-colors`}
                      >
                        {wh.enabled ? "Enabled" : "Disabled"}
                      </button>
                    </td>
                    <td className="px-5 py-3.5">
                      <button
                        onClick={() => deleteWebhook(wh.id)}
                        className="text-slate-600 hover:text-red-400 transition-colors text-xs"
                      >
                        Delete
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        )}

        {/* Recent delivery log */}
        {deliveries.length > 0 && (
          <div className="mt-6">
            <h3 className="text-sm font-medium text-slate-400 mb-3">Recent Deliveries</h3>
            <Card padding="none">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#1e2235]">
                    {["Event", "Destination", "Status", "Time"].map((h) => (
                      <th key={h} className="text-left px-5 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {deliveries.map((d) => {
                    const dest = webhooks.find((w) => w.id === d.destination_id);
                    return (
                      <tr key={d.id} className="border-b border-[#1e2235] hover:bg-white/[0.02]">
                        <td className="px-5 py-3">
                          <span className={`text-xs font-mono font-medium ${d.event_type === "alert.fired" ? "text-red-400" : "text-emerald-400"}`}>
                            {d.event_type}
                          </span>
                        </td>
                        <td className="px-5 py-3 text-slate-500 text-xs">{dest?.name ?? d.destination_id.slice(0, 8)}</td>
                        <td className="px-5 py-3">
                          {d.success
                            ? <span className="text-xs text-emerald-500">{d.status_code} OK</span>
                            : <span className="text-xs text-red-400" title={d.error_message ?? undefined}>
                                {d.status_code ? `${d.status_code} Error` : "Failed"}
                              </span>
                          }
                        </td>
                        <td className="px-5 py-3 text-slate-600 text-xs">{format(new Date(d.attempted_at), "MMM d, HH:mm:ss")}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
