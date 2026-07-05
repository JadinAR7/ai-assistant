"use client";

import { type FormEvent, useEffect, useMemo, useState } from "react";

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
  const [quickCommandLoading, setQuickCommandLoading] = useState<string | null>(null);
  const [mobileQueueLoading, setMobileQueueLoading] = useState<string | null>(null);
  const [actionResult, setActionResult] = useState<MobileActionResult | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: "Helix mobile is online. What do you want to move today?",
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

  async function sendMobileChatCommand(command: string, title = "Helix action") {
    const message = command.trim();
    if (!message || chatLoading) return;

    setActiveTab("chat");
    setActionResult(null);
    setQuickCommandLoading(title);
    setChatLoading(true);
    setChatMessages((current) => [...current, { role: "user", content: message }]);

    try {
      const result = await sendMobileChat(message);
      const responseText = result.message || "Done.";
      setChatMessages((current) => [
        ...current,
        { role: "assistant", content: responseText },
      ]);
      await loadMobileData();
    } catch {
      const errorMessage =
        "Helix backend is offline. Try again when the Mac mini is reachable.";
      setChatMessages((current) => [
        ...current,
        { role: "assistant", content: errorMessage, error: true },
      ]);
    } finally {
      setQuickCommandLoading(null);
      setChatLoading(false);
    }
  }

  async function sendChat(event?: FormEvent<HTMLFormElement>) {
    event?.preventDefault();
    const message = chatInput.trim();
    if (!message || chatLoading) return;

    setChatMessages((current) => [...current, { role: "user", content: message }]);
    setChatInput("");
    setChatLoading(true);
    setActionResult(null);

    try {
      const result = await sendMobileChat(message);
      setChatMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: result.message || "Done.",
        },
      ]);
      void loadMobileData();
    } catch {
      setChatMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            "Helix backend is offline. Try again when the Mac mini is reachable.",
          error: true,
        },
      ]);
    } finally {
      setChatLoading(false);
    }
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
          mobileQueueLoading={mobileQueueLoading}
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
          onInputChange={setChatInput}
          onSubmit={sendChat}
        />
      ) : null}

      {activeTab === "schedule" ? (
        <MobileSchedule blocks={todayBlocks} onStartPrompt={startPrompt} />
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
