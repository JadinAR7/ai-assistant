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
const IMPORT_URL = `${JOURNAL_URL}/import-pdf`;
const IMPORT_SAVE_URL = `${IMPORT_URL}/save`;

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
type JournalMode = "import" | "manual";
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
  const [journalMode, setJournalMode] = useState<JournalMode>("import");
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
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [previewingImport, setPreviewingImport] = useState(false);
  const [savingImportDraftId, setSavingImportDraftId] = useState<string | null>(
    null,
  );
  const [error, setError] = useState<string | null>(null);
  const [importError, setImportError] = useState<string | null>(null);
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
    } catch (deleteError) {
      setError(
        deleteError instanceof Error
          ? deleteError.message
          : "Journal entry could not be deleted.",
      );
    }
  }

  return (
    <main className="min-h-screen bg-[#05070b] text-white">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-[#05070b]/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300">
              Orbit
            </p>
            <h1 className="mt-1 text-xl font-semibold tracking-tight">
              Trade Journal
            </h1>
          </div>

          <nav className="flex flex-wrap items-center gap-2">
            <Link
              href="/"
              className="rounded-lg border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Core
            </Link>
            <Link
              href="/command-center"
              className="rounded-lg border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Command Center
            </Link>
            <Link
              href="/orbit"
              className="rounded-lg border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Orbit
            </Link>
          </nav>
        </div>
      </header>

      <div className="mx-auto flex max-w-7xl px-4 pt-4">
        <div className="grid w-full gap-2 rounded-lg border border-white/10 bg-neutral-900/80 p-1 sm:w-auto sm:grid-cols-2">
          {(["import", "manual"] as const).map((mode) => (
            <button
              key={mode}
              type="button"
              onClick={() => setJournalMode(mode)}
              className={`rounded-md px-4 py-2 text-sm font-semibold transition ${
                journalMode === mode
                  ? "bg-cyan-300 text-slate-950"
                  : "text-neutral-300 hover:bg-white/10 hover:text-white"
              }`}
            >
              {mode === "import" ? "Import Trades" : "Manual Entry"}
            </button>
          ))}
        </div>
      </div>

      <div
        className={`mx-auto max-w-7xl gap-4 px-4 py-4 ${
          journalMode === "manual"
            ? "grid xl:grid-cols-[0.9fr_1.15fr]"
            : "grid"
        }`}
      >
        <section className="space-y-4">
          <div className="rounded-lg border border-cyan-300/20 bg-cyan-300/5 p-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm text-cyan-100/80">
                  Data capture foundation
                </p>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight">
                  Journal List View
                </h2>
              </div>
              <button
                type="button"
                onClick={() => {
                  setJournalMode("manual");
                  beginCreate();
                }}
                className="rounded-lg bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
              >
                Create Entry
              </button>
            </div>
          </div>

          {journalMode === "import" ? (
          <section className="rounded-lg border border-white/10 bg-neutral-900/80 p-4">
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
                className="rounded-lg border border-cyan-300/30 bg-cyan-300/10 px-4 py-2 text-sm font-semibold text-cyan-100 transition hover:bg-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {previewingImport ? "Previewing..." : "Preview Import"}
              </button>
            </form>

            {importError ? (
              <div className="mt-3 rounded-lg border border-amber-400/25 bg-amber-400/10 px-3 py-2 text-sm text-amber-100">
                {importError}
              </div>
            ) : null}

            {importPreview ? (
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

                {importReviewComplete ? (
                  <div className="rounded-lg border border-emerald-400/25 bg-emerald-400/10 px-4 py-3 text-sm font-semibold text-emerald-100">
                    Import review complete.
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

          <div className="rounded-lg border border-white/10 bg-neutral-900/80 p-3">
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
                      setJournalMode("manual");
                      beginEdit(selectedEntry);
                    }}
                    className="rounded-lg border border-white/10 px-3 py-2 text-xs font-semibold text-neutral-100 hover:bg-white/10"
                  >
                    Edit
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleDelete(selectedEntry.id)}
                    className="rounded-lg border border-red-400/30 px-3 py-2 text-xs font-semibold text-red-100 hover:bg-red-500/10"
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

        {journalMode === "manual" ? (
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
