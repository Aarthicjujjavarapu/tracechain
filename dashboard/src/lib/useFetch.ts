"use client";
import { useEffect, useState, useCallback, useRef } from "react";

interface State<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

export function useFetch<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [state, setState] = useState<State<T>>({ data: null, loading: true, error: null });
  const mounted = useRef(true);

  const load = useCallback(async () => {
    setState((s) => ({ ...s, loading: true, error: null }));
    try {
      const data = await fetcher();
      if (mounted.current) setState({ data, loading: false, error: null });
    } catch (e: unknown) {
      if (mounted.current)
        setState({ data: null, loading: false, error: e instanceof Error ? e.message : "Failed to load" });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    mounted.current = true;
    load();
    return () => { mounted.current = false; };
  }, [load]);

  return { ...state, refetch: load };
}

export function useBackendStatus() {
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    const check = () =>
      fetch((process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000") + "/health")
        .then(() => setOnline(true))
        .catch(() => setOnline(false));
    check();
    const id = setInterval(check, 15_000);
    return () => clearInterval(id);
  }, []);

  return online;
}
