"use client";

import { type ReactNode, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import InboxTaskControls, { type InboxTask } from "./InboxTaskControls";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";
const CORPORATE_ESCAPE_TITLE = "Corporate Escape";
const INBOX_MILESTONE_TITLE = "Inbox / General";

export type MajorEvent = {
  id: number;
  title: string;
  description: string | null;
  target_date: string | null;
  status: string;
  progress_percent: number;
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
  milestones?: Array<{
    id: number;
    title: string;
    status: string;
    progress_percent: number;
  }>;
  milestone_title?: string | null;
};

export type MorningBriefing = {
  success: boolean;
  top_tasks: MorningBriefingTask[];
  current_blockers: string[];
  suggested_next_action: string;
};

export type DailyCloseout = {
  success: boolean;
  generated_at: string;
  completed_today: MorningBriefingTask[];
  open_tasks: MorningBriefingTask[];
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
    total_pnl: number;
    average_rule_adherence: number | null;
    sessions: Array<{
      id: number;
      session_date: string;
      symbol: string;
      pnl: number;
      session_grade?: string | null;
    }>;
  };
  recommended_review_prompt: string;
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

type OrbitBoardProps = Readonly<{
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
  milestoneTasksById: Record<number, InboxTask[]>;
  milestoneAdvisoriesById: Record<number, MilestoneProgressAdvisory>;
  latestProgressHistoryByMilestoneId: Record<number, MilestoneProgressHistory>;
  agents: AgentDefinition[];
  agentsError: string | null;
  errorMessage: string | null;
}>;

const tabs = [
  "Overview",
  "Tasks",
  "Milestones",
  "Reviews",
  "Readiness",
  "Agents",
] as const;
type Tab = (typeof tabs)[number];
type Toast = {
  message: string;
  type: "success" | "error";
};

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

function formatStatus(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
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

function isTaskOpen(task: InboxTask) {
  return !["complete", "completed", "done", "cancelled"].includes(
    task.status.toLowerCase(),
  );
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
    <section className="rounded-xl border border-white/10 bg-neutral-950/70 p-4">
      <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-neutral-500">
        {title}
      </h2>
      {children}
    </section>
  );
}

export default function OrbitBoard({
  event,
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
  milestoneTasksById,
  milestoneAdvisoriesById,
  latestProgressHistoryByMilestoneId,
  agents: initialAgents,
  agentsError,
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
  const [closeoutRating, setCloseoutRating] = useState("");
  const [closeoutNotes, setCloseoutNotes] = useState("");
  const [loadingCloseout, setLoadingCloseout] = useState(false);
  const [savingCloseoutReview, setSavingCloseoutReview] = useState(false);
  const [agents, setAgents] = useState<AgentDefinition[]>(initialAgents);
  const [runningAgentId, setRunningAgentId] = useState<number | null>(null);
  const [toast, setToast] = useState<Toast | null>(null);
  const daysRemaining = getDaysRemaining(event?.target_date ?? null);
  const progressPercentage = event?.progress_percent ?? 0;
  const overallReadiness = getOverallReadiness(readiness);
  const priorityTasks = morningBriefing?.top_tasks.slice(0, 3) ?? [];
  const activeBlockers = morningBriefing?.current_blockers ?? [];
  const tagMilestones = milestones.filter(
    (milestone) => milestone.title !== INBOX_MILESTONE_TITLE,
  );
  const suggestedNextAction =
    morningBriefing?.suggested_next_action &&
    morningBriefing.suggested_next_action !== "No suggested action yet"
      ? morningBriefing.suggested_next_action
      : null;

  const activeMilestones = useMemo(
    () =>
      [...milestones].sort(
        (left, right) => left.progress_percent - right.progress_percent,
      ),
    [milestones],
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

  return (
    <section className="relative rounded-2xl border border-white/10 bg-neutral-900/80 p-4 shadow-2xl shadow-black/30">
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

      <div className="mb-4 flex flex-wrap gap-2">
        {tabs.map((tab) => (
          <button
            key={tab}
            type="button"
            onClick={() => setActiveTab(tab)}
            className={`rounded-full border px-3 py-1.5 text-xs font-semibold transition ${
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
        <div className="grid gap-3 lg:grid-cols-[1.1fr_0.9fr]">
          <MiniPanel title="Corporate Escape">
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
            <div className="mt-4">
              <div className="mb-2 flex justify-between text-xs text-neutral-400">
                <span>Progress</span>
                <span>{progressPercentage}%</span>
              </div>
              <ProgressBar value={progressPercentage} />
            </div>
          </MiniPanel>

          <MiniPanel title="Suggested Next Action">
            <p className="text-sm leading-6 text-neutral-200">
              {suggestedNextAction ??
                (morningBriefingError
                  ? "Suggested action unavailable right now."
                  : "No suggested action yet")}
            </p>
          </MiniPanel>

          <MiniPanel title="Top Priority Tasks">
            {priorityTasks.length > 0 ? (
              <div className="space-y-2">
                {priorityTasks.map((task) => (
                  <div
                    key={task.id}
                    className="flex items-center justify-between gap-3 rounded-lg bg-white/[0.03] px-3 py-2"
                  >
                    <span className="min-w-0 truncate text-sm text-neutral-200">
                      {task.title}
                    </span>
                    <span className="shrink-0 text-xs text-neutral-500">
                      {task.milestone_title ?? formatStatus(task.status)}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-neutral-500">No priority tasks</p>
            )}
          </MiniPanel>

          <MiniPanel title="Current Blockers">
            {activeBlockers.length > 0 ? (
              <div className="space-y-2">
                {activeBlockers.slice(0, 4).map((blocker) => (
                  <p
                    key={blocker}
                    className="rounded-lg border border-red-400/20 bg-red-400/10 px-3 py-2 text-sm text-red-100"
                  >
                    {blocker}
                  </p>
                ))}
              </div>
            ) : (
              <p className="text-sm text-neutral-500">No active blockers</p>
            )}
          </MiniPanel>

          <MiniPanel title="Overall Readiness">
            <div className="flex items-center justify-between gap-4">
              <span className="text-3xl font-semibold text-white">
                {overallReadiness === null ? "--" : `${overallReadiness}%`}
              </span>
              <span className="text-xs text-neutral-500">
                {readiness.length} categories
              </span>
            </div>
            <div className="mt-4">
              <ProgressBar value={overallReadiness ?? 0} />
            </div>
          </MiniPanel>
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
              initialTasks={inboxTasks}
              milestones={tagMilestones}
            />
          )}
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
                        Tasks: {advisory?.completed_linked_tasks ?? 0} complete /{" "}
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
                    <span>Current: {milestone.progress_percent}%</span>
                    <span>
                      Task-based suggestion:{" "}
                      {suggestedPercent === null ? "--" : `${suggestedPercent}%`}
                    </span>
                    {showSuggestedPercent ? (
                      <span className="text-cyan-200">
                        Suggested from tasks: {suggestedPercent}%
                      </span>
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
                ? "No milestones are linked to Corporate Escape yet."
                : "Milestones will appear once the Corporate Escape event is available."}
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
                <div className="grid gap-2 sm:grid-cols-3">
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
                      {dailyCloseout.trade_summary.sessions_logged_today}
                    </p>
                    <p className="text-xs text-neutral-500">
                      {dailyCloseout.trade_summary.sessions_logged_today === 0
                        ? "No trade sessions logged today"
                        : "trade sessions today"}
                    </p>
                  </div>
                </div>

                <pre className="max-h-72 overflow-auto whitespace-pre-wrap rounded-lg border border-white/10 bg-black/20 p-3 text-sm leading-6 text-neutral-300">
                  {dailyCloseout.closeout_text}
                </pre>

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

          {reviews.length > 0 ? (
            reviews.map((review) => (
              <article
                key={review.id}
                className="rounded-xl border border-white/10 bg-neutral-950/70 p-4"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="truncate text-sm font-semibold text-neutral-100">
                      {review.title ?? formatStatus(review.review_type)}
                    </h2>
                    {review.summary ? (
                      <p className="mt-1 text-sm leading-6 text-neutral-400">
                        {review.summary}
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
            ))
          ) : (
            <div className="rounded-xl border border-white/10 bg-neutral-950/70 p-4 text-sm text-neutral-500">
              {reviewsError ? "Reviews are unavailable right now." : "No recent reviews"}
            </div>
          )}
        </div>
      ) : null}

      {activeTab === "Readiness" ? (
        <div className="space-y-2">
          {readinessError ? (
            <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-sm text-red-100">
              Readiness is unavailable right now.
            </div>
          ) : readiness.length > 0 ? (
            readiness.map((category) => (
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
              No readiness categories have been added to Orbit yet.
            </div>
          )}
        </div>
      ) : null}

      {activeTab === "Agents" ? (
        <div className="space-y-2">
          {agentsError ? (
            <div className="rounded-xl border border-red-500/30 bg-red-950/20 p-4 text-sm text-red-100">
              Agents are unavailable right now.
            </div>
          ) : agents.length > 0 ? (
            agents.map((agent) => {
              const lastRun = agent.last_run;
              const latestSummary =
                lastRun?.summary || lastRun?.error || "No runs logged yet.";

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
                  {lastRun?.started_at ? (
                    <p className="mt-2 text-xs text-neutral-600">
                      Last run {formatDateTime(lastRun.started_at)}
                    </p>
                  ) : null}
                </article>
              );
            })
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
