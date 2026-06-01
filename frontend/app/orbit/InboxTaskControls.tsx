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
};

function isCompleted(task: InboxTask) {
  return ["complete", "completed", "done", "cancelled"].includes(
    task.status.toLowerCase(),
  );
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

export default function InboxTaskControls({
  initialTasks,
}: Readonly<{
  initialTasks: InboxTask[];
}>) {
  const router = useRouter();
  const [tasks, setTasks] = useState(initialTasks);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [showCompletedToday, setShowCompletedToday] = useState(false);
  const [showOlderCompleted, setShowOlderCompleted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  const openTasks = useMemo(() => tasks.filter((task) => !isCompleted(task)), [tasks]);
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
      }),
    });

    if (!response.ok) {
      setError("Could not create task.");
      return;
    }

    setTitle("");
    setDescription("");
    setDueDate("");
    await reloadTasks();
  }

  async function completeTask(task: InboxTask) {
    setError(null);

    const response = await fetch(`${API_BASE}/orbit/tasks/${task.id}`, {
      method: "PATCH",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        status: "completed",
        completed_at: new Date().toISOString(),
      }),
    });

    if (!response.ok) {
      setError("Could not complete task.");
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

    return (
      <article className="rounded-xl border border-white/10 bg-neutral-950 p-3">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h3 className="text-sm font-semibold leading-5 text-neutral-100">
              {task.title}
            </h3>
            {task.description ? (
              <p className="mt-1 text-xs leading-5 text-neutral-400">
                {task.description}
              </p>
            ) : null}
            <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-neutral-500">
              <span>{formatStatus(task.status)}</span>
              {formattedDueDate ? <span>Due {formattedDueDate}</span> : null}
            </div>
          </div>

          {!completed ? (
            <button
              type="button"
              onClick={() => completeTask(task)}
              disabled={isPending}
              className="shrink-0 rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-2 py-1 text-xs font-semibold text-emerald-200 hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-60"
            >
              Complete
            </button>
          ) : null}
        </div>
      </article>
    );
  }

  return (
    <div className="space-y-3">
      <form onSubmit={createTask} className="space-y-2">
        <input
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="Add inbox task"
          className="w-full rounded-xl border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none placeholder:text-neutral-500 focus:border-blue-400/50"
        />
        <div className="grid gap-2 sm:grid-cols-[1fr_132px_auto]">
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="Description"
            className="min-w-0 rounded-xl border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none placeholder:text-neutral-500 focus:border-blue-400/50"
          />
          <input
            type="date"
            value={dueDate}
            onChange={(event) => setDueDate(event.target.value)}
            className="rounded-xl border border-white/10 bg-neutral-950 px-3 py-2 text-sm text-white outline-none focus:border-blue-400/50"
          />
          <button
            type="submit"
            disabled={isPending}
            className="rounded-xl bg-blue-500 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Add
          </button>
        </div>
      </form>

      {error ? (
        <div className="rounded-xl border border-red-500/20 bg-red-950/20 p-3 text-sm text-red-100">
          {error}
        </div>
      ) : null}

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
        completedToday.length > 0 ? (
          <div className="space-y-2">
            {completedToday.map((task) => (
              <TaskRow key={task.id} task={task} completed />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-white/10 bg-neutral-950 p-4 text-sm text-neutral-400">
            No completed tasks
          </div>
        )
      ) : null}

      {showOlderCompleted ? (
        olderCompleted.length > 0 ? (
          <div className="space-y-2">
            {olderCompleted.map((task) => (
              <TaskRow key={task.id} task={task} completed />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-white/10 bg-neutral-950 p-4 text-sm text-neutral-400">
            No completed tasks
          </div>
        )
      ) : null}
    </div>
  );
}
