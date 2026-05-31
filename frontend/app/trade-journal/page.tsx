import Link from "next/link";

export const dynamic = "force-dynamic";

const TRADE_SESSIONS_URL = "http://127.0.0.1:8000/orbit/trade-sessions";

type TradeSession = {
  id: number;
  session_date: string;
  symbol: string;
  pnl: number;
  notes: string | null;
  rule_adherence: number | null;
  confidence: number | null;
  session_grade: string | null;
  created_at: string;
  updated_at: string;
};

async function fetchTradeSessions() {
  const response = await fetch(TRADE_SESSIONS_URL, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Trade Journal API returned ${response.status}.`);
  }

  return response.json() as Promise<TradeSession[]>;
}

function formatDate(value: string) {
  const date = new Date(`${value}T00:00:00Z`);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}

function formatPnl(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

function formatAverage(value: number | null, suffix = "") {
  if (value === null) {
    return "--";
  }

  return `${Math.round(value * 10) / 10}${suffix}`;
}

function getAverage(values: Array<number | null>) {
  const validValues = values.filter(
    (value): value is number => typeof value === "number",
  );

  if (validValues.length === 0) {
    return null;
  }

  return (
    validValues.reduce((sum, value) => sum + value, 0) / validValues.length
  );
}

function getPnlClass(value: number) {
  if (value > 0) {
    return "text-emerald-300";
  }

  if (value < 0) {
    return "text-red-300";
  }

  return "text-neutral-200";
}

function StatCard({
  label,
  value,
  valueClassName = "text-white",
}: Readonly<{
  label: string;
  value: string;
  valueClassName?: string;
}>) {
  return (
    <article className="rounded-lg border border-white/10 bg-neutral-900 p-4">
      <p className="text-xs text-neutral-500">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${valueClassName}`}>
        {value}
      </p>
    </article>
  );
}

function ErrorPanel({ message }: { message: string }) {
  return (
    <section className="rounded-lg border border-red-500/30 bg-red-950/20 p-6">
      <p className="text-sm text-red-200/80">Trade Journal unavailable</p>
      <h2 className="mt-2 text-xl font-semibold text-white">
        Unable to load trade sessions.
      </h2>
      <p className="mt-2 text-sm text-red-100/80">{message}</p>
    </section>
  );
}

function EmptyState() {
  return (
    <section className="rounded-lg border border-white/10 bg-neutral-900 p-6">
      <p className="text-sm font-semibold text-neutral-100">
        No trade sessions yet.
      </p>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-neutral-400">
        Logged sessions will appear here with PnL, rule adherence, confidence,
        grades, and notes once Helix records them.
      </p>
    </section>
  );
}

export default async function TradeJournalPage() {
  let tradeSessions: TradeSession[] = [];
  let errorMessage: string | null = null;

  try {
    tradeSessions = await fetchTradeSessions();
  } catch (error) {
    errorMessage =
      error instanceof Error
        ? error.message
        : "Trade sessions could not be loaded.";
  }

  const totalPnl = tradeSessions.reduce(
    (sum, session) => sum + session.pnl,
    0,
  );
  const averageRuleAdherence = getAverage(
    tradeSessions.map((session) => session.rule_adherence),
  );
  const averageConfidence = getAverage(
    tradeSessions.map((session) => session.confidence),
  );

  return (
    <main className="min-h-screen bg-neutral-950 text-white">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-neutral-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-col gap-4 px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-cyan-300">
              Helix Module
            </p>
            <h1 className="text-lg font-semibold">Trade Journal</h1>
          </div>

          <nav className="flex flex-wrap items-center gap-2">
            <Link
              href="/"
              className="rounded-lg border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Core
            </Link>
            <Link
              href="/command-center"
              className="rounded-lg border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Command Center
            </Link>
            <Link
              href="/orbit"
              className="rounded-lg border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Orbit
            </Link>
          </nav>
        </div>
      </header>

      <div className="mx-auto max-w-7xl space-y-4 px-4 py-4">
        <section className="rounded-lg border border-cyan-300/20 bg-cyan-300/5 p-6">
          <p className="text-sm text-cyan-200/80">
            Session-level trading memory
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight">
            Trade Journal
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-6 text-neutral-300">
            Review recent trading sessions, track rule adherence and
            confidence, and keep performance details separate from Orbit&apos;s
            mission planning dashboard.
          </p>
        </section>

        {errorMessage ? (
          <ErrorPanel message={errorMessage} />
        ) : (
          <>
            <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              <StatCard
                label="Total sessions"
                value={tradeSessions.length.toString()}
              />
              <StatCard
                label="Total PnL"
                value={formatPnl(totalPnl)}
                valueClassName={getPnlClass(totalPnl)}
              />
              <StatCard
                label="Average rule adherence"
                value={formatAverage(averageRuleAdherence, "%")}
              />
              <StatCard
                label="Average confidence"
                value={formatAverage(averageConfidence, " / 10")}
              />
            </section>

            <section className="rounded-lg border border-white/10 bg-neutral-900 p-5">
              <div className="mb-4 flex items-center justify-between gap-3">
                <div>
                  <h2 className="text-sm font-semibold text-neutral-100">
                    Recent Trade Sessions
                  </h2>
                  <p className="mt-1 text-xs text-neutral-500">
                    Latest logged sessions from Orbit trade session storage.
                  </p>
                </div>
              </div>

              {tradeSessions.length > 0 ? (
                <div className="grid gap-3 lg:grid-cols-2">
                  {tradeSessions.map((session) => (
                    <article
                      key={session.id}
                      className="rounded-lg border border-white/10 bg-neutral-950 p-4"
                    >
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <p className="text-xs text-neutral-500">
                            {formatDate(session.session_date)}
                          </p>
                          <h3 className="mt-1 text-lg font-semibold text-white">
                            {session.symbol}
                          </h3>
                        </div>

                        <div className="sm:text-right">
                          <p
                            className={`text-lg font-semibold ${getPnlClass(
                              session.pnl,
                            )}`}
                          >
                            {formatPnl(session.pnl)}
                          </p>
                          <p className="mt-1 text-xs text-neutral-500">
                            Grade {session.session_grade ?? "--"}
                          </p>
                        </div>
                      </div>

                      <div className="mt-4 grid gap-2 sm:grid-cols-2">
                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                          <p className="text-xs text-neutral-500">
                            Rule adherence
                          </p>
                          <p className="mt-1 text-sm font-semibold text-neutral-100">
                            {session.rule_adherence === null
                              ? "--"
                              : `${session.rule_adherence}%`}
                          </p>
                        </div>

                        <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3">
                          <p className="text-xs text-neutral-500">
                            Confidence
                          </p>
                          <p className="mt-1 text-sm font-semibold text-neutral-100">
                            {session.confidence === null
                              ? "--"
                              : `${session.confidence} / 10`}
                          </p>
                        </div>
                      </div>

                      {session.notes ? (
                        <p className="mt-4 text-sm leading-6 text-neutral-400">
                          {session.notes}
                        </p>
                      ) : null}
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyState />
              )}
            </section>
          </>
        )}
      </div>
    </main>
  );
}
