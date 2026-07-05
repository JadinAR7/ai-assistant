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
};

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const response = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
    if (!response.ok) return null;
    return (await response.json()) as T;
  } catch {
    return null;
  }
}

function monthKey(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}`;
}

export async function fetchMobileData(): Promise<MobileData> {
  const [
    health,
    briefing,
    presenceResponse,
    scheduleBlocks,
    scanStatus,
    latestScanResponse,
    performanceCalendar,
    journalEntries,
    notificationCenter,
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
  };
}

export async function sendMobileChat(message: string) {
  const response = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, tool_mode: "auto" }),
  });

  if (!response.ok) {
    throw new Error(`Chat failed with ${response.status}`);
  }

  return (await response.json()) as { message?: string };
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
    throw new Error(`Mobile action failed with ${response.status}`);
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
