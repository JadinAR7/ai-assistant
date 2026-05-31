import Link from "next/link";

export default function AscendPage() {
  return (
    <main className="min-h-screen bg-neutral-950 px-4 py-6 text-white">
      <div className="mx-auto max-w-4xl">
        <header className="mb-8 flex items-center justify-between border-b border-white/10 pb-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300">
              Helix Module
            </p>
            <h1 className="mt-2 text-3xl font-semibold">Ascend</h1>
          </div>

          <Link
            href="/"
            className="rounded-lg border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
          >
            Core
          </Link>
        </header>

        <section className="rounded-lg border border-amber-300/25 bg-amber-300/10 p-6">
          <p className="text-sm font-semibold uppercase tracking-[0.2em] text-amber-200">
            Coming soon
          </p>
          <p className="mt-3 text-neutral-200">
            Ascend is coming soon. This module will hold long-term goals,
            training arcs, readiness systems, and progress tracking.
          </p>
        </section>
      </div>
    </main>
  );
}
