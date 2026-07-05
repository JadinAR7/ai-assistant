import { useState } from "react";

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
  onStart,
  onDone,
  onPause,
  onResume,
  onExtend,
  onRollLater,
  onRollTomorrow,
  onSwap,
  onStartPrompt,
}: Readonly<{
  blocks: ScheduleBlock[];
  actionLoading: string | null;
  actionResult: MobileActionResult | null;
  onStart: (id: number) => void;
  onDone: (id: number) => void;
  onPause: (id: number) => void;
  onResume: (id: number) => void;
  onExtend: (id: number, minutes?: number) => void;
  onRollLater: (id: number) => void;
  onRollTomorrow: (id: number) => void;
  onSwap: (id: number, withBlockId: number) => void;
  onStartPrompt: (prompt: string) => void;
}>) {
  const { placed, waiting } = splitPlacedAndWaitingBlocks(blocks);
  const actionableBlock = placed[0] ?? null;
  const [swapOpenForId, setSwapOpenForId] = useState<number | null>(null);

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
                onStart={onStart}
                onDone={onDone}
                onPause={onPause}
                onResume={onResume}
                onExtend={onExtend}
                onRollLater={onRollLater}
                onRollTomorrow={onRollTomorrow}
                onSwap={onSwap}
                swapCandidates={placed.filter((candidate) => candidate.id !== block.id)}
                swapOpen={swapOpenForId === block.id}
                onToggleSwap={() =>
                  setSwapOpenForId((current) =>
                    current === block.id ? null : block.id,
                  )
                }
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
  onStart,
  onDone,
  onPause,
  onResume,
  onExtend,
  onRollLater,
  onRollTomorrow,
  onSwap,
  swapCandidates,
  swapOpen,
  onToggleSwap,
}: Readonly<{
  block: ScheduleBlock;
  showActions: boolean;
  actionLoading: string | null;
  onStart: (id: number) => void;
  onDone: (id: number) => void;
  onPause: (id: number) => void;
  onResume: (id: number) => void;
  onExtend: (id: number, minutes?: number) => void;
  onRollLater: (id: number) => void;
  onRollTomorrow: (id: number) => void;
  onSwap: (id: number, withBlockId: number) => void;
  swapCandidates: ScheduleBlock[];
  swapOpen: boolean;
  onToggleSwap: () => void;
}>) {
  const doneKey = `schedule-done-${block.id}`;
  const startKey = `schedule-start-${block.id}`;
  const pauseKey = `schedule-pause-${block.id}`;
  const resumeKey = `schedule-resume-${block.id}`;
  const extendKey = `schedule-extend-${block.id}`;
  const laterKey = `schedule-roll-later-${block.id}`;
  const tomorrowKey = `schedule-roll-tomorrow-${block.id}`;
  const swapKey = `schedule-swap-${block.id}`;
  const lifecycle = block.lifecycle_status || block.status || "upcoming";
  const isActive = lifecycle === "active";
  const isPaused = lifecycle === "paused";
  const isDone = lifecycle === "done";
  const isDue = lifecycle === "due_now";

  return (
    <div className="rounded-xl border border-white/10 bg-black/25 p-3">
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-semibold text-neutral-100">
          {getBlockTitle(block)}
        </p>
        <span className="shrink-0 rounded-full border border-white/10 bg-white/[0.04] px-2 py-1 text-[11px] font-semibold text-neutral-400">
          {lifecycle.replaceAll("_", " ")}
        </span>
      </div>
      <p className="mt-1 text-xs text-neutral-500">{getBlockTime(block)}</p>
      {showActions && !isDone ? (
        <div className="mt-3 grid grid-cols-2 gap-2">
          {isActive ? (
            <MobilePrimaryButton
              onClick={() => onDone(block.id)}
              disabled={Boolean(actionLoading)}
            >
              {actionLoading === doneKey ? "Saving..." : "Done"}
            </MobilePrimaryButton>
          ) : isPaused ? (
            <MobilePrimaryButton
              onClick={() => onResume(block.id)}
              disabled={Boolean(actionLoading)}
            >
              {actionLoading === resumeKey ? "Resuming..." : "Resume"}
            </MobilePrimaryButton>
          ) : (
            <MobilePrimaryButton
              onClick={() => onStart(block.id)}
              disabled={Boolean(actionLoading)}
            >
              {actionLoading === startKey
                ? "Checking in..."
                : isDue
                  ? "Start / Check-in"
                  : "Start early"}
            </MobilePrimaryButton>
          )}
          {isActive ? (
            <MobileSecondaryButton
              onClick={() => onPause(block.id)}
              disabled={Boolean(actionLoading)}
            >
              {actionLoading === pauseKey ? "Pausing..." : "Pause"}
            </MobileSecondaryButton>
          ) : isPaused ? (
            <MobileSecondaryButton
              onClick={() => onDone(block.id)}
              disabled={Boolean(actionLoading)}
            >
              {actionLoading === doneKey ? "Saving..." : "Done"}
            </MobileSecondaryButton>
          ) : (
            <MobileSecondaryButton
              onClick={() => onRollLater(block.id)}
              disabled={Boolean(actionLoading)}
            >
              {actionLoading === laterKey || actionLoading === tomorrowKey
                ? "Rolling..."
                : "Roll"}
            </MobileSecondaryButton>
          )}
          {isActive ? (
            <MobileSecondaryButton
              onClick={() => onExtend(block.id, 15)}
              disabled={Boolean(actionLoading)}
            >
              {actionLoading === extendKey ? "Extending..." : "Extend +15"}
            </MobileSecondaryButton>
          ) : null}
          {(isActive || isPaused) ? (
            <MobileSecondaryButton
              onClick={() => onRollLater(block.id)}
              disabled={Boolean(actionLoading)}
            >
              {actionLoading === laterKey || actionLoading === tomorrowKey
                ? "Rolling..."
                : "Roll"}
            </MobileSecondaryButton>
          ) : null}
          <div className="col-span-2 grid grid-cols-2 gap-2">
            <MobileSecondaryButton
              onClick={() => onRollTomorrow(block.id)}
              disabled={Boolean(actionLoading)}
            >
              {actionLoading === tomorrowKey ? "Moving..." : "Tomorrow"}
            </MobileSecondaryButton>
            <MobileSecondaryButton
              onClick={onToggleSwap}
              disabled={Boolean(actionLoading) || swapCandidates.length === 0}
            >
              {actionLoading === swapKey ? "Swapping..." : "Swap"}
            </MobileSecondaryButton>
          </div>
          {swapOpen ? (
            <div className="col-span-2 grid gap-2 rounded-xl border border-white/10 bg-white/[0.03] p-2">
              {swapCandidates.map((candidate) => (
                <button
                  key={candidate.id}
                  type="button"
                  onClick={() => onSwap(block.id, candidate.id)}
                  disabled={Boolean(actionLoading)}
                  className="min-h-10 rounded-lg border border-white/10 bg-black/20 px-3 text-left text-xs font-semibold text-neutral-100 disabled:opacity-50"
                >
                  {getBlockTitle(candidate)} · {getBlockTime(candidate)}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      ) : showActions && isDone ? (
        <p className="mt-3 rounded-xl border border-emerald-300/20 bg-emerald-300/10 px-3 py-2 text-xs font-semibold text-emerald-100">
          Completed
        </p>
      ) : null}
    </div>
  );
}
