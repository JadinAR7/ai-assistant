import { type FormEvent } from "react";

import {
  MobileCard,
  MobilePrimaryButton,
} from "./MobileCard";
import { type ChatMessage } from "../lib/mobileTypes";

export default function MobileChat({
  messages,
  input,
  loading,
  onInputChange,
  onSubmit,
}: Readonly<{
  messages: ChatMessage[];
  input: string;
  loading: boolean;
  onInputChange: (value: string) => void;
  onSubmit: (event?: FormEvent<HTMLFormElement>) => void;
}>) {
  return (
    <MobileCard>
      <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Ask Helix
      </p>
      <div className="mt-3 grid max-h-[50dvh] gap-3 overflow-y-auto pr-1">
        {messages.map((message, index) => (
          <div
            key={`${message.role}-${index}-${message.content.slice(0, 8)}`}
            className={`rounded-2xl px-3 py-2 text-sm leading-6 ${
              message.role === "user"
                ? "ml-8 bg-cyan-300 text-slate-950"
                : message.error
                  ? "mr-8 border border-amber-300/20 bg-amber-300/10 text-amber-100"
                  : "mr-8 border border-white/10 bg-black/25 text-neutral-100"
            }`}
          >
            {message.content}
          </div>
        ))}
        {loading ? (
          <div className="mr-8 rounded-2xl border border-white/10 bg-black/25 px-3 py-2 text-sm text-neutral-400">
            Thinking...
          </div>
        ) : null}
      </div>
      <form onSubmit={onSubmit} className="mt-4 grid gap-2">
        <textarea
          value={input}
          onChange={(event) => onInputChange(event.target.value)}
          rows={4}
          placeholder="Ask, add a task, or schedule something..."
          className="min-h-28 w-full rounded-2xl border border-white/10 bg-black/25 px-4 py-4 text-base leading-6 text-white outline-none placeholder:text-neutral-600 focus:border-cyan-300/50"
        />
        <MobilePrimaryButton type="submit" disabled={loading}>
          {loading ? "Sending..." : "Send"}
        </MobilePrimaryButton>
      </form>
    </MobileCard>
  );
}
