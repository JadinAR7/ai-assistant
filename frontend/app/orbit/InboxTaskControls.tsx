"use client";

import { type FormEvent, useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export type InboxTask = {
  id: number;
  goal_id: number;
  title: string;
  description: string | null;
  status: string;
  due_date: string | null;
  completed_at: string | null;
  milestones?: LinkedMilestone[];
};

export type LinkedMilestone = {
  id: number;
  title: string;
  status: string;
  progress_percent: number;
};

function isCompleted(task: InboxTask) {
  return ["complete", "completed", "done", "cancelled"].includes(getStatus(task));
}

function getStatus(task: InboxTask) {
  return task.status.toLowerCase();
}

function formatStatus(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatDate(value: string | null) {
  if (!value) {
    return null;
  }

  const date = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function getLocalDateKey(date: Date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");

  return `${year}-${month}-${day}`;
}

function getCompletedDateKey(task: InboxTask) {
  if (!task.completed_at) {
    return null;
  }

  const date = new Date(task.completed_at);

  if (Number.isNaN(date.getTime())) {
    return null;
  }

  return getLocalDateKey(date);
}

function getStatusPillClasses(status: string) {
  switch (status.toLowerCase()) {
    case "in_progress":
      return "border-cyan-300/25 bg-cyan-300/10 text-cyan-100";
    case "open":
      return "border-blue-300/25 bg-blue-300/10 text-blue-100";
    case "queued":
      return "border-violet-300/25 bg-violet-300/10 text-violet-100";
    case "completed":
    case "complete":
    case "done":
      return "border-emerald-300/25 bg-emerald-300/10 text-emerald-100";
    default:
      return "border-white/10 bg-white/5 text-neutral-300";
  }
}

export default function InboxTaskControls({
  initialTasks,
  milestones,
}: Readonly<{
  initialTasks: InboxTask[];
  milestones: LinkedMilestone[];
}>) {
  const router = useRouter();
  const [tasks, setTasks] = useState(initialTasks);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [selectedMilestoneIds, setSelectedMilestoneIds] = useState<number[]>([]);
  const [showCompletedToday, setShowCompletedToday] = useState(false);
  const [showOlderCompleted, setShowOlderCompleted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const openTasks = useMemo(
    () => tasks.filter((task) => !isCompleted(task)),
    [tasks],
  );
  const completedTasks = useMemo(
    () => tasks.filter((task) => isCompleted(task)),
    [tasks],
  );
  const todayKey = getLocalDateKey(new Date());
  const completedToday = useMemo(
    () =>
      completedTasks.filter((task) => getCompletedDateKey(task) === todayKey),
    [completedTasks, todayKey],
  );
  const olderCompleted = useMemo(
    () =>
      completedTasks.filter((task) => getCompletedDateKey(task) !== todayKey),
    [completedTasks, todayKey],
  );

  function refreshOrbit() {
    startTransition(() => {
      router.refresh();
    });
  }

  async function reloadTasks() {
    const response = await fetch(`${API_BASE}/orbit/inbox-tasks`, {
      cache: "no-store",
    });

    if (!response.ok) {
      throw new Error("Unable to refresh inbox tasks.");
    }

    setTasks((await response.json()) as InboxTask[]);
    refreshOrbit();
  }

  async function createTask(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const cleanTitle = title.trim();
    if (!cleanTitle) {
      setError("Task title is required.");
      return;
    }

    setError(null);

    const response = await fetch(`${API_BASE}/orbit/inbox-tasks`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        title: cleanTitle,
        description: description.trim() || null,
        due_date: dueDate || null,
        milestone_ids: selectedMilestoneIds,
      }),
    });

    if (!response.ok) {
      setError("Could not create task.");
      return;
    }

    setTitle("");
    setDescription("");
    setDueDate("");
    setSelectedMilestoneIds([]);
    await reloadTasks();
  }

  async function updateTaskStatus(task: InboxTask, status: string) {
    setError(null);
    const isCompleting = status === "completed";

    const response = await fetch(`${API_BASE}/orbit/tasks/${task.id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        status,
        completed_at: isCompleting ? new Date().toISOString() : null,
      }),
    });

    if (!response.ok) {
      setError("Could not update task.");
      return;
    }

    await reloadTasks();
  }

  function TaskRow({
    task,
    completed = false,
  }: Readonly<{
    task: InboxTask;
    completed?: boolean;
  }>) {
    const formattedDueDate = formatDate(task.due_date);
    const status = getStatus(task);
    const linkedMilestones = task.milestones ?? [];

    return (
      <article className="rounded-xl border border-white/10 bg-neutral-950/80 px-3 py-2.5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <h3 className="truncate text-sm font-semibold leading-5 text-neutral-100">
              {task.title}
            </h3>
            {task.description ? (
              <p className="mt-1 whitespace-pre-line text-xs leading-5 text-neutral-400">
                {task.description}
              </p>
            ) : null}
            {linkedMilestones.length > 0 ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {linkedMilestones.map((milestone) => (
                  <span
                    key={milestone.id}
                    className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-2 py-0.5 text-[11px] font-semibold text-cyan-100"
                  >
                    {milestone.title}
                  </span>
                ))}
              </div>
            ) : null}
            <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-neutral-500">
              {formattedDueDate ? <span>Due {formattedDueDate}</span> : null}
              <span
                className={`rounded-full border px-2 py-0.5 text-[11px] font-semibold ${getStatusPillClasses(task.status)}`}
              >
                {formatStatus(task.status)}
              </span>
            </div>
          </div>

          {!completed ? (
            <div className="flex shrink-0 flex-wrap gap-1.5">
              {status !== "queued" ? (
                <button
                  type="button"
                  onClick={() => updateTaskStatus(task, "queued")}
                  disabled={isPending}
                  className="rounded-lg border border-white/10 px-2 py-1 text-xs font-semibold text-neutral-300 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Queue
                </button>
              ) : null}

              {status !== "in_progress" ? (
                <button
                  type="button"
                  onClick={() => updateTaskStatus(task, "in_progress")}
                  disabled={isPending}
                  className="rounded-lg border border-cyan-300/25 bg-cyan-300/10 px-2 py-1 text-xs font-semibold text-cyan-100 hover:bg-cyan-300/20 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  Start
                </button>
              ) : null}

              <button
                type="button"
                onClick={() => updateTaskStatus(task, "completed")}
                disabled={isPending}
                className="rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-2 py-1 text-xs font-semibold text-emerald-200 hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-60"
              >
                Complete
              </button>
            </div>
          ) : null}
        </div>
      </article>
    );
  }

  function toggleMilestone(milestoneId: number) {
    setSelectedMilestoneIds((current) =>
      current.includes(milestoneId)
        ? current.filter((id) => id !== milestoneId)
        : [...current, milestoneId],
    );
  }

  return (
    <div className="space-y-4">
      <form onSubmit={createTask} className="space-y-2">
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Add inbox task"
          className="w-full rounded-xl border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none placeholder:text-neutral-500 focus:border-blue-400/50"
        />
        <div className="grid gap-2 sm:grid-cols-[1fr_132px_auto]">
          <textarea
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Description, notes, or checklist"
            rows={2}
            className="min-h-20 min-w-0 resize-y rounded-xl border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none placeholder:text-neutral-500 focus:border-blue-400/50"
          />
          <input
            type="date"
            value={dueDate}
            onChange={(event) => setDueDate(event.target.value)}
            className="h-10 rounded-xl border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none focus:border-blue-400/50"
          />
          <button
            type="submit"
            disabled={isPending}
            className="h-10 rounded-xl bg-blue-500 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Add
          </button>
        </div>
        {milestones.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {milestones.map((milestone) => {
              const selected = selectedMilestoneIds.includes(milestone.id);

              return (
                <button
                  key={milestone.id}
                  type="button"
                  onClick={() => toggleMilestone(milestone.id)}
                  className={`rounded-full border px-2.5 py-1 text-xs font-semibold transition ${
                    selected
                      ? "border-cyan-300/50 bg-cyan-300/15 text-cyan-100"
                      : "border-white/10 bg-white/[0.03] text-neutral-500 hover:border-white/20 hover:text-white"
                  }`}
                >
                  {milestone.title}
                </button>
              );
            })}
          </div>
        ) : null}
      </form>

      {error ? (
        <div className="rounded-xl border border-red-500/20 bg-red-950/20 p-3 text-sm text-red-100">
          {error}
        </div>
      ) : null}

      <section className="space-y-2">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
            Open Tasks
          </h2>
          <span className="text-xs text-neutral-600">{openTasks.length}</span>
        </div>

        {openTasks.length > 0 ? (
          <div className="space-y-2">
            {openTasks.map((task) => (
              <TaskRow key={task.id} task={task} />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-white/10 bg-neutral-950 p-4 text-sm text-neutral-400">
            No open inbox tasks
          </div>
        )}
      </section>

      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => setShowCompletedToday((current) => !current)}
          className="text-xs font-semibold text-neutral-400 underline underline-offset-4 hover:text-white"
        >
          {showCompletedToday
            ? "Hide completed today"
            : "Show completed today"}
        </button>

        <button
          type="button"
          onClick={() => setShowOlderCompleted((current) => !current)}
          className="text-xs font-semibold text-neutral-400 underline underline-offset-4 hover:text-white"
        >
          {showOlderCompleted
            ? "Hide older completed"
            : "Show older completed"}
        </button>
      </div>

      {showCompletedToday ? (
        <section className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Completed Today
            </h2>
            <span className="text-xs text-neutral-600">
              {completedToday.length}
            </span>
          </div>

          {completedToday.length > 0 ? (
            <div className="space-y-2">
              {completedToday.map((task) => (
                <TaskRow key={task.id} task={task} completed />
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-white/10 bg-neutral-950 p-4 text-sm text-neutral-400">
              No completed tasks
            </div>
          )}
        </section>
      ) : null}

      {showOlderCompleted ? (
        <section className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Older Completed
            </h2>
            <span className="text-xs text-neutral-600">
              {olderCompleted.length}
            </span>
          </div>

          {olderCompleted.length > 0 ? (
            <div className="space-y-2">
              {olderCompleted.map((task) => (
                <TaskRow key={task.id} task={task} completed />
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-white/10 bg-neutral-950 p-4 text-sm text-neutral-400">
              No completed tasks
            </div>
          )}
        </section>
      ) : null}
    </div>
  );
}
