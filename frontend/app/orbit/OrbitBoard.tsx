"use client";

import { type ReactNode, useMemo, useState } from "react";
import InboxTaskControls, { type InboxTask } from "./InboxTaskControls";

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
  status: string;
  due_date: string | null;
  goal_id: number;
  milestone_title?: string | null;
};

export type MorningBriefing = {
  success: boolean;
  top_tasks: MorningBriefingTask[];
  current_blockers: string[];
  suggested_next_action: string;
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
  milestoneTasksById: Record<number, InboxTask[]>;
  errorMessage: string | null;
}>;

const tabs = [
  "Overview",
  "Tasks",
  "Milestones",
  "Reviews",
  "Readiness",
] as const;
type Tab = (typeof tabs)[number];

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
  milestoneTasksById,
  errorMessage,
}: OrbitBoardProps) {
  const [activeTab, setActiveTab] = useState<Tab>("Overview");
  const [expandedMilestoneIds, setExpandedMilestoneIds] = useState<number[]>([]);
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

  return (
    <section className="rounded-2xl border border-white/10 bg-neutral-900/80 p-4 shadow-2xl shadow-black/30">
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
              const expanded = expandedMilestoneIds.includes(milestone.id);

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
                        {openLinkedTasks.length} open / {linkedTasks.length} total tasks
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
    </section>
  );
}
