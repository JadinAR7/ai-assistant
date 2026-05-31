import Link from "next/link";

const event = {
  title: "Corporate Escape",
  targetDate: "February 28, 2027",
  daysRemaining: 273,
  progressPercentage: 18,
  milestones: [
    {
      title: "Define income replacement target",
      status: "In progress",
      detail: "Finalize monthly runway and baseline expense number.",
    },
    {
      title: "Build trading review cadence",
      status: "Active",
      detail: "Weekly performance review and rule adherence score.",
    },
    {
      title: "Create business launch plan",
      status: "Queued",
      detail: "Outline first offer, audience, and launch steps.",
    },
    {
      title: "Set capital accumulation checkpoints",
      status: "Queued",
      detail: "Track funding, reserves, and minimum safety buffer.",
    },
  ],
  blockers: [
    "Income replacement target needs a final number.",
    "Trading metrics are not connected to Orbit yet.",
    "Business launch path needs a concrete first offer.",
  ],
  weeklyFocus: [
    "Document the exact corporate exit criteria.",
    "Review the last five trading sessions for repeatable edge.",
    "Choose one business experiment to validate this week.",
    "Create a simple readiness score rubric.",
  ],
};

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-3 overflow-hidden rounded-full bg-neutral-800">
      <div
        className="h-full rounded-full bg-blue-500"
        style={{ width: `${value}%` }}
      />
    </div>
  );
}

function Panel({
  title,
  children,
}: Readonly<{
  title: string;
  children: React.ReactNode;
}>) {
  return (
    <section className="rounded-2xl border border-white/10 bg-neutral-900 p-5">
      <h2 className="mb-4 text-sm font-semibold text-neutral-100">{title}</h2>
      {children}
    </section>
  );
}

export default function OrbitPage() {
  return (
    <main className="min-h-screen bg-neutral-950 text-white">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-neutral-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-blue-300">
              Orbit
            </p>
            <h1 className="text-lg font-semibold">Planning Dashboard</h1>
          </div>

          <Link
            href="/"
            className="rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
          >
            Helix
          </Link>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 px-4 py-4 lg:grid-cols-[1.35fr_0.65fr]">
        <section className="rounded-2xl border border-blue-500/30 bg-blue-950/20 p-6">
          <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
            <div>
              <p className="mb-2 text-sm text-blue-200/70">
                Major Event Countdown
              </p>
              <h2 className="text-3xl font-semibold tracking-tight text-white">
                {event.title}
              </h2>
              <p className="mt-2 text-sm text-neutral-400">
                Target date: {event.targetDate}
              </p>
            </div>

            <div className="rounded-2xl border border-white/10 bg-neutral-950/70 px-5 py-4 text-right">
              <p className="text-xs text-neutral-500">Days remaining</p>
              <p className="mt-1 text-4xl font-semibold text-white">
                {event.daysRemaining}
              </p>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-[1fr_220px]">
            <div className="rounded-2xl border border-white/10 bg-neutral-950 p-4">
              <div className="mb-3 flex items-center justify-between text-sm">
                <span className="text-neutral-400">Progress</span>
                <span className="font-semibold text-blue-200">
                  {event.progressPercentage}%
                </span>
              </div>
              <ProgressBar value={event.progressPercentage} />
            </div>

            <div className="rounded-2xl border border-white/10 bg-neutral-950 p-4">
              <p className="text-xs text-neutral-500">Current phase</p>
              <p className="mt-2 text-sm font-semibold text-neutral-100">
                Foundation and validation
              </p>
              <p className="mt-1 text-xs text-neutral-400">
                Mock status until Orbit data storage is connected.
              </p>
            </div>
          </div>
        </section>

        <Panel title="This Week's Focus">
          <ul className="space-y-3 text-sm text-neutral-300">
            {event.weeklyFocus.map((item) => (
              <li
                key={item}
                className="rounded-xl border border-white/10 bg-neutral-950 p-3"
              >
                {item}
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Milestones">
          <div className="grid gap-3 md:grid-cols-2">
            {event.milestones.map((milestone) => (
              <article
                key={milestone.title}
                className="rounded-xl border border-white/10 bg-neutral-950 p-4"
              >
                <div className="mb-3 flex items-start justify-between gap-3">
                  <h3 className="text-sm font-semibold text-neutral-100">
                    {milestone.title}
                  </h3>
                  <span className="shrink-0 rounded-full border border-blue-500/20 bg-blue-500/15 px-2 py-1 text-xs text-blue-200">
                    {milestone.status}
                  </span>
                </div>
                <p className="text-sm text-neutral-400">{milestone.detail}</p>
              </article>
            ))}
          </div>
        </Panel>

        <Panel title="Blockers">
          <ul className="space-y-3 text-sm text-neutral-300">
            {event.blockers.map((blocker) => (
              <li
                key={blocker}
                className="rounded-xl border border-red-500/20 bg-red-950/20 p-3 text-red-100"
              >
                {blocker}
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </main>
  );
}
