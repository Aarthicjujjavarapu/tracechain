"use client";

import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  MarkerType,
  type NodeTypes,
  type Node,
  type Edge,
  BackgroundVariant,
} from "reactflow";
import "reactflow/dist/style.css";
import type { GraphNodeData, NodeKind } from "@/types";

// ── node colours per kind ─────────────────────────────────────────────────────

const KIND_STYLE: Record<NodeKind, { border: string; bg: string; label: string }> = {
  workflow:  { border: "#4f6ef7", bg: "#1a1f3a", label: "WORKFLOW"  },
  step:      { border: "#475569", bg: "#1a1f2e", label: "STEP"      },
  llm:       { border: "#8b5cf6", bg: "#1e1a35", label: "LLM"       },
  tool:      { border: "#10b981", bg: "#1a2e25", label: "TOOL"      },
  retriever: { border: "#f59e0b", bg: "#2a2215", label: "RETRIEVER" },
  reranker:  { border: "#f59e0b", bg: "#2a2215", label: "RERANKER"  },
  memory:    { border: "#06b6d4", bg: "#1a2a2e", label: "MEMORY"    },
  validator: { border: "#ec4899", bg: "#2e1a28", label: "VALIDATOR" },
  agent:     { border: "#4f6ef7", bg: "#1a1f3a", label: "AGENT"     },
  embedding: { border: "#64748b", bg: "#1a1f2e", label: "EMBEDDING" },
};

const STATUS_RING: Record<string, string> = {
  ok:       "#10b981",
  error:    "#ef4444",
  retrying: "#f59e0b",
  running:  "#4f6ef7",
};

// ── custom node ───────────────────────────────────────────────────────────────

function TraceNode({ data }: { data: GraphNodeData }) {
  const kind   = (data.kind ?? "step") as NodeKind;
  const style  = KIND_STYLE[kind] ?? KIND_STYLE.step;
  const ring   = STATUS_RING[data.status] ?? STATUS_RING.ok;
  const isError = data.status === "error";

  return (
    <div
      style={{
        border:      `1.5px solid ${isError ? "#ef4444" : style.border}`,
        background:  isError ? "#2e1a1a" : style.bg,
        boxShadow:   `0 0 0 1px ${ring}22`,
        borderRadius: 10,
        minWidth: 180,
        maxWidth: 240,
        fontFamily: "inherit",
      }}
      className="px-3 py-2.5 text-xs"
    >
      {/* header row */}
      <div className="flex items-center gap-1.5 mb-1.5">
        <span
          className="w-1.5 h-1.5 rounded-full shrink-0"
          style={{ background: ring }}
        />
        <span style={{ color: style.border, fontSize: 9, fontWeight: 600, letterSpacing: "0.08em" }}>
          {style.label}
        </span>
        {data.retry_count > 0 && (
          <span className="ml-auto text-[9px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/20">
            ↺{data.retry_count}
          </span>
        )}
      </div>

      {/* name */}
      <div className="text-slate-100 font-medium leading-tight truncate mb-2">
        {data.label}
      </div>

      {/* metrics row */}
      <div className="flex gap-3 flex-wrap">
        {data.duration_ms != null && (
          <Metric label="dur" value={`${Math.round(data.duration_ms)}ms`} />
        )}
        {data.input_tokens != null && (
          <Metric label="in" value={data.input_tokens.toLocaleString()} />
        )}
        {data.output_tokens != null && (
          <Metric label="out" value={data.output_tokens.toLocaleString()} />
        )}
        {data.cost_usd != null && data.cost_usd > 0 && (
          <Metric label="$" value={`$${data.cost_usd.toFixed(4)}`} color="#22c55e" />
        )}
      </div>

      {isError && (
        <div className="mt-2 text-[10px] text-red-400 bg-red-500/10 rounded px-2 py-1 border border-red-500/20 truncate">
          {(data.attributes["error.message"] as string) ?? "Error"}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, color }: { label: string; value: string; color?: string }) {
  return (
    <span className="text-[10px] text-slate-500">
      <span className="text-slate-600">{label}: </span>
      <span style={{ color: color ?? "#94a3b8" }}>{value}</span>
    </span>
  );
}

// ── edge styles ───────────────────────────────────────────────────────────────

const EDGE_STYLES: Record<string, React.CSSProperties> = {
  default:    { stroke: "#334155", strokeWidth: 1.5 },
  tool_call:  { stroke: "#10b981", strokeWidth: 1.5 },
  retrieval:  { stroke: "#f59e0b", strokeWidth: 1.5 },
  error:      { stroke: "#ef4444", strokeWidth: 1.5, strokeDasharray: "4 2" },
  retry:      { stroke: "#f59e0b", strokeWidth: 1.5, strokeDasharray: "4 2" },
};

// ── node type registry ────────────────────────────────────────────────────────

const nodeTypes: NodeTypes = Object.fromEntries(
  (["workflow","step","llm","tool","retriever","reranker","memory","validator","agent","embedding"] as NodeKind[])
    .map((k) => [k, TraceNode])
);

// ── main component ────────────────────────────────────────────────────────────

interface AgentGraphProps {
  nodes: Node[];
  edges: Edge[];
}

export default function AgentGraph({ nodes, edges }: AgentGraphProps) {
  const styledEdges = edges.map((e) => ({
    ...e,
    style:     EDGE_STYLES[e.type ?? "default"] ?? EDGE_STYLES.default,
    markerEnd: { type: MarkerType.ArrowClosed, color: "#334155", width: 12, height: 12 },
    animated:  false,
  }));

  return (
    <div style={{ height: Math.max(480, nodes.length * 60 + 120), width: "100%" }}>
      <ReactFlow
        nodes={nodes}
        edges={styledEdges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        proOptions={{ hideAttribution: true }}
        style={{ background: "#0d0f1a", borderRadius: 12 }}
        nodesDraggable={true}
        nodesConnectable={false}
        elementsSelectable={true}
        panOnDrag={true}
        zoomOnScroll={true}
      >
        <Background
          variant={BackgroundVariant.Dots}
          color="#1e2235"
          gap={20}
          size={1}
        />
        <Controls
          style={{ background: "#1a1f2e", border: "1px solid #252b3b" }}
          showInteractive={false}
        />
        <MiniMap
          style={{ background: "#13151f", border: "1px solid #252b3b" }}
          nodeColor={(n) => {
            const kind = (n.data?.kind ?? "step") as NodeKind;
            return KIND_STYLE[kind]?.border ?? "#475569";
          }}
          maskColor="#0d0f1a88"
        />
      </ReactFlow>
    </div>
  );
}
