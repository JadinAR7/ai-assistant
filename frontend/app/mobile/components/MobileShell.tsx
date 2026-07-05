import { type ReactNode } from "react";

import MobileBottomNav from "./MobileBottomNav";
import { type MobileTabId } from "../lib/mobileTypes";

export default function MobileShell({
  activeTab,
  backendReachable,
  loading,
  children,
  onTabChange,
}: Readonly<{
  activeTab: MobileTabId;
  backendReachable: boolean;
  loading: boolean;
  children: ReactNode;
  onTabChange: (tab: MobileTabId) => void;
}>) {
  return (
    <main className="min-h-dvh bg-[#05070b] text-white">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(circle_at_top_left,rgba(34,211,238,0.16),transparent_35%),linear-gradient(160deg,#07111f_0%,#05070b_45%,#101114_100%)]" />
      <div className="relative mx-auto flex min-h-dvh w-full max-w-md flex-col px-4 pb-[calc(6rem+env(safe-area-inset-bottom))] pt-[calc(1rem+env(safe-area-inset-top))]">
        <header className="sticky top-0 z-10 -mx-4 border-b border-white/10 bg-[#05070b]/85 px-4 pb-3 pt-[calc(0.75rem+env(safe-area-inset-top))] backdrop-blur">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300">
                Helix
              </p>
              <h1 className="mt-1 text-xl font-semibold tracking-tight">
                Mobile Home
              </h1>
            </div>
            <span
              className={`rounded-full border px-3 py-1.5 text-xs font-semibold ${
                backendReachable
                  ? "border-emerald-300/25 bg-emerald-300/10 text-emerald-100"
                  : "border-amber-300/25 bg-amber-300/10 text-amber-100"
              }`}
            >
              {loading ? "Checking" : backendReachable ? "Online" : "Offline"}
            </span>
          </div>
        </header>

        <div className="grid gap-4 py-4">{children}</div>
      </div>

      <MobileBottomNav activeTab={activeTab} onTabChange={onTabChange} />
    </main>
  );
}
