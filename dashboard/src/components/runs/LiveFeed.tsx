"use client";

import { useEffect, useRef, useState } from "react";

interface LiveEvent {
  span_id?: string;
  run_id?: string;
  name?: string;
  kind?: string;
  event_type?: string;
  status?: string;
  timestamp_ns?: number;
  duration_ns?: number;
  attributes?: Record<string, unknown>;
  error_message?: string;
  _received_at: number;
}

const KIND_COLOR: Record<string, string> = {
  workflow:  "#4f6ef7",
  step:      "#94a3b8",
  llm:       "#8b5cf6",
  tool:      "#10b981",
  retriever: "#f59e0b",
};

const STATUS_COLOR: Record<string, string> = {
  ok:      "#10b981",
  error:   "#ef4444",
  running: "#4f6ef7",
  unset:   "#475569",
};

function fmt_ns(ns?: number): string {
  if (ns == null) return "";
  if (ns < 1_000_000) return `${(ns / 1000).toFixed(0)}µs`;
  if (ns < 1_000_000_000) return `${(ns / 1_000_000).toFixed(1)}ms`;
  return `${(ns / 1_000_000_000).toFixed(2)}s`;
}

interface LiveFeedProps {
  runId: string;
  isRunning: boolean;
}

export default function LiveFeed({ runId, isRunning }: LiveFeedProps) {
  const [events, setEvents]       = useState<LiveEvent[]>([]);
  const [connected, setConnected] = useState(false);
  const [error, setError]         = useState<string | null>(null);
  const wsRef   = useRef<WebSocket | null>(null);
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const BASE = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000").replace(/^http/, "ws");
    const url  = `${BASE}/ws/live?run_id=${runId}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => { setConnected(true); setError(null); };
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setError("WebSocket connection failed — is the backend running?");

    ws.onmessage = (msg) => {
      try {
        const evt: LiveEvent = { ...JSON.parse(msg.data), _received_at: Date.now() };
        setEvents((prev) => [...prev.slice(-199), evt]);
      } catch { /* ignore malformed frames */ }
    };

    return () => {
      ws.close();
      wsRef.current = null;
    };
  }, [runId]);

  // Auto-scroll to bottom on new events
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [events]);

  return (
    <div className="space-y-3">
      {/* Status bar */}
      <div className="flex items-center gap-3 px-1">
        <span className="flex items-center gap-1.5 text-xs">
          <span
            className="w-2 h-2 rounded-full"
            style={{ background: connected ? "#10b981" : "#475569" }}
          />
          <span className="text-slate-400">
            {connected ? "Connected" : "Disconnected"}
          </span>
        </span>
        <span className="text-slate-600 text-xs">{events.length} events</span>
        {events.length > 0 && (
          <button
            onClick={() => setEvents([])}
            className="text-xs text-slate-600 hover:text-slate-400 ml-auto transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {error && (
        <p className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">
          {error}
        </p>
      )}

      {/* Event stream */}
      <div className="bg-[#0d0f1a] rounded-xl border border-[#1e2235] overflow-hidden">
        <div className="h-[480px] overflow-y-auto font-mono text-xs p-3 space-y-1.5">
          {events.length === 0 ? (
            <div className="flex items-center justify-center h-full">
              <div className="text-center">
                <div
                  className="w-2 h-2 rounded-full mx-auto mb-3 animate-pulse"
                  style={{ background: connected ? "#4f6ef7" : "#475569" }}
                />
                <p className="text-slate-600 text-xs">
                  {connected
                    ? isRunning
                      ? "Waiting for events…"
                      : "Listening — run a workflow to see live events"
                    : "Connecting…"}
                </p>
              </div>
            </div>
          ) : (
            events.map((evt, i) => (
              <EventRow key={i} evt={evt} />
            ))
          )}
          <div ref={bottomRef} />
        </div>
      </div>
    </div>
  );
}

function EventRow({ evt }: { evt: LiveEvent }) {
  const kindColor   = KIND_COLOR[evt.kind ?? ""] ?? "#64748b";
  const statusColor = STATUS_COLOR[evt.status ?? "unset"] ?? "#475569";
  const dur         = fmt_ns(evt.duration_ns);

  return (
    <div className="flex items-start gap-2 py-0.5 group hover:bg-white/[0.02] rounded px-1 -mx-1">
      {/* kind badge */}
      <span
        className="shrink-0 text-[9px] font-bold px-1.5 py-0.5 rounded mt-0.5"
        style={{ color: kindColor, background: `${kindColor}18`, border: `1px solid ${kindColor}30` }}
      >
        {(evt.kind ?? "span").toUpperCase()}
      </span>

      {/* name */}
      <span className="text-slate-300 truncate flex-1">{evt.name ?? evt.event_type ?? "—"}</span>

      {/* duration */}
      {dur && <span className="text-slate-600 shrink-0">{dur}</span>}

      {/* status dot */}
      <span
        className="w-1.5 h-1.5 rounded-full shrink-0 mt-1"
        style={{ background: statusColor }}
      />

      {/* error */}
      {evt.error_message && (
        <span className="text-red-400 truncate max-w-[180px] shrink-0 text-[10px]">
          {evt.error_message}
        </span>
      )}
    </div>
  );
}
