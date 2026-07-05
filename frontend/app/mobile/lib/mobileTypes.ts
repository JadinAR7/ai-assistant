export type MobileTabId = "home" | "chat" | "schedule" | "trading" | "journal";

export type PresenceMode = {
  mode?: string;
  label?: string;
  description?: string;
  notifications_allowed?: boolean;
  tts_allowed?: boolean;
  imessage_allowed?: boolean;
};

export type MorningBriefing = {
  success?: boolean;
  generated_at?: string;
  major_event?: {
    title?: string;
    days_remaining?: number | null;
    progress_percent?: number | null;
  } | null;
  readiness?: {
    overall?: number | null;
  };
  top_tasks?: Array<{
    id: number;
    title: string;
    status?: string;
    due_date?: string | null;
    priority_score?: number | null;
    milestone_title?: string | null;
  }>;
  current_blockers?: string[];
  suggested_next_action?: string;
  trading_performance?: {
    trading_total_pnl_30d?: number | null;
    trade_count_30d?: number | null;
    winning_days_30d?: number | null;
    losing_days_30d?: number | null;
    latest_trade_date?: string | null;
  };
};

export type ScheduleBlock = {
  id: number;
  title?: string | null;
  block_type: "fixed" | "flexible";
  category: string;
  day_of_week?: string | null;
  specific_date?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  duration_minutes?: number | null;
  active?: boolean;
  priority?: string;
};

export type ScanStatus = {
  scanner_enabled?: boolean;
  process_running?: boolean;
  running_scan?: boolean;
  latest_scan_success?: boolean | null;
  last_scan_timestamp?: string | null;
  heartbeat_timestamp?: string | null;
  csv_automation_paused?: boolean;
  csv_automation_status?: string;
  csv_automation_message?: string;
  default_symbol?: string;
  symbol?: string;
};

export type ScanRecord = {
  timestamp?: string;
  symbol?: string;
  signal_level?: string;
  narrative_state?: string;
  narrative_phase?: string;
  system_health?: {
    status?: string;
    severity?: string;
  };
  narrative?: {
    narrative_phase?: string;
    execution_readiness?: string;
    behavior_inside_zone?: string;
  };
};

export type PerformanceCalendarDay = {
  date: string;
  total_pnl: number;
  trade_count: number;
  win_count?: number;
  loss_count?: number;
  net_result?: string;
};

export type PerformanceCalendar = {
  summary?: {
    total_pnl?: number | null;
    trade_count?: number | null;
    winning_days?: number | null;
    losing_days?: number | null;
  };
  days?: PerformanceCalendarDay[];
};

export type JournalEntry = {
  id: number;
  trade_date?: string;
  symbol?: string;
  direction?: string;
  result_dollars?: number | null;
  strategy_mode?: string | null;
};

export type MobileReminder = {
  id: number;
  title: string;
  body?: string | null;
  due_at: string;
  status: "pending" | "done" | "dismissed";
  source: "chat" | "manual" | "schedule" | "scanner" | "system";
  created_at: string;
  completed_at?: string | null;
  dismissed_at?: string | null;
};

export type MobileNotification = {
  id: number;
  title: string;
  body?: string | null;
  type: "trading" | "schedule" | "task" | "system";
  status: "unread" | "read" | "dismissed" | "completed";
  priority: "low" | "normal" | "high";
  target?: {
    kind?: string | null;
    value?: string | null;
  } | null;
  created_at: string;
  acknowledged_at?: string | null;
  completed_at?: string | null;
  dismissed_at?: string | null;
};

export type MobileNotificationCenter = {
  reminders: MobileReminder[];
  notifications: MobileNotification[];
  next_reminder?: MobileReminder | null;
  unread_count: number;
  pending_count: number;
};

export type MobileData = {
  briefing: MorningBriefing | null;
  presence: PresenceMode | null;
  scheduleBlocks: ScheduleBlock[];
  scanStatus: ScanStatus | null;
  latestScan: ScanRecord | null;
  performanceCalendar: PerformanceCalendar | null;
  journalEntries: JournalEntry[];
  notificationCenter: MobileNotificationCenter | null;
  backendReachable: boolean;
  loadErrors: {
    briefing?: boolean;
    presence?: boolean;
    schedule?: boolean;
    scannerStatus?: boolean;
    latestScan?: boolean;
    performanceCalendar?: boolean;
    journalEntries?: boolean;
    notifications?: boolean;
  };
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  status?: "sending" | "sent" | "failed";
  retryOfMessageId?: string;
  error?: boolean;
};

export type MobileActionResult = {
  title: string;
  message: string;
  error?: boolean;
};
