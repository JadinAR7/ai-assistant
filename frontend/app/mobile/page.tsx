"use client";

import { type FormEvent, useEffect, useMemo, useRef, useState } from "react";

import MobileChat from "./components/MobileChat";
import MobileHome from "./components/MobileHome";
import MobileJournal from "./components/MobileJournal";
import MobileSchedule from "./components/MobileSchedule";
import MobileShell from "./components/MobileShell";
import MobileTrading from "./components/MobileTrading";
import {
  completeMobileNotification,
  completeMobileReminder,
  dismissMobileNotification,
  dismissMobileReminder,
  emptyMobileData,
  fetchMobileData,
  MobileChatError,
  completeMobileScheduleBlock,
  rollMobileScheduleBlockLater,
  rollMobileScheduleBlockTomorrow,
  startMobileScheduleBlock,
  runMobileScanner,
  sendMobileChat,
} from "./lib/mobileApi";
import {
  type ChatMessage,
  type MobileActionResult,
  type MobileData,
  type MobileTabId,
} from "./lib/mobileTypes";
import {
  getNextFlexibleBlock,
  getNextScheduleBlock,
  getTodayBlocks,
} from "./lib/mobileUtils";

export default function MobileHelixPage() {
  const [activeTab, setActiveTab] = useState<MobileTabId>("home");
  const [data, setData] = useState<MobileData>(emptyMobileData);
  const [loading, setLoading] = useState(true);
  const [scanLoading, setScanLoading] = useState(false);
  const [chatInput, setChatInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [retryingMessageId, setRetryingMessageId] = useState<string | null>(null);
  const [quickCommandLoading, setQuickCommandLoading] = useState<string | null>(null);
  const [mobileQueueLoading, setMobileQueueLoading] = useState<string | null>(null);
  const [scheduleActionLoading, setScheduleActionLoading] = useState<string | null>(null);
  const [actionResult, setActionResult] = useState<MobileActionResult | null>(null);
  const chatRequestInFlightRef = useRef(false);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Helix mobile is online. What do you want to move today?",
      status: "sent",
    },
  ]);

  const nextBlock = useMemo(
    () => getNextScheduleBlock(data.scheduleBlocks),
    [data.scheduleBlocks],
  );
  const todayBlocks = useMemo(
    () => getTodayBlocks(data.scheduleBlocks),
    [data.scheduleBlocks],
  );
  const nextFlexibleBlock = useMemo(
    () => getNextFlexibleBlock(data.scheduleBlocks),
    [data.scheduleBlocks],
  );
  const scannerSymbol =
    data.scanStatus?.default_symbol ||
    data.scanStatus?.symbol ||
    data.latestScan?.symbol ||
    "MES";
  const tradePerformance = data.briefing?.trading_performance;
  const calendarSummary = data.performanceCalendar?.summary;

  async function loadMobileData() {
    setLoading(true);
    setData(await fetchMobileData());
    setLoading(false);
  }

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadMobileData();
    }, 0);

    return () => window.clearTimeout(timer);
  }, []);

  function startPrompt(prompt: string) {
    setChatInput(prompt);
    setActiveTab("chat");
  }

  function createChatMessageId() {
    if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
      return crypto.randomUUID();
    }
    return `mobile-chat-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  }

  function getChatErrorMessage(error: unknown) {
    if (error instanceof MobileChatError) {
      if (error.reason === "timeout") {
        return "Helix took too long to respond. Try again.";
      }
      if (error.reason === "offline") {
        return "Helix backend is offline. Try again when the Mac mini is reachable.";
      }
      if (error.reason === "parse") {
        return error.message;
      }
      return error.message || "Helix could not send that message. Try again.";
    }
    return "Helix could not send that message. Try again.";
  }

  async function submitChatMessage(
    message: string,
    options: { userMessageId?: string; title?: string } = {},
  ) {
    const trimmedMessage = message.trim();
    if (!trimmedMessage || chatRequestInFlightRef.current) return;

    chatRequestInFlightRef.current = true;
    const userMessageId = options.userMessageId || createChatMessageId();
    const isRetry = Boolean(options.userMessageId);

    setActiveTab("chat");
    setActionResult(null);
    setChatLoading(true);

    if (options.title) {
      setQuickCommandLoading(options.title);
    }

    if (isRetry) {
      setRetryingMessageId(userMessageId);
      setChatMessages((current) =>
        current
          .filter((chatMessage) => chatMessage.retryOfMessageId !== userMessageId)
          .map((chatMessage) =>
            chatMessage.id === userMessageId
              ? { ...chatMessage, status: "sending" as const }
              : chatMessage,
          ),
      );
    } else {
      setChatMessages((current) => [
        ...current,
        {
          id: userMessageId,
          role: "user",
          content: trimmedMessage,
          status: "sending",
        },
      ]);
    }

    try {
      const result = await sendMobileChat(trimmedMessage);
      const responseText = result.message || "Done.";
      setChatMessages((current) => [
        ...current
          .filter((chatMessage) => chatMessage.retryOfMessageId !== userMessageId)
          .map((chatMessage) =>
            chatMessage.id === userMessageId
              ? { ...chatMessage, status: "sent" as const }
              : chatMessage,
          ),
        {
          id: createChatMessageId(),
          role: "assistant",
          content: responseText,
          status: "sent",
        },
      ]);
      void loadMobileData();
    } catch (error) {
      setChatMessages((current) => [
        ...current
          .filter((chatMessage) => chatMessage.retryOfMessageId !== userMessageId)
          .map((chatMessage) =>
            chatMessage.id === userMessageId
              ? { ...chatMessage, status: "failed" as const }
              : chatMessage,
          ),
        {
          id: createChatMessageId(),
          role: "system",
          content: getChatErrorMessage(error),
          status: "failed",
          retryOfMessageId: userMessageId,
          error: true,
        },
      ]);
    } finally {
      setQuickCommandLoading(null);
      setRetryingMessageId(null);
      setChatLoading(false);
      chatRequestInFlightRef.current = false;
    }
  }

  async function sendMobileChatCommand(command: string, title = "Helix action") {
    const message = command.trim();
    if (!message || chatRequestInFlightRef.current) return;
    void submitChatMessage(message, { title });
  }

  async function sendChat(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const message = chatInput.trim();
    if (!message || chatRequestInFlightRef.current) return;
    setChatInput("");
    void submitChatMessage(message);
  }

  function retryChatMessage(messageId: string) {
    if (chatRequestInFlightRef.current) return;
    const failedMessage = chatMessages.find(
      (message) => message.id === messageId && message.role === "user",
    );
    if (!failedMessage) return;
    void submitChatMessage(failedMessage.content, { userMessageId: messageId });
  }

  async function runScanner() {
    setScanLoading(true);
    setActionResult(null);
    try {
      await runMobileScanner(scannerSymbol);
      await loadMobileData();
      setActionResult({
        title: "Scanner",
        message: "Scanner request sent.",
      });
    } catch {
      setActionResult({
        title: "Scanner",
        message: "Couldn't load scanner status. Try again when the Mac mini is reachable.",
        error: true,
      });
    } finally {
      setScanLoading(false);
    }
  }

  async function runMobileQueueAction(
    key: string,
    title: string,
    action: () => Promise<unknown>,
  ) {
    if (mobileQueueLoading) return;

    setMobileQueueLoading(key);
    setActionResult(null);
    try {
      await action();
      await loadMobileData();
      setActionResult({ title, message: "Updated your mobile queue." });
    } catch {
      setActionResult({
        title,
        message: "Helix backend is offline. Try again when the Mac mini is reachable.",
        error: true,
      });
    } finally {
      setMobileQueueLoading(null);
    }
  }

  async function runScheduleAction(
    key: string,
    title: string,
    successMessage: string,
    action: () => Promise<unknown>,
  ) {
    if (scheduleActionLoading) return;

    setScheduleActionLoading(key);
    setActionResult(null);
    try {
      await action();
      await loadMobileData();
      setActionResult({ title, message: successMessage });
    } catch (error) {
      const message =
        error instanceof Error && error.message
          ? error.message
          : "Helix could not update that schedule block. Try again.";
      setActionResult({ title, message, error: true });
    } finally {
      setScheduleActionLoading(null);
    }
  }

  function startScheduleBlock(id: number) {
    runScheduleAction(
      `schedule-start-${id}`,
      "Schedule",
      "Checked in. This block is active now.",
      () => startMobileScheduleBlock(id),
    );
  }

  function completeScheduleBlock(id: number) {
    runScheduleAction(
      `schedule-done-${id}`,
      "Schedule",
      "Marked that block done.",
      () => completeMobileScheduleBlock(id),
    );
  }

  function rollScheduleBlockLater(id: number) {
    runScheduleAction(
      `schedule-roll-later-${id}`,
      "Schedule",
      "Rolled that block later today.",
      () => rollMobileScheduleBlockLater(id),
    );
  }

  function rollScheduleBlockTomorrow(id: number) {
    runScheduleAction(
      `schedule-roll-tomorrow-${id}`,
      "Schedule",
      "Rolled that block to tomorrow.",
      () => rollMobileScheduleBlockTomorrow(id),
    );
  }

  return (
    <MobileShell
      activeTab={activeTab}
      backendReachable={data.backendReachable}
      presenceLabel={data.presence?.label || data.presence?.mode}
      loading={loading}
      onTabChange={setActiveTab}
    >
      {activeTab === "home" ? (
        <MobileHome
          data={data}
          nextBlock={nextBlock}
          nextFlexibleBlock={nextFlexibleBlock}
          calendarSummary={calendarSummary}
          tradePerformance={tradePerformance}
          loading={loading}
          scanLoading={scanLoading}
          quickCommandLoading={quickCommandLoading}
          actionResult={actionResult}
          mobileQueueLoading={mobileQueueLoading || scheduleActionLoading}
          onRefresh={loadMobileData}
          onRunScanner={runScanner}
          onQuickCommand={sendMobileChatCommand}
          onCompleteReminder={(id) =>
            runMobileQueueAction(`reminder-complete-${id}`, "Reminder done", () =>
              completeMobileReminder(id),
            )
          }
          onDismissReminder={(id) =>
            runMobileQueueAction(`reminder-dismiss-${id}`, "Reminder dismissed", () =>
              dismissMobileReminder(id),
            )
          }
          onStartScheduleBlock={startScheduleBlock}
          onRollScheduleBlock={rollScheduleBlockLater}
          onAckNotification={(id) =>
            runMobileQueueAction(`notification-ack-${id}`, "Notification dismissed", () =>
              dismissMobileNotification(id),
            )
          }
          onCompleteNotification={(id) =>
            runMobileQueueAction(
              `notification-complete-${id}`,
              "Notification completed",
              () => completeMobileNotification(id),
            )
          }
          onStartPrompt={startPrompt}
          onTabChange={setActiveTab}
        />
      ) : null}

      {activeTab === "chat" ? (
        <MobileChat
          messages={chatMessages}
          input={chatInput}
          loading={chatLoading}
          retryingMessageId={retryingMessageId}
          onInputChange={setChatInput}
          onSubmit={sendChat}
          onRetry={retryChatMessage}
        />
      ) : null}

      {activeTab === "schedule" ? (
        <MobileSchedule
          blocks={todayBlocks}
          actionLoading={scheduleActionLoading}
          actionResult={actionResult}
          onStart={startScheduleBlock}
          onDone={completeScheduleBlock}
          onRollLater={rollScheduleBlockLater}
          onRollTomorrow={rollScheduleBlockTomorrow}
          onStartPrompt={startPrompt}
        />
      ) : null}

      {activeTab === "trading" ? (
        <MobileTrading
          scannerSymbol={scannerSymbol}
          scanStatus={data.scanStatus}
          latestScan={data.latestScan}
          calendarSummary={calendarSummary}
          tradePerformance={tradePerformance}
          scanLoading={scanLoading}
          onRunScanner={runScanner}
        />
      ) : null}

      {activeTab === "journal" ? (
        <MobileJournal
          entries={data.journalEntries}
          performanceCalendar={data.performanceCalendar}
          onStartPrompt={startPrompt}
        />
      ) : null}
    </MobileShell>
  );
}
