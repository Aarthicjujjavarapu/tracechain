"use client";
import { useEffect, useState } from "react";
import StatCard from "@/components/ui/StatCard";
import Card from "@/components/ui/Card";
import SimpleAreaChart from "@/components/charts/AreaChart";
import HBarChart from "@/components/charts/HBarChart";
import WorkflowHealthCard from "@/components/workflows/WorkflowHealthCard";
import { api } from "@/lib/api";
import type { OverviewMetrics, WorkflowHealth } from "@/types";

const DEMO: OverviewMetrics = {
  total_runs: 60, success_rate: 0.85, avg_latency_ms: 1240,
  total_cost: 0.0042, total_tokens: 48200, failure_count: 9,
};
const DEMO_RUNS    = [
  { date: "05-06", value: 4  }, { date: "05-07", value: 7  },
  { date: "05-08", value: 3  }, { date: "05-09", value: 9  },
  { date: "05-10", value: 6  }, { date: "05-11", value: 5  },
  { date: "05-12", value: 11 }, { date: "05-13", value: 8  },
  { date: "05-14", value: 6  }, { date: "05-15", value: 4  },
  { date: "05-16", value: 7  }, { date: "05-17", value: 5  },
  { date: "05-18", value: 9  }, { date: "05-19", value: 6  },
];
const DEMO_LATENCY = DEMO_RUNS.map((d, i) => ({ ...d, value: [820,950,710,1100,680,790,1240,860,920,730,1050,680,890,750][i] }));
const DEMO_COST    = DEMO_LATENCY.map((d) => ({ ...d, value: +(d.value * 0.000003).toFixed(6) }));
const DEMO_FAIL    = [
  { label: "validate_answer",  value: 8 }, { label: "generate_answer", value: 5 },
  { label: "retrieve_docs",    value: 3 }, { label: "search_documents", value: 2 },
];

export default function DashboardPage() {
  const [metrics,   setMetrics]   = useState<OverviewMetrics>(DEMO);
  const [runsTs,    setRunsTs]    = useState(DEMO_RUNS);
  const [latency,   setLatency]   = useState(DEMO_LATENCY);
  const [cost,      setCost]      = useState(DEMO_COST);
  const [failures,  setFailures]  = useState(DEMO_FAIL);
  const [workflows, setWorkflows] = useState<WorkflowHealth[]>([]);
  const [loaded,    setLoaded]    = useState(false);

  useEffect(() => {
    Promise.allSettled([
      api.metrics.overview(),
      api.metrics.timeseries.runs(14),
      api.metrics.timeseries.latency(14),
      api.metrics.timeseries.cost(14),
      api.metrics.failures(),
      api.metrics.workflows(30),
    ]).then(([ov, runs, lat, cost_, fail, wfs]) => {
      if (ov.status   === "fulfilled") setMetrics(ov.value);
      if (runs.status === "fulfilled") setRunsTs(
        runs.value.map((d) => ({ date: d.date.slice(5), value: d.value }))
      );
      if (lat.status  === "fulfilled") setLatency(
        lat.value.map((d) => ({ date: d.date.slice(5), value: d.value }))
      );
      if (cost_.status === "fulfilled") setCost(
        cost_.value.map((d) => ({ date: d.date.slice(5), value: d.value }))
      );
      if (fail.status === "fulfilled") setFailures(
        fail.value.slice(0, 6).map((r) => ({ label: r.step_name, value: r.failure_count }))
      );
      if (wfs.status === "fulfilled") setWorkflows(wfs.value);
      setLoaded(true);
    });
  }, []);

  const kpis = [
    { label: "Total Runs",   value: metrics.total_runs.toLocaleString(),           accent: "default" as const },
    { label: "Success Rate", value: `${(metrics.success_rate * 100).toFixed(1)}%`, accent: "green"   as const },
    { label: "Avg Latency",  value: `${Math.round(metrics.avg_latency_ms)}ms`,     accent: "blue"    as const },
    { label: "Total Cost",   value: `$${metrics.total_cost.toFixed(4)}`,           accent: "amber"   as const },
    { label: "Total Tokens", value: metrics.total_tokens.toLocaleString(),         accent: "violet"  as const },
    { label: "Failures",     value: metrics.failure_count.toLocaleString(),        accent: "red"     as const },
  ];

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">LLM workflow observability overview</p>
        </div>
        {!loaded && (
          <span className="text-xs text-slate-600 animate-pulse">loading live data…</span>
        )}
      </div>

      {/* KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-6 gap-4">
        {kpis.map((k) => <StatCard key={k.label} {...k} />)}
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Runs per Day</h2>
          <SimpleAreaChart
            data={runsTs} color="#4f6ef7" valueLabel="runs"
            formatValue={(v) => String(Math.round(v))} height={160}
          />
        </Card>
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Avg Latency — 14 days</h2>
          <SimpleAreaChart
            data={latency} color="#38bdf8" valueLabel="ms"
            formatValue={(v) => `${Math.round(v)}ms`} height={160}
          />
        </Card>
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Daily Cost — 14 days</h2>
          <SimpleAreaChart
            data={cost} color="#22c55e" valueLabel="$"
            formatValue={(v) => `$${v.toFixed(4)}`} height={160}
          />
        </Card>
      </div>

      {/* Failures */}
      <Card>
        <h2 className="text-sm font-medium text-slate-300 mb-4">Failures by Step</h2>
        <HBarChart
          data={failures} color="#ef4444"
          formatValue={(v) => String(v)}
          height={failures.length * 44 + 20}
        />
      </Card>

      {/* Workflow Health Matrix */}
      {workflows.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-medium text-slate-300">Workflow Health — last 30 days</h2>
            <span className="text-xs text-slate-600">{workflows.length} workflow{workflows.length !== 1 ? "s" : ""}</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {workflows.map((wf) => (
              <WorkflowHealthCard key={wf.workflow_name} wf={wf} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
