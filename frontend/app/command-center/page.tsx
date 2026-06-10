"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import ReactMarkdown from "react-markdown";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

function generateId() {
  return Math.random().toString(36).substring(2, 10);
}

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  error?: boolean;
  retryText?: string;
  createdAt?: string;
  source?: ResponseSource;
};

type ResponseSource =
  | "Intent"
  | "Scanner"
  | "CSV"
  | "Vision"
  | "Chat"
  | "Tool"
  | "System"
  | "User";

const LONG_RESPONSE_CHAR_LIMIT = 1200;
const LONG_RESPONSE_LINE_LIMIT = 18;
const COLLAPSED_PREVIEW_CHAR_LIMIT = 1600;
const COLLAPSED_PREVIEW_LINE_LIMIT = 24;

type ScanRecord = {
  timestamp?: string;
  timezone?: string;
  symbol?: string;
  sessions?: string[];
  session_label?: string;
  success?: boolean;
  screenshot_path?: string;
  vision_success?: boolean;
  vision_error?: string | null;
  csv_success?: boolean;
  message?: string;
  comparison?: {
    market_changes?: string[];
    visual_context_changes?: string[];
    system_status?: string[];
  };
  alert?: {
    should_alert?: boolean;
    alert_type?: string;
    severity?: string;
    reasons?: string[];
  };
  alert_eligibility?: {
    level?: string;
    should_notify?: boolean;
    reasons?: string[];
    blockers?: string[];
  };
  signal_level?: string;
  signal_reason?: string;
  narrative_state?: string;
  narrative_phase?: string;
  narrative_confidence?: string;
  narrative?: {
    liquidity_draw?: string;
    liquidity_draw_direction?: string;
    htf_reaction_zone?: string;
    reaction_zone_timeframe?: string;
    reaction_zone_type?: string;
    reaction_zone_status?: string;
    behavior_inside_zone?: string;
    structure_confirmation?: string;
    execution_readiness?: string;
    target_liquidity?: string;
    invalidation_context?: string;
    narrative_phase?: string;
    narrative_confidence?: string;
    missing_confirmations?: string[];
  };
  reaction_zone_status?: string;
  behavior_confirmation?: string;
  liquidity_draw_alignment?: string;
  repeat_suppressed?: boolean;
  presence_mode?: string;
  notification_allowed_by_presence?: boolean;
  presence_reason?: string;
  state?: {
    htf_bias?: string;
    execution_bias?: string;
    price_relation?: string;
    visual_4h_fvg?: boolean;
    visual_15m_fvg?: boolean;
    pdh_visible?: boolean;
    vision_success?: boolean;
    csv_success?: boolean;
  };
};

type ScanStatus = {
  symbol?: string;
  default_symbol?: string;
  timezone?: string;
  scanner_enabled?: boolean;
  process_running?: boolean;
  process_id?: number | null;
  heartbeat_timestamp?: string | null;
  running_scan?: boolean;
  last_scan_timestamp?: string | null;
  latest_scan_success?: boolean | null;
  scan_interval_seconds?: number;
  active_sessions?: string[];
  should_scan_now?: boolean;
  scheduled_scan_allowed?: boolean;
  automatic_scans_paused?: boolean;
};

type ScannerSettings = {
  default_symbol: string;
  scanner_enabled?: boolean;
  supported_symbols: string[];
  updated_at?: string;
};

type PresenceMode = {
  mode: string;
  label: string;
  description: string;
  scanner_min_signal_level: string;
  notifications_allowed: boolean;
  tts_allowed: boolean;
  imessage_allowed: boolean;
  scan_noise_profile: string;
  updated_at?: string;
};

function formatTimestamp(timestamp?: string) {
  if (!timestamp) return "Unknown";

  try {
    const date = new Date(timestamp);

    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
      timeZoneName: "short",
    }).format(date);
  } catch {
    return timestamp;
  }
}

function formatMessageTimestamp(timestamp?: string) {
  if (!timestamp) return "";

  try {
    const date = new Date(timestamp);
    if (Number.isNaN(date.getTime())) return "";

    const now = new Date();
    const sameDay =
      date.getFullYear() === now.getFullYear() &&
      date.getMonth() === now.getMonth() &&
      date.getDate() === now.getDate();

    return new Intl.DateTimeFormat("en-US", {
      month: sameDay ? undefined : "short",
      day: sameDay ? undefined : "numeric",
      hour: "numeric",
      minute: "2-digit",
      hour12: true,
    }).format(date);
  } catch {
    return "";
  }
}

function getFileName(path?: string) {
  if (!path) return "None";
  return path.split("/").pop() || path;
}

function formatLabel(value?: string) {
  if (!value) return "unknown";
  return value.replaceAll("_", " ");
}

function getAgeSeconds(timestamp?: string | null) {
  if (!timestamp) return null;

  const value = new Date(timestamp).getTime();

  if (Number.isNaN(value)) return null;

  return Math.max(0, Math.floor((Date.now() - value) / 1000));
}

function formatRelativeAge(timestamp?: string | null) {
  const seconds = getAgeSeconds(timestamp);

  if (seconds === null) return "Unknown";
  if (seconds < 60) return `${seconds}s ago`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;

  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

function getBiasBadgeClass(value?: string) {
  const lower = value?.toLowerCase() || "";

  if (lower.includes("bullish")) {
    return "bg-green-500/15 text-green-300 border-green-500/20";
  }

  if (lower.includes("bearish")) {
    return "bg-red-500/15 text-red-300 border-red-500/20";
  }

  if (lower.includes("neutral")) {
    return "bg-yellow-500/15 text-yellow-300 border-yellow-500/20";
  }

  return "bg-neutral-800 text-neutral-300 border-white/10";
}

function getSignalBadgeClass(level?: string) {
  switch ((level || "").toLowerCase()) {
    case "alert":
      return "bg-red-500/15 text-red-300 border-red-500/20";
    case "review":
      return "bg-yellow-500/15 text-yellow-300 border-yellow-500/20";
    case "watch":
      return "bg-blue-500/15 text-blue-300 border-blue-500/20";
    default:
      return "bg-neutral-800 text-neutral-300 border-white/10";
  }
}

function buildCompactScanSummary(record: ScanRecord | null) {
  if (!record) return "No scan loaded yet.";

  const htf = record.state?.htf_bias || "unknown";
  const execution = record.state?.execution_bias || "unknown";
  const relation = formatLabel(record.state?.price_relation);
  const signal = formatLabel(record.signal_level || "informational");
  const phase = formatLabel(
    record.narrative?.narrative_phase ||
      record.narrative_phase ||
      record.narrative_state ||
      "no_clear_narrative"
  );
  const behavior = formatLabel(
    record.narrative?.behavior_inside_zone || record.behavior_confirmation || "none"
  );
  const readiness = formatLabel(record.narrative?.execution_readiness || "not_ready");
  const eligibility = record.alert_eligibility?.should_notify
    ? "eligible"
    : "not notification-worthy";
  const presence = record.notification_allowed_by_presence
    ? "presence allows"
    : "presence blocks";

  return `Signal ${signal}. Phase ${phase}. HTF ${htf}, execution ${execution}. Price relation: ${relation}. Behavior: ${behavior}. Readiness: ${readiness}. Alert eligibility: ${eligibility}; ${presence}.`;
}

function inferMessageSource(
  content: string,
  role: Message["role"],
  preferred?: ResponseSource
): ResponseSource {
  if (preferred) return preferred;
  if (role === "user") return "User";

  const lower = content.toLowerCase();

  if (lower.startsWith("tool:") || lower.includes("tool output")) return "Tool";
  if (lower.includes("## latest") && lower.includes("scan")) return "Scanner";
  if (
    lower.includes("csv structural read") ||
    lower.includes("csv reference zones") ||
    lower.includes("stale csv reference close") ||
    lower.includes("analyze_market_csv")
  ) {
    return "CSV";
  }
  if (lower.includes("visual markings check") || lower.includes("image analysis")) {
    return "Vision";
  }
  if (
    lower.includes("presence mode") ||
    lower.includes("trading coach") ||
    lower.includes("pattern discovery") ||
    lower.includes("scanner correlation")
  ) {
    return "Intent";
  }
  if (lower.includes("backend connection failed") || lower.includes("chat cleared")) {
    return "System";
  }

  return "Chat";
}

function isLongResponse(content: string) {
  return (
    content.length > LONG_RESPONSE_CHAR_LIMIT ||
    content.split(/\r?\n/).length > LONG_RESPONSE_LINE_LIMIT
  );
}

function isRawToolLine(line: string) {
  const trimmed = line.trim();
  const lower = trimmed.toLowerCase();

  return (
    lower.startsWith("tool:") ||
    lower.startsWith("tool output") ||
    lower.startsWith("raw tool") ||
    lower.startsWith("[tool") ||
    lower.startsWith("```tool") ||
    /^[a-z_]+:\s*[{[]/.test(lower)
  );
}

function getReadableResponse(content: string) {
  const trimmed = content.trim();
  const finalMarker = trimmed.match(
    /(?:^|\n)(?:final(?: response)?|assistant|response):\s*/i
  );

  if (finalMarker?.index !== undefined) {
    const readable = trimmed.slice(finalMarker.index + finalMarker[0].length).trim();

    if (readable) return readable;
  }

  const readableLines = trimmed
    .split(/\r?\n/)
    .filter((line) => !isRawToolLine(line));

  return readableLines.join("\n").trim();
}

function getCollapsedPreview(content: string) {
  const lines = content.split(/\r?\n/);
  let preview = lines.slice(0, COLLAPSED_PREVIEW_LINE_LIMIT).join("\n");

  if (preview.length > COLLAPSED_PREVIEW_CHAR_LIMIT) {
    preview = preview.slice(0, COLLAPSED_PREVIEW_CHAR_LIMIT).trimEnd();
  }

  return preview.trim();
}

function sourceBadgeClass(source: ResponseSource) {
  switch (source) {
    case "Scanner":
      return "border-cyan-300/20 bg-cyan-300/10 text-cyan-100";
    case "CSV":
      return "border-amber-300/20 bg-amber-300/10 text-amber-100";
    case "Vision":
      return "border-violet-300/20 bg-violet-300/10 text-violet-100";
    case "Intent":
      return "border-emerald-300/20 bg-emerald-300/10 text-emerald-100";
    case "Tool":
      return "border-blue-300/20 bg-blue-300/10 text-blue-100";
    case "User":
      return "border-blue-200/20 bg-blue-200/15 text-blue-50";
    case "System":
      return "border-neutral-300/15 bg-neutral-300/10 text-neutral-200";
    default:
      return "border-white/10 bg-white/[0.04] text-neutral-200";
  }
}

function ResponseContent({
  content,
  collapsed,
}: Readonly<{
  content: string;
  collapsed: boolean;
}>) {
  const readableContent = getReadableResponse(content);

  if (!readableContent) {
    return <p className="text-neutral-400">Using tool...</p>;
  }

  const displayedContent =
    collapsed && isLongResponse(readableContent)
      ? getCollapsedPreview(readableContent)
      : readableContent;

  if (!displayedContent) {
    return <p className="text-neutral-400">Using tool...</p>;
  }

  return (
    <div className="prose prose-invert w-full max-w-none break-words prose-p:my-2 prose-headings:mb-2 prose-headings:mt-4 prose-h2:border-t prose-h2:border-white/10 prose-h2:pt-3 prose-h2:text-sm prose-h2:font-semibold prose-h2:text-cyan-100 prose-pre:max-w-full prose-pre:overflow-x-auto prose-code:break-words prose-ul:my-2 prose-li:my-1 prose-strong:text-neutral-100 [overflow-wrap:anywhere]">
      <ReactMarkdown>{displayedContent}</ReactMarkdown>
      {collapsed && isLongResponse(readableContent) ? (
        <div className="mt-3 border-t border-white/10 pt-3 text-xs text-neutral-500">
          Response collapsed for readability.
        </div>
      ) : null}
    </div>
  );
}

function MessageCard({
  msg,
  onDelete,
  onRetry,
}: Readonly<{
  msg: Message;
  onDelete: (id: string) => void;
  onRetry: (text: string) => void;
}>) {
  const readableContent = getReadableResponse(msg.content) || msg.content;
  const longResponse = isLongResponse(readableContent);
  const [expanded, setExpanded] = useState(!longResponse);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const source = inferMessageSource(msg.content, msg.role, msg.source);
  const timestamp = formatMessageTimestamp(msg.createdAt);

  async function copyMessage() {
    try {
      await navigator.clipboard.writeText(msg.content);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }

    window.setTimeout(() => setCopyState("idle"), 1800);
  }

  return (
    <div
      className={`group flex min-w-0 max-w-full ${
        msg.role === "user" ? "justify-end" : "justify-start"
      }`}
    >
      <article
        className={`min-w-0 break-words rounded-2xl px-3 py-3 text-sm leading-relaxed shadow-lg [overflow-wrap:anywhere] sm:px-4 ${
          msg.role === "user"
            ? "w-fit max-w-[92%] bg-blue-600 text-white sm:max-w-[72%] lg:max-w-[64%]"
            : msg.error
            ? "w-full max-w-full border border-red-500/30 bg-red-950/40 text-red-100 sm:w-[85%] lg:w-[82%]"
            : "w-full max-w-full border border-white/10 bg-neutral-900 text-neutral-100 sm:w-[85%] lg:w-[82%]"
        }`}
      >
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-wide ${sourceBadgeClass(
                source
              )}`}
            >
              {source}
            </span>
            {msg.error ? (
              <span className="rounded-full border border-red-300/20 bg-red-300/10 px-2 py-1 text-[11px] font-semibold uppercase tracking-wide text-red-100">
                Error
              </span>
            ) : null}
          </div>
          {timestamp ? (
            <time
              dateTime={msg.createdAt}
              className={`shrink-0 text-[11px] ${
                msg.role === "user" ? "text-blue-100/75" : "text-neutral-500"
              }`}
            >
              {timestamp}
            </time>
          ) : null}
        </div>

        <ResponseContent content={msg.content} collapsed={!expanded} />

        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <button
            type="button"
            onClick={copyMessage}
            title="Copy full response text"
            aria-label="Copy full response text"
            className={`min-h-9 rounded-lg border px-3 py-2 font-semibold transition ${
              msg.role === "user"
                ? "border-blue-100/20 bg-blue-100/10 text-blue-50 hover:bg-blue-100/20"
                : "border-white/10 bg-white/[0.03] text-neutral-300 hover:bg-white/[0.08] hover:text-white"
            }`}
          >
            {copyState === "copied"
              ? "Copied"
              : copyState === "failed"
              ? "Copy failed"
              : "Copy"}
          </button>

          {longResponse ? (
            <button
              type="button"
              onClick={() => setExpanded((value) => !value)}
              className={`min-h-9 rounded-lg border px-3 py-2 font-semibold transition ${
                msg.role === "user"
                  ? "border-blue-100/20 bg-blue-100/10 text-blue-50 hover:bg-blue-100/20"
                  : "border-white/10 bg-white/[0.03] text-neutral-300 hover:bg-white/[0.08] hover:text-white"
              }`}
            >
              {expanded ? "Show less" : "Show more"}
            </button>
          ) : null}

          {msg.error && msg.retryText ? (
            <button
              type="button"
              onClick={() => onRetry(msg.retryText || "")}
              className="min-h-9 rounded-lg border border-red-300/20 bg-red-300/10 px-3 py-2 font-semibold text-red-100"
            >
              Retry
            </button>
          ) : null}

          <button
            type="button"
            onClick={() => onDelete(msg.id)}
            className={`min-h-9 rounded-lg border px-3 py-2 font-semibold transition ${
              msg.role === "user"
                ? "border-blue-100/20 bg-blue-100/10 text-blue-50 hover:bg-blue-100/20"
                : "border-white/10 bg-white/[0.03] text-neutral-300 hover:bg-white/[0.08] hover:text-white"
            }`}
          >
            Delete
          </button>
        </div>
      </article>
    </div>
  );
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: generateId(),
      role: "assistant",
      content: "What’s good, Jadin? Helix is online.",
      createdAt: new Date().toISOString(),
      source: "System",
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [scanLoading, setScanLoading] = useState(false);
  const [latestScan, setLatestScan] = useState<ScanRecord | null>(null);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [scanStatusError, setScanStatusError] = useState(false);
  const [scannerSettings, setScannerSettings] = useState<ScannerSettings | null>(null);
  const [scannerSettingsLoading, setScannerSettingsLoading] = useState(false);
  const [presence, setPresence] = useState<PresenceMode | null>(null);
  const [presenceLoading, setPresenceLoading] = useState(false);

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);

  const [activeView, setActiveView] = useState<"chat" | "system">("chat");
  const [attachedFile, setAttachedFile] = useState<File | null>(null);

  useEffect(() => {
    if (window.matchMedia("(min-width: 1024px)").matches) {
      messagesContainerRef.current?.scrollTo({
        top: messagesContainerRef.current.scrollHeight,
        behavior: "smooth",
      });
      return;
    }

    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    loadHistory();
    loadScanStatus();
    loadLatestScan();
    loadScannerSettings();
    loadPresence();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      loadScanStatus();
    }, 12_000);

    return () => window.clearInterval(timer);
  }, []);

  function addAssistantMessage(
    content: string,
    error = false,
    source?: ResponseSource
  ) {
    setMessages((prev) => [
      ...prev,
      {
        id: generateId(),
        role: "assistant",
        content,
        error,
        createdAt: new Date().toISOString(),
        source: inferMessageSource(content, "assistant", source),
      },
    ]);
  }

  function formatScanSummary(record: ScanRecord) {
    const alert = record.alert;
    const eligibility = record.alert_eligibility;
    const comparison = record.comparison;

    const marketChanges = comparison?.market_changes?.length
      ? comparison.market_changes.map((item) => `- ${item}`).join("\n")
      : "- No market comparison available.";

    const visualChanges = comparison?.visual_context_changes?.length
      ? comparison.visual_context_changes.map((item) => `- ${item}`).join("\n")
      : "- No visual comparison available.";

    const alertReasons = alert?.reasons?.length
      ? alert.reasons.map((item) => `- ${item}`).join("\n")
      : "- No alert decision available.";

    const eligibilityReasons = eligibility?.reasons?.length
      ? eligibility.reasons.map((item) => `- ${item}`).join("\n")
      : "- No alert eligibility reason available.";

    const eligibilityBlockers = eligibility?.blockers?.length
      ? eligibility.blockers.map((item) => `- ${item}`).join("\n")
      : "- No alert eligibility blocker available.";
    const narrative = record.narrative || {};
    const missingConfirmations = narrative.missing_confirmations?.length
      ? narrative.missing_confirmations.map((item) => `- ${item}`).join("\n")
      : "- No missing confirmations recorded.";

    return `## Latest ${record.symbol || "MES"} Scan

**Session:** ${record.session_label || "Unknown"}  
**Time:** ${formatTimestamp(record.timestamp)}  
**Vision:** ${record.vision_success ? "Success" : "Failed"}  
**CSV:** ${record.csv_success ? "Success" : "Failed"}  
**Signal Level:** ${formatLabel(record.signal_level || "informational")}  
**Narrative Phase:** ${formatLabel(narrative.narrative_phase || record.narrative_phase || record.narrative_state || "no_clear_narrative")}
**Liquidity Draw:** ${narrative.liquidity_draw || "None identified"}
**Reaction Zone:** ${narrative.htf_reaction_zone || "Unclear"} (${formatLabel(narrative.reaction_zone_status || record.reaction_zone_status || "unclear")})
**Behavior:** ${formatLabel(narrative.behavior_inside_zone || record.behavior_confirmation || "none")}
**Structure Confirmation:** ${narrative.structure_confirmation || "5M unclear"}
**Execution Readiness:** ${formatLabel(narrative.execution_readiness || "not_ready")}
**Liquidity Draw Alignment:** ${formatLabel(record.liquidity_draw_alignment || "unclear")}  
**Repeat Suppressed:** ${record.repeat_suppressed ? "Yes" : "No"}  
**Presence Mode:** ${formatLabel(record.presence_mode || "home")}  
**Presence Allows Notification:** ${record.notification_allowed_by_presence ? "Yes" : "No"}  
**Alert Eligibility:** ${eligibility?.should_notify ? "Eligible" : "Not eligible"} (${eligibility?.level || "none"})

## Quick Read
${buildCompactScanSummary(record)}

## Missing Confirmations
${missingConfirmations}

## Market Changes
${marketChanges}

## Visual Context Changes
${visualChanges}

## Alert Eligibility Reasons
${eligibilityReasons}

## Alert Eligibility Blockers
${eligibilityBlockers}

## Presence Reason
${record.presence_reason || "No presence decision recorded."}

## Legacy Alert Reasons
${alertReasons}

---

${record.message || "No scan message returned."}`;
  }

  async function loadScanStatus() {
    try {
      const res = await fetch(`${API_BASE}/scan/status`);

      if (!res.ok) {
        throw new Error("Scan status request failed");
      }

      const data = await res.json();
      setScanStatus(data);
      setScanStatusError(false);
    } catch {
      setScanStatusError(true);
      console.log("Could not load scan status.");
    }
  }

  async function loadLatestScan() {
    try {
      const res = await fetch(`${API_BASE}/scan/latest`);
      const data = await res.json();

      if (data?.record) {
        setLatestScan(data.record);
        return data.record;
      }

      return null;
    } catch {
      console.log("Could not load latest scan.");
      return null;
    }
  }

  async function loadScannerSettings() {
    try {
      const res = await fetch(`${API_BASE}/scanner/settings`);

      if (!res.ok) {
        throw new Error("Scanner settings request failed");
      }

      const data = await res.json();
      const settings = data.settings || data;
      setScannerSettings(settings || null);
      return settings || null;
    } catch {
      console.log("Could not load scanner settings.");
      return null;
    }
  }

  async function updateScannerDefaultSymbol(symbol: string) {
    if (scannerSettingsLoading) return;

    setScannerSettingsLoading(true);

    try {
      const res = await fetch(`${API_BASE}/scanner/settings`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ default_symbol: symbol }),
      });

      if (!res.ok) {
        throw new Error("Scanner settings update failed");
      }

      const data = await res.json();
      setScannerSettings(data.settings || data || null);
      await loadScanStatus();
      await loadLatestScan();
    } catch {
      addAssistantMessage("Could not update scanner default symbol.", true);
    } finally {
      setScannerSettingsLoading(false);
    }
  }

  async function updateScannerEnabled(scannerEnabled: boolean) {
    if (scannerSettingsLoading) return;

    setScannerSettingsLoading(true);
    setScannerSettings((current) =>
      current ? { ...current, scanner_enabled: scannerEnabled } : current
    );
    setScanStatus((current) =>
      current
        ? {
            ...current,
            scanner_enabled: scannerEnabled,
            automatic_scans_paused: !scannerEnabled,
            scheduled_scan_allowed:
              scannerEnabled && Boolean(current.should_scan_now),
          }
        : current
    );

    try {
      const res = await fetch(`${API_BASE}/scanner/settings`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ scanner_enabled: scannerEnabled }),
      });

      if (!res.ok) {
        throw new Error("Scanner settings update failed");
      }

      const data = await res.json();
      setScannerSettings(data.settings || data || null);
      await loadScanStatus();
    } catch {
      addAssistantMessage("Could not update scanner activity setting.", true);
      await loadScannerSettings();
      await loadScanStatus();
    } finally {
      setScannerSettingsLoading(false);
    }
  }

  async function loadPresence() {
    try {
      const res = await fetch(`${API_BASE}/presence`);

      if (!res.ok) {
        throw new Error("Presence request failed");
      }

      const data = await res.json();
      setPresence(data.current || null);
    } catch {
      console.log("Could not load presence mode.");
    }
  }

  async function setPresenceMode(mode: string) {
    if (presenceLoading) return;

    setPresenceLoading(true);

    try {
      const res = await fetch(`${API_BASE}/presence`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ mode }),
      });

      if (!res.ok) {
        throw new Error("Presence update failed");
      }

      const data = await res.json();
      setPresence(data.current || null);
      await loadLatestScan();
    } catch {
      addAssistantMessage("Could not update presence mode.", true);
    } finally {
      setPresenceLoading(false);
    }
  }

  async function forceScanDefaultSymbol() {
    if (scanLoading || loading) return;

    const symbol = scannerSettings?.default_symbol || scanStatus?.symbol || "MES";
    const userMessage: Message = {
      id: generateId(),
      role: "user",
      content: `Force scan ${symbol}`,
      createdAt: new Date().toISOString(),
      source: "User",
    };

    setMessages((prev) => [...prev, userMessage]);
    setScanLoading(true);
    setLoading(true);

    try {
      const res = await fetch(`${API_BASE}/scan/force`, {
        method: "POST",
      });

      if (!res.ok) {
        throw new Error("Force scan failed");
      }

      const record: ScanRecord = await res.json();

      setLatestScan(record);
      await loadScanStatus();

      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "assistant",
          content: formatScanSummary(record),
          createdAt: new Date().toISOString(),
          source: "Scanner",
        },
      ]);
    } catch {
      addAssistantMessage(
        "Force scan failed. Check FastAPI, Playwright, TradingView, and Ollama.",
        true
      );
    } finally {
      setScanLoading(false);
      setLoading(false);
    }
  }

  async function sendMessage(messageText?: string) {
    const text = messageText ?? input;

    if ((!text.trim() && !attachedFile) || loading) return;

    const userMessage: Message = {
      id: generateId(),
      role: "user",
      content: text || `Analyze attached image: ${attachedFile?.name}`,
      createdAt: new Date().toISOString(),
      source: "User",
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      if (attachedFile) {
        const formData = new FormData();
        formData.append("file", attachedFile);
        formData.append(
          "prompt",
          text || "Analyze this chart using Jadin's Liquidity Narrative Continuation model."
        );

        const res = await fetch(`${API_BASE}/analyze-image`, {
          method: "POST",
          body: formData,
          signal: controller.signal,
        });

        if (!res.ok) throw new Error("Image analysis failed");

        const data = await res.json();

        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: "assistant",
            content: data.message || "No image analysis returned.",
            createdAt: new Date().toISOString(),
            source: "Vision",
          },
        ]);

        setAttachedFile(null);
        return;
      }

      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: text,
          tool_mode: "auto",
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error("Backend request failed");
      }

      const data = await res.json();
      const responseContent = data.message || "No response.";

      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "assistant",
          content: responseContent,
          createdAt: new Date().toISOString(),
          source: inferMessageSource(responseContent, "assistant"),
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "assistant",
          content: attachedFile
            ? "Image analysis failed. Check FastAPI/Ollama vision model."
            : "Backend connection failed. Check FastAPI.",
          error: true,
          retryText: text,
          createdAt: new Date().toISOString(),
          source: "System",
        },
      ]);
    } finally {
      abortRef.current = null;
      setLoading(false);
    }
  }

  function stopResponse() {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
    setScanLoading(false);
  }

  function deleteMessage(id: string) {
    setMessages((prev) => prev.filter((msg) => msg.id !== id));
  }

  async function clearChat() {
    try {
      await fetch(`${API_BASE}/reset`, {
        method: "POST",
      });
    } catch {
      console.log("Could not reset backend memory.");
    }

    setMessages([
      {
        id: generateId(),
        role: "assistant",
        content: "Chat cleared. Backend memory reset too.",
        createdAt: new Date().toISOString(),
        source: "System",
      },
    ]);

    messagesContainerRef.current?.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }

  async function loadHistory() {
    try {
      const res = await fetch(`${API_BASE}/history`);
      const data = await res.json();

      if (!data.history?.length) return;

      const loadedMessages: Message[] = data.history.map(
        (item: { role: string; content: string; timestamp?: string; created_at?: string }) => {
          const role = item.role.toLowerCase() === "user" ? "user" : "assistant";

          return {
          id: generateId(),
          role,
          content: item.content,
          createdAt: item.timestamp || item.created_at || new Date().toISOString(),
          source: inferMessageSource(item.content, role),
        };
        }
      );

      setMessages(loadedMessages);
    } catch {
      console.log("Could not load history.");
    }
  }

  async function handleFileUpload(file: File) {
    const isImage =
      file.type.startsWith("image/") ||
      file.name.endsWith(".png") ||
      file.name.endsWith(".jpg") ||
      file.name.endsWith(".jpeg") ||
      file.name.endsWith(".webp");

    const isTextFile =
      file.type.startsWith("text/") ||
      file.name.endsWith(".py") ||
      file.name.endsWith(".js") ||
      file.name.endsWith(".ts") ||
      file.name.endsWith(".tsx") ||
      file.name.endsWith(".json") ||
      file.name.endsWith(".md") ||
      file.name.endsWith(".txt");

    if (isImage) {
      setAttachedFile(file);
      return;
    }

    if (isTextFile) {
      const text = await file.text();
      setInput(`Attached file: ${file.name}\n\n${text.slice(0, 4000)}`);
      return;
    }

    setMessages((prev) => [
      ...prev,
      {
        id: generateId(),
        role: "assistant",
        content: `Attachment "${file.name}" is not supported yet.`,
        createdAt: new Date().toISOString(),
        source: "System",
      },
    ]);
  }

  const activeSessions =
    scanStatus?.active_sessions && scanStatus.active_sessions.length > 0
      ? scanStatus.active_sessions.join(" + ")
      : "Inactive";
  const heartbeatAgeSeconds = getAgeSeconds(scanStatus?.heartbeat_timestamp);
  const scanIntervalSeconds = scanStatus?.scan_interval_seconds || 0;
  const heartbeatIsStale =
    heartbeatAgeSeconds !== null &&
    scanIntervalSeconds > 0 &&
    heartbeatAgeSeconds > scanIntervalSeconds * 2;
  const scannerEnabled =
    scannerSettings?.scanner_enabled ?? scanStatus?.scanner_enabled ?? true;
  const scannerTone = !scannerEnabled
    ? "paused"
    : !scanStatus?.process_running
    ? "inactive"
    : heartbeatIsStale || heartbeatAgeSeconds === null
    ? "warning"
    : "active";
  const scannerBadgeClass =
    scannerTone === "active"
      ? "bg-green-500/20 text-green-200"
      : scannerTone === "paused"
      ? "bg-neutral-500/20 text-neutral-200"
      : scannerTone === "warning"
      ? "bg-yellow-500/20 text-yellow-200"
      : "bg-red-500/20 text-red-200";
  const scannerBadgeText =
    scannerTone === "active"
      ? "Active"
      : scannerTone === "paused"
      ? "Paused"
      : scannerTone === "warning"
      ? "Warning"
      : "Inactive";
  const scannerSubtitle = scanStatus?.running_scan
    ? "Scanning now..."
    : !scannerEnabled
    ? "Automatic scans paused"
    : scanStatus?.process_running && scanStatus?.should_scan_now
    ? "Watching scan window"
    : scanStatus?.process_running
    ? "Idle"
    : "Not running";
  const scannerSymbol =
    scannerSettings?.default_symbol || scanStatus?.default_symbol || scanStatus?.symbol || "MES";
  const scannerSupportedSymbols = scannerSettings?.supported_symbols?.length
    ? scannerSettings.supported_symbols
    : ["MES", "MNQ", "ES", "NQ"];

  const htfBias = latestScan?.state?.htf_bias || "unknown";
  const executionBias = latestScan?.state?.execution_bias || "unknown";
  const priceRelation = formatLabel(latestScan?.state?.price_relation);
  const signalLevel = latestScan?.signal_level || "informational";
  const narrative = latestScan?.narrative;
  const narrativeState = formatLabel(
    narrative?.narrative_phase ||
      latestScan?.narrative_phase ||
      latestScan?.narrative_state
  );
  const liquidityDraw = narrative?.liquidity_draw || "None identified";
  const reactionZone = narrative?.htf_reaction_zone || "Unclear";
  const reactionZoneStatus = formatLabel(
    narrative?.reaction_zone_status || latestScan?.reaction_zone_status
  );
  const behaviorConfirmation = formatLabel(
    narrative?.behavior_inside_zone || latestScan?.behavior_confirmation
  );
  const structureConfirmation = narrative?.structure_confirmation || "5M unclear";
  const executionReadiness = formatLabel(narrative?.execution_readiness || "not_ready");
  const missingConfirmations = narrative?.missing_confirmations || [];
  const liquidityDrawAlignment = formatLabel(latestScan?.liquidity_draw_alignment);
  const alertEligibilityLevel = latestScan?.alert_eligibility?.level || "none";
  const alertEligibilityNotify = latestScan?.alert_eligibility?.should_notify || false;
  const presenceAllows = latestScan?.notification_allowed_by_presence || false;
  const presenceModes = ["home", "trading", "away", "focus"];
  function renderComposerControls() {
    return (
      <>
      {attachedFile && (
        <div className="mb-2 flex min-w-0 max-w-full items-center justify-between rounded-xl border border-white/10 bg-neutral-900 px-3 py-2 text-xs text-neutral-300">
          <span className="min-w-0 truncate">Attached: {attachedFile.name}</span>

          <button
            type="button"
            onClick={() => setAttachedFile(null)}
            className="ml-3 text-neutral-400 underline underline-offset-4 hover:text-white"
          >
            Remove
          </button>
        </div>
      )}

      <div className="flex w-full min-w-0 max-w-full items-end gap-2 overflow-x-hidden rounded-2xl border border-white/10 bg-neutral-900 p-2 shadow-2xl">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border border-white/10 bg-neutral-950 text-xl leading-none text-neutral-300 hover:bg-white/10"
          title="Attach file"
          aria-label="Attach file"
        >
          +
        </button>

        <input
          ref={fileInputRef}
          type="file"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];

            if (file) {
              handleFileUpload(file);
            }

            e.currentTarget.value = "";
          }}
        />

        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              sendMessage();
            }
          }}
          placeholder="Ask Helix..."
          rows={1}
          className="max-h-32 min-h-11 min-w-0 flex-1 resize-none rounded-xl bg-neutral-950/70 px-3 py-3 text-sm text-white outline-none placeholder:text-neutral-500"
        />

        <button
          onClick={loading ? stopResponse : () => sendMessage()}
          className={`min-h-11 shrink-0 rounded-xl px-3 py-2 text-sm font-semibold sm:px-4 ${
            loading ? "bg-red-500 text-white" : "bg-white text-black"
          }`}
        >
          {loading ? "Stop" : "Send"}
        </button>
      </div>
      </>
    );
  }

  return (
    <main className="min-h-screen w-full max-w-full overflow-x-hidden bg-neutral-950 text-white">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-neutral-950/80 backdrop-blur">
        <div className="mx-auto flex w-full max-w-7xl flex-col gap-3 px-3 py-3 sm:px-4 lg:flex-row lg:items-center lg:justify-between lg:py-4">
          <div>
            <h1 className="text-lg font-semibold">Helix Command Center</h1>
            <p className="text-sm text-neutral-400">
              Local AI. Real tools. Full control.
            </p>
          </div>

          <div className="-mx-1 flex max-w-full gap-2 overflow-x-auto px-1 pb-1">
            <Link
              href="/"
              className="shrink-0 rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Core
            </Link>

            <Link
              href="/orbit"
              className="shrink-0 rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Orbit
            </Link>

            <Link
              href="/trade-journal"
              className="shrink-0 rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Trade Journal
            </Link>

            <button
              onClick={loadScanStatus}
              className="shrink-0 rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Refresh Status
            </button>

            <button
              onClick={clearChat}
              className="shrink-0 rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Clear
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid w-full max-w-7xl min-w-0 grid-cols-1 gap-3 overflow-x-hidden px-3 py-3 pb-32 sm:px-4 lg:grid-cols-[minmax(0,1fr)_380px] lg:gap-4 lg:py-4 lg:pb-4">
        <div className="min-w-0 max-w-full lg:hidden">
          <div className="grid w-full min-w-0 grid-cols-2 gap-2 rounded-2xl border border-white/10 bg-neutral-900 p-1">
            {(["chat", "system"] as const).map((view) => (
              <button
                key={view}
                type="button"
                onClick={() => setActiveView(view)}
                className={`min-h-11 rounded-xl px-3 py-2 text-sm font-semibold transition ${
                  activeView === view
                    ? "bg-blue-500/20 text-blue-100 ring-1 ring-blue-400/30"
                    : "text-neutral-400 hover:bg-white/[0.05] hover:text-neutral-100"
                }`}
              >
                {view === "chat" ? "Chat" : "System"}
              </button>
            ))}
          </div>
        </div>

        <section
          className={`min-w-0 max-w-full overflow-x-hidden rounded-2xl border border-white/10 bg-neutral-950 lg:flex lg:h-[calc(100vh-128px)] lg:min-h-[560px] lg:flex-col lg:overflow-hidden ${
            activeView === "system" ? "hidden lg:flex" : ""
          }`}
        >
          <div className="flex min-w-0 items-center justify-between gap-3 border-b border-white/10 px-3 py-2 text-xs text-neutral-400 sm:px-4 lg:hidden">
            <span className="min-w-0 truncate">
              {scannerSymbol} scanner · {scannerBadgeText.toLowerCase()}
            </span>
            <button
              type="button"
              onClick={() => setActiveView("system")}
              className="rounded-lg border border-white/10 px-2 py-1 font-semibold text-neutral-300"
            >
              System
            </button>
          </div>
          <div
            ref={messagesContainerRef}
            className="flex min-w-0 max-w-full flex-col gap-3 overflow-x-hidden px-3 py-4 pb-36 sm:px-4 sm:py-6 sm:pb-40 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:overflow-x-hidden lg:pb-6 lg:gap-4"
          >
            {messages.map((msg) => (
              <MessageCard
                key={msg.id}
                msg={msg}
                onDelete={deleteMessage}
                onRetry={sendMessage}
              />
            ))}

            {loading && (
              <div className="flex justify-start">
                <div className="rounded-2xl border border-white/10 bg-neutral-900 px-4 py-3 text-sm text-neutral-400">
                  <div className="flex gap-1">
                    <span className="animate-bounce">•</span>
                    <span className="animate-bounce [animation-delay:0.1s]">
                      •
                    </span>
                    <span className="animate-bounce [animation-delay:0.2s]">
                      •
                    </span>
                  </div>
                </div>
              </div>
            )}

            <div ref={bottomRef} />
          </div>

          <div className="hidden border-t border-white/10 bg-neutral-950/95 px-4 py-4 lg:block">
            {renderComposerControls()}
          </div>
        </section>

        <aside
          className={`min-w-0 max-w-full flex-col gap-3 lg:gap-4 ${
            activeView === "chat" ? "hidden lg:flex" : ""
          }`}
        >
          <section className="rounded-2xl border border-white/10 bg-neutral-900 p-3 sm:p-4">
            <div className="mb-3 flex items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold">Presence Mode</h2>
                <p className="text-xs text-neutral-400">
                  {presence?.label || "Home"} ·{" "}
                  {formatLabel(presence?.scan_noise_profile || "normal")}
                </p>
              </div>

              <span className="rounded-full border border-white/10 bg-neutral-950 px-2 py-1 text-xs text-neutral-300">
                {formatLabel(presence?.scanner_min_signal_level || "review")}+
              </span>
            </div>

            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {presenceModes.map((mode) => {
                const active = presence?.mode === mode;

                return (
                  <button
                    key={mode}
                    onClick={() => setPresenceMode(mode)}
                    disabled={presenceLoading}
                    className={`rounded-lg border px-2 py-3 text-xs font-semibold transition sm:py-2 ${
                      active
                        ? "border-blue-400/40 bg-blue-500/20 text-blue-100"
                        : "border-white/10 bg-neutral-950 text-neutral-300 hover:bg-white/10"
                    } disabled:cursor-not-allowed disabled:opacity-50`}
                  >
                    {mode === "home"
                      ? "Home"
                      : mode === "trading"
                      ? "Trading"
                      : mode === "away"
                      ? "Away"
                      : "Focus"}
                  </button>
                );
              })}
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2 text-xs">
              <div className="rounded-lg bg-neutral-950 p-2">
                <p className="text-neutral-500">Notify</p>
                <p className="mt-1 font-semibold text-neutral-200">
                  {presence?.notifications_allowed ? "On" : "Off"}
                </p>
              </div>

              <div className="rounded-lg bg-neutral-950 p-2">
                <p className="text-neutral-500">iMessage</p>
                <p className="mt-1 font-semibold text-neutral-200">
                  {presence?.imessage_allowed ? "On" : "Off"}
                </p>
              </div>

              <div className="rounded-lg bg-neutral-950 p-2">
                <p className="text-neutral-500">TTS</p>
                <p className="mt-1 font-semibold text-neutral-200">
                  {presence?.tts_allowed ? "On" : "Off"}
                </p>
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-blue-500/30 bg-blue-950/20 p-3 sm:p-4">
            <div className="mb-3 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-sm font-semibold text-blue-100">
                  {scannerSymbol} Scanner
                </h2>
                <p className="text-xs text-blue-200/70">{scannerSubtitle}</p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded-full px-2 py-1 text-xs ${scannerBadgeClass}`}
                >
                  {scannerBadgeText}
                </span>
                <div className="flex rounded-full border border-white/10 bg-neutral-950/70 p-1 text-xs">
                  <button
                    type="button"
                    onClick={() => updateScannerEnabled(true)}
                    disabled={scannerSettingsLoading}
                    className={`rounded-full px-3 py-1 font-semibold transition ${
                      scannerEnabled
                        ? "bg-green-500/20 text-green-100"
                        : "text-neutral-400 hover:text-white"
                    } disabled:cursor-not-allowed disabled:opacity-50`}
                  >
                    On
                  </button>
                  <button
                    type="button"
                    onClick={() => updateScannerEnabled(false)}
                    disabled={scannerSettingsLoading}
                    className={`rounded-full px-3 py-1 font-semibold transition ${
                      !scannerEnabled
                        ? "bg-neutral-500/30 text-neutral-100"
                        : "text-neutral-400 hover:text-white"
                    } disabled:cursor-not-allowed disabled:opacity-50`}
                  >
                    Off
                  </button>
                </div>
              </div>
            </div>

            {scanStatusError ? (
              <div className="mb-3 rounded-xl border border-yellow-500/20 bg-yellow-950/30 px-3 py-2 text-xs text-yellow-100">
                Status unavailable.
              </div>
            ) : (
              <div className="mb-3 grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
                <div className="rounded-xl bg-neutral-950/70 p-3">
                  <p className="text-neutral-500">Process</p>
                  <p className="mt-1 font-semibold text-neutral-100">
                    {scanStatus?.process_running ? "Running" : "Not running"}
                  </p>
                </div>

                <div className="rounded-xl bg-neutral-950/70 p-3">
                  <p className="text-neutral-500">Running scan</p>
                  <p className="mt-1 font-semibold text-neutral-100">
                    {scanStatus?.running_scan ? "Yes" : "No"}
                  </p>
                </div>

                <div className="rounded-xl bg-neutral-950/70 p-3">
                  <p className="text-neutral-500">Heartbeat age</p>
                  <p className="mt-1 font-semibold text-neutral-100">
                    {formatRelativeAge(scanStatus?.heartbeat_timestamp)}
                  </p>
                </div>

                <div className="rounded-xl bg-neutral-950/70 p-3">
                  <p className="text-neutral-500">Last scan age</p>
                  <p className="mt-1 font-semibold text-neutral-100">
                    {formatRelativeAge(scanStatus?.last_scan_timestamp)}
                  </p>
                </div>

                <div className="rounded-xl bg-neutral-950/70 p-3">
                  <p className="text-neutral-500">Last success</p>
                  <p className="mt-1 font-semibold text-neutral-100">
                    {scanStatus?.latest_scan_success === null ||
                    scanStatus?.latest_scan_success === undefined
                      ? "Unknown"
                      : scanStatus.latest_scan_success
                      ? "Yes"
                      : "No"}
                  </p>
                </div>

                <div className="rounded-xl bg-neutral-950/70 p-3">
                  <p className="text-neutral-500">Next interval</p>
                  <p className="mt-1 font-semibold text-neutral-100">
                    {scanStatus?.scan_interval_seconds
                      ? `${Math.round(scanStatus.scan_interval_seconds / 60)}m`
                      : "Unknown"}
                  </p>
                </div>
              </div>
            )}

            <div className="mb-3">
              <p className="mb-2 text-xs text-blue-200/70">Default symbol</p>
              <div className="flex flex-wrap gap-2">
                {scannerSupportedSymbols.map((symbol) => {
                  const active = symbol === scannerSymbol;

                  return (
                    <button
                      key={symbol}
                      type="button"
                      onClick={() => updateScannerDefaultSymbol(symbol)}
                      disabled={scannerSettingsLoading}
                      className={`min-w-14 flex-1 rounded-lg border px-3 py-3 text-xs font-semibold transition sm:flex-none sm:py-2 ${
                        active
                          ? "border-blue-400/40 bg-blue-500/20 text-blue-100"
                          : "border-white/10 bg-neutral-950/70 text-neutral-300 hover:bg-white/10"
                      } disabled:cursor-not-allowed disabled:opacity-50`}
                    >
                      {symbol}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="mb-3 rounded-xl bg-neutral-950/70 p-3 text-xs">
              <p className="text-neutral-500">Active sessions</p>
              <p className="mt-1 font-semibold text-neutral-100">
                {activeSessions}
              </p>
            </div>

            <div className="grid gap-2 sm:grid-cols-2">
              <button
                onClick={forceScanDefaultSymbol}
                disabled={scanLoading || loading}
                className="rounded-xl bg-blue-600 px-3 py-3 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50 sm:py-2"
              >
                {scanLoading ? "Scanning..." : `Run Manual Scan ${scannerSymbol}`}
              </button>

              <button
                onClick={async () => {
                  const record = await loadLatestScan();

                  if (record) {
                    addAssistantMessage(formatScanSummary(record));
                  } else {
                    addAssistantMessage(
                      `No latest ${scannerSymbol} scan found yet. Run Scan ${scannerSymbol} first.`,
                      true
                    );
                  }
                }}
                className="rounded-xl border border-white/10 px-3 py-3 text-sm text-neutral-200 hover:bg-white/10 sm:py-2"
              >
                Latest Scan
              </button>
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-neutral-900 p-3 sm:p-4">
            <h2 className="mb-3 text-sm font-semibold">Latest Scan Summary</h2>

            <div className="rounded-xl border border-white/10 bg-neutral-950 p-3 text-sm text-neutral-200">
              {buildCompactScanSummary(latestScan)}
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-neutral-900 p-3 sm:p-4">
            <h2 className="mb-3 text-sm font-semibold">Latest State</h2>

            {latestScan ? (
              <div className="space-y-3 text-sm">
                <div className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">HTF bias</p>
                    <span
                      className={`mt-2 inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${getBiasBadgeClass(
                        htfBias
                      )}`}
                    >
                      {formatLabel(htfBias)}
                    </span>
                  </div>

                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">Execution</p>
                    <span
                      className={`mt-2 inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${getBiasBadgeClass(
                        executionBias
                      )}`}
                    >
                      {formatLabel(executionBias)}
                    </span>
                  </div>

                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">Price relation</p>
                    <p className="mt-2 font-semibold text-neutral-200">
                      {priceRelation}
                    </p>
                  </div>

                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">Signal</p>
                    <span
                      className={`mt-2 inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${getSignalBadgeClass(
                        signalLevel
                      )}`}
                    >
                      {formatLabel(signalLevel)}
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-2 text-xs sm:grid-cols-2">
                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">Narrative Phase</p>
                    <p className="mt-2 font-semibold text-neutral-200">
                      {narrativeState}
                    </p>
                  </div>

                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">Liquidity Draw</p>
                    <p className="mt-2 font-semibold text-neutral-200">
                      {liquidityDraw}
                    </p>
                  </div>

                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">Reaction Zone</p>
                    <p className="mt-2 font-semibold text-neutral-200">
                      {reactionZone}
                    </p>
                    <p className="mt-1 text-neutral-500">{reactionZoneStatus}</p>
                  </div>

                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">Behavior</p>
                    <p className="mt-2 font-semibold text-neutral-200">
                      {behaviorConfirmation}
                    </p>
                  </div>

                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">Structure Confirmation</p>
                    <p className="mt-2 font-semibold text-neutral-200">
                      {structureConfirmation}
                    </p>
                  </div>

                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">Execution Readiness</p>
                    <p className="mt-2 font-semibold text-neutral-200">
                      {executionReadiness}
                    </p>
                  </div>

                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">Liquidity Alignment</p>
                    <p className="mt-2 font-semibold text-neutral-200">
                      {liquidityDrawAlignment}
                    </p>
                  </div>
                </div>

                <div className="rounded-xl bg-neutral-950 p-3 text-xs">
                  <p className="mb-1 text-neutral-500">Missing Confirmations</p>
                  {missingConfirmations.length ? (
                    <ul className="list-disc space-y-1 pl-5 text-neutral-300">
                      {missingConfirmations.slice(0, 4).map((item, index) => (
                        <li key={`${item}-${index}`}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="text-neutral-300">
                      No missing confirmations recorded.
                    </p>
                  )}
                </div>

                <div className="rounded-xl bg-neutral-950 p-3 text-xs">
                  <p className="mb-1 text-neutral-500">Alert eligibility</p>
                  <p className="text-neutral-200">
                    {alertEligibilityNotify ? "Eligible" : "Not eligible"} ·{" "}
                    {formatLabel(alertEligibilityLevel)}
                    {latestScan.repeat_suppressed ? " · repeat suppressed" : ""}
                  </p>
                </div>

                <div className="rounded-xl bg-neutral-950 p-3 text-xs">
                  <p className="mb-1 text-neutral-500">Presence gate</p>
                  <p className="text-neutral-200">
                    {formatLabel(latestScan.presence_mode || "home")} ·{" "}
                    {presenceAllows ? "allows" : "blocks"}
                  </p>
                  <p className="mt-1 text-neutral-400">
                    {latestScan.presence_reason || "No presence decision recorded."}
                  </p>
                </div>

                <div className="rounded-xl bg-neutral-950 p-3 text-xs">
                  <p className="mb-1 text-neutral-500">Last scan</p>
                  <p className="break-words text-neutral-200">
                    {formatTimestamp(latestScan.timestamp)}
                  </p>
                </div>

                <div className="rounded-xl bg-neutral-950 p-3 text-xs">
                  <p className="mb-1 text-neutral-500">Screenshot</p>
                  <p className="break-words text-neutral-300">
                    {getFileName(latestScan.screenshot_path)}
                  </p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-neutral-400">
                No scan loaded yet. Run Scan {scannerSymbol}.
              </p>
            )}
          </section>

          <section className="rounded-2xl border border-white/10 bg-neutral-900 p-3 sm:p-4">
            <h2 className="mb-3 text-sm font-semibold">Alert Decision</h2>

            {latestScan?.alert ? (
              <div className="space-y-2 text-sm">
                <p>
                  <span className="text-neutral-400">Eligibility:</span>{" "}
                  {alertEligibilityNotify ? "Yes" : "No"} ({alertEligibilityLevel})
                </p>
                <p>
                  <span className="text-neutral-400">Should alert:</span>{" "}
                  {latestScan.alert.should_alert ? "Yes" : "No"}
                </p>
                <p>
                  <span className="text-neutral-400">Type:</span>{" "}
                  {latestScan.alert.alert_type || "none"}
                </p>
                <p>
                  <span className="text-neutral-400">Severity:</span>{" "}
                  {latestScan.alert.severity || "none"}
                </p>

                <div className="pt-2">
                  <p className="mb-1 text-xs text-neutral-500">Reasons</p>
                  <ul className="list-disc space-y-1 pl-5 text-xs text-neutral-300">
                    {(latestScan.alert.reasons || []).map((reason, index) => (
                      <li key={`${reason}-${index}`}>{reason}</li>
                    ))}
                  </ul>
                </div>
              </div>
            ) : (
              <p className="text-sm text-neutral-400">
                No alert decision loaded.
              </p>
            )}
          </section>
        </aside>
      </div>

      <footer
        className={`fixed bottom-0 left-0 right-0 max-w-full overflow-x-hidden border-t border-white/10 bg-neutral-950/90 backdrop-blur lg:hidden ${
          activeView === "system" ? "hidden" : ""
        }`}
      >
        <div className="mx-auto w-full max-w-7xl min-w-0 px-3 py-3 sm:px-4 sm:py-4">
          {renderComposerControls()}
        </div>
      </footer>
    </main>
  );
}
