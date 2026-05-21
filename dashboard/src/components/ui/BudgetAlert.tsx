"use client";
import { useState } from "react";

interface ExceededDay {
  date: string;
  value: number;
}

interface Props {
  exceededDays: ExceededDay[];
  threshold: number;
  label?: string;
}

export default function BudgetAlert({ exceededDays, threshold, label = "daily" }: Props) {
  const [dismissed, setDismissed] = useState(false);

  if (exceededDays.length === 0 || dismissed) return null;

  const worst = exceededDays.reduce((a, b) => (a.value > b.value ? a : b));

  return (
    <div className="flex items-start gap-3 px-4 py-3 bg-amber-500/10 border border-amber-500/25 rounded-xl text-sm">
      <svg className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" fill="none" viewBox="0 0 16 16">
        <path d="M8 2L1.5 13.5h13L8 2Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
        <line x1="8" y1="7" x2="8" y2="10" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
        <circle cx="8" cy="12" r="0.6" fill="currentColor"/>
      </svg>
      <div className="flex-1 min-w-0">
        <p className="text-amber-300 font-medium leading-none">
          {label.charAt(0).toUpperCase() + label.slice(1)} cost budget exceeded
        </p>
        <p className="text-amber-500/80 text-xs mt-1.5 leading-relaxed">
          {exceededDays.length} {exceededDays.length === 1 ? "day" : "days"} over the
          ${threshold.toFixed(4)} limit. Peak: <span className="text-amber-400">${worst.value.toFixed(4)}</span> on {worst.date}.
        </p>
      </div>
      <button
        onClick={() => setDismissed(true)}
        className="text-amber-600 hover:text-amber-400 transition-colors text-xs shrink-0 leading-none mt-0.5"
        aria-label="Dismiss alert"
      >
        ✕
      </button>
    </div>
  );
}
