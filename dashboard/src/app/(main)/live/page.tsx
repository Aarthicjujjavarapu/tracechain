"use client";
import { useState, useCallback, useRef, useEffect } from "react";
import Link from "next/link";
import { format } from "date-fns";
import Card from "@/components/ui/Card";
import { useWebSocket, type WSStatus } from "@/hooks/useWebSocket";

const API_BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const WS_URL   = API_BASE.replace(/^http/, "ws") + "/ws/live";
const MAX_EVENTS = 200;

interface LiveEvent {
  _key:          number;
  received_at:   Date;
  event_type:    string;
  run_id?:       string;
  workflow_name?: string;
  status?:       string;
  name?:         string;
  kind?:         string;
  error_message?: string;
  duration_ms?:  number;
  reliability_score?: number;
}

function eventColors(type: string) {
  if (type === "run.failed")    return "bg-red-500/15 text-red-400 border-red-500/20";
  if (type === "run.completed") return "bg-emerald-500/15 text-emerald-400 border-emerald-500/20";
  if (type === "run.created")   return "bg-blue-500/15 text-blue-400 border-blue-500/20";
  if (type === "run.replayed")  return "bg-purple-500/15 text-purple-400 border-purple-500/20";
  if (type.startsWith("span.")) return "bg-slate-500/10 text-slate-500 border-slate-500/10";
  return "bg-brand-500/15 text-brand-400 border-brand-500/20";
}

function statusColor(s: string | undefined) {
  if (!s) return "text-slate-600";
  if (s === "success" || s === "ok" || s === "running") return s === "running" ? "text-amber-400" : "text-emerald-400";
  if (s === "failed" || s === "error") return "text-red-400";
  return "text-slate-400";
}

function ConnectionBadge({ status }: { status: WSStatus }) {
  const dot = status === "open"
    ? "bg-emerald-400 animate-pulse"
    : status === "connecting"
    ? "bg-amber-400 animate-pulse"
    : "bg-red-400";
  const label = status === "open" ? "Connected" : status === "connecting" ? "Connecting…" : "Disconnected — retrying";
  return (
    <div className="flex items-center gap-2">
      <span className={`w-2 h-2 rounded-full flex-shrink-0 ${dot}`} />
      <span className="text-xs text-slate-400">{label}</span>
    </div>
  );
}

let _counter = 0;

export default function LivePage() {
  const [events,  setEvents]  = useState<LiveEvent[]>([]);
  const [filter,  setFilter]  = useState("");
  const [paused,  setPaused]  = useState(false);
  const pausedRef = useRef(paused);
  useEffect(() => { pausedRef.current = paused; }, [paused]);

  const handleMessage = useCallback((raw: unknown) => {
    if (pausedRef.current) return;
    const d = raw as Record<string, unknown>;
    const ev: LiveEvent = {
      _key:              ++_counter,
      received_at:       new Date(),
      event_type:        String(d.event_type ?? "unknown"),
      run_id:            d.run_id         ? String(d.run_id) : undefined,
      workflow_name:     d.workflow_name  ? String(d.workflow_name) : undefined,
      status:            d.status         ? String(d.status) : undefined,
      name:              d.name           ? String(d.name) : undefined,
      kind:              d.kind           ? String(d.kind) : undefined,
      error_message:     d.error_message  ? String(d.error_message) : undefined,
      duration_ms:       typeof d.duration_ms === "number" ? d.duration_ms : undefined,
      reliability_score: typeof d.reliability_score === "number" ? d.reliability_score : undefined,
    };
    setEvents((prev) => [ev, ...prev].slice(0, MAX_EVENTS));
  }, []);

  const wsStatus = useWebSocket({ url: WS_URL, onMessage: handleMessage });

  const filtered = filter.trim()
    ? events.filter(
        (e) =>
          e.workflow_name?.toLowerCase().includes(filter.toLowerCase()) ||
          e.event_type.toLowerCase().includes(filter.toLowerCase()),
      )
    : events;

  // summary counts
  const counts = events.reduce<Record<string, number>>((acc, e) => {
    acc[e.event_type] = (acc[e.event_type] ?? 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-xl font-semibold text-white">Live Activity</h1>
          <p className="text-sm text-slate-500 mt-1">Real-time event stream — newest first</p>
        </div>
        <ConnectionBadge status={wsStatus} />
      </div>

      {/* Stats pills */}
      {events.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([type, n]) => (
            <span
              key={type}
              className={`text-xs px-2.5 py-1 rounded-full border font-mono cursor-pointer select-none transition-opacity ${
                eventColors(type)
              } ${filter === type ? "opacity-100 ring-1 ring-current" : "opacity-70 hover:opacity-100"}`}
              onClick={() => setFilter((f) => f === type ? "" : type)}
              title="Click to filter"
            >
              {type} <span className="font-bold">{n}</span>
            </span>
          ))}
        </div>
      )}

      {/* Controls */}
      <div className="flex items-center gap-3 flex-wrap">
        <input
          placeholder="Filter by workflow or event type…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="bg-[#13151f] border border-[#252b3b] text-slate-300 text-sm rounded-lg px-3 py-2 focus:outline-none focus:border-brand-500 w-72"
        />
        <button
          onClick={() => setPaused((p) => !p)}
          className={`px-3 py-2 text-sm rounded-lg border transition-colors ${
            paused
              ? "bg-amber-500/20 border-amber-500/40 text-amber-400 hover:bg-amber-500/30"
              : "bg-[#13151f] border-[#252b3b] text-slate-400 hover:text-slate-300"
          }`}
        >
          {paused ? "▶ Resume" : "⏸ Pause"}
        </button>
        <button
          onClick={() => setEvents([])}
          className="px-3 py-2 text-sm rounded-lg border border-[#252b3b] bg-[#13151f] text-slate-400 hover:text-slate-300 transition-colors"
        >
          Clear
        </button>
        <span className="text-xs text-slate-600 ml-auto">
          {filtered.length}{filter ? `/${events.length}` : ""} / {MAX_EVENTS} events
        </span>
      </div>

      {/* Feed table */}
      <Card padding="none">
        {filtered.length === 0 ? (
          <div className="py-20 text-center">
            <div className="text-3xl mb-4 opacity-40">⚡</div>
            <p className="text-slate-500 text-sm">
              {events.length > 0 ? "No events match the current filter." : "Waiting for events…"}
            </p>
            <p className="text-slate-600 text-xs mt-1">
              {events.length === 0 && "Run a workflow or trigger a SDK call to see live activity here."}
            </p>
          </div>
        ) : (
          <div className="overflow-auto max-h-[600px]">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-[#0d0f1a] z-10">
                <tr className="border-b border-[#252b3b]">
                  {["Time", "Event", "Workflow", "Run ID", "Detail"].map((h) => (
                    <th key={h} className="text-left px-4 py-3 text-xs text-slate-500 font-medium uppercase tracking-wider whitespace-nowrap">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {filtered.map((e) => (
                  <tr key={e._key} className="border-b border-[#1e2235] hover:bg-white/[0.02] transition-colors">
                    {/* Time */}
                    <td className="px-4 py-3 text-xs text-slate-500 font-mono whitespace-nowrap">
                      {format(e.received_at, "HH:mm:ss.SSS")}
                    </td>

                    {/* Event type */}
                    <td className="px-4 py-3 whitespace-nowrap">
                      <span className={`text-xs font-mono px-2 py-0.5 rounded border ${eventColors(e.event_type)}`}>
                        {e.event_type}
                      </span>
                    </td>

                    {/* Workflow */}
                    <td className="px-4 py-3 text-xs">
                      {e.workflow_name ? (
                        <Link
                          href={`/runs?workflow_name=${encodeURIComponent(e.workflow_name)}`}
                          className="text-slate-300 hover:text-brand-400 transition-colors"
                        >
                          {e.workflow_name}
                        </Link>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>

                    {/* Run ID */}
                    <td className="px-4 py-3 text-xs">
                      {e.run_id ? (
                        <Link
                          href={`/runs/${e.run_id}`}
                          className="text-brand-400 hover:text-brand-300 font-mono transition-colors"
                        >
                          {e.run_id.slice(0, 8)}…
                        </Link>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>

                    {/* Detail */}
                    <td className="px-4 py-3 text-xs max-w-xs">
                      {e.error_message ? (
                        <span className="text-red-400 truncate block" title={e.error_message}>
                          {e.error_message.length > 70
                            ? e.error_message.slice(0, 70) + "…"
                            : e.error_message}
                        </span>
                      ) : e.reliability_score != null ? (
                        <span className={
                          e.reliability_score >= 80 ? "text-emerald-400"
                          : e.reliability_score >= 60 ? "text-amber-400"
                          : "text-red-400"
                        }>
                          reliability {e.reliability_score}
                          {e.duration_ms != null && ` · ${(e.duration_ms / 1000).toFixed(2)}s`}
                        </span>
                      ) : e.duration_ms != null ? (
                        <span className="text-slate-400">{(e.duration_ms / 1000).toFixed(2)}s</span>
                      ) : e.name ? (
                        <span className="text-slate-400">
                          {e.name}{e.kind ? ` (${e.kind})` : ""}
                        </span>
                      ) : e.status ? (
                        <span className={statusColor(e.status)}>{e.status}</span>
                      ) : (
                        <span className="text-slate-600">—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <p className="text-xs text-slate-700 text-center">
        Events are kept in memory only — refreshing this page clears the feed.
        Connect your SDK to <code className="text-slate-600">/v1/ingest/batch</code> to see span-level events.
      </p>
    </div>
  );
}
