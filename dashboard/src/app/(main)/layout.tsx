import Sidebar from "@/components/layout/Sidebar";
import BackendBanner from "@/components/layout/BackendBanner";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen bg-[#0f1117]">
      <Sidebar />
      <main className="ml-56 flex-1 min-h-screen">
        <BackendBanner />
        <div className="max-w-7xl mx-auto px-6 py-8">
          {children}
        </div>
      </main>
    </div>
  );
}
