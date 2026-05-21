"use client";
import { useEffect, useState } from "react";

const KEY_PER_RUN = "tc_budget_per_run";
const KEY_PER_DAY = "tc_budget_per_day";

function readNum(key: string): number | null {
  try {
    const v = localStorage.getItem(key);
    if (!v) return null;
    const n = parseFloat(v);
    return isFinite(n) && n > 0 ? n : null;
  } catch {
    return null;
  }
}

export function useBudget() {
  const [perRun, setPerRun] = useState<number | null>(null);
  const [perDay, setPerDay] = useState<number | null>(null);

  useEffect(() => {
    setPerRun(readNum(KEY_PER_RUN));
    setPerDay(readNum(KEY_PER_DAY));
  }, []);

  function savePerRun(v: number | null) {
    setPerRun(v);
    if (v == null || v <= 0) localStorage.removeItem(KEY_PER_RUN);
    else localStorage.setItem(KEY_PER_RUN, String(v));
  }

  function savePerDay(v: number | null) {
    setPerDay(v);
    if (v == null || v <= 0) localStorage.removeItem(KEY_PER_DAY);
    else localStorage.setItem(KEY_PER_DAY, String(v));
  }

  return { perRun, perDay, savePerRun, savePerDay };
}
