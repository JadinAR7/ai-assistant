import { type MobileTabId } from "../lib/mobileTypes";

const tabs: Array<{ id: MobileTabId; label: string }> = [
  { id: "home", label: "Home" },
  { id: "chat", label: "Chat" },
  { id: "schedule", label: "Schedule" },
  { id: "trading", label: "Trading" },
  { id: "journal", label: "Journal" },
];

export default function MobileBottomNav({
  activeTab,
  onTabChange,
}: Readonly<{
  activeTab: MobileTabId;
  onTabChange: (tab: MobileTabId) => void;
}>) {
  return (
    <nav className="fixed bottom-0 left-0 right-0 z-20 border-t border-white/10 bg-neutral-950/95 px-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] pt-2 backdrop-blur">
      <div className="mx-auto grid max-w-md grid-cols-5 gap-1">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => onTabChange(tab.id)}
            className={`flex min-h-14 flex-col items-center justify-center gap-1 rounded-2xl border px-1 text-[10px] font-semibold transition active:scale-[0.98] ${
              activeTab === tab.id
                ? "border-cyan-300/50 bg-cyan-300/15 text-cyan-100"
                : "border-transparent text-neutral-400 hover:bg-white/[0.06] hover:text-neutral-100"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                activeTab === tab.id ? "bg-cyan-300" : "bg-transparent"
              }`}
            />
            <span className="leading-none">{tab.label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}
