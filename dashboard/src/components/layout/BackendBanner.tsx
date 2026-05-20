"use client";
import { useBackendStatus } from "@/lib/useFetch";

export default function BackendBanner() {
  const online = useBackendStatus();

  if (online === true || online === null) return null;

  return (
    <div className="mx-6 mt-4 px-4 py-2.5 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 text-xs flex items-center gap-2">
      <svg width="14" height="14" viewBox="0 0 16 16" fill="none">
        <path d="M8 2L14 13H2L8 2Z" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round"/>
        <path d="M8 6v4M8 11.5v.5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
      </svg>
      Backend offline — start with{" "}
      <code className="font-mono bg-amber-500/10 px-1 rounded">
        docker-compose up -d && uvicorn app.main:app
      </code>
      . Dashboard shows demo data.
    </div>
  );
}
