import {
  MobileCard,
  MobileMetric,
  MobilePrimaryButton,
} from "./MobileCard";
import {
  type MorningBriefing,
  type PerformanceCalendar,
  type ScanRecord,
  type ScanStatus,
} from "../lib/mobileTypes";
import {
  formatCurrency,
  formatLabel,
  formatRelativeAge,
} from "../lib/mobileUtils";

export default function MobileTrading({
  scannerSymbol,
  scanStatus,
  latestScan,
  calendarSummary,
  tradePerformance,
  scanLoading,
  onRunScanner,
}: Readonly<{
  scannerSymbol: string;
  scanStatus: ScanStatus | null;
  latestScan: ScanRecord | null;
  calendarSummary?: PerformanceCalendar["summary"];
  tradePerformance?: MorningBriefing["trading_performance"];
  scanLoading: boolean;
  onRunScanner: () => void;
}>) {
  const scanPhase =
    latestScan?.narrative?.narrative_phase ||
    latestScan?.narrative_phase ||
    latestScan?.narrative_state;

  return (
    <>
      <MobileCard>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Trading
        </p>
        <h2 className="mt-1 text-lg font-semibold">Performance Snapshot</h2>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <MobileMetric
            label="30d PnL"
            value={formatCurrency(
              tradePerformance?.trading_total_pnl_30d ?? calendarSummary?.total_pnl,
            )}
          />
          <MobileMetric
            label="Trades"
            value={
              tradePerformance?.trade_count_30d ?? calendarSummary?.trade_count ?? "--"
            }
          />
          <MobileMetric
            label="Winning Days"
            value={tradePerformance?.winning_days_30d ?? "--"}
          />
          <MobileMetric
            label="Losing Days"
            value={tradePerformance?.losing_days_30d ?? "--"}
          />
        </div>
      </MobileCard>
      <MobileCard>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Latest Scanner Review
        </p>
        <h2 className="mt-1 text-lg font-semibold">{scannerSymbol}</h2>
        <div className="mt-3 grid gap-2">
          <MobileMetric
            label="Phase"
            value={formatLabel(scanPhase || latestScan?.signal_level)}
          />
          <MobileMetric
            label="Health"
            value={formatLabel(latestScan?.system_health?.status || "Unknown")}
          />
          <MobileMetric
            label="Automation"
            value={scanStatus?.scanner_enabled ? "On" : "Off"}
            tone={scanStatus?.scanner_enabled ? "good" : "warn"}
          />
          <MobileMetric
            label="Last Scan"
            value={formatRelativeAge(scanStatus?.last_scan_timestamp)}
          />
        </div>
        <div className="mt-4 grid gap-2">
          <MobilePrimaryButton onClick={onRunScanner} disabled={scanLoading}>
            {scanLoading ? "Scanning..." : "Run Manual Scan"}
          </MobilePrimaryButton>
        </div>
      </MobileCard>
    </>
  );
}
