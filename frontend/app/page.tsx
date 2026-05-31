import Link from "next/link";

const modules = [
  {
    name: "Command Center",
    href: "/command-center",
    status: "Live",
    description: "Chat, scan controls, market status, and latest MES reads.",
  },
  {
    name: "Orbit",
    href: "/orbit",
    status: "Live",
    description: "Planning, milestones, major events, and execution tracking.",
  },
  {
    name: "Trade Journal",
    href: "/trade-journal",
    status: "Soon",
    description: "Session reviews, rule adherence, and performance memory.",
  },
  {
    name: "Ascend",
    href: "/ascend",
    status: "Soon",
    description: "Long-term goals, training arcs, and progress systems.",
  },
];

export default function HelixCorePage() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[#05070b] text-white">
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_top,#14315f55,transparent_34%),linear-gradient(135deg,#07111f_0%,#05070b_45%,#0b1117_100%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.035)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.035)_1px,transparent_1px)] bg-[size:48px_48px] opacity-30" />

      <section className="relative mx-auto flex min-h-screen max-w-7xl flex-col px-4 py-6 sm:px-6 lg:px-8">
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

        <div className="grid flex-1 items-center gap-8 py-10 lg:grid-cols-[0.95fr_1.05fr]">
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
            </div>
          </div>

          <div className="relative">
            <div className="rounded-lg border border-cyan-300/20 bg-slate-950/80 p-5 shadow-2xl shadow-cyan-950/40 backdrop-blur">
              <div className="mb-5 flex items-center justify-between border-b border-white/10 pb-4">
                <div>
                  <p className="text-xs uppercase tracking-[0.22em] text-neutral-500">
                    Core access
                  </p>
                  <h3 className="mt-1 text-lg font-semibold">
                    Module Directory
                  </h3>
                </div>
                <div className="h-3 w-3 rounded-full bg-cyan-300 shadow-[0_0_24px_rgba(103,232,249,0.9)]" />
              </div>

              <div className="mb-5 grid place-items-center rounded-lg border border-cyan-300/15 bg-cyan-300/5 p-8">
                <div className="grid h-44 w-44 place-items-center rounded-full border border-cyan-300/30 bg-slate-950 shadow-[inset_0_0_50px_rgba(34,211,238,0.14)]">
                  <div className="grid h-28 w-28 place-items-center rounded-full border border-emerald-300/30 bg-emerald-300/10">
                    <span className="text-2xl font-semibold tracking-[0.16em] text-cyan-100">
                      HX
                    </span>
                  </div>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                {modules.map((module) => (
                  <Link
                    key={module.href}
                    href={module.href}
                    className="group rounded-lg border border-white/10 bg-white/[0.04] p-4 transition hover:border-cyan-300/50 hover:bg-cyan-300/10"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <h4 className="text-sm font-semibold text-white">
                        {module.name}
                      </h4>
                      <span
                        className={`rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-wide ${
                          module.status === "Live"
                            ? "border-emerald-300/30 bg-emerald-300/10 text-emerald-200"
                            : "border-amber-300/30 bg-amber-300/10 text-amber-200"
                        }`}
                      >
                        {module.status}
                      </span>
                    </div>
                    <p className="mt-3 text-sm leading-6 text-neutral-400 group-hover:text-neutral-200">
                      {module.description}
                    </p>
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
