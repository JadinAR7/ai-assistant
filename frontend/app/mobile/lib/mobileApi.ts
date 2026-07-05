import {
  type JournalEntry,
  type MobileData,
  type MobileNotification,
  type MobileNotificationCenter,
  type MobileReminder,
  type MorningBriefing,
  type PerformanceCalendar,
  type PresenceMode,
  type ScanRecord,
  type ScanStatus,
  type ScheduleBlock,
} from "./mobileTypes";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export const emptyMobileData: MobileData = {
  briefing: null,
  presence: null,
  scheduleBlocks: [],
  scanStatus: null,
  latestScan: null,
  performanceCalendar: null,
  journalEntries: [],
  notificationCenter: null,
  backendReachable: false,
  loadErrors: {},
};

export type MobileChatErrorReason = "offline" | "timeout" | "parse" | "unknown";

export class MobileChatError extends Error {
  reason: MobileChatErrorReason;

  constructor(reason: MobileChatErrorReason, message: string) {
    super(message);
    this.name = "MobileChatError";
    this.reason = reason;
  }
}

type ChatResponse = {
  message?: string;
  detail?: string;
  error?: string;
};

type FetchResult<T> = {
  data: T | null;
  error: boolean;
};

async function fetchJson<T>(path: string): Promise<FetchResult<T>> {
  try {
    const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!response.ok) return { data: null, error: true };
    return { data: (await response.json()) as T, error: false };
  } catch {
    return { data: null, error: true };
  }
}

function monthKey(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

export async function fetchMobileData(): Promise<MobileData> {
  const [
    healthResult,
    briefingResult,
    presenceResult,
    scheduleResult,
    scanStatusResult,
    latestScanResult,
    performanceResult,
    journalResult,
    notificationResult,
  ] = await Promise.all([
    fetchJson<{ status?: string }>("/"),
    fetchJson<MorningBriefing>("/orbit/morning-briefing"),
    fetchJson<{ current?: PresenceMode | null }>("/presence"),
    fetchJson<ScheduleBlock[]>("/orbit/schedule-blocks"),
    fetchJson<ScanStatus>("/scan/status"),
    fetchJson<{
      record?: ScanRecord | null;
      latest_successful_market_scan?: ScanRecord | null;
    }>("/scan/latest"),
    fetchJson<PerformanceCalendar>(
      `/orbit/trade-journal/performance-calendar?month=${monthKey()}&source=all`,
    ),
    fetchJson<JournalEntry[]>("/orbit/trade-journal"),
    fetchJson<MobileNotificationCenter>("/mobile/notifications"),
  ]);
  const health = healthResult.data;
  const briefing = briefingResult.data;
  const presenceResponse = presenceResult.data;
  const scheduleBlocks = scheduleResult.data;
  const scanStatus = scanStatusResult.data;
  const latestScanResponse = latestScanResult.data;
  const performanceCalendar = performanceResult.data;
  const journalEntries = journalResult.data;
  const notificationCenter = notificationResult.data;

  return {
    briefing,
    presence: presenceResponse?.current ?? null,
    scheduleBlocks: Array.isArray(scheduleBlocks) ? scheduleBlocks : [],
    scanStatus,
    latestScan:
      latestScanResponse?.record ??
      latestScanResponse?.latest_successful_market_scan ??
      null,
    performanceCalendar,
    journalEntries: Array.isArray(journalEntries) ? journalEntries.slice(0, 5) : [],
    notificationCenter,
    backendReachable: Boolean(health),
    loadErrors: {
      briefing: briefingResult.error,
      presence: presenceResult.error,
      schedule: scheduleResult.error,
      scannerStatus: scanStatusResult.error,
      latestScan: latestScanResult.error,
      performanceCalendar: performanceResult.error,
      journalEntries: journalResult.error,
      notifications: notificationResult.error,
    },
  };
}

export async function sendMobileChat(message: string) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 120000);

  try {
    const response = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, tool_mode: "auto" }),
      signal: controller.signal,
    });

    let data: ChatResponse;
    try {
      data = (await response.json()) as ChatResponse;
    } catch {
      throw new MobileChatError(
        "parse",
        "Helix responded, but Mobile Chat could not read the response.",
      );
    }

    if (!response.ok) {
      throw new MobileChatError(
        "unknown",
        data.detail || data.error || `Chat failed with ${response.status}`,
      );
    }

    return data as { message?: string };
  } catch (error) {
    if (error instanceof MobileChatError) {
      throw error;
    }
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new MobileChatError("timeout", "Chat request timed out");
    }
    throw new MobileChatError("offline", "Chat backend is unreachable");
  } finally {
    window.clearTimeout(timeout);
  }
}

export async function runMobileScanner(symbol: string) {
  await fetch(`${API_BASE}/scan/force`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ symbol }),
  });
}

async function postMobileAction<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method: "POST" });
  if (!response.ok) {
    try {
      const data = (await response.json()) as { detail?: string; error?: string };
      throw new Error(
        data.detail || data.error || `Mobile action failed with ${response.status}`,
      );
    } catch (error) {
      if (error instanceof Error) throw error;
      throw new Error(`Mobile action failed with ${response.status}`);
    }
  }
  return (await response.json()) as T;
}

export function completeMobileReminder(id: number) {
  return postMobileAction<MobileReminder>(`/mobile/reminders/${id}/complete`);
}

export function dismissMobileReminder(id: number) {
  return postMobileAction<MobileReminder>(`/mobile/reminders/${id}/dismiss`);
}

export function ackMobileNotification(id: number) {
  return postMobileAction<MobileNotification>(`/mobile/notifications/${id}/ack`);
}

export function dismissMobileNotification(id: number) {
  return postMobileAction<MobileNotification>(
    `/mobile/notifications/${id}/dismiss`,
  );
}

export function completeMobileNotification(id: number) {
  return postMobileAction<MobileNotification>(
    `/mobile/notifications/${id}/complete`,
  );
}

export function completeMobileScheduleBlock(id: number) {
  return postMobileAction<ScheduleBlock>(`/mobile/schedule-blocks/${id}/done`);
}

export function startMobileScheduleBlock(id: number) {
  return postMobileAction<ScheduleBlock>(`/mobile/schedule-blocks/${id}/start`);
}

export function rollMobileScheduleBlockLater(id: number) {
  return postMobileAction<ScheduleBlock>(
    `/mobile/schedule-blocks/${id}/roll-later`,
  );
}

export function rollMobileScheduleBlockTomorrow(id: number) {
  return postMobileAction<ScheduleBlock>(
    `/mobile/schedule-blocks/${id}/roll-tomorrow`,
  );
}
