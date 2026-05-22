"use client";
import { useEffect, useRef, useState } from "react";

export type WSStatus = "connecting" | "open" | "closed" | "error";

interface Options {
  url: string;
  onMessage: (data: unknown) => void;
  reconnectDelayMs?: number;
}

export function useWebSocket({ url, onMessage, reconnectDelayMs = 3000 }: Options): WSStatus {
  const [status, setStatus] = useState<WSStatus>("connecting");
  const wsRef        = useRef<WebSocket | null>(null);
  const onMsgRef     = useRef(onMessage);
  const unmountedRef = useRef(false);
  const timerRef     = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => { onMsgRef.current = onMessage; }, [onMessage]);

  useEffect(() => {
    unmountedRef.current = false;

    function connect() {
      if (unmountedRef.current) return;
      setStatus("connecting");
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen  = () => { if (!unmountedRef.current) setStatus("open"); };
      ws.onerror = () => { if (!unmountedRef.current) setStatus("error"); };
      ws.onmessage = (e) => {
        try { onMsgRef.current(JSON.parse(e.data as string)); } catch {}
      };
      ws.onclose = () => {
        if (unmountedRef.current) return;
        setStatus("closed");
        timerRef.current = setTimeout(connect, reconnectDelayMs);
      };
    }

    connect();

    return () => {
      unmountedRef.current = true;
      if (timerRef.current) clearTimeout(timerRef.current);
      wsRef.current?.close();
    };
  }, [url, reconnectDelayMs]);

  return status;
}
