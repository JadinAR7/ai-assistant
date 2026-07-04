"use client";

import Link from "next/link";
import {
  FormEvent,
  RefObject,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const JOURNAL_URL = `${API_BASE}/orbit/trade-journal`;
const PERFORMANCE_CALENDAR_URL = `${JOURNAL_URL}/performance-calendar`;
const IMPORT_URL = `${JOURNAL_URL}/import-pdf`;
const IMPORT_SAVE_URL = `${IMPORT_URL}/save`;
const IMPORT_CALENDAR_SAVE_URL = `${IMPORT_URL}/save-calendar`;
const TRADING_COACH_REVIEW_URL = `${API_BASE}/orbit/trading-coach/review`;
const TRADING_CORRELATION_REVIEW_URL = `${API_BASE}/orbit/trading-correlation/review`;
const PATTERN_DISCOVERY_REVIEW_URL = `${API_BASE}/orbit/pattern-discovery/review`;

const directions = ["Long", "Short"] as const;
const sessions = ["Asia", "London", "New York", "After Hours"] as const;
const htfBiasOptions = ["Bullish", "Bearish", "Neutral"] as const;
const strategyProfileName = "Liquidity Narrative Continuation";
const strategyModeOptions = ["Scalp", "Day Trade", "Hybrid / Review"] as const;
const liquidityOptions = [
  "PDH",
  "PDL",
  "Asia High",
  "Asia Low",
  "London High",
  "London Low",
  "Weekly High",
  "Weekly Low",
  "Custom",
] as const;
const reactionZoneOptions = [
  "Daily FVG",
  "4H FVG",
  "1H FVG",
  "15M FVG",
  "Custom",
] as const;
const behaviorOptions = [
  "Acceptance",
  "Rejection",
  "Sweep",
  "Reclaim",
  "Displacement",
  "Consolidation",
] as const;
const executionOptions = [
  "BRTC",
  "MSS",
  "BOS",
  "FVG Retest",
  "Liquidity Sweep",
] as const;

type Direction = (typeof directions)[number];
type TradeSession = (typeof sessions)[number];
type HtfBias = (typeof htfBiasOptions)[number];
type StrategyMode = (typeof strategyModeOptions)[number];
type TradeJournalSection =
  | "home"
  | "import"
  | "manual"
  | "entries"
  | "calendar"
  | "coach"
  | "scanner"
  | "patterns";

const sectionNavItems: { id: TradeJournalSection; label: string }[] = [
  { id: "home", label: "Home" },
  { id: "import", label: "Import" },
  { id: "manual", label: "Manual" },
  { id: "entries", label: "Entries" },
  { id: "calendar", label: "Calendar" },
  { id: "coach", label: "Coach" },
  { id: "scanner", label: "Scanner Match" },
  { id: "patterns", label: "Patterns" },
];
type DraftStatus = "pending" | "saved" | "skipped";

type TradeJournalEntry = {
  id: number;
  trade_date: string;
  symbol: string;
  direction: Direction;
  entry_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  exit_price: number | null;
  result_dollars: number | null;
  result_r: number | null;
  contracts: number | null;
  session: TradeSession | null;
  htf_bias: HtfBias | null;
  strategy_profile: string;
  strategy_mode: StrategyMode;
  draw_on_liquidity: string[];
  reaction_zone: string | null;
  behavior_tags: string[];
  execution_tags: string[];
  why_taken: string | null;
  price_intent: string | null;
  liquidity_target: string | null;
  went_well: string | null;
  went_wrong: string | null;
  lesson_learned: string | null;
  screenshot_path: string | null;
  csv_path: string | null;
  created_at: string;
  updated_at: string;
};

type DailySummary = {
  gross_pnl: number | null;
  total_pnl: number | null;
  fees_commissions: number | null;
  trade_count: number | null;
  contract_count: number | null;
  win_rate: number | null;
  expectancy: number | null;
  average_trade_time: string | null;
  longest_trade_time: string | null;
};

type ImportedOrder = {
  order_id: string | null;
  side: string | null;
  quantity: number | null;
  contract: string | null;
  order_type: string | null;
  limit_price: number | null;
  stop_price: number | null;
  status: string | null;
  filled_qty: number | null;
  fill_time: string | null;
  average_fill_price: number | null;
  timestamp: string | null;
  account: string | null;
  venue: string | null;
  notional_value: number | null;
};

type ImportDraft = {
  draft_id: string;
  selected: boolean;
  trade_date: string | null;
  symbol: string;
  direction: Direction;
  quantity: number | null;
  contracts: number | null;
  entry_price: number | null;
  entry_time: string | null;
  exit_price: number | null;
  exit_time: string | null;
  duration: string | null;
  pnl: number | null;
  session: TradeSession | null;
  stop_detected: boolean;
  stop_canceled: boolean;
  market_entry: boolean;
  market_exit: boolean;
  limit_entry: boolean;
  limit_exit: boolean;
  related_order_ids: string[];
  warnings: string[];
  htf_bias: HtfBias | null;
  draw_on_liquidity: string[];
  reaction_zone: string | null;
  behavior_tags: string[];
  execution_tags: string[];
  why_taken: string | null;
  price_intent: string | null;
  liquidity_target: string | null;
  went_well: string | null;
  went_wrong: string | null;
  lesson_learned: string | null;
  screenshot_path: string | null;
  csv_path: string | null;
};

type ImportPreview = {
  daily_summary: DailySummary;
  trade_drafts: ImportDraft[];
  unmatched_orders: ImportedOrder[];
  warnings: string[];
  source_files: {
    performance_pdf: string | null;
    orders_pdf: string | null;
  };
};

type ImportSaveResponse = {
  created_entries: TradeJournalEntry[];
  warnings: string[];
};

type CalendarImportSaveResponse = {
  created_entries: TradeJournalEntry[];
  imported: number;
  skipped_duplicates: number;
  updated: number;
  warnings: string[];
};

type CalendarNetResult = "win" | "loss" | "flat" | "no_trades";
type CalendarSourceFilter = "all" | "journal" | "calendar_only";

type PerformanceCalendarDay = {
  date: string;
  total_pnl: number;
  trade_count: number;
  win_count: number;
  loss_count: number;
  net_result: CalendarNetResult;
  largest_win: number | null;
  largest_loss: number | null;
  symbols: string[];
  sources: Record<string, { pnl: number; trade_count: number }>;
};

type PerformanceCalendar = {
  month: string;
  summary: {
    total_pnl: number;
    trade_count: number;
    winning_days: number;
    losing_days: number;
    flat_days: number;
    best_day: { date: string; pnl: number } | null;
    worst_day: { date: string; pnl: number } | null;
  };
  days: PerformanceCalendarDay[];
};

type CalendarCell = {
  date: string | null;
  dayNumber: number | null;
  isToday: boolean;
  performance: PerformanceCalendarDay | null;
};

type TradingCoachReview = {
  summary: {
    total_trades_reviewed: number;
    wins: number | null;
    losses: number | null;
    total_pnl: number | null;
    average_pnl: number | null;
    strategy_mode_distribution: Record<string, number>;
    session_distribution: Record<string, number>;
  };
  strengths: string[];
  weaknesses: string[];
  missing_data: string[];
  model_alignment: {
    label: string;
    score: number;
    complete_context_trades: number;
    weak_context_trades: number;
  };
  suggested_focus: string[];
  warnings: string[];
  readable_summary: string;
};

type TradingCorrelationReview = {
  summary: {
    trades_reviewed: number;
    trades_with_scan_match: number;
    aligned_count: number;
    partially_aligned_count: number;
    conflicted_count: number;
    insufficient_data_count: number;
    common_mismatches: { reason: string; count: number }[];
  };
  correlations: {
    journal_entry_id: number;
    symbol: string;
    trade_date: string;
    direction: Direction;
    result_dollars: number | null;
    alignment_label: string;
    match_confidence: string;
    scanner_narrative_phase: string | null;
    scanner_signal_level: string | null;
  }[];
  suggested_data_to_capture: string[];
  readable_summary: string;
};

type PatternDiscoveryReview = {
  summary: {
    trades_reviewed: number;
    total_pnl: number | null;
    average_pnl: number | null;
  };
  sample_size_warning: string | null;
  recurring_strengths: string[];
  recurring_weaknesses: string[];
  profitable_contexts: string[];
  weak_contexts: string[];
  missing_data_patterns: string[];
  suggested_next_review_questions: string[];
  pattern_confidence: string;
  readable_summary: string;
};

type JournalForm = {
  trade_date: string;
  symbol: string;
  direction: Direction;
  entry_price: string;
  stop_loss: string;
  take_profit: string;
  exit_price: string;
  result_dollars: string;
  result_r: string;
  contracts: string;
  session: "" | TradeSession;
  htf_bias: "" | HtfBias;
  strategy_profile: string;
  strategy_mode: StrategyMode;
  draw_on_liquidity: string[];
  reaction_zone: string;
  behavior_tags: string[];
  execution_tags: string[];
  why_taken: string;
  price_intent: string;
  liquidity_target: string;
  went_well: string;
  went_wrong: string;
  lesson_learned: string;
  screenshot_path: string;
  csv_path: string;
};

const emptyForm = (): JournalForm => ({
  trade_date: new Date().toISOString().slice(0, 10),
  symbol: "",
  direction: "Long",
  entry_price: "",
  stop_loss: "",
  take_profit: "",
  exit_price: "",
  result_dollars: "",
  result_r: "",
  contracts: "",
  session: "",
  htf_bias: "",
  strategy_profile: strategyProfileName,
  strategy_mode: "Hybrid / Review",
  draw_on_liquidity: [],
  reaction_zone: "",
  behavior_tags: [],
  execution_tags: [],
  why_taken: "",
  price_intent: "",
  liquidity_target: "",
  went_well: "",
  went_wrong: "",
  lesson_learned: "",
  screenshot_path: "",
  csv_path: "",
});

function formFromEntry(entry: TradeJournalEntry): JournalForm {
  return {
    trade_date: entry.trade_date,
    symbol: entry.symbol,
    direction: entry.direction,
    entry_price: entry.entry_price?.toString() ?? "",
    stop_loss: entry.stop_loss?.toString() ?? "",
    take_profit: entry.take_profit?.toString() ?? "",
    exit_price: entry.exit_price?.toString() ?? "",
    result_dollars: entry.result_dollars?.toString() ?? "",
    result_r: entry.result_r?.toString() ?? "",
    contracts: entry.contracts?.toString() ?? "",
    session: entry.session ?? "",
    htf_bias: entry.htf_bias ?? "",
    strategy_profile: entry.strategy_profile || strategyProfileName,
    strategy_mode: entry.strategy_mode ?? "Hybrid / Review",
    draw_on_liquidity: entry.draw_on_liquidity,
    reaction_zone: entry.reaction_zone ?? "",
    behavior_tags: entry.behavior_tags,
    execution_tags: entry.execution_tags,
    why_taken: entry.why_taken ?? "",
    price_intent: entry.price_intent ?? "",
    liquidity_target: entry.liquidity_target ?? "",
    went_well: entry.went_well ?? "",
    went_wrong: entry.went_wrong ?? "",
    lesson_learned: entry.lesson_learned ?? "",
    screenshot_path: entry.screenshot_path ?? "",
    csv_path: entry.csv_path ?? "",
  };
}

function optionalNumber(value: string) {
  if (value.trim() === "") {
    return null;
  }
  return Number(value);
}

function optionalText(value: string) {
  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}

function toPayload(form: JournalForm) {
  return {
    trade_date: form.trade_date,
    symbol: form.symbol.trim().toUpperCase(),
    direction: form.direction,
    entry_price: optionalNumber(form.entry_price),
    stop_loss: optionalNumber(form.stop_loss),
    take_profit: optionalNumber(form.take_profit),
    exit_price: optionalNumber(form.exit_price),
    result_dollars: optionalNumber(form.result_dollars),
    result_r: optionalNumber(form.result_r),
    contracts:
      form.contracts.trim() === "" ? null : Math.max(0, Number(form.contracts)),
    session: form.session || null,
    htf_bias: form.htf_bias || null,
    strategy_profile: form.strategy_profile || strategyProfileName,
    strategy_mode: form.strategy_mode,
    draw_on_liquidity: form.draw_on_liquidity,
    reaction_zone: optionalText(form.reaction_zone),
    behavior_tags: form.behavior_tags,
    execution_tags: form.execution_tags,
    why_taken: optionalText(form.why_taken),
    price_intent: optionalText(form.price_intent),
    liquidity_target: optionalText(form.liquidity_target),
    went_well: optionalText(form.went_well),
    went_wrong: optionalText(form.went_wrong),
    lesson_learned: optionalText(form.lesson_learned),
    screenshot_path: optionalText(form.screenshot_path),
    csv_path: optionalText(form.csv_path),
  };
}

function formatCurrency(value: number | null) {
  if (value === null) {
    return "--";
  }

  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatNumber(value: number | null, suffix = "") {
  if (value === null) {
    return "--";
  }

  return `${value}${suffix}`;
}

function formatPercent(value: number | null) {
  if (value === null) {
    return "--";
  }

  return `${value}%`;
}

function resultClass(value: number | null) {
  if (value === null) {
    return "text-neutral-300";
  }
  if (value > 0) {
    return "text-emerald-300";
  }
  if (value < 0) {
    return "text-red-300";
  }
  return "text-neutral-200";
}

function toMonthKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

function toDateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(
    date.getDate(),
  ).padStart(2, "0")}`;
}

function parseMonthKey(month: string) {
  const [year, monthNumber] = month.split("-").map(Number);
  return new Date(year, (monthNumber || 1) - 1, 1);
}

function shiftMonth(month: string, offset: number) {
  const date = parseMonthKey(month);
  date.setMonth(date.getMonth() + offset);
  return toMonthKey(date);
}

function formatMonthLabel(month: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    year: "numeric",
  }).format(parseMonthKey(month));
}

function buildCalendarCells(
  month: string,
  calendar: PerformanceCalendar | null,
): CalendarCell[] {
  const monthStart = parseMonthKey(month);
  const performanceByDate = new Map(
    (calendar?.days ?? []).map((day) => [day.date, day]),
  );
  const todayKey = toDateKey(new Date());
  const daysInMonth = new Date(
    monthStart.getFullYear(),
    monthStart.getMonth() + 1,
    0,
  ).getDate();
  const leadingPlaceholders = Array.from(
    { length: monthStart.getDay() },
    () => ({
      date: null,
      dayNumber: null,
      isToday: false,
      performance: null,
    }),
  );
  const monthCells = Array.from({ length: daysInMonth }, (_, index) => {
    const cellDate = new Date(monthStart);
    cellDate.setDate(index + 1);
    const dateKey = toDateKey(cellDate);

    return {
      date: dateKey,
      dayNumber: cellDate.getDate(),
      isToday: dateKey === todayKey,
      performance: performanceByDate.get(dateKey) ?? null,
    };
  });

  return [...leadingPlaceholders, ...monthCells];
}

function calendarCellClass(cell: CalendarCell) {
  const netResult = cell.performance?.net_result ?? "no_trades";
  const tone =
    netResult === "win"
      ? "border-emerald-300/30 bg-emerald-400/10"
      : netResult === "loss"
        ? "border-red-300/30 bg-red-400/10"
        : netResult === "flat"
          ? "border-amber-300/25 bg-amber-300/10"
          : "border-white/10 bg-neutral-950";
  const today = cell.isToday ? "ring-1 ring-cyan-300/70" : "";

  return `${tone} ${today}`;
}

function toggleValue(values: string[], value: string) {
  return values.includes(value)
    ? values.filter((item) => item !== value)
    : [...values, value];
}

function FieldLabel({
  label,
  children,
}: Readonly<{ label: string; children: React.ReactNode }>) {
  return (
    <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
      {label}
      {children}
    </label>
  );
}

function inputClassName(extra = "") {
  return `min-h-10 rounded-lg border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none transition placeholder:text-neutral-600 focus:border-cyan-300/60 ${extra}`;
}

function TagGroup({
  label,
  options,
  values,
  onChange,
}: Readonly<{
  label: string;
  options: readonly string[];
  values: string[];
  onChange: (values: string[]) => void;
}>) {
  return (
    <div>
      <p className="text-xs font-semibold text-neutral-300">{label}</p>
      <div className="mt-2 flex flex-wrap gap-2">
        {options.map((option) => {
          const active = values.includes(option);
          return (
            <button
              key={option}
              type="button"
              onClick={() => onChange(toggleValue(values, option))}
              className={`rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                active
                  ? "border-cyan-300/60 bg-cyan-300/15 text-cyan-100"
                  : "border-white/10 bg-white/[0.03] text-neutral-400 hover:border-white/25 hover:text-white"
              }`}
            >
              {option}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function DetailRow({
  label,
  value,
}: Readonly<{ label: string; value: React.ReactNode }>) {
  return (
    <div className="rounded-lg border border-white/10 bg-neutral-950 p-3">
      <p className="text-xs text-neutral-500">{label}</p>
      <div className="mt-1 text-sm font-semibold text-neutral-100">{value}</div>
    </div>
  );
}

function TextBlock({
  title,
  value,
}: Readonly<{ title: string; value: string | null }>) {
  return (
    <section className="rounded-lg border border-white/10 bg-neutral-950 p-4">
      <h3 className="text-xs font-semibold uppercase text-neutral-500">
        {title}
      </h3>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-neutral-300">
        {value || "--"}
      </p>
    </section>
  );
}

function ChipList({ values }: Readonly<{ values: string[] }>) {
  if (values.length === 0) {
    return <span className="text-neutral-500">--</span>;
  }

  return (
    <div className="flex flex-wrap gap-1.5">
      {values.map((value) => (
        <span
          key={value}
          className="rounded-md border border-cyan-300/25 bg-cyan-300/10 px-2 py-1 text-xs text-cyan-100"
        >
          {value}
        </span>
      ))}
    </div>
  );
}

function ReviewList({
  title,
  values,
}: Readonly<{ title: string; values: string[] }>) {
  return (
    <section className="rounded-lg border border-white/10 bg-neutral-950 p-3">
      <h3 className="text-xs font-semibold uppercase text-neutral-500">
        {title}
      </h3>
      {values.length === 0 ? (
        <p className="mt-2 text-sm text-neutral-500">--</p>
      ) : (
        <ul className="mt-2 grid gap-2 text-sm leading-6 text-neutral-300">
          {values.slice(0, 4).map((value) => (
            <li key={value}>{value}</li>
          ))}
        </ul>
      )}
    </section>
  );
}

function PdfFilePicker({
  label,
  file,
  inputRef,
  onChange,
  onClear,
}: Readonly<{
  label: string;
  file: File | null;
  inputRef: RefObject<HTMLInputElement | null>;
  onChange: (file: File | null) => void;
  onClear: () => void;
}>) {
  return (
    <div className="grid gap-1.5 text-xs font-semibold text-neutral-300">
      <span>{label}</span>
      <input
        ref={inputRef}
        type="file"
        accept="application/pdf,.pdf"
        onChange={(event) => onChange(event.target.files?.[0] ?? null)}
        className="sr-only"
      />
      <div className="flex min-w-0 flex-col gap-2 rounded-lg border border-white/10 bg-neutral-950 p-2 sm:flex-row sm:items-center">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="shrink-0 rounded-md bg-cyan-300 px-3 py-2 text-xs font-semibold text-slate-950 transition hover:bg-cyan-200"
        >
          Choose PDF
        </button>
        <p className="min-w-0 flex-1 truncate px-1 text-sm font-medium text-neutral-300">
          {file?.name ?? "No file selected"}
        </p>
        {file ? (
          <button
            type="button"
            onClick={onClear}
            className="shrink-0 rounded-md border border-red-400/30 px-3 py-2 text-xs font-semibold text-red-100 hover:bg-red-500/10"
          >
            Remove
          </button>
        ) : null}
      </div>
    </div>
  );
}

export default function TradeJournalPage() {
  const performanceInputRef = useRef<HTMLInputElement | null>(null);
  const ordersInputRef = useRef<HTMLInputElement | null>(null);
  const calendarPerformanceInputRef = useRef<HTMLInputElement | null>(null);
  const calendarOrdersInputRef = useRef<HTMLInputElement | null>(null);
  const [activeSection, setActiveSection] =
    useState<TradeJournalSection>("home");
  const [entries, setEntries] = useState<TradeJournalEntry[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<JournalForm>(() => emptyForm());
  const [performancePdf, setPerformancePdf] = useState<File | null>(null);
  const [ordersPdf, setOrdersPdf] = useState<File | null>(null);
  const [importPreview, setImportPreview] = useState<ImportPreview | null>(
    null,
  );
  const [importDrafts, setImportDrafts] = useState<ImportDraft[]>([]);
  const [activeDraftIndex, setActiveDraftIndex] = useState(0);
  const [draftStatuses, setDraftStatuses] = useState<
    Record<string, DraftStatus>
  >({});
  const [importWorkflowCollapsed, setImportWorkflowCollapsed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewingImport, setPreviewingImport] = useState(false);
  const [savingImportDraftId, setSavingImportDraftId] = useState<string | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
  const [coachReview, setCoachReview] = useState<TradingCoachReview | null>(
    null,
  );
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);
  const [correlationReview, setCorrelationReview] =
    useState<TradingCorrelationReview | null>(null);
  const [correlationLoading, setCorrelationLoading] = useState(false);
  const [correlationError, setCorrelationError] = useState<string | null>(null);
  const [patternReview, setPatternReview] =
    useState<PatternDiscoveryReview | null>(null);
  const [patternLoading, setPatternLoading] = useState(false);
  const [patternError, setPatternError] = useState<string | null>(null);
  const [calendarMonth, setCalendarMonth] = useState(() =>
    toMonthKey(new Date()),
  );
  const [performanceCalendar, setPerformanceCalendar] =
    useState<PerformanceCalendar | null>(null);
  const [calendarSource, setCalendarSource] =
    useState<CalendarSourceFilter>("all");
  const [calendarLoading, setCalendarLoading] = useState(false);
  const [calendarError, setCalendarError] = useState<string | null>(null);
  const [calendarRefreshKey, setCalendarRefreshKey] = useState(0);
  const [calendarImportPreview, setCalendarImportPreview] =
    useState<ImportPreview | null>(null);
  const [calendarPerformancePdf, setCalendarPerformancePdf] =
    useState<File | null>(null);
  const [calendarOrdersPdf, setCalendarOrdersPdf] = useState<File | null>(null);
  const [calendarImportLoading, setCalendarImportLoading] = useState(false);
  const [calendarImportSaving, setCalendarImportSaving] = useState(false);
  const [calendarImportError, setCalendarImportError] = useState<string | null>(
    null,
  );
  const [calendarImportResult, setCalendarImportResult] =
    useState<CalendarImportSaveResponse | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const selectedEntry = useMemo(
    () => entries.find((entry) => entry.id === selectedId) ?? entries[0] ?? null,
    [entries, selectedId],
  );
  const activeDraft = importDrafts[activeDraftIndex] ?? null;
  const importReviewComplete =
    importDrafts.length > 0 &&
    importDrafts.every(
      (draft) => (draftStatuses[draft.draft_id] ?? "pending") !== "pending",
    );
  const savedDraftCount = importDrafts.filter(
    (draft) => draftStatus(draft) === "saved",
  ).length;
  const skippedDraftCount = importDrafts.filter(
    (draft) => draftStatus(draft) === "skipped",
  ).length;
  const calendarCells = useMemo(
    () => buildCalendarCells(calendarMonth, performanceCalendar),
    [calendarMonth, performanceCalendar],
  );

  useEffect(() => {
    let mounted = true;

    async function loadEntries() {
      try {
        const response = await fetch(JOURNAL_URL, { cache: "no-store" });
        if (!response.ok) {
          throw new Error(`Trade Journal API returned ${response.status}.`);
        }
        const data = (await response.json()) as TradeJournalEntry[];

        if (!mounted) {
          return;
        }

        setEntries(data);
        setSelectedId(data[0]?.id ?? null);
      } catch (loadError) {
        if (!mounted) {
          return;
        }

        setError(
          loadError instanceof Error
            ? loadError.message
            : "Trade Journal could not be loaded.",
        );
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    }

    void loadEntries();

    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    if (activeSection !== "calendar") {
      return;
    }

    let mounted = true;

    async function loadCalendar() {
      setCalendarLoading(true);
      setCalendarError(null);

      try {
        const response = await fetch(
          `${PERFORMANCE_CALENDAR_URL}?month=${calendarMonth}&source=${calendarSource}`,
          { cache: "no-store" },
        );
        if (!response.ok) {
          throw new Error(`Performance calendar API returned ${response.status}.`);
        }
        const data = (await response.json()) as PerformanceCalendar;

        if (mounted) {
          setPerformanceCalendar(data);
        }
      } catch (loadError) {
        if (mounted) {
          setCalendarError(
            loadError instanceof Error
              ? loadError.message
              : "Performance calendar could not be loaded.",
          );
        }
      } finally {
        if (mounted) {
          setCalendarLoading(false);
        }
      }
    }

    void loadCalendar();

    return () => {
      mounted = false;
    };
  }, [activeSection, calendarMonth, calendarSource, calendarRefreshKey]);

  function updateForm<K extends keyof JournalForm>(
    key: K,
    value: JournalForm[K],
  ) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  function updateImportDraft<K extends keyof ImportDraft>(
    draftId: string,
    key: K,
    value: ImportDraft[K],
  ) {
    setImportDrafts((current) =>
      current.map((draft) =>
        draft.draft_id === draftId ? { ...draft, [key]: value } : draft,
      ),
    );
  }

  function getPreviousSavedDraft(index: number) {
    for (let currentIndex = index - 1; currentIndex >= 0; currentIndex -= 1) {
      const draft = importDrafts[currentIndex];
      if (draft && draftStatus(draft) === "saved") {
        return draft;
      }
    }

    return null;
  }

  function copyPreviousDraftInfo(index: number) {
    const active = importDrafts[index];
    const previous = getPreviousSavedDraft(index);

    if (!active || !previous) {
      return;
    }

    setImportDrafts((current) =>
      current.map((draft, draftIndex) =>
        draftIndex === index
          ? {
              ...draft,
              htf_bias: previous.htf_bias,
              draw_on_liquidity: [...previous.draw_on_liquidity],
              reaction_zone: previous.reaction_zone,
              behavior_tags: [...previous.behavior_tags],
              execution_tags: [...previous.execution_tags],
              why_taken: previous.why_taken,
              price_intent: previous.price_intent,
              liquidity_target: previous.liquidity_target,
              went_well: previous.went_well,
              went_wrong: previous.went_wrong,
              lesson_learned: previous.lesson_learned,
              screenshot_path: previous.screenshot_path,
              csv_path: previous.csv_path,
            }
          : draft,
      ),
    );
    setToast("Copied context from previous saved trade.");
  }

  function draftStatus(draft: ImportDraft): DraftStatus {
    return draftStatuses[draft.draft_id] ?? "pending";
  }

  function isDraftUnlocked(index: number) {
    if (index === 0) {
      return true;
    }

    return importDrafts
      .slice(0, index)
      .every((draft) => draftStatus(draft) !== "pending");
  }

  function moveToNextPendingDraft(fromIndex: number, nextStatuses = draftStatuses) {
    const nextIndex = importDrafts.findIndex(
      (draft, index) =>
        index > fromIndex && (nextStatuses[draft.draft_id] ?? "pending") === "pending",
    );

    if (nextIndex !== -1) {
      setActiveDraftIndex(nextIndex);
    }
  }

  function resetImportReview() {
    setImportPreview(null);
    setImportDrafts([]);
    setActiveDraftIndex(0);
    setDraftStatuses({});
    setImportWorkflowCollapsed(false);
  }

  function resetImportFiles() {
    setPerformancePdf(null);
    setOrdersPdf(null);
    setImportError(null);
    resetImportReview();
    if (performanceInputRef.current) {
      performanceInputRef.current.value = "";
    }
    if (ordersInputRef.current) {
      ordersInputRef.current.value = "";
    }
    setActiveSection("import");
  }

  function viewJournalAfterImport() {
    setImportWorkflowCollapsed(true);
    setImportError(null);
    setActiveSection("entries");
  }

  function handlePerformanceFileChange(file: File | null) {
    setPerformancePdf(file);
    resetImportReview();
    setImportError(null);
  }

  function handleOrdersFileChange(file: File | null) {
    setOrdersPdf(file);
    resetImportReview();
    setImportError(null);
  }

  function clearPerformancePdf() {
    setPerformancePdf(null);
    resetImportReview();
    setImportError(null);
    if (performanceInputRef.current) {
      performanceInputRef.current.value = "";
    }
  }

  function clearOrdersPdf() {
    setOrdersPdf(null);
    resetImportReview();
    setImportError(null);
    if (ordersInputRef.current) {
      ordersInputRef.current.value = "";
    }
  }

  function beginCreate() {
    setEditingId(null);
    setForm(emptyForm());
    setToast(null);
  }

  function beginEdit(entry: TradeJournalEntry) {
    setEditingId(entry.id);
    setSelectedId(entry.id);
    setForm(formFromEntry(entry));
    setToast(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError(null);

    try {
      const response = await fetch(
        editingId === null ? JOURNAL_URL : `${JOURNAL_URL}/${editingId}`,
        {
          method: editingId === null ? "POST" : "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(toPayload(form)),
        },
      );

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Save failed with ${response.status}.`);
      }

      const saved = (await response.json()) as TradeJournalEntry;
      setEntries((current) => {
        if (editingId === null) {
          return [saved, ...current];
        }
        return current.map((entry) => (entry.id === saved.id ? saved : entry));
      });
      setSelectedId(saved.id);
      setEditingId(null);
      setForm(emptyForm());
      setToast("Journal entry saved.");
      setCalendarRefreshKey((current) => current + 1);
      setActiveSection("entries");
    } catch (saveError) {
      setError(
        saveError instanceof Error
          ? saveError.message
          : "Journal entry could not be saved.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleImportPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!performancePdf && !ordersPdf) {
      setImportError("Add a Performance PDF, an Orders PDF, or both.");
      return;
    }

    setPreviewingImport(true);
    setImportError(null);

    try {
      const body = new FormData();
      if (performancePdf) {
        body.append("performance_pdf", performancePdf);
      }
      if (ordersPdf) {
        body.append("orders_pdf", ordersPdf);
      }

      const response = await fetch(IMPORT_URL, {
        method: "POST",
        body,
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Import preview failed with ${response.status}.`);
      }

      const preview = (await response.json()) as ImportPreview;
      const statuses = preview.trade_drafts.reduce<Record<string, DraftStatus>>(
        (nextStatuses, draft) => ({
          ...nextStatuses,
          [draft.draft_id]: "pending",
        }),
        {},
      );

      setImportPreview(preview);
      setImportDrafts(preview.trade_drafts);
      setActiveDraftIndex(0);
      setDraftStatuses(statuses);
      setImportWorkflowCollapsed(false);
      setToast("Import preview ready.");
    } catch (previewError) {
      setImportError(
        previewError instanceof Error
          ? previewError.message
          : "Import preview failed.",
      );
    } finally {
      setPreviewingImport(false);
    }
  }

  async function handleCalendarImportPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!calendarPerformancePdf && !calendarOrdersPdf) {
      setCalendarImportError("Add a Performance PDF, an Orders PDF, or both.");
      return;
    }

    setCalendarImportLoading(true);
    setCalendarImportError(null);
    setCalendarImportResult(null);

    try {
      const body = new FormData();
      if (calendarPerformancePdf) {
        body.append("performance_pdf", calendarPerformancePdf);
      }
      if (calendarOrdersPdf) {
        body.append("orders_pdf", calendarOrdersPdf);
      }

      const response = await fetch(IMPORT_URL, {
        method: "POST",
        body,
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Calendar import preview failed with ${response.status}.`);
      }

      const preview = (await response.json()) as ImportPreview;
      setCalendarImportPreview(preview);
      setToast("Calendar import preview ready.");
    } catch (previewError) {
      setCalendarImportError(
        previewError instanceof Error
          ? previewError.message
          : "Calendar import preview failed.",
      );
    } finally {
      setCalendarImportLoading(false);
    }
  }

  async function saveCalendarImport() {
    if (!calendarImportPreview) {
      setCalendarImportError("Preview calendar trades before importing.");
      return;
    }

    setCalendarImportSaving(true);
    setCalendarImportError(null);

    try {
      const response = await fetch(IMPORT_CALENDAR_SAVE_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trade_drafts: calendarImportPreview.trade_drafts.map((draft) => ({
            ...draft,
            selected: true,
          })),
          source_files: calendarImportPreview.source_files,
        }),
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Calendar import save failed with ${response.status}.`);
      }

      const result = (await response.json()) as CalendarImportSaveResponse;
      setCalendarImportResult(result);
      setCalendarRefreshKey((current) => current + 1);
      setToast(
        `Calendar import saved: ${result.imported} imported, ${result.skipped_duplicates} duplicate${
          result.skipped_duplicates === 1 ? "" : "s"
        } skipped.`,
      );
      if (result.warnings.length > 0) {
        setCalendarImportError(result.warnings.join(" "));
      }
    } catch (saveError) {
      setCalendarImportError(
        saveError instanceof Error
          ? saveError.message
          : "Calendar trades could not be saved.",
      );
    } finally {
      setCalendarImportSaving(false);
    }
  }

  async function saveImportDraft(draft: ImportDraft, index: number) {
    setImportError(null);
    setSavingImportDraftId(draft.draft_id);

    try {
      const response = await fetch(IMPORT_SAVE_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          trade_drafts: [{ ...draft, selected: true }],
        }),
      });

      if (!response.ok) {
        const message = await response.text();
        throw new Error(message || `Import save failed with ${response.status}.`);
      }

      const result = (await response.json()) as ImportSaveResponse;
      const nextStatuses = {
        ...draftStatuses,
        [draft.draft_id]: "saved" as DraftStatus,
      };

      setEntries((current) => [...result.created_entries, ...current]);
      setSelectedId(result.created_entries[0]?.id ?? selectedId);
      setDraftStatuses(nextStatuses);
      setToast("Imported 1 journal entry.");
      setCalendarRefreshKey((current) => current + 1);
      moveToNextPendingDraft(index, nextStatuses);
      if (result.warnings.length > 0) {
        setImportError(result.warnings.join(" "));
      }
    } catch (saveError) {
      setImportError(
        saveError instanceof Error
          ? saveError.message
          : "Import drafts could not be saved.",
      );
    } finally {
      setSavingImportDraftId(null);
    }
  }

  function skipImportDraft(draft: ImportDraft, index: number) {
    const nextStatuses = {
      ...draftStatuses,
      [draft.draft_id]: "skipped" as DraftStatus,
    };

    setImportError(null);
    setDraftStatuses(nextStatuses);
    setToast(`Skipped Trade ${index + 1}.`);
    moveToNextPendingDraft(index, nextStatuses);
  }

  async function handleDelete(entryId: number) {
    const confirmed = window.confirm("Delete this trade journal entry?");
    if (!confirmed) {
      return;
    }

    setError(null);
    try {
      const response = await fetch(`${JOURNAL_URL}/${entryId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`Delete failed with ${response.status}.`);
      }
      setEntries((current) => current.filter((entry) => entry.id !== entryId));
      setSelectedId((current) => (current === entryId ? null : current));
      if (editingId === entryId) {
        beginCreate();
      }
      setToast("Journal entry deleted.");
      setCalendarRefreshKey((current) => current + 1);
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Journal entry could not be deleted.",
      );
    }
  }

  async function handleTradingCoachReview() {
    setReviewLoading(true);
    setReviewError(null);

    try {
      const response = await fetch(TRADING_COACH_REVIEW_URL, {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Trading Coach API returned ${response.status}.`);
      }

      const review = (await response.json()) as TradingCoachReview;
      setCoachReview(review);
    } catch (reviewLoadError) {
      setReviewError(
        reviewLoadError instanceof Error
          ? reviewLoadError.message
          : "Trading Coach review could not be loaded.",
      );
    } finally {
      setReviewLoading(false);
    }
  }

  async function handleTradingCorrelationReview() {
    setCorrelationLoading(true);
    setCorrelationError(null);

    try {
      const response = await fetch(TRADING_CORRELATION_REVIEW_URL, {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Scanner Correlation API returned ${response.status}.`);
      }

      const review = (await response.json()) as TradingCorrelationReview;
      setCorrelationReview(review);
    } catch (reviewLoadError) {
      setCorrelationError(
        reviewLoadError instanceof Error
          ? reviewLoadError.message
          : "Scanner Correlation review could not be loaded.",
      );
    } finally {
      setCorrelationLoading(false);
    }
  }

  async function handlePatternDiscoveryReview() {
    setPatternLoading(true);
    setPatternError(null);

    try {
      const response = await fetch(PATTERN_DISCOVERY_REVIEW_URL, {
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`Pattern Discovery API returned ${response.status}.`);
      }

      const review = (await response.json()) as PatternDiscoveryReview;
      setPatternReview(review);
    } catch (reviewLoadError) {
      setPatternError(
        reviewLoadError instanceof Error
          ? reviewLoadError.message
          : "Pattern Discovery review could not be loaded.",
      );
    } finally {
      setPatternLoading(false);
    }
  }

  return (
    <main className="min-h-screen overflow-x-hidden bg-[#05070b] text-white">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-[#05070b]/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-3 px-3 py-3 sm:flex-row sm:items-center sm:justify-between sm:px-4 sm:py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300">
              Orbit
            </p>
            <h1 className="mt-1 text-xl font-semibold tracking-tight">
              Trade Journal
            </h1>
          </div>

          <nav className="-mx-1 flex max-w-full gap-2 overflow-x-auto px-1 pb-1 sm:flex-wrap sm:overflow-visible sm:pb-0">
            <Link
              href="/"
              className="shrink-0 rounded-lg border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Core
            </Link>
            <Link
              href="/command-center"
              className="shrink-0 rounded-lg border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Command Center
            </Link>
            <Link
              href="/orbit"
              className="shrink-0 rounded-lg border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Orbit
            </Link>
          </nav>
        </div>
      </header>

      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-3 pt-3 sm:flex-row sm:items-center sm:justify-between sm:px-4 sm:pt-4">
        <div className="-mx-1 flex max-w-full gap-2 overflow-x-auto rounded-lg border border-white/10 bg-neutral-900/80 p-1 sm:mx-0 sm:flex-wrap sm:overflow-visible">
          {sectionNavItems.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => {
                setActiveSection(item.id);
                if (item.id === "import") {
                  setImportWorkflowCollapsed(false);
                }
                if (item.id === "manual") {
                  beginCreate();
                }
              }}
              className={`shrink-0 rounded-md px-3 py-2.5 text-xs font-semibold transition sm:py-2 sm:text-sm ${
                activeSection === item.id
                  ? "bg-cyan-300 text-slate-950"
                  : "text-neutral-300 hover:bg-white/10 hover:text-white"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={() => setActiveSection("entries")}
          className="rounded-lg border border-cyan-300/30 bg-cyan-300/10 px-4 py-3 text-center text-sm font-semibold text-cyan-100 transition hover:bg-cyan-300/20 sm:py-2"
        >
          Actual Trades
        </button>
      </div>

      <div className="mx-auto grid max-w-7xl gap-3 px-3 py-3 sm:gap-4 sm:px-4 sm:py-4">
        {toast ? (
          <div className="rounded-lg border border-emerald-400/25 bg-emerald-400/10 px-4 py-3 text-sm text-emerald-100">
            {toast}
          </div>
        ) : null}

        {error ? (
          <div className="rounded-lg border border-red-500/30 bg-red-950/20 px-4 py-3 text-sm text-red-100">
            {error}
          </div>
        ) : null}

        {activeSection === "home" ? (
        <section className="space-y-4">
          <div className="rounded-lg border border-cyan-300/20 bg-cyan-300/5 p-4 sm:p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm text-cyan-100/80">
                  Data capture foundation
                </p>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight">
                  Trade Journal
                </h2>
                <p className="mt-2 max-w-2xl text-sm leading-6 text-neutral-300">
                  Capture trades, review execution quality, and keep the coaching
                  rooms close without stacking every workflow on one screen.
                </p>
              </div>
              <button
                type="button"
                onClick={() => setActiveSection("entries")}
                className="rounded-lg border border-cyan-300/30 bg-cyan-300/10 px-4 py-3 text-center text-sm font-semibold text-cyan-100 transition hover:bg-cyan-300/20 sm:py-2"
              >
                View Journal Entries
              </button>
            </div>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <button
              type="button"
              onClick={() => {
                setImportWorkflowCollapsed(false);
                setActiveSection("import");
              }}
              className="rounded-lg border border-white/10 bg-neutral-900/80 p-4 text-left transition hover:border-cyan-300/40 hover:bg-cyan-300/10"
            >
              <p className="text-xs text-neutral-500">Workflow</p>
              <h3 className="mt-1 text-base font-semibold text-white">
                Import Trades
              </h3>
              <p className="mt-2 text-sm leading-6 text-neutral-400">
                Preview PDFs and save each draft into the journal.
              </p>
            </button>
            <button
              type="button"
              onClick={() => {
                beginCreate();
                setActiveSection("manual");
              }}
              className="rounded-lg border border-white/10 bg-neutral-900/80 p-4 text-left transition hover:border-cyan-300/40 hover:bg-cyan-300/10"
            >
              <p className="text-xs text-neutral-500">Workflow</p>
              <h3 className="mt-1 text-base font-semibold text-white">
                Manual Entry
              </h3>
              <p className="mt-2 text-sm leading-6 text-neutral-400">
                Create a journal entry directly from your trade context.
              </p>
            </button>
            <button
              type="button"
              onClick={() => setActiveSection("entries")}
              className="rounded-lg border border-white/10 bg-neutral-900/80 p-4 text-left transition hover:border-cyan-300/40 hover:bg-cyan-300/10"
            >
              <p className="text-xs text-neutral-500">Actual Trades</p>
              <h3 className="mt-1 text-base font-semibold text-white">
                View Journal Entries
              </h3>
              <p className="mt-2 text-sm leading-6 text-neutral-400">
                {entries.length} saved trade{entries.length === 1 ? "" : "s"}.
              </p>
            </button>
            <button
              type="button"
              onClick={() => setActiveSection("calendar")}
              className="rounded-lg border border-white/10 bg-neutral-900/80 p-4 text-left transition hover:border-cyan-300/40 hover:bg-cyan-300/10"
            >
              <p className="text-xs text-neutral-500">Performance</p>
              <h3 className="mt-1 text-base font-semibold text-white">
                Profit Calendar
              </h3>
              <p className="mt-2 text-sm leading-6 text-neutral-400">
                Review daily PnL, trade count, and win/loss days by month.
              </p>
            </button>
          </div>

          <div className="grid gap-3 lg:grid-cols-3">
            <section className="rounded-lg border border-white/10 bg-neutral-900/80 p-4">
              <p className="text-xs text-neutral-500">Trading Coach Review</p>
              <h3 className="mt-1 text-base font-semibold text-white">
                Model Alignment
              </h3>
              <p className="mt-2 text-sm leading-6 text-neutral-400">
                Review saved entries against Liquidity Narrative Continuation.
              </p>
              <button
                type="button"
                onClick={() => setActiveSection("coach")}
                className="mt-3 rounded-lg bg-cyan-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 sm:py-2"
              >
                Open Coach
              </button>
            </section>
            <section className="rounded-lg border border-white/10 bg-neutral-900/80 p-4">
              <p className="text-xs text-neutral-500">Scanner + Journal Review</p>
              <h3 className="mt-1 text-base font-semibold text-white">
                Scanner Match
              </h3>
              <p className="mt-2 text-sm leading-6 text-neutral-400">
                Compare journal entries with nearby scanner context.
              </p>
              <button
                type="button"
                onClick={() => setActiveSection("scanner")}
                className="mt-3 rounded-lg bg-cyan-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 sm:py-2"
              >
                Open Scanner Match
              </button>
            </section>
            <section className="rounded-lg border border-white/10 bg-neutral-900/80 p-4">
              <p className="text-xs text-neutral-500">Pattern Discovery</p>
              <h3 className="mt-1 text-base font-semibold text-white">
                Early Patterns
              </h3>
              <p className="mt-2 text-sm leading-6 text-neutral-400">
                Look for recurring behavior in the saved trading record.
              </p>
              <button
                type="button"
                onClick={() => setActiveSection("patterns")}
                className="mt-3 rounded-lg bg-cyan-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 sm:py-2"
              >
                Open Patterns
              </button>
            </section>
          </div>
        </section>
        ) : null}

        {activeSection === "calendar" ? (
          <section className="rounded-lg border border-white/10 bg-neutral-900/80 p-3 sm:p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs text-neutral-500">Profit Calendar</p>
                <h2 className="mt-1 text-lg font-semibold text-white">
                  {formatMonthLabel(calendarMonth)}
                </h2>
              </div>
              <div className="flex flex-wrap gap-2">
                {[
                  ["all", "All"],
                  ["journal", "Journal Entries"],
                  ["calendar_only", "Calendar Only"],
                ].map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setCalendarSource(value as CalendarSourceFilter)}
                    className={`rounded-lg border px-3 py-2 text-xs font-semibold transition ${
                      calendarSource === value
                        ? "border-cyan-300/60 bg-cyan-300 text-slate-950"
                        : "border-white/10 text-neutral-100 hover:bg-white/10"
                    }`}
                  >
                    {label}
                  </button>
                ))}
                <button
                  type="button"
                  onClick={() => setCalendarMonth(shiftMonth(calendarMonth, -1))}
                  className="rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold text-neutral-100 transition hover:bg-white/10"
                >
                  Previous
                </button>
                <button
                  type="button"
                  onClick={() => setCalendarMonth(toMonthKey(new Date()))}
                  className="rounded-lg border border-cyan-300/30 bg-cyan-300/10 px-3 py-2 text-xs font-semibold text-cyan-100 transition hover:bg-cyan-300/20"
                >
                  Today
                </button>
                <button
                  type="button"
                  onClick={() => setCalendarMonth(shiftMonth(calendarMonth, 1))}
                  className="rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold text-neutral-100 transition hover:bg-white/10"
                >
                  Next
                </button>
              </div>
            </div>

            {calendarError ? (
              <div className="mt-3 rounded-lg border border-red-500/30 bg-red-950/20 px-3 py-2 text-sm text-red-100">
                {calendarError}
              </div>
            ) : null}

            <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-6">
              <DetailRow
                label="Month PnL"
                value={
                  <span
                    className={resultClass(
                      performanceCalendar?.summary.total_pnl ?? null,
                    )}
                  >
                    {formatCurrency(performanceCalendar?.summary.total_pnl ?? null)}
                  </span>
                }
              />
              <DetailRow
                label="Total Trades"
                value={performanceCalendar?.summary.trade_count ?? "--"}
              />
              <DetailRow
                label="Winning Days"
                value={performanceCalendar?.summary.winning_days ?? "--"}
              />
              <DetailRow
                label="Losing Days"
                value={performanceCalendar?.summary.losing_days ?? "--"}
              />
              <DetailRow
                label="Best Day"
                value={
                  performanceCalendar?.summary.best_day
                    ? `${performanceCalendar.summary.best_day.date} ${formatCurrency(
                        performanceCalendar.summary.best_day.pnl,
                      )}`
                    : "--"
                }
              />
              <DetailRow
                label="Worst Day"
                value={
                  performanceCalendar?.summary.worst_day
                    ? `${performanceCalendar.summary.worst_day.date} ${formatCurrency(
                        performanceCalendar.summary.worst_day.pnl,
                      )}`
                    : "--"
                }
              />
            </div>

            <section className="mt-4 rounded-lg border border-cyan-300/20 bg-cyan-300/5 p-3">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div>
                  <p className="text-xs text-cyan-100/80">Calendar PnL Only</p>
                  <h3 className="mt-1 text-base font-semibold text-white">
                    Import Calendar Trades
                  </h3>
                  <p className="mt-2 max-w-2xl text-sm leading-6 text-neutral-300">
                    Calendar PnL imports are for performance tracking only. They
                    will not be used for strategy coaching unless promoted later.
                  </p>
                </div>
                {calendarImportResult ? (
                  <div className="rounded-lg border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-neutral-300">
                    {calendarImportResult.imported} imported •{" "}
                    {calendarImportResult.skipped_duplicates} duplicate
                    {calendarImportResult.skipped_duplicates === 1 ? "" : "s"}{" "}
                    skipped
                  </div>
                ) : null}
              </div>

              <form
                onSubmit={(event) => void handleCalendarImportPreview(event)}
                className="mt-3 grid gap-3 lg:grid-cols-[1fr_1fr_auto]"
              >
                <PdfFilePicker
                  label="Performance PDF"
                  file={calendarPerformancePdf}
                  inputRef={calendarPerformanceInputRef}
                  onChange={(file) => {
                    setCalendarPerformancePdf(file);
                    setCalendarImportPreview(null);
                    setCalendarImportResult(null);
                    setCalendarImportError(null);
                  }}
                  onClear={() => {
                    setCalendarPerformancePdf(null);
                    setCalendarImportPreview(null);
                    setCalendarImportResult(null);
                    setCalendarImportError(null);
                    if (calendarPerformanceInputRef.current) {
                      calendarPerformanceInputRef.current.value = "";
                    }
                  }}
                />
                <PdfFilePicker
                  label="Orders PDF"
                  file={calendarOrdersPdf}
                  inputRef={calendarOrdersInputRef}
                  onChange={(file) => {
                    setCalendarOrdersPdf(file);
                    setCalendarImportPreview(null);
                    setCalendarImportResult(null);
                    setCalendarImportError(null);
                  }}
                  onClear={() => {
                    setCalendarOrdersPdf(null);
                    setCalendarImportPreview(null);
                    setCalendarImportResult(null);
                    setCalendarImportError(null);
                    if (calendarOrdersInputRef.current) {
                      calendarOrdersInputRef.current.value = "";
                    }
                  }}
                />
                <button
                  type="submit"
                  disabled={calendarImportLoading}
                  className="self-end rounded-lg border border-cyan-300/30 bg-cyan-300/10 px-4 py-3 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-50 lg:py-2"
                >
                  {calendarImportLoading ? "Previewing..." : "Preview"}
                </button>
              </form>

              {calendarImportError ? (
                <div className="mt-3 rounded-lg border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">
                  {calendarImportError}
                </div>
              ) : null}

              {calendarImportPreview ? (
                <div className="mt-3 rounded-lg border border-white/10 bg-neutral-950 p-3">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <p className="text-xs text-neutral-500">
                        {calendarImportPreview.trade_drafts.length} calendar trade
                        {calendarImportPreview.trade_drafts.length === 1
                          ? ""
                          : "s"}{" "}
                        ready
                      </p>
                      <p className="mt-1 text-sm font-semibold text-neutral-100">
                        Preview PnL{" "}
                        {formatCurrency(
                          calendarImportPreview.trade_drafts.reduce(
                            (total, draft) => total + (draft.pnl ?? 0),
                            0,
                          ),
                        )}
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => void saveCalendarImport()}
                      disabled={
                        calendarImportSaving ||
                        calendarImportPreview.trade_drafts.length === 0
                      }
                      className="rounded-lg bg-cyan-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50 sm:py-2"
                    >
                      {calendarImportSaving ? "Importing..." : "Import Calendar PnL"}
                    </button>
                  </div>
                </div>
              ) : null}
            </section>

            <div className="mt-4 overflow-auto rounded-lg border border-white/10 bg-neutral-950 p-2">
              <div className="grid min-w-[720px] grid-cols-7 gap-2">
                {["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => (
                  <div
                    key={day}
                    className="px-2 py-1 text-xs font-semibold uppercase text-neutral-500"
                  >
                    {day}
                  </div>
                ))}

                {calendarLoading ? (
                  <div className="col-span-7 rounded-lg border border-white/10 bg-white/[0.03] p-6 text-center text-sm text-neutral-400">
                    Loading calendar...
                  </div>
                ) : (
                  calendarCells.map((cell, index) => {
                    const performance = cell.performance;
                    if (cell.date === null) {
                      return (
                        <div
                          key={`placeholder-${index}`}
                          className="min-h-28"
                          aria-hidden="true"
                        />
                      );
                    }
                    return (
                      <div
                        key={cell.date}
                        className={`min-h-28 rounded-lg border p-2 ${calendarCellClass(
                          cell,
                        )}`}
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-sm font-semibold text-neutral-100">
                            {cell.dayNumber}
                          </span>
                          {performance?.symbols.length ? (
                            <span className="truncate text-[11px] font-semibold text-neutral-500">
                              {performance.symbols.join(", ")}
                            </span>
                          ) : null}
                        </div>
                        <div className="mt-4">
                          {performance ? (
                            <>
                              <p
                                className={`text-sm font-semibold ${resultClass(
                                  performance.total_pnl,
                                )}`}
                              >
                                {formatCurrency(performance.total_pnl)}
                              </p>
                              <p className="mt-1 text-xs text-neutral-400">
                                {performance.trade_count}{" "}
                                {performance.trade_count === 1
                                  ? "Trade"
                                  : "Trades"}
                              </p>
                              <p className="mt-2 text-[11px] text-neutral-500">
                                {performance.win_count}W / {performance.loss_count}L
                              </p>
                            </>
                          ) : (
                            <p className="text-xs text-neutral-600">No trades</p>
                          )}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          </section>
        ) : null}

        {activeSection === "coach" ? (
          <section className="rounded-lg border border-white/10 bg-neutral-900/80 p-3 sm:p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs text-neutral-500">Trading Coach</p>
                <h2 className="mt-1 text-lg font-semibold text-white">
                  Journal Review
                </h2>
              </div>
              <button
                type="button"
                onClick={() => void handleTradingCoachReview()}
                disabled={reviewLoading}
                className="rounded-lg border border-cyan-300/30 bg-cyan-300/10 px-4 py-3 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-50 sm:py-2"
              >
                {reviewLoading ? "Reviewing..." : "Review Trades"}
              </button>
            </div>

            {reviewError ? (
              <div className="mt-3 rounded-lg border border-red-500/30 bg-red-950/20 px-3 py-2 text-sm text-red-100">
                {reviewError}
              </div>
            ) : null}

            {coachReview ? (
              <div className="mt-4 grid gap-3">
                <div className="grid gap-2 sm:grid-cols-3">
                  <DetailRow
                    label="Trades reviewed"
                    value={coachReview.summary.total_trades_reviewed}
                  />
                  <DetailRow
                    label="Model alignment"
                    value={`${coachReview.model_alignment.label} (${coachReview.model_alignment.score}%)`}
                  />
                  <DetailRow
                    label="Average PnL"
                    value={formatCurrency(coachReview.summary.average_pnl)}
                  />
                </div>

                {coachReview.summary.total_trades_reviewed === 0 ? (
                  <p className="rounded-lg border border-white/10 bg-neutral-950 p-3 text-sm text-neutral-300">
                    No journal entries available yet. Import or create trades first.
                  </p>
                ) : (
                  <div className="grid gap-3 lg:grid-cols-2">
                    <ReviewList title="Strengths" values={coachReview.strengths} />
                    <ReviewList title="Weaknesses" values={coachReview.weaknesses} />
                    <ReviewList
                      title="Suggested Focus"
                      values={coachReview.suggested_focus}
                    />
                    <ReviewList
                      title="Missing Data"
                      values={coachReview.missing_data}
                    />
                  </div>
                )}
              </div>
            ) : (
              <p className="mt-3 text-sm leading-6 text-neutral-400">
                Run a read-only review of recent journal entries against Liquidity
                Narrative Continuation.
              </p>
            )}
          </section>

        ) : null}

        {activeSection === "scanner" ? (
          <section className="rounded-lg border border-white/10 bg-neutral-900/80 p-3 sm:p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs text-neutral-500">Scanner Correlation</p>
                <h2 className="mt-1 text-lg font-semibold text-white">
                  Scanner + Journal Review
                </h2>
              </div>
              <button
                type="button"
                onClick={() => void handleTradingCorrelationReview()}
                disabled={correlationLoading}
                className="rounded-lg border border-cyan-300/30 bg-cyan-300/10 px-4 py-3 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-50 sm:py-2"
              >
                {correlationLoading ? "Reviewing..." : "Review Scanner Match"}
              </button>
            </div>

            {correlationError ? (
              <div className="mt-3 rounded-lg border border-red-500/30 bg-red-950/20 px-3 py-2 text-sm text-red-100">
                {correlationError}
              </div>
            ) : null}

            {correlationReview ? (
              <div className="mt-4 grid gap-3">
                <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
                  <DetailRow
                    label="Trades"
                    value={correlationReview.summary.trades_reviewed}
                  />
                  <DetailRow
                    label="Matched scans"
                    value={correlationReview.summary.trades_with_scan_match}
                  />
                  <DetailRow
                    label="Aligned"
                    value={correlationReview.summary.aligned_count}
                  />
                  <DetailRow
                    label="Partial"
                    value={correlationReview.summary.partially_aligned_count}
                  />
                  <DetailRow
                    label="Conflicted"
                    value={correlationReview.summary.conflicted_count}
                  />
                  <DetailRow
                    label="Insufficient"
                    value={correlationReview.summary.insufficient_data_count}
                  />
                </div>

                <div className="grid gap-3 lg:grid-cols-2">
                  <ReviewList
                    title="Common Mismatches"
                    values={
                      correlationReview.summary.common_mismatches.length > 0
                        ? correlationReview.summary.common_mismatches.map(
                            (item) => `${item.reason} (${item.count})`,
                          )
                        : correlationReview.suggested_data_to_capture
                    }
                  />
                  <section className="rounded-lg border border-white/10 bg-neutral-950 p-3">
                    <h3 className="text-xs font-semibold uppercase text-neutral-500">
                      Recent Correlated Trades
                    </h3>
                    {correlationReview.correlations.length === 0 ? (
                      <p className="mt-2 text-sm leading-6 text-neutral-400">
                        {correlationReview.readable_summary}
                      </p>
                    ) : (
                      <div className="mt-2 grid gap-2">
                        {correlationReview.correlations.slice(0, 5).map((item) => (
                          <div
                            key={item.journal_entry_id}
                            className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-neutral-300"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <span className="font-semibold text-neutral-100">
                                {item.symbol} {item.direction}
                              </span>
                              <span className="text-xs capitalize text-cyan-100">
                                {item.alignment_label.replaceAll("_", " ")}
                              </span>
                            </div>
                            <p className="mt-1 text-xs text-neutral-500">
                              {item.trade_date} • {item.match_confidence} match •{" "}
                              {item.scanner_narrative_phase?.replaceAll("_", " ") ??
                                "no scanner phase"}{" "}
                              • {item.scanner_signal_level ?? "no signal"}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </section>
                </div>
              </div>
            ) : (
              <p className="mt-3 text-sm leading-6 text-neutral-400">
                Compare recent journal entries against nearby scanner records.
              </p>
            )}
          </section>

        ) : null}

        {activeSection === "patterns" ? (
          <section className="rounded-lg border border-white/10 bg-neutral-900/80 p-3 sm:p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs text-neutral-500">Pattern Discovery</p>
                <h2 className="mt-1 text-lg font-semibold text-white">
                  Trade Pattern Review
                </h2>
              </div>
              <button
                type="button"
                onClick={() => void handlePatternDiscoveryReview()}
                disabled={patternLoading}
                className="rounded-lg border border-cyan-300/30 bg-cyan-300/10 px-4 py-3 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-50 sm:py-2"
              >
                {patternLoading ? "Reviewing..." : "Find Patterns"}
              </button>
            </div>

            {patternError ? (
              <div className="mt-3 rounded-lg border border-red-500/30 bg-red-950/20 px-3 py-2 text-sm text-red-100">
                {patternError}
              </div>
            ) : null}

            {patternReview ? (
              <div className="mt-4 grid gap-3">
                <div className="grid gap-2 sm:grid-cols-3">
                  <DetailRow
                    label="Trades reviewed"
                    value={patternReview.summary.trades_reviewed}
                  />
                  <DetailRow
                    label="Pattern confidence"
                    value={patternReview.pattern_confidence}
                  />
                  <DetailRow
                    label="Average PnL"
                    value={formatCurrency(patternReview.summary.average_pnl)}
                  />
                </div>

                {patternReview.sample_size_warning ? (
                  <p className="rounded-lg border border-amber-400/25 bg-amber-400/10 p-3 text-sm leading-6 text-amber-100">
                    {patternReview.sample_size_warning}
                  </p>
                ) : null}

                {patternReview.summary.trades_reviewed === 0 ? (
                  <p className="rounded-lg border border-white/10 bg-neutral-950 p-3 text-sm text-neutral-300">
                    {patternReview.readable_summary}
                  </p>
                ) : (
                  <div className="grid gap-3 lg:grid-cols-2">
                    <ReviewList
                      title="Recurring Strengths"
                      values={patternReview.recurring_strengths}
                    />
                    <ReviewList
                      title="Recurring Weaknesses"
                      values={patternReview.recurring_weaknesses}
                    />
                    <ReviewList
                      title="Profitable Contexts"
                      values={
                        patternReview.profitable_contexts.length > 0
                          ? patternReview.profitable_contexts
                          : patternReview.missing_data_patterns.slice(0, 4)
                      }
                    />
                    <ReviewList
                      title="Weak Contexts"
                      values={
                        patternReview.weak_contexts.length > 0
                          ? patternReview.weak_contexts
                          : patternReview.missing_data_patterns.slice(0, 4)
                      }
                    />
                    <ReviewList
                      title="Next Questions"
                      values={patternReview.suggested_next_review_questions}
                    />
                  </div>
                )}
              </div>
            ) : (
              <p className="mt-3 text-sm leading-6 text-neutral-400">
                Look for early recurring patterns in saved trades and scanner
                correlation.
              </p>
            )}
          </section>

        ) : null}

          {activeSection === "import" && !importWorkflowCollapsed ? (
          <section className="rounded-lg border border-white/10 bg-neutral-900/80 p-3 sm:p-4">
            {importReviewComplete ? (
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="text-xs text-emerald-300">Import complete</p>
                  <h2 className="mt-1 text-lg font-semibold text-white">
                    {`Import complete — ${importDrafts.length} trade${
                      importDrafts.length === 1 ? "" : "s"
                    } processed.`}
                  </h2>
                  <p className="mt-2 text-sm text-neutral-400">
                    {savedDraftCount} saved, {skippedDraftCount} skipped.
                  </p>
                </div>
                <div className="flex flex-col gap-2 sm:flex-row">
                  <button
                    type="button"
                    onClick={resetImportFiles}
                    className="rounded-lg bg-cyan-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 sm:py-2"
                  >
                    New Import
                  </button>
                  <button
                    type="button"
                    onClick={viewJournalAfterImport}
                    className="rounded-lg border border-white/10 px-4 py-3 text-sm font-semibold text-neutral-100 transition hover:bg-white/10 sm:py-2"
                  >
                    View Journal
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-xs text-neutral-500">Import Trades</p>
                    <h2 className="mt-1 text-lg font-semibold text-white">
                      PDF Import Preview
                    </h2>
                  </div>
                  {importDrafts.length > 0 ? (
                    <p className="rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold text-neutral-300">
                      Trade {Math.min(activeDraftIndex + 1, importDrafts.length)} of{" "}
                      {importDrafts.length}
                    </p>
                  ) : null}
                </div>

                <form
                  onSubmit={(event) => void handleImportPreview(event)}
                  className="mt-4 grid gap-3"
                >
                  <div className="grid gap-3 sm:grid-cols-2">
                    <PdfFilePicker
                      label="Performance PDF"
                      file={performancePdf}
                      inputRef={performanceInputRef}
                      onChange={handlePerformanceFileChange}
                      onClear={clearPerformancePdf}
                    />
                    <PdfFilePicker
                      label="Orders PDF"
                      file={ordersPdf}
                      inputRef={ordersInputRef}
                      onChange={handleOrdersFileChange}
                      onClear={clearOrdersPdf}
                    />
                  </div>
                  <button
                    type="submit"
                    disabled={previewingImport}
                    className="rounded-lg border border-cyan-300/30 bg-cyan-300/10 px-4 py-3 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-50 sm:py-2"
                  >
                    {previewingImport ? "Previewing..." : "Preview Import"}
                  </button>
                </form>
              </>
            )}

            {importError ? (
              <div className="mt-3 rounded-lg border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">
                {importError}
              </div>
            ) : null}

            {importPreview && !importReviewComplete ? (
              <div className="mt-4 space-y-3">
                <div className="rounded-lg border border-white/10 bg-neutral-950 p-3">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs text-neutral-500">Daily Summary</p>
                      <h3 className="mt-1 text-sm font-semibold text-neutral-100">
                        {importPreview.source_files.performance_pdf ??
                          "Orders-only preview"}
                      </h3>
                    </div>
                    <p className="text-xs text-neutral-500">
                      {importDrafts.length} draft
                      {importDrafts.length === 1 ? "" : "s"}
                    </p>
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-2">
                    <DetailRow
                      label="Gross PnL"
                      value={formatCurrency(importPreview.daily_summary.gross_pnl)}
                    />
                    <DetailRow
                      label="Total PnL"
                      value={formatCurrency(importPreview.daily_summary.total_pnl)}
                    />
                    <DetailRow
                      label="Fees / Commissions"
                      value={formatCurrency(
                        importPreview.daily_summary.fees_commissions,
                      )}
                    />
                    <DetailRow
                      label="Trade Count"
                      value={formatNumber(importPreview.daily_summary.trade_count)}
                    />
                    <DetailRow
                      label="Contract Count"
                      value={formatNumber(
                        importPreview.daily_summary.contract_count,
                      )}
                    />
                    <DetailRow
                      label="Win Rate"
                      value={formatPercent(importPreview.daily_summary.win_rate)}
                    />
                    <DetailRow
                      label="Expectancy"
                      value={formatCurrency(importPreview.daily_summary.expectancy)}
                    />
                    <DetailRow
                      label="Average Trade Time"
                      value={importPreview.daily_summary.average_trade_time ?? "--"}
                    />
                    <DetailRow
                      label="Longest Trade Time"
                      value={importPreview.daily_summary.longest_trade_time ?? "--"}
                    />
                  </div>
                </div>

                {importPreview.warnings.length > 0 ? (
                  <div className="rounded-lg border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">
                    {importPreview.warnings.join(" ")}
                  </div>
                ) : null}

                {importDrafts.length > 0 ? (
                  <div className="rounded-lg border border-white/10 bg-neutral-950 p-3">
                    <div className="flex flex-wrap gap-2">
                      {importDrafts.map((draft, index) => {
                        const status = draftStatus(draft);
                        const unlocked = isDraftUnlocked(index);
                        const isActive = activeDraftIndex === index;

                        return (
                          <button
                            key={draft.draft_id}
                            type="button"
                            disabled={!unlocked}
                            onClick={() => setActiveDraftIndex(index)}
                            className={`min-w-0 rounded-lg border px-3 py-2 text-left transition ${
                              isActive
                                ? "border-cyan-300/60 bg-cyan-300/10"
                                : "border-white/10 bg-white/[0.03] hover:border-white/25"
                            } disabled:cursor-not-allowed disabled:opacity-45`}
                          >
                            <span className="block truncate text-xs font-semibold text-neutral-100">
                              Trade {index + 1}: {draft.direction}{" "}
                              {formatCurrency(draft.pnl)}
                            </span>
                            <span
                              className={`mt-1 block text-[11px] capitalize ${
                                status === "saved"
                                  ? "text-emerald-300"
                                  : status === "skipped"
                                    ? "text-amber-300"
                                    : "text-neutral-500"
                              }`}
                            >
                              {unlocked ? status : "locked"}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ) : null}

                {activeDraft ? (
                  <article className="rounded-lg border border-white/10 bg-neutral-950 p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <p className="text-xs font-semibold text-neutral-400">
                          Active Trade Draft
                        </p>
                        <h3 className="mt-2 text-base font-semibold text-white">
                          Trade {activeDraftIndex + 1}: {activeDraft.symbol}{" "}
                          {activeDraft.direction}
                        </h3>
                        <p className="mt-1 text-sm text-neutral-400">
                          {formatNumber(activeDraft.entry_price)} -&gt;{" "}
                          {formatNumber(activeDraft.exit_price)}
                        </p>
                      </div>
                      <p className="rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold capitalize text-neutral-300">
                        {draftStatus(activeDraft)}
                      </p>
                    </div>

                    {activeDraftIndex > 0 ? (
                      <div className="mt-3 flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={() => copyPreviousDraftInfo(activeDraftIndex)}
                          disabled={
                            draftStatus(activeDraft) !== "pending" ||
                            getPreviousSavedDraft(activeDraftIndex) === null
                          }
                          className="rounded-lg border border-cyan-300/30 bg-cyan-300/10 px-3 py-2 text-xs font-semibold text-cyan-100 transition hover:bg-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Copy Previous Info
                        </button>
                      </div>
                    ) : null}

                    <div className="mt-3 flex flex-wrap gap-2">
                      <span className="rounded-md border border-white/10 px-2 py-1 text-xs text-neutral-300">
                        Direction {activeDraft.direction}
                      </span>
                      {activeDraft.stop_detected ? (
                        <span className="rounded-md border border-amber-300/30 bg-amber-300/10 px-2 py-1 text-xs text-amber-100">
                          Stop detected
                        </span>
                      ) : null}
                      {activeDraft.stop_canceled ? (
                        <span className="rounded-md border border-red-300/30 bg-red-300/10 px-2 py-1 text-xs text-red-100">
                          Stop canceled
                        </span>
                      ) : null}
                      {activeDraft.market_entry ? (
                        <span className="rounded-md border border-cyan-300/30 bg-cyan-300/10 px-2 py-1 text-xs text-cyan-100">
                          Market entry
                        </span>
                      ) : null}
                      {activeDraft.market_exit ? (
                        <span className="rounded-md border border-cyan-300/30 bg-cyan-300/10 px-2 py-1 text-xs text-cyan-100">
                          Market exit
                        </span>
                      ) : null}
                      {activeDraft.limit_entry ? (
                        <span className="rounded-md border border-emerald-300/30 bg-emerald-300/10 px-2 py-1 text-xs text-emerald-100">
                          Limit entry
                        </span>
                      ) : null}
                      {activeDraft.limit_exit ? (
                        <span className="rounded-md border border-emerald-300/30 bg-emerald-300/10 px-2 py-1 text-xs text-emerald-100">
                          Limit exit
                        </span>
                      ) : null}
                    </div>

                    <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                      <DetailRow
                        label="Quantity"
                        value={formatNumber(activeDraft.quantity)}
                      />
                      <DetailRow
                        label="Contracts"
                        value={formatNumber(activeDraft.contracts)}
                      />
                      <DetailRow
                        label="Entry"
                        value={formatNumber(activeDraft.entry_price)}
                      />
                      <DetailRow
                        label="Exit"
                        value={formatNumber(activeDraft.exit_price)}
                      />
                      <DetailRow
                        label="PnL"
                        value={
                          <span className={resultClass(activeDraft.pnl)}>
                            {formatCurrency(activeDraft.pnl)}
                          </span>
                        }
                      />
                      <DetailRow
                        label="Duration"
                        value={activeDraft.duration ?? "--"}
                      />
                      <DetailRow
                        label="Session"
                        value={activeDraft.session ?? "--"}
                      />
                      <DetailRow
                        label="Order IDs"
                        value={
                          activeDraft.related_order_ids.length > 0
                            ? activeDraft.related_order_ids.join(", ")
                            : "--"
                        }
                      />
                    </div>

                    {activeDraft.warnings.length > 0 ? (
                      <div className="mt-3 rounded-lg border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">
                        {activeDraft.warnings.join(" ")}
                      </div>
                    ) : null}

                    <div className="mt-4 grid gap-4">
                      <FieldLabel label="HTF Bias">
                        <select
                          value={activeDraft.htf_bias ?? ""}
                          onChange={(event) =>
                            updateImportDraft(
                              activeDraft.draft_id,
                              "htf_bias",
                              (event.target.value || null) as HtfBias | null,
                            )
                          }
                          className={inputClassName()}
                        >
                          <option value="">Select bias</option>
                          {htfBiasOptions.map((bias) => (
                            <option key={bias}>{bias}</option>
                          ))}
                        </select>
                      </FieldLabel>
                      <TagGroup
                        label="Draw on Liquidity"
                        options={liquidityOptions}
                        values={activeDraft.draw_on_liquidity}
                        onChange={(values) =>
                          updateImportDraft(
                            activeDraft.draft_id,
                            "draw_on_liquidity",
                            values,
                          )
                        }
                      />
                      <FieldLabel label="Reaction Zone">
                        <select
                          value={activeDraft.reaction_zone ?? ""}
                          onChange={(event) =>
                            updateImportDraft(
                              activeDraft.draft_id,
                              "reaction_zone",
                              event.target.value || null,
                            )
                          }
                          className={inputClassName()}
                        >
                          <option value="">Select zone</option>
                          {reactionZoneOptions.map((zone) => (
                            <option key={zone}>{zone}</option>
                          ))}
                        </select>
                      </FieldLabel>
                      <TagGroup
                        label="Behavior Tags"
                        options={behaviorOptions}
                        values={activeDraft.behavior_tags}
                        onChange={(values) =>
                          updateImportDraft(
                            activeDraft.draft_id,
                            "behavior_tags",
                            values,
                          )
                        }
                      />
                      <TagGroup
                        label="Execution Tags"
                        options={executionOptions}
                        values={activeDraft.execution_tags}
                        onChange={(values) =>
                          updateImportDraft(
                            activeDraft.draft_id,
                            "execution_tags",
                            values,
                          )
                        }
                      />
                      <FieldLabel label="Why did I take this trade?">
                        <textarea
                          value={activeDraft.why_taken ?? ""}
                          onChange={(event) =>
                            updateImportDraft(
                              activeDraft.draft_id,
                              "why_taken",
                              event.target.value || null,
                            )
                          }
                          className={inputClassName("min-h-20 resize-y")}
                        />
                      </FieldLabel>
                      <FieldLabel label="What was price trying to do?">
                        <textarea
                          value={activeDraft.price_intent ?? ""}
                          onChange={(event) =>
                            updateImportDraft(
                              activeDraft.draft_id,
                              "price_intent",
                              event.target.value || null,
                            )
                          }
                          className={inputClassName("min-h-20 resize-y")}
                        />
                      </FieldLabel>
                      <FieldLabel label="What liquidity was I targeting?">
                        <textarea
                          value={activeDraft.liquidity_target ?? ""}
                          onChange={(event) =>
                            updateImportDraft(
                              activeDraft.draft_id,
                              "liquidity_target",
                              event.target.value || null,
                            )
                          }
                          className={inputClassName("min-h-20 resize-y")}
                        />
                      </FieldLabel>
                      <div className="grid gap-3 sm:grid-cols-2">
                        <FieldLabel label="What went well?">
                          <textarea
                            value={activeDraft.went_well ?? ""}
                            onChange={(event) =>
                              updateImportDraft(
                                activeDraft.draft_id,
                                "went_well",
                                event.target.value || null,
                              )
                            }
                            className={inputClassName("min-h-20 resize-y")}
                          />
                        </FieldLabel>
                        <FieldLabel label="What went wrong?">
                          <textarea
                            value={activeDraft.went_wrong ?? ""}
                            onChange={(event) =>
                              updateImportDraft(
                                activeDraft.draft_id,
                                "went_wrong",
                                event.target.value || null,
                              )
                            }
                            className={inputClassName("min-h-20 resize-y")}
                          />
                        </FieldLabel>
                      </div>
                      <FieldLabel label="Lesson learned">
                        <textarea
                          value={activeDraft.lesson_learned ?? ""}
                          onChange={(event) =>
                            updateImportDraft(
                              activeDraft.draft_id,
                              "lesson_learned",
                              event.target.value || null,
                            )
                          }
                          className={inputClassName("min-h-20 resize-y")}
                        />
                      </FieldLabel>
                      <FieldLabel label="Screenshot path optional">
                        <input
                          value={activeDraft.screenshot_path ?? ""}
                          onChange={(event) =>
                            updateImportDraft(
                              activeDraft.draft_id,
                              "screenshot_path",
                              event.target.value || null,
                            )
                          }
                          className={inputClassName()}
                          placeholder="/path/to/chart.png"
                        />
                      </FieldLabel>
                    </div>

                    <div className="mt-4 flex flex-col gap-2 border-t border-white/10 pt-4 sm:flex-row sm:items-center sm:justify-between">
                      <button
                        type="button"
                        onClick={() => setActiveDraftIndex(activeDraftIndex - 1)}
                        disabled={activeDraftIndex === 0}
                        className="rounded-lg border border-white/10 px-4 py-2 text-sm font-semibold text-neutral-100 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        Previous Draft
                      </button>
                      <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
                        <button
                          type="button"
                          onClick={() =>
                            skipImportDraft(activeDraft, activeDraftIndex)
                          }
                          disabled={
                            savingImportDraftId !== null ||
                            draftStatus(activeDraft) !== "pending"
                          }
                          className="rounded-lg border border-amber-300/30 px-4 py-2 text-sm font-semibold text-amber-100 transition hover:bg-amber-300/10 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          Skip Draft
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            void saveImportDraft(activeDraft, activeDraftIndex)
                          }
                          disabled={
                            savingImportDraftId !== null ||
                            draftStatus(activeDraft) !== "pending"
                          }
                          className="rounded-lg bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          {savingImportDraftId === activeDraft.draft_id
                            ? "Saving..."
                            : "Save Draft"}
                        </button>
                      </div>
                    </div>
                  </article>
                ) : null}

                {importPreview.unmatched_orders.length > 0 ? (
                  <div className="rounded-lg border border-white/10 bg-neutral-950 p-3">
                    <p className="text-xs text-neutral-500">Unmatched Orders</p>
                    <div className="mt-2 grid gap-2">
                      {importPreview.unmatched_orders.map((order, index) => (
                        <div
                          key={`${order.order_id ?? "order"}-${index}`}
                          className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-neutral-300"
                        >
                          {order.order_id ?? "No ID"} • {order.side ?? "--"} •{" "}
                          {order.contract ?? "--"} • {order.order_type ?? "--"} •{" "}
                          {order.status ?? "--"}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>
            ) : null}
          </section>
          ) : null}

        {activeSection === "entries" ? (
        <section className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
          <div className="rounded-lg border border-white/10 bg-neutral-900/80 p-3">
            <div className="mb-3 flex flex-col gap-3 px-1 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs text-neutral-500">Journal List View</p>
                <h2 className="mt-1 text-lg font-semibold text-white">
                  Actual Trades
                </h2>
              </div>
              <button
                type="button"
                onClick={() => {
                  beginCreate();
                  setActiveSection("manual");
                }}
                className="rounded-lg bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
              >
                Create Entry
              </button>
            </div>
            {loading ? (
              <p className="p-3 text-sm text-neutral-400">Loading entries...</p>
            ) : entries.length === 0 ? (
              <div className="p-3">
                <p className="text-sm font-semibold text-neutral-100">
                  No journal entries yet.
                </p>
                <p className="mt-2 text-sm leading-6 text-neutral-400">
                  Capture the trade information, context, narrative, review,
                  and attachments after each trade.
                </p>
              </div>
            ) : (
              <div className="grid gap-2">
                {entries.map((entry) => (
                  <button
                    key={entry.id}
                    type="button"
                    onClick={() => setSelectedId(entry.id)}
                    className={`rounded-lg border p-3 text-left transition ${
                      selectedEntry?.id === entry.id
                        ? "border-cyan-300/50 bg-cyan-300/10"
                        : "border-white/10 bg-neutral-950 hover:border-white/20"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs text-neutral-500">
                          {entry.trade_date} • {entry.session ?? "No session"}
                        </p>
                        <h3 className="mt-1 text-base font-semibold text-white">
                          {entry.symbol} {entry.direction}
                        </h3>
                      </div>
                      <p
                        className={`text-sm font-semibold ${resultClass(
                          entry.result_dollars,
                        )}`}
                      >
                        {formatCurrency(entry.result_dollars)}
                      </p>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <span className="rounded-md border border-white/10 px-2 py-1 text-xs text-neutral-300">
                        {entry.htf_bias ?? "No HTF bias"}
                      </span>
                      <span className="rounded-md border border-white/10 px-2 py-1 text-xs text-neutral-300">
                        {entry.reaction_zone ?? "No zone"}
                      </span>
                      <span className="rounded-md border border-cyan-300/25 bg-cyan-300/10 px-2 py-1 text-xs text-cyan-100">
                        {entry.strategy_mode ?? "Hybrid / Review"}
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>

          {selectedEntry ? (
            <section className="rounded-lg border border-white/10 bg-neutral-900/80 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-xs text-neutral-500">
                    Journal Detail View
                  </p>
                  <h2 className="mt-1 text-lg font-semibold">
                    {selectedEntry.symbol} {selectedEntry.direction}
                  </h2>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setActiveSection("manual");
                      beginEdit(selectedEntry);
                    }}
                    className="rounded-lg border border-white/10 px-3 py-2.5 text-xs font-semibold text-neutral-100 hover:bg-white/10"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDelete(selectedEntry.id)}
                    className="rounded-lg border border-red-400/30 px-3 py-2.5 text-xs font-semibold text-red-100 hover:bg-red-500/10"
                  >
                    Delete
                  </button>
                </div>
              </div>

              <div className="mt-4 grid gap-3 sm:grid-cols-2">
                <DetailRow label="Entry" value={formatNumber(selectedEntry.entry_price)} />
                <DetailRow label="Stop Loss" value={formatNumber(selectedEntry.stop_loss)} />
                <DetailRow label="Take Profit" value={formatNumber(selectedEntry.take_profit)} />
                <DetailRow label="Exit" value={formatNumber(selectedEntry.exit_price)} />
                <DetailRow
                  label="Result"
                  value={
                    <span className={resultClass(selectedEntry.result_dollars)}>
                      {formatCurrency(selectedEntry.result_dollars)}
                    </span>
                  }
                />
                <DetailRow label="Result R" value={formatNumber(selectedEntry.result_r, "R")} />
                <DetailRow label="Contracts" value={formatNumber(selectedEntry.contracts)} />
                <DetailRow label="HTF Bias" value={selectedEntry.htf_bias ?? "--"} />
                <DetailRow
                  label="Strategy Profile"
                  value={selectedEntry.strategy_profile || strategyProfileName}
                />
                <DetailRow
                  label="Strategy Mode"
                  value={selectedEntry.strategy_mode ?? "Hybrid / Review"}
                />
              </div>

              <div className="mt-3 grid gap-3">
                <DetailRow
                  label="Draw on Liquidity"
                  value={<ChipList values={selectedEntry.draw_on_liquidity} />}
                />
                <DetailRow
                  label="Reaction Zone"
                  value={selectedEntry.reaction_zone ?? "--"}
                />
                <DetailRow
                  label="Behavior Tags"
                  value={<ChipList values={selectedEntry.behavior_tags} />}
                />
                <DetailRow
                  label="Execution Tags"
                  value={<ChipList values={selectedEntry.execution_tags} />}
                />
              </div>

              <div className="mt-3 grid gap-3">
                <TextBlock
                  title="Why did I take this trade?"
                  value={selectedEntry.why_taken}
                />
                <TextBlock
                  title="What was price trying to do?"
                  value={selectedEntry.price_intent}
                />
                <TextBlock
                  title="What liquidity was I targeting?"
                  value={selectedEntry.liquidity_target}
                />
                <TextBlock title="What went well?" value={selectedEntry.went_well} />
                <TextBlock title="What went wrong?" value={selectedEntry.went_wrong} />
                <TextBlock title="Lesson learned" value={selectedEntry.lesson_learned} />
              </div>

              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <DetailRow
                  label="Screenshot path"
                  value={selectedEntry.screenshot_path ?? "--"}
                />
                <DetailRow label="CSV path" value={selectedEntry.csv_path ?? "--"} />
              </div>
            </section>
          ) : null}
        </section>
        ) : null}

        {activeSection === "manual" ? (
        <section className="rounded-lg border border-white/10 bg-neutral-900/80 p-4">
          <div className="mb-4 flex items-center justify-between gap-3">
            <div>
              <p className="text-xs text-neutral-500">
                {editingId === null ? "Create Entry" : "Edit Entry"}
              </p>
              <h2 className="mt-1 text-lg font-semibold">
                {editingId === null ? "New Journal Entry" : "Update Journal Entry"}
              </h2>
            </div>
            {editingId !== null ? (
              <button
                type="button"
                onClick={beginCreate}
                className="rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold text-neutral-100 hover:bg-white/10"
              >
                Cancel Edit
              </button>
            ) : null}
          </div>

          <form onSubmit={(event) => void handleSubmit(event)} className="space-y-5">
            <section>
              <h3 className="text-sm font-semibold text-cyan-100">
                Trade Information
              </h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <FieldLabel label="Trade Date">
                  <input
                    required
                    type="date"
                    value={form.trade_date}
                    onChange={(event) => updateForm("trade_date", event.target.value)}
                    className={inputClassName()}
                  />
                </FieldLabel>
                <FieldLabel label="Symbol">
                  <input
                    required
                    value={form.symbol}
                    onChange={(event) => updateForm("symbol", event.target.value)}
                    className={inputClassName("uppercase")}
                    placeholder="MES"
                  />
                </FieldLabel>
                <FieldLabel label="Direction">
                  <select
                    value={form.direction}
                    onChange={(event) =>
                      updateForm("direction", event.target.value as Direction)
                    }
                    className={inputClassName()}
                  >
                    {directions.map((direction) => (
                      <option key={direction}>{direction}</option>
                    ))}
                  </select>
                </FieldLabel>
                <FieldLabel label="Session">
                  <select
                    value={form.session}
                    onChange={(event) =>
                      updateForm("session", event.target.value as "" | TradeSession)
                    }
                    className={inputClassName()}
                  >
                    <option value="">Select session</option>
                    {sessions.map((session) => (
                      <option key={session}>{session}</option>
                    ))}
                  </select>
                </FieldLabel>
                <FieldLabel label="Entry Price">
                  <input
                    inputMode="decimal"
                    value={form.entry_price}
                    onChange={(event) => updateForm("entry_price", event.target.value)}
                    className={inputClassName()}
                  />
                </FieldLabel>
                <FieldLabel label="Stop Loss">
                  <input
                    inputMode="decimal"
                    value={form.stop_loss}
                    onChange={(event) => updateForm("stop_loss", event.target.value)}
                    className={inputClassName()}
                  />
                </FieldLabel>
                <FieldLabel label="Take Profit">
                  <input
                    inputMode="decimal"
                    value={form.take_profit}
                    onChange={(event) => updateForm("take_profit", event.target.value)}
                    className={inputClassName()}
                  />
                </FieldLabel>
                <FieldLabel label="Exit Price">
                  <input
                    inputMode="decimal"
                    value={form.exit_price}
                    onChange={(event) => updateForm("exit_price", event.target.value)}
                    className={inputClassName()}
                  />
                </FieldLabel>
                <FieldLabel label="Result ($)">
                  <input
                    inputMode="decimal"
                    value={form.result_dollars}
                    onChange={(event) =>
                      updateForm("result_dollars", event.target.value)
                    }
                    className={inputClassName()}
                  />
                </FieldLabel>
                <FieldLabel label="Result (R)">
                  <input
                    inputMode="decimal"
                    value={form.result_r}
                    onChange={(event) => updateForm("result_r", event.target.value)}
                    className={inputClassName()}
                  />
                </FieldLabel>
                <FieldLabel label="Contracts">
                  <input
                    inputMode="numeric"
                    value={form.contracts}
                    onChange={(event) => updateForm("contracts", event.target.value)}
                    className={inputClassName()}
                  />
                </FieldLabel>
              </div>
            </section>

            <section>
              <h3 className="text-sm font-semibold text-cyan-100">
                Trade Context
              </h3>
              <div className="mt-3 grid gap-3">
                <FieldLabel label="HTF Bias">
                  <select
                    value={form.htf_bias}
                    onChange={(event) =>
                      updateForm("htf_bias", event.target.value as "" | HtfBias)
                    }
                    className={inputClassName()}
                  >
                    <option value="">Select bias</option>
                    {htfBiasOptions.map((bias) => (
                      <option key={bias}>{bias}</option>
                    ))}
                  </select>
                </FieldLabel>
                <FieldLabel label="Strategy Profile">
                  <input
                    readOnly
                    value={form.strategy_profile}
                    className={inputClassName("text-neutral-300")}
                  />
                </FieldLabel>
                <FieldLabel label="Strategy Mode">
                  <select
                    value={form.strategy_mode}
                    onChange={(event) =>
                      updateForm("strategy_mode", event.target.value as StrategyMode)
                    }
                    className={inputClassName()}
                  >
                    {strategyModeOptions.map((mode) => (
                      <option key={mode}>{mode}</option>
                    ))}
                  </select>
                </FieldLabel>
                <TagGroup
                  label="Draw on Liquidity"
                  options={liquidityOptions}
                  values={form.draw_on_liquidity}
                  onChange={(values) => updateForm("draw_on_liquidity", values)}
                />
                <FieldLabel label="Reaction Zone">
                  <select
                    value={form.reaction_zone}
                    onChange={(event) =>
                      updateForm("reaction_zone", event.target.value)
                    }
                    className={inputClassName()}
                  >
                    <option value="">Select zone</option>
                    {reactionZoneOptions.map((zone) => (
                      <option key={zone}>{zone}</option>
                    ))}
                  </select>
                </FieldLabel>
                <TagGroup
                  label="Behavior Tags"
                  options={behaviorOptions}
                  values={form.behavior_tags}
                  onChange={(values) => updateForm("behavior_tags", values)}
                />
                <TagGroup
                  label="Execution Tags"
                  options={executionOptions}
                  values={form.execution_tags}
                  onChange={(values) => updateForm("execution_tags", values)}
                />
              </div>
            </section>

            <section>
              <h3 className="text-sm font-semibold text-cyan-100">Narrative</h3>
              <div className="mt-3 grid gap-3">
                <FieldLabel label="Why did I take this trade?">
                  <textarea
                    value={form.why_taken}
                    onChange={(event) => updateForm("why_taken", event.target.value)}
                    className={inputClassName("min-h-24 resize-y")}
                  />
                </FieldLabel>
                <FieldLabel label="What was price trying to do?">
                  <textarea
                    value={form.price_intent}
                    onChange={(event) =>
                      updateForm("price_intent", event.target.value)
                    }
                    className={inputClassName("min-h-24 resize-y")}
                  />
                </FieldLabel>
                <FieldLabel label="What liquidity was I targeting?">
                  <textarea
                    value={form.liquidity_target}
                    onChange={(event) =>
                      updateForm("liquidity_target", event.target.value)
                    }
                    className={inputClassName("min-h-24 resize-y")}
                  />
                </FieldLabel>
              </div>
            </section>

            <section>
              <h3 className="text-sm font-semibold text-cyan-100">Review</h3>
              <div className="mt-3 grid gap-3">
                <FieldLabel label="What went well?">
                  <textarea
                    value={form.went_well}
                    onChange={(event) => updateForm("went_well", event.target.value)}
                    className={inputClassName("min-h-20 resize-y")}
                  />
                </FieldLabel>
                <FieldLabel label="What went wrong?">
                  <textarea
                    value={form.went_wrong}
                    onChange={(event) => updateForm("went_wrong", event.target.value)}
                    className={inputClassName("min-h-20 resize-y")}
                  />
                </FieldLabel>
                <FieldLabel label="Lesson learned">
                  <textarea
                    value={form.lesson_learned}
                    onChange={(event) =>
                      updateForm("lesson_learned", event.target.value)
                    }
                    className={inputClassName("min-h-20 resize-y")}
                  />
                </FieldLabel>
              </div>
            </section>

            <section>
              <h3 className="text-sm font-semibold text-cyan-100">
                Attachments
              </h3>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <FieldLabel label="Screenshot path">
                  <input
                    value={form.screenshot_path}
                    onChange={(event) =>
                      updateForm("screenshot_path", event.target.value)
                    }
                    className={inputClassName()}
                    placeholder="/path/to/chart.png"
                  />
                </FieldLabel>
                <FieldLabel label="CSV path">
                  <input
                    value={form.csv_path}
                    onChange={(event) => updateForm("csv_path", event.target.value)}
                    className={inputClassName()}
                    placeholder="/path/to/export.csv"
                  />
                </FieldLabel>
              </div>
            </section>

            <div className="flex flex-col gap-2 border-t border-white/10 pt-4 sm:flex-row sm:items-center sm:justify-end">
              <button
                type="button"
                onClick={beginCreate}
                className="rounded-lg border border-white/10 px-4 py-2 text-sm font-semibold text-neutral-100 hover:bg-white/10"
              >
                Clear
              </button>
              <button
                type="submit"
                disabled={saving || form.symbol.trim() === ""}
                className="rounded-lg bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {saving ? "Saving..." : editingId === null ? "Save Entry" : "Update Entry"}
              </button>
            </div>
          </form>
        </section>
        ) : null}
      </div>
    </main>
  );
}
