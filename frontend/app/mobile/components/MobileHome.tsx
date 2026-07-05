import {
  MobileCard,
  MobileMetric,
  MobilePrimaryButton,
  MobileSecondaryButton,
} from "./MobileCard";
import MobileNotifications from "./MobileNotifications";
import {
  type MobileActionResult,
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

type QuickCommand = (command: string, title?: string) => void;

function MobileStatusNote({
  title,
  message,
  actionLabel,
  onAction,
}: Readonly<{
  title: string;
  message: string;
  actionLabel?: string;
  onAction?: () => void;
}>) {
  return (
    <MobileCard className="border-amber-300/25 bg-amber-300/10">
      <p className="text-sm font-semibold text-amber-100">{title}</p>
      <p className="mt-1 text-xs leading-5 text-amber-100/75">{message}</p>
      {actionLabel && onAction ? (
        <div className="mt-3">
          <MobileSecondaryButton onClick={onAction}>{actionLabel}</MobileSecondaryButton>
        </div>
      ) : null}
    </MobileCard>
  );
}

export default function MobileHome({
  data,
  nextBlock,
  nextFlexibleBlock,
  calendarSummary,
  tradePerformance,
  loading,
  scanLoading,
  quickCommandLoading,
  mobileQueueLoading,
  actionResult,
  onRefresh,
  onRunScanner,
  onQuickCommand,
  onCompleteReminder,
  onDismissReminder,
  onStartScheduleBlock,
  onPauseScheduleBlock,
  onResumeScheduleBlock,
  onExtendScheduleBlock,
  onRollScheduleBlock,
  onAckNotification,
  onCompleteNotification,
  onStartPrompt,
  onTabChange,
}: Readonly<{
  data: MobileData;
  nextBlock: ScheduleBlock | null;
  nextFlexibleBlock: ScheduleBlock | null;
  calendarSummary?: PerformanceCalendar["summary"];
  tradePerformance?: MorningBriefing["trading_performance"];
  loading: boolean;
  scanLoading: boolean;
  quickCommandLoading: string | null;
  mobileQueueLoading: string | null;
  actionResult: MobileActionResult | null;
  onRefresh: () => void;
  onRunScanner: () => void;
  onQuickCommand: QuickCommand;
  onCompleteReminder: (id: number) => void;
  onDismissReminder: (id: number) => void;
  onStartScheduleBlock: (id: number) => void;
  onPauseScheduleBlock: (id: number) => void;
  onResumeScheduleBlock: (id: number) => void;
  onExtendScheduleBlock: (id: number) => void;
  onRollScheduleBlock: (id: number) => void;
  onAckNotification: (id: number) => void;
  onCompleteNotification: (id: number) => void;
  onStartPrompt: (prompt: string) => void;
  onTabChange: (tab: MobileTabId) => void;
}>) {
  const briefing = data.briefing;
  const topTask = briefing?.top_tasks?.[0];
  const blockers = briefing?.current_blockers ?? [];
  const progress = briefing?.major_event?.progress_percent;
  const readiness = briefing?.readiness?.overall;
  const tradeCount = tradePerformance?.trade_count_30d ?? calendarSummary?.trade_count;
  const pnl = tradePerformance?.trading_total_pnl_30d ?? calendarSummary?.total_pnl;
  const scanHealth = data.latestScan?.system_health?.status;
  const scanPhase =
    data.latestScan?.narrative?.narrative_phase ||
    data.latestScan?.narrative_phase ||
    data.latestScan?.narrative_state ||
    data.latestScan?.signal_level;

  return (
    <>
      <MobileCard className="border-cyan-300/20 bg-cyan-300/[0.06]">
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-cyan-200/80">
              Daily Command Surface
            </p>
            <h2 className="mt-2 text-2xl font-semibold tracking-tight">
              What matters now
            </h2>
            <p className="mt-1 text-sm text-neutral-400">
              Briefing, focus, schedule, trading, and quick commands.
            </p>
          </div>
          <button
            type="button"
            onClick={onRefresh}
            className="min-h-10 rounded-xl border border-white/10 bg-white/[0.04] px-3 text-xs font-semibold text-neutral-200"
          >
            {loading ? "..." : "Refresh"}
          </button>
        </div>
      </MobileCard>

      {!loading && !data.backendReachable ? (
        <MobileStatusNote
          title="Helix backend is offline."
          message="Try again when the Mac mini is reachable."
          actionLabel="Retry"
          onAction={onRefresh}
        />
      ) : null}

      {!loading && data.backendReachable && data.loadErrors.briefing ? (
        <MobileStatusNote
          title={"Couldn't load briefing."}
          message="Your daily cards are still usable, but Orbit briefing data did not come through."
          actionLabel="Retry"
          onAction={onRefresh}
        />
      ) : null}

      <MobileCard>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Morning Briefing
            </p>
            <h2 className="mt-1 text-lg font-semibold text-neutral-100">
              {briefing?.major_event?.title || "Briefing unavailable"}
            </h2>
          </div>
          <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-neutral-400">
            Orbit
          </span>
        </div>

        <div className="mt-3 grid grid-cols-3 gap-2">
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
            label="Ready"
            value={
              readiness === null || readiness === undefined ? "--" : `${readiness}%`
            }
            tone={
              readiness !== null && readiness !== undefined && readiness >= 70
                ? "good"
                : "neutral"
            }
          />
        </div>

        <div className="mt-3 rounded-xl border border-white/10 bg-black/25 p-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                Top Priority
              </p>
              <p className="mt-1 text-sm font-semibold text-neutral-100">
                {topTask?.title || "No priority task loaded yet."}
              </p>
            </div>
            <span
              className={`shrink-0 rounded-full border px-2 py-1 text-[11px] font-semibold ${
                blockers.length
                  ? "border-amber-300/25 bg-amber-300/10 text-amber-100"
                  : "border-emerald-300/25 bg-emerald-300/10 text-emerald-100"
              }`}
            >
              {blockers.length} blocker{blockers.length === 1 ? "" : "s"}
            </span>
          </div>
          <p className="mt-2 text-xs leading-5 text-neutral-400">
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
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Today Focus
        </p>
        <h2 className="mt-1 text-lg font-semibold text-neutral-100">
          {topTask?.title || "No focus task yet"}
        </h2>
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-neutral-400">
            {topTask?.milestone_title || "Inbox / General"}
          </span>
          <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-neutral-400">
            {topTask?.due_date ? `Due ${topTask.due_date}` : "No due date"}
          </span>
          <span className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-2 py-1 text-cyan-100">
            P{topTask?.priority_score ?? 0}
          </span>
        </div>
        <div className="mt-4">
          <MobilePrimaryButton
            onClick={() =>
              onQuickCommand(
                topTask
                  ? `Help me advance this task today: ${topTask.title}`
                  : "Help me choose one useful focus task for today from Orbit.",
                "Advance task",
              )
            }
            disabled={Boolean(quickCommandLoading)}
          >
            {quickCommandLoading === "Advance task" ? "Advancing..." : "Advance task"}
          </MobilePrimaryButton>
        </div>
      </MobileCard>

      <MobileCard>
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Schedule
            </p>
            <h2 className="mt-1 text-lg font-semibold text-neutral-100">
              {nextBlock
                ? getBlockTitle(nextBlock)
                : "No scheduled blocks found for today."}
            </h2>
            <p className="mt-1 text-sm text-neutral-400">
              {nextBlock ? getBlockTime(nextBlock) : "Use a quick command to add one."}
            </p>
          </div>
          <span className="rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-xs text-neutral-400">
            Today
          </span>
        </div>

        {nextFlexibleBlock ? (
          <div className="mt-3 rounded-xl border border-cyan-300/15 bg-cyan-300/5 px-3 py-2">
            <p className="text-[11px] font-semibold uppercase tracking-wide text-cyan-200/80">
              Flexible block waiting
            </p>
            <p className="mt-1 text-sm text-neutral-200">
              {getBlockTitle(nextFlexibleBlock)} · {getBlockTime(nextFlexibleBlock)}
            </p>
          </div>
        ) : null}

        <div className="mt-4 grid grid-cols-3 gap-2">
          <MobileSecondaryButton
            onClick={() =>
              onQuickCommand(
                "Can you add 30 minutes of reading to my schedule?",
                "Add reading",
              )
            }
            disabled={Boolean(quickCommandLoading)}
          >
            Reading
          </MobileSecondaryButton>
          <MobileSecondaryButton
            onClick={() =>
              onQuickCommand("Add a workout to my schedule today.", "Add workout")
            }
            disabled={Boolean(quickCommandLoading)}
          >
            Workout
          </MobileSecondaryButton>
          <MobileSecondaryButton
            onClick={() =>
              onQuickCommand(
                "Plan my day from my current Orbit priorities and schedule.",
                "Plan my day",
              )
            }
            disabled={Boolean(quickCommandLoading)}
          >
            Plan
          </MobileSecondaryButton>
        </div>
      </MobileCard>

      <MobileCard>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Trading Snapshot
        </p>
        {data.loadErrors.scannerStatus ? (
          <p className="mt-2 rounded-xl border border-amber-300/20 bg-amber-300/10 px-3 py-2 text-xs leading-5 text-amber-100">
            Couldn&apos;t load scanner status. Try again when the Mac mini is reachable.
          </p>
        ) : null}
        <div className="mt-3 grid grid-cols-2 gap-2">
          <MobileMetric
            label="30D PnL"
            value={formatCurrency(pnl)}
            tone={(pnl ?? 0) >= 0 ? "good" : "warn"}
          />
          <MobileMetric label="30D Trades" value={tradeCount ?? "--"} />
          <MobileMetric
            label="Scanner"
            value={data.scanStatus?.scanner_enabled ? "On" : "Off"}
            tone={data.scanStatus?.scanner_enabled ? "good" : "warn"}
          />
          <MobileMetric label="Health" value={formatLabel(scanHealth)} />
          <MobileMetric label="Phase" value={formatLabel(scanPhase)} />
          <MobileMetric
            label="Last Scan"
            value={formatRelativeAge(data.scanStatus?.last_scan_timestamp)}
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
          <MobileSecondaryButton
            onClick={() => onQuickCommand("Add a task:", "Add task")}
            disabled={Boolean(quickCommandLoading)}
          >
            Add Task
          </MobileSecondaryButton>
          <MobileSecondaryButton
            onClick={() =>
              onQuickCommand(
                "Can you add 30 minutes of reading to my schedule?",
                "Add schedule block",
              )
            }
            disabled={Boolean(quickCommandLoading)}
          >
            Add Schedule Block
          </MobileSecondaryButton>
          <MobileSecondaryButton
            onClick={() =>
              onQuickCommand(
                "Remind me tonight to review my top priority.",
                "Remind me tonight",
              )
            }
            disabled={Boolean(quickCommandLoading)}
          >
            Remind Tonight
          </MobileSecondaryButton>
          <MobileSecondaryButton
            onClick={() =>
              onQuickCommand(
                "Remind me to review my trades tonight.",
                "Review trades reminder",
              )
            }
            disabled={Boolean(quickCommandLoading)}
          >
            Review Trades
          </MobileSecondaryButton>
          <MobileSecondaryButton onClick={() => onStartPrompt("Remind me to ")}>
            Set Reminder
          </MobileSecondaryButton>
          <MobileSecondaryButton
            onClick={() =>
              onQuickCommand(
                "Plan my day from my Orbit schedule and top priorities.",
                "Plan my day",
              )
            }
            disabled={Boolean(quickCommandLoading)}
          >
            Plan My Day
          </MobileSecondaryButton>
          <MobileSecondaryButton
            onClick={() => onQuickCommand("Log a trade note:", "Log trade note")}
            disabled={Boolean(quickCommandLoading)}
          >
            Log Trade Note
          </MobileSecondaryButton>
          <MobileSecondaryButton onClick={onRunScanner} disabled={scanLoading}>
            {scanLoading ? "Scanning..." : "Run Scanner"}
          </MobileSecondaryButton>
        </div>
      </MobileCard>

      {actionResult ? (
        <MobileCard
          className={
            actionResult.error
              ? "border-amber-300/25 bg-amber-300/10"
              : "border-emerald-300/25 bg-emerald-300/10"
          }
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
            {actionResult.title}
          </p>
          <p className="mt-2 text-sm leading-6 text-neutral-100">
            {actionResult.message}
          </p>
        </MobileCard>
      ) : null}

      <MobileNotifications
        center={data.notificationCenter}
        actionLoading={mobileQueueLoading}
        onCompleteReminder={onCompleteReminder}
        onDismissReminder={onDismissReminder}
        onStartScheduleBlock={onStartScheduleBlock}
        onPauseScheduleBlock={onPauseScheduleBlock}
        onResumeScheduleBlock={onResumeScheduleBlock}
        onExtendScheduleBlock={onExtendScheduleBlock}
        onRollScheduleBlock={onRollScheduleBlock}
        onAckNotification={onAckNotification}
        onCompleteNotification={onCompleteNotification}
        loadFailed={data.loadErrors.notifications}
        onRetry={onRefresh}
      />
    </>
  );
}
