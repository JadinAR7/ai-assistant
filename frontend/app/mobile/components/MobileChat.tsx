import { type FormEvent, useState } from "react";

import {
  MobileCard,
  MobilePrimaryButton,
} from "./MobileCard";
import { type ChatMessage } from "../lib/mobileTypes";

export default function MobileChat({
  messages,
  input,
  loading,
  retryingMessageId,
  onInputChange,
  onSubmit,
  onRetry,
}: Readonly<{
  messages: ChatMessage[];
  input: string;
  loading: boolean;
  retryingMessageId: string | null;
  onInputChange: (value: string) => void;
  onSubmit: (event?: FormEvent<HTMLFormElement>) => void;
  onRetry: (messageId: string) => void;
}>) {
  const [copyState, setCopyState] = useState<{
    key: string;
    status: "copied" | "failed";
  } | null>(null);

  function fallbackCopyText(content: string) {
    const textArea = document.createElement("textarea");
    textArea.value = content;
    textArea.setAttribute("readonly", "true");
    textArea.style.position = "fixed";
    textArea.style.top = "0";
    textArea.style.left = "0";
    textArea.style.width = "1px";
    textArea.style.height = "1px";
    textArea.style.opacity = "0";
    textArea.style.fontSize = "16px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    textArea.setSelectionRange(0, content.length);

    try {
      return document.execCommand("copy");
    } finally {
      document.body.removeChild(textArea);
    }
  }

  async function copyMessage(key: string, content: string) {
    let copied = false;

    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(content);
        copied = true;
      }
    } catch {
      copied = false;
    }

    if (!copied) {
      try {
        copied = fallbackCopyText(content);
      } catch {
        copied = false;
      }
    }

    setCopyState({ key, status: copied ? "copied" : "failed" });
    window.setTimeout(() => setCopyState(null), copied ? 1700 : 1900);
  }

  function copyButtonLabel(key: string) {
    if (copyState?.key !== key) return "Copy";
    return copyState.status === "copied" ? "Copied" : "Copy failed";
  }

  return (
    <MobileCard>
      <p className="text-xs font-semibold uppercase tracking-wide text-neutral-500">
        Ask Helix
      </p>
      <div className="mt-3 grid max-h-[50dvh] gap-3 overflow-y-auto pr-1">
        {messages.map((message, index) => {
          const copyKey = message.id || `${message.role}-${index}`;
          const retryingThisMessage =
            Boolean(message.retryOfMessageId) &&
            retryingMessageId === message.retryOfMessageId;

          return (
            <article
              key={copyKey}
              className={`rounded-2xl px-3 py-2 text-sm leading-6 ${
                message.role === "user"
                  ? "ml-8 bg-cyan-300 text-slate-950"
                  : message.error
                    ? "mr-8 border border-amber-300/20 bg-amber-300/10 text-amber-100"
                    : "mr-8 border border-white/10 bg-black/25 text-neutral-100"
              }`}
            >
              <div className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                {message.content}
              </div>
              <div className="mt-2 flex flex-wrap items-center justify-end gap-2">
                {message.status === "sending" ? (
                  <span className="mr-auto text-[11px] font-semibold uppercase tracking-wide opacity-70">
                    Sending
                  </span>
                ) : null}
                {message.role === "user" && message.status === "failed" ? (
                  <span className="mr-auto text-[11px] font-semibold uppercase tracking-wide opacity-70">
                    Not sent
                  </span>
                ) : null}
                {message.retryOfMessageId ? (
                  <button
                    type="button"
                    onClick={() => onRetry(message.retryOfMessageId || "")}
                    disabled={loading || retryingThisMessage}
                    className="min-h-9 rounded-full border border-amber-200/30 bg-amber-200/10 px-4 text-[11px] font-semibold text-amber-100 disabled:opacity-50"
                  >
                    {retryingThisMessage ? "Retrying..." : "Retry"}
                  </button>
                ) : null}
                <button
                  type="button"
                  onClick={() => void copyMessage(copyKey, message.content)}
                  className={`min-h-9 rounded-full border px-3 text-[11px] font-semibold ${
                    message.role === "user"
                      ? "border-slate-950/15 bg-slate-950/10 text-slate-950"
                      : "border-white/10 bg-white/[0.04] text-neutral-300"
                  }`}
                >
                  {copyButtonLabel(copyKey)}
                </button>
              </div>
            </article>
          );
        })}
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
