import Link from "next/link";

export const dynamic = "force-dynamic";

const CORPORATE_ESCAPE_TITLE = "Corporate Escape";
const MAJOR_EVENTS_URL = "http://127.0.0.1:8000/orbit/major-events";
const MILESTONES_URL = "http://127.0.0.1:8000/orbit/milestones";
const TASKS_URL = "http://127.0.0.1:8000/orbit/tasks";
const REVIEWS_URL = "http://127.0.0.1:8000/orbit/reviews";

type MajorEvent = {
  id: number;
  title: string;
  description: string | null;
  target_date: string | null;
  status: string;
  progress_percent: number;
};

type Milestone = {
  id: number;
  major_event_id: number;
  title: string;
  description: string | null;
  status: string;
  progress_percent: number;
  target_value: number | null;
  current_value: number | null;
  due_date: string | null;
};

type OrbitTask = {
  id: number;
  goal_id: number;
  title: string;
  description: string | null;
  status: string;
  due_date: string | null;
  completed_at: string | null;
};

type OrbitReview = {
  id: number | string;
  title?: string | null;
  review_type: string;
  summary?: string | null;
  rating?: number | string | null;
  created_at?: string | null;
};

const blockers = [
  "Income replacement target needs a final number.",
  "Trading metrics are not connected to Orbit yet.",
  "Business launch path needs a concrete first offer.",
];

const weeklyFocus = [
  "Document the exact corporate exit criteria.",
  "Review the last five trading sessions for repeatable edge.",
  "Choose one business experiment to validate this week.",
  "Create a simple readiness score rubric.",
];

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Orbit API returned ${response.status} for ${url}`);
  }

  return response.json() as Promise<T>;
}

async function getOrbitData() {
  const [majorEvents, milestones, tasks, reviewsResult] = await Promise.all([
    fetchJson<MajorEvent[]>(MAJOR_EVENTS_URL),
    fetchJson<Milestone[]>(MILESTONES_URL),
    fetchJson<OrbitTask[]>(TASKS_URL),
    fetchJson<OrbitReview[]>(REVIEWS_URL)
      .then((reviews) => ({ reviews, error: null }))
      .catch((error: unknown) => ({
        reviews: [],
        error:
          error instanceof Error
            ? error.message
            : "Orbit reviews could not be loaded.",
      })),
  ]);

  const event = majorEvents.find(
    (majorEvent) => majorEvent.title === CORPORATE_ESCAPE_TITLE,
  );

  return {
    event,
    milestones: event
      ? milestones.filter((milestone) => milestone.major_event_id === event.id)
      : [],
    reviews: getLatestReviews(reviewsResult.reviews),
    reviewsError: reviewsResult.error,
    tasks,
  };
}

function getLatestReviews(reviews: OrbitReview[]) {
  return reviews
    .map((review, index) => ({ review, index }))
    .sort((left, right) => {
      const leftTime = left.review.created_at
        ? new Date(left.review.created_at).getTime()
        : Number.NaN;
      const rightTime = right.review.created_at
        ? new Date(right.review.created_at).getTime()
        : Number.NaN;

      if (Number.isNaN(leftTime) && Number.isNaN(rightTime)) {
        return left.index - right.index;
      }

      if (Number.isNaN(leftTime)) {
        return 1;
      }

      if (Number.isNaN(rightTime)) {
        return -1;
      }

      return rightTime - leftTime;
    })
    .slice(0, 3)
    .map(({ review }) => review);
}

function formatDate(value: string | null) {
  if (!value) {
    return "No target date set";
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(value));
}

function formatDateTime(value: string) {
  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function formatStatus(value: string) {
  return value
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function getDaysRemaining(targetDate: string | null) {
  if (!targetDate) {
    return null;
  }

  const target = new Date(`${targetDate}T00:00:00Z`).getTime();
  const now = Date.now();
  const days = Math.ceil((target - now) / (1000 * 60 * 60 * 24));

  return Math.max(days, 0);
}

function ProgressBar({ value }: { value: number }) {
  const clampedValue = Math.min(Math.max(value, 0), 100);

  return (
    <div className="h-3 overflow-hidden rounded-full bg-neutral-800">
      <div
        className="h-full rounded-full bg-blue-500"
        style={{ width: `${clampedValue}%` }}
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

function OrbitError({ message }: { message: string }) {
  return (
    <section className="rounded-2xl border border-red-500/30 bg-red-950/20 p-6">
      <p className="mb-2 text-sm text-red-200/80">Orbit API unavailable</p>
      <h2 className="text-xl font-semibold text-white">
        Unable to load Corporate Escape data.
      </h2>
      <p className="mt-2 text-sm text-red-100/80">{message}</p>
    </section>
  );
}

export default async function OrbitPage() {
  let orbitData: Awaited<ReturnType<typeof getOrbitData>>;
  let errorMessage: string | null = null;

  try {
    orbitData = await getOrbitData();
  } catch (error) {
    orbitData = {
      event: undefined,
      milestones: [],
      reviews: [],
      reviewsError: null,
      tasks: [],
    };
    errorMessage =
      error instanceof Error
        ? error.message
        : "Orbit data could not be loaded.";
  }

  const event = orbitData.event;
  const daysRemaining = getDaysRemaining(event?.target_date ?? null);
  const progressPercentage = event?.progress_percent ?? 0;

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

          <div className="flex items-center gap-2">
            <Link
              href="/"
              className="rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Core
            </Link>

            <Link
              href="/command-center"
              className="rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Command Center
            </Link>
          </div>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl grid-cols-1 gap-4 px-4 py-4 lg:grid-cols-[1.35fr_0.65fr]">
        {errorMessage ? (
          <OrbitError message={errorMessage} />
        ) : (
          <section className="rounded-2xl border border-blue-500/30 bg-blue-950/20 p-6">
            <div className="mb-8 flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="mb-2 text-sm text-blue-200/70">
                  Major Event Countdown
                </p>
                <h2 className="text-3xl font-semibold tracking-tight text-white">
                  {event?.title ?? CORPORATE_ESCAPE_TITLE}
                </h2>
                <p className="mt-2 text-sm text-neutral-400">
                  {event
                    ? `Target date: ${formatDate(event.target_date)}`
                    : "Corporate Escape has not been added to Orbit yet."}
                </p>
              </div>

              <div className="rounded-2xl border border-white/10 bg-neutral-950/70 px-5 py-4 text-right">
                <p className="text-xs text-neutral-500">Days remaining</p>
                <p className="mt-1 text-4xl font-semibold text-white">
                  {daysRemaining ?? "--"}
                </p>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-[1fr_220px]">
              <div className="rounded-2xl border border-white/10 bg-neutral-950 p-4">
                <div className="mb-3 flex items-center justify-between text-sm">
                  <span className="text-neutral-400">Progress</span>
                  <span className="font-semibold text-blue-200">
                    {progressPercentage}%
                  </span>
                </div>
                <ProgressBar value={progressPercentage} />
              </div>

              <div className="rounded-2xl border border-white/10 bg-neutral-950 p-4">
                <p className="text-xs text-neutral-500">Current status</p>
                <p className="mt-2 text-sm font-semibold text-neutral-100">
                  {event ? formatStatus(event.status) : "Not connected"}
                </p>
                <p className="mt-1 text-xs text-neutral-400">
                  {event?.description ?? "Waiting for Orbit event data."}
                </p>
              </div>
            </div>
          </section>
        )}

        <Panel title="This Week's Focus">
          <ul className="space-y-3 text-sm text-neutral-300">
            {weeklyFocus.map((item) => (
              <li
                key={item}
                className="rounded-xl border border-white/10 bg-neutral-950 p-3"
              >
                {item}
              </li>
            ))}
          </ul>
        </Panel>

        <Panel title="Inbox Tasks">
          {orbitData.tasks.length > 0 ? (
            <div className="grid gap-3 md:grid-cols-2">
              {orbitData.tasks.map((task) => (
                <article
                  key={task.id}
                  className="rounded-xl border border-white/10 bg-neutral-950 p-4"
                >
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <h3 className="text-sm font-semibold text-neutral-100">
                      {task.title}
                    </h3>
                    <span className="shrink-0 rounded-full border border-blue-500/20 bg-blue-500/15 px-2 py-1 text-xs text-blue-200">
                      {formatStatus(task.status)}
                    </span>
                  </div>
                  {task.due_date ? (
                    <p className="text-xs text-neutral-400">
                      Due {formatDate(task.due_date)}
                    </p>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-white/10 bg-neutral-950 p-4 text-sm text-neutral-400">
              No inbox tasks have been added to Orbit yet.
            </div>
          )}
        </Panel>

        <Panel title="Reviews">
          {orbitData.reviews.length > 0 ? (
            <div className="grid gap-3 md:grid-cols-2">
              {orbitData.reviews.map((review) => (
                <article
                  key={review.id}
                  className="rounded-xl border border-white/10 bg-neutral-950 p-4"
                >
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <h3 className="text-sm font-semibold text-neutral-100">
                      {review.title ?? formatStatus(review.review_type)}
                    </h3>
                    <span className="shrink-0 rounded-full border border-blue-500/20 bg-blue-500/15 px-2 py-1 text-xs text-blue-200">
                      {formatStatus(review.review_type)}
                    </span>
                  </div>
                  {review.summary ? (
                    <p className="text-sm text-neutral-400">
                      {review.summary}
                    </p>
                  ) : null}
                  {(review.rating !== null &&
                    review.rating !== undefined) ||
                  review.created_at ? (
                    <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-neutral-500">
                      {review.rating !== null &&
                      review.rating !== undefined ? (
                        <span>Rating {review.rating}</span>
                      ) : null}
                      {review.created_at ? (
                        <span>{formatDateTime(review.created_at)}</span>
                      ) : null}
                    </div>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-white/10 bg-neutral-950 p-4 text-sm text-neutral-400">
              {orbitData.reviewsError
                ? "Reviews are unavailable right now."
                : "No reviews saved yet."}
            </div>
          )}
        </Panel>

        <Panel title="Milestones">
          {orbitData.milestones.length > 0 ? (
            <div className="grid gap-3 md:grid-cols-2">
              {orbitData.milestones.map((milestone) => (
                <article
                  key={milestone.id}
                  className="rounded-xl border border-white/10 bg-neutral-950 p-4"
                >
                  <div className="mb-3 flex items-start justify-between gap-3">
                    <h3 className="text-sm font-semibold text-neutral-100">
                      {milestone.title}
                    </h3>
                    <span className="shrink-0 rounded-full border border-blue-500/20 bg-blue-500/15 px-2 py-1 text-xs text-blue-200">
                      {formatStatus(milestone.status)}
                    </span>
                  </div>
                  <p className="text-sm text-neutral-400">
                    {milestone.description ?? "No milestone detail added yet."}
                  </p>
                </article>
              ))}
            </div>
          ) : (
            <div className="rounded-xl border border-white/10 bg-neutral-950 p-4 text-sm text-neutral-400">
              {event
                ? "No milestones are linked to Corporate Escape yet."
                : "Milestones will appear once the Corporate Escape event is available."}
            </div>
          )}
        </Panel>

        <Panel title="Blockers">
          <ul className="space-y-3 text-sm text-neutral-300">
            {blockers.map((blocker) => (
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
