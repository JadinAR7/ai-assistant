import argparse
import json
import time
from datetime import datetime, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo

from tools import analyze_tradingview


# -------------------------
# Scan configuration
# -------------------------
SYMBOL = "MES"
SCAN_INTERVAL_SECONDS = 5 * 60
TIMEZONE = ZoneInfo("America/Denver")

BASE_DIR = Path(__file__).resolve().parent
SCAN_HISTORY_PATH = BASE_DIR / "scan_history.jsonl"


# -------------------------
# Session windows
# -------------------------
def _time_in_range(now_time: dt_time, start: dt_time, end: dt_time) -> bool:
    """
    Handles same-day time windows.
    Example: 7:30 AM to 2:00 PM.
    """
    return start <= now_time <= end


def get_active_sessions(now: datetime) -> list[str]:
    """
    Returns active scan sessions based on Mountain Time.

    Weekday convention:
    Monday = 0
    Tuesday = 1
    Wednesday = 2
    Thursday = 3
    Friday = 4
    Saturday = 5
    Sunday = 6
    """
    sessions = []
    weekday = now.weekday()
    now_time = now.time()

    # -------------------------
    # Sunday market open
    # -------------------------
    if weekday == 6 and _time_in_range(now_time, dt_time(16, 0), dt_time(16, 15)):
        sessions.append("Sunday Open")

    # -------------------------
    # Tokyo session
    # Futures reopen Sunday evening, so include Sunday through Thursday nights.
    # Friday evening is excluded because the futures week is closed.
    # -------------------------
    if weekday in [6, 0, 1, 2, 3] and _time_in_range(now_time, dt_time(18, 0), dt_time(23, 59)):
        sessions.append("Tokyo")

    # -------------------------
    # London session
    # Monday through Friday morning.
    # -------------------------
    if weekday in [0, 1, 2, 3, 4] and _time_in_range(now_time, dt_time(1, 30), dt_time(9, 29)):
        sessions.append("London")

    # -------------------------
    # New York session
    # Monday through Friday.
    # -------------------------
    if weekday in [0, 1, 2, 3, 4] and _time_in_range(now_time, dt_time(7, 30), dt_time(14, 0)):
        sessions.append("New York")

    return sessions


def should_scan_now(now: datetime) -> bool:
    return len(get_active_sessions(now)) > 0


# -------------------------
# Scan storage
# -------------------------
def save_scan_record(record: dict) -> None:
    SCAN_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    with SCAN_HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_scan_record(result: dict, now: datetime, sessions: list[str]) -> dict:
    visual_extraction = result.get("visual_extraction", {}) or {}
    csv_analysis = result.get("csv_analysis", {}) or {}

    return {
        "timestamp": now.isoformat(),
        "timezone": "America/Denver",
        "symbol": SYMBOL,
        "sessions": sessions,
        "session_label": " + ".join(sessions),
        "success": result.get("success", False),
        "screenshot_path": result.get("screenshot_path"),
        "vision_success": visual_extraction.get("success", False),
        "vision_error": visual_extraction.get("error"),
        "csv_success": csv_analysis.get("success", False),
        "message": result.get("message"),
    }


# -------------------------
# Scan runner
# -------------------------
def run_scan(force: bool = False) -> dict | None:
    now = datetime.now(TIMEZONE)
    sessions = get_active_sessions(now)

    if not force and not sessions:
        print(f"[{now.isoformat()}] Outside scan window. No scan ran.")
        return None

    session_label = " + ".join(sessions) if sessions else "Forced Scan"

    print(f"[{now.isoformat()}] Running {SYMBOL} scan during: {session_label}")

    try:
        result = analyze_tradingview(
            symbol=SYMBOL,
            prompt=f"Scheduled {SYMBOL} scan during {session_label}. Analyze with marked levels.",
        )

        record = build_scan_record(
            result=result,
            now=now,
            sessions=sessions if sessions else ["Forced Scan"],
        )

        save_scan_record(record)

        print("Scan saved.")
        print("Screenshot:", record.get("screenshot_path"))
        print("Vision success:", record.get("vision_success"))
        print("CSV success:", record.get("csv_success"))
        print()
        print(record.get("message"))

        return record

    except Exception as e:
        error_record = {
            "timestamp": now.isoformat(),
            "timezone": "America/Denver",
            "symbol": SYMBOL,
            "sessions": sessions if sessions else ["Forced Scan"],
            "session_label": session_label,
            "success": False,
            "error": str(e),
        }

        save_scan_record(error_record)

        print("Scan failed:", e)
        return error_record


def run_loop() -> None:
    print("Scheduled scanner started.")
    print(f"Symbol: {SYMBOL}")
    print(f"Interval: {SCAN_INTERVAL_SECONDS // 60} minutes")
    print(f"History file: {SCAN_HISTORY_PATH}")
    print("Press CTRL+C to stop.")
    print()

    while True:
        run_scan(force=False)
        time.sleep(SCAN_INTERVAL_SECONDS)


# -------------------------
# CLI entrypoint
# -------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scheduled MES chart scanner.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one scan if inside an active session window.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Run one scan immediately, even outside session windows.",
    )

    args = parser.parse_args()

    if args.force:
        run_scan(force=True)
    elif args.once:
        run_scan(force=False)
    else:
        run_loop()