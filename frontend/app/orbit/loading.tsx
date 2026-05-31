export default function OrbitLoading() {
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
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 px-4 py-4 lg:grid-cols-[1.35fr_0.65fr]">
        <section className="rounded-2xl border border-blue-500/30 bg-blue-950/20 p-6">
          <p className="mb-2 text-sm text-blue-200/70">
            Major Event Countdown
          </p>
          <div className="h-9 w-64 max-w-full animate-pulse rounded bg-neutral-800" />
          <div className="mt-4 h-4 w-48 animate-pulse rounded bg-neutral-800" />
          <div className="mt-8 h-20 animate-pulse rounded-2xl border border-white/10 bg-neutral-950" />
        </section>

        <section className="rounded-2xl border border-white/10 bg-neutral-900 p-5">
          <div className="mb-4 h-4 w-32 animate-pulse rounded bg-neutral-800" />
          <div className="space-y-3">
            <div className="h-11 animate-pulse rounded-xl border border-white/10 bg-neutral-950" />
            <div className="h-11 animate-pulse rounded-xl border border-white/10 bg-neutral-950" />
            <div className="h-11 animate-pulse rounded-xl border border-white/10 bg-neutral-950" />
          </div>
        </section>
      </div>
    </main>
  );
}
