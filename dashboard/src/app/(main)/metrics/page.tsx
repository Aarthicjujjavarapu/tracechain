"use client";
import { useEffect, useMemo, useState } from "react";
import Card from "@/components/ui/Card";
import SimpleAreaChart from "@/components/charts/AreaChart";
import HBarChart from "@/components/charts/HBarChart";
import BudgetAlert from "@/components/ui/BudgetAlert";
import { api } from "@/lib/api";
import { useBudget } from "@/lib/useBudget";

type PT       = { date: string; value: number };
type LabelVal = { label: string; value: number };

const PRESETS = [7, 14, 30, 90] as const;
type Preset = typeof PRESETS[number];

export default function MetricsPage() {
  const [days,       setDays]      = useState<Preset>(14);
  const [latencyTs,  setLatencyTs] = useState<PT[]>([]);
  const [costTs,     setCostTs]    = useState<PT[]>([]);
  const [srTs,       setSrTs]      = useState<PT[]>([]);
  const [runsTs,     setRunsTs]    = useState<PT[]>([]);
  const [qualityTs,  setQualityTs] = useState<PT[]>([]);
  const [tokensTs,   setTokensTs]  = useState<PT[]>([]);
  const [costModel,  setCostModel] = useState<LabelVal[]>([]);
  const [failures,   setFailures]  = useState<LabelVal[]>([]);
  const [latencyWf,  setLatencyWf] = useState<LabelVal[]>([]);
  const [loading,    setLoading]   = useState(true);

  const { perRun, perDay, savePerRun, savePerDay } = useBudget();
  const [perDayInput, setPerDayInput] = useState("");
  const [perRunInput, setPerRunInput] = useState("");

  // Sync inputs when budget values load from localStorage
  useEffect(() => { if (perDay != null) setPerDayInput(String(perDay)); }, [perDay]);
  useEffect(() => { if (perRun != null) setPerRunInput(String(perRun)); }, [perRun]);

  const exceededDays = useMemo(
    () => perDay != null ? costTs.filter((d) => d.value > perDay) : [],
    [costTs, perDay],
  );

  useEffect(() => {
    setLoading(true);
    Promise.allSettled([
      api.metrics.timeseries.latency(days),
      api.metrics.timeseries.cost(days),
      api.metrics.timeseries.successRate(days),
      api.metrics.timeseries.runs(days),
      api.metrics.timeseries.quality(days),
      api.metrics.timeseries.tokens(days),
      api.metrics.cost(days),
      api.metrics.failures(days),
      api.metrics.latency(days),
    ]).then(([lat, cost, sr, runs, quality, tokens, costM, fail, latWf]) => {
      if (lat.status     === "fulfilled") setLatencyTs(lat.value);
      if (cost.status    === "fulfilled") setCostTs(cost.value);
      if (sr.status      === "fulfilled") setSrTs(sr.value);
      if (runs.status    === "fulfilled") setRunsTs(runs.value);
      if (quality.status === "fulfilled") setQualityTs(quality.value);
      if (tokens.status  === "fulfilled") setTokensTs(tokens.value);
      if (costM.status   === "fulfilled")
        setCostModel(costM.value.map((r) => ({ label: r.model, value: r.total_cost })));
      if (fail.status    === "fulfilled")
        setFailures(fail.value.map((r) => ({ label: r.step_name, value: r.failure_count })));
      if (latWf.status   === "fulfilled")
        setLatencyWf(latWf.value.map((r) => ({ label: r.workflow_name, value: r.avg_latency_ms })));
      setLoading(false);
    });
  }, [days]);

  const empty = (data: unknown[]) => !loading && data.length === 0;

  function commitPerDay() {
    const v = parseFloat(perDayInput);
    savePerDay(isFinite(v) && v > 0 ? v : null);
    if (!isFinite(v) || v <= 0) setPerDayInput("");
  }

  function commitPerRun() {
    const v = parseFloat(perRunInput);
    savePerRun(isFinite(v) && v > 0 ? v : null);
    if (!isFinite(v) || v <= 0) setPerRunInput("");
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-white">Metrics</h1>
          <p className="text-sm text-slate-500 mt-1">
            Performance, cost, quality, and reliability — last {days} days
          </p>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Budget inputs */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 whitespace-nowrap">Daily budget $</span>
            <input
              type="number"
              min="0"
              step="0.0001"
              value={perDayInput}
              onChange={(e) => setPerDayInput(e.target.value)}
              onBlur={commitPerDay}
              onKeyDown={(e) => e.key === "Enter" && commitPerDay()}
              placeholder="none"
              className="w-24 bg-[#13151f] border border-[#252b3b] text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-brand-500 placeholder:text-slate-700"
            />
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-500 whitespace-nowrap">Per-run budget $</span>
            <input
              type="number"
              min="0"
              step="0.0001"
              value={perRunInput}
              onChange={(e) => setPerRunInput(e.target.value)}
              onBlur={commitPerRun}
              onKeyDown={(e) => e.key === "Enter" && commitPerRun()}
              placeholder="none"
              className="w-24 bg-[#13151f] border border-[#252b3b] text-slate-300 text-xs rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-brand-500 placeholder:text-slate-700"
            />
          </div>

          {/* Range picker */}
          <div className="flex items-center gap-1 bg-[#13151f] border border-[#252b3b] rounded-lg p-1">
            {PRESETS.map((p) => (
              <button
                key={p}
                onClick={() => setDays(p)}
                className={`px-3 py-1.5 text-xs rounded-md font-medium transition-colors ${
                  days === p
                    ? "bg-brand-500 text-white"
                    : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
                }`}
              >
                {p}d
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Budget alert */}
      {perDay != null && (
        <BudgetAlert exceededDays={exceededDays} threshold={perDay} />
      )}

      {/* Row 1 — volume + latency */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Runs per Day</h2>
          {loading ? <Skeleton /> : empty(runsTs) ? <Empty /> : (
            <SimpleAreaChart
              data={runsTs} color="#4f6ef7" valueLabel="runs"
              formatValue={(v) => String(Math.round(v))} height={180}
            />
          )}
        </Card>
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Avg Latency per Day</h2>
          {loading ? <Skeleton /> : empty(latencyTs) ? <Empty /> : (
            <SimpleAreaChart
              data={latencyTs} color="#38bdf8" valueLabel="ms"
              formatValue={(v) => `${Math.round(v)}ms`} height={180}
            />
          )}
        </Card>
      </div>

      {/* Row 2 — cost + tokens */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Cost per Day</h2>
          {loading ? <Skeleton /> : empty(costTs) ? <Empty /> : (
            <SimpleAreaChart
              data={costTs} color="#22c55e" valueLabel="$"
              formatValue={(v) => `$${v.toFixed(4)}`} height={180}
              threshold={perDay ?? undefined}
            />
          )}
        </Card>
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Tokens per Day</h2>
          {loading ? <Skeleton /> : empty(tokensTs) ? <Empty /> : (
            <SimpleAreaChart
              data={tokensTs} color="#a78bfa" valueLabel="tokens"
              formatValue={(v) => v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(Math.round(v))}
              height={180}
            />
          )}
        </Card>
      </div>

      {/* Row 3 — quality + success rate */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Avg Quality Score per Day</h2>
          {loading ? <Skeleton /> : empty(qualityTs) ? <Empty /> : (
            <SimpleAreaChart
              data={qualityTs} color="#f59e0b" valueLabel="score"
              formatValue={(v) => `${(v * 100).toFixed(0)}%`} height={180}
            />
          )}
        </Card>
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Success Rate per Day</h2>
          {loading ? <Skeleton /> : empty(srTs) ? <Empty /> : (
            <SimpleAreaChart
              data={srTs} color="#34d399" valueLabel="rate"
              formatValue={(v) => `${(v * 100).toFixed(0)}%`} height={180}
            />
          )}
        </Card>
      </div>

      {/* Row 4 — breakdowns */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Cost by Model</h2>
          {loading ? <Skeleton /> : empty(costModel) ? <Empty /> : (
            <HBarChart
              data={costModel}
              formatValue={(v) => `$${v.toFixed(4)}`}
              height={Math.max(180, costModel.length * 44)}
            />
          )}
        </Card>
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Failures by Step</h2>
          {loading ? <Skeleton /> : empty(failures) ? <Empty /> : (
            <HBarChart
              data={failures} color="#ef4444"
              formatValue={(v) => String(v)}
              height={Math.max(180, failures.length * 44)}
            />
          )}
        </Card>
      </div>

      {/* Row 5 — latency by workflow */}
      <Card>
        <h2 className="text-sm font-medium text-slate-300 mb-4">Avg Latency by Workflow</h2>
        {loading ? <Skeleton /> : empty(latencyWf) ? <Empty /> : (
          <HBarChart
            data={latencyWf} color="#8b5cf6"
            formatValue={(v) => `${Math.round(v)}ms`}
            height={Math.max(180, latencyWf.length * 44)}
          />
        )}
      </Card>
    </div>
  );
}

function Empty() {
  return (
    <p className="text-slate-600 text-sm py-10 text-center">
      No data yet — run some workflows first.
    </p>
  );
}

function Skeleton() {
  return (
    <div className="py-10 flex items-center justify-center">
      <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
    </div>
  );
}
