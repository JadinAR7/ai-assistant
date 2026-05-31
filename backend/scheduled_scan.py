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
# Structured scan state
# -------------------------
def extract_structured_state(record: dict) -> dict:
    """
    Extracts stable state fields from the scan message.

    V1 is message-derived because analyze_tradingview currently returns the
    clean final message but not a dedicated compact_state object in the scan
    record. Later, we can save compact_state directly from tools.py.
    """
    message = record.get("message") or ""

    state = {
        "htf_bias": "unknown",
        "execution_bias": "unknown",
        "price_relation": "unknown",
        "visual_4h_fvg": False,
        "visual_15m_fvg": False,
        "pdh_visible": False,
        "vision_success": record.get("vision_success"),
        "csv_success": record.get("csv_success"),
    }

    message_lower = message.lower()

    if "1d bias is bullish" in message_lower or "htf remains bullish" in message_lower:
        state["htf_bias"] = "bullish"
    elif "1d bias is bearish" in message_lower or "htf remains bearish" in message_lower:
        state["htf_bias"] = "bearish"
    elif "1d bias is neutral" in message_lower or "htf remains neutral" in message_lower:
        state["htf_bias"] = "neutral"

    if "execution bias is bearish" in message_lower or "execution is bearish" in message_lower:
        state["execution_bias"] = "bearish"
    elif "execution bias is bullish" in message_lower or "execution is bullish" in message_lower:
        state["execution_bias"] = "bullish"
    elif "execution bias is neutral" in message_lower or "execution is neutral" in message_lower:
        state["execution_bias"] = "neutral"

    if "current price is inside the active computed zone" in message_lower:
        state["price_relation"] = "inside_active_zone"
    elif "above the active computed zone" in message_lower:
        state["price_relation"] = "above_active_zone"
    elif "below the active computed zone" in message_lower:
        state["price_relation"] = "below_active_zone"

    state["visual_4h_fvg"] = "visual 4h fvg" in message_lower or "4hr fvg" in message_lower
    state["visual_15m_fvg"] = "visual 15m fvg" in message_lower or "15min fvg" in message_lower
    state["pdh_visible"] = "pdh" in message_lower or "pdnyh" in message_lower

    return state


# -------------------------
# Structured comparison
# -------------------------
def compare_structured_states(previous: dict | None, current: dict) -> dict:
    if not previous:
        return {
            "market_changes": ["No previous successful scan found for comparison."],
            "visual_context_changes": [],
            "system_status": [
                f"Vision success: {current.get('vision_success')}",
                f"CSV success: {current.get('csv_success')}",
            ],
        }

    previous_state = previous.get("state") or extract_structured_state(previous)
    current_state = current.get("state") or extract_structured_state(current)

    market_changes = []
    visual_context_changes = []
    system_status = []

    # -------------------------
    # Market structure changes
    # -------------------------
    market_fields = [
        ("htf_bias", "HTF bias"),
        ("execution_bias", "Execution bias"),
        ("price_relation", "Price relation"),
    ]

    for field, label in market_fields:
        old_value = previous_state.get(field)
        new_value = current_state.get(field)

        if old_value != new_value:
            market_changes.append(f"{label} changed from {old_value} to {new_value}.")

    # -------------------------
    # Visual context changes
    # -------------------------
    visual_flags = [
        ("visual_4h_fvg", "4H FVG visual confirmation"),
        ("visual_15m_fvg", "15M FVG visual confirmation"),
        ("pdh_visible", "PDH visual reference"),
    ]

    for field, label in visual_flags:
        old_value = previous_state.get(field)
        new_value = current_state.get(field)

        if old_value != new_value:
            if new_value:
                visual_context_changes.append(f"{label} appeared.")
            else:
                visual_context_changes.append(f"{label} disappeared.")

    # -------------------------
    # System/data status changes
    # -------------------------
    system_fields = [
        ("vision_success", "Vision status"),
        ("csv_success", "CSV status"),
    ]

    for field, label in system_fields:
        old_value = previous_state.get(field)
        new_value = current_state.get(field)

        if old_value != new_value:
            system_status.append(f"{label} changed from {old_value} to {new_value}.")

    if not market_changes:
        market_changes.append("No major market structure change detected.")

    if not visual_context_changes:
        visual_context_changes.append("No major visual context change detected.")

    if not system_status:
        system_status.append(
            f"Vision success: {current_state.get('vision_success')}; CSV success: {current_state.get('csv_success')}."
        )

    return {
        "market_changes": market_changes,
        "visual_context_changes": visual_context_changes,
        "system_status": system_status,
    }


# -------------------------
# Alert eligibility
# -------------------------
def evaluate_alert_eligibility(comparison: dict, current_record: dict) -> dict:
    """
    Decides whether a scan is important enough to alert on.

    V1 does not send alerts. It only marks whether the scan would be alert-worthy.
    Later this can trigger iMessage, mobile push, or TTS.
    """
    market_changes = comparison.get("market_changes", []) if isinstance(comparison, dict) else []
    visual_context_changes = comparison.get("visual_context_changes", []) if isinstance(comparison, dict) else []
    system_status = comparison.get("system_status", []) if isinstance(comparison, dict) else []

    state = current_record.get("state", {})

    should_alert = False
    reasons = []
    alert_type = "none"
    severity = "none"

    # -------------------------
    # Market structure alerts
    # -------------------------
    meaningful_market_change = [
        item for item in market_changes
        if "No major market structure change detected" not in item
        and "No previous successful scan found for comparison" not in item
    ]

    if meaningful_market_change:
        should_alert = True
        alert_type = "market_state_change"
        severity = "high"
        reasons.extend(meaningful_market_change)

    # -------------------------
    # Price relation alerts
    # -------------------------
    price_relation = state.get("price_relation")

    if price_relation == "inside_active_zone":
        should_alert = True
        alert_type = "price_at_active_zone" if alert_type == "none" else alert_type
        severity = "medium" if severity == "none" else severity
        reasons.append("Price is inside the active computed zone.")

    # -------------------------
    # Data quality alerts
    # -------------------------
    vision_success = state.get("vision_success")
    csv_success = state.get("csv_success")

    if csv_success is False:
        should_alert = True
        alert_type = "csv_failure"
        severity = "high"
        reasons.append("CSV analysis failed.")

    if vision_success is False:
        # Vision failure matters, but CSV can still carry the read.
        should_alert = True
        if alert_type == "none":
            alert_type = "vision_failure"
        if severity == "none":
            severity = "low"
        reasons.append("Vision extraction failed.")

    # -------------------------
    # Visual-only changes
    # -------------------------
    visual_only_change = [
        item for item in visual_context_changes
        if "No major visual context change detected" not in item
    ]

    if visual_only_change and not should_alert:
        # Save it, but do not alert from visual flicker alone.
        reasons.extend(
            f"Visual-only change, no alert: {item}"
            for item in visual_only_change
        )

    if not reasons:
        reasons.append("No alert-worthy change detected.")

    return {
        "should_alert": should_alert,
        "alert_type": alert_type,
        "severity": severity,
        "reasons": reasons,
        "system_status": system_status,
    }


# -------------------------
# Scan storage
# -------------------------
def save_scan_record(record: dict) -> None:
    SCAN_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)

    with SCAN_HISTORY_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def build_scan_record(
    result: dict,
    now: datetime,
    sessions: list[str],
    comparison: dict | None = None,
    alert: dict | None = None,
) -> dict:
    visual_extraction = result.get("visual_extraction", {}) or {}
    csv_analysis = result.get("csv_analysis", {}) or {}

    record = {
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
        "comparison": comparison or {
            "market_changes": [],
            "visual_context_changes": [],
            "system_status": [],
        },
        "alert": alert or {
            "should_alert": False,
            "alert_type": "none",
            "severity": "none",
            "reasons": [],
        },
    }

    record["state"] = extract_structured_state(record)

    return record


# -------------------------
# Scan history lookup
# -------------------------
def load_last_successful_scan(current_timestamp: str | None = None) -> dict | None:
    if not SCAN_HISTORY_PATH.exists():
        return None

    last_scan = None

    with SCAN_HISTORY_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if current_timestamp and record.get("timestamp") == current_timestamp:
                continue

            if record.get("symbol") != SYMBOL:
                continue

            if not record.get("success"):
                continue

            if not record.get("csv_success"):
                continue

            last_scan = record

    return last_scan


# -------------------------
# Legacy text comparison backup
# -------------------------
def extract_scan_facts(record: dict) -> dict:
    message = record.get("message") or ""

    return {
        "timestamp": record.get("timestamp"),
        "session_label": record.get("session_label"),
        "vision_success": record.get("vision_success"),
        "csv_success": record.get("csv_success"),
        "message": message,
    }


def compare_scan_messages(previous: dict | None, current: dict) -> list[str]:
    if not previous:
        return ["No previous successful scan found for comparison."]

    previous_facts = extract_scan_facts(previous)
    current_facts = extract_scan_facts(current)

    changes = []

    previous_message = previous_facts.get("message", "")
    current_message = current_facts.get("message", "")

    if previous_facts.get("vision_success") != current_facts.get("vision_success"):
        changes.append(
            f"Vision status changed from {previous_facts.get('vision_success')} to {current_facts.get('vision_success')}."
        )

    if previous_facts.get("csv_success") != current_facts.get("csv_success"):
        changes.append(
            f"CSV status changed from {previous_facts.get('csv_success')} to {current_facts.get('csv_success')}."
        )

    key_phrases = [
        "HTF remains bullish",
        "HTF remains bearish",
        "HTF and execution are aligned bullish",
        "HTF and execution are aligned bearish",
        "execution is bearish",
        "execution is bullish",
        "Current price is inside the active computed zone",
        "Current price is",
        "Visual 4H FVG appears aligned",
        "Visual 15M FVG was detected",
    ]

    for phrase in key_phrases:
        was_present = phrase in previous_message
        is_present = phrase in current_message

        if was_present != is_present:
            changes.append(
                f"State phrase changed: '{phrase}' is now {'present' if is_present else 'absent'}."
            )

    if not changes:
        changes.append("No major state change detected from the previous scan.")

    return changes


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

        previous_scan = load_last_successful_scan()

        temporary_record = build_scan_record(
            result=result,
            now=now,
            sessions=sessions if sessions else ["Forced Scan"],
        )

        comparison = compare_structured_states(previous_scan, temporary_record)

        temporary_record["comparison"] = comparison
        alert = evaluate_alert_eligibility(comparison, temporary_record)

        record = build_scan_record(
            result=result,
            now=now,
            sessions=sessions if sessions else ["Forced Scan"],
            comparison=comparison,
            alert=alert,
        )

        save_scan_record(record)

        print("Scan saved.")
        print("Screenshot:", record.get("screenshot_path"))
        print("Vision success:", record.get("vision_success"))
        print("CSV success:", record.get("csv_success"))

        print()
        print(record.get("message"))

        print()
        print("Comparison:")

        comparison = record.get("comparison", {})

        print("Market changes:")
        for item in comparison.get("market_changes", []):
            print("-", item)

        print("Visual context changes:")
        for item in comparison.get("visual_context_changes", []):
            print("-", item)

        print("System status:")
        for item in comparison.get("system_status", []):
            print("-", item)

        print()
        print("Alert decision:")
        alert = record.get("alert", {})
        print("Should alert:", alert.get("should_alert"))
        print("Type:", alert.get("alert_type"))
        print("Severity:", alert.get("severity"))
        print("Reasons:")
        for item in alert.get("reasons", []):
            print("-", item)

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