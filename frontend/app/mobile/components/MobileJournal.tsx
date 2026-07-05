import {
  MobileCard,
  MobileMetric,
  MobilePrimaryButton,
} from "./MobileCard";
import {
  type JournalEntry,
  type PerformanceCalendar,
} from "../lib/mobileTypes";
import { formatCurrency, formatDate } from "../lib/mobileUtils";

export default function MobileJournal({
  entries,
  performanceCalendar,
  onStartPrompt,
}: Readonly<{
  entries: JournalEntry[];
  performanceCalendar: PerformanceCalendar | null;
  onStartPrompt: (prompt: string) => void;
}>) {
  const calendarSummary = performanceCalendar?.summary;
  const recentDays = [...(performanceCalendar?.days ?? [])]
    .filter((day) => day.trade_count > 0)
    .sort((left, right) => right.date.localeCompare(left.date))
    .slice(0, 10);

  return (
    <>
      <MobileCard>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Journal
        </p>
        <h2 className="mt-1 text-lg font-semibold">Quick Capture</h2>
        <p className="mt-2 text-sm leading-6 text-neutral-300">
          Capture the note here first. Full imports and coaching stay in the
          desktop admin portal.
        </p>
        <div className="mt-4 grid gap-2">
          <MobilePrimaryButton
            onClick={() => onStartPrompt("Log a quick trade note: ")}
          >
            Quick Log Note
          </MobilePrimaryButton>
        </div>
      </MobileCard>

      <MobileCard>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Profit Calendar
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <MobileMetric
            label="Month PnL"
            value={formatCurrency(calendarSummary?.total_pnl)}
          />
          <MobileMetric
            label="Trades"
            value={calendarSummary?.trade_count ?? "--"}
          />
        </div>

        <div className="mt-4 grid gap-2">
          {recentDays.length ? (
            recentDays.map((day) => (
              <div
                key={day.date}
                className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-black/25 p-3"
              >
                <div>
                  <p className="text-sm font-semibold text-neutral-100">
                    {formatDate(day.date)}
                  </p>
                  <p className="mt-1 text-xs text-neutral-500">
                    {day.trade_count} trade{day.trade_count === 1 ? "" : "s"}
                    {day.win_count !== undefined || day.loss_count !== undefined
                      ? ` · ${day.win_count ?? 0}W/${day.loss_count ?? 0}L`
                      : ""}
                  </p>
                </div>
                <p
                  className={`text-sm font-semibold ${
                    day.total_pnl >= 0 ? "text-emerald-200" : "text-amber-200"
                  }`}
                >
                  {formatCurrency(day.total_pnl)}
                </p>
              </div>
            ))
          ) : (
            <p className="rounded-xl border border-dashed border-white/10 px-3 py-4 text-sm text-neutral-500">
              Daily PnL will appear here after calendar data loads.
            </p>
          )}
        </div>
      </MobileCard>

      <MobileCard>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Recent Entries
        </p>
        <div className="mt-3 grid gap-2">
          {entries.length ? (
            entries.map((entry) => (
              <div
                key={entry.id}
                className="rounded-xl border border-white/10 bg-black/25 p-3"
              >
                <p className="text-sm font-semibold text-neutral-100">
                  {entry.symbol || "Trade"}{" "}
                  {entry.direction ? `· ${entry.direction}` : ""}
                </p>
                <p className="mt-1 text-xs text-neutral-500">
                  {formatDate(entry.trade_date)} ·{" "}
                  {formatCurrency(entry.result_dollars)}
                </p>
              </div>
            ))
          ) : (
            <p className="rounded-xl border border-dashed border-white/10 px-3 py-4 text-sm text-neutral-500">
              Recent entries will appear here.
            </p>
          )}
        </div>
      </MobileCard>
    </>
  );
}
