import { type ReactNode } from "react";

export function MobileCard({
  children,
  className = "",
}: Readonly<{ children: ReactNode; className?: string }>) {
  return (
    <section
      className={`rounded-2xl border border-white/10 bg-neutral-900/80 p-4 shadow-xl shadow-black/20 ${className}`}
    >
      {children}
    </section>
  );
}

export function MobileMetric({
  label,
  value,
  tone = "neutral",
}: Readonly<{
  label: string;
  value: ReactNode;
  tone?: "neutral" | "good" | "warn";
}>) {
  const toneClass =
    tone === "good"
      ? "text-emerald-200"
      : tone === "warn"
        ? "text-amber-200"
        : "text-neutral-100";

  return (
    <div className="rounded-xl border border-white/10 bg-black/25 px-3 py-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-neutral-500">
        {label}
      </p>
      <p className={`mt-1 text-sm font-semibold ${toneClass}`}>{value}</p>
    </div>
  );
}

export function MobilePrimaryButton({
  children,
  onClick,
  disabled,
  type = "button",
}: Readonly<{
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  type?: "button" | "submit";
}>) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className="min-h-12 rounded-xl bg-cyan-300 px-4 py-3 text-center text-sm font-semibold text-slate-950 transition hover:bg-cyan-200 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {children}
    </button>
  );
}

export function MobileSecondaryButton({
  children,
  onClick,
  disabled,
}: Readonly<{
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
}>) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="min-h-12 rounded-xl border border-white/10 bg-white/[0.04] px-4 py-3 text-center text-sm font-semibold text-neutral-100 transition hover:bg-white/[0.08] disabled:cursor-not-allowed disabled:opacity-60"
    >
      {children}
    </button>
  );
}
