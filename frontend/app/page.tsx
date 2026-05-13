"use client";

import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

function generateId() {
  return Math.random().toString(36).substring(2, 10);
}

type Message = {
  id: string;
  role: "user" | "assistant";
  content: string;
  error?: boolean;
  retryText?: string;
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: generateId(),
      role: "assistant",
      content: "What’s good, Jadin? Assistant is online.",
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const [toolMode, setToolMode] = useState("auto");


  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  useEffect(() => {
  loadHistory();
}, []);

  async function sendMessage(messageText?: string) {
    const text = messageText ?? input;

    if (!text.trim() || loading) return;

    const userMessage: Message = {
      id: generateId(),
      role: "user",
      content: text,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: text,
          tool_mode: toolMode,
        }),
        signal: controller.signal,
      });

      if (!res.ok) {
        throw new Error("Backend request failed");
      }

      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "assistant",
          content: data.message || "No response.",
        },
      ]);
    } catch (error) {
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "assistant",
          content: "Backend connection failed. Check FastAPI.",
          error: true,
          retryText: text,
        },
      ]);
    } finally {
      abortRef.current = null;
      setLoading(false);
    }
  }

  function stopResponse() {
    abortRef.current?.abort();
    abortRef.current = null;
    setLoading(false);
  }

  function deleteMessage(id: string) {
    setMessages((prev) => prev.filter((msg) => msg.id !== id));
  }

  

  async function clearChat() {
    try {
      await fetch(`${API_BASE}/reset`, {
        method: "POST",
      });
    } catch {
      console.log("Could not reset backend memory.");
    }

    setMessages([
      {
        id: generateId(),
        role: "assistant",
        content: "Chat cleared. Backend memory reset too.",
      },
    ]);

    messagesContainerRef.current?.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  }

  async function loadHistory() {
    try {
      const res = await fetch(`${API_BASE}/history`);
      const data = await res.json();

      if (!data.history?.length) return;

      const loadedMessages: Message[] = data.history.map(
        (item: { role: string; content: string }) => ({
          id: generateId(),
          role: item.role.toLowerCase() === "user" ? "user" : "assistant",
          content: item.content,
        })
      );

      setMessages(loadedMessages);
    } catch {
      console.log("Could not load history.");
    }
  }

  async function handleFileUpload(file: File) {
    const isTextFile =
      file.type.startsWith("text/") ||
      file.name.endsWith(".py") ||
      file.name.endsWith(".js") ||
      file.name.endsWith(".ts") ||
      file.name.endsWith(".tsx") ||
      file.name.endsWith(".json") ||
      file.name.endsWith(".md") ||
      file.name.endsWith(".txt");

    if (!isTextFile) {
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "assistant",
          content: `Attachment "${file.name}" was selected, but image/PDF upload is not wired yet. Text/code files work right now.`,
        },
      ]);
      return;
    }

    const text = await file.text();

    setInput(`Attached file: ${file.name}\n\n${text.slice(0, 4000)}`);
  }

  return (
    <main className="min-h-screen bg-neutral-950 text-white flex flex-col">
      <header className="sticky top-0 z-10 border-b border-white/10 bg-neutral-950/80 backdrop-blur">
        <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-4">
          <div>
            <h1 className="text-lg font-semibold">Jadin AI Assistant</h1>
            <p className="text-sm text-neutral-400">
              Local AI. Real tools. Full control.
            </p>
          </div>

          <button
            onClick={clearChat}
            className="rounded-xl border border-white/10 px-3 py-2 text-xs text-neutral-300 hover:bg-white/10"
          >
            Clear
          </button>
        </div>
      </header>

      <section className="flex-1 overflow-y-auto">
        <div className="mx-auto flex max-w-3xl flex-col gap-4 px-4 py-6 pb-40">
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`group flex ${
                msg.role === "user" ? "justify-end" : "justify-start"
              }`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-lg ${
                  msg.role === "user"
                    ? "bg-blue-600 text-white"
                    : msg.error
                    ? "border border-red-500/30 bg-red-950/40 text-red-100"
                    : "border border-white/10 bg-neutral-900 text-neutral-100"
                }`}
              >
                <div className="prose prose-invert max-w-none prose-p:my-2 prose-headings:my-3 prose-ul:my-2 prose-li:my-1">
                {msg.content.startsWith("TOOL:") ? (
                  "Using tool..."
                ) : (
                  <ReactMarkdown>{msg.content}</ReactMarkdown>
                )}
              </div>

                <div className="mt-2 flex gap-2 opacity-70">
                  {msg.error && msg.retryText && (
                    <button
                      onClick={() => sendMessage(msg.retryText)}
                      className="text-xs text-red-200 underline underline-offset-4"
                    >
                      Retry
                    </button>
                  )}

                  <button
                    onClick={() => deleteMessage(msg.id)}
                    className="text-xs text-neutral-400 underline underline-offset-4 hover:text-white"
                  >
                    Delete
                  </button>
                </div>
              </div>
            </div>
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="rounded-2xl border border-white/10 bg-neutral-900 px-4 py-3 text-sm text-neutral-400">
                <div className="flex gap-1">
                  <span className="animate-bounce">•</span>
                  <span className="animate-bounce [animation-delay:0.1s]">
                    •
                  </span>
                  <span className="animate-bounce [animation-delay:0.2s]">
                    •
                  </span>
                </div>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </section>

      <footer className="fixed bottom-0 left-0 right-0 border-t border-white/10 bg-neutral-950/90 backdrop-blur">
        <div className="mx-auto max-w-3xl px-4 py-4">
          <div className="flex gap-2 rounded-2xl border border-white/10 bg-neutral-900 p-2 shadow-2xl">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="rounded-xl border border-white/10 px-3 text-lg text-neutral-400 hover:bg-white/10"
              title="Attach file"
            >
              +
            </button>

            <input
              ref={fileInputRef}
              type="file"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handleFileUpload(file);
              }}
            />

            <select
              value={toolMode}
              onChange={(e) => setToolMode(e.target.value)}
              className="rounded-xl border border-white/10 bg-neutral-950 px-2 text-xs text-neutral-300 outline-none"
            >
              <option value="auto">Auto</option>
              <option value="market_csv">Market CSV</option>
            </select>

            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
              placeholder="Ask your assistant..."
              rows={1}
              className="min-h-11 flex-1 resize-none bg-transparent px-3 py-2 text-sm text-white outline-none placeholder:text-neutral-500"
            />

            <button
              onClick={loading ? stopResponse : () => sendMessage()}
              className={`rounded-xl px-4 py-2 text-sm font-semibold ${
                loading ? "bg-red-500 text-white" : "bg-white text-black"
              }`}
            >
              {loading ? "Stop" : "Send"}
            </button>
          </div>
        </div>
      </footer>
    </main>
  );
}