import Link from "next/link";
import OrbitBoard, {
  type AgentDefinition,
  type AgentPrioritizationResult,
  type DailyCloseout,
  type MajorEvent,
  type Milestone,
  type MilestoneProgressAdvisory,
  type MilestoneProgressHistory,
  type MorningCheckInStatus,
  type MorningBriefing,
  type OrbitReview,
  type ReadinessCategory,
  type RecommendationSet,
  type ScheduleBlock,
  type ScheduledAgentStatus,
} from "./OrbitBoard";
import { type InboxTask } from "./InboxTaskControls";

export const dynamic = "force-dynamic";

const MAJOR_EVENTS_URL = "http://127.0.0.1:8000/orbit/major-events";
const MILESTONES_URL = "http://127.0.0.1:8000/orbit/milestones";
const MILESTONE_ADVISORIES_URL =
  "http://127.0.0.1:8000/orbit/milestones/progress-advisory";
const RECENT_PROGRESS_HISTORY_URL =
  "http://127.0.0.1:8000/orbit/progress-history/recent";
const REVIEWS_URL = "http://127.0.0.1:8000/orbit/reviews";
const READINESS_URL = "http://127.0.0.1:8000/orbit/readiness";
const MORNING_BRIEFING_URL = "http://127.0.0.1:8000/orbit/morning-briefing";
const DAILY_CLOSEOUT_URL = "http://127.0.0.1:8000/orbit/daily-closeout";
const RECOMMENDATIONS_URL = "http://127.0.0.1:8000/orbit/recommendations";
const INBOX_TASKS_URL = "http://127.0.0.1:8000/orbit/inbox-tasks";
const SCHEDULE_BLOCKS_URL = "http://127.0.0.1:8000/orbit/schedule-blocks";
const AGENTS_URL = "http://127.0.0.1:8000/agents";
const AGENT_PRIORITIZATION_URL = "http://127.0.0.1:8000/agents/prioritize";
const SCHEDULED_AGENTS_STATUS_URL =
  "http://127.0.0.1:8000/agents/scheduled/status";
const MORNING_CHECKIN_STATUS_URL =
  "http://127.0.0.1:8000/agents/morning/status";

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url, { cache: "no-store" });

  if (!response.ok) {
    throw new Error(`Orbit API returned ${response.status} for ${url}`);
  }

  return response.json() as Promise<T>;
}

async function getOrbitData() {
  const [
    majorEvents,
    milestones,
    reviewsResult,
    readinessResult,
    briefingResult,
    dailyCloseoutResult,
    recommendationsResult,
    inboxTasksResult,
    milestoneAdvisoriesResult,
    progressHistoryResult,
    agentsResult,
    agentPrioritizationResult,
    scheduledAgentsStatusResult,
    morningCheckInStatusResult,
    scheduleBlocksResult,
  ] = await Promise.all([
    fetchJson<MajorEvent[]>(MAJOR_EVENTS_URL),
    fetchJson<Milestone[]>(MILESTONES_URL),
    fetchJson<OrbitReview[]>(REVIEWS_URL)
      .then((reviews) => ({ reviews, error: null }))
      .catch((error: unknown) => ({
        reviews: [],
        error:
          error instanceof Error
            ? error.message
            : "Orbit reviews could not be loaded.",
      })),
    fetchJson<ReadinessCategory[]>(READINESS_URL)
      .then((readiness) => ({ readiness, error: null }))
      .catch((error: unknown) => ({
        readiness: [],
        error:
          error instanceof Error
            ? error.message
            : "Orbit readiness could not be loaded.",
      })),
    fetchJson<MorningBriefing>(MORNING_BRIEFING_URL)
      .then((briefing) => ({ briefing, error: null }))
      .catch((error: unknown) => ({
        briefing: null,
        error:
          error instanceof Error
            ? error.message
            : "Orbit briefing could not be loaded.",
      })),
    fetchJson<DailyCloseout>(DAILY_CLOSEOUT_URL)
      .then((closeout) => ({ closeout, error: null }))
      .catch((error: unknown) => ({
        closeout: null,
        error:
          error instanceof Error
            ? error.message
            : "Orbit closeout could not be loaded.",
      })),
    fetchJson<RecommendationSet>(RECOMMENDATIONS_URL)
      .then((recommendations) => ({ recommendations, error: null }))
      .catch((error: unknown) => ({
        recommendations: null,
        error:
          error instanceof Error
            ? error.message
            : "Orbit recommendations could not be loaded.",
      })),
    fetchJson<InboxTask[]>(INBOX_TASKS_URL)
      .then((inboxTasks) => ({ inboxTasks, error: null }))
      .catch((error: unknown) => ({
        inboxTasks: [],
        error:
          error instanceof Error
            ? error.message
            : "Orbit inbox tasks could not be loaded.",
      })),
    fetchJson<MilestoneProgressAdvisory[]>(MILESTONE_ADVISORIES_URL)
      .then((advisories) => ({ advisories, error: null }))
      .catch(() => ({
        advisories: [],
        error: "Orbit milestone progress advisories could not be loaded.",
      })),
    fetchJson<MilestoneProgressHistory[]>(RECENT_PROGRESS_HISTORY_URL)
      .then((history) => ({ history, error: null }))
      .catch(() => ({
        history: [],
        error: "Orbit milestone progress history could not be loaded.",
      })),
    fetchJson<AgentDefinition[]>(AGENTS_URL)
      .then((agents) => ({ agents, error: null }))
      .catch((error: unknown) => ({
        agents: [],
        error:
          error instanceof Error
            ? error.message
            : "Orbit agents could not be loaded.",
      })),
    fetchJson<AgentPrioritizationResult>(AGENT_PRIORITIZATION_URL)
      .then((prioritization) => ({ prioritization, error: null }))
      .catch((error: unknown) => ({
        prioritization: null,
        error:
          error instanceof Error
            ? error.message
            : "Agent prioritization could not be loaded.",
      })),
    fetchJson<ScheduledAgentStatus>(SCHEDULED_AGENTS_STATUS_URL)
      .then((status) => ({ status, error: null }))
      .catch((error: unknown) => ({
        status: null,
        error:
          error instanceof Error
            ? error.message
            : "Scheduled agents status could not be loaded.",
      })),
    fetchJson<MorningCheckInStatus>(MORNING_CHECKIN_STATUS_URL)
      .then((status) => ({ status, error: null }))
      .catch((error: unknown) => ({
        status: null,
        error:
          error instanceof Error
            ? error.message
            : "Morning check-in status could not be loaded.",
      })),
    fetchJson<ScheduleBlock[]>(SCHEDULE_BLOCKS_URL)
      .then((scheduleBlocks) => ({ scheduleBlocks, error: null }))
      .catch((error: unknown) => ({
        scheduleBlocks: [],
        error:
          error instanceof Error
            ? error.message
            : "Schedule blocks could not be loaded.",
      })),
  ]);

  const event = getPrimaryMajorEvent(majorEvents);
  const milestoneTasksById = await getMilestoneTasksById(milestones);
  const milestoneAdvisoriesById = Object.fromEntries(
    milestoneAdvisoriesResult.advisories.map((advisory) => [
      advisory.milestone_id,
      advisory,
    ]),
  ) as Record<number, MilestoneProgressAdvisory>;
  const latestProgressHistoryByMilestoneId = progressHistoryResult.history
    .reduce<Record<number, MilestoneProgressHistory>>((latestById, history) => {
      if (!latestById[history.milestone_id]) {
        latestById[history.milestone_id] = history;
      }
      return latestById;
    }, {});

  return {
    majorEvents,
    event,
    milestones,
    reviews: getLatestReviews(reviewsResult.reviews),
    reviewsError: reviewsResult.error,
    readiness: readinessResult.readiness,
    readinessError: readinessResult.error,
    morningBriefing: briefingResult.briefing,
    morningBriefingError: briefingResult.error,
    dailyCloseout: dailyCloseoutResult.closeout,
    dailyCloseoutError: dailyCloseoutResult.error,
    recommendations: recommendationsResult.recommendations,
    recommendationsError: recommendationsResult.error,
    inboxTasks: inboxTasksResult.inboxTasks,
    inboxTasksError: inboxTasksResult.error,
    milestoneTasksById,
    milestoneAdvisoriesById,
    latestProgressHistoryByMilestoneId,
    agents: agentsResult.agents,
    agentsError: agentsResult.error,
    agentPrioritization: agentPrioritizationResult.prioritization,
    agentPrioritizationError: agentPrioritizationResult.error,
    scheduledAgentsStatus: scheduledAgentsStatusResult.status,
    scheduledAgentsStatusError: scheduledAgentsStatusResult.error,
    morningCheckInStatus: morningCheckInStatusResult.status,
    morningCheckInStatusError: morningCheckInStatusResult.error,
    scheduleBlocks: scheduleBlocksResult.scheduleBlocks,
    scheduleBlocksError: scheduleBlocksResult.error,
  };
}

function getPrimaryMajorEvent(majorEvents: MajorEvent[]): MajorEvent | undefined {
  return (
    majorEvents.find((majorEvent) => majorEvent.status === "active") ??
    majorEvents.find((majorEvent) => majorEvent.status !== "archived") ??
    majorEvents[0]
  );
}

async function getMilestoneTasksById(milestones: Milestone[]) {
  const entries = await Promise.all(
    milestones.map(async (milestone) => {
      try {
        const tasks = await fetchJson<InboxTask[]>(
          `${MILESTONES_URL}/${milestone.id}/tasks`,
        );
        return [milestone.id, tasks] as const;
      } catch {
        return [milestone.id, []] as const;
      }
    }),
  );

  return Object.fromEntries(entries) as Record<number, InboxTask[]>;
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

export default async function OrbitPage() {
  let orbitData: Awaited<ReturnType<typeof getOrbitData>>;
  let errorMessage: string | null = null;

  try {
    orbitData = await getOrbitData();
  } catch (error) {
    orbitData = {
      majorEvents: [],
      event: undefined,
      milestones: [],
      reviews: [],
      reviewsError: null,
      readiness: [],
      readinessError: null,
      morningBriefing: null,
      morningBriefingError: null,
      dailyCloseout: null,
      dailyCloseoutError: null,
      recommendations: null,
      recommendationsError: null,
      inboxTasks: [],
      inboxTasksError: null,
      milestoneTasksById: {},
      milestoneAdvisoriesById: {},
      latestProgressHistoryByMilestoneId: {},
      agents: [],
      agentsError: null,
      agentPrioritization: null,
      agentPrioritizationError: null,
      scheduledAgentsStatus: null,
      scheduledAgentsStatusError: null,
      morningCheckInStatus: null,
      morningCheckInStatusError: null,
      scheduleBlocks: [],
      scheduleBlocksError: null,
    };
    errorMessage =
      error instanceof Error
        ? error.message
        : "Orbit data could not be loaded.";
  }

  return (
    <main className="min-h-screen bg-neutral-950 text-white">
      <header className="sticky top-0 z-20 border-b border-white/10 bg-neutral-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-cyan-300">
              Orbit
            </p>
            <h1 className="text-lg font-semibold">Operating Board</h1>
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

            <Link
              href="/trade-journal"
              className="rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
            >
              Trade Journal
            </Link>
          </div>
        </div>
      </header>

      <div className="mx-auto max-w-6xl px-4 py-4">
        <OrbitBoard
          majorEvents={orbitData.majorEvents}
          event={orbitData.event}
          milestones={orbitData.milestones}
          reviews={orbitData.reviews}
          reviewsError={orbitData.reviewsError}
          readiness={orbitData.readiness}
          readinessError={orbitData.readinessError}
          morningBriefing={orbitData.morningBriefing}
          morningBriefingError={orbitData.morningBriefingError}
          dailyCloseout={orbitData.dailyCloseout}
          dailyCloseoutError={orbitData.dailyCloseoutError}
          recommendations={orbitData.recommendations}
          recommendationsError={orbitData.recommendationsError}
          inboxTasks={orbitData.inboxTasks}
          inboxTasksError={orbitData.inboxTasksError}
          milestoneTasksById={orbitData.milestoneTasksById}
          milestoneAdvisoriesById={orbitData.milestoneAdvisoriesById}
          latestProgressHistoryByMilestoneId={
            orbitData.latestProgressHistoryByMilestoneId
          }
          agents={orbitData.agents}
          agentsError={orbitData.agentsError}
          agentPrioritization={orbitData.agentPrioritization}
          agentPrioritizationError={orbitData.agentPrioritizationError}
          scheduledAgentsStatus={orbitData.scheduledAgentsStatus}
          scheduledAgentsStatusError={orbitData.scheduledAgentsStatusError}
          morningCheckInStatus={orbitData.morningCheckInStatus}
          morningCheckInStatusError={orbitData.morningCheckInStatusError}
          scheduleBlocks={orbitData.scheduleBlocks}
          scheduleBlocksError={orbitData.scheduleBlocksError}
          errorMessage={errorMessage}
        />
      </div>
    </main>
  );
}
