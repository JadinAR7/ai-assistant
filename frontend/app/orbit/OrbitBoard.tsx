"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import InboxTaskControls, {
  type InboxTask,
  type TaskComposerPrefill,
} from "./InboxTaskControls";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const CORPORATE_ESCAPE_TITLE = "Corporate Escape";
const INBOX_MILESTONE_TITLE = "Inbox / General";

export type MajorEventStatus = "active" | "paused" | "completed" | "archived";

export type MajorEvent = {
  id: number;
  title: string;
  description: string | null;
  target_date: string | null;
  status: MajorEventStatus;
  progress_percent: number;
  calculated_progress_percent?: number | null;
};

export type Milestone = {
  id: number;
  major_event_id: number;
  title: string;
  description: string | null;
  status: string;
  progress_percent: number;
  target_value: number | null;
  current_value: number | null;
  due_date: string | null;
};

export type MilestoneProgressAdvisory = {
  milestone_id: number;
  total_linked_tasks: number;
  completed_linked_tasks: number;
  open_linked_tasks: number;
  in_progress_linked_tasks: number;
  queued_linked_tasks: number;
  suggested_task_completion_percent: number | null;
  reason: string | null;
};

export type MilestoneProgressHistory = {
  id: number;
  milestone_id: number;
  milestone_title?: string | null;
  previous_progress: number;
  new_progress: number;
  change_amount: number;
  reason?: string | null;
  source: "manual" | "task_advisory" | "helix_tool" | "system";
  created_at: string;
};

export type OrbitReview = {
  id: number | string;
  title?: string | null;
  review_type: string;
  summary?: string | null;
  rating?: number | string | null;
  created_at?: string | null;
};

export type ReadinessCategory = {
  id: number;
  major_event_id: number;
  category_name: string;
  current_score: number;
  target_score: number;
  notes: string | null;
  last_updated: string;
};

export type MorningBriefingTask = {
  id: number;
  title: string;
  description?: string | null;
  status: string;
  due_date: string | null;
  completed_at?: string | null;
  goal_id: number;
  priority_score?: number;
  priority_factors?: string[];
  milestones?: Array<{
    id: number;
    title: string;
    status: string;
    progress_percent: number;
    major_event_id?: number;
  }>;
  milestone_title?: string | null;
};

export type StrategicGap = {
  milestone_id: number;
  title: string;
  milestone_title?: string | null;
  priority_score: number;
  reasons: string[];
  progress_percent?: number;
  linked_task_count?: number;
  open_linked_task_count?: number;
  completed_linked_task_count?: number;
};

export type RecommendationTaskDraft = {
  title: string;
  description: string | null;
  milestone_ids: number[];
};

export type Recommendation = {
  id: string;
  category:
    | "task_execution"
    | "strategic_gap"
    | "blocker_resolution"
    | "readiness_improvement";
  recommendation: string;
  score: number;
  rationale: string[];
};

export type RecommendationSet = {
  success: boolean;
  generated_at: string;
  recommendations: Recommendation[];
  rationale: string[];
};

export type MorningBriefing = {
  success: boolean;
  top_tasks: MorningBriefingTask[];
  strategic_gaps?: StrategicGap[];
  current_blockers: string[];
  suggested_next_action: string;
  recommendations?: Recommendation[];
  recommendation_rationale?: string[];
};

export type DailyCloseout = {
  success: boolean;
  generated_at: string;
  completed_today: MorningBriefingTask[];
  open_tasks: MorningBriefingTask[];
  strategic_gaps?: StrategicGap[];
  milestone_progress: Array<{
    id: number;
    milestone_id: number;
    milestone_title?: string | null;
    previous_progress: number;
    new_progress: number;
    change_amount: number;
    reason?: string | null;
    source: "manual" | "task_advisory" | "helix_tool" | "system";
    created_at: string;
  }>;
  readiness: {
    overall: number;
    categories: ReadinessCategory[];
  };
  trade_summary: {
    sessions_logged_today: number;
    trading_sessions_reviewed?: number;
    trade_count?: number;
    total_pnl: number;
    average_rule_adherence: number | null;
    wins?: number;
    losses?: number;
    sessions: Array<{
      id: number;
      session_date?: string;
      trade_date?: string;
      symbol: string;
      pnl?: number;
      result_dollars?: number;
      session?: string | null;
      direction?: string | null;
      session_grade?: string | null;
    }>;
  };
  recommended_review_prompt: string;
  tomorrow_focus?: Recommendation[];
  recommendations?: Recommendation[];
  recommendation_rationale?: string[];
  closeout_text: string;
};

export type AgentRun = {
  id: number;
  agent_id: number;
  agent_name?: string | null;
  status: "running" | "completed" | "failed";
  started_at: string;
  completed_at?: string | null;
  summary?: string | null;
  output_json?: Record<string, unknown> | null;
  error?: string | null;
};

export type AgentDefinition = {
  id: number;
  name: string;
  agent_type: string;
  description?: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
  last_run?: AgentRun | null;
};

export type AgentPriorityRank = {
  agent_type: string;
  agent_name: string;
  priority_score: number;
  reasons: string[];
};

export type AgentPrioritizationResult = {
  recommended_agent_type: string;
  recommended_agent_name: string;
  priority_score: number;
  reason: string;
  ranked_agents: AgentPriorityRank[];
  actions_taken: string[];
};

export type ScheduledAgentWindowStatus = {
  agent_type: string;
  window_start: string;
  window_end: string;
  due: boolean;
  reason: string;
  last_run?: AgentRun | null;
};

export type ScheduledAgentStatus = {
  current_local_time: string;
  scheduler_enabled: boolean;
  scheduler_status: string;
  morning: ScheduledAgentWindowStatus;
  evening: ScheduledAgentWindowStatus;
  last_scheduled_morning_run?: AgentRun | null;
  last_scheduled_evening_run?: AgentRun | null;
  prioritization_snapshot_due: boolean;
  last_prioritization_snapshot?: Record<string, unknown> | null;
};

export type ScheduleBlockType = "fixed" | "flexible";
export type ScheduleBlockCategory =
  | "boxing"
  | "family"
  | "reading"
  | "work"
  | "trading"
  | "milestone"
  | "leisure"
  | "personal"
  | "other";
export type ScheduleBlockPriority = "low" | "medium" | "high";
export type ScheduleTimePreference =
  | "anytime"
  | "morning"
  | "afternoon"
  | "evening"
  | "night";
export type FlexiblePlacementMode = "whenever_free" | "preferred_day";
export type DayOfWeek =
  | "monday"
  | "tuesday"
  | "wednesday"
  | "thursday"
  | "friday"
  | "saturday"
  | "sunday";

export type ScheduleBlock = {
  id: number;
  title?: string | null;
  block_type: ScheduleBlockType;
  category: ScheduleBlockCategory;
  day_of_week: DayOfWeek | null;
  specific_date: string | null;
  start_time: string | null;
  end_time: string | null;
  duration_minutes: number | null;
  recurrence: string | null;
  recurrence_end_type: "never" | "date" | "occurrences" | "weeks" | null;
  recurrence_end_date: string | null;
  recurrence_count: number | null;
  recurrence_weeks: number | null;
  preferred_days: DayOfWeek[];
  time_preference: ScheduleTimePreference | null;
  flexible_placement_mode: FlexiblePlacementMode | null;
  priority: ScheduleBlockPriority;
  notes: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
};

export type ScheduleDayStatus = "healthy" | "busy" | "overloaded";

export type ScheduleDaySummary = {
  day: DayOfWeek;
  date: string;
  total_scheduled_minutes: number;
  total_scheduled_hours: number;
  remaining_available_minutes: number;
  remaining_available_hours: number;
  high_priority_commitments: number;
  flexible_blocks: number;
  status: ScheduleDayStatus;
};

export type ScheduleAvailableWindow = {
  day: DayOfWeek;
  date: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  after_block_title?: string | null;
  before_block_title?: string | null;
};

export type SchedulePlacementCandidate = {
  flexible_block_id: number;
  title: string;
  category: ScheduleBlockCategory;
  day: DayOfWeek;
  date: string;
  start_time: string;
  end_time: string;
  duration_minutes: number;
  preference_matched: boolean;
  reason: string;
  recommendation: string;
};

export type ScheduleIntelligence = {
  week_start: string;
  week_end: string;
  day_summaries: ScheduleDaySummary[];
  overloaded_days: ScheduleDaySummary[];
  underutilized_days: ScheduleDaySummary[];
  available_windows: ScheduleAvailableWindow[];
  recommendations: string[];
  placement_candidates: SchedulePlacementCandidate[];
  most_available_day?: ScheduleDaySummary | null;
  most_overloaded_day?: ScheduleDaySummary | null;
  recommended_placement?: string | null;
  unplaced_flexible_blocks: number;
};

export type ScheduleBlockPlacementResult = {
  fixed_block: ScheduleBlock;
  source_block: ScheduleBlock;
  created: boolean;
};

export type MorningCheckInStatus = {
  date: string;
  morning_acknowledged: boolean;
  morning_acknowledged_at?: string | null;
  morning_fallback_sent: boolean;
  morning_fallback_sent_at?: string | null;
  morning_agent_run_id?: number | null;
  delivery_channel?: string | null;
  current_local_time: string;
  cutoff_time: string;
  cutoff_due: boolean;
};

type MorningCheckInResult = {
  success: boolean;
  summary?: string | null;
  agent_run?: AgentRun | null;
  status: MorningCheckInStatus;
  delivery_channel?: string | null;
  tts_spoken: boolean;
  fallback_sent: boolean;
  reason?: string | null;
};

type ScheduledAgentRunOnceResult = {
  checked_at: string;
  actions: Array<{
    schedule: string;
    status: string;
    agent_type?: string | null;
    reason?: string | null;
    agent_run_id?: number | null;
    result_status?: string | null;
    snapshot_date?: string | null;
  }>;
  runs: AgentRun[];
  status: ScheduledAgentStatus;
};

type ReadinessSuggestion = {
  category: string;
  current_score: number;
  suggested_score: number;
  confidence: string;
  evidence: string[];
  rationale: string[];
};

type OrbitBoardProps = Readonly<{
  majorEvents: MajorEvent[];
  event: MajorEvent | undefined;
  milestones: Milestone[];
  reviews: OrbitReview[];
  reviewsError: string | null;
  readiness: ReadinessCategory[];
  readinessError: string | null;
  morningBriefing: MorningBriefing | null;
  morningBriefingError: string | null;
  inboxTasks: InboxTask[];
  inboxTasksError: string | null;
  dailyCloseout: DailyCloseout | null;
  dailyCloseoutError: string | null;
  recommendations: RecommendationSet | null;
  recommendationsError: string | null;
  milestoneTasksById: Record<number, InboxTask[]>;
  milestoneAdvisoriesById: Record<number, MilestoneProgressAdvisory>;
  latestProgressHistoryByMilestoneId: Record<number, MilestoneProgressHistory>;
  agents: AgentDefinition[];
  agentsError: string | null;
  agentPrioritization: AgentPrioritizationResult | null;
  agentPrioritizationError: string | null;
  scheduledAgentsStatus: ScheduledAgentStatus | null;
  scheduledAgentsStatusError: string | null;
  morningCheckInStatus: MorningCheckInStatus | null;
  morningCheckInStatusError: string | null;
  scheduleBlocks: ScheduleBlock[];
  scheduleBlocksError: string | null;
  scheduleIntelligence: ScheduleIntelligence | null;
  scheduleIntelligenceError: string | null;
  errorMessage: string | null;
}>;

const tabs = [
  "Overview",
  "Major Events",
  "Tasks",
  "Schedule",
  "Milestones",
  "Reviews",
  "Readiness",
  "Trade Journal",
  "Agents",
] as const;
type Tab = (typeof tabs)[number];
type ScheduleSection = "calendar" | "add" | "intelligence" | "blocks";
type Toast = {
  message: string;
  type: "success" | "error";
};
const CLOSEOUT_LIST_LIMIT = 3;
const majorEventStatusOptions: MajorEventStatus[] = [
  "active",
  "paused",
  "completed",
  "archived",
];
const emptyMajorEventForm = {
  title: "",
  description: "",
  target_date: "",
  status: "active" as MajorEventStatus,
};
type MajorEventFormState = typeof emptyMajorEventForm;
const dayOptions: DayOfWeek[] = [
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
  "sunday",
];
const categoryOptions: ScheduleBlockCategory[] = [
  "boxing",
  "family",
  "reading",
  "work",
  "trading",
  "milestone",
  "leisure",
  "personal",
  "other",
];
const priorityOptions: ScheduleBlockPriority[] = ["low", "medium", "high"];
const scheduleSectionItems: { id: ScheduleSection; label: string }[] = [
  { id: "calendar", label: "Calendar" },
  { id: "add", label: "Add Block" },
  { id: "intelligence", label: "Intelligence" },
  { id: "blocks", label: "Blocks" },
];
const durationUnitOptions = ["minutes", "hours"] as const;
type DurationUnit = (typeof durationUnitOptions)[number];
const maxScheduleDurationMinutes = 480;
const timePreferenceOptions: ScheduleTimePreference[] = [
  "anytime",
  "morning",
  "afternoon",
  "evening",
  "night",
];
const timePreferenceLabels: Record<ScheduleTimePreference, string> = {
  anytime: "Anytime",
  morning: "Morning",
  afternoon: "Afternoon",
  evening: "Evening",
  night: "Night",
};
const flexiblePlacementLabels: Record<FlexiblePlacementMode, string> = {
  whenever_free: "Whenever I'm free",
  preferred_day: "Use preferred day/date",
};
const recurrenceOptions = [
  "once",
  "daily",
  "weekly",
  "every_other_week",
  "monthly",
  "every_other_month",
] as const;
const recurrenceLabels: Record<(typeof recurrenceOptions)[number], string> = {
  once: "Once",
  daily: "Daily",
  weekly: "Weekly",
  every_other_week: "Every other week",
  monthly: "Monthly",
  every_other_month: "Every other month",
};
const recurrenceEndOptions = ["never", "date", "occurrences", "weeks"] as const;
const recurrenceEndLabels: Record<(typeof recurrenceEndOptions)[number], string> = {
  never: "Never ends",
  date: "Ends on date",
  occurrences: "Ends after occurrences",
  weeks: "Ends after weeks",
};
const scheduleCategoryFallbackLabels: Record<ScheduleBlockCategory, string> = {
  boxing: "Boxing",
  family: "Family Time",
  reading: "Reading",
  work: "Work",
  trading: "Trading",
  milestone: "Milestone Work",
  leisure: "Leisure",
  personal: "Personal",
  other: "Other",
};
const emptyScheduleForm = {
  title: "",
  block_type: "fixed" as ScheduleBlockType,
  category: "work" as ScheduleBlockCategory,
  day_of_week: "monday" as DayOfWeek | "",
  selected_dates: [] as string[],
  same_time: true,
  date_times: {} as Record<string, { start_time: string; end_time: string }>,
  preferred_days: [] as DayOfWeek[],
  specific_date: "",
  start_time: "",
  end_time: "",
  duration_value: "",
  duration_unit: "minutes" as DurationUnit,
  recurrence: "once" as (typeof recurrenceOptions)[number],
  recurrence_end_type: "never" as (typeof recurrenceEndOptions)[number],
  recurrence_end_date: "",
  recurrence_count: "",
  recurrence_weeks: "",
  time_preference: "anytime" as ScheduleTimePreference,
  flexible_placement_mode: "preferred_day" as FlexiblePlacementMode,
  priority: "medium" as ScheduleBlockPriority,
  notes: "",
  active: true,
};
type ScheduleFormState = typeof emptyScheduleForm;

function formatDate(value: string | null) {
  if (!value) {
    return "No target date set";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

function formatDateTime(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function toDateOnlyString(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function addDays(date: Date, days: number) {
  const nextDate = new Date(date);
  nextDate.setDate(nextDate.getDate() + days);
  return nextDate;
}

function getWeekStart(date: Date) {
  const weekStart = new Date(date);
  weekStart.setHours(0, 0, 0, 0);
  const dayOffset = (weekStart.getDay() + 6) % 7;
  weekStart.setDate(weekStart.getDate() - dayOffset);
  return weekStart;
}

function formatWeekHeading(weekDays: { date: Date }[]) {
  const firstDay = weekDays[0]?.date ?? new Date();
  const lastDay = weekDays[weekDays.length - 1]?.date ?? firstDay;
  const firstMonth = new Intl.DateTimeFormat("en-US", { month: "long" }).format(
    firstDay,
  );
  const lastMonth = new Intl.DateTimeFormat("en-US", { month: "long" }).format(
    lastDay,
  );
  const firstYear = firstDay.getFullYear();
  const lastYear = lastDay.getFullYear();

  if (firstYear !== lastYear) {
    return `${firstMonth} ${firstYear} - ${lastMonth} ${lastYear}`;
  }

  if (firstMonth !== lastMonth) {
    return `${firstMonth} - ${lastMonth} ${firstYear}`;
  }

  return `${firstMonth} ${firstYear}`;
}

function formatWeekDateLabel(date: Date) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(date);
}

function isSameDate(left: Date, right: Date) {
  return toDateOnlyString(left) === toDateOnlyString(right);
}

function formatStatus(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatTime(value: string | null) {
  if (!value) {
    return "--";
  }

  const [hourValue, minuteValue] = value.split(":");
  const hour = Number(hourValue);
  const minute = Number(minuteValue ?? "0");

  if (Number.isNaN(hour) || Number.isNaN(minute)) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(2026, 0, 1, hour, minute));
}

function formatBlockCardTiming(block: ScheduleBlock) {
  if (block.block_type === "fixed") {
    return `${formatTime(block.start_time)}-${formatTime(block.end_time)}`;
  }

  return formatDuration(block.duration_minutes);
}

function formatScheduleDaySummary(day: ScheduleDaySummary | null | undefined) {
  if (!day) {
    return "Unavailable";
  }

  return `${formatStatus(day.day)} | ${formatDuration(
    day.total_scheduled_minutes,
  )} scheduled`;
}

function formatDuration(durationMinutes: number | null) {
  if (!durationMinutes) {
    return "--";
  }

  if (durationMinutes < 60) {
    return `${durationMinutes} min`;
  }

  const hours = durationMinutes / 60;
  return `${Number.isInteger(hours) ? hours : hours.toFixed(1)} hr`;
}

function getDurationMinutesFromForm(form: ScheduleFormState) {
  const duration = Number(form.duration_value);

  if (Number.isNaN(duration)) {
    return null;
  }

  return form.duration_unit === "hours" ? Math.round(duration * 60) : duration;
}

function getDurationFormFields(durationMinutes: number | null) {
  if (!durationMinutes) {
    return {
      duration_value: "",
      duration_unit: "minutes" as DurationUnit,
    };
  }

  if (durationMinutes >= 60 && durationMinutes % 60 === 0) {
    return {
      duration_value: String(durationMinutes / 60),
      duration_unit: "hours" as DurationUnit,
    };
  }

  return {
    duration_value: String(durationMinutes),
    duration_unit: "minutes" as DurationUnit,
  };
}

function getScheduleBlockLabel(block: ScheduleBlock) {
  return block.title?.trim() || scheduleCategoryFallbackLabels[block.category];
}

type ScheduleBlockDisplayGroup = {
  key: string;
  label: string;
  blocks: ScheduleBlock[];
  summaryLabel: string;
};

type ScheduleBlockPatternRow = {
  key: string;
  block: ScheduleBlock;
  blocks: ScheduleBlock[];
  daysLabel: string;
};

type CalendarScheduleBlockGroup = {
  key: string;
  label: string;
  summaryLabel: string;
  blocks: ScheduleBlock[];
};

const compactDayLabels: Record<DayOfWeek, string> = {
  monday: "Mon",
  tuesday: "Tue",
  wednesday: "Wed",
  thursday: "Thu",
  friday: "Fri",
  saturday: "Sat",
  sunday: "Sun",
};

function getScheduleBlockGroupLabel(block: ScheduleBlock) {
  const categoryLabel = scheduleCategoryFallbackLabels[block.category];
  const title = block.title?.trim();
  return title && title !== categoryLabel
    ? `${categoryLabel} / ${title}`
    : categoryLabel;
}

function getScheduleBlockSortTime(block: ScheduleBlock) {
  const dayIndex = block.day_of_week ? dayOptions.indexOf(block.day_of_week) : 8;
  return `${String(dayIndex).padStart(2, "0")}-${block.specific_date ?? ""}-${
    block.start_time ?? ""
  }`;
}

function getCalendarScheduleSortKey(block: ScheduleBlock) {
  const startMinutes = scheduleTimeToMinutes(block.start_time);
  return [
    String(startMinutes ?? 9999).padStart(4, "0"),
    getScheduleBlockLabel(block).toLowerCase(),
    String(block.id).padStart(8, "0"),
  ].join(":");
}

function getScheduleBlockDay(block: ScheduleBlock): DayOfWeek | null {
  if (block.recurrence === "daily") {
    return null;
  }

  if (block.day_of_week) {
    return block.day_of_week;
  }

  if (block.specific_date) {
    const date = new Date(`${block.specific_date}T00:00:00`);
    if (!Number.isNaN(date.getTime())) {
      return dayOptions[(date.getDay() + 6) % 7];
    }
  }

  return null;
}

function getScheduleBlockDays(block: ScheduleBlock): DayOfWeek[] {
  if (block.recurrence === "daily") {
    return dayOptions;
  }

  if (Array.isArray(block.preferred_days) && block.preferred_days.length > 0) {
    return block.preferred_days.filter((day) => dayOptions.includes(day));
  }

  const day = getScheduleBlockDay(block);
  return day ? [day] : [];
}

function formatRecurrenceEnd(block: ScheduleBlock) {
  if (!block.recurrence || block.recurrence === "once") {
    return "";
  }

  if (block.recurrence_end_type === "date" && block.recurrence_end_date) {
    return `until ${formatDate(block.recurrence_end_date)}`;
  }

  if (block.recurrence_end_type === "occurrences" && block.recurrence_count) {
    return `for ${block.recurrence_count} occurrence${
      block.recurrence_count === 1 ? "" : "s"
    }`;
  }

  if (block.recurrence_end_type === "weeks" && block.recurrence_weeks) {
    return `for ${block.recurrence_weeks} week${
      block.recurrence_weeks === 1 ? "" : "s"
    }`;
  }

  return "";
}

function formatCompactDayRange(days: DayOfWeek[]) {
  const uniqueIndexes = Array.from(
    new Set(days.map((day) => dayOptions.indexOf(day)).filter((index) => index >= 0)),
  ).sort((left, right) => left - right);

  if (uniqueIndexes.length === 0) {
    return "Unscheduled";
  }

  const ranges: string[] = [];
  let start = uniqueIndexes[0];
  let end = start;

  for (const index of uniqueIndexes.slice(1)) {
    if (index === end + 1) {
      end = index;
      continue;
    }

    ranges.push(formatCompactDayRangePart(start, end));
    start = index;
    end = index;
  }
  ranges.push(formatCompactDayRangePart(start, end));

  return ranges.join(",");
}

function formatCompactDayPattern(days: DayOfWeek[]) {
  const rangeLabel = formatCompactDayRange(days);
  return rangeLabel.replaceAll(",", "/");
}

function formatCompactDayRangePart(startIndex: number, endIndex: number) {
  const startDay = dayOptions[startIndex];
  const endDay = dayOptions[endIndex];

  if (startIndex === endIndex) {
    return compactDayLabels[startDay];
  }

  return `${compactDayLabels[startDay]}-${compactDayLabels[endDay]}`;
}

function getSchedulePatternKey(block: ScheduleBlock) {
  if (block.block_type === "flexible") {
    return [
      "flexible",
      block.flexible_placement_mode ?? "",
      block.duration_minutes ?? "",
      block.time_preference ?? "",
      getScheduleBlockDays(block).join(","),
      block.recurrence ?? "once",
      block.recurrence_end_type ?? "never",
      block.recurrence_end_date ?? "",
      block.recurrence_count ?? "",
      block.recurrence_weeks ?? "",
    ].join(":");
  }

  return [
    "fixed",
    block.start_time ?? "",
    block.end_time ?? "",
    block.recurrence ?? "once",
    block.recurrence_end_type ?? "never",
    block.recurrence_end_date ?? "",
    block.recurrence_count ?? "",
    block.recurrence_weeks ?? "",
  ].join(":");
}

function getExpandedSchedulePatternKey(block: ScheduleBlock) {
  return [
    getSchedulePatternKey(block),
    block.priority,
    block.active ? "active" : "inactive",
    block.notes ?? "",
  ].join(":");
}

function groupScheduleBlocksByPattern(
  blocks: ScheduleBlock[],
): ScheduleBlockPatternRow[] {
  const patterns = new Map<string, ScheduleBlock[]>();
  blocks.forEach((block) => {
    const key = getExpandedSchedulePatternKey(block);
    patterns.set(key, [...(patterns.get(key) ?? []), block]);
  });

  return Array.from(patterns.entries())
    .map(([key, patternBlocks]) => {
      const sortedBlocks = [...patternBlocks].sort((left, right) => {
        const leftSort = getScheduleBlockSortTime(left);
        const rightSort = getScheduleBlockSortTime(right);
        if (leftSort !== rightSort) {
          return leftSort.localeCompare(rightSort);
        }
        return left.id - right.id;
      });

      return {
        key,
        block: sortedBlocks[0],
        blocks: sortedBlocks,
        daysLabel: formatCompactDayPattern(
          sortedBlocks.flatMap(getScheduleBlockDays),
        ),
      };
    })
    .sort((left, right) => {
      const leftSort = getScheduleBlockSortTime(left.block);
      const rightSort = getScheduleBlockSortTime(right.block);
      if (leftSort !== rightSort) {
        return leftSort.localeCompare(rightSort);
      }
      return left.block.id - right.block.id;
    });
}

function getSchedulePatternSummary(blocks: ScheduleBlock[]) {
  if (blocks.length === 0) {
    return "0 blocks";
  }

  const patterns = new Map<string, ScheduleBlock[]>();
  blocks.forEach((block) => {
    const key = getSchedulePatternKey(block);
    patterns.set(key, [...(patterns.get(key) ?? []), block]);
  });

  const patternEntries = Array.from(patterns.values()).sort((left, right) =>
    getScheduleBlockSortTime(left[0]).localeCompare(getScheduleBlockSortTime(right[0])),
  );
  const patternCount = patternEntries.length;
  const countLabel = `${patternCount} ${patternCount === 1 ? "block" : "blocks"}`;
  const daysLabel = formatCompactDayRange(
    patternEntries.flatMap((patternBlocks) =>
      patternBlocks.flatMap(getScheduleBlockDays),
    ),
  );

  if (blocks[0].block_type === "flexible") {
    const block = blocks[0];
    const placement =
      block.flexible_placement_mode === "whenever_free"
        ? "Needs placement"
        : daysLabel;
    const preference =
      block.time_preference && block.time_preference !== "anytime"
        ? `${timePreferenceLabels[block.time_preference]} preferred`
        : "Flexible";
    const endLabel = formatRecurrenceEnd(block);
    return `${countLabel} · ${placement} · ${formatDuration(
      block.duration_minutes,
    )} · ${preference}${endLabel ? ` · ${endLabel}` : ""}`;
  }

  if (patternEntries.length <= 3) {
    const detail = patternEntries
      .map((patternBlocks) => {
        const block = patternBlocks[0];
        const endLabel = formatRecurrenceEnd(block);
        return `${formatCompactDayRange(
          patternBlocks.flatMap(getScheduleBlockDays),
        )} · ${formatTime(block.start_time)}-${formatTime(block.end_time)}${
          endLabel ? ` · ${endLabel}` : ""
        }`;
      })
      .join(" · ");
    return `${countLabel} · ${detail}`;
  }

  const startMinutes = blocks
    .map((block) => scheduleTimeToMinutes(block.start_time))
    .filter((value): value is number => value !== null);
  const endMinutes = blocks
    .map((block) => scheduleTimeToMinutes(block.end_time))
    .filter((value): value is number => value !== null);
  const timeSummary =
    startMinutes.length > 0 && endMinutes.length > 0
      ? `${formatMinutesAsTime(Math.min(...startMinutes))}-${formatMinutesAsTime(
          Math.max(...endMinutes),
        )}`
      : "Mixed times";

  return `${countLabel} · ${daysLabel} · ${timeSummary}`;
}

function scheduleTimeToMinutes(value: string | null) {
  if (!value) {
    return null;
  }

  const [hourValue, minuteValue] = value.split(":");
  const hour = Number(hourValue);
  const minute = Number(minuteValue ?? "0");
  if (Number.isNaN(hour) || Number.isNaN(minute)) {
    return null;
  }
  return hour * 60 + minute;
}

function formatMinutesAsTime(minutes: number) {
  const hour = Math.floor(minutes / 60);
  const minute = minutes % 60;
  return formatTime(`${String(hour).padStart(2, "0")}:${String(minute).padStart(2, "0")}`);
}

function groupScheduleBlocks(blocks: ScheduleBlock[]): ScheduleBlockDisplayGroup[] {
  const groups = new Map<string, ScheduleBlock[]>();
  blocks.forEach((block) => {
    const key = `${block.category}:${getScheduleBlockLabel(block)}`;
    groups.set(key, [...(groups.get(key) ?? []), block]);
  });

  return Array.from(groups.entries())
    .map(([key, groupedBlocks]) => {
      const sortedBlocks = [...groupedBlocks].sort((left, right) => {
        const leftSort = getScheduleBlockSortTime(left);
        const rightSort = getScheduleBlockSortTime(right);
        if (leftSort !== rightSort) {
          return leftSort.localeCompare(rightSort);
        }
        return left.id - right.id;
      });
      return {
        key,
        label: getScheduleBlockGroupLabel(sortedBlocks[0]),
        blocks: sortedBlocks,
        summaryLabel: getSchedulePatternSummary(sortedBlocks),
      };
    })
    .sort((left, right) => left.label.localeCompare(right.label));
}

function groupCalendarScheduleBlocks(blocks: ScheduleBlock[]): CalendarScheduleBlockGroup[] {
  const groups = new Map<string, ScheduleBlock[]>();
  blocks.forEach((block) => {
    const key = `${block.category}:${getScheduleBlockLabel(block)}:${getSchedulePatternKey(block)}`;
    groups.set(key, [...(groups.get(key) ?? []), block]);
  });

  return Array.from(groups.entries())
    .map(([key, groupedBlocks]) => {
      const sortedBlocks = [...groupedBlocks].sort((left, right) => {
        const leftSort = getCalendarScheduleSortKey(left);
        const rightSort = getCalendarScheduleSortKey(right);
        if (leftSort !== rightSort) {
          return leftSort.localeCompare(rightSort);
        }
        return left.id - right.id;
      });
      return {
        key,
        label: getScheduleBlockGroupLabel(sortedBlocks[0]),
        summaryLabel: getSchedulePatternSummary(sortedBlocks),
        blocks: sortedBlocks,
      };
    })
    .sort((left, right) =>
      getCalendarScheduleSortKey(left.blocks[0]).localeCompare(
        getCalendarScheduleSortKey(right.blocks[0]),
      ),
    );
}

function getWeekDateKeyForDay(weekStart: Date, day: DayOfWeek) {
  const dayIndex = dayOptions.indexOf(day);
  if (dayIndex === -1) {
    return "";
  }

  return toDateOnlyString(addDays(weekStart, dayIndex));
}

function getScheduleBlockTargetDateKeys(
  block: ScheduleBlock,
  weekDays: { day: DayOfWeek; date: Date; dateKey: string }[],
) {
  if (
    block.block_type === "flexible" &&
    block.flexible_placement_mode === "whenever_free"
  ) {
    return [];
  }

  const recurrence = block.recurrence ?? "once";
  const candidates =
    recurrence === "daily"
      ? weekDays
      : weekDays.filter((weekDay) =>
          getScheduleBlockDays(block).includes(weekDay.day),
        );

  if (recurrence === "once") {
    if (block.specific_date) {
      return weekDays.some((weekDay) => weekDay.dateKey === block.specific_date)
        ? [block.specific_date]
        : [];
    }
    return candidates.slice(0, 1).map((weekDay) => weekDay.dateKey);
  }

  const recurrenceCandidates =
    recurrence === "every_other_week"
      ? candidates.filter((weekDay) => {
          const anchor = getScheduleBlockAnchorDate(block, weekDays);
          if (!anchor) {
            return true;
          }
          const weekDelta = Math.floor(
            (weekDay.date.getTime() - anchor.getTime()) / (7 * 24 * 60 * 60 * 1000),
          );
          return weekDelta % 2 === 0;
        })
      : candidates;

  return recurrenceCandidates
    .filter((weekDay) => scheduleBlockPassesRecurrenceEnd(block, weekDay.date))
    .map((weekDay) => weekDay.dateKey);
}

function getScheduleBlockAnchorDate(
  block: ScheduleBlock,
  weekDays: { day: DayOfWeek; date: Date; dateKey: string }[],
) {
  const value = block.specific_date || block.created_at.slice(0, 10) || weekDays[0]?.dateKey;
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
}

function scheduleBlockPassesRecurrenceEnd(block: ScheduleBlock, currentDate: Date) {
  if (!block.recurrence || block.recurrence === "once") {
    return true;
  }

  if (block.recurrence_end_type === "date" && block.recurrence_end_date) {
    return currentDate <= new Date(`${block.recurrence_end_date}T23:59:59`);
  }

  const anchor = getScheduleBlockAnchorDate(block, [
    {
      day: dayOptions[currentDate.getDay() === 0 ? 6 : currentDate.getDay() - 1],
      date: currentDate,
      dateKey: toDateOnlyString(currentDate),
    },
  ]);
  if (!anchor) {
    return true;
  }

  if (block.recurrence_end_type === "weeks" && block.recurrence_weeks) {
    const endDate = addDays(anchor, block.recurrence_weeks * 7 - 1);
    return currentDate <= endDate;
  }

  if (block.recurrence_end_type === "occurrences" && block.recurrence_count) {
    const occurrenceIndex = getScheduleOccurrenceIndex(block, anchor, currentDate);
    return occurrenceIndex >= 1 && occurrenceIndex <= block.recurrence_count;
  }

  return true;
}

function getScheduleOccurrenceIndex(
  block: ScheduleBlock,
  anchor: Date,
  currentDate: Date,
) {
  if (block.recurrence === "daily") {
    return (
      Math.floor(
        (currentDate.getTime() - anchor.getTime()) / (24 * 60 * 60 * 1000),
      ) + 1
    );
  }

  const days = getScheduleBlockDays(block);
  const dayIndexes = days
    .map((day) => dayOptions.indexOf(day))
    .filter((index) => index >= 0)
    .sort((left, right) => left - right);
  const weekDelta = Math.max(
    0,
    Math.floor(
      (currentDate.getTime() - anchor.getTime()) / (7 * 24 * 60 * 60 * 1000),
    ),
  );
  const weeksPerCycle = block.recurrence === "every_other_week" ? 2 : 1;
  const cycleDelta = Math.floor(weekDelta / weeksPerCycle);
  const currentDayIndex = (currentDate.getDay() + 6) % 7;
  const dayPosition = Math.max(0, dayIndexes.indexOf(currentDayIndex));
  return cycleDelta * Math.max(dayIndexes.length, 1) + dayPosition + 1;
}

function scheduleFormFromBlock(block: ScheduleBlock): ScheduleFormState {
  const durationFields = getDurationFormFields(block.duration_minutes);

  return {
    title: block.title ?? "",
    block_type: block.block_type,
    category: block.category,
    day_of_week: block.day_of_week ?? "",
    selected_dates: [],
    same_time: true,
    date_times: {},
    preferred_days:
      Array.isArray(block.preferred_days) && block.preferred_days.length > 0
        ? block.preferred_days
        : block.day_of_week
          ? [block.day_of_week]
          : [],
    specific_date: block.specific_date ?? "",
    start_time: block.start_time ?? "",
    end_time: block.end_time ?? "",
    ...durationFields,
    recurrence: recurrenceOptions.includes(
      block.recurrence as (typeof recurrenceOptions)[number],
    )
      ? (block.recurrence as (typeof recurrenceOptions)[number])
      : "once",
    recurrence_end_type:
      block.recurrence_end_type && recurrenceEndOptions.includes(block.recurrence_end_type)
        ? block.recurrence_end_type
        : "never",
    recurrence_end_date: block.recurrence_end_date ?? "",
    recurrence_count: block.recurrence_count ? String(block.recurrence_count) : "",
    recurrence_weeks: block.recurrence_weeks ? String(block.recurrence_weeks) : "",
    time_preference:
      block.time_preference && timePreferenceOptions.includes(block.time_preference)
        ? block.time_preference
        : "anytime",
    flexible_placement_mode:
      block.flexible_placement_mode === "whenever_free"
        ? "whenever_free"
        : "preferred_day",
    priority: block.priority,
    notes: block.notes ?? "",
    active: block.active,
  };
}

function majorEventFormFromEvent(event: MajorEvent): MajorEventFormState {
  return {
    title: event.title,
    description: event.description ?? "",
    target_date: event.target_date ?? "",
    status: event.status,
  };
}

function getPrimaryMajorEvent(events: MajorEvent[]) {
  return (
    events.find((majorEvent) => majorEvent.status === "active") ??
    events.find((majorEvent) => majorEvent.status !== "archived") ??
    events[0]
  );
}

function getMajorEventProgress(event: MajorEvent | undefined) {
  return event?.calculated_progress_percent ?? event?.progress_percent ?? 0;
}

function getExcerpt(value: string | null | undefined, limit = 160) {
  if (!value) {
    return "";
  }

  const compact = value.replace(/\s+/g, " ").trim();

  if (compact.length <= limit) {
    return compact;
  }

  return `${compact.slice(0, limit - 3).trim()}...`;
}

function getReviewTitle(review: OrbitReview) {
  return review.title ?? formatStatus(review.review_type);
}

function getDaysRemaining(targetDate: string | null) {
  if (!targetDate) {
    return null;
  }

  const target = new Date(`${targetDate}T00:00:00Z`).getTime();
  const days = Math.ceil((target - Date.now()) / (1000 * 60 * 60 * 24));

  return Math.max(days, 0);
}

function getOverallReadiness(readiness: ReadinessCategory[]) {
  if (readiness.length === 0) {
    return null;
  }

  const total = readiness.reduce(
    (sum, category) => sum + category.current_score,
    0,
  );

  return Math.round(total / readiness.length);
}

function getCompactGapReasons(reasons: string[]) {
  const preferred = [
    "No linked tasks",
    "Progress remains 0%",
    "Progress <= 10%",
    "No recent progress activity",
    "No linked open tasks",
    "Active milestone",
    "In progress milestone",
  ];
  const ordered = preferred.filter((reason) => reasons.includes(reason));

  return [
    ...ordered,
    ...reasons.filter((reason) => !ordered.includes(reason)),
  ];
}

function isTaskOpen(task: { status: string }) {
  return !["complete", "completed", "done", "cancelled"].includes(
    task.status.toLowerCase(),
  );
}

function getRecommendationId(gap: StrategicGap) {
  return `strategic-gap-${gap.milestone_id}`;
}

function getRecommendationTargetId(recommendation: Recommendation) {
  const rawId = recommendation.id.split("-").at(-1);
  const targetId = Number(rawId);
  return Number.isNaN(targetId) ? null : targetId;
}

function formatTaskSummary(task: MorningBriefingTask) {
  const milestone = task.milestone_title ?? task.milestones?.[0]?.title;
  return milestone ? `${task.title} (${milestone})` : task.title;
}

function formatProgressSummary(
  progress: DailyCloseout["milestone_progress"][number],
) {
  const title = progress.milestone_title ?? `Milestone ${progress.milestone_id}`;
  return `${title}: ${progress.previous_progress}% -> ${progress.new_progress}%`;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function getRecordField(
  record: Record<string, unknown> | null | undefined,
  field: string,
) {
  if (!record) {
    return undefined;
  }

  return record[field];
}

function getTextField(
  record: Record<string, unknown> | null | undefined,
  field: string,
) {
  const value = getRecordField(record, field);
  return typeof value === "string" && value.trim() ? value : null;
}

function getScoreText(record: Record<string, unknown> | null | undefined) {
  const value = getRecordField(record, "priority_score");

  if (typeof value === "number" || typeof value === "string") {
    return `P${value}`;
  }

  return null;
}

function getStringArrayField(
  record: Record<string, unknown> | null | undefined,
  field: string,
) {
  const value = getRecordField(record, field);

  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is string => typeof item === "string");
}

function getReadinessSuggestions(
  record: Record<string, unknown> | null | undefined,
) {
  const value = getRecordField(record, "suggestions");

  if (!Array.isArray(value)) {
    return [];
  }

  return value.filter((item): item is ReadinessSuggestion => {
    if (!isRecord(item)) {
      return false;
    }

    return (
      typeof item.category === "string" &&
      typeof item.current_score === "number" &&
      typeof item.suggested_score === "number" &&
      typeof item.confidence === "string" &&
      Array.isArray(item.evidence) &&
      item.evidence.every((entry) => typeof entry === "string") &&
      Array.isArray(item.rationale) &&
      item.rationale.every((entry) => typeof entry === "string")
    );
  });
}

function formatExecutiveItem(
  record: Record<string, unknown> | null | undefined,
  fallback: string,
) {
  const title = getTextField(record, "title") ?? fallback;
  const score = getScoreText(record);
  return score ? `${title} (${score})` : title;
}

function ProgressBar({ value }: Readonly<{ value: number }>) {
  const clampedValue = Math.min(Math.max(value, 0), 100);

  return (
    <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
      <div
        className="h-full rounded-full bg-cyan-300"
        style={{ width: `${clampedValue}%` }}
      />
    </div>
  );
}

function MiniPanel({
  title,
  children,
}: Readonly<{
  title: string;
  children: ReactNode;
}>) {
  return (
    <section className="rounded-xl border border-white/10 bg-neutral-950/70 p-3">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        {title}
      </h2>
      {children}
    </section>
  );
}

function ScheduleBlockActionMenu({
  block,
  actionBlocks,
  mutatingScheduleBlockId,
  onEdit,
  onArchive,
  onDelete,
}: Readonly<{
  block: ScheduleBlock;
  actionBlocks?: ScheduleBlock[];
  mutatingScheduleBlockId: number | null;
  onEdit: (block: ScheduleBlock, patternBlocks?: ScheduleBlock[]) => void;
  onArchive: (block: ScheduleBlock) => void;
  onDelete: (blockId: number) => void;
}>) {
  return (
    <details className="relative shrink-0">
      <summary className="flex h-7 w-7 cursor-pointer list-none items-center justify-center rounded-md border border-white/10 bg-white/[0.03] text-sm font-semibold text-neutral-300 hover:border-white/20 hover:text-white">
        ...
      </summary>
      <div className="absolute right-0 top-8 z-20 w-28 rounded-lg border border-white/10 bg-neutral-950 p-1 shadow-xl shadow-black/40">
        <button
          type="button"
          onClick={() => onEdit(block, actionBlocks)}
          className="block w-full rounded-md px-2 py-1 text-left text-xs font-semibold text-neutral-300 hover:bg-white/[0.06] hover:text-white"
        >
          Edit
        </button>
        {block.active ? (
          <button
            type="button"
            onClick={() => onArchive(block)}
            disabled={mutatingScheduleBlockId === block.id}
            className="block w-full rounded-md px-2 py-1 text-left text-xs font-semibold text-amber-100 hover:bg-amber-300/10 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Archive
          </button>
        ) : null}
        <button
          type="button"
          onClick={() => onDelete(block.id)}
          disabled={mutatingScheduleBlockId === block.id}
          className="block w-full rounded-md px-2 py-1 text-left text-xs font-semibold text-red-100 hover:bg-red-300/10 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Delete
        </button>
      </div>
    </details>
  );
}

function CalendarScheduleBlockCard({
  block,
  mutatingScheduleBlockId,
  placingScheduleBlockId,
  onEdit,
  onArchive,
  onDelete,
  onPlace,
  placementCandidate,
  onFindSlot,
  compact = false,
}: Readonly<{
  block: ScheduleBlock;
  mutatingScheduleBlockId: number | null;
  placingScheduleBlockId?: number | null;
  onEdit: (block: ScheduleBlock, patternBlocks?: ScheduleBlock[]) => void;
  onArchive: (block: ScheduleBlock) => void;
  onDelete: (blockId: number) => void;
  onPlace?: (blockId: number, candidate?: SchedulePlacementCandidate) => void;
  placementCandidate?: SchedulePlacementCandidate | null;
  onFindSlot?: () => void;
  compact?: boolean;
}>) {
  const canPlace =
    block.active &&
    block.block_type === "flexible";

  return (
    <article
      className={`rounded-lg border ${
        block.active
          ? "border-cyan-300/15 bg-cyan-300/[0.06]"
          : "border-white/5 bg-white/[0.02] opacity-60"
      } ${compact ? "px-3 py-2" : "px-3 py-2.5"}`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="break-words text-sm font-semibold leading-5 text-neutral-100">
            {getScheduleBlockLabel(block)}
          </h4>
          {block.notes && !compact ? (
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-neutral-500">
              {block.notes}
            </p>
          ) : null}
        </div>
        <ScheduleBlockActionMenu
          block={block}
          mutatingScheduleBlockId={mutatingScheduleBlockId}
          onEdit={onEdit}
          onArchive={onArchive}
          onDelete={onDelete}
        />
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <span className="whitespace-nowrap rounded-full border border-cyan-300/15 bg-cyan-300/5 px-2 py-0.5 text-[11px] font-semibold text-cyan-100">
          {formatBlockCardTiming(block)}
        </span>
        {block.block_type === "flexible" ? (
          <span className="rounded-full border border-violet-300/20 bg-violet-300/10 px-2 py-0.5 text-[11px] font-semibold text-violet-100">
            Flexible
          </span>
        ) : null}
        {block.block_type === "flexible" &&
        block.flexible_placement_mode === "whenever_free" ? (
          <span className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-100">
            Whenever free
          </span>
        ) : null}
        {block.block_type === "flexible" &&
        block.time_preference &&
        block.time_preference !== "anytime" ? (
          <span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-2 py-0.5 text-[11px] font-semibold text-amber-100">
            {timePreferenceLabels[block.time_preference]} preferred
          </span>
        ) : null}
        <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] font-semibold text-neutral-400">
          {formatStatus(block.category)}
        </span>
        <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] font-semibold text-neutral-400">
          {formatStatus(block.priority)}
        </span>
      </div>
      {canPlace ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {placementCandidate ? (
            <button
              type="button"
              onClick={() => onPlace?.(block.id, placementCandidate)}
              disabled={placingScheduleBlockId === block.id}
              className="rounded-md border border-emerald-300/25 bg-emerald-300/10 px-2 py-1 text-xs font-semibold text-emerald-100 hover:bg-emerald-300/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {placingScheduleBlockId === block.id
                ? "Placing..."
                : "Place suggested slot"}
            </button>
          ) : (
            <button
              type="button"
              onClick={onFindSlot}
              className="rounded-md border border-cyan-300/25 bg-cyan-300/10 px-2 py-1 text-xs font-semibold text-cyan-100 hover:bg-cyan-300/20"
            >
              Find Slot
            </button>
          )}
          {placementCandidate ? (
            <span className="text-xs text-neutral-500">
              {formatStatus(placementCandidate.day)} ·{" "}
              {formatTime(placementCandidate.start_time)}-
              {formatTime(placementCandidate.end_time)}
            </span>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function CalendarScheduleBlockGroupCard({
  group,
  mutatingScheduleBlockId,
  onEdit,
  onArchive,
  onDelete,
}: Readonly<{
  group: CalendarScheduleBlockGroup;
  mutatingScheduleBlockId: number | null;
  onEdit: (block: ScheduleBlock, patternBlocks?: ScheduleBlock[]) => void;
  onArchive: (block: ScheduleBlock) => void;
  onDelete: (blockId: number) => void;
}>) {
  const [expanded, setExpanded] = useState(false);

  return (
    <article className="rounded-lg border border-cyan-300/15 bg-cyan-300/[0.06]">
      <button
        type="button"
        onClick={() => setExpanded((current) => !current)}
        className="flex w-full items-start justify-between gap-2 px-2.5 py-2.5 text-left lg:px-3"
      >
        <span className="min-w-0">
          <span className="block break-normal text-sm font-semibold leading-5 text-neutral-100">
            {group.label}
          </span>
          <span className="mt-1 block text-[11px] leading-5 text-neutral-500 sm:text-xs">
            {group.summaryLabel}
          </span>
        </span>
        <span className="shrink-0 rounded-full border border-white/10 bg-neutral-950 px-2 py-0.5 text-[11px] font-semibold text-neutral-400">
          {expanded ? "Close" : "Open"}
        </span>
      </button>
      {expanded ? (
        <div className="grid gap-2 border-t border-white/10 p-2">
          {group.blocks.map((block) => (
            <CalendarScheduleBlockCard
              key={block.id}
              block={block}
              compact
              mutatingScheduleBlockId={mutatingScheduleBlockId}
              onEdit={onEdit}
              onArchive={onArchive}
              onDelete={onDelete}
            />
          ))}
        </div>
      ) : null}
    </article>
  );
}

function ScheduleBlockPatternRowCard({
  pattern,
  isFlexibleColumn,
  mutatingScheduleBlockId,
  placingScheduleBlockId,
  placementCandidate,
  onFindSlot,
  onPlace,
  onEdit,
  onArchive,
  onDelete,
}: Readonly<{
  pattern: ScheduleBlockPatternRow;
  isFlexibleColumn: boolean;
  mutatingScheduleBlockId: number | null;
  placingScheduleBlockId: number | null;
  placementCandidate?: SchedulePlacementCandidate;
  onFindSlot: () => void;
  onPlace: (blockId: number, candidate?: SchedulePlacementCandidate) => void;
  onEdit: (block: ScheduleBlock, patternBlocks?: ScheduleBlock[]) => void;
  onArchive: (block: ScheduleBlock) => void;
  onDelete: (blockId: number) => void;
}>) {
  const block = pattern.block;
  const canPlace = block.active && block.block_type === "flexible";

  return (
    <article
      className={`rounded-lg border ${
        block.active
          ? "border-cyan-300/15 bg-cyan-300/[0.06]"
          : "border-white/5 bg-white/[0.02] opacity-60"
      } px-3 py-2`}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="break-words text-sm font-semibold leading-5 text-neutral-100">
            {getScheduleBlockLabel(block)}
          </h4>
          {block.notes ? (
            <p className="mt-1 line-clamp-2 text-xs leading-5 text-neutral-500">
              {block.notes}
            </p>
          ) : null}
        </div>
        <ScheduleBlockActionMenu
          block={block}
          actionBlocks={pattern.blocks}
          mutatingScheduleBlockId={mutatingScheduleBlockId}
          onEdit={onEdit}
          onArchive={onArchive}
          onDelete={onDelete}
        />
      </div>
      <div className="mt-2 flex flex-wrap gap-1.5">
        <span className="whitespace-nowrap rounded-full border border-cyan-300/15 bg-cyan-300/5 px-2 py-0.5 text-[11px] font-semibold text-cyan-100">
          {pattern.daysLabel}
        </span>
        <span className="whitespace-nowrap rounded-full border border-cyan-300/15 bg-cyan-300/5 px-2 py-0.5 text-[11px] font-semibold text-cyan-100">
          {formatBlockCardTiming(block)}
        </span>
        {block.block_type === "flexible" ? (
          <span className="rounded-full border border-violet-300/20 bg-violet-300/10 px-2 py-0.5 text-[11px] font-semibold text-violet-100">
            Flexible
          </span>
        ) : null}
        {block.block_type === "flexible" &&
        block.flexible_placement_mode === "whenever_free" ? (
          <span className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-2 py-0.5 text-[11px] font-semibold text-emerald-100">
            Whenever free
          </span>
        ) : null}
        {block.block_type === "flexible" &&
        block.time_preference &&
        block.time_preference !== "anytime" ? (
          <span className="rounded-full border border-amber-300/20 bg-amber-300/10 px-2 py-0.5 text-[11px] font-semibold text-amber-100">
            {timePreferenceLabels[block.time_preference]} preferred
          </span>
        ) : null}
        <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] font-semibold text-neutral-400">
          {formatStatus(block.category)}
        </span>
        <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] font-semibold text-neutral-400">
          {formatStatus(block.priority)}
        </span>
      </div>
      {canPlace ? (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {placementCandidate ? (
            <button
              type="button"
              onClick={() => onPlace(block.id, placementCandidate)}
              disabled={placingScheduleBlockId === block.id}
              className="rounded-md border border-emerald-300/25 bg-emerald-300/10 px-2 py-1 text-xs font-semibold text-emerald-100 hover:bg-emerald-300/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {placingScheduleBlockId === block.id
                ? "Placing..."
                : "Place suggested slot"}
            </button>
          ) : (
            <button
              type="button"
              onClick={isFlexibleColumn ? onFindSlot : undefined}
              className="rounded-md border border-cyan-300/25 bg-cyan-300/10 px-2 py-1 text-xs font-semibold text-cyan-100 hover:bg-cyan-300/20"
            >
              Find Slot
            </button>
          )}
          {placementCandidate ? (
            <span className="text-xs text-neutral-500">
              {formatStatus(placementCandidate.day)} ·{" "}
              {formatTime(placementCandidate.start_time)}-
              {formatTime(placementCandidate.end_time)}
            </span>
          ) : null}
        </div>
      ) : null}
    </article>
  );
}

function ScheduleBlockDisplayGroupCard({
  group,
  isFlexibleColumn,
  mutatingScheduleBlockId,
  placingScheduleBlockId,
  placementCandidatesByBlockId,
  onFindSlot,
  onPlace,
  onEdit,
  onArchive,
  onDelete,
  defaultOpen = false,
}: Readonly<{
  group: ScheduleBlockDisplayGroup;
  isFlexibleColumn: boolean;
  mutatingScheduleBlockId: number | null;
  placingScheduleBlockId: number | null;
  placementCandidatesByBlockId: Map<number, SchedulePlacementCandidate>;
  onFindSlot: () => void;
  onPlace: (blockId: number, candidate?: SchedulePlacementCandidate) => void;
  onEdit: (block: ScheduleBlock, patternBlocks?: ScheduleBlock[]) => void;
  onArchive: (block: ScheduleBlock) => void;
  onDelete: (blockId: number) => void;
  defaultOpen?: boolean;
}>) {
  const [expanded, setExpanded] = useState(defaultOpen);
  const patternRows = groupScheduleBlocksByPattern(group.blocks);
  const needsPlacement = patternRows.filter(
    (pattern) =>
      pattern.block.active &&
      pattern.block.block_type === "flexible",
  ).length;
  const summaryLabel =
    needsPlacement > 0
      ? `${group.summaryLabel} · ${needsPlacement} needs placement`
      : group.summaryLabel;

  return (
    <article className="rounded-lg border border-white/10 bg-white/[0.03]">
      <button
        type="button"
        onClick={() => setExpanded((current) => !current)}
        className="flex min-h-12 w-full cursor-pointer items-center justify-between gap-3 px-3 py-2 text-left"
      >
        <span className="min-w-0">
          <span className="block truncate text-sm font-semibold text-neutral-100">
            {group.label}
          </span>
          <span className="mt-0.5 block text-xs leading-5 text-neutral-500">
            {summaryLabel}
          </span>
        </span>
        <span className="shrink-0 rounded-full border border-white/10 bg-neutral-950 px-2 py-0.5 text-[11px] font-semibold text-neutral-400">
          {expanded ? "Close" : "Open"}
        </span>
      </button>
      {expanded ? (
        <div className="grid gap-2 border-t border-white/10 p-2">
          {patternRows.map((pattern) => (
            <ScheduleBlockPatternRowCard
              key={pattern.key}
              pattern={pattern}
              isFlexibleColumn={isFlexibleColumn}
              mutatingScheduleBlockId={mutatingScheduleBlockId}
              placingScheduleBlockId={placingScheduleBlockId}
              placementCandidate={placementCandidatesByBlockId.get(
                pattern.block.id,
              )}
              onFindSlot={onFindSlot}
              onPlace={onPlace}
              onEdit={onEdit}
              onArchive={onArchive}
              onDelete={onDelete}
            />
          ))}
        </div>
      ) : null}
    </article>
  );
}

export default function OrbitBoard({
  majorEvents: initialMajorEvents,
  event: initialEvent,
  milestones,
  reviews,
  reviewsError,
  readiness,
  readinessError,
  morningBriefing,
  morningBriefingError,
  inboxTasks,
  inboxTasksError,
  dailyCloseout: initialDailyCloseout,
  dailyCloseoutError,
  recommendations,
  recommendationsError,
  milestoneTasksById,
  milestoneAdvisoriesById,
  latestProgressHistoryByMilestoneId,
  agents: initialAgents,
  agentsError,
  agentPrioritization,
  agentPrioritizationError,
  scheduledAgentsStatus: initialScheduledAgentsStatus,
  scheduledAgentsStatusError,
  morningCheckInStatus: initialMorningCheckInStatus,
  morningCheckInStatusError,
  scheduleBlocks: initialScheduleBlocks,
  scheduleBlocksError,
  scheduleIntelligence,
  scheduleIntelligenceError,
  errorMessage,
}: OrbitBoardProps) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const [expandedMilestoneIds, setExpandedMilestoneIds] = useState<number[]>([]);
  const [applyingMilestoneId, setApplyingMilestoneId] = useState<number | null>(
    null,
  );
  const [dailyCloseout, setDailyCloseout] = useState<DailyCloseout | null>(
    initialDailyCloseout,
  );
  const [showFullCloseout, setShowFullCloseout] = useState(false);
  const [showReviewHistory, setShowReviewHistory] = useState(false);
  const [closeoutRating, setCloseoutRating] = useState("");
  const [closeoutNotes, setCloseoutNotes] = useState("");
  const [loadingCloseout, setLoadingCloseout] = useState(false);
  const [savingCloseoutReview, setSavingCloseoutReview] = useState(false);
  const [agents, setAgents] = useState<AgentDefinition[]>(initialAgents);
  const [runningAgentId, setRunningAgentId] = useState<number | null>(null);
  const [scheduledAgentsStatus, setScheduledAgentsStatus] =
    useState<ScheduledAgentStatus | null>(initialScheduledAgentsStatus);
  const [checkingScheduledAgents, setCheckingScheduledAgents] = useState(false);
  const [morningCheckInStatus, setMorningCheckInStatus] =
    useState<MorningCheckInStatus | null>(initialMorningCheckInStatus);
  const [morningCheckInSummary, setMorningCheckInSummary] = useState<
    string | null
  >(null);
  const [checkingInMorning, setCheckingInMorning] = useState(false);
  const [taskDraftsByRecommendationId, setTaskDraftsByRecommendationId] =
    useState<Record<string, RecommendationTaskDraft>>({});
  const [previewingRecommendationId, setPreviewingRecommendationId] =
    useState<string | null>(null);
  const [creatingRecommendationId, setCreatingRecommendationId] = useState<
    string | null
  >(null);
  const [taskComposerPrefill, setTaskComposerPrefill] =
    useState<TaskComposerPrefill | null>(null);
  const [majorEvents, setMajorEvents] =
    useState<MajorEvent[]>(initialMajorEvents);
  const [selectedMajorEventId, setSelectedMajorEventId] = useState<
    number | null
  >(initialEvent?.id ?? getPrimaryMajorEvent(initialMajorEvents)?.id ?? null);
  const [majorEventForm, setMajorEventForm] =
    useState<MajorEventFormState>(emptyMajorEventForm);
  const [editingMajorEventId, setEditingMajorEventId] = useState<number | null>(
    null,
  );
  const [savingMajorEvent, setSavingMajorEvent] = useState(false);
  const [archivingMajorEventId, setArchivingMajorEventId] = useState<
    number | null
  >(null);
  const [scheduleBlocks, setScheduleBlocks] = useState<ScheduleBlock[]>(
    initialScheduleBlocks,
  );
  const [scheduleForm, setScheduleForm] =
    useState<ScheduleFormState>(emptyScheduleForm);
  const [activeScheduleSection, setActiveScheduleSection] =
    useState<ScheduleSection>("calendar");
  const [visibleWeekStart, setVisibleWeekStart] = useState(() =>
    getWeekStart(new Date()),
  );
  const [editingScheduleBlockId, setEditingScheduleBlockId] = useState<
    number | null
  >(null);
  const [savingScheduleBlock, setSavingScheduleBlock] = useState(false);
  const [mutatingScheduleBlockId, setMutatingScheduleBlockId] = useState<
    number | null
  >(null);
  const [placingScheduleBlockId, setPlacingScheduleBlockId] = useState<
    number | null
  >(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const selectedEvent =
    majorEvents.find((majorEvent) => majorEvent.id === selectedMajorEventId) ??
    initialEvent ??
    getPrimaryMajorEvent(majorEvents);
  const event = selectedEvent;
  const eventMilestones = useMemo(
    () =>
      event
        ? milestones.filter((milestone) => milestone.major_event_id === event.id)
        : [],
    [event, milestones],
  );
  const eventReadiness = useMemo(
    () =>
      event
        ? readiness.filter((category) => category.major_event_id === event.id)
        : readiness,
    [event, readiness],
  );
  const eventMilestoneIds = useMemo(
    () => new Set(eventMilestones.map((milestone) => milestone.id)),
    [eventMilestones],
  );
  const eventReadinessIds = useMemo(
    () => new Set(eventReadiness.map((category) => category.id)),
    [eventReadiness],
  );
  const daysRemaining = getDaysRemaining(event?.target_date ?? null);
  const progressPercentage = getMajorEventProgress(event);
  const overallReadiness = getOverallReadiness(eventReadiness);
  const priorityTasks = useMemo(() => {
    const byId = new Map<number, MorningBriefingTask>();

    (morningBriefing?.top_tasks ?? [])
      .filter((task) => {
        const linkedMilestones = task.milestones ?? [];
        return (
          linkedMilestones.some((milestone) =>
            eventMilestoneIds.has(milestone.id),
          ) ||
          linkedMilestones.some(
            (milestone) =>
              event?.id !== undefined && milestone.major_event_id === event.id,
          ) ||
          (task.milestone_title
            ? eventMilestones.some(
                (milestone) => milestone.title === task.milestone_title,
              )
            : false)
        );
      })
      .forEach((task) => byId.set(task.id, task));

    eventMilestones.forEach((milestone) => {
      (milestoneTasksById[milestone.id] ?? []).forEach((task) => {
        if (isTaskOpen(task) && !byId.has(task.id)) {
          byId.set(task.id, {
            ...task,
            milestone_title: milestone.title,
          });
        }
      });
    });

    return Array.from(byId.values())
      .filter(isTaskOpen)
      .sort((left, right) => {
        const leftScore = left.priority_score ?? 0;
        const rightScore = right.priority_score ?? 0;
        if (leftScore !== rightScore) {
          return rightScore - leftScore;
        }
        return left.title.localeCompare(right.title);
      })
      .slice(0, 3);
  }, [event, eventMilestoneIds, eventMilestones, milestoneTasksById, morningBriefing]);
  const strategicGaps = useMemo(
    () =>
      (morningBriefing?.strategic_gaps ?? []).filter((gap) =>
        eventMilestoneIds.has(gap.milestone_id),
      ),
    [eventMilestoneIds, morningBriefing],
  );
  const activeBlockers = useMemo(() => {
    const blockers: string[] = [];
    const stalledMilestones = eventMilestones.filter(
      (milestone) =>
        milestone.title !== INBOX_MILESTONE_TITLE &&
        ["active", "in_progress"].includes(milestone.status.toLowerCase()) &&
        milestone.progress_percent === 0,
    );
    const lowReadiness = eventReadiness.filter(
      (category) => category.current_score < 50,
    );

    stalledMilestones.slice(0, 2).forEach((milestone) => {
      blockers.push(
        `Milestone is active but still at 0%: ${milestone.title}.`,
      );
    });

    if (lowReadiness.length > 0) {
      blockers.push(
        `Low readiness categories: ${lowReadiness
          .slice(0, 3)
          .map((category) => category.category_name)
          .join(", ")}.`,
      );
    }

    return blockers;
  }, [eventMilestones, eventReadiness]);
  const mostRecentReview = reviews[0] ?? null;
  const topRecommendations = useMemo(() => {
    const scopedTaskIds = new Set(priorityTasks.map((task) => task.id));
    const sourceRecommendations =
      recommendations?.recommendations ?? morningBriefing?.recommendations ?? [];

    return sourceRecommendations.filter((recommendation) => {
      const targetId = getRecommendationTargetId(recommendation);

      if (recommendation.category === "strategic_gap") {
        return targetId !== null && eventMilestoneIds.has(targetId);
      }

      if (recommendation.category === "task_execution") {
        return targetId !== null && scopedTaskIds.has(targetId);
      }

      if (recommendation.category === "readiness_improvement") {
        return targetId !== null && eventReadinessIds.has(targetId);
      }

      if (recommendation.category === "blocker_resolution") {
        return activeBlockers.some((blocker) =>
          recommendation.recommendation.includes(blocker),
        );
      }

      return false;
    });
  }, [
    activeBlockers,
    eventMilestoneIds,
    eventReadinessIds,
    morningBriefing,
    priorityTasks,
    recommendations,
  ]);
  const tagMilestones = eventMilestones.filter(
    (milestone) => milestone.title !== INBOX_MILESTONE_TITLE,
  );
  const suggestedNextAction = topRecommendations[0]?.recommendation ?? null;

  const activeMilestones = useMemo(
    () =>
      [...eventMilestones].sort(
        (left, right) => left.progress_percent - right.progress_percent,
      ),
    [eventMilestones],
  );
  const visibleWeekDays = useMemo(
    () =>
      dayOptions.map((day, index) => {
        const date = addDays(visibleWeekStart, index);
        return {
          day,
          date,
          dateKey: toDateOnlyString(date),
        };
      }),
    [visibleWeekStart],
  );
  const scheduleBlocksByDate = useMemo(() => {
    const blocksByDate = new Map<string, ScheduleBlock[]>(
      visibleWeekDays.map((day) => [day.dateKey, []]),
    );

    scheduleBlocks.forEach((block) => {
      if (!block.active) {
        return;
      }

      getScheduleBlockTargetDateKeys(block, visibleWeekDays).forEach((dateKey) => {
        blocksByDate.set(dateKey, [...(blocksByDate.get(dateKey) ?? []), block]);
      });
    });

    visibleWeekDays.forEach((day) => {
      blocksByDate.set(
        day.dateKey,
        [...(blocksByDate.get(day.dateKey) ?? [])].sort((left, right) => {
          const leftSort = getCalendarScheduleSortKey(left);
          const rightSort = getCalendarScheduleSortKey(right);
          if (leftSort !== rightSort) {
            return leftSort.localeCompare(rightSort);
          }
          return left.id - right.id;
        }),
      );
    });

    return new Map(
      Array.from(blocksByDate.entries()).map(([dateKey, blocks]) => [
        dateKey,
        groupCalendarScheduleBlocks(blocks),
      ]),
    );
  }, [scheduleBlocks, visibleWeekDays]);
  const unplacedScheduleBlocks = useMemo(() => {
    return scheduleBlocks
      .filter(
        (block) =>
          block.block_type === "flexible" &&
          block.active,
      )
      .sort((left, right) => {
        const leftPriority = priorityOptions.indexOf(left.priority);
        const rightPriority = priorityOptions.indexOf(right.priority);
        if (leftPriority !== rightPriority) {
          return rightPriority - leftPriority;
        }
        return getScheduleBlockLabel(left).localeCompare(
          getScheduleBlockLabel(right),
        );
      });
  }, [scheduleBlocks]);
  const scheduleBlockGroups = useMemo(
    () => ({
      fixed: groupScheduleBlocks(
        scheduleBlocks.filter(
          (block) => block.block_type === "fixed" && block.active,
        ),
      ),
      flexible: groupScheduleBlocks(
        scheduleBlocks.filter(
          (block) => block.block_type === "flexible" && block.active,
        ),
      ),
      archived: groupScheduleBlocks(scheduleBlocks.filter((block) => !block.active)),
    }),
    [scheduleBlocks],
  );
  const placementCandidatesByBlockId = useMemo(() => {
    const candidates = new Map<number, SchedulePlacementCandidate>();
    (scheduleIntelligence?.placement_candidates ?? []).forEach((candidate) => {
      candidates.set(candidate.flexible_block_id, candidate);
    });
    return candidates;
  }, [scheduleIntelligence]);
  const currentScheduleMonthYear = useMemo(
    () => formatWeekHeading(visibleWeekDays),
    [visibleWeekDays],
  );

  useEffect(() => {
    if (!toast) {
      return;
    }

    const timeout = window.setTimeout(() => {
      setToast(null);
    }, 4000);

    return () => window.clearTimeout(timeout);
  }, [toast]);

  function changeActiveTab(nextTab: Tab) {
    if (nextTab !== "Tasks") {
      setTaskComposerPrefill(null);
    }
    setActiveTab(nextTab);
  }

  async function applySuggestedProgress(
    milestoneId: number,
    progressPercent: number,
  ) {
    setApplyingMilestoneId(milestoneId);
    setToast(null);

    const response = await fetch(`${API_BASE}/orbit/milestones/${milestoneId}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        progress_percent: progressPercent,
        progress_update_source: "task_advisory",
        progress_update_reason: "Applied task-derived progress advisory.",
      }),
    });

    if (!response.ok) {
      setToast({
        message: "Could not apply suggested progress.",
        type: "error",
      });
      setApplyingMilestoneId(null);
      return;
    }

    setToast({
      message: "Suggested progress applied.",
      type: "success",
    });
    setApplyingMilestoneId(null);
    router.refresh();
  }

  async function generateDailyCloseout() {
    setLoadingCloseout(true);
    setToast(null);

    const response = await fetch(`${API_BASE}/orbit/daily-closeout`);

    if (!response.ok) {
      setToast({
        message: "Could not generate daily closeout.",
        type: "error",
      });
      setLoadingCloseout(false);
      return;
    }

    setDailyCloseout((await response.json()) as DailyCloseout);
    setShowFullCloseout(false);
    setLoadingCloseout(false);
  }

  async function saveDailyCloseoutReview() {
    setSavingCloseoutReview(true);
    setToast(null);

    const ratingValue = closeoutRating.trim();
    const response = await fetch(`${API_BASE}/orbit/daily-closeout/review`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        rating: ratingValue ? Number(ratingValue) : undefined,
        summary: closeoutNotes.trim() || undefined,
      }),
    });

    if (!response.ok) {
      setToast({
        message: "Could not save daily review.",
        type: "error",
      });
      setSavingCloseoutReview(false);
      return;
    }

    setToast({
      message: "Daily review saved.",
      type: "success",
    });
    setCloseoutRating("");
    setCloseoutNotes("");
    setSavingCloseoutReview(false);
    router.refresh();
  }

  async function runAgent(agentId: number) {
    setRunningAgentId(agentId);
    setToast(null);

    const response = await fetch(`${API_BASE}/agents/${agentId}/run`, {
      method: "POST",
    });

    if (!response.ok) {
      setToast({
        message: "Could not run agent.",
        type: "error",
      });
      setRunningAgentId(null);
      return;
    }

    const run = (await response.json()) as AgentRun;
    setAgents((current) =>
      current.map((agent) =>
        agent.id === agentId ? { ...agent, last_run: run } : agent,
      ),
    );
    setToast({
      message:
        run.status === "completed"
          ? "Agent run logged."
          : "Agent run finished with an error.",
      type: run.status === "completed" ? "success" : "error",
    });
    setRunningAgentId(null);
    router.refresh();
  }

  async function checkScheduledAgentsNow() {
    setCheckingScheduledAgents(true);
    setToast(null);

    const response = await fetch(`${API_BASE}/agents/scheduled/run-once`, {
      method: "POST",
    });

    if (!response.ok) {
      setToast({
        message: "Could not check scheduled agents.",
        type: "error",
      });
      setCheckingScheduledAgents(false);
      return;
    }

    const result = (await response.json()) as ScheduledAgentRunOnceResult;
    setScheduledAgentsStatus(result.status);
    if (result.runs.length > 0) {
      setAgents((current) =>
        current.map((agent) => {
          const run = result.runs.find((entry) => entry.agent_id === agent.id);
          return run ? { ...agent, last_run: run } : agent;
        }),
      );
    }
    const runCount = result.actions.filter(
      (action) => action.status === "ran",
    ).length;
    const snapshotCaptured = result.actions.some(
      (action) =>
        action.schedule === "prioritization_snapshot" &&
        action.status === "captured",
    );
    setToast({
      message:
        runCount > 0 || snapshotCaptured
          ? "Scheduled agent check completed."
          : "No scheduled agents are due.",
      type: "success",
    });
    setCheckingScheduledAgents(false);
    router.refresh();
  }

  async function runMorningCheckIn() {
    setCheckingInMorning(true);
    setToast(null);

    const response = await fetch(`${API_BASE}/agents/morning/check-in`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        source: "ui",
        speak: false,
      }),
    });

    if (!response.ok) {
      setToast({
        message: "Could not run morning check-in.",
        type: "error",
      });
      setCheckingInMorning(false);
      return;
    }

    const result = (await response.json()) as MorningCheckInResult;
    setMorningCheckInStatus(result.status);
    setMorningCheckInSummary(result.summary ?? null);
    if (result.agent_run) {
      setAgents((current) =>
        current.map((agent) =>
          agent.id === result.agent_run?.agent_id
            ? { ...agent, last_run: result.agent_run }
            : agent,
        ),
      );
    }
    setToast({
      message: "Morning check-in acknowledged.",
      type: "success",
    });
    setCheckingInMorning(false);
    router.refresh();
  }

  async function previewRecommendationTask(gap: StrategicGap) {
    const recommendationId = getRecommendationId(gap);
    setPreviewingRecommendationId(recommendationId);
    setToast(null);

    const response = await fetch(
      `${API_BASE}/orbit/recommendations/${recommendationId}/task-draft`,
      { method: "POST" },
    );

    if (!response.ok) {
      setToast({
        message: "Could not preview task draft.",
        type: "error",
      });
      setPreviewingRecommendationId(null);
      return;
    }

    const draft = (await response.json()) as RecommendationTaskDraft;
    setTaskDraftsByRecommendationId((current) => ({
      ...current,
      [recommendationId]: draft,
    }));
    setPreviewingRecommendationId(null);
  }

  async function createRecommendationTask(gap: StrategicGap) {
    const recommendationId = getRecommendationId(gap);
    setCreatingRecommendationId(recommendationId);
    setToast(null);

    const response = await fetch(
      `${API_BASE}/orbit/recommendations/${recommendationId}/task-draft`,
      { method: "POST" },
    );

    if (!response.ok) {
      setToast({
        message: "Could not open task composer.",
        type: "error",
      });
      setCreatingRecommendationId(null);
      return;
    }

    const draft = (await response.json()) as RecommendationTaskDraft;
    setTaskDraftsByRecommendationId((current) => ({
      ...current,
      [recommendationId]: draft,
    }));
    setTaskComposerPrefill({
      title: draft.title,
      description: draft.description,
      milestoneIds: draft.milestone_ids,
      helperText: "Task composer opened with milestone preselected.",
      requestId: Date.now(),
    });
    setActiveTab("Tasks");
    setToast({
      message: "Task composer opened with milestone preselected.",
      type: "success",
    });
    setCreatingRecommendationId(null);
  }

  function setMajorEventField<K extends keyof MajorEventFormState>(
    field: K,
    value: MajorEventFormState[K],
  ) {
    setMajorEventForm((current) => ({ ...current, [field]: value }));
  }

  function startMajorEventCreate() {
    setEditingMajorEventId(null);
    setMajorEventForm(emptyMajorEventForm);
  }

  function startMajorEventEdit(majorEvent: MajorEvent) {
    setEditingMajorEventId(majorEvent.id);
    setMajorEventForm(majorEventFormFromEvent(majorEvent));
    setSelectedMajorEventId(majorEvent.id);
  }

  function getMajorEventPayload() {
    const payload = {
      title: majorEventForm.title.trim(),
      description: majorEventForm.description.trim() || null,
      target_date: majorEventForm.target_date || null,
      status: majorEventForm.status,
    };

    if (editingMajorEventId) {
      return payload;
    }

    return {
      ...payload,
      progress_percent: 0,
    };
  }

  async function saveMajorEvent() {
    if (!majorEventForm.title.trim()) {
      setToast({ message: "Major event title is required.", type: "error" });
      return;
    }

    setSavingMajorEvent(true);
    setToast(null);

    const response = await fetch(
      editingMajorEventId
        ? `${API_BASE}/orbit/major-events/${editingMajorEventId}`
        : `${API_BASE}/orbit/major-events`,
      {
        method: editingMajorEventId ? "PATCH" : "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(getMajorEventPayload()),
      },
    );

    if (!response.ok) {
      setToast({ message: "Could not save major event.", type: "error" });
      setSavingMajorEvent(false);
      return;
    }

    const savedEvent = (await response.json()) as MajorEvent;
    setMajorEvents((current) => {
      if (editingMajorEventId) {
        return current.map((majorEvent) =>
          majorEvent.id === savedEvent.id ? savedEvent : majorEvent,
        );
      }

      return [...current, savedEvent];
    });
    setSelectedMajorEventId(savedEvent.id);
    setEditingMajorEventId(null);
    setMajorEventForm(emptyMajorEventForm);
    setToast({ message: "Major event saved.", type: "success" });
    setSavingMajorEvent(false);
    router.refresh();
  }

  async function archiveMajorEvent(majorEvent: MajorEvent) {
    setArchivingMajorEventId(majorEvent.id);
    setToast(null);

    const response = await fetch(
      `${API_BASE}/orbit/major-events/${majorEvent.id}`,
      { method: "DELETE" },
    );

    if (!response.ok) {
      setToast({ message: "Could not archive major event.", type: "error" });
      setArchivingMajorEventId(null);
      return;
    }

    const archivedEvent = (await response.json()) as MajorEvent;
    setMajorEvents((current) =>
      current.map((entry) =>
        entry.id === archivedEvent.id ? archivedEvent : entry,
      ),
    );
    if (selectedMajorEventId === archivedEvent.id) {
      const nextEvent = getPrimaryMajorEvent(
        majorEvents.map((entry) =>
          entry.id === archivedEvent.id ? archivedEvent : entry,
        ),
      );
      setSelectedMajorEventId(nextEvent?.id ?? archivedEvent.id);
    }
    setToast({ message: "Major event archived.", type: "success" });
    setArchivingMajorEventId(null);
    router.refresh();
  }

  function setScheduleField<K extends keyof ScheduleFormState>(
    field: K,
    value: ScheduleFormState[K],
  ) {
    setScheduleForm((current) => ({ ...current, [field]: value }));
  }

  function setScheduleSameTime(value: boolean) {
    setScheduleForm((current) => ({
      ...current,
      same_time: value,
      start_time: value ? current.start_time : "",
      end_time: value ? current.end_time : "",
      date_times: value
        ? current.date_times
        : Object.fromEntries(
            Object.entries(current.date_times).map(([dateKey, dateTime]) => [
              dateKey,
              {
                start_time: dateTime.start_time,
                end_time: dateTime.end_time,
              },
            ]),
          ),
    }));
  }

  function clearScheduleTimes() {
    setScheduleForm((current) => ({
      ...current,
      start_time: "",
      end_time: "",
      date_times: Object.fromEntries(
        Object.keys(current.date_times).map((dateKey) => [
          dateKey,
          { start_time: "", end_time: "" },
        ]),
      ),
    }));
  }

  function togglePreferredScheduleDay(day: DayOfWeek) {
    setScheduleForm((current) => {
      const preferredDays = current.preferred_days.includes(day)
        ? current.preferred_days.filter((value) => value !== day)
        : [...current.preferred_days, day];
      return {
        ...current,
        preferred_days: preferredDays,
        day_of_week: preferredDays[0] ?? "",
      };
    });
  }

  function toggleScheduleSelectedDate(dateKey: string) {
    setScheduleForm((current) => {
      const selected = current.selected_dates.includes(dateKey)
        ? current.selected_dates.filter((value) => value !== dateKey)
        : [...current.selected_dates, dateKey];
      const dateTimes = { ...current.date_times };

      if (selected.includes(dateKey) && !dateTimes[dateKey]) {
        dateTimes[dateKey] = {
          start_time: current.start_time,
          end_time: current.end_time,
        };
      }

      return {
        ...current,
        selected_dates: selected,
        date_times: dateTimes,
        day_of_week:
          editingScheduleBlockId || selected.length === 0
            ? current.day_of_week
            : "",
        specific_date:
          editingScheduleBlockId || selected.length === 0
            ? current.specific_date
            : "",
      };
    });
  }

  function setScheduleDateTime(
    dateKey: string,
    field: "start_time" | "end_time",
    value: string,
  ) {
    setScheduleForm((current) => ({
      ...current,
      date_times: {
        ...current.date_times,
        [dateKey]: {
          start_time: current.date_times[dateKey]?.start_time ?? current.start_time,
          end_time: current.date_times[dateKey]?.end_time ?? current.end_time,
          [field]: value,
        },
      },
    }));
  }

  function setSchedulePickerWeek(nextWeekStart: Date) {
    setVisibleWeekStart(nextWeekStart);
    setScheduleForm((current) => ({
      ...current,
      selected_dates: [],
      date_times: {},
    }));
  }

  function getEditingScheduleBlock() {
    return (
      scheduleBlocks.find((block) => block.id === editingScheduleBlockId) ??
      null
    );
  }

  function getEditBaseDateKey(block: ScheduleBlock | null) {
    if (!block) {
      return "";
    }

    if (block.specific_date) {
      return block.specific_date;
    }

    if (block.day_of_week) {
      return getWeekDateKeyForDay(visibleWeekStart, block.day_of_week);
    }

    return "";
  }

  function scheduleBlockMatchesPayload(
    block: ScheduleBlock,
    payload: ReturnType<typeof getSchedulePayload>,
    targetDateKey: string,
    targetDay: DayOfWeek,
  ) {
    const titleMatches =
      (block.title ?? "").trim() === String(payload.title ?? "").trim();
    const categoryMatches = block.category === payload.category;
    const timeMatches =
      (block.start_time ?? "") === (payload.start_time ?? "") &&
      (block.end_time ?? "") === (payload.end_time ?? "");

    if (!titleMatches || !categoryMatches || !timeMatches) {
      return false;
    }

    if (block.recurrence === "daily") {
      return true;
    }

    if (payload.specific_date) {
      return block.specific_date === targetDateKey;
    }

    return block.day_of_week === targetDay && block.recurrence === payload.recurrence;
  }

  function scheduleBlockMatchesSelectedDayApply(
    block: ScheduleBlock,
    sourceBlock: ScheduleBlock,
    selectedDays: Set<DayOfWeek>,
  ) {
    if (block.block_type !== "fixed") {
      return false;
    }
    if (!block.day_of_week || !selectedDays.has(block.day_of_week)) {
      return false;
    }
    if (block.category !== sourceBlock.category) {
      return false;
    }
    if (getScheduleBlockLabel(block) !== getScheduleBlockLabel(sourceBlock)) {
      return false;
    }
    return (block.recurrence ?? "once") === (sourceBlock.recurrence ?? "once");
  }

  function startScheduleBlockCreate(blockType: ScheduleBlockType) {
    setEditingScheduleBlockId(null);
    setScheduleForm({
      ...emptyScheduleForm,
      block_type: blockType,
      day_of_week: blockType === "fixed" ? "monday" : "",
      preferred_days: [],
      flexible_placement_mode:
        blockType === "flexible" ? "whenever_free" : "preferred_day",
    });
    setActiveScheduleSection("add");
  }

  function startScheduleBlockEdit(
    block: ScheduleBlock,
    patternBlocks: ScheduleBlock[] = [block],
  ) {
    const editWeekStart = block.specific_date
      ? getWeekStart(new Date(`${block.specific_date}T00:00:00`))
      : visibleWeekStart;
    const baseDateKey =
      block.specific_date ??
      (block.day_of_week
        ? getWeekDateKeyForDay(editWeekStart, block.day_of_week)
        : "");
    const patternDateKeys = patternBlocks
      .map((patternBlock) =>
        patternBlock.specific_date ??
        (patternBlock.day_of_week
          ? getWeekDateKeyForDay(editWeekStart, patternBlock.day_of_week)
          : ""),
      )
      .filter(Boolean);
    const selectedDateKeys =
      patternDateKeys.length > 0
        ? Array.from(new Set(patternDateKeys))
        : baseDateKey
          ? [baseDateKey]
          : [];
    const dateTimes = Object.fromEntries(
      patternBlocks
        .map((patternBlock) => {
          const dateKey =
            patternBlock.specific_date ??
            (patternBlock.day_of_week
              ? getWeekDateKeyForDay(editWeekStart, patternBlock.day_of_week)
              : "");
          return dateKey
            ? [
                dateKey,
                {
                  start_time: patternBlock.start_time ?? "",
                  end_time: patternBlock.end_time ?? "",
                },
              ]
            : null;
        })
        .filter(
          (
            entry,
          ): entry is [string, { start_time: string; end_time: string }] =>
            entry !== null,
        ),
    );

    setEditingScheduleBlockId(block.id);
    setVisibleWeekStart(editWeekStart);
    setScheduleForm({
      ...scheduleFormFromBlock(block),
      selected_dates: selectedDateKeys,
      date_times: dateTimes,
    });
    setActiveScheduleSection("add");
  }

  function getSchedulePayload(
    overrides: Partial<Pick<
      ScheduleFormState,
      "day_of_week" | "specific_date" | "start_time" | "end_time" | "recurrence"
    >> = {},
  ) {
    const form = { ...scheduleForm, ...overrides };
    const durationMinutes =
      form.block_type === "flexible"
        ? getDurationMinutesFromForm(form)
        : null;
    const usesWheneverFree =
      form.block_type === "flexible" &&
      form.flexible_placement_mode === "whenever_free";
    const preferredDays = usesWheneverFree
      ? []
      : form.block_type === "flexible"
        ? form.preferred_days
        : [];
    const recurrenceEndType =
      form.recurrence === "once" ? "never" : form.recurrence_end_type;

    return {
      title: form.title.trim(),
      block_type: form.block_type,
      category: form.category,
      day_of_week:
        usesWheneverFree
          ? null
          : form.block_type === "flexible" && preferredDays.length > 0
            ? preferredDays[0]
            : form.day_of_week || null,
      specific_date: usesWheneverFree ? null : form.specific_date || null,
      start_time: form.start_time || null,
      end_time: form.end_time || null,
      duration_minutes: durationMinutes,
      recurrence: form.recurrence,
      recurrence_end_type: recurrenceEndType,
      recurrence_end_date:
        recurrenceEndType === "date" ? form.recurrence_end_date || null : null,
      recurrence_count:
        recurrenceEndType === "occurrences" && form.recurrence_count
          ? Number(form.recurrence_count)
          : null,
      recurrence_weeks:
        recurrenceEndType === "weeks" && form.recurrence_weeks
          ? Number(form.recurrence_weeks)
          : null,
      preferred_days: preferredDays,
      time_preference: form.time_preference,
      flexible_placement_mode: form.flexible_placement_mode,
      priority: form.priority,
      notes: form.notes.trim() || null,
      active: form.active,
    };
  }

  async function saveScheduleBlock() {
    const editingBlock = getEditingScheduleBlock();
    const editBaseDateKey = getEditBaseDateKey(editingBlock);
    const selectedDates =
      scheduleForm.block_type === "fixed" ? scheduleForm.selected_dates : [];
    const selectedDateEntries = selectedDates
      .map((dateKey) => {
        const weekDay = visibleWeekDays.find((day) => day.dateKey === dateKey);
        return weekDay ? { dateKey, day: weekDay.day } : null;
      })
      .filter(
        (entry): entry is { dateKey: string; day: DayOfWeek } => entry !== null,
      );
    const shouldApplySelectedDays =
      Boolean(editingScheduleBlockId) &&
      scheduleForm.block_type === "fixed" &&
      selectedDateEntries.length > 0;
    const additionalSelectedDates = editingScheduleBlockId
      ? []
      : selectedDates;
    const editDateTime =
      editingScheduleBlockId && editBaseDateKey
        ? scheduleForm.date_times[editBaseDateKey]
        : null;
    const baseStartTime =
      scheduleForm.block_type === "fixed" && !scheduleForm.same_time && editDateTime
        ? editDateTime.start_time
        : scheduleForm.start_time;
    const baseEndTime =
      scheduleForm.block_type === "fixed" && !scheduleForm.same_time && editDateTime
        ? editDateTime.end_time
        : scheduleForm.end_time;

    if (
      scheduleForm.block_type === "fixed" &&
      !shouldApplySelectedDays &&
      additionalSelectedDates.length === 0 &&
      ((!scheduleForm.day_of_week && !scheduleForm.specific_date) ||
        !baseStartTime ||
        !baseEndTime)
    ) {
      setToast({
        message: "Fixed blocks need a recurring day or date, plus start and end time.",
        type: "error",
      });
      return;
    }

    if (
      scheduleForm.recurrence !== "once" &&
      scheduleForm.recurrence_end_type === "date" &&
      !scheduleForm.recurrence_end_date
    ) {
      setToast({
        message: "Recurrence end date is required.",
        type: "error",
      });
      return;
    }

    if (
      scheduleForm.recurrence !== "once" &&
      scheduleForm.recurrence_end_type === "occurrences" &&
      !scheduleForm.recurrence_count
    ) {
      setToast({
        message: "Occurrence count is required.",
        type: "error",
      });
      return;
    }

    if (
      scheduleForm.recurrence !== "once" &&
      scheduleForm.recurrence_end_type === "weeks" &&
      !scheduleForm.recurrence_weeks
    ) {
      setToast({
        message: "Week count is required.",
        type: "error",
      });
      return;
    }

    if (
      scheduleForm.block_type === "fixed" &&
      (additionalSelectedDates.length > 0 || shouldApplySelectedDays)
    ) {
      const datesToValidate = shouldApplySelectedDays
        ? selectedDates
        : additionalSelectedDates;
      const missingDateTime = datesToValidate.some((dateKey) => {
        const dateTime = scheduleForm.date_times[dateKey];
        const startTime = scheduleForm.same_time
          ? scheduleForm.start_time
          : dateTime?.start_time;
        const endTime = scheduleForm.same_time
          ? scheduleForm.end_time
          : dateTime?.end_time;
        return !startTime || !endTime;
      });

      if (missingDateTime) {
        setToast({
          message: "Selected dates need start and end times.",
          type: "error",
        });
        return;
      }
    }

    if (scheduleForm.block_type === "flexible") {
      const durationMinutes = getDurationMinutesFromForm(scheduleForm);

      if (durationMinutes === null || durationMinutes <= 0) {
        setToast({
          message: "Flexible blocks need a duration greater than 0.",
          type: "error",
        });
        return;
      }

      if (durationMinutes > maxScheduleDurationMinutes) {
        setToast({
          message: "Flexible blocks cannot exceed 8 hours.",
          type: "error",
        });
        return;
      }
    }

    setSavingScheduleBlock(true);
    setToast(null);

    const basePayload = getSchedulePayload({
      start_time: baseStartTime,
      end_time: baseEndTime,
    });
    const additionalPayloads =
      scheduleForm.block_type === "fixed" && additionalSelectedDates.length > 0
        ? additionalSelectedDates.map((dateKey) => {
            const dateTime = scheduleForm.date_times[dateKey] ?? {
              start_time: scheduleForm.start_time,
              end_time: scheduleForm.end_time,
            };
            const targetDay =
              visibleWeekDays.find((weekDay) => weekDay.dateKey === dateKey)
                ?.day ?? "monday";
            const createsWeeklyBlock =
              scheduleForm.recurrence === "weekly" && !scheduleForm.specific_date;

            return getSchedulePayload({
              day_of_week: createsWeeklyBlock ? targetDay : "",
              specific_date: createsWeeklyBlock ? "" : dateKey,
              start_time: scheduleForm.same_time
                ? scheduleForm.start_time
                : dateTime.start_time,
              end_time: scheduleForm.same_time
                ? scheduleForm.end_time
                : dateTime.end_time,
              recurrence: createsWeeklyBlock ? "weekly" : "once",
            });
          })
        : [];
    const duplicateFilteredAdditionalPayloads = additionalPayloads.filter(
      (payload, index) => {
        const dateKey = additionalSelectedDates[index];
        const targetDay =
          visibleWeekDays.find((weekDay) => weekDay.dateKey === dateKey)?.day ??
          "monday";

        return !scheduleBlocks.some(
          (block) =>
            block.id !== editingScheduleBlockId &&
            scheduleBlockMatchesPayload(block, payload, dateKey, targetDay),
        );
      },
    );

    const savedBlocks: ScheduleBlock[] = [];
    let response: Response | null = null;

    if (editingScheduleBlockId && shouldApplySelectedDays) {
      const selectedDays = Array.from(
        new Set(selectedDateEntries.map((entry) => entry.day)),
      );
      const dayTimes = Object.fromEntries(
        selectedDateEntries.map((entry) => {
          const dateTime = scheduleForm.date_times[entry.dateKey] ?? {
            start_time: "",
            end_time: "",
          };
          return [
            entry.day,
            {
              start_time: dateTime.start_time,
              end_time: dateTime.end_time,
            },
          ];
        }),
      );

      response = await fetch(
        `${API_BASE}/orbit/schedule-blocks/${editingScheduleBlockId}/apply-days`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            ...basePayload,
            selected_days: selectedDays,
            same_time: scheduleForm.same_time,
            day_times: dayTimes,
          }),
        },
      );

      if (response.ok) {
        savedBlocks.push(...((await response.json()) as ScheduleBlock[]));
      }
    } else if (editingScheduleBlockId) {
      response = await fetch(
        `${API_BASE}/orbit/schedule-blocks/${editingScheduleBlockId}`,
        {
          method: "PATCH",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(basePayload),
        },
      );

      if (response.ok) {
        savedBlocks.push((await response.json()) as ScheduleBlock);
      }
    }

    const createPayloads = editingScheduleBlockId
      ? []
      : additionalPayloads.length > 0
        ? additionalPayloads
        : [basePayload];

    for (const payload of createPayloads) {
      if (response && !response.ok) {
        break;
      }

      response = await fetch(
        `${API_BASE}/orbit/schedule-blocks`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify(payload),
        },
      );

      if (!response.ok) {
        break;
      }

      savedBlocks.push((await response.json()) as ScheduleBlock);
    }

    if (response && !response.ok) {
      let message = "Could not save schedule block.";
      try {
        const errorBody = (await response?.json()) as { detail?: string };
        message = errorBody.detail ?? message;
      } catch {
        message = "Could not save schedule block.";
      }

      setToast({ message, type: "error" });
      setSavingScheduleBlock(false);
      return;
    }

    setScheduleBlocks((current) => {
      if (editingScheduleBlockId && shouldApplySelectedDays && editingBlock) {
        const selectedDays = new Set(
          selectedDateEntries.map((entry) => entry.day),
        );
        const withoutSelectedDayBlocks = current.filter(
          (block) =>
            !scheduleBlockMatchesSelectedDayApply(
              block,
              editingBlock,
              selectedDays,
            ),
        );
        return [...withoutSelectedDayBlocks, ...savedBlocks];
      }

      if (editingScheduleBlockId) {
        const savedBlock = savedBlocks[0];
        return [
          ...current.map((block) =>
            block.id === savedBlock.id ? savedBlock : block,
          ),
          ...savedBlocks.slice(1),
        ];
      }

      return [...current, ...savedBlocks];
    });
    setScheduleForm({
      ...emptyScheduleForm,
      block_type: scheduleForm.block_type,
      day_of_week: scheduleForm.block_type === "fixed" ? "monday" : "",
      preferred_days: [],
      flexible_placement_mode:
        scheduleForm.block_type === "flexible" ? "whenever_free" : "preferred_day",
    });
    setEditingScheduleBlockId(null);
    setToast({
      message:
        editingScheduleBlockId && savedBlocks.length > 1
          ? `${savedBlocks.length - 1} additional schedule block${
              savedBlocks.length === 2 ? "" : "s"
            } added.`
          : editingScheduleBlockId &&
              duplicateFilteredAdditionalPayloads.length <
                additionalPayloads.length
            ? "Schedule block saved. Matching duplicate days were skipped."
            : savedBlocks.length > 1
          ? `${savedBlocks.length} schedule blocks saved.`
          : "Schedule block saved.",
      type: "success",
    });
    setSavingScheduleBlock(false);
    setActiveScheduleSection("calendar");
    router.refresh();
  }

  async function archiveScheduleBlock(block: ScheduleBlock) {
    setMutatingScheduleBlockId(block.id);
    setToast(null);

    const response = await fetch(
      `${API_BASE}/orbit/schedule-blocks/${block.id}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ active: false }),
      },
    );

    if (!response.ok) {
      setToast({ message: "Could not archive schedule block.", type: "error" });
      setMutatingScheduleBlockId(null);
      return;
    }

    const archivedBlock = (await response.json()) as ScheduleBlock;
    setScheduleBlocks((current) =>
      current.map((entry) =>
        entry.id === archivedBlock.id ? archivedBlock : entry,
      ),
    );
    setToast({ message: "Schedule block archived.", type: "success" });
    setMutatingScheduleBlockId(null);
    router.refresh();
  }

  async function deleteScheduleBlock(blockId: number) {
    setMutatingScheduleBlockId(blockId);
    setToast(null);

    const response = await fetch(`${API_BASE}/orbit/schedule-blocks/${blockId}`, {
      method: "DELETE",
    });

    if (!response.ok) {
      setToast({ message: "Could not delete schedule block.", type: "error" });
      setMutatingScheduleBlockId(null);
      return;
    }

    setScheduleBlocks((current) =>
      current.filter((block) => block.id !== blockId),
    );
    if (editingScheduleBlockId === blockId) {
      setEditingScheduleBlockId(null);
      setScheduleForm(emptyScheduleForm);
    }
    setToast({ message: "Schedule block deleted.", type: "success" });
    setMutatingScheduleBlockId(null);
    router.refresh();
  }

  async function placeFlexibleScheduleBlock(
    blockId: number,
    candidate?: SchedulePlacementCandidate,
  ) {
    setPlacingScheduleBlockId(blockId);
    setToast(null);

    const params = new URLSearchParams();
    if (candidate) {
      params.set("date", candidate.date);
      params.set("start_time", candidate.start_time);
    }
    const queryString = params.toString();
    const response = await fetch(
      `${API_BASE}/orbit/schedule-blocks/${blockId}/place${
        queryString ? `?${queryString}` : ""
      }`,
      { method: "POST" },
    );

    if (!response.ok) {
      let message = "Could not place flexible block.";
      try {
        const errorBody = (await response.json()) as { detail?: string };
        message = errorBody.detail ?? message;
      } catch {
        message = "Could not place flexible block.";
      }

      setToast({ message, type: "error" });
      setPlacingScheduleBlockId(null);
      return;
    }

    const result = (await response.json()) as ScheduleBlockPlacementResult;
    setScheduleBlocks((current) => {
      const withoutPlacedFixedDuplicate = current.filter(
        (block) =>
          block.id !== result.fixed_block.id &&
          block.id !== result.source_block.id,
      );
      return [
        ...withoutPlacedFixedDuplicate,
        result.source_block,
        result.fixed_block,
      ];
    });
    setToast({
      message: result.created
        ? "Flexible block placed on the calendar."
        : "Existing calendar block found. Flexible block archived.",
      type: "success",
    });
    setPlacingScheduleBlockId(null);
    setActiveScheduleSection("calendar");
    router.refresh();
  }

  return (
    <section className="relative overflow-hidden rounded-2xl border border-white/10 bg-neutral-900/80 p-3 shadow-2xl shadow-black/30 sm:p-4">
      {toast ? (
        <div
          className={`absolute right-4 top-4 z-30 max-w-72 rounded-xl border px-3 py-2 text-sm shadow-2xl backdrop-blur ${
            toast.type === "success"
              ? "border-emerald-400/25 bg-emerald-400/10 text-emerald-100 shadow-emerald-950/30"
              : "border-red-400/25 bg-red-500/10 text-red-100 shadow-red-950/30"
          }`}
          role="status"
        >
          {toast.message}
        </div>
      ) : null}

      <div className="-mx-1 mb-4 flex gap-2 overflow-x-auto px-1 pb-1 sm:flex-wrap sm:overflow-visible sm:pb-0">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
              onClick={() => changeActiveTab(tab)}
            className={`shrink-0 rounded-full border px-3 py-2 text-xs font-semibold transition sm:py-1.5 ${
              activeTab === tab
                ? "border-cyan-300/50 bg-cyan-300/15 text-cyan-100"
                : "border-white/10 bg-white/[0.03] text-neutral-400 hover:border-white/20 hover:text-white"
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {errorMessage ? (
        <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-sm text-red-100">
          Orbit API unavailable: {errorMessage}
        </div>
      ) : null}

      {activeTab === "Overview" ? (
        <div className="flex flex-col gap-2 lg:grid lg:grid-cols-[1.1fr_0.9fr] lg:items-start">
          <div className="contents lg:flex lg:flex-col lg:gap-2">
            <div className="order-1 lg:order-none">
              <MiniPanel title="Major Event">
            <div className="flex items-start justify-between gap-4">
              <div>
                <h2 className="text-2xl font-semibold tracking-tight text-white">
                  {event?.title ?? CORPORATE_ESCAPE_TITLE}
                </h2>
                <p className="mt-1 text-xs text-neutral-500">
                  {event
                    ? `${formatDate(event.target_date)} | ${formatStatus(event.status)}`
                    : "Major event not connected yet"}
                </p>
              </div>
              <div className="text-right">
                <p className="text-3xl font-semibold text-white">
                  {daysRemaining ?? "--"}
                </p>
                <p className="text-xs text-neutral-500">days</p>
              </div>
            </div>
            {majorEvents.length > 1 ? (
              <select
                value={event?.id ?? ""}
                onChange={(selectEvent) =>
                  setSelectedMajorEventId(Number(selectEvent.target.value))
                }
                className="mt-3 w-full rounded-lg border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
              >
                {majorEvents.map((majorEvent) => (
                  <option key={majorEvent.id} value={majorEvent.id}>
                    {majorEvent.title} ({formatStatus(majorEvent.status)})
                  </option>
                ))}
              </select>
            ) : null}
            <div className="mt-3">
              <div className="mb-1.5 flex justify-between text-xs text-neutral-400">
                <span>Calculated progress</span>
                <span>{progressPercentage}%</span>
              </div>
              <ProgressBar value={progressPercentage} />
              <p className="mt-1.5 text-xs text-neutral-500">
                Calculated from milestones, readiness, and recent activity.
              </p>
            </div>
              </MiniPanel>
            </div>

            <div className="order-3 lg:order-none">
              <MiniPanel title="Top Priority Tasks">
                {priorityTasks.length > 0 ? (
                  <div className="space-y-1.5">
                    {priorityTasks.map((task) => (
                      <div
                        key={task.id}
                        className="flex items-center justify-between gap-2 rounded-lg bg-white/[0.03] px-2.5 py-1.5"
                      >
                        <span className="min-w-0 truncate text-sm text-neutral-200">
                          {task.title}
                        </span>
                        <div className="flex shrink-0 items-center gap-1.5">
                          <span className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-2 py-0.5 text-[11px] font-semibold text-cyan-100">
                            P{task.priority_score ?? 0}
                          </span>
                          <span className="text-xs text-neutral-500">
                            {task.milestone_title ?? formatStatus(task.status)}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-neutral-500">
                    No priority tasks linked to this event yet.
                  </p>
                )}
              </MiniPanel>
            </div>

            <div className="order-7 lg:order-none">
              <MiniPanel title="Overall Readiness">
                {eventReadiness.length > 0 ? (
                  <>
                    <div className="flex items-center justify-between gap-3">
                      <span className="text-2xl font-semibold text-white">
                        {overallReadiness === null ? "--" : `${overallReadiness}%`}
                      </span>
                      <span className="text-xs text-neutral-500">
                        {eventReadiness.length} categories
                      </span>
                    </div>
                    <div className="mt-2">
                      <ProgressBar value={overallReadiness ?? 0} />
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-neutral-500">
                    No readiness categories for this event yet.
                  </p>
                )}
              </MiniPanel>
            </div>
          </div>

          <div className="contents lg:flex lg:flex-col lg:gap-2">
            <div className="order-2 lg:order-none">
              <MiniPanel title="Suggested Next Action">
                <p className="line-clamp-3 text-sm leading-5 text-neutral-200">
                  {suggestedNextAction ??
                    (morningBriefingError
                      ? "Suggested action unavailable right now."
                      : "No suggested action yet")}
                </p>
              </MiniPanel>
            </div>

            <div className="order-4 lg:order-none">
              <MiniPanel title="Recommendations">
                {topRecommendations.length > 0 ? (
                  <div className="space-y-1.5">
                    {topRecommendations.slice(0, 3).map((recommendation) => (
                      <div
                        key={recommendation.id}
                        className="rounded-lg bg-white/[0.03] px-2.5 py-1.5"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <p className="line-clamp-2 min-w-0 text-sm leading-5 text-neutral-200">
                            {recommendation.recommendation}
                          </p>
                          <span className="shrink-0 rounded-full border border-cyan-300/20 bg-cyan-300/10 px-2 py-0.5 text-[11px] font-semibold text-cyan-100">
                            {recommendation.score}
                          </span>
                        </div>
                        <p className="mt-0.5 text-[11px] uppercase tracking-wide text-neutral-500">
                          {formatStatus(recommendation.category)}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-neutral-500">
                    {recommendationsError
                      ? "Recommendations unavailable right now."
                      : "No recommendations for this event yet."}
                  </p>
                )}
              </MiniPanel>
            </div>

            <div className="order-5 lg:order-none">
              <MiniPanel title="Strategic Gaps">
                {strategicGaps.length > 0 ? (
                  <div className="space-y-1.5">
                    {strategicGaps.slice(0, 2).map((gap) => {
                      const recommendationId = getRecommendationId(gap);
                      const draft = taskDraftsByRecommendationId[recommendationId];

                      return (
                        <div
                          key={gap.milestone_id}
                          className="rounded-lg bg-white/[0.03] px-2.5 py-1.5"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="min-w-0 truncate text-sm text-neutral-200">
                              {gap.title}
                            </span>
                            <span className="shrink-0 rounded-full border border-amber-300/25 bg-amber-300/10 px-2 py-0.5 text-[11px] font-semibold text-amber-100">
                              P{gap.priority_score}
                            </span>
                          </div>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {getCompactGapReasons(gap.reasons).slice(0, 2).map((reason) => (
                              <span
                                key={reason}
                                className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] text-neutral-400"
                              >
                                {reason}
                              </span>
                            ))}
                          </div>
                          <p className="mt-1 truncate text-[11px] text-neutral-500">
                            Milestone: {gap.milestone_title ?? gap.title}
                          </p>
                          <div className="mt-1.5 flex flex-wrap gap-1.5">
                            <button
                              type="button"
                              onClick={() => previewRecommendationTask(gap)}
                              disabled={previewingRecommendationId === recommendationId}
                              className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-xs font-semibold text-neutral-300 hover:border-white/20 hover:text-white disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {previewingRecommendationId === recommendationId
                                ? "Previewing..."
                                : "Preview Task"}
                            </button>
                            <button
                              type="button"
                              onClick={() => createRecommendationTask(gap)}
                              disabled={creatingRecommendationId === recommendationId}
                              className="rounded-md border border-emerald-300/25 bg-emerald-300/10 px-2 py-0.5 text-xs font-semibold text-emerald-100 hover:bg-emerald-300/20 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {creatingRecommendationId === recommendationId
                                ? "Creating..."
                                : "Create Task"}
                            </button>
                          </div>
                          {draft ? (
                            <div className="mt-1.5 rounded-lg border border-white/10 bg-black/20 px-2.5 py-1.5">
                              <p className="truncate text-xs font-semibold text-neutral-200">
                                {draft.title}
                              </p>
                              {draft.description ? (
                                <p className="mt-1 line-clamp-2 text-xs leading-5 text-neutral-400">
                                  {draft.description}
                                </p>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="text-sm text-neutral-500">
                    No strategic gaps for this event yet.
                  </p>
                )}
              </MiniPanel>
            </div>

            <div className="order-6 lg:order-none">
              <MiniPanel title="Current Blockers">
                {activeBlockers.length > 0 ? (
                  <div className="space-y-1.5">
                    {activeBlockers.slice(0, 2).map((blocker) => (
                      <p
                        key={blocker}
                        className="line-clamp-2 rounded-lg border border-red-400/20 bg-red-400/10 px-2.5 py-1.5 text-sm leading-5 text-red-100"
                      >
                        {blocker}
                      </p>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-neutral-500">
                    No blockers detected for this event yet.
                  </p>
                )}
              </MiniPanel>
            </div>
          </div>
        </div>
      ) : null}

      {activeTab === "Major Events" ? (
        <div className="grid gap-3 lg:grid-cols-[0.9fr_1.1fr]">
          <section className="rounded-xl border border-white/10 bg-neutral-950/70 p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-neutral-100">
                  Major Event
                </h2>
                <p className="mt-1 text-xs text-neutral-500">
                  {editingMajorEventId
                    ? "Editing saved event"
                    : "Create a new Orbit anchor"}
                </p>
              </div>
              <button
                type="button"
                onClick={startMajorEventCreate}
                className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs font-semibold text-neutral-300 hover:border-white/20 hover:text-white"
              >
                New Event
              </button>
            </div>

            <div className="space-y-2">
              <input
                type="text"
                value={majorEventForm.title}
                onChange={(event) =>
                  setMajorEventField("title", event.target.value)
                }
                placeholder="Title"
                className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none placeholder:text-neutral-600 focus:border-cyan-300/50"
              />
              <textarea
                value={majorEventForm.description}
                onChange={(event) =>
                  setMajorEventField("description", event.target.value)
                }
                placeholder="Description"
                rows={3}
                className="min-h-24 w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none placeholder:text-neutral-600 focus:border-cyan-300/50"
              />
              <div className="grid gap-2 sm:grid-cols-2">
                <input
                  type="date"
                  value={majorEventForm.target_date}
                  onChange={(event) =>
                    setMajorEventField("target_date", event.target.value)
                  }
                  className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                />
                <select
                  value={majorEventForm.status}
                  onChange={(event) =>
                    setMajorEventField(
                      "status",
                      event.target.value as MajorEventStatus,
                    )
                  }
                  className="rounded-lg border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                >
                  {majorEventStatusOptions.map((statusOption) => (
                    <option key={statusOption} value={statusOption}>
                      {formatStatus(statusOption)}
                    </option>
                  ))}
                </select>
              </div>
              <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                <div className="flex items-center justify-between gap-3 text-xs text-neutral-500">
                  <span>Calculated progress</span>
                  <span>
                    {editingMajorEventId
                      ? `${getMajorEventProgress(
                          majorEvents.find(
                            (majorEvent) => majorEvent.id === editingMajorEventId,
                          ),
                        )}%`
                      : "0%"}
                  </span>
                </div>
                <p className="mt-1 text-xs text-neutral-400">
                  Calculated from milestones, readiness, and recent activity.
                </p>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={saveMajorEvent}
                  disabled={savingMajorEvent}
                  className="rounded-lg border border-emerald-300/25 bg-emerald-300/10 px-3 py-2 text-xs font-semibold text-emerald-100 hover:bg-emerald-300/20 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {savingMajorEvent
                    ? "Saving..."
                    : editingMajorEventId
                      ? "Save Changes"
                      : "Add Event"}
                </button>
                {editingMajorEventId ? (
                  <button
                    type="button"
                    onClick={startMajorEventCreate}
                    className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs font-semibold text-neutral-300 hover:border-white/20 hover:text-white"
                  >
                    Cancel
                  </button>
                ) : null}
              </div>
            </div>
          </section>

          <section className="rounded-xl border border-white/10 bg-neutral-950/70 p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-neutral-100">
                  Events
                </h2>
                <p className="mt-1 text-xs text-neutral-500">
                  {majorEvents.length} event{majorEvents.length === 1 ? "" : "s"}
                </p>
              </div>
              {majorEvents.length > 0 ? (
                <select
                  value={event?.id ?? ""}
                  onChange={(selectEvent) =>
                    setSelectedMajorEventId(Number(selectEvent.target.value))
                  }
                  className="rounded-lg border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                >
                  {majorEvents.map((majorEvent) => (
                    <option key={majorEvent.id} value={majorEvent.id}>
                      {majorEvent.title}
                    </option>
                  ))}
                </select>
              ) : null}
            </div>

            {majorEvents.length > 0 ? (
              <div className="space-y-2">
                {majorEvents.map((majorEvent) => {
                  const linkedMilestones = milestones.filter(
                    (milestone) => milestone.major_event_id === majorEvent.id,
                  );
                  const isSelected = event?.id === majorEvent.id;

                  return (
                    <article
                      key={majorEvent.id}
                      className={`rounded-lg border px-3 py-2 ${
                        isSelected
                          ? "border-cyan-300/30 bg-cyan-300/10"
                          : majorEvent.status === "archived"
                            ? "border-white/5 bg-black/20 opacity-60"
                            : "border-white/10 bg-white/[0.03]"
                      }`}
                    >
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-sm font-semibold text-neutral-100">
                              {majorEvent.title}
                            </h3>
                            <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] text-neutral-400">
                              {formatStatus(majorEvent.status)}
                            </span>
                            {isSelected ? (
                              <span className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-2 py-0.5 text-[11px] text-cyan-100">
                                Selected
                              </span>
                            ) : null}
                          </div>
                          <p className="mt-1 text-xs text-neutral-500">
                            {formatDate(majorEvent.target_date)} |{" "}
                            Calculated progress {getMajorEventProgress(majorEvent)}% |{" "}
                            {linkedMilestones.length} milestone
                            {linkedMilestones.length === 1 ? "" : "s"}
                          </p>
                          <p className="mt-1 text-[11px] text-neutral-500">
                            Calculated from milestones, readiness, and recent
                            activity.
                          </p>
                          {majorEvent.description ? (
                            <p className="mt-1 line-clamp-2 text-sm leading-5 text-neutral-400">
                              {majorEvent.description}
                            </p>
                          ) : null}
                        </div>
                        <div className="flex shrink-0 flex-wrap gap-1.5">
                          <button
                            type="button"
                            onClick={() => setSelectedMajorEventId(majorEvent.id)}
                            className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-xs font-semibold text-neutral-300 hover:border-white/20 hover:text-white"
                          >
                            Select
                          </button>
                          <button
                            type="button"
                            onClick={() => startMajorEventEdit(majorEvent)}
                            className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-xs font-semibold text-neutral-300 hover:border-white/20 hover:text-white"
                          >
                            Edit
                          </button>
                          {majorEvent.status !== "archived" ? (
                            <button
                              type="button"
                              onClick={() => archiveMajorEvent(majorEvent)}
                              disabled={archivingMajorEventId === majorEvent.id}
                              className="rounded-md border border-amber-300/25 bg-amber-300/10 px-2 py-1 text-xs font-semibold text-amber-100 hover:bg-amber-300/20 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              Archive
                            </button>
                          ) : null}
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm text-neutral-500">
                No major events have been added yet.
              </p>
            )}
          </section>
        </div>
      ) : null}

      {activeTab === "Tasks" ? (
        <div className="rounded-xl border border-white/10 bg-neutral-950/70 p-4">
          {inboxTasksError ? (
            <p className="text-sm text-red-100">
              Inbox tasks are unavailable right now.
            </p>
          ) : (
            <InboxTaskControls
              key={taskComposerPrefill?.requestId ?? "task-composer"}
              initialTasks={inboxTasks}
              milestones={tagMilestones}
              composerPrefill={taskComposerPrefill}
              onComposerPrefillConsumed={() => setTaskComposerPrefill(null)}
            />
          )}
        </div>
      ) : null}

      {activeTab === "Schedule" ? (
        <div className="space-y-3">
          <section className="rounded-xl border border-white/10 bg-neutral-950/70 p-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="-mx-1 flex max-w-full gap-2 overflow-x-auto px-1 pb-1 sm:mx-0 sm:flex-wrap sm:overflow-visible sm:pb-0">
                {scheduleSectionItems.map((item) => (
                  <button
                    key={item.id}
                    type="button"
                    onClick={() => setActiveScheduleSection(item.id)}
                    className={`shrink-0 rounded-lg border px-3 py-2.5 text-xs font-semibold transition sm:py-2 ${
                      activeScheduleSection === item.id
                        ? "border-cyan-300/40 bg-cyan-300/15 text-cyan-100"
                        : "border-white/10 bg-white/[0.03] text-neutral-400 hover:text-white"
                    }`}
                  >
                    {item.label}
                  </button>
                ))}
              </div>
              <p className="text-xs text-neutral-500">
                {currentScheduleMonthYear} · {scheduleBlocks.length} block
                {scheduleBlocks.length === 1 ? "" : "s"} saved
                {unplacedScheduleBlocks.length > 0
                  ? ` · ${unplacedScheduleBlocks.length} flexible needs placement`
                  : ""}
              </p>
            </div>
          </section>

          {activeScheduleSection === "add" ? (
          <section className="rounded-xl border border-white/10 bg-neutral-950/70 p-3 sm:p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-neutral-100">
                  Schedule Block
                </h2>
                <p className="mt-1 text-xs text-neutral-500">
                  {editingScheduleBlockId
                    ? "Editing saved block"
                    : "Create a fixed or flexible block"}
                </p>
              </div>
            </div>

            <div className="grid gap-3">
              <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                <span>Type</span>
                <div className="flex gap-1.5">
                  <button
                    type="button"
                    onClick={() => startScheduleBlockCreate("fixed")}
                    className={`rounded-lg border px-4 py-3 text-xs font-semibold sm:py-2 ${
                      scheduleForm.block_type === "fixed"
                        ? "border-cyan-300/40 bg-cyan-300/15 text-cyan-100"
                        : "border-white/10 bg-white/[0.03] text-neutral-400 hover:text-white"
                    }`}
                  >
                    Fixed
                  </button>
                  <button
                    type="button"
                    onClick={() => startScheduleBlockCreate("flexible")}
                    className={`rounded-lg border px-4 py-3 text-xs font-semibold sm:py-2 ${
                      scheduleForm.block_type === "flexible"
                        ? "border-cyan-300/40 bg-cyan-300/15 text-cyan-100"
                        : "border-white/10 bg-white/[0.03] text-neutral-400 hover:text-white"
                    }`}
                  >
                    Flexible
                  </button>
                </div>
              </label>

              <div className="grid gap-3 lg:grid-cols-[1.2fr_1fr_1fr]">
                <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                  <span>Title optional</span>
                  <input
                    type="text"
                    value={scheduleForm.title}
                    onChange={(event) =>
                      setScheduleField("title", event.target.value)
                    }
                    className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                  />
                </label>
                <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                  <span>Category</span>
                <select
                  value={scheduleForm.category}
                  onChange={(event) =>
                    setScheduleField(
                      "category",
                      event.target.value as ScheduleBlockCategory,
                    )
                  }
                  className="rounded-lg border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                >
                  {categoryOptions.map((category) => (
                    <option key={category} value={category}>
                      {formatStatus(category)}
                    </option>
                  ))}
                </select>
                </label>
                <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                  <span>Priority</span>
                <select
                  value={scheduleForm.priority}
                  onChange={(event) =>
                    setScheduleField(
                      "priority",
                      event.target.value as ScheduleBlockPriority,
                    )
                  }
                  className="rounded-lg border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                >
                  {priorityOptions.map((priority) => (
                    <option key={priority} value={priority}>
                      {formatStatus(priority)}
                    </option>
                  ))}
                </select>
                </label>
              </div>

              {scheduleForm.block_type === "fixed" ? (
                <div className="grid gap-3">
                  <div className="rounded-lg border border-white/10 bg-white/[0.02] p-3">
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <span className="text-xs font-semibold text-neutral-300">
                            {editingScheduleBlockId
                              ? "Apply to more days"
                              : "Dates this week"}
                          </span>
                          <p className="mt-1 text-[11px] text-neutral-500">
                            {formatWeekHeading(visibleWeekDays)}
                          </p>
                        </div>
                        <label className="flex items-center gap-2 text-xs text-neutral-400">
                          <input
                            type="checkbox"
                            checked={scheduleForm.same_time}
                            onChange={(event) =>
                              setScheduleSameTime(event.target.checked)
                            }
                            className="h-4 w-4 accent-cyan-300"
                          />
                          Same time
                        </label>
                      </div>
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() =>
                            setSchedulePickerWeek(addDays(visibleWeekStart, -7))
                          }
                          className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-xs font-semibold text-neutral-300 hover:border-white/20 hover:text-white"
                        >
                          Previous Week
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            setSchedulePickerWeek(getWeekStart(new Date()))
                          }
                          className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-xs font-semibold text-neutral-300 hover:border-white/20 hover:text-white"
                        >
                          This Week
                        </button>
                        <button
                          type="button"
                          onClick={() =>
                            setSchedulePickerWeek(addDays(visibleWeekStart, 7))
                          }
                          className="rounded-md border border-white/10 bg-white/[0.03] px-2 py-1 text-xs font-semibold text-neutral-300 hover:border-white/20 hover:text-white"
                        >
                          Next Week
                        </button>
                      </div>
                      <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                        {visibleWeekDays.map((weekDay) => {
                          const selected = scheduleForm.selected_dates.includes(
                            weekDay.dateKey,
                          );
                          const dateTime = scheduleForm.date_times[weekDay.dateKey] ?? {
                            start_time: scheduleForm.start_time,
                            end_time: scheduleForm.end_time,
                          };

                          return (
                            <div
                              key={weekDay.dateKey}
                              className={`rounded-lg border p-2 ${
                                selected
                                  ? "border-cyan-300/40 bg-cyan-300/10"
                                  : "border-white/10 bg-neutral-950/60"
                              }`}
                            >
                              <label className="flex items-center gap-2 text-xs font-semibold text-neutral-200">
                                <input
                                  type="checkbox"
                                  checked={selected}
                                  onChange={() =>
                                    toggleScheduleSelectedDate(weekDay.dateKey)
                                  }
                                  className="h-4 w-4 accent-cyan-300"
                                />
                                <span>
                                  {formatStatus(weekDay.day)} ·{" "}
                                  {formatWeekDateLabel(weekDay.date)}
                                </span>
                              </label>
                              {selected && !scheduleForm.same_time ? (
                                <div className="mt-2 grid grid-cols-2 gap-2">
                                  <input
                                    type="time"
                                    value={dateTime.start_time}
                                    onChange={(event) =>
                                      setScheduleDateTime(
                                        weekDay.dateKey,
                                        "start_time",
                                        event.target.value,
                                      )
                                    }
                                    className="min-w-0 rounded-md border border-white/10 bg-white/[0.03] px-2 py-1.5 text-xs text-white outline-none focus:border-cyan-300/50"
                                  />
                                  <input
                                    type="time"
                                    value={dateTime.end_time}
                                    onChange={(event) =>
                                      setScheduleDateTime(
                                        weekDay.dateKey,
                                        "end_time",
                                        event.target.value,
                                      )
                                    }
                                    className="min-w-0 rounded-md border border-white/10 bg-white/[0.03] px-2 py-1.5 text-xs text-white outline-none focus:border-cyan-300/50"
                                  />
                                </div>
                              ) : null}
                            </div>
                          );
                        })}
                      </div>
                  </div>

                  <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                    <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                      <span>Day</span>
                      <select
                        value={scheduleForm.day_of_week}
                        onChange={(event) =>
                          setScheduleField(
                            "day_of_week",
                            event.target.value as DayOfWeek | "",
                          )
                        }
                        disabled={
                          !editingScheduleBlockId &&
                          scheduleForm.selected_dates.length > 0
                        }
                        className="rounded-lg border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <option value="">Recurring day</option>
                        {dayOptions.map((day) => (
                          <option key={day} value={day}>
                            {formatStatus(day)}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                      <span>Specific Date</span>
                      <input
                        type="date"
                        value={scheduleForm.specific_date}
                        onChange={(event) =>
                          setScheduleField("specific_date", event.target.value)
                        }
                        disabled={
                          !editingScheduleBlockId &&
                          scheduleForm.selected_dates.length > 0
                        }
                        className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50 disabled:cursor-not-allowed disabled:opacity-50"
                      />
                    </label>
                    <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                      <span>Start Time</span>
                      <input
                        type="time"
                        value={scheduleForm.start_time}
                        onChange={(event) =>
                          setScheduleField("start_time", event.target.value)
                        }
                        disabled={!scheduleForm.same_time}
                        className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50 disabled:cursor-not-allowed disabled:opacity-50"
                      />
                    </label>
                    <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                      <span>End Time</span>
                      <input
                        type="time"
                        value={scheduleForm.end_time}
                        onChange={(event) =>
                          setScheduleField("end_time", event.target.value)
                        }
                        disabled={!scheduleForm.same_time}
                        className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50 disabled:cursor-not-allowed disabled:opacity-50"
                      />
                    </label>
                    <div className="flex items-end">
                      <button
                        type="button"
                        onClick={clearScheduleTimes}
                        className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-xs font-semibold text-neutral-300 hover:border-white/20 hover:text-white"
                      >
                        Clear Time
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
                  <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                    <span>Placement</span>
                    <select
                      value={scheduleForm.flexible_placement_mode}
                      onChange={(event) => {
                        const mode = event.target.value as FlexiblePlacementMode;
                        setScheduleForm((current) => ({
                          ...current,
                          flexible_placement_mode: mode,
                          day_of_week:
                            mode === "whenever_free" ? "" : current.day_of_week,
                          preferred_days:
                            mode === "whenever_free" ? [] : current.preferred_days,
                          specific_date:
                            mode === "whenever_free"
                              ? ""
                              : current.specific_date,
                        }));
                      }}
                      className="rounded-lg border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                    >
                      {(
                        Object.keys(
                          flexiblePlacementLabels,
                        ) as FlexiblePlacementMode[]
                      ).map((mode) => (
                        <option key={mode} value={mode}>
                          {flexiblePlacementLabels[mode]}
                        </option>
                      ))}
                    </select>
                  </label>
                  <div className="grid gap-1.5 text-xs font-semibold text-neutral-300 md:col-span-2">
                    <span>Preferred Days</span>
                    <div className="flex flex-wrap gap-1.5">
                      {dayOptions.map((day) => {
                        const selected = scheduleForm.preferred_days.includes(day);
                        return (
                          <button
                            key={day}
                            type="button"
                            onClick={() => togglePreferredScheduleDay(day)}
                            disabled={
                              scheduleForm.flexible_placement_mode === "whenever_free"
                            }
                            className={`rounded-md border px-2 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${
                              selected
                                ? "border-cyan-300/40 bg-cyan-300/15 text-cyan-100"
                                : "border-white/10 bg-white/[0.03] text-neutral-400 hover:text-white"
                            }`}
                          >
                            {compactDayLabels[day]}
                          </button>
                        );
                      })}
                    </div>
                  </div>
                  <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                    <span>Specific Date</span>
                    <input
                      type="date"
                      value={scheduleForm.specific_date}
                      onChange={(event) =>
                        setScheduleField("specific_date", event.target.value)
                      }
                      disabled={
                        scheduleForm.flexible_placement_mode === "whenever_free"
                      }
                      className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50 disabled:cursor-not-allowed disabled:opacity-50"
                    />
                  </label>
                  <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                    <span>Duration</span>
                    <input
                      type="number"
                      min="0.25"
                      max={
                        scheduleForm.duration_unit === "hours"
                          ? maxScheduleDurationMinutes / 60
                          : maxScheduleDurationMinutes
                      }
                      step={scheduleForm.duration_unit === "hours" ? "0.25" : "1"}
                      value={scheduleForm.duration_value}
                      onChange={(event) =>
                        setScheduleField("duration_value", event.target.value)
                      }
                      className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                    />
                  </label>
                  <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                    <span>Duration Unit</span>
                    <select
                      value={scheduleForm.duration_unit}
                      onChange={(event) =>
                        setScheduleField(
                          "duration_unit",
                          event.target.value as DurationUnit,
                        )
                      }
                      className="rounded-lg border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                    >
                      {durationUnitOptions.map((unit) => (
                        <option key={unit} value={unit}>
                          {unit === "minutes" ? "Minutes" : "Hours"}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                    <span>Time Preference</span>
                    <select
                      value={scheduleForm.time_preference}
                      onChange={(event) =>
                        setScheduleField(
                          "time_preference",
                          event.target.value as ScheduleTimePreference,
                        )
                      }
                      className="rounded-lg border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                    >
                      {timePreferenceOptions.map((preference) => (
                        <option key={preference} value={preference}>
                          {timePreferenceLabels[preference]}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>
              )}

              <div className="grid gap-3 lg:grid-cols-[1fr_1.5fr]">
              <div className="grid gap-3">
                <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                  <span>Recurrence</span>
                  <select
                    value={scheduleForm.recurrence}
                    onChange={(event) => {
                      const recurrence = event.target
                        .value as ScheduleFormState["recurrence"];
                      setScheduleForm((current) => ({
                        ...current,
                        recurrence,
                        recurrence_end_type:
                          recurrence === "once"
                            ? "never"
                            : current.recurrence_end_type,
                      }));
                    }}
                    className="w-full rounded-lg border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                  >
                    {recurrenceOptions.map((recurrence) => (
                      <option key={recurrence} value={recurrence}>
                        {recurrenceLabels[recurrence]}
                      </option>
                    ))}
                  </select>
                </label>
                {scheduleForm.recurrence !== "once" ? (
                  <div className="grid gap-2 rounded-lg border border-white/10 bg-white/[0.02] p-3">
                    <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                      <span>Ends</span>
                      <select
                        value={scheduleForm.recurrence_end_type}
                        onChange={(event) =>
                          setScheduleField(
                            "recurrence_end_type",
                            event.target
                              .value as ScheduleFormState["recurrence_end_type"],
                          )
                        }
                        className="w-full rounded-lg border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                      >
                        {recurrenceEndOptions.map((option) => (
                          <option key={option} value={option}>
                            {recurrenceEndLabels[option]}
                          </option>
                        ))}
                      </select>
                    </label>
                    {scheduleForm.recurrence_end_type === "date" ? (
                      <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                        <span>End Date</span>
                        <input
                          type="date"
                          value={scheduleForm.recurrence_end_date}
                          onChange={(event) =>
                            setScheduleField(
                              "recurrence_end_date",
                              event.target.value,
                            )
                          }
                          className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                        />
                      </label>
                    ) : null}
                    {scheduleForm.recurrence_end_type === "occurrences" ? (
                      <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                        <span>Occurrences</span>
                        <input
                          type="number"
                          min="1"
                          value={scheduleForm.recurrence_count}
                          onChange={(event) =>
                            setScheduleField("recurrence_count", event.target.value)
                          }
                          className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                        />
                      </label>
                    ) : null}
                    {scheduleForm.recurrence_end_type === "weeks" ? (
                      <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                        <span>Weeks</span>
                        <input
                          type="number"
                          min="1"
                          value={scheduleForm.recurrence_weeks}
                          onChange={(event) =>
                            setScheduleField("recurrence_weeks", event.target.value)
                          }
                          className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
                        />
                      </label>
                    ) : null}
                  </div>
                ) : null}
              </div>
              <label className="grid gap-1.5 text-xs font-semibold text-neutral-300">
                <span>Notes</span>
              <textarea
                value={scheduleForm.notes}
                onChange={(event) =>
                  setScheduleField("notes", event.target.value)
                }
                rows={3}
                className="min-h-20 w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none focus:border-cyan-300/50"
              />
              </label>
              </div>
              <label className="flex items-center gap-2 text-xs text-neutral-400">
                <input
                  type="checkbox"
                  checked={scheduleForm.active}
                  onChange={(event) =>
                    setScheduleField("active", event.target.checked)
                  }
                  className="h-4 w-4 accent-cyan-300"
                />
                Active
              </label>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={saveScheduleBlock}
                  disabled={savingScheduleBlock}
                  className="rounded-lg border border-emerald-300/25 bg-emerald-300/10 px-4 py-3 text-xs font-semibold text-emerald-100 hover:bg-emerald-300/20 disabled:cursor-not-allowed disabled:opacity-60 sm:py-2"
                >
                  {savingScheduleBlock
                    ? "Saving..."
                    : editingScheduleBlockId
                      ? "Save Changes"
                      : "Add Block"}
                </button>
                {editingScheduleBlockId ? (
                  <button
                    type="button"
                    onClick={() => {
                      setEditingScheduleBlockId(null);
                      setScheduleForm(emptyScheduleForm);
                      setActiveScheduleSection("calendar");
                    }}
                    className="rounded-lg border border-white/10 bg-white/[0.03] px-4 py-3 text-xs font-semibold text-neutral-300 hover:border-white/20 hover:text-white sm:py-2"
                  >
                    Cancel
                  </button>
                ) : null}
              </div>
            </div>
          </section>
          ) : null}

          {activeScheduleSection === "intelligence" ? (
          <section className="rounded-xl border border-cyan-300/15 bg-cyan-300/[0.04] p-3 sm:p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-neutral-100">
                  Schedule Intelligence
                </h2>
                <p className="mt-1 text-xs text-neutral-500">
                  Schedule density, open windows, and manual placement actions
                </p>
              </div>
              <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide text-neutral-400">
                Manual placement
              </span>
            </div>

            {scheduleIntelligenceError ? (
              <p className="text-sm text-red-100">
                Schedule intelligence is unavailable right now.
              </p>
            ) : scheduleIntelligence ? (
              <div className="grid gap-3">
              <div className="grid gap-2 lg:grid-cols-4">
                <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-wide text-neutral-500">
                    Most Available
                  </p>
                  <p className="mt-1 text-sm font-semibold text-neutral-100">
                    {formatScheduleDaySummary(
                      scheduleIntelligence.most_available_day,
                    )}
                  </p>
                </div>
                <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-wide text-neutral-500">
                    Most Overloaded
                  </p>
                  <p className="mt-1 text-sm font-semibold text-neutral-100">
                    {formatScheduleDaySummary(
                      scheduleIntelligence.most_overloaded_day,
                    )}
                  </p>
                </div>
                <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-wide text-neutral-500">
                    Recommended Placement
                  </p>
                  <p className="mt-1 line-clamp-2 text-sm font-semibold text-neutral-100">
                    {scheduleIntelligence.recommended_placement ??
                      "No placement recommendation yet"}
                  </p>
                </div>
                <div className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                  <p className="text-[11px] uppercase tracking-wide text-neutral-500">
                    Unplaced Flexible
                  </p>
                  <p className="mt-1 text-sm font-semibold text-neutral-100">
                    {scheduleIntelligence.unplaced_flexible_blocks}
                  </p>
                </div>
              </div>
              <div className="grid gap-3 lg:grid-cols-2">
                <div className="rounded-lg border border-white/10 bg-black/20 p-3 lg:col-span-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Place Flexible Blocks
                  </h3>
                  {scheduleIntelligence.placement_candidates.length > 0 ? (
                    <div className="mt-2 grid gap-2 md:grid-cols-2">
                      {scheduleIntelligence.placement_candidates.map((candidate) => (
                        <div
                          key={`${candidate.flexible_block_id}-${candidate.date}-${candidate.start_time}`}
                          className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2"
                        >
                          <div className="flex flex-wrap items-start justify-between gap-2">
                            <div className="min-w-0">
                              <p className="text-sm font-semibold text-neutral-100">
                                {candidate.title}
                              </p>
                              <p className="mt-1 text-xs leading-5 text-neutral-500">
                                {formatStatus(candidate.day)} ·{" "}
                                {formatTime(candidate.start_time)}-
                                {formatTime(candidate.end_time)} ·{" "}
                                {candidate.reason}
                              </p>
                            </div>
                            <button
                              type="button"
                              onClick={() =>
                                placeFlexibleScheduleBlock(
                                  candidate.flexible_block_id,
                                  candidate,
                                )
                              }
                              disabled={
                                placingScheduleBlockId ===
                                candidate.flexible_block_id
                              }
                              className="rounded-md border border-emerald-300/25 bg-emerald-300/10 px-2 py-1 text-xs font-semibold text-emerald-100 hover:bg-emerald-300/20 disabled:cursor-not-allowed disabled:opacity-60"
                            >
                              {placingScheduleBlockId ===
                              candidate.flexible_block_id
                                ? "Placing..."
                                : "Place Block"}
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-neutral-500">
                      No flexible block placements are available for this week.
                    </p>
                  )}
                </div>
                <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Best Windows
                  </h3>
                  {scheduleIntelligence.available_windows.length > 0 ? (
                    <div className="mt-2 grid gap-2">
                      {scheduleIntelligence.available_windows.slice(0, 5).map((window) => (
                        <p
                          key={`${window.date}-${window.start_time}-${window.end_time}`}
                          className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-neutral-300"
                        >
                          {formatStatus(window.day)} · {formatTime(window.start_time)}
                          -{formatTime(window.end_time)} ·{" "}
                          {formatDuration(window.duration_minutes)}
                        </p>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-2 text-sm text-neutral-500">
                      No open windows surfaced for this week.
                    </p>
                  )}
                </div>
                <div className="rounded-lg border border-white/10 bg-black/20 p-3">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                    Recommendations
                  </h3>
                  {scheduleIntelligence.recommendations.length > 0 ? (
                    <ul className="mt-2 grid gap-2 text-sm leading-6 text-neutral-300">
                      {scheduleIntelligence.recommendations.map((recommendation) => (
                        <li
                          key={recommendation}
                          className="rounded-md border border-white/10 bg-white/[0.03] px-3 py-2"
                        >
                          {recommendation}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p className="mt-2 text-sm text-neutral-500">
                      No recommendations for this week yet.
                    </p>
                  )}
                </div>
              </div>
              </div>
            ) : (
              <p className="text-sm text-neutral-500">
                Schedule intelligence has not loaded yet.
              </p>
            )}
          </section>
          ) : null}

          {activeScheduleSection === "calendar" ? (
          <section className="rounded-xl border border-white/10 bg-neutral-950/70 p-3 sm:p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
                <div className="grid w-full grid-cols-3 rounded-lg border border-white/10 bg-white/[0.03] p-1 sm:flex sm:w-auto">
                  <button
                    type="button"
                    onClick={() =>
                      setVisibleWeekStart((current) => addDays(current, -7))
                    }
                    className="rounded-md px-3 py-2 text-xs font-semibold text-neutral-300 hover:bg-white/[0.06] hover:text-white sm:px-2 sm:py-1"
                  >
                    Previous
                  </button>
                  <button
                    type="button"
                    onClick={() => setVisibleWeekStart(getWeekStart(new Date()))}
                    className="rounded-md px-3 py-2 text-xs font-semibold text-neutral-300 hover:bg-white/[0.06] hover:text-white sm:px-2 sm:py-1"
                  >
                    Today
                  </button>
                  <button
                    type="button"
                    onClick={() =>
                      setVisibleWeekStart((current) => addDays(current, 7))
                    }
                    className="rounded-md px-3 py-2 text-xs font-semibold text-neutral-300 hover:bg-white/[0.06] hover:text-white sm:px-2 sm:py-1"
                  >
                    Next
                  </button>
                </div>
                <div className="w-full rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-center text-xs font-semibold text-neutral-300 sm:w-auto sm:py-1.5">
                  Monday-Sunday
                </div>
              </div>
            </div>

            {scheduleBlocksError ? (
              <p className="text-sm text-red-100">
                Schedule blocks are unavailable right now.
              </p>
            ) : (
              <div className="space-y-3">
                <div className="space-y-3 sm:hidden">
                  {visibleWeekDays.map((weekDay) => {
                    const groups =
                      scheduleBlocksByDate.get(weekDay.dateKey) ?? [];
                    const today = isSameDate(weekDay.date, new Date());

                    return (
                      <section
                        key={weekDay.dateKey}
                        className={`rounded-lg border ${
                          today
                            ? "border-cyan-300/35 bg-cyan-300/[0.05]"
                            : "border-white/10 bg-black/20"
                        }`}
                      >
                        <div
                          className={`flex items-center justify-between gap-3 border-b px-3 py-2.5 ${
                            today ? "border-cyan-300/20" : "border-white/10"
                          }`}
                        >
                          <div className="min-w-0">
                            <h3 className="text-sm font-semibold text-neutral-100">
                              {formatStatus(weekDay.day)}{" "}
                              <span className="text-neutral-500">
                                {formatWeekDateLabel(weekDay.date)}
                              </span>
                            </h3>
                          </div>
                          <span className="shrink-0 rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] text-neutral-500">
                            {groups.length}
                          </span>
                        </div>
                        <div className="space-y-2 p-2.5">
                          {groups.length > 0 ? (
                            groups.map((group) => (
                              <CalendarScheduleBlockGroupCard
                                key={group.key}
                                group={group}
                                mutatingScheduleBlockId={
                                  mutatingScheduleBlockId
                                }
                                onEdit={startScheduleBlockEdit}
                                onArchive={archiveScheduleBlock}
                                onDelete={deleteScheduleBlock}
                              />
                            ))
                          ) : (
                            <p className="rounded-lg border border-dashed border-white/10 px-3 py-3 text-xs leading-5 text-neutral-600">
                              No blocks scheduled.
                            </p>
                          )}
                        </div>
                      </section>
                    );
                  })}
                </div>
                <div className="hidden max-w-full overflow-x-auto pb-2 sm:block">
                  <div className="grid min-w-[78rem] grid-cols-[repeat(7,minmax(10.75rem,1fr))] gap-2 xl:min-w-[86rem]">
                    {visibleWeekDays.map((weekDay) => {
                      const groups =
                        scheduleBlocksByDate.get(weekDay.dateKey) ?? [];
                      const today = isSameDate(weekDay.date, new Date());

                      return (
                        <div
                          key={weekDay.dateKey}
                          className={`min-h-[22rem] min-w-0 rounded-lg border lg:min-h-[26rem] ${
                            today
                              ? "border-cyan-300/35 bg-cyan-300/[0.05]"
                              : "border-white/10 bg-black/20"
                          }`}
                        >
                          <div
                            className={`flex items-center justify-between gap-2 border-b px-3 py-2 ${
                              today ? "border-cyan-300/20" : "border-white/10"
                            }`}
                          >
                            <div>
                              <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-300">
                                {formatStatus(weekDay.day)}
                              </h3>
                              <p className="mt-0.5 text-xs text-neutral-500">
                                {formatWeekDateLabel(weekDay.date)}
                              </p>
                            </div>
                            <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] text-neutral-500">
                              {groups.length}
                            </span>
                          </div>
                          <div className="space-y-2 p-2">
                            {groups.length > 0 ? (
                              groups.map((group) => (
                                <CalendarScheduleBlockGroupCard
                                  key={group.key}
                                  group={group}
                                  mutatingScheduleBlockId={
                                    mutatingScheduleBlockId
                                  }
                                  onEdit={startScheduleBlockEdit}
                                  onArchive={archiveScheduleBlock}
                                  onDelete={deleteScheduleBlock}
                                />
                              ))
                            ) : (
                              <p className="rounded-lg border border-dashed border-white/10 px-3 py-4 text-xs leading-5 text-neutral-600">
                                No blocks scheduled.
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            )}
          </section>
          ) : null}

          {activeScheduleSection === "blocks" ? (
          <section className="rounded-xl border border-white/10 bg-neutral-950/70 p-3 sm:p-4">
            <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-neutral-100">
                  Schedule Blocks
                </h2>
                <p className="mt-1 text-xs text-neutral-500">
                  Manage fixed, flexible, and inactive blocks.
                </p>
              </div>
              <button
                type="button"
                onClick={() => startScheduleBlockCreate("fixed")}
                className="rounded-lg border border-cyan-300/30 bg-cyan-300/10 px-3 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-300/20"
              >
                Add Block
              </button>
            </div>

            {scheduleBlocksError ? (
              <p className="text-sm text-red-100">
                Schedule blocks are unavailable right now.
              </p>
            ) : (
              <div className="grid gap-4 lg:grid-cols-3">
                {[
                  ["Fixed Blocks", scheduleBlockGroups.fixed],
                  ["Flexible Blocks", scheduleBlockGroups.flexible],
                  ["Archived / Inactive", scheduleBlockGroups.archived],
                ].map(([title, groups]) => {
                  const typedGroups = groups as ScheduleBlockDisplayGroup[];
                  const totalBlocks = typedGroups.reduce(
                    (sum, group) =>
                      sum + groupScheduleBlocksByPattern(group.blocks).length,
                    0,
                  );
                  const isFlexibleColumn = title === "Flexible Blocks";

                  return (
                    <section
                      key={title as string}
                      className="rounded-lg border border-white/10 bg-black/20 p-3"
                    >
                      <div className="mb-3 flex items-center justify-between gap-2">
                        <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                          {title as string}
                        </h3>
                        <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] text-neutral-500">
                          {totalBlocks}
                        </span>
                      </div>
                      {typedGroups.length > 0 ? (
                        <div className="grid gap-2">
                          {typedGroups.map((group) => {
                            return (
                              <ScheduleBlockDisplayGroupCard
                                key={group.key}
                                group={group}
                                isFlexibleColumn={isFlexibleColumn}
                                defaultOpen={typedGroups.length <= 4}
                                mutatingScheduleBlockId={mutatingScheduleBlockId}
                                placingScheduleBlockId={placingScheduleBlockId}
                                placementCandidatesByBlockId={
                                  placementCandidatesByBlockId
                                }
                                onFindSlot={() =>
                                  setActiveScheduleSection("intelligence")
                                }
                                onPlace={placeFlexibleScheduleBlock}
                                onEdit={startScheduleBlockEdit}
                                onArchive={archiveScheduleBlock}
                                onDelete={deleteScheduleBlock}
                              />
                            );
                          })}
                        </div>
                      ) : (
                        <p className="rounded-lg border border-dashed border-white/10 px-3 py-4 text-xs leading-5 text-neutral-600">
                          No blocks in this group.
                        </p>
                      )}
                    </section>
                  );
                })}
              </div>
            )}
          </section>
          ) : null}
        </div>
      ) : null}

      {activeTab === "Milestones" ? (
        <div className="space-y-2">
          {activeMilestones.length > 0 ? (
            activeMilestones.map((milestone) => {
              const linkedTasks = milestoneTasksById[milestone.id] ?? [];
              const openLinkedTasks = linkedTasks.filter(isTaskOpen);
              const advisory = milestoneAdvisoriesById[milestone.id];
              const suggestedPercent =
                advisory?.suggested_task_completion_percent ?? null;
              const showSuggestedPercent =
                suggestedPercent !== null &&
                suggestedPercent !== milestone.progress_percent;
              const expanded = expandedMilestoneIds.includes(milestone.id);
              const latestProgressChange =
                latestProgressHistoryByMilestoneId[milestone.id];

              return (
                <article
                  key={milestone.id}
                  className="rounded-xl border border-white/10 bg-neutral-950/70 p-4"
                >
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h2 className="truncate text-sm font-semibold text-neutral-100">
                        {milestone.title}
                      </h2>
                      <p className="mt-1 text-xs text-neutral-500">
                        Unique tasks: {advisory?.completed_linked_tasks ?? 0}{" "}
                        complete /{" "}
                        {advisory?.total_linked_tasks ?? linkedTasks.length} total
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-2">
                      <span className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-2 py-1 text-xs text-cyan-100">
                        {formatStatus(milestone.status)}
                      </span>
                      {linkedTasks.length > 0 ? (
                        <button
                          type="button"
                          onClick={() =>
                            setExpandedMilestoneIds((current) =>
                              expanded
                                ? current.filter((id) => id !== milestone.id)
                                : [...current, milestone.id],
                            )
                          }
                          className="text-xs font-semibold text-neutral-400 underline underline-offset-4 hover:text-white"
                        >
                          {expanded ? "Hide" : "Tasks"}
                        </button>
                      ) : null}
                    </div>
                  </div>
                  <div className="mb-2 flex justify-between text-xs text-neutral-500">
                    <span>
                      {milestone.due_date ? `Due ${formatDate(milestone.due_date)}` : "Progress"}
                    </span>
                    <span>{milestone.progress_percent}%</span>
                  </div>
                  <ProgressBar value={milestone.progress_percent} />
                  {latestProgressChange ? (
                    <p className="mt-2 text-xs text-neutral-500">
                      Latest change: {latestProgressChange.previous_progress}%{" "}
                      {"->"}{" "}
                      {latestProgressChange.new_progress}% via{" "}
                      {formatStatus(latestProgressChange.source)}
                      {latestProgressChange.reason
                        ? ` - ${latestProgressChange.reason}`
                        : ""}
                    </p>
                  ) : null}
                  <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-neutral-500">
                    <span>{openLinkedTasks.length} open</span>
                    <span>Current saved progress: {milestone.progress_percent}%</span>
                    <span>
                      Task completion suggestion:{" "}
                      {suggestedPercent === null ? "--" : `${suggestedPercent}%`}
                    </span>
                    {showSuggestedPercent ? (
                      <span className="text-cyan-200">
                        Suggested progress update available: {suggestedPercent}%
                      </span>
                    ) : suggestedPercent !== null ? (
                      <span>Task suggestion matches current progress</span>
                    ) : null}
                    {suggestedPercent === null && advisory?.reason ? (
                      <span>{advisory.reason}</span>
                    ) : null}
                    {showSuggestedPercent ? (
                      <button
                        type="button"
                        onClick={() =>
                          applySuggestedProgress(milestone.id, suggestedPercent)
                        }
                        disabled={applyingMilestoneId === milestone.id}
                        className="rounded-lg border border-cyan-300/25 bg-cyan-300/10 px-2 py-1 text-xs font-semibold text-cyan-100 hover:bg-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        {applyingMilestoneId === milestone.id
                          ? "Applying..."
                          : "Apply suggested progress"}
                      </button>
                    ) : null}
                  </div>
                  {expanded ? (
                    <div className="mt-3 space-y-1.5">
                      {linkedTasks.map((task) => (
                        <div
                          key={task.id}
                          className="flex items-center justify-between gap-3 rounded-lg bg-white/[0.03] px-3 py-2"
                        >
                          <span className="min-w-0 truncate text-sm text-neutral-300">
                            {task.title}
                          </span>
                          <span className="shrink-0 text-xs text-neutral-500">
                            {formatStatus(task.status)}
                          </span>
                        </div>
                      ))}
                    </div>
                  ) : null}
                </article>
              );
            })
          ) : (
            <div className="rounded-xl border border-white/10 bg-neutral-950/70 p-4 text-sm text-neutral-500">
              {event
                ? `No milestones are linked to ${event.title} yet.`
                : "Milestones will appear once a major event is available."}
            </div>
          )}
        </div>
      ) : null}

      {activeTab === "Reviews" ? (
        <div className="space-y-2">
          <article className="rounded-xl border border-white/10 bg-neutral-950/70 p-4">
            <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-semibold text-neutral-100">
                  Daily Closeout
                </h2>
                <p className="mt-1 text-xs text-neutral-500">
                  {dailyCloseout?.generated_at
                    ? `Generated ${formatDateTime(dailyCloseout.generated_at)}`
                    : dailyCloseoutError
                      ? "Closeout unavailable right now."
                      : "Ready when you are."}
                </p>
              </div>
              <button
                type="button"
                onClick={generateDailyCloseout}
                disabled={loadingCloseout}
                className="rounded-lg border border-cyan-300/25 bg-cyan-300/10 px-3 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loadingCloseout ? "Generating..." : dailyCloseout ? "Refresh" : "Generate"}
              </button>
            </div>

            {dailyCloseout ? (
              <div className="space-y-3">
                <div className="grid gap-2 sm:grid-cols-4">
                  <div className="rounded-lg bg-white/[0.03] px-3 py-2">
                    <p className="text-lg font-semibold text-white">
                      {dailyCloseout.completed_today.length}
                    </p>
                    <p className="text-xs text-neutral-500">
                      {dailyCloseout.completed_today.length === 0
                        ? "No tasks completed today"
                        : "completed today"}
                    </p>
                  </div>
                  <div className="rounded-lg bg-white/[0.03] px-3 py-2">
                    <p className="text-lg font-semibold text-white">
                      {dailyCloseout.open_tasks.length}
                    </p>
                    <p className="text-xs text-neutral-500">
                      {dailyCloseout.open_tasks.length === 0
                        ? "No open tasks remaining"
                        : "open tasks"}
                    </p>
                  </div>
                  <div className="rounded-lg bg-white/[0.03] px-3 py-2">
                    <p className="text-lg font-semibold text-white">
                      {dailyCloseout.milestone_progress.length}
                    </p>
                    <p className="text-xs text-neutral-500">
                      {dailyCloseout.milestone_progress.length === 0
                        ? "No milestone changes"
                        : "milestone changes"}
                    </p>
                  </div>
                  <div className="rounded-lg bg-white/[0.03] px-3 py-2">
                    <p className="text-lg font-semibold text-white">
                      {dailyCloseout.trade_summary.trading_sessions_reviewed ??
                        dailyCloseout.trade_summary.sessions_logged_today}
                    </p>
                    <p className="text-xs text-neutral-500">
                      {(dailyCloseout.trade_summary.trading_sessions_reviewed ??
                        dailyCloseout.trade_summary.sessions_logged_today) === 0
                        ? "No trade days logged today"
                        : "trade days today"}
                    </p>
                  </div>
                  <div className="rounded-lg bg-white/[0.03] px-3 py-2">
                    <p className="text-lg font-semibold text-white">
                      {dailyCloseout.trade_summary.trade_count ?? 0}
                    </p>
                    <p className="text-xs text-neutral-500">journal trades</p>
                  </div>
                  <div className="rounded-lg bg-white/[0.03] px-3 py-2">
                    <p className="text-lg font-semibold text-white">
                      {dailyCloseout.trade_summary.total_pnl.toLocaleString(
                        "en-US",
                        {
                          style: "currency",
                          currency: "USD",
                          maximumFractionDigits: 2,
                        },
                      )}
                    </p>
                    <p className="text-xs text-neutral-500">journal PnL</p>
                  </div>
                </div>

                <div className="grid gap-2 lg:grid-cols-2">
                  <section className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                      Completed Today
                    </h3>
                    {dailyCloseout.completed_today.length > 0 ? (
                      <ul className="mt-2 space-y-1">
                        {dailyCloseout.completed_today
                          .slice(0, CLOSEOUT_LIST_LIMIT)
                          .map((task) => (
                            <li
                              key={task.id}
                              className="truncate text-sm text-neutral-300"
                            >
                              {formatTaskSummary(task)}
                            </li>
                          ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm text-neutral-500">
                        No tasks completed today.
                      </p>
                    )}
                  </section>

                  <section className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                      Still Open
                    </h3>
                    {dailyCloseout.open_tasks.length > 0 ? (
                      <ul className="mt-2 space-y-1">
                        {dailyCloseout.open_tasks
                          .slice(0, CLOSEOUT_LIST_LIMIT)
                          .map((task) => (
                            <li
                              key={task.id}
                              className="truncate text-sm text-neutral-300"
                            >
                              {formatTaskSummary(task)}
                            </li>
                          ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm text-neutral-500">
                        No open tasks remaining.
                      </p>
                    )}
                  </section>

                  <section className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                      Milestone Progress
                    </h3>
                    {dailyCloseout.milestone_progress.length > 0 ? (
                      <ul className="mt-2 space-y-1">
                        {dailyCloseout.milestone_progress
                          .slice(0, CLOSEOUT_LIST_LIMIT)
                          .map((progress) => (
                            <li
                              key={progress.id}
                              className="truncate text-sm text-neutral-300"
                              title={progress.reason ?? undefined}
                            >
                              {formatProgressSummary(progress)}
                            </li>
                          ))}
                      </ul>
                    ) : (
                      <p className="mt-2 text-sm text-neutral-500">
                        No milestone progress changes.
                      </p>
                    )}
                  </section>

                  <section className="rounded-lg border border-white/10 bg-black/20 px-3 py-2">
                    <h3 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
                      Trade Summary
                    </h3>
                    <p className="mt-2 text-sm text-neutral-300">
                      {dailyCloseout.trade_summary.sessions_logged_today} session
                      {dailyCloseout.trade_summary.sessions_logged_today === 1
                        ? ""
                        : "s"}{" "}
                      today, PnL {dailyCloseout.trade_summary.total_pnl}.
                    </p>
                    <p className="mt-1 text-xs text-neutral-500">
                      Rule adherence:{" "}
                      {dailyCloseout.trade_summary.average_rule_adherence === null
                        ? "not logged"
                        : `${dailyCloseout.trade_summary.average_rule_adherence}%`}
                    </p>
                  </section>
                </div>

                <div className="rounded-lg border border-cyan-300/15 bg-cyan-300/5 px-3 py-2">
                  <h3 className="text-xs font-semibold uppercase tracking-wide text-cyan-200/80">
                    Review Prompt
                  </h3>
                  <p className="mt-1 text-sm leading-6 text-neutral-200">
                    {dailyCloseout.recommended_review_prompt}
                  </p>
                </div>

                <div>
                  <button
                    type="button"
                    onClick={() => setShowFullCloseout((current) => !current)}
                    className="text-xs font-semibold text-neutral-400 underline underline-offset-4 hover:text-white"
                  >
                    {showFullCloseout ? "Hide full closeout" : "View full closeout"}
                  </button>
                  {showFullCloseout ? (
                    <pre className="mt-2 max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-white/10 bg-black/20 p-3 text-sm leading-6 text-neutral-300">
                      {dailyCloseout.closeout_text}
                    </pre>
                  ) : null}
                </div>

                <div className="grid gap-2 sm:grid-cols-[8rem_1fr_auto]">
                  <input
                    type="number"
                    min="1"
                    max="10"
                    value={closeoutRating}
                    onChange={(event) => setCloseoutRating(event.target.value)}
                    placeholder="Rating"
                    className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none placeholder:text-neutral-600 focus:border-cyan-300/50"
                  />
                  <textarea
                    value={closeoutNotes}
                    onChange={(event) => setCloseoutNotes(event.target.value)}
                    placeholder="Notes"
                    rows={2}
                    className="min-h-10 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2 text-sm text-white outline-none placeholder:text-neutral-600 focus:border-cyan-300/50"
                  />
                  <button
                    type="button"
                    onClick={saveDailyCloseoutReview}
                    disabled={savingCloseoutReview}
                    className="rounded-lg border border-emerald-300/25 bg-emerald-300/10 px-3 py-2 text-xs font-semibold text-emerald-100 hover:bg-emerald-300/20 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {savingCloseoutReview ? "Saving..." : "Save Daily Review"}
                  </button>
                </div>
              </div>
            ) : (
              <p className="text-sm text-neutral-500">
                No daily closeout generated yet.
              </p>
            )}
          </article>

          <section className="rounded-xl border border-white/10 bg-neutral-950/70 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-neutral-100">
                  Review History
                </h2>
                <p className="mt-1 text-xs text-neutral-500">
                  {reviewsError
                    ? "Reviews are unavailable right now."
                    : `${reviews.length} saved review${reviews.length === 1 ? "" : "s"}`}
                  {mostRecentReview ? (
                    <>
                      {" | Latest: "}
                      {getReviewTitle(mostRecentReview)}
                      {mostRecentReview.created_at
                        ? `, ${formatDateTime(mostRecentReview.created_at)}`
                        : ""}
                    </>
                  ) : null}
                </p>
              </div>
              {reviews.length > 0 ? (
                <button
                  type="button"
                  onClick={() => setShowReviewHistory((current) => !current)}
                  className="text-xs font-semibold text-neutral-400 underline underline-offset-4 hover:text-white"
                >
                  {showReviewHistory
                    ? "Hide review history"
                    : "Show review history"}
                </button>
              ) : null}
            </div>

            {showReviewHistory && reviews.length > 0 ? (
              <div className="mt-3 space-y-2">
                {reviews.map((review) => (
                  <article
                    key={review.id}
                    className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h3 className="truncate text-sm font-semibold text-neutral-100">
                          {getReviewTitle(review)}
                        </h3>
                        {review.summary ? (
                          <p className="mt-1 text-sm leading-6 text-neutral-400">
                            {getExcerpt(review.summary)}
                          </p>
                        ) : null}
                      </div>
                      <span className="shrink-0 text-xs text-neutral-500">
                        {review.created_at
                          ? formatDateTime(review.created_at)
                          : formatStatus(review.review_type)}
                      </span>
                    </div>
                  </article>
                ))}
              </div>
            ) : null}
          </section>
        </div>
      ) : null}

      {activeTab === "Readiness" ? (
        <div className="space-y-2">
          {readinessError ? (
            <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-sm text-red-100">
              Readiness is unavailable right now.
            </div>
          ) : eventReadiness.length > 0 ? (
            eventReadiness.map((category) => (
              <article
                key={category.id}
                className="rounded-xl border border-white/10 bg-neutral-950/70 p-4"
              >
                <div className="mb-3 flex items-center justify-between gap-3">
                  <h2 className="text-sm font-semibold text-neutral-100">
                    {category.category_name}
                  </h2>
                  <span className="text-xs text-neutral-500">
                    {category.current_score}% / {category.target_score}%
                  </span>
                </div>
                <ProgressBar value={category.current_score} />
                {category.notes ? (
                  <p className="mt-2 text-sm text-neutral-400">
                    {category.notes}
                  </p>
                ) : null}
              </article>
            ))
          ) : (
            <div className="rounded-xl border border-white/10 bg-neutral-950/70 p-4 text-sm text-neutral-500">
              No readiness categories have been added for this major event yet.
            </div>
          )}
        </div>
      ) : null}

      {activeTab === "Trade Journal" ? (
        <div className="rounded-xl border border-cyan-300/20 bg-cyan-300/5 p-5">
          <p className="text-xs font-semibold uppercase tracking-wide text-cyan-200">
            Data Capture
          </p>
          <h2 className="mt-2 text-lg font-semibold text-white">
            Trade Journal v1
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-neutral-300">
            Capture trade information, context, narrative, review notes, and
            attachment paths for future trading intelligence.
          </p>
          <button
            type="button"
            onClick={() => router.push("/trade-journal")}
            className="mt-4 rounded-lg bg-cyan-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
          >
            Open Trade Journal
          </button>
        </div>
      ) : null}

      {activeTab === "Agents" ? (
        <div className="space-y-2">
          {agentsError ? (
            <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-sm text-red-100">
              Agents are unavailable right now.
            </div>
          ) : agents.length > 0 ? (
            <>
              <article className="rounded-xl border border-white/10 bg-neutral-950/70 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                      Morning Check-In
                    </p>
                    <h2 className="mt-1 text-sm font-semibold text-neutral-100">
                      {morningCheckInStatus?.morning_acknowledged
                        ? "Acknowledged"
                        : morningCheckInStatus?.morning_fallback_sent
                          ? "Fallback Sent"
                          : morningCheckInStatusError
                            ? "Unavailable"
                            : "Waiting"}
                    </h2>
                    <p className="mt-1 text-xs text-neutral-500">
                      Cutoff:{" "}
                      {morningCheckInStatus?.cutoff_time ?? "06:30"} local
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={runMorningCheckIn}
                    disabled={checkingInMorning}
                    className="rounded-lg border border-cyan-300/25 bg-cyan-300/10 px-3 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {checkingInMorning ? "Starting..." : "Good Morning Helix"}
                  </button>
                </div>
                {morningCheckInStatus ? (
                  <div className="mt-3 grid gap-2 md:grid-cols-3">
                    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                        Acknowledged
                      </p>
                      <p className="mt-1 text-sm text-neutral-200">
                        {morningCheckInStatus.morning_acknowledged
                          ? "Yes"
                          : "No"}
                      </p>
                      <p className="mt-1 text-xs text-neutral-600">
                        {morningCheckInStatus.morning_acknowledged_at
                          ? formatDateTime(
                              morningCheckInStatus.morning_acknowledged_at,
                            )
                          : "No check-in yet"}
                      </p>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                        Fallback
                      </p>
                      <p className="mt-1 text-sm text-neutral-200">
                        {morningCheckInStatus.morning_fallback_sent
                          ? "Sent"
                          : "Not sent"}
                      </p>
                      <p className="mt-1 text-xs text-neutral-600">
                        {morningCheckInStatus.morning_fallback_sent_at
                          ? formatDateTime(
                              morningCheckInStatus.morning_fallback_sent_at,
                            )
                          : morningCheckInStatus.cutoff_due
                            ? "Cutoff passed"
                            : "Before cutoff"}
                      </p>
                    </div>
                    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                        Channel
                      </p>
                      <p className="mt-1 text-sm text-neutral-200">
                        {morningCheckInStatus.delivery_channel
                          ? formatStatus(morningCheckInStatus.delivery_channel)
                          : "None"}
                      </p>
                      <p className="mt-1 text-xs text-neutral-600">
                        {morningCheckInStatus.morning_agent_run_id
                          ? `Run ${morningCheckInStatus.morning_agent_run_id}`
                          : "No run linked"}
                      </p>
                    </div>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-neutral-500">
                    {morningCheckInStatusError ??
                      "Morning check-in status has not loaded yet."}
                  </p>
                )}
                {morningCheckInSummary ? (
                  <p className="mt-3 line-clamp-6 whitespace-pre-wrap text-sm leading-6 text-neutral-300">
                    {morningCheckInSummary}
                  </p>
                ) : null}
              </article>
              <article className="rounded-xl border border-white/10 bg-neutral-950/70 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                      Scheduled Agents
                    </p>
                    <h2 className="mt-1 text-sm font-semibold text-neutral-100">
                      {scheduledAgentsStatus?.scheduler_enabled
                        ? formatStatus(scheduledAgentsStatus.scheduler_status)
                        : scheduledAgentsStatusError
                          ? "Unavailable"
                          : "Loading"}
                    </h2>
                    <p className="mt-1 text-xs text-neutral-500">
                      Current local time:{" "}
                      {scheduledAgentsStatus
                        ? formatDateTime(
                            scheduledAgentsStatus.current_local_time,
                          )
                        : "Unknown"}
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={checkScheduledAgentsNow}
                    disabled={checkingScheduledAgents}
                    className="rounded-lg border border-cyan-300/25 bg-cyan-300/10 px-3 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    {checkingScheduledAgents
                      ? "Checking..."
                      : "Check Scheduled Agents Now"}
                  </button>
                </div>
                {scheduledAgentsStatus ? (
                  <div className="mt-3 grid gap-2 md:grid-cols-3">
                    {[
                      ["Morning Review", scheduledAgentsStatus.morning],
                      ["Evening Review", scheduledAgentsStatus.evening],
                    ].map(([label, schedule]) => {
                      const typedSchedule =
                        schedule as ScheduledAgentWindowStatus;
                      return (
                        <div
                          key={String(label)}
                          className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <p className="truncate text-sm font-semibold text-neutral-100">
                              {String(label)}
                            </p>
                            <span
                              className={`shrink-0 rounded-full border px-2 py-0.5 text-xs ${
                                typedSchedule.due
                                  ? "border-cyan-300/25 bg-cyan-300/10 text-cyan-100"
                                  : "border-neutral-500/25 bg-neutral-500/10 text-neutral-400"
                              }`}
                            >
                              {typedSchedule.due ? "Due" : "Not due"}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-neutral-500">
                            {typedSchedule.window_start}-
                            {typedSchedule.window_end} local
                          </p>
                          <p className="mt-1 line-clamp-2 text-xs leading-5 text-neutral-400">
                            {typedSchedule.reason}
                          </p>
                          <p className="mt-1 text-xs text-neutral-600">
                            Last run:{" "}
                            {typedSchedule.last_run?.started_at
                              ? formatDateTime(
                                  typedSchedule.last_run.started_at,
                                )
                              : "Never"}
                          </p>
                        </div>
                      );
                    })}
                    <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                      <div className="flex items-center justify-between gap-2">
                        <p className="truncate text-sm font-semibold text-neutral-100">
                          Prioritization Snapshot
                        </p>
                        <span
                          className={`shrink-0 rounded-full border px-2 py-0.5 text-xs ${
                            scheduledAgentsStatus.prioritization_snapshot_due
                              ? "border-cyan-300/25 bg-cyan-300/10 text-cyan-100"
                              : "border-neutral-500/25 bg-neutral-500/10 text-neutral-400"
                          }`}
                        >
                          {scheduledAgentsStatus.prioritization_snapshot_due
                            ? "Due"
                            : "Current"}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-neutral-500">
                        Once per day
                      </p>
                      <p className="mt-1 line-clamp-2 text-xs leading-5 text-neutral-400">
                        Latest:{" "}
                        {typeof scheduledAgentsStatus
                          .last_prioritization_snapshot?.created_at === "string"
                          ? formatDateTime(
                              scheduledAgentsStatus.last_prioritization_snapshot
                                .created_at,
                            )
                          : "No snapshot yet"}
                      </p>
                    </div>
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-neutral-500">
                    {scheduledAgentsStatusError ??
                      "Scheduled agent status has not loaded yet."}
                  </p>
                )}
              </article>
              {agentPrioritization ? (
                <article className="rounded-xl border border-cyan-300/20 bg-cyan-300/10 p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[11px] font-semibold uppercase tracking-wide text-cyan-100/70">
                        Recommended Next Agent
                      </p>
                      <h2 className="mt-1 text-base font-semibold text-neutral-50">
                        {agentPrioritization.recommended_agent_name}
                      </h2>
                      <p className="mt-2 max-w-3xl text-sm leading-6 text-cyan-50/80">
                        {agentPrioritization.reason}
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="rounded-full border border-cyan-200/30 bg-neutral-950/40 px-3 py-1 text-sm font-semibold text-cyan-50">
                        P{agentPrioritization.priority_score}
                      </span>
                      {(() => {
                        const recommendedAgent = agents.find(
                          (agent) =>
                            agent.agent_type ===
                            agentPrioritization.recommended_agent_type,
                        );

                        return recommendedAgent ? (
                          <button
                            type="button"
                            onClick={() => runAgent(recommendedAgent.id)}
                            disabled={
                              !recommendedAgent.enabled ||
                              runningAgentId === recommendedAgent.id
                            }
                            className="rounded-lg border border-cyan-200/30 bg-neutral-950/40 px-3 py-2 text-xs font-semibold text-cyan-50 hover:bg-neutral-950/60 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {runningAgentId === recommendedAgent.id
                              ? "Running..."
                              : "Run"}
                          </button>
                        ) : null;
                      })()}
                    </div>
                  </div>
                  <div className="mt-3 grid gap-2 md:grid-cols-3">
                    {agentPrioritization.ranked_agents
                      .slice(0, 3)
                      .map((rank) => (
                        <div
                          key={rank.agent_type}
                          className="rounded-lg border border-cyan-100/15 bg-neutral-950/35 px-3 py-2"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <p className="truncate text-sm font-semibold text-neutral-100">
                              {rank.agent_name}
                            </p>
                            <span className="shrink-0 text-xs font-semibold text-cyan-100">
                              P{rank.priority_score}
                            </span>
                          </div>
                          <p className="mt-1 line-clamp-2 text-xs leading-5 text-cyan-50/70">
                            {rank.reasons[0] ?? "No reason available."}
                          </p>
                        </div>
                      ))}
                  </div>
                </article>
              ) : agentPrioritizationError ? (
                <div className="rounded-xl border border-white/10 bg-neutral-950/70 p-4 text-sm text-neutral-500">
                  Agent prioritization is unavailable right now.
                </div>
              ) : null}
              {agents.map((agent) => {
              const lastRun = agent.last_run;
              const latestSummary =
                lastRun?.summary || lastRun?.error || "No runs logged yet.";
              const output = lastRun?.output_json;
              const executiveOutput =
                agent.agent_type === "executive_assistant" && isRecord(output)
                  ? output
                  : null;
              const webSearchOutput =
                agent.agent_type === "web_search" && isRecord(output)
                  ? output
                  : null;
              const readinessAdvisoryOutput =
                agent.agent_type === "readiness_advisory" && isRecord(output)
                  ? output
                  : null;
              const priorityTask = getRecordField(
                executiveOutput,
                "highest_priority_task",
              );
              const strategicGap = getRecordField(
                executiveOutput,
                "highest_strategic_gap",
              );
              const topRecommendation = getRecordField(
                executiveOutput,
                "top_recommendation",
              );
              const researchTarget =
                getTextField(webSearchOutput, "research_target") ??
                "No research target yet";
              const suggestedQueries = getStringArrayField(
                webSearchOutput,
                "suggested_queries",
              );
              const webSearchPerformed =
                getRecordField(webSearchOutput, "web_search_performed") === true;
              const readinessSuggestions = getReadinessSuggestions(
                readinessAdvisoryOutput,
              );
              const readinessApprovalRequired =
                getRecordField(readinessAdvisoryOutput, "approval_required") === true;

              return (
                <article
                  key={agent.id}
                  className="rounded-xl border border-white/10 bg-neutral-950/70 p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="text-sm font-semibold text-neutral-100">
                          {agent.name}
                        </h2>
                        <span
                          className={`rounded-full border px-2 py-0.5 text-xs ${
                            agent.enabled
                              ? "border-emerald-300/25 bg-emerald-300/10 text-emerald-100"
                              : "border-neutral-500/25 bg-neutral-500/10 text-neutral-400"
                          }`}
                        >
                          {agent.enabled ? "Enabled" : "Disabled"}
                        </span>
                        <span className="rounded-full border border-white/10 bg-white/[0.03] px-2 py-0.5 text-xs text-neutral-400">
                          {lastRun ? formatStatus(lastRun.status) : "Never run"}
                        </span>
                      </div>
                      {agent.description ? (
                        <p className="mt-1 text-xs text-neutral-500">
                          {agent.description}
                        </p>
                      ) : null}
                    </div>
                    <button
                      type="button"
                      onClick={() => runAgent(agent.id)}
                      disabled={!agent.enabled || runningAgentId === agent.id}
                      className="rounded-lg border border-cyan-300/25 bg-cyan-300/10 px-3 py-2 text-xs font-semibold text-cyan-100 hover:bg-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {runningAgentId === agent.id ? "Running..." : "Run"}
                    </button>
                  </div>
                  <p className="mt-3 line-clamp-4 whitespace-pre-wrap text-sm leading-6 text-neutral-300">
                    {latestSummary}
                  </p>
                  {executiveOutput ? (
                    <div className="mt-3 grid gap-2 md:grid-cols-3">
                      <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                          Highest Priority Task
                        </p>
                        <p className="mt-1 truncate text-sm text-neutral-200">
                          {isRecord(priorityTask)
                            ? formatExecutiveItem(
                                priorityTask,
                                "No active priority task",
                              )
                            : "No active priority task"}
                        </p>
                      </div>
                      <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                          Highest Strategic Gap
                        </p>
                        <p className="mt-1 truncate text-sm text-neutral-200">
                          {isRecord(strategicGap)
                            ? formatExecutiveItem(strategicGap, "No strategic gap")
                            : "No strategic gap"}
                        </p>
                      </div>
                      <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                          Top Recommendation
                        </p>
                        <p className="mt-1 truncate text-sm text-neutral-200">
                          {isRecord(topRecommendation)
                            ? formatExecutiveItem(
                                topRecommendation,
                                "No recommendations",
                              )
                            : "No recommendations"}
                        </p>
                      </div>
                    </div>
                  ) : null}
                  {webSearchOutput ? (
                    <div className="mt-3 grid gap-2 md:grid-cols-3">
                      <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                          Research Target
                        </p>
                        <p className="mt-1 truncate text-sm text-neutral-200">
                          {researchTarget}
                        </p>
                      </div>
                      <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                          Suggested Queries
                        </p>
                        <p className="mt-1 line-clamp-2 text-sm text-neutral-200">
                          {suggestedQueries.length > 0
                            ? suggestedQueries.slice(0, 2).join("; ")
                            : "No queries yet"}
                        </p>
                      </div>
                      <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                        <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                          Web Search Performed
                        </p>
                        <p className="mt-1 text-sm text-neutral-200">
                          {webSearchPerformed ? "Yes" : "No"}
                        </p>
                      </div>
                    </div>
                  ) : null}
                  {readinessAdvisoryOutput ? (
                    <div className="mt-3 space-y-2">
                      <div className="grid gap-2 md:grid-cols-3">
                        <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                            Readiness Suggestions
                          </p>
                          <p className="mt-1 text-sm text-neutral-200">
                            {readinessSuggestions.length}
                          </p>
                        </div>
                        <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                            Approval Required
                          </p>
                          <p className="mt-1 text-sm text-neutral-200">
                            {readinessApprovalRequired ? "Yes" : "No"}
                          </p>
                        </div>
                        <div className="rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
                            Confidence
                          </p>
                          <p className="mt-1 text-sm text-neutral-200">
                            {readinessSuggestions.length > 0
                              ? formatStatus(readinessSuggestions[0].confidence)
                              : "No suggestion"}
                          </p>
                        </div>
                      </div>
                      {readinessSuggestions.length > 0 ? (
                        <div className="space-y-2">
                          {readinessSuggestions.slice(0, 4).map((suggestion) => (
                            <div
                              key={suggestion.category}
                              className="rounded-lg border border-cyan-300/15 bg-cyan-300/5 px-3 py-2"
                            >
                              <div className="flex flex-wrap items-start justify-between gap-2">
                                <div>
                                  <p className="text-sm font-semibold text-neutral-100">
                                    {suggestion.category}
                                  </p>
                                  <p className="mt-1 text-xs text-neutral-500">
                                    Confidence: {formatStatus(suggestion.confidence)}
                                  </p>
                                </div>
                                <span className="rounded-full border border-cyan-300/25 bg-cyan-300/10 px-2 py-0.5 text-xs font-semibold text-cyan-100">
                                  {suggestion.current_score}% -&gt;{" "}
                                  {suggestion.suggested_score}%
                                </span>
                              </div>
                              <p className="mt-2 line-clamp-2 text-sm leading-6 text-neutral-300">
                                {suggestion.evidence.slice(0, 3).join("; ")}
                              </p>
                            </div>
                          ))}
                        </div>
                      ) : null}
                    </div>
                  ) : null}
                  {lastRun?.started_at ? (
                    <p className="mt-2 text-xs text-neutral-600">
                      Last run {formatDateTime(lastRun.started_at)}
                    </p>
                  ) : null}
                </article>
              );
            })}
            </>
          ) : (
            <div className="rounded-xl border border-white/10 bg-neutral-950/70 p-4 text-sm text-neutral-500">
              No agents have been defined yet.
            </div>
          )}
        </div>
      ) : null}
    </section>
  );
}
