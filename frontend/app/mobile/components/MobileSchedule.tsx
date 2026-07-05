import {
  MobileCard,
  MobilePrimaryButton,
} from "./MobileCard";
import { type ScheduleBlock } from "../lib/mobileTypes";
import { getBlockTime, getBlockTitle } from "../lib/mobileUtils";

export default function MobileSchedule({
  blocks,
  onStartPrompt,
}: Readonly<{
  blocks: ScheduleBlock[];
  onStartPrompt: (prompt: string) => void;
}>) {
  return (
    <>
      <MobileCard>
        <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
          Today
        </p>
        <h2 className="mt-1 text-lg font-semibold">Schedule</h2>
        <div className="mt-3 grid gap-2">
          {blocks.length ? (
            blocks.map((block) => (
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
            ))
          ) : (
            <p className="rounded-xl border border-dashed border-white/10 px-3 py-4 text-sm text-neutral-500">
              Today&apos;s schedule will appear here.
            </p>
          )}
        </div>
      </MobileCard>
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
