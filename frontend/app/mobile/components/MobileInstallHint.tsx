"use client";

import { useEffect, useState } from "react";

const DISMISS_KEY = "helix-mobile-install-hint-dismissed";

function getDismissed() {
  try {
    return window.localStorage.getItem(DISMISS_KEY) === "true";
  } catch {
    return false;
  }
}

function setDismissed() {
  try {
    window.localStorage.setItem(DISMISS_KEY, "true");
  } catch {
    return;
  }
}

function isIosSafariBrowser() {
  if (typeof window === "undefined") return false;

  const userAgent = window.navigator.userAgent;
  const isIos =
    /iPad|iPhone|iPod/.test(userAgent) ||
    (userAgent.includes("Macintosh") && "ontouchend" in document);
  const isSafari = /Safari/.test(userAgent) && !/CriOS|FxiOS|EdgiOS/.test(userAgent);
  const isStandalone =
    window.matchMedia("(display-mode: standalone)").matches ||
    Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone);

  return isIos && isSafari && !isStandalone;
}

export default function MobileInstallHint() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!isIosSafariBrowser()) return;
    if (getDismissed()) return;
    const timer = window.setTimeout(() => setVisible(true), 0);
    return () => window.clearTimeout(timer);
  }, []);

  if (!visible) return null;

  return (
    <section className="mx-4 mt-3 rounded-2xl border border-cyan-300/20 bg-cyan-300/10 p-3 text-sm text-cyan-50 shadow-xl shadow-black/20">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="font-semibold">Add Helix to your Home Screen</p>
          <p className="mt-1 text-xs leading-5 text-cyan-100/80">
            Tap Share, then Add to Home Screen for the app-style view.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setDismissed();
            setVisible(false);
          }}
          className="min-h-8 rounded-full border border-white/10 bg-white/[0.06] px-3 text-xs font-semibold text-cyan-50"
        >
          Hide
        </button>
      </div>
    </section>
  );
}
