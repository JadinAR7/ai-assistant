import {
  MobileCard,
  MobilePrimaryButton,
  MobileSecondaryButton,
} from "./MobileCard";
import { type MobileActionResult, type ScheduleBlock } from "../lib/mobileTypes";
import {
  getBlockTime,
  getBlockTitle,
  splitPlacedAndWaitingBlocks,
} from "../lib/mobileUtils";

export default function MobileSchedule({
  blocks,
  actionLoading,
  actionResult,
  onDone,
  onRollLater,
  onRollTomorrow,
  onStartPrompt,
}: Readonly<{
  blocks: ScheduleBlock[];
  actionLoading: string | null;
  actionResult: MobileActionResult | null;
  onDone: (id: number) => void;
  onRollLater: (id: number) => void;
  onRollTomorrow: (id: number) => void;
  onStartPrompt: (prompt: string) => void;
}>) {
  const { placed, waiting } = splitPlacedAndWaitingBlocks(blocks);
  const actionableBlock = placed[0] ?? null;

  return (
    <>
      <MobileCard>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Today
        </p>
        <h2 className="mt-1 text-lg font-semibold">Schedule</h2>
        <div className="mt-3 grid gap-2">
          {placed.length ? (
            placed.map((block) => (
              <ScheduleBlockRow
                key={block.id}
                block={block}
                showActions={actionableBlock?.id === block.id}
                actionLoading={actionLoading}
                onDone={onDone}
                onRollLater={onRollLater}
                onRollTomorrow={onRollTomorrow}
              />
            ))
          ) : (
            <p className="rounded-xl border border-dashed border-white/10 px-3 py-4 text-sm text-neutral-500">
              Today&apos;s schedule will appear here.
            </p>
          )}
        </div>

        {waiting.length ? (
          <div className="mt-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
              Waiting to be placed
            </p>
            <div className="mt-3 grid gap-2">
              {waiting.map((block) => (
                <div
                  key={block.id}
                  className="rounded-xl border border-white/10 bg-black/25 p-3"
                >
                  <p className="text-sm font-semibold text-neutral-100">
                    {getBlockTitle(block)}
                  </p>
                  <p className="mt-1 text-xs text-neutral-500">
                    {getBlockTime(block)}
                  </p>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </MobileCard>
      {actionResult ? (
        <MobileCard
          className={
            actionResult.error
              ? "border-amber-300/25 bg-amber-300/10"
              : "border-emerald-300/25 bg-emerald-300/10"
          }
        >
          <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
            {actionResult.title}
          </p>
          <p className="mt-2 text-sm leading-6 text-neutral-100">
            {actionResult.message}
          </p>
        </MobileCard>
      ) : null}
      <MobileCard>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Fast Scheduling
        </p>
        <p className="mt-2 text-sm leading-6 text-neutral-300">
          Try: &quot;Add 30 minutes of reading whenever I&apos;m free today.&quot;
        </p>
        <div className="mt-4 grid gap-2">
          <MobilePrimaryButton
            onClick={() =>
              onStartPrompt(
                "Add 30 minutes of reading whenever I am free today.",
              )
            }
          >
            Add Flexible Block
          </MobilePrimaryButton>
        </div>
      </MobileCard>
    </>
  );
}

function ScheduleBlockRow({
  block,
  showActions,
  actionLoading,
  onDone,
  onRollLater,
  onRollTomorrow,
}: Readonly<{
  block: ScheduleBlock;
  showActions: boolean;
  actionLoading: string | null;
  onDone: (id: number) => void;
  onRollLater: (id: number) => void;
  onRollTomorrow: (id: number) => void;
}>) {
  const doneKey = `schedule-done-${block.id}`;
  const laterKey = `schedule-roll-later-${block.id}`;
  const tomorrowKey = `schedule-roll-tomorrow-${block.id}`;

  return (
    <div className="rounded-xl border border-white/10 bg-black/25 p-3">
      <p className="text-sm font-semibold text-neutral-100">
        {getBlockTitle(block)}
      </p>
      <p className="mt-1 text-xs text-neutral-500">{getBlockTime(block)}</p>
      {showActions ? (
        <div className="mt-3 grid grid-cols-3 gap-2">
          <MobilePrimaryButton
            onClick={() => onDone(block.id)}
            disabled={Boolean(actionLoading)}
          >
            {actionLoading === doneKey ? "Saving..." : "Done"}
          </MobilePrimaryButton>
          <MobileSecondaryButton
            onClick={() => onRollLater(block.id)}
            disabled={Boolean(actionLoading)}
          >
            {actionLoading === laterKey ? "Rolling..." : "Roll later"}
          </MobileSecondaryButton>
          <MobileSecondaryButton
            onClick={() => onRollTomorrow(block.id)}
            disabled={Boolean(actionLoading)}
          >
            {actionLoading === tomorrowKey ? "Moving..." : "Tomorrow"}
          </MobileSecondaryButton>
        </div>
      ) : null}
    </div>
  );
}
