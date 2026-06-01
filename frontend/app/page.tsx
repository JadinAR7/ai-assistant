import Link from "next/link";

export const dynamic = "force-dynamic";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const modules = [
  {
    name: "Command Center",
    href: "/command-center",
    status: "Live",
  },
  {
    name: "Orbit",
    href: "/orbit",
    status: "Live",
  },
  {
    name: "Trade Journal",
    href: "/trade-journal",
    status: "Live",
  },
  {
    name: "Ascend",
    href: "/ascend",
    status: "Soon",
  },
];

type MorningBriefing = {
  success: boolean;
  generated_at: string;
  major_event: {
    title: string;
    days_remaining: number | null;
    progress_percent: number;
  } | null;
  readiness: {
    overall: number;
    categories: Array<{
      id: number;
      category_name: string;
      current_score: number;
      target_score: number;
      notes: string | null;
    }>;
  };
  priority_milestones: Array<{
    id: number;
    title: string;
    status: string;
    progress_percent: number;
    due_date: string | null;
  }>;
  top_tasks: Array<{
    id: number;
    title: string;
    status: string;
    due_date: string | null;
    goal_id: number;
  }>;
  current_blockers: string[];
  suggested_next_action: string;
  briefing_text: string;
};

async function fetchMorningBriefing() {
  try {
    const response = await fetch(`${API_BASE}/orbit/morning-briefing`, {
      cache: "no-store",
    });

    if (!response.ok) {
      return null;
    }

    return response.json() as Promise<MorningBriefing>;
  } catch {
    return null;
  }
}

function compactNextAction(value?: string) {
  if (!value || value === "No suggested action yet") {
    return "No suggested action yet";
  }

  if (value.includes("Define income replacement target")) {
    return "Clear income replacement blocker";
  }

  return value
    .replace(/^Complete or advance:\s*/i, "")
    .replace(/^Clear blocker:\s*/i, "")
    .replace(/^Move milestone forward:\s*/i, "")
    .replace(/\.$/, "");
}

function MorningStatusLine({
  briefing,
}: Readonly<{
  briefing: MorningBriefing | null;
}>) {
  if (!briefing?.success) {
    return (
      <p className="text-center text-sm text-neutral-500">
        Orbit briefing unavailable
      </p>
    );
  }

  const event = briefing.major_event;
  const eventText = event
    ? `${event.title} • ${
        event.days_remaining === null || event.days_remaining === undefined
          ? "No target date"
          : `${event.days_remaining} days`
      }`
    : "No active event";
  const nextAction = compactNextAction(briefing.suggested_next_action);

  return (
    <div className="space-y-1 text-center text-sm">
      <p className="font-medium text-cyan-100">{eventText}</p>
      <p className="text-neutral-300">Readiness {briefing.readiness.overall}%</p>
      <p className="mx-auto max-w-md truncate text-neutral-400">
        Next: {nextAction}
      </p>
    </div>
  );
}

export default async function HelixCorePage() {
  const morningBriefing = await fetchMorningBriefing();

  return (
    <main className="relative min-h-screen overflow-hidden bg-[#05070b] text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,#14315f55,transparent_34%),linear-gradient(135deg,#07111f_0%,#05070b_45%,#0b1117_100%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.035)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.035)_1px,transparent_1px)] bg-[size:48px_48px] opacity-30" />

      <section className="relative mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-5 sm:px-6 lg:px-8">
        <header className="flex items-center justify-between border-b border-white/10 pb-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.28em] text-cyan-300">
              Helix
            </p>
            <h1 className="mt-1 text-xl font-semibold tracking-tight">
              Core
            </h1>
          </div>

          <div className="rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-xs font-semibold text-emerald-200">
            System online
          </div>
        </header>

        <div className="grid flex-1 items-center gap-8 py-6 lg:grid-cols-[0.95fr_1.05fr]">
          <div className="max-w-2xl">
            <p className="text-sm font-semibold uppercase tracking-[0.24em] text-cyan-300">
              Assistant operating layer
            </p>
            <h2 className="mt-4 text-4xl font-semibold tracking-tight text-white sm:text-6xl">
              Helix Core
            </h2>
            <p className="mt-5 max-w-xl text-base leading-7 text-neutral-300">
              Helix online. What would you like to access today?
            </p>

            <div className="mt-8 flex flex-wrap gap-3">
              <Link
                href="/command-center"
                className="rounded-lg bg-cyan-300 px-4 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-200"
              >
                Open Command Center
              </Link>
              <Link
                href="/orbit"
                className="rounded-lg border border-white/15 px-4 py-3 text-sm font-semibold text-neutral-100 transition hover:bg-white/10"
              >
                Open Orbit
              </Link>
              <Link
                href="/trade-journal"
                className="rounded-lg border border-white/15 px-4 py-3 text-sm font-semibold text-neutral-100 transition hover:bg-white/10"
              >
                Open Trade Journal
              </Link>
            </div>
          </div>

          <div className="relative">
            <div className="rounded-lg border border-cyan-300/20 bg-slate-950/70 px-6 py-7 shadow-2xl shadow-cyan-950/40 backdrop-blur">
              <div className="grid place-items-center">
                <div className="grid h-48 w-48 place-items-center rounded-full border border-cyan-300/30 bg-cyan-300/[0.03] shadow-[inset_0_0_54px_rgba(34,211,238,0.16),0_0_70px_rgba(34,211,238,0.08)]">
                  <div className="grid h-28 w-28 place-items-center rounded-full border border-emerald-300/30 bg-emerald-300/10 shadow-[0_0_42px_rgba(110,231,183,0.14)]">
                    <span className="text-2xl font-semibold tracking-[0.16em] text-cyan-100">
                      HX
                    </span>
                  </div>
                </div>
              </div>

              <div className="mt-5 border-y border-white/10 py-4">
                <MorningStatusLine briefing={morningBriefing} />
              </div>

              <div className="mt-5 flex flex-wrap justify-center gap-2">
                {modules.map((module) => (
                  <Link
                    key={module.href}
                    href={module.href}
                    className={`rounded-full border px-3 py-2 text-xs font-semibold transition ${
                      module.status === "Live"
                        ? "border-cyan-300/25 bg-cyan-300/10 text-cyan-100 hover:border-cyan-200/60 hover:bg-cyan-300/15"
                        : "border-amber-300/25 bg-amber-300/10 text-amber-100 hover:border-amber-200/60 hover:bg-amber-300/15"
                    }`}
                  >
                    {module.name}
                    {module.status === "Soon" ? " soon" : ""}
                  </Link>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}
