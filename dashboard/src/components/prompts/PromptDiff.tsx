"use client";
import { useMemo, useState } from "react";
import type { PromptVersion } from "@/types";

// ── diff algorithm (line-level LCS) ───────────────────────────────────────────

type Op = { type: "same" | "removed" | "added"; text: string };

function computeDiff(a: string[], b: string[]): Op[] {
  const m = a.length, n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = 1; i <= m; i++)
    for (let j = 1; j <= n; j++)
      dp[i][j] = a[i - 1] === b[j - 1]
        ? dp[i - 1][j - 1] + 1
        : Math.max(dp[i - 1][j], dp[i][j - 1]);

  const ops: Op[] = [];
  let i = m, j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && a[i - 1] === b[j - 1]) {
      ops.unshift({ type: "same", text: a[i - 1] });
      i--; j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      ops.unshift({ type: "added", text: b[j - 1] });
      j--;
    } else {
      ops.unshift({ type: "removed", text: a[i - 1] });
      i--;
    }
  }
  return ops;
}

type SplitRow = { left: Op | null; right: Op | null };

function toSplitRows(ops: Op[]): SplitRow[] {
  const rows: SplitRow[] = [];
  let qi = 0;
  while (qi < ops.length) {
    if (ops[qi].type === "same") {
      rows.push({ left: ops[qi], right: ops[qi] });
      qi++;
    } else {
      const removed: Op[] = [];
      const added: Op[] = [];
      while (qi < ops.length && ops[qi].type !== "same") {
        if (ops[qi].type === "removed") removed.push(ops[qi]);
        else added.push(ops[qi]);
        qi++;
      }
      const len = Math.max(removed.length, added.length);
      for (let k = 0; k < len; k++) {
        rows.push({
          left:  k < removed.length ? removed[k] : null,
          right: k < added.length   ? added[k]   : null,
        });
      }
    }
  }
  return rows;
}

// ── sub-components ─────────────────────────────────────────────────────────────

const LINE_BASE = "font-mono text-xs px-3 py-0.5 whitespace-pre-wrap break-all leading-5 min-h-[1.5rem]";

function SplitCell({ op, side }: { op: Op | null; side: "left" | "right" }) {
  if (!op) {
    const bg = side === "left" ? "bg-red-950/20" : "bg-emerald-950/20";
    return <td className={`${LINE_BASE} ${bg} w-1/2 text-transparent select-none`}>&nbsp;</td>;
  }
  const bg =
    op.type === "removed" ? "bg-red-950/40 text-red-300"
    : op.type === "added"   ? "bg-emerald-950/40 text-emerald-300"
    : "text-slate-400";
  return <td className={`${LINE_BASE} ${bg} w-1/2`}>{op.text || " "}</td>;
}

function GutterCell({ op, lineNum }: { op: Op | null; lineNum: number | null }) {
  const bg =
    !op || op.type === "same" ? "text-slate-700"
    : op.type === "removed"   ? "bg-red-950/40 text-red-700"
    : "bg-emerald-950/40 text-emerald-700";
  const marker =
    !op            ? " "
    : op.type === "removed" ? "-"
    : op.type === "added"   ? "+"
    : " ";
  return (
    <td className={`font-mono text-[10px] px-1.5 select-none w-8 text-right ${bg}`}>
      {lineNum != null ? lineNum : ""}
      <span className="ml-1">{marker}</span>
    </td>
  );
}

// ── main component ─────────────────────────────────────────────────────────────

interface Props {
  left:  PromptVersion;
  right: PromptVersion;
}

export default function PromptDiff({ left, right }: Props) {
  const [mode, setMode] = useState<"split" | "unified">("split");

  const leftLines  = useMemo(() => left.prompt_text.split("\n"),  [left.prompt_text]);
  const rightLines = useMemo(() => right.prompt_text.split("\n"), [right.prompt_text]);
  const ops        = useMemo(() => computeDiff(leftLines, rightLines), [leftLines, rightLines]);
  const splitRows  = useMemo(() => toSplitRows(ops), [ops]);

  const added   = ops.filter((o) => o.type === "added").length;
  const removed = ops.filter((o) => o.type === "removed").length;
  const same    = ops.filter((o) => o.type === "same").length;
  const changed = added === 0 && removed === 0;

  // Line numbers per side
  let leftNum = 0, rightNum = 0;

  return (
    <div className="space-y-3">
      {/* Toolbar */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div className="flex items-center gap-3 text-xs">
          <span className="text-emerald-400 font-medium">+{added}</span>
          <span className="text-red-400 font-medium">−{removed}</span>
          <span className="text-slate-600">{same} unchanged</span>
          {changed && <span className="text-slate-500">No differences</span>}
        </div>
        <div className="flex items-center gap-1 bg-[#0d0f1a] border border-[#252b3b] rounded-lg p-0.5">
          {(["split", "unified"] as const).map((m) => (
            <button
              key={m}
              onClick={() => setMode(m)}
              className={`px-3 py-1 text-xs rounded-md font-medium transition-colors capitalize ${
                mode === m
                  ? "bg-brand-500 text-white"
                  : "text-slate-400 hover:text-slate-200"
              }`}
            >
              {m}
            </button>
          ))}
        </div>
      </div>

      {/* Column headers */}
      {mode === "split" && (
        <div className="grid grid-cols-2 gap-px">
          <div className="bg-[#13151f] border border-[#252b3b] rounded-tl-lg px-4 py-2 text-xs text-slate-400">
            <span className="font-mono bg-[#252b3b] px-1.5 py-0.5 rounded text-slate-300 mr-2">{left.version}</span>
            {left.is_active && <span className="text-emerald-500 text-[10px] font-medium">Active</span>}
          </div>
          <div className="bg-[#13151f] border border-[#252b3b] rounded-tr-lg px-4 py-2 text-xs text-slate-400">
            <span className="font-mono bg-[#252b3b] px-1.5 py-0.5 rounded text-slate-300 mr-2">{right.version}</span>
            {right.is_active && <span className="text-emerald-500 text-[10px] font-medium">Active</span>}
          </div>
        </div>
      )}

      {/* Diff body */}
      <div className="rounded-lg border border-[#252b3b] overflow-auto max-h-[520px] bg-[#0a0c14]">
        {mode === "split" ? (
          <table className="w-full border-collapse text-left">
            <tbody>
              {splitRows.map((row, idx) => {
                const ln = row.left  ? (row.left.type  !== "added"   ? ++leftNum  : leftNum)  : leftNum;
                const rn = row.right ? (row.right.type !== "removed" ? ++rightNum : rightNum) : rightNum;
                return (
                  <tr key={idx} className="border-b border-[#1a1f2e] last:border-0">
                    <GutterCell op={row.left}  lineNum={row.left  && row.left.type  !== "added"   ? ln : null} />
                    <SplitCell  op={row.left}  side="left" />
                    <td className="w-px bg-[#1e2235]" />
                    <GutterCell op={row.right} lineNum={row.right && row.right.type !== "removed" ? rn : null} />
                    <SplitCell  op={row.right} side="right" />
                  </tr>
                );
              })}
            </tbody>
          </table>
        ) : (
          <table className="w-full border-collapse text-left">
            <tbody>
              {ops.map((op, idx) => {
                const ln =
                  op.type === "same"    ? `${++leftNum}  ${++rightNum}`
                  : op.type === "removed" ? `${++leftNum}  `
                  : `   ${++rightNum}`;
                const bg =
                  op.type === "removed" ? "bg-red-950/40"
                  : op.type === "added"   ? "bg-emerald-950/40"
                  : "";
                const text =
                  op.type === "removed" ? "text-red-300"
                  : op.type === "added"   ? "text-emerald-300"
                  : "text-slate-400";
                const marker =
                  op.type === "removed" ? "-"
                  : op.type === "added"   ? "+"
                  : " ";
                return (
                  <tr key={idx} className={`border-b border-[#1a1f2e] last:border-0 ${bg}`}>
                    <td className={`font-mono text-[10px] px-2 select-none text-slate-700 w-16 whitespace-nowrap`}>{ln}</td>
                    <td className={`font-mono text-[10px] px-1 select-none w-4 ${text}`}>{marker}</td>
                    <td className={`${LINE_BASE} ${text} w-full`}>{op.text || " "}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
