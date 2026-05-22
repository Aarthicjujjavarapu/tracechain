"use client";
import { useState } from "react";

export default function CodeBlock({ code, language = "python" }: { code: string; language?: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="relative group rounded-xl overflow-hidden border border-[#252b3b]">
      <div className="flex items-center justify-between px-4 py-2 bg-[#13151f] border-b border-[#252b3b]">
        <span className="text-xs text-slate-500 font-mono">{language}</span>
        <button
          onClick={copy}
          className="text-xs text-slate-500 hover:text-slate-300 transition-colors px-2 py-1 rounded"
        >
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      <pre className="bg-[#0d0f1a] p-4 overflow-x-auto text-sm leading-relaxed">
        <code className="text-slate-300 font-mono">{code}</code>
      </pre>
    </div>
  );
}
