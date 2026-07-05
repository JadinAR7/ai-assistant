import {
  MobileCard,
  MobileMetric,
  MobilePrimaryButton,
  MobileSecondaryButton,
} from "./MobileCard";
import {
  type MobileData,
  type MobileTabId,
  type MorningBriefing,
  type PerformanceCalendar,
  type ScheduleBlock,
} from "../lib/mobileTypes";
import {
  formatCurrency,
  formatLabel,
  formatRelativeAge,
  getBlockTime,
  getBlockTitle,
} from "../lib/mobileUtils";

export default function MobileHome({
  data,
  nextBlock,
  scannerSymbol,
  calendarSummary,
  tradePerformance,
  loading,
  scanLoading,
  onRefresh,
  onRunScanner,
  onStartPrompt,
  onTabChange,
}: Readonly<{
  data: MobileData;
  nextBlock: ScheduleBlock | null;
  scannerSymbol: string;
  calendarSummary?: PerformanceCalendar["summary"];
  tradePerformance?: MorningBriefing["trading_performance"];
  loading: boolean;
  scanLoading: boolean;
  onRefresh: () => void;
  onRunScanner: () => void;
  onStartPrompt: (prompt: string) => void;
  onTabChange: (tab: MobileTabId) => void;
}>) {
  const briefing = data.briefing;
  const topTask = briefing?.top_tasks?.[0];
  const blockers = briefing?.current_blockers ?? [];
  const progress = briefing?.major_event?.progress_percent;
  const readiness = briefing?.readiness?.overall;
  const scanPhase =
    data.latestScan?.narrative?.narrative_phase ||
    data.latestScan?.narrative_phase ||
    data.latestScan?.narrative_state;

  return (
    <>
      <MobileCard className="border-cyan-300/20 bg-cyan-300/[0.06]">
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-cyan-200/80">
              Morning Briefing
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">
              {briefing?.major_event?.title || "Helix Daily"}
            </h2>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="min-h-10 rounded-xl border border-white/10 bg-white/[0.04] px-3 text-xs font-semibold text-neutral-200"
          >
            {loading ? "..." : "Refresh"}
          </button>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2">
          <MobileMetric
            label="Progress"
            value={progress === null || progress === undefined ? "--" : `${progress}%`}
          />
          <MobileMetric
            label="Days"
            value={
              briefing?.major_event?.days_remaining === null ||
              briefing?.major_event?.days_remaining === undefined
                ? "--"
                : briefing.major_event.days_remaining
            }
          />
          <MobileMetric
            label="Readiness"
            value={
              readiness === null || readiness === undefined ? "--" : `${readiness}%`
            }
            tone={
              readiness !== null && readiness !== undefined && readiness >= 70
                ? "good"
                : "neutral"
            }
          />
          <MobileMetric
            label="Blockers"
            value={blockers.length}
            tone={blockers.length ? "warn" : "good"}
          />
        </div>

        <div className="mt-4 rounded-xl border border-white/10 bg-black/25 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
            Top Priority
          </p>
          <p className="mt-1 text-sm font-semibold text-neutral-100">
            {topTask?.title || "No priority task loaded yet."}
          </p>
          {topTask?.milestone_title ? (
            <p className="mt-1 text-xs text-neutral-500">
              {topTask.milestone_title}
            </p>
          ) : null}
        </div>

        <div className="mt-3 rounded-xl border border-white/10 bg-black/25 p-3">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
            Next Action
          </p>
          <p className="mt-1 text-sm leading-6 text-neutral-200">
            {briefing?.suggested_next_action || "No suggested action yet."}
          </p>
        </div>

        {blockers.length ? (
          <div className="mt-3 grid gap-2">
            {blockers.slice(0, 2).map((blocker) => (
              <p
                key={blocker}
                className="rounded-xl border border-amber-300/20 bg-amber-300/10 px-3 py-2 text-xs leading-5 text-amber-100"
              >
                {blocker}
              </p>
            ))}
          </div>
        ) : null}
      </MobileCard>

      <MobileCard>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Today / Schedule
            </p>
            <h2 className="mt-1 text-lg font-semibold text-neutral-100">
              {getBlockTitle(nextBlock)}
            </h2>
            <p className="mt-1 text-sm text-neutral-400">
              {getBlockTime(nextBlock)}
            </p>
          </div>
          <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-neutral-400">
            Today
          </span>
        </div>
        <div className="mt-4 grid gap-2">
          <MobilePrimaryButton
            onClick={() =>
              onStartPrompt("Add a 30 minute flexible block to my schedule today.")
            }
          >
            Add Schedule Block
          </MobilePrimaryButton>
          <MobileSecondaryButton onClick={() => onTabChange("schedule")}>
            Open Schedule
          </MobileSecondaryButton>
        </div>
      </MobileCard>

      <MobileCard>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Trading Snapshot
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <MobileMetric
            label="30d PnL"
            value={formatCurrency(
              tradePerformance?.trading_total_pnl_30d ?? calendarSummary?.total_pnl,
            )}
            tone={
              (tradePerformance?.trading_total_pnl_30d ??
                calendarSummary?.total_pnl ??
                0) >= 0
                ? "good"
                : "warn"
            }
          />
          <MobileMetric
            label="Trades"
            value={
              tradePerformance?.trade_count_30d ?? calendarSummary?.trade_count ?? "--"
            }
          />
          <MobileMetric
            label={`${scannerSymbol} Scan`}
            value={formatLabel(scanPhase || data.latestScan?.signal_level)}
          />
          <MobileMetric
            label="Automation"
            value={data.scanStatus?.scanner_enabled ? "On" : "Off"}
            tone={data.scanStatus?.scanner_enabled ? "good" : "warn"}
          />
        </div>
      </MobileCard>

      <MobileCard>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Quick Actions
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <MobilePrimaryButton onClick={() => onTabChange("chat")}>
            Ask Helix
          </MobilePrimaryButton>
          <MobileSecondaryButton onClick={() => onStartPrompt("Add a task: ")}>
            Add Task
          </MobileSecondaryButton>
          <MobileSecondaryButton
            onClick={() => onStartPrompt("Add a schedule block for ")}
          >
            Add Block
          </MobileSecondaryButton>
          <MobileSecondaryButton
            onClick={() => onStartPrompt("Log a quick trade note: ")}
          >
            Log Trade
          </MobileSecondaryButton>
          <MobileSecondaryButton onClick={onRunScanner} disabled={scanLoading}>
            {scanLoading ? "Scanning..." : "Run Scanner"}
          </MobileSecondaryButton>
          <MobileSecondaryButton onClick={() => onTabChange("journal")}>
            Journal
          </MobileSecondaryButton>
        </div>
      </MobileCard>

      <MobileCard>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          System Status
        </p>
        <div className="mt-3 grid gap-2">
          <MobileMetric
            label="Backend"
            value={data.backendReachable ? "Reachable" : "Unavailable"}
            tone={data.backendReachable ? "good" : "warn"}
          />
          <MobileMetric
            label="Scanner Service"
            value={data.scanStatus?.process_running ? "Running" : "Not running"}
            tone={data.scanStatus?.process_running ? "good" : "warn"}
          />
          <MobileMetric
            label="Last Scan"
            value={formatRelativeAge(data.scanStatus?.last_scan_timestamp)}
          />
          <MobileMetric
            label="CSV Automation"
            value={
              data.scanStatus?.csv_automation_paused
                ? "Paused"
                : formatLabel(data.scanStatus?.csv_automation_status || "Ready")
            }
            tone={data.scanStatus?.csv_automation_paused ? "warn" : "good"}
          />
        </div>
      </MobileCard>
    </>
  );
}
