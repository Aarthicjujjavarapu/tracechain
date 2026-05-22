"use client";
import { useEffect, useState } from "react";
import { format } from "date-fns";
import Card from "@/components/ui/Card";
import { SeverityBadge } from "@/components/failures/SeverityBadge";
import { api } from "@/lib/api";
import type { Incident, IncidentStatus } from "@/types";

const STATUS_STYLES: Record<IncidentStatus, string> = {
  OPEN:         "bg-red-500/10    text-red-400    border-red-500/20",
  ACKNOWLEDGED: "bg-amber-500/10  text-amber-400  border-amber-500/20",
  RESOLVED:     "bg-emerald-500/10 text-emerald-400 border-emerald-500/20",
};

function StatusChip({ status }: { status: IncidentStatus }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold border ${STATUS_STYLES[status]}`}>
      {status}
    </span>
  );
}

function IncidentRow({ inc, onAck, onResolve }: {
  inc: Incident;
  onAck:     (id: string) => void;
  onResolve: (id: string) => void;
}) {
  return (
    <tr className="border-b border-[#1a1d2e] hover:bg-[#0f1119]/60 transition-colors">
      <td className="py-3 px-4">
        <div className="flex flex-col gap-0.5">
          <span className="text-sm text-white font-medium">{inc.title}</span>
          {inc.workflow_name && (
            <span className="text-xs text-slate-500">{inc.workflow_name}</span>
          )}
        </div>
      </td>
      <td className="py-3 px-4">
        <SeverityBadge severity={inc.severity} />
      </td>
      <td className="py-3 px-4">
        <StatusChip status={inc.status} />
      </td>
      <td className="py-3 px-4 text-xs text-slate-400 tabular-nums">
        {inc.occurrence_count}
      </td>
      <td className="py-3 px-4 text-xs text-slate-500">
        {format(new Date(inc.last_seen_at), "MMM d, HH:mm")}
      </td>
      <td className="py-3 px-4">
        {inc.recommended_action && (
          <p className="text-xs text-slate-400 max-w-xs truncate" title={inc.recommended_action}>
            {inc.recommended_action}
          </p>
        )}
      </td>
      <td className="py-3 px-4">
        <div className="flex gap-2">
          {inc.status === "OPEN" && (
            <button
              onClick={() => onAck(inc.id)}
              className="text-xs text-amber-400 hover:text-amber-300 transition-colors"
            >
              Acknowledge
            </button>
          )}
          {inc.status !== "RESOLVED" && (
            <button
              onClick={() => onResolve(inc.id)}
              className="text-xs text-emerald-400 hover:text-emerald-300 transition-colors"
            >
              Resolve
            </button>
          )}
          {inc.status === "RESOLVED" && (
            <span className="text-xs text-slate-600">—</span>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function IncidentsPage() {
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [total,     setTotal]     = useState(0);
  const [loading,   setLoading]   = useState(true);
  const [statusFilter, setStatusFilter] = useState<string>("");

  async function load(status?: string) {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (status) params.status = status;
      const data = await api.incidents.list(params);
      setIncidents(data.items);
      setTotal(data.total);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(statusFilter || undefined); }, [statusFilter]);

  const openCount = incidents.filter(i => i.status === "OPEN").length;
  const ackCount  = incidents.filter(i => i.status === "ACKNOWLEDGED").length;

  async function handleAck(id: string) {
    await api.incidents.acknowledge(id);
    load(statusFilter || undefined);
  }

  async function handleResolve(id: string) {
    await api.incidents.resolve(id);
    load(statusFilter || undefined);
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-white">Incidents</h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Grouped failure patterns detected across workflow runs
          </p>
        </div>
        <div className="flex items-center gap-4 text-sm">
          {openCount > 0 && (
            <span className="text-red-400 font-medium">{openCount} open</span>
          )}
          {ackCount > 0 && (
            <span className="text-amber-400">{ackCount} acknowledged</span>
          )}
        </div>
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        {(["", "OPEN", "ACKNOWLEDGED", "RESOLVED"] as const).map((s) => (
          <button
            key={s}
            onClick={() => setStatusFilter(s)}
            className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
              statusFilter === s
                ? "bg-brand-500/20 border-brand-500/40 text-brand-400"
                : "bg-[#0f1119] border-[#252b3b] text-slate-400 hover:text-slate-300"
            }`}
          >
            {s || "All"}
          </button>
        ))}
      </div>

      <Card padding="none">
        {loading ? (
          <div className="flex items-center justify-center h-40">
            <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : incidents.length === 0 ? (
          <div className="p-12 text-center">
            <p className="text-slate-500 text-sm">No incidents found.</p>
            <p className="text-slate-600 text-xs mt-1">
              Incidents are created automatically when failure patterns are detected across runs.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead>
                <tr className="border-b border-[#252b3b] text-xs text-slate-500 uppercase tracking-wider">
                  <th className="py-3 px-4 font-medium">Incident</th>
                  <th className="py-3 px-4 font-medium">Severity</th>
                  <th className="py-3 px-4 font-medium">Status</th>
                  <th className="py-3 px-4 font-medium">Occurrences</th>
                  <th className="py-3 px-4 font-medium">Last Seen</th>
                  <th className="py-3 px-4 font-medium">Recommendation</th>
                  <th className="py-3 px-4 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {incidents.map((inc) => (
                  <IncidentRow
                    key={inc.id}
                    inc={inc}
                    onAck={handleAck}
                    onResolve={handleResolve}
                  />
                ))}
              </tbody>
            </table>
            {total > incidents.length && (
              <div className="px-4 py-3 border-t border-[#252b3b] text-xs text-slate-500">
                Showing {incidents.length} of {total} incidents
              </div>
            )}
          </div>
        )}
      </Card>
    </div>
  );
}
