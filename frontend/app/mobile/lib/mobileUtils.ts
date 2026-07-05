import { type ScheduleBlock } from "./mobileTypes";

const dayNames = [
  "sunday",
  "monday",
  "tuesday",
  "wednesday",
  "thursday",
  "friday",
  "saturday",
];

export function formatLabel(value?: string | null) {
  if (!value) return "Unknown";
  return value
    .replaceAll("_", " ")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function formatCurrency(value?: number | null) {
  if (value === null || value === undefined || Number.isNaN(value)) return "--";
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  });
}

export function formatDate(value?: string | null) {
  if (!value) return "No date";
  const date = new Date(`${value}T00:00:00`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(date);
}

function formatTime(value?: string | null) {
  if (!value) return "";
  const [hourValue, minuteValue] = value.split(":");
  const hour = Number(hourValue);
  const minute = Number(minuteValue || "0");
  if (Number.isNaN(hour) || Number.isNaN(minute)) return value;
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(2026, 0, 1, hour, minute));
}

export function formatRelativeAge(timestamp?: string | null) {
  if (!timestamp) return "No scan yet";
  const value = new Date(timestamp).getTime();
  if (Number.isNaN(value)) return "Unknown";

  const seconds = Math.max(0, Math.floor((Date.now() - value) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function getTimeGreeting(date = new Date()) {
  const hour = date.getHours();
  if (hour < 12) return "Good morning";
  if (hour < 17) return "Good afternoon";
  return "Good evening";
}

function toDateKey(date: Date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(
    date.getDate(),
  ).padStart(2, "0")}`;
}

export function getBlockTitle(block?: ScheduleBlock | null) {
  if (!block) return "Today's schedule will appear here.";
  return block.title?.trim() || formatLabel(block.category);
}

export function getBlockTime(block?: ScheduleBlock | null) {
  if (!block) return "No block loaded";
  if (block.block_type === "flexible") {
    return `${block.duration_minutes ?? 30} min flexible`;
  }

  const start = formatTime(block.start_time);
  const end = formatTime(block.end_time);
  return start && end ? `${start}-${end}` : "Time not set";
}

export function getNextScheduleBlock(blocks: ScheduleBlock[]) {
  const now = new Date();
  const todayKey = toDateKey(now);
  const todayName = dayNames[now.getDay()];
  const currentMinutes = now.getHours() * 60 + now.getMinutes();

  const fixedToday = blocks
    .filter((block) => {
      if (block.active === false || block.block_type !== "fixed") return false;
      return block.specific_date === todayKey || block.day_of_week === todayName;
    })
    .map((block) => {
      const [hourValue, minuteValue] = (block.start_time || "23:59").split(":");
      const startMinutes = Number(hourValue) * 60 + Number(minuteValue || "0");
      return { block, startMinutes };
    })
    .filter(({ startMinutes }) => startMinutes >= currentMinutes)
    .sort((left, right) => left.startMinutes - right.startMinutes);

  if (fixedToday[0]) return fixedToday[0].block;

  return (
    blocks.find(
      (block) => block.active !== false && block.block_type === "flexible",
    ) ?? null
  );
}

export function getNextFlexibleBlock(blocks: ScheduleBlock[]) {
  return (
    blocks.find(
      (block) => block.active !== false && block.block_type === "flexible",
    ) ?? null
  );
}

export function getTodayBlocks(blocks: ScheduleBlock[]) {
  const todayKey = toDateKey(new Date());
  const todayName = dayNames[new Date().getDay()];

  return blocks
    .filter((block) => {
      if (block.active === false) return false;
      if (block.block_type === "flexible") return true;
      return block.specific_date === todayKey || block.day_of_week === todayName;
    })
    .slice(0, 5);
}
