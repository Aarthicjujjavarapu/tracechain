"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import Card from "@/components/ui/Card";
import ScoreBar from "@/components/ui/ScoreBar";
import { api } from "@/lib/api";
import type { PromptVersion } from "@/types";

interface Metrics {
  usage_count: number;
  avg_latency_ms: number | null;
  avg_cost: number | null;
  success_rate: number;
  avg_quality_score: number | null;
}

export default function PromptDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [prompt,  setPrompt]  = useState<PromptVersion | null>(null);
  const [metrics, setMetrics] = useState<Metrics | null>(null);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.prompts.get(id),
      api.prompts.metrics(id),
    ]).then(([p, m]) => {
      setPrompt(p as PromptVersion);
      setMetrics(m as Metrics);
    }).catch(() => {});
  }, [id]);

  if (!prompt) return (
    <div className="flex items-center justify-center h-64">
      <p className="text-slate-500 text-sm">Loading…</p>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Link href="/prompts" className="hover:text-slate-300">Prompts</Link>
        <span>/</span>
        <span className="text-slate-300">{prompt.prompt_name}</span>
      </div>

      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold text-white">{prompt.prompt_name}</h1>
        <span className="font-mono text-xs bg-[#252b3b] px-2 py-1 rounded text-slate-300">{prompt.version}</span>
        <span className={`text-xs font-medium ${prompt.is_active ? "text-emerald-400" : "text-slate-600"}`}>
          {prompt.is_active ? "Active" : "Inactive"}
        </span>
      </div>

      {/* Metrics */}
      {metrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: "Total Uses",   value: metrics.usage_count.toLocaleString() },
            { label: "Avg Latency",  value: metrics.avg_latency_ms != null ? `${Math.round(metrics.avg_latency_ms)}ms` : "—" },
            { label: "Avg Cost",     value: metrics.avg_cost != null ? `$${metrics.avg_cost.toFixed(5)}` : "—" },
            { label: "Success Rate", value: `${(metrics.success_rate * 100).toFixed(1)}%` },
          ].map(({ label, value }) => (
            <Card key={label} padding="sm">
              <p className="text-xs text-slate-500 uppercase tracking-wider">{label}</p>
              <p className="text-xl font-bold text-white mt-1">{value}</p>
            </Card>
          ))}
        </div>
      )}

      {/* Quality score bar */}
      {metrics?.avg_quality_score != null && (
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Avg Quality Score</h2>
          <div className="max-w-md">
            <ScoreBar label="Quality" value={metrics.avg_quality_score} />
          </div>
        </Card>
      )}

      {/* Prompt text */}
      <Card>
        <h2 className="text-sm font-medium text-slate-300 mb-3">Prompt Template</h2>
        <pre className="text-sm text-slate-300 bg-[#0d0f1a] rounded-lg p-4 overflow-auto font-mono leading-relaxed whitespace-pre-wrap">
          {prompt.prompt_text}
        </pre>
      </Card>
    </div>
  );
}
