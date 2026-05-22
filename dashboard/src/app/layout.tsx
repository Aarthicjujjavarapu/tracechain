import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TraceChain — LLM Observability",
  description: "Reliability-first orchestration framework for AI workflows",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#0f1117] text-slate-200 antialiased">
        {children}
      </body>
    </html>
  );
}
