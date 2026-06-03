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
};

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
  reaction_zone_status?: string;
  behavior_confirmation?: string;
  liquidity_draw_alignment?: string;
  repeat_suppressed?: boolean;
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

function getAlertBadgeClass(shouldAlert?: boolean, severity?: string) {
  if (!shouldAlert) {
    return "bg-neutral-800 text-neutral-300 border-white/10";
  }

  if (severity === "high") {
    return "bg-red-500/15 text-red-300 border-red-500/20";
  }

  if (severity === "medium") {
    return "bg-yellow-500/15 text-yellow-300 border-yellow-500/20";
  }

  return "bg-blue-500/15 text-blue-300 border-blue-500/20";
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
  const behavior = formatLabel(record.behavior_confirmation || "none");
  const eligibility = record.alert_eligibility?.should_notify
    ? "eligible"
    : "not notification-worthy";

  return `Signal ${signal}. HTF ${htf}, execution ${execution}. Price relation: ${relation}. Behavior: ${behavior}. Alert eligibility: ${eligibility}.`;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: generateId(),
      role: "assistant",
      content: "What’s good, Jadin? Helix is online.",
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [scanLoading, setScanLoading] = useState(false);
  const [latestScan, setLatestScan] = useState<ScanRecord | null>(null);
  const [scanStatus, setScanStatus] = useState<ScanStatus | null>(null);
  const [scanStatusError, setScanStatusError] = useState(false);

  const bottomRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);

  const [toolMode, setToolMode] = useState("auto");
  const [attachedFile, setAttachedFile] = useState<File | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
    loadHistory();
    loadScanStatus();
    loadLatestScan();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      loadScanStatus();
    }, 12_000);

    return () => window.clearInterval(timer);
  }, []);

  function addAssistantMessage(content: string, error = false) {
    setMessages((prev) => [
      ...prev,
      {
        id: generateId(),
        role: "assistant",
        content,
        error,
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

    return `## Latest MES Scan

**Session:** ${record.session_label || "Unknown"}  
**Time:** ${formatTimestamp(record.timestamp)}  
**Vision:** ${record.vision_success ? "Success" : "Failed"}  
**CSV:** ${record.csv_success ? "Success" : "Failed"}  
**Signal Level:** ${formatLabel(record.signal_level || "informational")}  
**Narrative State:** ${formatLabel(record.narrative_state || "no_clear_narrative")}  
**Reaction Zone Status:** ${formatLabel(record.reaction_zone_status || "unclear")}  
**Behavior Confirmation:** ${formatLabel(record.behavior_confirmation || "none")}  
**Liquidity Draw Alignment:** ${formatLabel(record.liquidity_draw_alignment || "unclear")}  
**Repeat Suppressed:** ${record.repeat_suppressed ? "Yes" : "No"}  
**Alert Eligibility:** ${eligibility?.should_notify ? "Eligible" : "Not eligible"} (${eligibility?.level || "none"})

## Quick Read
${buildCompactScanSummary(record)}

## Market Changes
${marketChanges}

## Visual Context Changes
${visualChanges}

## Alert Eligibility Reasons
${eligibilityReasons}

## Alert Eligibility Blockers
${eligibilityBlockers}

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

  async function forceScanMES() {
    if (scanLoading || loading) return;

    const userMessage: Message = {
      id: generateId(),
      role: "user",
      content: "Force scan MES",
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
          tool_mode: toolMode,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error("Backend request failed");
      }

      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "assistant",
          content: data.message || "No response.",
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
        (item: { role: string; content: string }) => ({
          id: generateId(),
          role: item.role.toLowerCase() === "user" ? "user" : "assistant",
          content: item.content,
        })
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
  const scannerTone = !scanStatus?.process_running
    ? "inactive"
    : heartbeatIsStale || heartbeatAgeSeconds === null
    ? "warning"
    : "active";
  const scannerBadgeClass =
    scannerTone === "active"
      ? "bg-green-500/20 text-green-200"
      : scannerTone === "warning"
      ? "bg-yellow-500/20 text-yellow-200"
      : "bg-red-500/20 text-red-200";
  const scannerBadgeText =
    scannerTone === "active"
      ? "Active"
      : scannerTone === "warning"
      ? "Warning"
      : "Inactive";
  const scannerSubtitle = scanStatus?.running_scan
    ? "Scanning now..."
    : scanStatus?.process_running && scanStatus?.should_scan_now
    ? "Watching scan window"
    : scanStatus?.process_running
    ? "Idle"
    : "Not running";

  const htfBias = latestScan?.state?.htf_bias || "unknown";
  const executionBias = latestScan?.state?.execution_bias || "unknown";
  const priceRelation = formatLabel(latestScan?.state?.price_relation);
  const alertShouldFire = latestScan?.alert?.should_alert || false;
  const alertSeverity = latestScan?.alert?.severity || "none";
  const signalLevel = latestScan?.signal_level || "informational";
  const narrativeState = formatLabel(latestScan?.narrative_state);
  const reactionZoneStatus = formatLabel(latestScan?.reaction_zone_status);
  const behaviorConfirmation = formatLabel(latestScan?.behavior_confirmation);
  const liquidityDrawAlignment = formatLabel(latestScan?.liquidity_draw_alignment);
  const alertEligibilityLevel = latestScan?.alert_eligibility?.level || "none";
  const alertEligibilityNotify = latestScan?.alert_eligibility?.should_notify || false;

  return (
    <main className="min-h-screen bg-neutral-950 text-white">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-neutral-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <div>
            <h1 className="text-lg font-semibold">Helix Command Center</h1>
            <p className="text-sm text-neutral-400">
              Local AI. Real tools. Full control.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Core
            </Link>

            <Link
              href="/orbit"
              className="rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Orbit
            </Link>

            <Link
              href="/trade-journal"
              className="rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Trade Journal
            </Link>

            <button
              onClick={loadScanStatus}
              className="rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Refresh Status
            </button>

            <button
              onClick={clearChat}
              className="rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Clear
            </button>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 px-4 py-4 pb-36 lg:grid-cols-[1fr_380px]">
        <section className="min-h-[70vh] overflow-hidden rounded-2xl border border-white/10 bg-neutral-950">
          <div
            ref={messagesContainerRef}
            className="flex max-h-[calc(100vh-190px)] flex-col gap-4 overflow-y-auto px-4 py-6"
          >
            {messages.map((msg) => (
              <div
                key={msg.id}
                className={`group flex ${
                  msg.role === "user" ? "justify-end" : "justify-start"
                }`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-lg ${
                    msg.role === "user"
                      ? "bg-blue-600 text-white"
                      : msg.error
                      ? "border border-red-500/30 bg-red-950/40 text-red-100"
                      : "border border-white/10 bg-neutral-900 text-neutral-100"
                  }`}
                >
                  <div className="prose prose-invert max-w-none prose-p:my-2 prose-headings:my-3 prose-ul:my-2 prose-li:my-1">
                    {msg.content.startsWith("TOOL:") ? (
                      "Using tool..."
                    ) : (
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    )}
                  </div>

                  <div className="mt-2 flex gap-3 opacity-70">
                    <button
                      onClick={() => navigator.clipboard.writeText(msg.content)}
                      className="text-xs text-neutral-400 underline underline-offset-4 hover:text-white"
                    >
                      Copy
                    </button>

                    {msg.error && msg.retryText && (
                      <button
                        onClick={() => sendMessage(msg.retryText)}
                        className="text-xs text-red-200 underline underline-offset-4"
                      >
                        Retry
                      </button>
                    )}

                    <button
                      onClick={() => deleteMessage(msg.id)}
                      className="text-xs text-neutral-400 underline underline-offset-4 hover:text-white"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
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
        </section>

        <aside className="flex flex-col gap-4">
          <section className="rounded-2xl border border-blue-500/30 bg-blue-950/20 p-4">
            <div className="mb-3 flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-blue-100">
                  MES Scanner
                </h2>
                <p className="text-xs text-blue-200/70">{scannerSubtitle}</p>
              </div>

              <span
                className={`rounded-full px-2 py-1 text-xs ${scannerBadgeClass}`}
              >
                {scannerBadgeText}
              </span>
            </div>

            {scanStatusError ? (
              <div className="mb-3 rounded-xl border border-yellow-500/20 bg-yellow-950/30 px-3 py-2 text-xs text-yellow-100">
                Status unavailable.
              </div>
            ) : (
              <div className="mb-3 grid grid-cols-2 gap-2 text-xs">
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

            <div className="mb-3 rounded-xl bg-neutral-950/70 p-3 text-xs">
              <p className="text-neutral-500">Active sessions</p>
              <p className="mt-1 font-semibold text-neutral-100">
                {activeSessions}
              </p>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={forceScanMES}
                disabled={scanLoading || loading}
                className="rounded-xl bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-500 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {scanLoading ? "Scanning..." : "Scan MES"}
              </button>

              <button
                onClick={async () => {
                  const record = await loadLatestScan();

                  if (record) {
                    addAssistantMessage(formatScanSummary(record));
                  } else {
                    addAssistantMessage(
                      "No latest scan found yet. Run Scan MES first.",
                      true
                    );
                  }
                }}
                className="rounded-xl border border-white/10 px-3 py-2 text-sm text-neutral-200 hover:bg-white/10"
              >
                Latest Scan
              </button>
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-neutral-900 p-4">
            <h2 className="mb-3 text-sm font-semibold">Latest Scan Summary</h2>

            <div className="rounded-xl border border-white/10 bg-neutral-950 p-3 text-sm text-neutral-200">
              {buildCompactScanSummary(latestScan)}
            </div>
          </section>

          <section className="rounded-2xl border border-white/10 bg-neutral-900 p-4">
            <h2 className="mb-3 text-sm font-semibold">Latest State</h2>

            {latestScan ? (
              <div className="space-y-3 text-sm">
                <div className="grid grid-cols-2 gap-2 text-xs">
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

                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">Narrative</p>
                    <p className="mt-2 font-semibold text-neutral-200">
                      {narrativeState}
                    </p>
                  </div>

                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">Reaction zone</p>
                    <p className="mt-2 font-semibold text-neutral-200">
                      {reactionZoneStatus}
                    </p>
                  </div>

                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">Behavior</p>
                    <p className="mt-2 font-semibold text-neutral-200">
                      {behaviorConfirmation}
                    </p>
                  </div>

                  <div className="rounded-xl bg-neutral-950 p-3">
                    <p className="text-neutral-500">Liquidity alignment</p>
                    <p className="mt-2 font-semibold text-neutral-200">
                      {liquidityDrawAlignment}
                    </p>
                  </div>
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
                No scan loaded yet. Run Scan MES.
              </p>
            )}
          </section>

          <section className="rounded-2xl border border-white/10 bg-neutral-900 p-4">
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

      <footer className="fixed bottom-0 left-0 right-0 border-t border-white/10 bg-neutral-950/90 backdrop-blur">
        <div className="mx-auto max-w-7xl px-4 py-4">
          {attachedFile && (
            <div className="mb-2 flex items-center justify-between rounded-xl border border-white/10 bg-neutral-900 px-3 py-2 text-xs text-neutral-300">
              <span className="truncate">Attached: {attachedFile.name}</span>

              <button
                type="button"
                onClick={() => setAttachedFile(null)}
                className="ml-3 text-neutral-400 underline underline-offset-4 hover:text-white"
              >
                Remove
              </button>
            </div>
          )}

          <div className="flex gap-2 rounded-2xl border border-white/10 bg-neutral-900 p-2 shadow-2xl">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="rounded-xl border border-white/10 px-3 text-lg text-neutral-400 hover:bg-white/10"
              title="Attach file"
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

            <select
              value={toolMode}
              onChange={(e) => setToolMode(e.target.value)}
              className="rounded-xl border border-white/10 bg-neutral-950 px-2 text-xs text-neutral-300 outline-none"
            >
              <option value="auto">Auto</option>
              <option value="market_csv">Market CSV</option>
              <option value="analyze_tradingview">TradingView</option>
            </select>

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
              className="min-h-11 flex-1 resize-none bg-transparent px-3 py-2 text-sm text-white outline-none placeholder:text-neutral-500"
            />

            <button
              onClick={loading ? stopResponse : () => sendMessage()}
              className={`rounded-xl px-4 py-2 text-sm font-semibold ${
                loading ? "bg-red-500 text-white" : "bg-white text-black"
              }`}
            >
              {loading ? "Stop" : "Send"}
            </button>
          </div>
        </div>
      </footer>
    </main>
  );
}
