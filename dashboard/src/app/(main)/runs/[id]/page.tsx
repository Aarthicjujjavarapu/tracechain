"use client";
import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import Card from "@/components/ui/Card";
import { StatusBadge } from "@/components/ui/Badge";
import ScoreBar from "@/components/ui/ScoreBar";
import TraceTimeline from "@/components/runs/TraceTimeline";
import LLMCallCard from "@/components/runs/LLMCallCard";
import ReplayHistory from "@/components/runs/ReplayHistory";
import ComparePanel from "@/components/runs/ComparePanel";
import { api } from "@/lib/api";
import type { WorkflowRun, TraceStep, LLMCall, EvaluationResult, HumanFeedback } from "@/types";
import { format } from "date-fns";

type Tab = "trace" | "llm" | "eval" | "io";

export default function RunDetailPage() {
  const { id }  = useParams<{ id: string }>();
  const router  = useRouter();

  const [run,      setRun]      = useState<WorkflowRun | null>(null);
  const [steps,    setSteps]    = useState<TraceStep[]>([]);
  const [llmCalls, setLlmCalls] = useState<LLMCall[]>([]);
  const [evals,    setEvals]    = useState<EvaluationResult[]>([]);
  const [feedback, setFeedback] = useState<HumanFeedback[]>([]);
  const [loadErr,  setLoadErr]  = useState<string | null>(null);

  const [replays,     setReplays]     = useState<WorkflowRun[]>([]);
  const [originalRun, setOriginalRun] = useState<WorkflowRun | null>(null);
  const [originalEval,setOriginalEval]= useState<EvaluationResult | null>(null);

  const [rating,     setRating]     = useState(0);
  const [comment,    setComment]    = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [fbSuccess,  setFbSuccess]  = useState(false);
  const [replaying,  setReplaying]  = useState(false);
  const [activeTab,  setActiveTab]  = useState<Tab>("trace");

  useEffect(() => {
    if (!id) return;
    async function loadAll() {
      const [r, s, l, e, f] = await Promise.allSettled([
        api.runs.get(id),
        api.runs.steps(id),
        api.runs.llmCalls(id),
        api.runs.evaluations(id),
        api.runs.feedback(id),
      ]);
      if (r.status === "rejected") { setLoadErr(r.reason.message); return; }
      const loadedRun = r.value;
      setRun(loadedRun);
      if (s.status === "fulfilled") setSteps(s.value);
      if (l.status === "fulfilled") setLlmCalls(l.value);
      if (e.status === "fulfilled") setEvals(e.value);
      if (f.status === "fulfilled") setFeedback(f.value);

      // Fetch replay list (shows on original runs; empty on replays)
      const replayData = await api.runs.replays(id).catch(() => null);
      if (replayData) setReplays(replayData.items);

      // If this is a replay, load the original run + its eval for ComparePanel
      if (loadedRun.is_replay && loadedRun.original_run_id) {
        const [origR, origE] = await Promise.allSettled([
          api.runs.get(loadedRun.original_run_id),
          api.runs.evaluations(loadedRun.original_run_id),
        ]);
        if (origR.status === "fulfilled") setOriginalRun(origR.value);
        if (origE.status === "fulfilled") setOriginalEval(origE.value[0] ?? null);
      }
    }
    loadAll();
  }, [id]);

  const handleReplay = async () => {
    setReplaying(true);
    try {
      const newRun = await api.runs.replay(id);
      router.push(`/runs/${newRun.id}`);
    } catch { setReplaying(false); }
  };

  const handleFeedback = async () => {
    if (!rating) return;
    setSubmitting(true);
    try {
      await api.runs.submitFeedback(id, { rating, comment: comment || undefined });
      const fresh = await api.runs.feedback(id);
      setFeedback(fresh);
      setRating(0); setComment(""); setFbSuccess(true);
      setTimeout(() => setFbSuccess(false), 3000);
    } catch {} finally { setSubmitting(false); }
  };

  if (loadErr) return (
    <div className="p-10 text-center">
      <p className="text-red-400 text-sm">{loadErr}</p>
      <Link href="/runs" className="text-brand-400 text-xs mt-3 inline-block">← Back to runs</Link>
    </div>
  );

  if (!run) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
        <p className="text-slate-500 text-sm">Loading run…</p>
      </div>
    </div>
  );

  const eval0       = evals[0];
  const totalCost   = llmCalls.reduce((s, c) => s + (c.estimated_cost ?? 0), 0);
  const totalTokens = llmCalls.reduce((s, c) => s + (c.total_tokens  ?? 0), 0);

  const TABS: { key: Tab; label: string }[] = [
    { key: "trace", label: "Trace Timeline"          },
    { key: "llm",   label: `LLM Calls (${llmCalls.length})` },
    { key: "eval",  label: "Evaluation"              },
    { key: "io",    label: "Input / Output"          },
  ];

  return (
    <div className="space-y-6">
      {/* Breadcrumb */}
      <div className="flex items-center gap-2 text-sm text-slate-500">
        <Link href="/runs" className="hover:text-slate-300 transition-colors">Runs</Link>
        <span>/</span>
        <span className="text-slate-400 font-mono text-xs">{id.slice(0, 8)}…</span>
      </div>

      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div className="space-y-1">
          <div className="flex items-center gap-3 flex-wrap">
            <h1 className="text-xl font-semibold text-white">{run.workflow_name}</h1>
            <StatusBadge status={run.status} />
            {run.is_replay && (
              <span className="text-xs text-violet-400 bg-violet-500/10 px-2 py-0.5 rounded border border-violet-500/20">REPLAY</span>
            )}
          </div>
          <p className="text-xs text-slate-500 font-mono">{id}</p>
          <p className="text-xs text-slate-500">
            {format(new Date(run.started_at), "MMM d, yyyy · HH:mm:ss")}
            {run.duration_ms != null && ` · ${run.duration_ms.toLocaleString()}ms total`}
          </p>
          {run.original_run_id && (
            <p className="text-xs text-violet-400">
              Replay of{" "}
              <Link href={`/runs/${run.original_run_id}`} className="underline hover:text-violet-300">
                {run.original_run_id.slice(0, 8)}…
              </Link>
            </p>
          )}
        </div>
        <button
          onClick={handleReplay} disabled={replaying}
          className="px-4 py-2 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white text-sm rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          {replaying ? (
            <><div className="w-3.5 h-3.5 border-2 border-white border-t-transparent rounded-full animate-spin"/>Replaying…</>
          ) : "↺ Replay Run"}
        </button>
      </div>

      {/* Mini KPIs */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[
          ["Duration",     run.duration_ms != null ? `${run.duration_ms.toLocaleString()}ms` : "—"],
          ["Total Cost",   totalCost   > 0 ? `$${totalCost.toFixed(5)}`      : "—"],
          ["Total Tokens", totalTokens > 0 ? totalTokens.toLocaleString()    : "—"],
          ["LLM Calls",    llmCalls.length.toString()],
        ].map(([label, value]) => (
          <Card key={label} padding="sm">
            <p className="text-xs text-slate-500 uppercase tracking-wider">{label}</p>
            <p className="text-lg font-bold text-white mt-1">{value}</p>
          </Card>
        ))}
      </div>

      {/* Compare panel — only for replay runs once original is loaded */}
      {run.is_replay && originalRun && (
        <ComparePanel
          original={{ run: originalRun, eval: originalEval }}
          replay={{ run, eval: eval0 ?? null }}
        />
      )}

      {/* Replay history — only for original runs that have replays */}
      {!run.is_replay && replays.length > 0 && (
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-4">Replay History</h2>
          <ReplayHistory replays={replays} currentId={id} />
        </Card>
      )}

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[#252b3b] overflow-x-auto">
        {TABS.map(({ key, label }) => (
          <button key={key} onClick={() => setActiveTab(key)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors whitespace-nowrap ${
              activeTab === key
                ? "border-brand-500 text-brand-400"
                : "border-transparent text-slate-500 hover:text-slate-300"
            }`}>{label}</button>
        ))}
      </div>

      {/* Tab panels */}
      {activeTab === "trace" && (
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-5">Execution Timeline</h2>
          {steps.length === 0
            ? <p className="text-slate-500 text-sm">No steps recorded for this run.</p>
            : <TraceTimeline steps={steps} />}
        </Card>
      )}

      {activeTab === "llm" && (
        <div className="space-y-3">
          {llmCalls.length === 0
            ? <Card><p className="text-slate-500 text-sm">No LLM calls recorded.</p></Card>
            : llmCalls.map((c) => <LLMCallCard key={c.id} call={c} />)}
        </div>
      )}

      {activeTab === "eval" && (
        <Card>
          <h2 className="text-sm font-medium text-slate-300 mb-5">Evaluation Scores</h2>
          {eval0 ? (
            <div className="space-y-4 max-w-lg">
              <ScoreBar label="Relevance"          value={eval0.relevance_score}    />
              <ScoreBar label="Groundedness"       value={eval0.groundedness_score} />
              <ScoreBar label="Hallucination Risk" value={eval0.hallucination_risk} invert />
              <ScoreBar label="Quality Score"      value={eval0.quality_score}      />
              {eval0.failure_reason && (
                <p className="text-xs text-amber-400 bg-amber-500/10 rounded-lg p-3 mt-2 border border-amber-500/20">
                  {eval0.failure_reason}
                </p>
              )}
            </div>
          ) : (
            <p className="text-slate-500 text-sm">No evaluation data — call <code className="text-slate-400">evaluate_run()</code> in your workflow.</p>
          )}
        </Card>
      )}

      {activeTab === "io" && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <h2 className="text-sm font-medium text-slate-300 mb-3">Input</h2>
            <pre className="text-xs text-slate-300 bg-[#0d0f1a] rounded-lg p-4 overflow-auto max-h-80 font-mono leading-relaxed">
              {JSON.stringify(run.input_payload, null, 2)}
            </pre>
          </Card>
          <Card>
            <h2 className="text-sm font-medium text-slate-300 mb-3">Output</h2>
            {run.output_payload ? (
              <pre className="text-xs text-slate-300 bg-[#0d0f1a] rounded-lg p-4 overflow-auto max-h-80 font-mono leading-relaxed">
                {JSON.stringify(run.output_payload, null, 2)}
              </pre>
            ) : run.error_message ? (
              <div className="bg-red-500/5 border border-red-500/20 rounded-lg p-4">
                <p className="text-xs text-red-400 font-mono whitespace-pre-wrap">{run.error_message}</p>
              </div>
            ) : (
              <p className="text-slate-500 text-sm">No output recorded.</p>
            )}
          </Card>
        </div>
      )}

      {/* Feedback */}
      <Card>
        <h2 className="text-sm font-medium text-slate-300 mb-4">Human Feedback</h2>

        {feedback.length > 0 && (
          <div className="space-y-2 mb-5">
            {feedback.map((fb) => (
              <div key={fb.id} className="flex items-start gap-3 bg-[#13151f] rounded-lg p-3">
                <div className="flex gap-0.5 shrink-0">
                  {[1,2,3,4,5].map((s) => (
                    <span key={s} className={s <= fb.rating ? "text-amber-400" : "text-slate-700"}>★</span>
                  ))}
                </div>
                {fb.comment && <p className="text-sm text-slate-400">{fb.comment}</p>}
                <span className="text-xs text-slate-600 ml-auto shrink-0">
                  {format(new Date(fb.created_at), "MMM d")}
                </span>
              </div>
            ))}
          </div>
        )}

        <div className="space-y-3 border-t border-[#252b3b] pt-4">
          <p className="text-xs text-slate-500">Rate this run</p>
          <div className="flex gap-1">
            {[1,2,3,4,5].map((s) => (
              <button key={s} onClick={() => setRating(s)}
                className={`text-xl transition-colors ${s <= rating ? "text-amber-400" : "text-slate-700 hover:text-amber-600"}`}>
                ★
              </button>
            ))}
          </div>
          <textarea value={comment} onChange={(e) => setComment(e.target.value)}
            placeholder="Optional comment…" rows={2}
            className="w-full bg-[#13151f] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500 resize-none" />
          <div className="flex items-center gap-3">
            <button onClick={handleFeedback} disabled={!rating || submitting}
              className="px-4 py-2 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 text-white text-sm rounded-lg font-medium transition-colors">
              {submitting ? "Submitting…" : "Submit Feedback"}
            </button>
            {fbSuccess && <span className="text-xs text-emerald-400">Feedback saved!</span>}
          </div>
        </div>
      </Card>
    </div>
  );
}
