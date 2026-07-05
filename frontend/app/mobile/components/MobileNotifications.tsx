import { useState } from "react";

import {
  MobileCard,
  MobilePrimaryButton,
  MobileSecondaryButton,
} from "./MobileCard";
import {
  type MobileNotification,
  type MobileNotificationCenter,
  type MobileReminder,
} from "../lib/mobileTypes";

function formatDueAt(value?: string | null) {
  if (!value) return "Time not set";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  const today = new Date();
  const tomorrow = new Date();
  tomorrow.setDate(today.getDate() + 1);
  const sameDay =
    date.getFullYear() === today.getFullYear() &&
    date.getMonth() === today.getMonth() &&
    date.getDate() === today.getDate();
  const nextDay =
    date.getFullYear() === tomorrow.getFullYear() &&
    date.getMonth() === tomorrow.getMonth() &&
    date.getDate() === tomorrow.getDate();
  const time = new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);

  if (sameDay) return `Today ${time}`;
  if (nextDay) return `Tomorrow ${time}`;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function NotificationPill({
  notification,
}: Readonly<{ notification: MobileNotification }>) {
  const tone =
    notification.priority === "high"
      ? "border-amber-300/25 bg-amber-300/10 text-amber-100"
      : "border-white/10 bg-white/[0.04] text-neutral-300";

  return (
    <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold ${tone}`}>
      {notification.type}
    </span>
  );
}

export default function MobileNotifications({
  center,
  actionLoading,
  onCompleteReminder,
  onDismissReminder,
  onAckNotification,
  onCompleteNotification,
  onRetry,
  loadFailed,
}: Readonly<{
  center: MobileNotificationCenter | null;
  actionLoading: string | null;
  onCompleteReminder: (id: number) => void;
  onDismissReminder: (id: number) => void;
  onAckNotification: (id: number) => void;
  onCompleteNotification: (id: number) => void;
  onRetry: () => void;
  loadFailed?: boolean;
}>) {
  const [showAll, setShowAll] = useState(false);
  const reminders = center?.reminders ?? [];
  const notifications = center?.notifications ?? [];
  const items = [
    ...reminders.map((reminder) => ({ kind: "reminder" as const, reminder })),
    ...notifications.map((notification) => ({
      kind: "notification" as const,
      notification,
    })),
  ];
  const visibleItems = showAll ? items : items.slice(0, 3);
  const nextReminder = center?.next_reminder ?? reminders[0] ?? null;

  return (
    <MobileCard>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
            Reminders & Notifications
          </p>
          <h2 className="mt-1 text-lg font-semibold text-neutral-100">
            {nextReminder ? nextReminder.title : "Nothing pending"}
          </h2>
          <p className="mt-1 text-sm text-neutral-400">
            {nextReminder
              ? formatDueAt(nextReminder.due_at)
              : "Your mobile queue is clear."}
          </p>
        </div>
        <div className="grid min-w-16 gap-1 text-right">
          <span className="text-lg font-semibold text-neutral-100">
            {center?.pending_count ?? 0}
          </span>
          <span className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
            Pending
          </span>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2">
        <div className="rounded-xl border border-white/10 bg-black/25 px-3 py-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
            Unread
          </p>
          <p className="mt-1 text-sm font-semibold text-neutral-100">
            {center?.unread_count ?? 0}
          </p>
        </div>
        <div className="rounded-xl border border-white/10 bg-black/25 px-3 py-2">
          <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
            Next
          </p>
          <p className="mt-1 text-sm font-semibold text-neutral-100">
            {nextReminder ? formatDueAt(nextReminder.due_at) : "--"}
          </p>
        </div>
      </div>

      {loadFailed ? (
        <div className="mt-3 rounded-xl border border-amber-300/20 bg-amber-300/10 p-3">
          <p className="text-sm font-semibold text-amber-100">
            Couldn&apos;t load reminders.
          </p>
          <p className="mt-1 text-xs leading-5 text-amber-100/75">
            Try again when the Mac mini is reachable.
          </p>
          <div className="mt-3">
            <MobileSecondaryButton onClick={onRetry}>Retry</MobileSecondaryButton>
          </div>
        </div>
      ) : null}

      {visibleItems.length ? (
        <div className="mt-3 grid gap-2">
          {visibleItems.map((item) =>
            item.kind === "reminder" ? (
              <ReminderRow
                key={`reminder-${item.reminder.id}`}
                reminder={item.reminder}
                actionLoading={actionLoading}
                onComplete={onCompleteReminder}
                onDismiss={onDismissReminder}
              />
            ) : (
              <NotificationRow
                key={`notification-${item.notification.id}`}
                notification={item.notification}
                actionLoading={actionLoading}
                onAck={onAckNotification}
                onComplete={onCompleteNotification}
              />
            ),
          )}
        </div>
      ) : null}

      {items.length > 3 ? (
        <button
          type="button"
          onClick={() => setShowAll((current) => !current)}
          className="mt-3 min-h-10 w-full rounded-xl border border-white/10 bg-white/[0.04] px-3 text-sm font-semibold text-neutral-100"
        >
          {showAll ? "Show Less" : "View All"}
        </button>
      ) : null}
    </MobileCard>
  );
}

function ReminderRow({
  reminder,
  actionLoading,
  onComplete,
  onDismiss,
}: Readonly<{
  reminder: MobileReminder;
  actionLoading: string | null;
  onComplete: (id: number) => void;
  onDismiss: (id: number) => void;
}>) {
  const completeKey = `reminder-complete-${reminder.id}`;
  const dismissKey = `reminder-dismiss-${reminder.id}`;

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-neutral-100">{reminder.title}</p>
          <p className="mt-1 text-xs text-neutral-400">{formatDueAt(reminder.due_at)}</p>
        </div>
        <span className="rounded-full border border-cyan-300/20 bg-cyan-300/10 px-2 py-1 text-[11px] font-semibold text-cyan-100">
          {reminder.source}
        </span>
      </div>
      {reminder.body ? (
        <p className="mt-2 text-xs leading-5 text-neutral-400">{reminder.body}</p>
      ) : null}
      <div className="mt-3 grid grid-cols-2 gap-2">
        <MobilePrimaryButton
          onClick={() => onComplete(reminder.id)}
          disabled={Boolean(actionLoading)}
        >
          {actionLoading === completeKey ? "Saving..." : "Done"}
        </MobilePrimaryButton>
        <MobileSecondaryButton
          onClick={() => onDismiss(reminder.id)}
          disabled={Boolean(actionLoading)}
        >
          {actionLoading === dismissKey ? "Dismissing..." : "Dismiss"}
        </MobileSecondaryButton>
      </div>
    </div>
  );
}

function NotificationRow({
  notification,
  actionLoading,
  onAck,
  onComplete,
}: Readonly<{
  notification: MobileNotification;
  actionLoading: string | null;
  onAck: (id: number) => void;
  onComplete: (id: number) => void;
}>) {
  const ackKey = `notification-ack-${notification.id}`;
  const completeKey = `notification-complete-${notification.id}`;

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-neutral-100">
            {notification.title}
          </p>
          <p className="mt-1 text-xs text-neutral-400">
            {notification.body || "No details attached."}
          </p>
        </div>
        <NotificationPill notification={notification} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2">
        <MobileSecondaryButton
          onClick={() => onAck(notification.id)}
          disabled={Boolean(actionLoading)}
        >
          {actionLoading === ackKey ? "Saving..." : "Dismiss"}
        </MobileSecondaryButton>
        <MobilePrimaryButton
          onClick={() => onComplete(notification.id)}
          disabled={Boolean(actionLoading)}
        >
          {actionLoading === completeKey ? "Completing..." : "Done"}
        </MobilePrimaryButton>
      </div>
    </div>
  );
}
