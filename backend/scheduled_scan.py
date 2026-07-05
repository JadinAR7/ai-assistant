import argparse
import csv
import json
import os
import subprocess
import time
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from news_risk import build_news_risk_summary, format_news_risk_section
from notification_config import get_default_imessage_recipient
from presence import get_presence
from scanner_settings import (
    DEFAULT_SCANNER_SYMBOL,
    get_default_scanner_symbol,
    get_scanner_settings,
    normalize_scanner_symbol,
)
from tools import (
    analyze_market_csv,
    analyze_tradingview,
    capture_tradingview,
    extract_tradingview_visuals_from_path,
)


# -------------------------
# Scan configuration
# -------------------------
SYMBOL = DEFAULT_SCANNER_SYMBOL
SCAN_TIMEFRAME = "15M"
HTF_CSV_TIMEFRAMES = ["1D", "4H", "1H"]
SCHEDULED_SCAN_TIMEFRAMES = ["15M", "5M"]
CONDITIONAL_EXECUTION_TIMEFRAMES = ["1M"]
SCAN_INTERVAL_SECONDS = 5 * 60
TIMEZONE = ZoneInfo("America/Denver")


SCAN_NOTIFY_ENABLED = os.getenv("SCAN_NOTIFY_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
SCAN_NOTIFY_IMESSAGE_ENABLED = os.getenv("SCAN_NOTIFY_IMESSAGE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
SCAN_NOTIFY_TTS_ENABLED = os.getenv("SCAN_NOTIFY_TTS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
SCAN_SIGNAL_LEVELS = ["informational", "watch", "review", "alert"]
SCAN_ALERT_MIN_LEVEL = os.getenv("SCAN_ALERT_MIN_LEVEL", "review").strip().lower() or "review"
if SCAN_ALERT_MIN_LEVEL not in SCAN_SIGNAL_LEVELS:
    SCAN_ALERT_MIN_LEVEL = "review"
try:
    SCAN_SUPPRESS_REPEATS_MINUTES = max(
        0,
        int(os.getenv("SCAN_SUPPRESS_REPEATS_MINUTES", "15").strip() or "15"),
    )
except ValueError:
    SCAN_SUPPRESS_REPEATS_MINUTES = 15

BASE_DIR = Path(__file__).resolve().parent
SCAN_HISTORY_PATH = BASE_DIR / "scan_history.jsonl"
SCAN_RUNTIME_STATUS_PATH = BASE_DIR / "scan_runtime_status.json"
SCAN_SCREENSHOTS_DIR = BASE_DIR / "pictures" / "tradingview_screenshots"


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


def attach_news_risk(result: dict, now: datetime) -> None:
    try:
        news_risk = build_news_risk_summary(now=now)
    except Exception as e:
        news_risk = {
            "success": False,
            "timestamp": now.isoformat(),
            "timezone": "America/Denver",
            "risk": "Low",
            "next_major_event": None,
            "time_until_event": None,
            "event_importance": None,
            "upcoming_events": [],
            "upcoming_red_usd_events": [],
            "upcoming_orange_usd_events": [],
            "fed_speakers": [],
            "breaking_news": [],
            "provider_status": {
                "calendar": [f"news risk unavailable: {e}"],
                "breaking_news": [f"news risk unavailable: {e}"],
            },
        }

    result["news_risk"] = news_risk
    result["message"] = (
        (result.get("message") or "")
        + "\n\n"
        + format_news_risk_section(news_risk)
    ).strip()


# -------------------------
# Screenshot cleanup
# -------------------------
def _default_screenshot_cleanup_result() -> dict:
    return {
        "enabled": True,
        "mode": "replace_on_new_scan",
        "deleted_count": 0,
        "errors": [],
    }


def cleanup_scan_screenshots(symbol: str = SYMBOL) -> dict:
    result = _default_screenshot_cleanup_result()
    symbol = normalize_scanner_symbol(symbol)

    try:
        if not SCAN_SCREENSHOTS_DIR.exists():
            return result

        screenshot_files = [
            path
            for path in SCAN_SCREENSHOTS_DIR.glob(f"{symbol}_*.png")
            if path.is_file()
        ]

        for path in screenshot_files:
            try:
                path.unlink()
                result["deleted_count"] += 1
            except OSError as e:
                result["errors"].append(f"Could not delete {path}: {e}")
    except Exception as e:
        result["errors"].append(str(e))

    return result


# -------------------------
# Multi-timeframe visual context
# -------------------------
def _screenshot_path_exists(path: str | None) -> bool:
    return bool(path and Path(path).exists() and Path(path).is_file())


def _latest_saved_screenshot_for_timeframe(
    *,
    symbol: str,
    timeframe: str,
    now: datetime | None = None,
    tolerance_minutes: int = 20,
) -> str | None:
    symbol = normalize_scanner_symbol(symbol)
    timeframe = timeframe.upper()
    now = now or datetime.now(TIMEZONE)

    if not SCAN_SCREENSHOTS_DIR.exists():
        return None

    candidates = []
    pattern = f"{symbol}_{timeframe}_*.png"
    for path in SCAN_SCREENSHOTS_DIR.glob(pattern):
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, tz=TIMEZONE)
        except OSError:
            continue
        age_minutes = abs((now - modified).total_seconds()) / 60
        if age_minutes <= tolerance_minutes:
            candidates.append((modified, path))

    if not candidates:
        return None

    return str(sorted(candidates, key=lambda item: item[0], reverse=True)[0][1])


def _failed_timeframe_capture(timeframe: str, error: str | None = None, **extra) -> dict:
    capture = {
        "timeframe": timeframe,
        "capture_success": False,
        "success": False,
        "screenshot_path": None,
        "visual_extraction": None,
        "vision_success": False,
        "vision_error": None,
        "error": error or "Screenshot was not captured.",
    }
    capture.update({key: value for key, value in extra.items() if value is not None})
    return capture


def _normalize_timeframe_capture(
    *,
    timeframe: str,
    result: dict | None,
    symbol: str,
    run_vision_if_found: bool = False,
    prompt: str = "",
) -> dict:
    result = result if isinstance(result, dict) else {}
    screenshot_path = result.get("screenshot_path")
    recovered_from_file = False
    warning = None

    if not _screenshot_path_exists(screenshot_path):
        found_path = _latest_saved_screenshot_for_timeframe(symbol=symbol, timeframe=timeframe)
        if found_path:
            screenshot_path = found_path
            recovered_from_file = True
            warning = f"{timeframe} screenshot capture result was missing, but saved screenshot was found and used."

    if not _screenshot_path_exists(screenshot_path):
        if result:
            error = result.get("error") or result.get("message") or f"{timeframe} screenshot was not captured and no saved screenshot was found."
        else:
            error = f"{timeframe} screenshot capture result was missing and no saved screenshot was found."
        return _failed_timeframe_capture(
            timeframe,
            error,
            system_health_issue=result.get("system_health_issue"),
            affected_source=result.get("affected_source"),
        )

    visual_extraction = result.get("visual_extraction") or {}
    if run_vision_if_found and not visual_extraction.get("success"):
        visual_extraction = extract_tradingview_visuals_from_path(
            image_path=screenshot_path,
            prompt=prompt,
            symbol=symbol,
            source=f"scheduled {timeframe} TradingView capture",
        )

    return {
        "timeframe": timeframe,
        "capture_success": True,
        "success": True,
        "screenshot_path": screenshot_path,
        "visual_extraction": visual_extraction,
        "vision_success": visual_extraction.get("success", False),
        "vision_error": visual_extraction.get("error"),
        "error": None,
        **({"capture_warning": warning, "system_health_issue": "capture_result_missing_but_file_found"} if recovered_from_file else {}),
    }


def _build_timeframe_capture_from_result(timeframe: str, result: dict, *, symbol: str = SYMBOL, prompt: str = "") -> dict:
    return _normalize_timeframe_capture(
        timeframe=timeframe,
        result=result,
        symbol=symbol,
        run_vision_if_found=True,
        prompt=prompt,
    )


def _capture_timeframe_context(
    *,
    symbol: str,
    timeframe: str,
    prompt: str,
) -> dict:
    symbol = normalize_scanner_symbol(symbol)
    capture_result = capture_tradingview(symbol=symbol, timeframe=timeframe)

    normalized_capture = _normalize_timeframe_capture(
        timeframe=timeframe,
        result=capture_result if isinstance(capture_result, dict) else None,
        symbol=symbol,
    )

    if not normalized_capture.get("capture_success"):
        return normalized_capture

    screenshot_path = normalized_capture.get("screenshot_path")
    visual_extraction = extract_tradingview_visuals_from_path(
        image_path=screenshot_path,
        prompt=prompt,
        symbol=symbol,
        source=f"scheduled {timeframe} TradingView capture",
    )

    return {
        "timeframe": timeframe,
        "capture_success": True,
        "success": True,
        "screenshot_path": screenshot_path,
        "visual_extraction": visual_extraction,
        "vision_success": visual_extraction.get("success", False),
        "vision_error": visual_extraction.get("error"),
        "error": None,
        **({"capture_warning": normalized_capture.get("capture_warning"), "system_health_issue": "capture_result_missing_but_file_found"} if normalized_capture.get("capture_warning") else {}),
    }


def collect_scheduled_timeframe_captures(
    *,
    symbol: str = SYMBOL,
    primary_timeframe: str,
    primary_result: dict,
    session_label: str,
) -> dict:
    symbol = normalize_scanner_symbol(symbol)
    prompt = (
        f"Scheduled {symbol} scan during {session_label}. "
        "Extract visible user markings only."
    )
    captures = {}

    for timeframe in SCHEDULED_SCAN_TIMEFRAMES:
        if timeframe == primary_timeframe:
            captures[timeframe] = _build_timeframe_capture_from_result(
                timeframe=timeframe,
                result=primary_result,
                symbol=symbol,
                prompt=prompt,
            )
            continue

        try:
            captures[timeframe] = _capture_timeframe_context(
                symbol=symbol,
                timeframe=timeframe,
                prompt=prompt,
            )
        except Exception as e:
            captures[timeframe] = _failed_timeframe_capture(timeframe, str(e))

    return captures


def live_vision_timeframe_status(record: dict) -> dict[str, dict]:
    status = {}
    captures = record.get("timeframe_captures") or {}
    primary_timeframe = str(record.get("timeframe") or "")

    for timeframe in SCHEDULED_SCAN_TIMEFRAMES:
        capture = captures.get(timeframe)
        if not isinstance(capture, dict):
            capture = {}
        if not capture and primary_timeframe == timeframe:
            capture = {
                "screenshot_path": record.get("screenshot_path"),
                "vision_success": record.get("vision_success"),
                "vision_error": record.get("vision_error"),
            }
        status[timeframe] = {
            "capture_success": bool(capture.get("capture_success") or capture.get("screenshot_path")),
            "vision_success": bool(capture.get("vision_success")),
            "vision_quality_score": (capture.get("visual_extraction") or {}).get("vision_quality_score"),
            "vision_quality_status": (capture.get("visual_extraction") or {}).get("vision_quality_status"),
            "error": capture.get("vision_error") or capture.get("error"),
            "screenshot_path": capture.get("screenshot_path"),
        }

    return status


def live_vision_success_count(record: dict) -> int:
    return sum(
        1 for item in live_vision_timeframe_status(record).values()
        if item.get("capture_success") and item.get("vision_success")
    )


def has_partial_live_vision(record: dict) -> bool:
    return live_vision_success_count(record) > 0


def has_full_live_vision(record: dict) -> bool:
    return live_vision_success_count(record) == len(SCHEDULED_SCAN_TIMEFRAMES)


def structural_csv_available(record: dict) -> bool:
    if record.get("csv_success") is True:
        return True

    csv_analysis = record.get("csv_analysis") or {}
    if csv_analysis.get("success") is True:
        return True

    analysis = csv_analysis.get("analysis") or {}
    return bool(
        analysis.get("daily")
        or analysis.get("h4")
        or analysis.get("htf")
        or csv_analysis.get("zone_ranking")
        or analysis.get("zone_ranking")
    )


def _captured_timeframes(timeframe_captures: dict | None) -> list[str]:
    return [
        timeframe
        for timeframe, capture in (timeframe_captures or {}).items()
        if (capture or {}).get("screenshot_path")
    ]


def scanner_source_roles(one_minute_capture_reason: str | None = None) -> dict:
    return {
        "htf_structure": "CSV only: 1D/4H/1H",
        "live_vision": "15M/5M screenshots",
        "one_minute": (
            "1M screenshot captured for execution confirmation."
            if one_minute_capture_reason
            else "Conditional; not captured unless execution watch is active."
        ),
        "does_not_generate_trade_signals": True,
    }


def attach_scan_source_metadata(
    result: dict,
    timeframe_captures: dict | None,
    *,
    one_minute_capture_reason: str | None = None,
) -> None:
    requested = list(SCHEDULED_SCAN_TIMEFRAMES)
    if one_minute_capture_reason and "1M" not in requested:
        requested.append("1M")

    result["screenshots_requested"] = requested
    result["screenshots_captured"] = _captured_timeframes(timeframe_captures)
    result["csv_timeframes_used"] = list(HTF_CSV_TIMEFRAMES)
    result["one_minute_capture_reason"] = one_minute_capture_reason
    result["scanner_source_roles"] = scanner_source_roles(one_minute_capture_reason)


def _should_capture_one_minute_execution_context(record: dict) -> bool:
    narrative = record.get("narrative") or {}
    phase = str(narrative.get("narrative_phase") or record.get("narrative_phase") or "")
    return phase == "execution_watch"


def _append_one_minute_execution_context(record: dict, *, symbol: str, session_label: str) -> None:
    if not _should_capture_one_minute_execution_context(record):
        return

    timeframe_captures = record.setdefault("timeframe_captures", {})
    if timeframe_captures.get("1M"):
        return

    reason = "1M captured because scanner entered execution watch."
    prompt = (
        f"Scheduled {symbol} execution-watch scan during {session_label}. "
        "Extract visible 1M execution confirmation context only."
    )
    try:
        timeframe_captures["1M"] = _capture_timeframe_context(
            symbol=symbol,
            timeframe="1M",
            prompt=prompt,
        )
    except Exception as e:
        timeframe_captures["1M"] = _failed_timeframe_capture("1M", str(e))

    record["one_minute_capture_reason"] = reason
    record["screenshots_requested"] = list(SCHEDULED_SCAN_TIMEFRAMES) + ["1M"]
    record["screenshots_captured"] = _captured_timeframes(timeframe_captures)
    record["csv_timeframes_used"] = list(HTF_CSV_TIMEFRAMES)
    record["scanner_source_roles"] = scanner_source_roles(reason)
    record["message"] = (
        (record.get("message") or "")
        + "\n\n"
        + "## Conditional 1M Execution Context\n"
        + f"{reason}\n"
        + f"1M: {'captured' if timeframe_captures['1M'].get('screenshot_path') else 'failed'}"
    ).strip()


def scanner_mode_for_record(record: dict) -> str:
    narrative = record.get("narrative") or {}
    phase = str(narrative.get("narrative_phase") or record.get("narrative_phase") or "no_clear_narrative")
    alert_level = str((record.get("alert_eligibility") or {}).get("level") or "none").lower()
    signal_level = str(record.get("signal_level") or "informational").lower()

    if phase == "execution_watch":
        return "execution_watch"
    if alert_level in {"medium", "high"} or signal_level in {"review", "alert"}:
        return "alert_review"
    if phase in {"interacting_with_reaction_zone", "behavior_forming", "structure_confirming"}:
        return "reaction_mode"
    if phase in {"approaching_reaction_zone", "draw_identified"}:
        return "watch"
    return "htf_map"


def attach_scanner_mode(record: dict) -> None:
    mode = scanner_mode_for_record(record)
    record["scanner_mode"] = mode
    record["scanner_state"] = mode
    record["scanner_mode_label"] = mode.replace("_", " ").title()


def format_timeframe_screenshots_section(timeframe_captures: dict | None) -> str:
    lines = [
        "## Scanner Sources",
        "HTF Structure: CSV only (1D/4H/1H)",
        "Live Vision: 15M/5M screenshots",
        "1M: Conditional execution confirmation only",
        "",
        "## Timeframe Screenshots",
    ]

    for timeframe in SCHEDULED_SCAN_TIMEFRAMES:
        capture = (timeframe_captures or {}).get(timeframe) or {}
        status = "captured" if capture.get("screenshot_path") else "failed"
        lines.append(f"- {timeframe}: {status}")

    return "\n".join(lines)


def scheduled_timeframe_label() -> str:
    return "/".join(SCHEDULED_SCAN_TIMEFRAMES)


def attach_timeframe_screenshots_section(
    result: dict,
    timeframe_captures: dict | None,
) -> None:
    result["timeframe_captures"] = timeframe_captures or {}
    attach_scan_source_metadata(
        result,
        timeframe_captures,
        one_minute_capture_reason=result.get("one_minute_capture_reason"),
    )
    result["message"] = (
        (result.get("message") or "")
        + "\n\n"
        + format_timeframe_screenshots_section(timeframe_captures)
    ).strip()


# -------------------------
# Liquidity draw engine
# -------------------------
LIQUIDITY_REFERENCE_LABELS = {
    "pdh": "PDH",
    "pdl": "PDL",
    "pdnyh": "PDNYH",
    "pdnyl": "PDNYL",
    "asia_high": "Asia High",
    "asia_low": "Asia Low",
    "london_high": "London High",
    "london_low": "London Low",
    "previous_week_high": "Previous Week High",
    "previous_week_low": "Previous Week Low",
}

LIQUIDITY_IMPORTANCE = {
    "previous_week_high": 15,
    "previous_week_low": 15,
    "pdh": 12,
    "pdl": 12,
    "pdnyh": 10,
    "pdnyl": 10,
    "asia_high": 8,
    "asia_low": 8,
    "london_high": 8,
    "london_low": 8,
}


def _safe_float(value) -> float | None:
    if value is None:
        return None

    try:
        return float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


def _parse_csv_time(value: str | None) -> datetime | None:
    if not value:
        return None

    text = str(value).strip()

    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _fmt_draw_price(value) -> str:
    number = _safe_float(value)

    if number is None:
        return "unknown"

    return f"{number:.2f}".rstrip("0").rstrip(".")


def _load_csv_rows_from_file(filename: str | None) -> list[dict]:
    if not filename:
        return []

    path = Path(filename)

    if not path.is_absolute():
        path = BASE_DIR / "csv_data" / filename

    if not path.exists():
        return []

    rows = []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            parsed_time = _parse_csv_time(row.get("time"))

            if not parsed_time:
                continue

            high = _safe_float(row.get("high"))
            low = _safe_float(row.get("low"))
            close = _safe_float(row.get("close"))

            if high is None or low is None:
                continue

            rows.append({
                "time": parsed_time,
                "high": high,
                "low": low,
                "close": close,
            })

    return rows


def _csv_files_used(record: dict) -> dict:
    csv_analysis = record.get("csv_analysis") or {}
    analysis = csv_analysis.get("analysis") or {}
    return analysis.get("files_used") or {}


def _latest_completed_daily_reference(daily_rows: list[dict], current_price: float | None) -> list[dict]:
    if not daily_rows:
        return []

    latest = daily_rows[-1]
    ref_time = latest.get("time")

    return [
        {
            "key": "pdh",
            "label": LIQUIDITY_REFERENCE_LABELS["pdh"],
            "side": "above",
            "price": latest.get("high"),
            "reference_time": ref_time.isoformat() if ref_time else None,
            "untouched": bool(current_price is not None and current_price < latest.get("high")),
        },
        {
            "key": "pdl",
            "label": LIQUIDITY_REFERENCE_LABELS["pdl"],
            "side": "below",
            "price": latest.get("low"),
            "reference_time": ref_time.isoformat() if ref_time else None,
            "untouched": bool(current_price is not None and current_price > latest.get("low")),
        },
    ]


def _previous_week_references(daily_rows: list[dict], current_price: float | None) -> list[dict]:
    if not daily_rows:
        return []

    latest_time = daily_rows[-1].get("time")

    if not latest_time:
        return []

    current_week_start = latest_time.date() - timedelta(days=latest_time.weekday())
    previous_week_start = current_week_start - timedelta(days=7)
    previous_week_end = current_week_start

    week_rows = [
        row for row in daily_rows
        if previous_week_start <= row["time"].date() < previous_week_end
    ]

    if not week_rows:
        return []

    week_high = max(row["high"] for row in week_rows)
    week_low = min(row["low"] for row in week_rows)
    week_end_time = week_rows[-1]["time"]
    rows_after = [row for row in daily_rows if row["time"].date() >= current_week_start]
    high_touched = any(row["high"] >= week_high for row in rows_after)
    low_touched = any(row["low"] <= week_low for row in rows_after)

    return [
        {
            "key": "previous_week_high",
            "label": LIQUIDITY_REFERENCE_LABELS["previous_week_high"],
            "side": "above",
            "price": week_high,
            "reference_time": week_end_time.isoformat(),
            "untouched": bool(not high_touched and current_price is not None and current_price < week_high),
        },
        {
            "key": "previous_week_low",
            "label": LIQUIDITY_REFERENCE_LABELS["previous_week_low"],
            "side": "below",
            "price": week_low,
            "reference_time": week_end_time.isoformat(),
            "untouched": bool(not low_touched and current_price is not None and current_price > week_low),
        },
    ]


def _session_window_for_row(row_time: datetime, start: dt_time, end: dt_time) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(row_time.date(), start, tzinfo=row_time.tzinfo)
    end_dt = datetime.combine(row_time.date(), end, tzinfo=row_time.tzinfo)

    if end_dt <= start_dt:
        end_dt += timedelta(days=1)

    if row_time < start_dt:
        start_dt -= timedelta(days=1)
        end_dt -= timedelta(days=1)

    return start_dt, end_dt


def _latest_session_references(
    rows: list[dict],
    *,
    high_key: str,
    low_key: str,
    start: dt_time,
    end: dt_time,
    current_price: float | None,
) -> list[dict]:
    if not rows:
        return []

    latest_time = rows[-1]["time"]
    start_dt, end_dt = _session_window_for_row(latest_time, start, end)

    if latest_time < end_dt:
        start_dt -= timedelta(days=1)
        end_dt -= timedelta(days=1)

    session_rows = [
        row for row in rows
        if start_dt <= row["time"] <= end_dt
    ]

    if not session_rows:
        return []

    high = max(row["high"] for row in session_rows)
    low = min(row["low"] for row in session_rows)
    rows_after = [row for row in rows if row["time"] > end_dt]
    high_touched = any(row["high"] >= high for row in rows_after)
    low_touched = any(row["low"] <= low for row in rows_after)

    return [
        {
            "key": high_key,
            "label": LIQUIDITY_REFERENCE_LABELS[high_key],
            "side": "above",
            "price": high,
            "reference_time": end_dt.isoformat(),
            "untouched": bool(not high_touched and current_price is not None and current_price < high),
        },
        {
            "key": low_key,
            "label": LIQUIDITY_REFERENCE_LABELS[low_key],
            "side": "below",
            "price": low,
            "reference_time": end_dt.isoformat(),
            "untouched": bool(not low_touched and current_price is not None and current_price > low),
        },
    ]


def _visible_liquidity_labels(record: dict) -> set[str]:
    visual_context = _record_visual_context(record)
    text = visual_context.get("text_all") or ""
    visible = set()

    checks = {
        "pdh": ["pdh"],
        "pdl": ["pdl"],
        "pdnyh": ["pdnyh"],
        "pdnyl": ["pdnyl"],
        "asia_high": ["asia high", "tokyo high"],
        "asia_low": ["asia low", "tokyo low"],
        "london_high": ["london high"],
        "london_low": ["london low"],
        "previous_week_high": ["previous week high", "pwh"],
        "previous_week_low": ["previous week low", "pwl"],
    }

    for key, terms in checks.items():
        if any(term in text for term in terms):
            visible.add(key)

    return visible


def _liquidity_direction_aligned(side: str, htf_bias: str) -> bool:
    return (
        (htf_bias == "bullish" and side == "above")
        or (htf_bias == "bearish" and side == "below")
    )


def _score_liquidity_reference(reference: dict, current_price: float | None, htf_bias: str) -> dict:
    price = _safe_float(reference.get("price"))
    side = reference.get("side")
    score = 0
    reasons = []

    if price is None or current_price is None:
        return {**reference, "distance": None, "score": 0, "scoring_reasons": ["Missing price context."]}

    distance = abs(current_price - price)
    reference["distance"] = round(distance, 2)

    if reference.get("untouched"):
        score += 50
        reasons.append("Untouched relative to available CSV context.")
    else:
        score -= 20
        reasons.append("Already swept or not cleanly beyond current price.")

    if _liquidity_direction_aligned(side, htf_bias):
        score += 30
        reasons.append(f"Aligned with {htf_bias} HTF bias.")
    elif htf_bias in ["bullish", "bearish"]:
        score -= 10
        reasons.append(f"Counter to {htf_bias} HTF bias.")
    else:
        reasons.append("HTF bias is neutral or unknown.")

    if distance <= 10:
        score += 25
        reasons.append("Nearest meaningful liquidity.")
    elif distance <= 30:
        score += 18
        reasons.append("Nearby liquidity.")
    elif distance <= 75:
        score += 10
        reasons.append("Within reasonable reach.")
    else:
        score -= 5
        reasons.append("Farther from current price.")

    score += LIQUIDITY_IMPORTANCE.get(reference.get("key"), 0)

    if reference.get("visible"):
        score += 8
        reasons.append("Also visible on chart markings.")

    reference["score"] = round(score, 2)
    reference["scoring_reasons"] = _dedupe_text(reasons)

    return reference


def determine_liquidity_draw(record: dict) -> dict:
    csv_analysis = record.get("csv_analysis") or {}
    analysis = csv_analysis.get("analysis") or {}
    context = analysis.get("context") or {}
    state = record.get("state") or extract_structured_state(record)
    files_used = _csv_files_used(record)

    current_price = _safe_float(context.get("current_price"))
    htf_bias = context.get("bias") or state.get("htf_bias") or "unknown"
    execution_bias = context.get("execution_bias") or state.get("execution_bias") or "unknown"
    csv_stale = _csv_is_stale(record)
    visible_keys = _visible_liquidity_labels(record)

    references = []
    daily_rows = _load_csv_rows_from_file(files_used.get("daily"))
    one_minute_rows = _load_csv_rows_from_file(files_used.get("ltf"))

    references.extend(_latest_completed_daily_reference(daily_rows, current_price))
    references.extend(_previous_week_references(daily_rows, current_price))
    references.extend(_latest_session_references(
        one_minute_rows,
        high_key="pdnyh",
        low_key="pdnyl",
        start=dt_time(7, 30),
        end=dt_time(14, 0),
        current_price=current_price,
    ))
    references.extend(_latest_session_references(
        one_minute_rows,
        high_key="asia_high",
        low_key="asia_low",
        start=dt_time(18, 0),
        end=dt_time(23, 59),
        current_price=current_price,
    ))
    references.extend(_latest_session_references(
        one_minute_rows,
        high_key="london_high",
        low_key="london_low",
        start=dt_time(1, 30),
        end=dt_time(9, 29),
        current_price=current_price,
    ))

    scored = []

    for reference in references:
        if reference.get("price") is None:
            continue

        reference["visible"] = reference.get("key") in visible_keys
        scored.append(_score_liquidity_reference(reference, current_price, htf_bias))

    ranked = sorted(scored, key=lambda item: item.get("score", 0), reverse=True)
    primary = ranked[0] if ranked else None
    secondary = ranked[1] if len(ranked) > 1 else None

    reasons = []

    if primary:
        reasons.append(
            f"{primary['label']} ranks highest because it is "
            f"{'untouched' if primary.get('untouched') else 'already contested'}, "
            f"{'aligned' if _liquidity_direction_aligned(primary.get('side'), htf_bias) else 'not aligned'} "
            f"with HTF bias, and {primary.get('distance')} points from current CSV price."
        )
    else:
        reasons.append("No usable liquidity references were available from CSV or visual context.")

    if secondary:
        reasons.append(f"{secondary['label']} is the next strongest reference after the primary draw.")

    if htf_bias in ["bullish", "bearish"]:
        reasons.append(f"HTF bias is {htf_bias}; liquidity in that direction receives priority.")
    else:
        reasons.append("HTF bias is neutral or unknown, so distance and untouched status carry more weight.")

    if execution_bias != htf_bias and execution_bias in ["bullish", "bearish"]:
        reasons.append(f"Execution is {execution_bias}, so the draw is descriptive until structure resolves.")

    if csv_stale:
        reasons.append("CSV is stale; levels remain structural references, but live price relation needs visual confirmation.")

    confidence = "low"

    if primary:
        primary_aligned = _liquidity_direction_aligned(primary.get("side"), htf_bias)
        primary_near = (primary.get("distance") or 9999) <= 75

        if primary.get("untouched") and primary_aligned and primary_near:
            confidence = "high"
        elif primary.get("untouched") or primary_aligned or primary_near:
            confidence = "medium"

    if csv_stale:
        confidence = _downgrade_confidence(confidence)

    return {
        "primary_draw": primary,
        "secondary_draw": secondary,
        "confidence": confidence,
        "reasons": _dedupe_text(reasons),
        "candidates": ranked,
        "does_not_generate_trade_signals": True,
    }


def _format_draw_item(item: dict | None) -> str:
    if not item:
        return "None identified"

    status = "untouched" if item.get("untouched") else "already swept/contested"
    distance = item.get("distance")
    distance_text = f", {distance} points away" if distance is not None else ""
    visible_text = ", visible on chart" if item.get("visible") else ""

    return (
        f"{item.get('label')} at {_fmt_draw_price(item.get('price'))} "
        f"({status}{distance_text}{visible_text})"
    )


def format_liquidity_draw_section(liquidity_draw: dict) -> str:
    confidence = str(liquidity_draw.get("confidence") or "low").capitalize()
    reasons = liquidity_draw.get("reasons") or ["No liquidity draw decision was available."]

    lines = [
        "## Liquidity Draw",
        f"Primary Draw: {_format_draw_item(liquidity_draw.get('primary_draw'))}",
        "",
        f"Secondary Draw: {_format_draw_item(liquidity_draw.get('secondary_draw'))}",
        "",
        f"Confidence: {confidence}",
        "",
        "Reasons:",
    ]
    lines.extend(f"- {item}" for item in reasons)

    return "\n".join(lines)


def attach_liquidity_draw(record: dict) -> None:
    liquidity_draw = determine_liquidity_draw(record)
    record["liquidity_draw"] = liquidity_draw
    record["message"] = (
        (record.get("message") or "")
        + "\n\n"
        + format_liquidity_draw_section(liquidity_draw)
    ).strip()


# -------------------------
# Behavior classification
# -------------------------
BEHAVIOR_CLASSIFICATIONS = {
    "acceptance",
    "rejection",
    "reclaim",
    "sweep",
    "displacement",
    "consolidation",
    "bullish_continuation_compression",
    "bullish_continuation_expansion",
    "unknown",
}

GOLDEN_PATTERN_NAME = "HTF FVG sweep -> 1H reclaim/retest -> 5M continuation breakout"

GOLDEN_PATTERN_STEPS = {
    "sweep_into_htf_fvg": "Price swept/filled into the 4H/1H FVG reaction zone.",
    "reclaim_of_reaction_zone": "Price reclaimed the reaction zone after the FVG interaction.",
    "retest_of_1h_fvg": "Price retested or respected the 1H FVG.",
    "five_min_continuation_fvg": "A 5M FVG is visible as continuation structure.",
    "continuation_breakout": "Price broke away from the 5M continuation FVG.",
}

CONTINUATION_PATTERN_NAME = "Bullish Continuation Compression"

CONTINUATION_PATTERN_STEPS = {
    "htf_bias_bullish": "HTF bias is bullish.",
    "upside_liquidity_draw": "Primary liquidity draw remains above price.",
    "draw_is_pdh_or_prior_high": "Upside draw is PDH or a prior high.",
    "holding_above_key_level": "Price is holding above or around PDH/prior high/key level.",
    "visible_15m_or_5m_fvg": "15M or 5M FVG is visible as continuation structure.",
    "compression_not_rejection": "Behavior is compression/consolidation without clear rejection.",
    "no_clear_5m_breakdown": "5M does not clearly break down.",
}

EXPANSION_PATTERN_NAME = "Bullish Continuation Expansion"

EXPANSION_PATTERN_STEPS = {
    "htf_bias_bullish": "HTF bias is bullish.",
    "upside_liquidity_draw": "Primary liquidity draw remains above price.",
    "compression_context": "Prior or current behavior is bullish continuation compression.",
    "five_min_breakout_or_displacement": "5M shows breakout/displacement away from compression.",
    "holding_above_key_level_or_fvg": "Price is holding above PDH/prior high or continuation FVG.",
    "no_clear_5m_breakdown": "5M does not clearly break down.",
    "news_risk_not_high": "News Risk is not High.",
}


def _visuals_for_timeframe(record: dict, timeframe: str) -> dict:
    timeframe_captures = record.get("timeframe_captures") or {}
    capture = timeframe_captures.get(timeframe) or {}
    visuals = _visuals_from_capture(capture)

    if visuals:
        return visuals

    if record.get("timeframe") == timeframe:
        return (record.get("visual_extraction") or {}).get("visuals") or {}

    return {}


def _behavior_visual_text_from_visuals(visuals: dict) -> str:
    parts = []

    for label in visuals.get("visible_labels") or []:
        parts.append(str(label))

    for key in ["horizontal_lines", "drawn_boxes"]:
        for item in visuals.get(key) or []:
            if isinstance(item, dict):
                parts.extend([
                    str(item.get("label") or ""),
                    str(item.get("location_notes") or ""),
                ])
            else:
                parts.append(str(item))

    for key in ["arrows_or_annotations", "notes_about_user_markings"]:
        for item in visuals.get(key) or []:
            parts.append(str(item))

    return " ".join(part for part in parts if part).lower()


def _behavior_text_by_timeframe(record: dict) -> dict[str, str]:
    return {
        timeframe: _behavior_visual_text_from_visuals(_visuals_for_timeframe(record, timeframe))
        for timeframe in ["15M", "5M", "1M"]
    }


def _count_terms(text: str, terms: list[str]) -> int:
    return sum(1 for term in terms if term in text)


def _append_term_evidence(evidence: list[str], label: str, text: str, terms: list[str]) -> int:
    matches = [term for term in terms if term in text]

    if matches:
        evidence.append(f"{label} visual text includes: {', '.join(matches[:4])}.")

    return len(matches)


def _behavior_term_matches(text: str, terms: list[str]) -> list[str]:
    return [term for term in terms if term in text]


def _format_reaction_zone(zone: dict | None) -> str:
    if not zone:
        return "Unclear"

    timeframe = str(zone.get("timeframe") or "HTF")
    zone_type = str(zone.get("type") or "").strip()
    low = _fmt_draw_price(zone.get("low"))
    high = _fmt_draw_price(zone.get("high"))

    label = f"{timeframe} {zone_type} FVG".strip()

    if low != "unknown" and high != "unknown":
        return f"{label} {low}-{high}"

    return label


def _visual_fvg_timeframe_from_text(text: str) -> str | None:
    checks = [
        ("4H", ["4h fvg", "4hr fvg", "4 hour fvg", "4-hour fvg"]),
        ("1H", ["1h fvg", "1hr fvg", "1 hour fvg", "1-hour fvg"]),
        ("15M", ["15m fvg", "15min fvg", "15 minute fvg", "15-minute fvg"]),
        ("5M", ["5m fvg", "5min fvg", "5 min fvg", "5 minute fvg", "5-minute fvg"]),
    ]

    for timeframe, terms in checks:
        if any(term in text for term in terms):
            return timeframe

    if "fvg" in text:
        return "Visual"

    return None


def _visual_item_prices(item: dict) -> list[float]:
    prices = []

    for key in ["approx_low", "approx_high", "approx_price", "low", "high", "price"]:
        value = _safe_float(item.get(key))

        if value is not None:
            prices.append(value)

    return prices


def _range_prices_near_fvg(visuals: dict, fvg_prices: list[float]) -> list[float]:
    nearby = []

    if not fvg_prices:
        return nearby

    for key in ["horizontal_lines", "drawn_boxes"]:
        for item in visuals.get(key) or []:
            if not isinstance(item, dict):
                continue

            label = str(item.get("label") or "").lower()
            notes = str(item.get("location_notes") or "").lower()

            if "range" not in f"{label} {notes}":
                continue

            for price in _visual_item_prices(item):
                if any(abs(price - fvg_price) <= 6 for fvg_price in fvg_prices):
                    nearby.append(price)

    return nearby


def _format_visual_zone_bounds(prices: list[float]) -> str:
    if not prices:
        return ""

    low = min(prices)
    high = max(prices)

    if low == high:
        low -= 2
        high += 2
    elif high - low < 4:
        low -= 2

    return f" around {_fmt_draw_price(low)}-{_fmt_draw_price(high)}"


def _visual_reaction_zone(record: dict) -> dict | None:
    candidates = []
    priority = {"4H": 0, "1H": 1, "15M": 2, "Visual": 3}

    for capture_timeframe in ["15M", "5M", "1M"]:
        visuals = _visuals_for_timeframe(record, capture_timeframe)

        if not visuals:
            continue

        for key in ["drawn_boxes", "horizontal_lines"]:
            for item in visuals.get(key) or []:
                if not isinstance(item, dict):
                    continue

                text = " ".join([
                    str(item.get("label") or ""),
                    str(item.get("location_notes") or ""),
                    str(item.get("color") or ""),
                ]).lower()
                timeframe = _visual_fvg_timeframe_from_text(text)

                if not timeframe:
                    continue

                fvg_prices = _visual_item_prices(item)
                prices = fvg_prices + _range_prices_near_fvg(visuals, fvg_prices)
                candidates.append({
                    "timeframe": timeframe,
                    "capture_timeframe": capture_timeframe,
                    "prices": prices,
                    "label": str(item.get("label") or f"{timeframe} FVG"),
                })

        visual_text = _behavior_visual_text_from_visuals(visuals)
        text_timeframe = _visual_fvg_timeframe_from_text(visual_text)

        if text_timeframe and not any(
            item.get("timeframe") == text_timeframe and item.get("capture_timeframe") == capture_timeframe
            for item in candidates
        ):
            candidates.append({
                "timeframe": text_timeframe,
                "capture_timeframe": capture_timeframe,
                "prices": _range_prices_near_fvg(visuals, []),
                "label": f"{text_timeframe} FVG",
            })

    if not candidates:
        return None

    capture_priority = ["15M", "5M", "1M"]
    candidates.sort(
        key=lambda item: (
            priority.get(item.get("timeframe"), 9),
            capture_priority.index(item.get("capture_timeframe")),
        )
    )
    best_priority = priority.get(candidates[0].get("timeframe"), 9)
    best = [
        item for item in candidates
        if priority.get(item.get("timeframe"), 9) == best_priority
    ]
    timeframes = _dedupe_text([str(item.get("timeframe")) for item in best if item.get("timeframe")])
    all_prices = []

    for item in best:
        all_prices.extend(item.get("prices") or [])

    timeframe_label = "/".join(
        timeframe for timeframe in timeframes
        if str(timeframe).lower() != "visual"
    )
    label_prefix = f"Visual {timeframe_label}".strip()

    return {
        "source": "visual",
        "label": f"{label_prefix} FVG{_format_visual_zone_bounds(all_prices)}",
        "timeframes": timeframes,
        "prices": all_prices,
    }


def _active_reaction_zone(record: dict, visual_text_all: str) -> tuple[str, dict | None, str]:
    csv_stale = _csv_is_stale(record)
    visual_zone = _visual_reaction_zone(record)

    if csv_stale and visual_zone:
        return visual_zone.get("label") or "Visual FVG", visual_zone, "visual"

    csv_analysis = record.get("csv_analysis") or {}
    analysis = csv_analysis.get("analysis") or {}
    zone_ranking = analysis.get("zone_ranking") or {}
    active_zone = zone_ranking.get("active_zone") or {}

    if active_zone:
        return _format_reaction_zone(active_zone), active_zone, "csv"

    visual_candidates = []
    for timeframe in ["15M", "5M"]:
        timeframe_label = timeframe.lower()
        alternate_label = timeframe_label.replace("h", "hr")

        if f"{timeframe_label} fvg" in visual_text_all or f"{alternate_label} fvg" in visual_text_all:
            visual_candidates.append(f"{timeframe} FVG")

    if visual_candidates:
        return " / ".join(visual_candidates), None, "visual"

    if "fvg" in visual_text_all:
        return "Visible FVG", None, "visual"

    return "Unclear", None, "unclear"


def _behavior_location(record: dict, active_zone: dict | None, visual_text_all: str) -> str:
    parts = []
    state = record.get("state") or extract_structured_state(record)
    price_relation = state.get("price_relation")
    primary_draw = (record.get("liquidity_draw") or {}).get("primary_draw") or {}

    relation_labels = {
        "inside_active_zone": "inside active FVG reaction zone",
        "above_active_zone": "above active FVG reaction zone",
        "below_active_zone": "below active FVG reaction zone",
    }

    if active_zone and active_zone.get("source") == "visual":
        timeframes = "/".join(active_zone.get("timeframes") or []) or "visual"
        parts.append(f"around Visual {timeframes} FVG")
    elif price_relation in relation_labels:
        parts.append(relation_labels[price_relation])
    elif active_zone and active_zone.get("relation_to_price"):
        relation = str(active_zone.get("relation_to_price")).replace("_", " ")
        parts.append(f"{relation} relative to active FVG reaction zone")

    draw_label = primary_draw.get("label")
    if draw_label:
        if primary_draw.get("untouched") is False:
            parts.append(f"through/taken {draw_label}")
        elif primary_draw.get("side") == "above":
            parts.append(f"below {draw_label}")
        elif primary_draw.get("side") == "below":
            parts.append(f"above {draw_label}")

    for key, label in [
        ("pdh", "PDH"),
        ("pdl", "PDL"),
        ("pdnyh", "PDNYH"),
        ("pdnyl", "PDNYL"),
        ("asia high", "Asia High"),
        ("asia low", "Asia Low"),
        ("london high", "London High"),
        ("london low", "London Low"),
    ]:
        if key in visual_text_all and label not in " / ".join(parts):
            parts.append(f"around {label}")

    if not parts:
        return "Unclear"

    return " / ".join(_dedupe_text(parts[:3]))


def _liquidity_draw_status(record: dict, visual_text_all: str) -> tuple[str, list[str]]:
    liquidity_draw = record.get("liquidity_draw") or {}
    primary = liquidity_draw.get("primary_draw") or {}
    candidates = liquidity_draw.get("candidates") or []
    evidence = []

    taken_terms = [
        "sweep",
        "swept",
        "raid",
        "liquidity taken",
        "took liquidity",
        "ran stops",
        "stop run",
        "taken",
    ]

    if not primary:
        return "unclear", ["No primary liquidity draw was available."]

    label = primary.get("label") or "Primary draw"
    primary_taken_visually = (
        str(primary.get("key") or "").replace("_", " ") in visual_text_all
        and _contains_any(visual_text_all, taken_terms)
    )

    if primary.get("untouched") is False or primary_taken_visually:
        evidence.append(f"{label} appears swept/contested, so the draw may be fulfilled.")
        return "fulfilled", evidence

    if primary.get("untouched") is True:
        evidence.append(f"{label} remains the active draw in available context.")

    taken_candidates = [
        item for item in candidates
        if item.get("untouched") is False
        and item.get("key") in {
            "pdh",
            "pdl",
            "pdnyh",
            "pdnyl",
            "asia_high",
            "asia_low",
            "london_high",
            "london_low",
        }
    ]

    for item in taken_candidates[:2]:
        evidence.append(f"{item.get('label')} has already been swept/contested in available liquidity context.")

    return "active", evidence


def _structure_confirmation(visual_text_5m: str) -> tuple[str, bool, list[str]]:
    if not visual_text_5m:
        return "5M unavailable", False, ["5M structure confirmation is missing."]

    confirmation_terms = [
        "mss",
        "bos",
        "market structure shift",
        "break of structure",
        "displacement",
        "reclaim",
        "reclaimed",
        "holding above",
        "holding below",
        "reject",
        "rejected",
    ]
    unclear_terms = ["range", "chop", "sideways", "unclear", "balanced", "consolidation"]

    matches = _behavior_term_matches(visual_text_5m, confirmation_terms)

    if matches:
        return f"5M confirms: {', '.join(matches[:3])}", True, []

    if _contains_any(visual_text_5m, unclear_terms):
        return "5M unclear", False, ["5M shows range/unclear structure rather than confirmation."]

    return "5M unclear", False, ["5M visual context is present but does not confirm MSS/BOS, reclaim, rejection, or hold."]


def _has_visual_fvg_for_timeframe(text: str, timeframe: str) -> bool:
    terms_by_timeframe = {
        "4H": ["4h fvg", "4hr fvg", "4 hour fvg", "4-hour fvg"],
        "1H": ["1h fvg", "1hr fvg", "1 hour fvg", "1-hour fvg"],
        "15M": ["15m fvg", "15min fvg", "15 min fvg", "15 minute fvg", "15-minute fvg"],
        "5M": ["5m fvg", "5min fvg", "5 min fvg", "5 minute fvg", "5-minute fvg"],
    }

    return _contains_any(text, terms_by_timeframe.get(timeframe, []))


def _csv_has_fvg_timeframe(record: dict, timeframe: str) -> bool:
    analysis = (record.get("csv_analysis") or {}).get("analysis") or {}
    zone_ranking = analysis.get("zone_ranking") or {}
    zones = []
    zones.extend(zone_ranking.get("all_ranked_zones") or [])

    active_zone = zone_ranking.get("active_zone")
    if active_zone:
        zones.append(active_zone)

    for zone in zones:
        if str(zone.get("timeframe") or "").upper() == timeframe and zone.get("low") is not None and zone.get("high") is not None:
            return True

    return False


def _detect_golden_pattern_match(
    record: dict,
    text_by_timeframe: dict[str, str],
    *,
    liquidity_draw_status: str,
    has_5m_confirmation: bool,
) -> dict:
    visual_text_4h = text_by_timeframe.get("4H", "")
    visual_text_1h = text_by_timeframe.get("1H", "")
    visual_text_15m = text_by_timeframe.get("15M", "")
    visual_text_5m = text_by_timeframe.get("5M", "")
    visual_text_htf = " ".join(text for text in [visual_text_4h, visual_text_1h] if text)
    visual_text_ltf = " ".join(text for text in [visual_text_15m, visual_text_5m] if text)
    visual_text_all = " ".join(text for text in text_by_timeframe.values() if text)
    state = record.get("state") or extract_structured_state(record)
    price_relation = str(state.get("price_relation") or "")

    has_4h_fvg = _has_visual_fvg_for_timeframe(visual_text_all, "4H") or _csv_has_fvg_timeframe(record, "4H")
    has_1h_fvg = _has_visual_fvg_for_timeframe(visual_text_all, "1H") or _csv_has_fvg_timeframe(record, "1H")
    has_5m_fvg = _has_visual_fvg_for_timeframe(visual_text_5m, "5M") or _has_visual_fvg_for_timeframe(visual_text_all, "5M")

    fvg_interaction_terms = [
        "sweep",
        "swept",
        "fill",
        "filled",
        "mitigation",
        "mitigated",
        "tap",
        "tapped",
        "inside",
        "into",
        "through",
        "reaction",
    ]
    reclaim_terms = [
        "reclaim",
        "reclaimed",
        "recover",
        "recovered",
        "regained",
        "back above",
        "back below",
        "holding above",
        "hold above",
        "holds above",
        "holding below",
        "hold below",
        "holds below",
        "accepted",
        "acceptance",
        "swept and reclaimed",
    ]
    retest_terms = [
        "retest",
        "retested",
        "test",
        "tested",
        "tap",
        "tapped",
        "respect",
        "respected",
        "defended",
        "holding above",
        "holding below",
        "support",
        "reaction",
    ]
    continuation_fvg_terms = [
        "continuation",
        "continue",
        "5m fvg",
        "5min fvg",
        "5 min fvg",
        "5 minute fvg",
        "5-minute fvg",
    ]
    breakout_terms = [
        "breakout",
        "broke out",
        "break out",
        "break from",
        "break above",
        "break below",
        "bos",
        "mss",
        "break of structure",
        "market structure shift",
        "displacement",
        "expansion",
        "impulse",
        "impulsive",
        "continuation breakout",
    ]

    htf_fvg_interaction = (
        has_4h_fvg
        and has_1h_fvg
        and (
            _contains_any(visual_text_htf or visual_text_all, fvg_interaction_terms)
            or price_relation in ["inside_active_zone", "above_active_zone", "below_active_zone"]
            or liquidity_draw_status == "fulfilled"
        )
    )
    reclaim_of_reaction_zone = (
        (has_4h_fvg or has_1h_fvg)
        and _contains_any(visual_text_all, reclaim_terms)
    )
    retest_of_1h_fvg = (
        has_1h_fvg
        and (
            _contains_any(visual_text_1h or visual_text_all, retest_terms)
            or reclaim_of_reaction_zone
        )
    )
    five_min_continuation_fvg = (
        has_5m_fvg
        and (
            _contains_any(visual_text_ltf or visual_text_all, continuation_fvg_terms)
            or has_5m_confirmation
        )
    )
    continuation_breakout = (
        has_5m_fvg
        and (
            _contains_any(visual_text_ltf or visual_text_all, breakout_terms)
            or (has_5m_confirmation and _contains_any(visual_text_ltf, ["break", "bos", "mss", "displacement", "expansion"]))
        )
    )

    matched_step_keys = [
        step
        for step, matched in [
            ("sweep_into_htf_fvg", htf_fvg_interaction),
            ("reclaim_of_reaction_zone", reclaim_of_reaction_zone),
            ("retest_of_1h_fvg", retest_of_1h_fvg),
            ("five_min_continuation_fvg", five_min_continuation_fvg),
            ("continuation_breakout", continuation_breakout),
        ]
        if matched
    ]
    missing_step_keys = [
        step for step in GOLDEN_PATTERN_STEPS
        if step not in matched_step_keys
    ]

    if len(matched_step_keys) == len(GOLDEN_PATTERN_STEPS):
        confidence = "high"
    elif len(matched_step_keys) >= 3 and (
        five_min_continuation_fvg
        or continuation_breakout
        or reclaim_of_reaction_zone
        or retest_of_1h_fvg
    ):
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "matched": len(missing_step_keys) == 0,
        "pattern_name": GOLDEN_PATTERN_NAME,
        "matched_steps": matched_step_keys,
        "missing_steps": missing_step_keys,
        "confidence": confidence,
    }


def _primary_draw_is_prior_high(primary_draw: dict) -> bool:
    key = str(primary_draw.get("key") or "").lower()
    label = str(primary_draw.get("label") or "").lower()
    high_terms = ["pdh", "high", "previous week high", "pdnyh", "asia high", "london high"]

    return any(term in key or term in label for term in high_terms)


def _detect_continuation_pattern_match(
    record: dict,
    text_by_timeframe: dict[str, str],
    *,
    weighted_scores: dict[str, int],
    explicit_consolidation: bool,
    explicit_rejection: bool,
    has_5m_confirmation: bool,
) -> dict:
    state = record.get("state") or extract_structured_state(record)
    liquidity_draw = record.get("liquidity_draw") or {}
    primary_draw = liquidity_draw.get("primary_draw") or {}
    htf_bias = str(state.get("htf_bias") or "unknown").lower()
    price_relation = str(state.get("price_relation") or "")
    visual_text_15m = text_by_timeframe.get("15M", "")
    visual_text_5m = text_by_timeframe.get("5M", "")
    visual_text_all = " ".join(text for text in text_by_timeframe.values() if text)

    htf_bias_bullish = htf_bias == "bullish"
    upside_liquidity_draw = primary_draw.get("side") == "above" and primary_draw.get("untouched") is not False
    draw_is_pdh_or_prior_high = upside_liquidity_draw and _primary_draw_is_prior_high(primary_draw)
    visible_15m_or_5m_fvg = (
        _has_visual_fvg_for_timeframe(visual_text_15m, "15M")
        or _has_visual_fvg_for_timeframe(visual_text_5m, "5M")
        or _has_visual_fvg_for_timeframe(visual_text_all, "15M")
        or _has_visual_fvg_for_timeframe(visual_text_all, "5M")
    )
    holding_terms = [
        "holding above",
        "hold above",
        "holds above",
        "above pdh",
        "above high",
        "above previous high",
        "above prior high",
        "support",
        "defended",
        "accepted",
        "acceptance",
    ]
    key_level_terms = ["pdh", "previous high", "prior high", "pdnyh", "asia high", "london high"]
    holding_above_key_level = (
        price_relation in ["above_active_zone", "inside_active_zone"]
        or _contains_any(visual_text_all, holding_terms)
        or (_contains_any(visual_text_all, key_level_terms) and primary_draw.get("side") == "above")
    )
    compression_terms = [
        "range",
        "chop",
        "sideways",
        "balanced",
        "consolidation",
        "compress",
        "compression",
        "inside range",
        "avg:",
        "range:",
    ]
    compression_not_rejection = (
        (explicit_consolidation or weighted_scores.get("consolidation", 0) > 0 or _contains_any(visual_text_all, compression_terms))
        and not explicit_rejection
        and weighted_scores.get("rejection", 0) == 0
    )
    breakdown_terms = [
        "breakdown",
        "broke down",
        "break down",
        "lost support",
        "lost level",
        "failed support",
        "below pdh",
        "below prior high",
        "below previous high",
        "reject",
        "rejected",
        "rejection",
    ]
    no_clear_5m_breakdown = not _contains_any(visual_text_5m, breakdown_terms)

    matched_step_keys = [
        step
        for step, matched in [
            ("htf_bias_bullish", htf_bias_bullish),
            ("upside_liquidity_draw", upside_liquidity_draw),
            ("draw_is_pdh_or_prior_high", draw_is_pdh_or_prior_high),
            ("holding_above_key_level", holding_above_key_level),
            ("visible_15m_or_5m_fvg", visible_15m_or_5m_fvg),
            ("compression_not_rejection", compression_not_rejection),
            ("no_clear_5m_breakdown", no_clear_5m_breakdown),
        ]
        if matched
    ]
    missing_step_keys = [
        step for step in CONTINUATION_PATTERN_STEPS
        if step not in matched_step_keys
    ]
    matched = bool(
        htf_bias_bullish
        and visible_15m_or_5m_fvg
        and compression_not_rejection
        and no_clear_5m_breakdown
        and (upside_liquidity_draw or holding_above_key_level)
    )

    if has_5m_confirmation and matched and holding_above_key_level and upside_liquidity_draw:
        confidence = "high"
    elif matched and upside_liquidity_draw and holding_above_key_level:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "matched": matched,
        "pattern_name": CONTINUATION_PATTERN_NAME,
        "matched_steps": matched_step_keys,
        "missing_steps": missing_step_keys,
        "confidence": confidence,
    }


def _csv_fresh_or_recent(record: dict) -> bool:
    freshness = record.get("csv_freshness") or {}

    if not isinstance(freshness, dict):
        return False

    for timeframe in HTF_CSV_TIMEFRAMES:
        item = freshness.get(timeframe) or {}

        if not isinstance(item, dict):
            continue

        age_minutes = _safe_float(item.get("age_minutes"))
        threshold_minutes = _safe_float(item.get("threshold_minutes"))

        if item.get("is_stale") is False:
            return True

        if age_minutes is not None and threshold_minutes is not None and age_minutes <= threshold_minutes * 2:
            return True

    return False


def _detect_expansion_pattern_match(
    record: dict,
    text_by_timeframe: dict[str, str],
    *,
    continuation_pattern_match: dict,
    has_5m_confirmation: bool,
    news_risk_level: str,
) -> dict:
    state = record.get("state") or extract_structured_state(record)
    liquidity_draw = record.get("liquidity_draw") or {}
    primary_draw = liquidity_draw.get("primary_draw") or {}
    prior_behavior = record.get("behavior_classification") or {}
    prior_classification = str(prior_behavior.get("classification") or "").lower()
    htf_bias = str(state.get("htf_bias") or "unknown").lower()
    price_relation = str(state.get("price_relation") or "")
    visual_text_15m = text_by_timeframe.get("15M", "")
    visual_text_5m = text_by_timeframe.get("5M", "")
    visual_text_all = " ".join(text for text in text_by_timeframe.values() if text)

    htf_bias_bullish = htf_bias == "bullish"
    upside_liquidity_draw = primary_draw.get("side") == "above" and primary_draw.get("untouched") is not False
    compression_context = (
        prior_classification == "bullish_continuation_compression"
        or bool(continuation_pattern_match.get("matched"))
    )
    breakout_terms = [
        "breakout",
        "broke out",
        "break out",
        "break above",
        "bos",
        "mss",
        "break of structure",
        "market structure shift",
        "displacement",
        "expansion",
        "impulse",
        "impulsive",
        "strong move",
        "breakaway",
    ]
    five_min_breakout_or_displacement = _contains_any(visual_text_5m, breakout_terms) or (
        has_5m_confirmation
        and _contains_any(visual_text_5m, ["break", "bos", "mss", "displacement", "expansion"])
    )
    holding_terms = [
        "holding above",
        "hold above",
        "holds above",
        "above pdh",
        "above high",
        "above previous high",
        "above prior high",
        "support",
        "defended",
        "accepted",
        "acceptance",
        "reclaimed",
        "5m fvg",
        "5min fvg",
        "15m fvg",
        "15min fvg",
    ]
    holding_above_key_level_or_fvg = (
        price_relation in ["above_active_zone", "inside_active_zone"]
        or _contains_any(visual_text_all, holding_terms)
        or _has_visual_fvg_for_timeframe(visual_text_15m, "15M")
        or _has_visual_fvg_for_timeframe(visual_text_5m, "5M")
    )
    breakdown_terms = [
        "breakdown",
        "broke down",
        "break down",
        "lost support",
        "lost level",
        "failed support",
        "below pdh",
        "below prior high",
        "below previous high",
        "reject",
        "rejected",
        "rejection",
    ]
    no_clear_5m_breakdown = not _contains_any(visual_text_5m, breakdown_terms)
    news_risk_not_high = news_risk_level != "high"

    matched_step_keys = [
        step
        for step, matched in [
            ("htf_bias_bullish", htf_bias_bullish),
            ("upside_liquidity_draw", upside_liquidity_draw),
            ("compression_context", compression_context),
            ("five_min_breakout_or_displacement", five_min_breakout_or_displacement),
            ("holding_above_key_level_or_fvg", holding_above_key_level_or_fvg),
            ("no_clear_5m_breakdown", no_clear_5m_breakdown),
            ("news_risk_not_high", news_risk_not_high),
        ]
        if matched
    ]
    missing_step_keys = [
        step for step in EXPANSION_PATTERN_STEPS
        if step not in matched_step_keys
    ]
    matched = bool(
        htf_bias_bullish
        and upside_liquidity_draw
        and compression_context
        and five_min_breakout_or_displacement
        and holding_above_key_level_or_fvg
        and no_clear_5m_breakdown
        and news_risk_not_high
    )

    if matched and has_5m_confirmation and _csv_fresh_or_recent(record):
        confidence = "high"
    elif matched:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "matched": matched,
        "pattern_name": EXPANSION_PATTERN_NAME,
        "matched_steps": matched_step_keys,
        "missing_steps": missing_step_keys,
        "confidence": confidence,
    }


def _get_csv_refresh_limitation() -> str | None:
    try:
        from csv_refresh import get_csv_refresh_status

        status = get_csv_refresh_status()
    except Exception as e:
        return f"CSV refresh status unavailable: {e}"

    if not isinstance(status, dict):
        return "CSV refresh status is unavailable or malformed."

    if not status.get("last_success"):
        last_error = status.get("last_error")

        if last_error:
            return f"CSV refresh has no successful run yet; latest status: {last_error}"

        return "CSV refresh has no successful run yet."

    if status.get("last_error"):
        return f"CSV refresh latest error: {status.get('last_error')}"

    return None


def _cap_confidence_for_context(
    confidence: str,
    *,
    htf_bias: str,
    execution_bias: str,
    csv_stale: bool,
    live_visual_clear: bool,
    strong_visual_evidence: bool,
    has_5m_confirmation: bool,
    news_risk_level: str,
) -> str:
    capped = confidence

    if htf_bias != execution_bias and htf_bias in ["bullish", "bearish"] and execution_bias in ["bullish", "bearish"]:
        if capped == "high":
            capped = "medium"

    if csv_stale:
        if strong_visual_evidence:
            if capped == "high":
                capped = "medium"
        elif not live_visual_clear:
            capped = "low"
        else:
            capped = _downgrade_confidence(capped)

    if not has_5m_confirmation and capped == "high":
        capped = "medium"

    if news_risk_level == "high":
        capped = _downgrade_confidence(capped)

    return capped


def classify_behavior(record: dict) -> dict:
    state = record.get("state") or extract_structured_state(record)
    htf_bias = state.get("htf_bias", "unknown")
    execution_bias = state.get("execution_bias", "unknown")
    liquidity_draw = record.get("liquidity_draw") or {}
    primary_draw = liquidity_draw.get("primary_draw") or {}
    csv_stale = _csv_is_stale(record)
    news_risk_level = _news_risk_level(record)

    text_by_timeframe = _behavior_text_by_timeframe(record)
    visual_text_15m = text_by_timeframe.get("15M", "")
    visual_text_5m = text_by_timeframe.get("5M", "")
    visual_text_all = " ".join(text for text in text_by_timeframe.values() if text)

    evidence = []
    missing_confirmation = []
    data_limitations = []
    reaction_zone, active_zone, reaction_zone_source = _active_reaction_zone(record, visual_text_all)
    stale_zone_guardrail = _stale_csv_zone_guardrail(record, active_zone, visual_text_all)
    behavior_location = _behavior_location(record, active_zone, visual_text_all)
    liquidity_draw_status, draw_status_evidence = _liquidity_draw_status(record, visual_text_all)
    structure_confirmation, has_5m_confirmation, structure_missing = _structure_confirmation(visual_text_5m)
    golden_pattern_match = _detect_golden_pattern_match(
        record,
        text_by_timeframe,
        liquidity_draw_status=liquidity_draw_status,
        has_5m_confirmation=has_5m_confirmation,
    )

    behavior_terms = {
        "acceptance": [
            "acceptance",
            "accepted",
            "holding above",
            "hold above",
            "holds above",
            "holding below",
            "hold below",
            "holds below",
            "respect",
            "respected",
            "support",
            "defended",
        ],
        "rejection": [
            "rejection",
            "reject",
            "rejected",
            "failure",
            "failed",
            "unable to hold",
            "lost level",
            "below level",
            "resistance",
            "supply",
            "movement away",
            "away from",
            "failed continuation",
            "continuation failed",
        ],
        "reclaim": [
            "reclaim",
            "reclaimed",
            "recovered",
            "regained",
            "back above",
            "back below",
            "taken and recovered",
            "swept and reclaimed",
        ],
        "sweep": [
            "sweep",
            "swept",
            "raid",
            "liquidity taken",
            "took liquidity",
            "stop run",
            "ran stops",
            "taken but not recovered",
        ],
        "displacement": [
            "displacement",
            "impulse",
            "impulsive",
            "strong move",
            "expansion",
            "breakaway",
            "large candle",
            "aggressive move",
            "mss",
            "bos",
            "market structure shift",
            "break of structure",
        ],
        "consolidation": [
            "range",
            "chop",
            "sideways",
            "balanced",
            "consolidation",
            "compress",
            "compression",
            "inside range",
            "avg:",
            "range:",
        ],
    }

    timeframe_weights = {
        "15M": 3,
        "5M": 2,
    }
    weighted_scores = {classification: 0 for classification in BEHAVIOR_CLASSIFICATIONS}

    for classification, terms in behavior_terms.items():
        matches_15m = _behavior_term_matches(visual_text_15m, terms)
        matches_5m = _behavior_term_matches(visual_text_5m, terms)
        weighted_scores[classification] = (
            len(matches_15m) * timeframe_weights["15M"]
            + min(len(matches_5m), 2) * timeframe_weights["5M"]
        )

        if matches_15m:
            evidence.append(f"15M behavior evidence for {classification}: {', '.join(matches_15m[:4])}.")
        if matches_5m:
            evidence.append(f"5M structure evidence for {classification}: {', '.join(matches_5m[:4])}.")

    has_reaction_zone = _contains_any(
        visual_text_all,
        ["fvg", "pd h", "pdh", "pdl", "pdnyh", "pdnyl", "previous week", "asia", "london"],
    )
    has_directional_behavior = any(
        weighted_scores[item] > 0
        for item in ["acceptance", "rejection", "reclaim", "sweep", "displacement"]
    )
    has_15m_directional_behavior = any(
        _behavior_term_matches(visual_text_15m, behavior_terms[item])
        for item in ["acceptance", "rejection", "reclaim", "sweep", "displacement"]
    )

    evidence.append("Framework hierarchy: HTF CSV map -> 15M live context -> 5M structure -> conditional 1M execution confirmation.")
    evidence.append(f"Reaction zone is treated as decision context, not an entry signal: {reaction_zone}.")
    evidence.extend(stale_zone_guardrail.get("evidence") or [])
    if state.get("price_relation") == "inside_active_zone" and not has_directional_behavior:
        evidence.append(
            "Price is interacting with a reaction zone; behavior must confirm acceptance/rejection before this becomes alert-worthy."
        )

    if reaction_zone_source == "visual":
        evidence.append("CSV is stale and visual FVG markings are available, so behavior classification anchors to the visual reaction zone.")

    evidence.extend(draw_status_evidence)

    if primary_draw:
        evidence.append(
            f"Primary liquidity draw is {primary_draw.get('label')} at {_fmt_draw_price(primary_draw.get('price'))}."
        )

    if htf_bias != "unknown" or execution_bias != "unknown":
        evidence.append(f"Bias context: HTF {htf_bias}, execution {execution_bias}.")

    if structure_missing:
        missing_confirmation.extend(structure_missing)

    explicit_reclaim = weighted_scores["reclaim"] > 0 and (
        weighted_scores["sweep"] > 0
        or _contains_any(visual_text_all, ["lost", "swept", "taken", "raid"])
        or liquidity_draw_status == "fulfilled"
    )
    explicit_sweep = weighted_scores["sweep"] > 0 or (
        liquidity_draw_status == "fulfilled"
        and not _contains_any(visual_text_all, ["reclaim", "reclaimed", "regained", "recovered", "back above", "back below"])
    )
    explicit_acceptance = weighted_scores["acceptance"] > 0 and has_reaction_zone
    explicit_rejection = weighted_scores["rejection"] > 0 and has_reaction_zone
    explicit_displacement = weighted_scores["displacement"] > 0 and (
        has_reaction_zone or _contains_any(visual_text_all, ["away from", "breakaway", "expansion"])
    )
    explicit_consolidation = weighted_scores["consolidation"] > 0 and (
        has_reaction_zone or not has_directional_behavior
    )
    continuation_pattern_match = _detect_continuation_pattern_match(
        record,
        text_by_timeframe,
        weighted_scores=weighted_scores,
        explicit_consolidation=explicit_consolidation,
        explicit_rejection=explicit_rejection,
        has_5m_confirmation=has_5m_confirmation,
    )
    expansion_pattern_match = _detect_expansion_pattern_match(
        record,
        text_by_timeframe,
        continuation_pattern_match=continuation_pattern_match,
        has_5m_confirmation=has_5m_confirmation,
        news_risk_level=news_risk_level,
    )
    golden_steps = set(golden_pattern_match.get("matched_steps") or [])
    golden_reclaim_or_retest = bool(
        "sweep_into_htf_fvg" in golden_steps
        and (
            "reclaim_of_reaction_zone" in golden_steps
            or "retest_of_1h_fvg" in golden_steps
        )
    )
    golden_continuation_breakout = bool(
        "five_min_continuation_fvg" in golden_steps
        and "continuation_breakout" in golden_steps
    )

    if golden_reclaim_or_retest and not explicit_reclaim:
        explicit_reclaim = True
        evidence.append("Golden pattern logic: HTF/1H FVG interaction plus reclaim/retest evidence upgrades behavior toward reclaim.")

    if golden_continuation_breakout and not explicit_displacement:
        explicit_displacement = True
        evidence.append("Golden pattern logic: 5M continuation FVG plus breakout evidence upgrades behavior toward displacement.")

    if continuation_pattern_match.get("matched") and explicit_consolidation:
        evidence.append("Continuation pattern logic: compression is aligned with bullish HTF bias, upside liquidity, and visible 15M/5M FVG context.")

    if expansion_pattern_match.get("matched"):
        evidence.append("Expansion pattern logic: bullish compression context has 5M breakout/displacement evidence without a clear breakdown.")

    if stale_zone_guardrail.get("block_bullish_execution_watch") and expansion_pattern_match.get("matched"):
        expansion_pattern_match = {
            **expansion_pattern_match,
            "matched": False,
            "confidence": "low",
            "missing_steps": _dedupe_text(
                list(expansion_pattern_match.get("missing_steps") or [])
                + ["stale_csv_bullish_zone_reclaim"]
            ),
        }
        evidence.append("Stale CSV guardrail blocked bullish expansion: live price is below the referenced bullish zone and reclaim is needed first.")

    if stale_zone_guardrail.get("block_bullish_execution_watch") and continuation_pattern_match.get("matched"):
        continuation_pattern_match = {
            **continuation_pattern_match,
            "matched": False,
            "confidence": "low",
            "missing_steps": _dedupe_text(
                list(continuation_pattern_match.get("missing_steps") or [])
                + ["stale_csv_bullish_zone_reclaim"]
            ),
        }
        evidence.append("Stale CSV guardrail blocked bullish continuation: live price is below the referenced bullish zone and reclaim is needed first.")

    if stale_zone_guardrail.get("block_bullish_execution_watch"):
        classification = "displacement" if explicit_displacement else "rejection"
        evidence.append("Behavior logic: stale CSV bullish support is not active while live price is below it; classify as bearish intraday displacement/rejection until reclaim.")
    elif expansion_pattern_match.get("matched"):
        classification = "bullish_continuation_expansion"
        evidence.append("Behavior logic: bullish continuation compression is expanding away from the 5M structure.")
    elif explicit_displacement and golden_continuation_breakout:
        classification = "displacement"
        evidence.append("Behavior logic: the golden-pattern continuation leg shows breakout/displacement from the 5M FVG.")
    elif explicit_reclaim:
        classification = "reclaim"
        evidence.append("Behavior logic: liquidity was swept/lost and then regained in the available visual context.")
    elif explicit_rejection:
        classification = "rejection"
        evidence.append("Behavior logic: price failed to hold the marked zone/level and moved or is described away from it.")
    elif explicit_acceptance:
        classification = "acceptance"
        evidence.append("Behavior logic: price appears to hold beyond or respect a key level/FVG after interaction.")
    elif explicit_sweep:
        classification = "sweep"
        evidence.append("Behavior logic: liquidity appears taken, but no clear reclaim is visible yet.")
    elif explicit_displacement:
        classification = "displacement"
        evidence.append("Behavior logic: visual context describes a strong directional move away from the zone/level.")
    elif continuation_pattern_match.get("matched") and explicit_consolidation:
        classification = "bullish_continuation_compression"
        evidence.append("Behavior logic: price is compressing in bullish continuation context rather than neutral consolidation.")
    elif explicit_consolidation:
        classification = "consolidation"
        evidence.append("Behavior logic: price appears to be ranging or compressing around the marked zone/level.")
    elif has_reaction_zone:
        classification = "unknown"
        evidence.append("Visuals show marked levels/zones, but no clear hold, fail, reclaim, sweep, displacement, or consolidation behavior.")
    else:
        classification = "unknown"
        evidence.append("No reaction zone or behavior-specific visual evidence was clear enough to classify.")

    if classification not in BEHAVIOR_CLASSIFICATIONS:
        classification = "unknown"

    classification_score = weighted_scores.get(classification, 0)
    if classification == "unknown":
        confidence = "low"
    elif classification == "bullish_continuation_expansion":
        confidence = str(expansion_pattern_match.get("confidence") or "medium")
    elif classification == "bullish_continuation_compression":
        confidence = str(continuation_pattern_match.get("confidence") or "low")
    elif classification_score >= 7 and has_15m_directional_behavior and has_5m_confirmation:
        confidence = "high"
    elif classification_score >= 3 or has_15m_directional_behavior:
        confidence = "medium"
    else:
        confidence = "low"

    if classification == "acceptance":
        missing_confirmation.append("Need repeated live candles holding beyond the level or zone.")
    elif classification == "rejection":
        missing_confirmation.append("Need visible failure to hold plus movement away from the level or zone.")
    elif classification == "reclaim":
        missing_confirmation.append("Need visible evidence that the level was taken and then recovered.")
    elif classification == "sweep":
        missing_confirmation.append("Need visible evidence that liquidity was taken and not reclaimed.")
    elif classification == "displacement":
        missing_confirmation.append("Need visible strong directional movement away from the reaction zone.")
    elif classification == "bullish_continuation_compression":
        missing_confirmation.append("Need 5M continuation confirmation to upgrade compression from watch context to cleaner behavior.")
    elif classification == "bullish_continuation_expansion":
        missing_confirmation.append("Need sustained 5M hold above the expansion structure for higher confidence.")
    elif classification == "consolidation":
        missing_confirmation.append("Need cleaner directional behavior around the marked level or FVG reaction zone.")
    else:
        missing_confirmation.append("Need clearer live visual behavior around the marked level or zone.")

    if htf_bias != execution_bias and htf_bias in ["bullish", "bearish"] and execution_bias in ["bullish", "bearish"]:
        missing_confirmation.append("HTF and execution bias conflict; confidence is capped until structure resolves.")

    if not has_5m_confirmation:
        missing_confirmation.append("Missing 5M confirmation caps confidence at Medium.")

    if not record.get("vision_success"):
        data_limitations.append("Primary visual extraction did not succeed.")

    missing_visual_tfs = [
        timeframe for timeframe in ["15M", "5M"]
        if not text_by_timeframe.get(timeframe)
    ]

    if missing_visual_tfs:
        data_limitations.append(f"Missing readable visual context for: {', '.join(missing_visual_tfs)}.")

    if csv_stale:
        data_limitations.extend([
            "CSV is stale; using CSV only for structural context.",
            "Live vision is primary for current price and zone interaction.",
            "CSV is stale; live acceptance/rejection is not classified from CSV close.",
        ])
        data_limitations.extend(stale_zone_guardrail.get("warnings") or [])

        if reaction_zone_source == "visual":
            data_limitations.append("Reaction zone is visual/manual and approximate; exact bounds should be confirmed on chart.")
        elif reaction_zone_source == "csv":
            data_limitations.append("No visual FVG was detected, so the stale CSV FVG is used only as a fallback reaction-zone reference.")

    if news_risk_level == "high":
        data_limitations.append("News Risk is High; behavior quality may be less reliable.")
    elif news_risk_level == "medium":
        data_limitations.append("News Risk is Medium; confirmation quality matters more.")

    csv_refresh_limitation = _get_csv_refresh_limitation()
    if csv_refresh_limitation:
        data_limitations.append(csv_refresh_limitation)

    continuation_pattern_detected = bool(continuation_pattern_match.get("matched"))
    expansion_pattern_detected = bool(expansion_pattern_match.get("matched"))
    live_visual_clear = (has_directional_behavior and bool(visual_text_15m)) or continuation_pattern_detected or expansion_pattern_detected
    strong_visual_evidence = bool(
        has_15m_directional_behavior and has_5m_confirmation
    ) or bool(
        classification == "bullish_continuation_compression"
        and continuation_pattern_match.get("confidence") in ["medium", "high"]
    ) or bool(
        classification == "bullish_continuation_expansion"
        and expansion_pattern_match.get("confidence") in ["medium", "high"]
    )
    confidence = _cap_confidence_for_context(
        confidence,
        htf_bias=htf_bias,
        execution_bias=execution_bias,
        csv_stale=csv_stale,
        live_visual_clear=live_visual_clear,
        strong_visual_evidence=strong_visual_evidence,
        has_5m_confirmation=has_5m_confirmation,
        news_risk_level=news_risk_level,
    )

    if not evidence:
        evidence.append("No usable behavior evidence was detected.")

    if not data_limitations:
        data_limitations.append("No major behavior-classification data limitation detected.")

    return {
        "behavior_classification_version": "v3",
        "classification": classification,
        "liquidity_draw_status": liquidity_draw_status,
        "reaction_zone": reaction_zone,
        "stale_csv_guardrail": stale_zone_guardrail,
        "behavior_location": behavior_location,
        "structure_confirmation": structure_confirmation,
        "confidence": confidence,
        "golden_pattern_match": golden_pattern_match,
        "continuation_pattern_match": continuation_pattern_match,
        "expansion_pattern_match": expansion_pattern_match,
        "evidence": _dedupe_text(evidence),
        "missing_confirmation": _dedupe_text(missing_confirmation),
        "data_limitations": _dedupe_text(data_limitations),
        "does_not_generate_trade_signals": True,
    }


def _format_golden_pattern_match_state(golden_pattern_match: dict) -> str:
    if golden_pattern_match.get("matched"):
        return "Yes"

    if golden_pattern_match.get("matched_steps"):
        return "Partial"

    return "No"


def _format_behavior_label(classification: str) -> str:
    return classification.replace("_", " ").title()


def format_golden_pattern_check_section(golden_pattern_match: dict) -> str:
    matched_steps = golden_pattern_match.get("matched_steps") or []
    missing_steps = golden_pattern_match.get("missing_steps")
    if missing_steps is None:
        missing_steps = list(GOLDEN_PATTERN_STEPS.keys())

    lines = [
        "## Golden Pattern Check",
        f"Pattern: {golden_pattern_match.get('pattern_name') or GOLDEN_PATTERN_NAME}",
        f"Matched: {_format_golden_pattern_match_state(golden_pattern_match)}",
        "",
        "Matched steps:",
    ]

    if matched_steps:
        lines.extend(f"- {GOLDEN_PATTERN_STEPS.get(step, step)}" for step in matched_steps)
    else:
        lines.append("- None detected.")

    lines.extend(["", "Missing steps:"])

    if missing_steps:
        lines.extend(f"- {GOLDEN_PATTERN_STEPS.get(step, step)}" for step in missing_steps)
    else:
        lines.append("- None.")

    return "\n".join(lines)


def format_continuation_pattern_check_section(continuation_pattern_match: dict) -> str:
    matched_steps = continuation_pattern_match.get("matched_steps") or []
    missing_steps = continuation_pattern_match.get("missing_steps")
    if missing_steps is None:
        missing_steps = list(CONTINUATION_PATTERN_STEPS.keys())

    lines = [
        "## Continuation Pattern Check",
        f"Pattern: {continuation_pattern_match.get('pattern_name') or CONTINUATION_PATTERN_NAME}",
        f"Matched: {_format_golden_pattern_match_state(continuation_pattern_match)}",
        "",
        "Matched steps:",
    ]

    if matched_steps:
        lines.extend(f"- {CONTINUATION_PATTERN_STEPS.get(step, step)}" for step in matched_steps)
    else:
        lines.append("- None detected.")

    lines.extend(["", "Missing steps:"])

    if missing_steps:
        lines.extend(f"- {CONTINUATION_PATTERN_STEPS.get(step, step)}" for step in missing_steps)
    else:
        lines.append("- None.")

    return "\n".join(lines)


def format_expansion_pattern_check_section(expansion_pattern_match: dict) -> str:
    matched_steps = expansion_pattern_match.get("matched_steps") or []
    missing_steps = expansion_pattern_match.get("missing_steps")
    if missing_steps is None:
        missing_steps = list(EXPANSION_PATTERN_STEPS.keys())

    lines = [
        "## Expansion Pattern Check",
        f"Pattern: {expansion_pattern_match.get('pattern_name') or EXPANSION_PATTERN_NAME}",
        f"Matched: {_format_golden_pattern_match_state(expansion_pattern_match)}",
        "",
        "Matched steps:",
    ]

    if matched_steps:
        lines.extend(f"- {EXPANSION_PATTERN_STEPS.get(step, step)}" for step in matched_steps)
    else:
        lines.append("- None detected.")

    lines.extend(["", "Missing steps:"])

    if missing_steps:
        lines.extend(f"- {EXPANSION_PATTERN_STEPS.get(step, step)}" for step in missing_steps)
    else:
        lines.append("- None.")

    return "\n".join(lines)


def format_behavior_classification_section(behavior: dict) -> str:
    classification = _format_behavior_label(str(behavior.get("classification") or "unknown"))
    liquidity_draw_status = str(behavior.get("liquidity_draw_status") or "unclear").capitalize()
    reaction_zone = behavior.get("reaction_zone") or "Unclear"
    behavior_location = behavior.get("behavior_location") or "Unclear"
    structure_confirmation = behavior.get("structure_confirmation") or "5M unclear"
    confidence = str(behavior.get("confidence") or "low").capitalize()
    evidence = behavior.get("evidence") or ["No behavior evidence was available."]
    missing = behavior.get("missing_confirmation") or ["Need clearer live confirmation."]
    limitations = behavior.get("data_limitations") or ["No major data limitation detected."]
    golden_pattern_match = behavior.get("golden_pattern_match") or {
        "matched": False,
        "pattern_name": GOLDEN_PATTERN_NAME,
        "matched_steps": [],
        "missing_steps": list(GOLDEN_PATTERN_STEPS.keys()),
        "confidence": "low",
    }
    continuation_pattern_match = behavior.get("continuation_pattern_match") or {
        "matched": False,
        "pattern_name": CONTINUATION_PATTERN_NAME,
        "matched_steps": [],
        "missing_steps": list(CONTINUATION_PATTERN_STEPS.keys()),
        "confidence": "low",
    }
    expansion_pattern_match = behavior.get("expansion_pattern_match") or {
        "matched": False,
        "pattern_name": EXPANSION_PATTERN_NAME,
        "matched_steps": [],
        "missing_steps": list(EXPANSION_PATTERN_STEPS.keys()),
        "confidence": "low",
    }
    stale_guardrail = behavior.get("stale_csv_guardrail") or {}

    lines = [
        "## Behavior Classification",
        f"Classification: {classification}",
        f"Liquidity Draw Status: {liquidity_draw_status}",
        f"Reaction Zone: {reaction_zone}",
        f"Behavior Location: {behavior_location}",
        f"Structure Confirmation: {structure_confirmation}",
        "",
        f"Confidence: {confidence}",
        "",
        "Evidence:",
    ]
    lines.extend(f"- {item}" for item in evidence)
    lines.extend(["", "Missing confirmation:"])
    lines.extend(f"- {item}" for item in missing)
    lines.extend(["", "Data limitations:"])
    lines.extend(f"- {item}" for item in limitations)
    if stale_guardrail.get("warnings"):
        lines.extend([
            "",
            "Stale CSV Guardrail:",
            f"- Zone status: {str(stale_guardrail.get('zone_status') or 'unclear').replace('_', ' ')}",
            f"- Intraday behavior: {str(stale_guardrail.get('intraday_behavior') or 'unclear').replace('_', ' ')}",
        ])
        lines.extend(f"- {item}" for item in stale_guardrail.get("warnings") or [])
    lines.extend(["", format_golden_pattern_check_section(golden_pattern_match)])
    lines.extend(["", format_continuation_pattern_check_section(continuation_pattern_match)])
    lines.extend(["", format_expansion_pattern_check_section(expansion_pattern_match)])

    return "\n".join(lines)


def _sanitize_message_for_stale_csv_guardrail(message: str, behavior: dict) -> str:
    guardrail = behavior.get("stale_csv_guardrail") or {}
    if not guardrail.get("block_bullish_execution_watch"):
        return message

    blocked_terms = [
        "bullish setup",
        "price reacting near",
        "to buy reclaim",
        "buy reclaim",
        "execution_watch_long",
        "execution watch long",
        "bullish continuation watch",
    ]
    kept_lines = []
    removed = False

    for line in (message or "").splitlines():
        line_lower = line.lower()
        if any(term in line_lower for term in blocked_terms):
            removed = True
            continue
        kept_lines.append(line)

    sanitized = "\n".join(kept_lines).strip()
    if removed:
        correction = (
            "Stale CSV Guardrail: CSV zones are structural only here; live vision "
            "shows reclaim is needed before bullish review."
        )
        sanitized = f"{sanitized}\n\n{correction}".strip()

    return sanitized


def attach_behavior_classification(record: dict) -> None:
    behavior = classify_behavior(record)
    record["behavior_classification"] = behavior
    base_message = _sanitize_message_for_stale_csv_guardrail(
        record.get("message") or "",
        behavior,
    )
    record["message"] = (
        base_message
        + "\n\n"
        + format_behavior_classification_section(behavior)
    ).strip()


# -------------------------
# Opportunity recognition
# -------------------------
OPPORTUNITY_TYPE_LABELS = {
    "no_opportunity": "No Opportunity",
    "bullish_continuation_watch": "Bullish Continuation Watch",
    "bearish_continuation_watch": "Bearish Continuation Watch",
    "reversal_watch": "Reversal Watch",
    "range_chop_warning": "Range/Chop Warning",
}


def _dedupe_text(items: list[str]) -> list[str]:
    seen = set()
    cleaned = []

    for item in items:
        text = str(item).strip()
        key = text.lower()

        if not text or key in seen:
            continue

        seen.add(key)
        cleaned.append(text)

    return cleaned


def _visuals_from_capture(capture: dict | None) -> dict:
    extraction = (capture or {}).get("visual_extraction") or {}
    return extraction.get("visuals") or {}


def _visual_text_from_visuals(visuals: dict) -> str:
    parts = []

    for label in visuals.get("visible_labels") or []:
        parts.append(str(label))

    for key in ["horizontal_lines", "drawn_boxes"]:
        for item in visuals.get(key) or []:
            if isinstance(item, dict):
                parts.extend([
                    str(item.get("label") or ""),
                    str(item.get("color") or ""),
                    str(item.get("location_notes") or ""),
                ])
            else:
                parts.append(str(item))

    for key in ["arrows_or_annotations", "notes_about_user_markings", "uncertainty_flags"]:
        for item in visuals.get(key) or []:
            parts.append(str(item))

    return " ".join(part for part in parts if part).lower()


def _record_visual_context(record: dict) -> dict:
    timeframe_captures = record.get("timeframe_captures") or {}
    capture_15m = timeframe_captures.get("15M") or {}
    visuals_15m = _visuals_from_capture(capture_15m)

    if not visuals_15m and record.get("timeframe") == "15M":
        visuals_15m = (record.get("visual_extraction") or {}).get("visuals") or {}

    all_visual_text = [_visual_text_from_visuals(visuals_15m)]

    for timeframe, capture in timeframe_captures.items():
        if timeframe == "5M":
            continue

        all_visual_text.append(_visual_text_from_visuals(_visuals_from_capture(capture)))

    return {
        "visuals_15m": visuals_15m,
        "text_15m": _visual_text_from_visuals(visuals_15m),
        "text_all": " ".join(text for text in all_visual_text if text),
    }


def _contains_any(text: str, terms: list[str]) -> bool:
    return any(term in text for term in terms)


def _csv_is_stale(record: dict) -> bool:
    freshness = record.get("csv_freshness") or {}

    if isinstance(freshness, dict):
        if freshness.get("is_stale"):
            return True

        for timeframe in HTF_CSV_TIMEFRAMES:
            item = freshness.get(timeframe) or {}
            if isinstance(item, dict) and item.get("is_stale"):
                return True

    return False


def _zone_direction(zone: dict | None, htf_bias: str = "unknown") -> str:
    if not zone:
        return "unknown"

    text = " ".join(
        str(zone.get(key) or "")
        for key in ["type", "label", "direction", "bias"]
    ).lower()

    if any(term in text for term in ["bullish", "demand", "support"]):
        return "bullish"
    if any(term in text for term in ["bearish", "supply", "resistance"]):
        return "bearish"
    if htf_bias in {"bullish", "bearish"}:
        return htf_bias
    return "unknown"


def _stale_csv_zone_guardrail(
    record: dict,
    active_zone: dict | None = None,
    visual_text_all: str = "",
) -> dict:
    state = record.get("state") or extract_structured_state(record)
    htf_bias = str(state.get("htf_bias") or "unknown").lower()
    price_relation = str(state.get("price_relation") or "unknown").lower()
    zone = active_zone

    if zone is None:
        zone = (
            ((record.get("csv_analysis") or {}).get("analysis") or {})
            .get("zone_ranking", {})
            .get("active_zone")
            or {}
        )

    zone_direction = _zone_direction(zone, htf_bias)
    guardrail = {
        "applies": False,
        "zone_status": "unclear",
        "block_bullish_execution_watch": False,
        "block_bearish_execution_watch": False,
        "execution_readiness": None,
        "intraday_behavior": "unclear",
        "warnings": [],
        "evidence": [],
    }

    if not _csv_is_stale(record):
        return guardrail

    guardrail["warnings"].extend([
        "CSV is stale; using CSV only for structural context.",
        "Live vision is primary for current price and zone interaction.",
    ])

    bearish_visual_terms = [
        "bearish",
        "displacement lower",
        "move lower",
        "strong move down",
        "breakdown",
        "broke down",
        "lost support",
        "lost level",
        "failed support",
        "below level",
        "below fvg",
        "rejection",
        "reject",
        "rejected",
        "selloff",
    ]
    bullish_visual_terms = [
        "bullish",
        "displacement higher",
        "move higher",
        "strong move up",
        "breakout",
        "broke out",
        "lost resistance",
        "failed resistance",
        "above level",
        "above fvg",
        "reclaim",
        "reclaimed",
        "acceptance",
    ]
    bearish_visual = _contains_any(visual_text_all, bearish_visual_terms)
    bullish_visual = _contains_any(visual_text_all, bullish_visual_terms)

    if zone_direction == "bullish" and price_relation == "below_active_zone":
        guardrail.update({
            "applies": True,
            "zone_status": "failed_support" if bearish_visual else "below_zone",
            "block_bullish_execution_watch": True,
            "execution_readiness": "no_long_until_reclaim",
            "intraday_behavior": "bearish_intraday_displacement" if bearish_visual else "reclaim_needed",
        })
        guardrail["evidence"].append(
            "Live/visual state places price below the stale CSV bullish FVG/support reference; treat the zone as failed or needing reclaim, not active support."
        )
    elif zone_direction == "bearish" and price_relation == "above_active_zone":
        guardrail.update({
            "applies": True,
            "zone_status": "failed_resistance" if bullish_visual else "above_zone",
            "block_bearish_execution_watch": True,
            "execution_readiness": "no_short_until_reject",
            "intraday_behavior": "bullish_intraday_displacement" if bullish_visual else "reject_needed",
        })
        guardrail["evidence"].append(
            "Live/visual state places price above the stale CSV bearish FVG/resistance reference; treat the zone as failed or needing rejection, not active resistance."
        )

    if guardrail["applies"]:
        if zone_direction == "bullish":
            guardrail["warnings"].append(
                "HTF map may still contain bullish FVGs, but live intraday behavior is not bullish until price reclaims the referenced zone."
            )
        elif zone_direction == "bearish":
            guardrail["warnings"].append(
                "HTF map may still contain bearish FVGs, but live intraday behavior is not bearish until price rejects back below the referenced zone."
            )

    return guardrail


def _news_risk_level(record: dict) -> str:
    news_risk = record.get("news_risk") or {}
    return str(news_risk.get("risk") or "Low").strip().lower()


def _downgrade_confidence(confidence: str) -> str:
    if confidence == "high":
        return "medium"
    if confidence == "medium":
        return "low"
    return "low"


def recognize_opportunity(record: dict) -> dict:
    state = record.get("state") or extract_structured_state(record)
    htf_bias = state.get("htf_bias", "unknown")
    execution_bias = state.get("execution_bias", "unknown")
    price_relation = state.get("price_relation", "unknown")

    visual_context = _record_visual_context(record)
    visual_text_15m = visual_context.get("text_15m", "")
    visual_text_all = visual_context.get("text_all", "")
    stale_zone_guardrail = _stale_csv_zone_guardrail(record, visual_text_all=visual_text_all)

    bullish_terms = [
        "pdh",
        "pdnyh",
        "fvg",
        "reclaim",
        "holding above",
        "hold above",
        "above level",
        "above the level",
        "support",
        "demand",
        "bullish",
    ]
    bearish_terms = [
        "rejection",
        "reject",
        "failure",
        "failed",
        "lost level",
        "reclaim lost",
        "below level",
        "below the level",
        "resistance",
        "supply",
        "bearish",
    ]
    range_terms = ["range", "chop", "sideways", "consolidation", "balanced", "inside range"]
    reversal_terms = ["sweep", "reversal", "raid", "failed breakout", "failed breakdown"]

    bullish_visual = _contains_any(visual_text_15m, bullish_terms) or _contains_any(visual_text_all, bullish_terms)
    bearish_visual = _contains_any(visual_text_15m, bearish_terms) or _contains_any(visual_text_all, bearish_terms)
    range_visual = _contains_any(visual_text_all, range_terms)
    reversal_visual = _contains_any(visual_text_all, reversal_terms)
    csv_stale = _csv_is_stale(record)
    news_risk_level = _news_risk_level(record)

    opportunity_type = "no_opportunity"
    confidence = "low"
    reasons = []
    risks = []
    next_confirmation_needed = []

    if htf_bias == "bullish" and execution_bias == "bearish":
        if bullish_visual:
            opportunity_type = "bullish_continuation_watch"
            confidence = "medium"
            reasons.append("HTF bias is bullish while execution is temporarily bearish.")
            reasons.append("15M or multi-timeframe visuals include reclaim, FVG, PDH, or hold-above context.")
            next_confirmation_needed.append("Execution structure needs to shift back in line with the bullish HTF read.")
            next_confirmation_needed.append("Price should continue respecting the marked level or zone on fresh chart context.")
        else:
            opportunity_type = "range_chop_warning" if range_visual else "no_opportunity"
            reasons.append("HTF and execution bias conflict without enough supportive visual context.")
            next_confirmation_needed.append("Wait for clearer visual confirmation around a marked level or zone.")
    elif htf_bias == "bearish" and execution_bias == "bullish":
        if bearish_visual:
            opportunity_type = "bearish_continuation_watch"
            confidence = "medium"
            reasons.append("HTF bias is bearish while execution is temporarily bullish.")
            reasons.append("15M or multi-timeframe visuals include rejection, failure, lost-level, or overhead context.")
            next_confirmation_needed.append("Execution structure needs to shift back in line with the bearish HTF read.")
            next_confirmation_needed.append("Price should continue failing or rejecting the marked level or zone on fresh chart context.")
        else:
            opportunity_type = "range_chop_warning" if range_visual else "no_opportunity"
            reasons.append("HTF and execution bias conflict without enough rejection or failure evidence.")
            next_confirmation_needed.append("Wait for clearer visual confirmation around a marked level or zone.")
    elif htf_bias == execution_bias and htf_bias in ["bullish", "bearish"]:
        if htf_bias == "bullish" and bullish_visual:
            opportunity_type = "bullish_continuation_watch"
            confidence = "medium"
            reasons.append("HTF and execution bias are aligned bullish.")
            reasons.append("Visual context includes bullish level, FVG, PDH, or hold-above evidence.")
            next_confirmation_needed.append("Fresh lower-timeframe structure should continue to support the aligned bullish read.")
        elif htf_bias == "bearish" and bearish_visual:
            opportunity_type = "bearish_continuation_watch"
            confidence = "medium"
            reasons.append("HTF and execution bias are aligned bearish.")
            reasons.append("Visual context includes rejection, failure, supply, or lost-level evidence.")
            next_confirmation_needed.append("Fresh lower-timeframe structure should continue to support the aligned bearish read.")
        elif range_visual:
            opportunity_type = "range_chop_warning"
            reasons.append("Bias is aligned, but visual context suggests range or chop conditions.")
            next_confirmation_needed.append("Need cleaner displacement away from the current range.")
        else:
            reasons.append("Bias is aligned, but visual context is not specific enough for an opportunity watch.")
            next_confirmation_needed.append("Need clearer marked-level confirmation before upgrading the watch.")
    elif reversal_visual and (bullish_visual or bearish_visual):
        opportunity_type = "reversal_watch"
        confidence = "low"
        reasons.append("Visual context includes sweep, raid, reversal, or failed-breakout language.")
        next_confirmation_needed.append("Need follow-through structure before treating the reversal context as meaningful.")
    elif range_visual:
        opportunity_type = "range_chop_warning"
        reasons.append("Visual context suggests range or chop conditions.")
        next_confirmation_needed.append("Need cleaner directional structure away from the range.")
    else:
        reasons.append("No conservative opportunity context was confirmed from current state and visuals.")
        next_confirmation_needed.append("Need alignment between HTF, execution, and visible marked-level behavior.")

    if price_relation != "unknown":
        reasons.append(f"Computed price relation is {price_relation}.")

    if csv_stale:
        confidence = _downgrade_confidence(confidence)
        risks.extend([
            "CSV is stale; using CSV only for structural context.",
            "Live vision is primary for current price and zone interaction.",
            "CSV freshness is stale, so computed current price should be treated as historical context.",
        ])

    if stale_zone_guardrail.get("block_bullish_execution_watch") and opportunity_type == "bullish_continuation_watch":
        opportunity_type = "no_opportunity"
        confidence = "low"
        reasons.append("Stale CSV guardrail blocks bullish continuation watch because live price is below the referenced bullish zone.")
        next_confirmation_needed.append("No long execution review until live price reclaims and holds the referenced reaction zone.")
    elif stale_zone_guardrail.get("block_bearish_execution_watch") and opportunity_type == "bearish_continuation_watch":
        opportunity_type = "no_opportunity"
        confidence = "low"
        reasons.append("Stale CSV guardrail blocks bearish continuation watch because live price is above the referenced bearish zone.")
        next_confirmation_needed.append("No short execution review until live price rejects back below the referenced reaction zone.")

    if news_risk_level == "high":
        confidence = _downgrade_confidence(confidence)
        risks.append("News Risk is High, so market movement may be less reliable.")
    elif news_risk_level == "medium":
        risks.append("News Risk is Medium, so confirmation quality matters more.")

    if not record.get("vision_success"):
        confidence = "low"
        risks.append("Primary visual extraction did not succeed.")

    if not visual_text_15m:
        risks.append("15M visual labels were not available or not readable.")

    if not risks:
        risks.append("No major contextual risk flag was detected.")

    return {
        "opportunity_type": opportunity_type,
        "confidence": confidence,
        "reasons": _dedupe_text(reasons),
        "risks": _dedupe_text(risks),
        "next_confirmation_needed": _dedupe_text(next_confirmation_needed),
    }


def format_opportunity_watch_section(opportunity: dict) -> str:
    opportunity_type = opportunity.get("opportunity_type") or "no_opportunity"
    label = OPPORTUNITY_TYPE_LABELS.get(opportunity_type, "No Opportunity")
    confidence = str(opportunity.get("confidence") or "low").capitalize()
    reasons = opportunity.get("reasons") or ["No conservative opportunity context was confirmed."]
    risks = opportunity.get("risks") or ["No major contextual risk flag was detected."]
    confirmations = opportunity.get("next_confirmation_needed") or [
        "Need clearer alignment between market state and visible chart context."
    ]

    lines = [
        "## Opportunity Watch",
        f"Type: {label}",
        f"Confidence: {confidence}",
        "",
        "Reasons:",
    ]
    lines.extend(f"- {item}" for item in reasons)
    lines.extend(["", "Risks:"])
    lines.extend(f"- {item}" for item in risks)
    lines.extend(["", "Next confirmation needed:"])
    lines.extend(f"- {item}" for item in confirmations)

    return "\n".join(lines)


def attach_opportunity_watch(record: dict) -> None:
    opportunity = recognize_opportunity(record)
    record["opportunity_watch"] = opportunity
    record["message"] = (
        (record.get("message") or "")
        + "\n\n"
        + format_opportunity_watch_section(opportunity)
    ).strip()


# -------------------------
# Narrative scanner state
# -------------------------
NARRATIVE_PHASES = {
    "no_clear_narrative",
    "draw_identified",
    "approaching_reaction_zone",
    "interacting_with_reaction_zone",
    "behavior_forming",
    "structure_confirming",
    "execution_watch",
    "continuation_confirmed",
    "narrative_invalidated",
}


def _format_narrative_draw(primary_draw: dict | None) -> str:
    if not primary_draw:
        return "None identified"

    label = primary_draw.get("label") or "Primary draw"
    price = _fmt_draw_price(primary_draw.get("price"))
    if price == "unknown":
        return str(label)

    return f"{label} at {price}"


def _reaction_zone_details(record: dict, reaction_zone_status: str) -> dict:
    behavior = record.get("behavior_classification") or {}
    behavior_zone = str(behavior.get("reaction_zone") or "").strip()
    active_zone = (
        ((record.get("csv_analysis") or {}).get("analysis") or {})
        .get("zone_ranking", {})
        .get("active_zone")
        or {}
    )

    zone_label = behavior_zone if behavior_zone and behavior_zone.lower() != "unclear" else ""
    if not zone_label and active_zone:
        zone_label = _format_reaction_zone(active_zone)
    if not zone_label:
        zone_label = "Unclear"

    timeframe = str(active_zone.get("timeframe") or "").upper()
    if not timeframe:
        zone_lower = zone_label.lower()
        if "4h" in zone_lower or "4hr" in zone_lower:
            timeframe = "4H"
        elif "1h" in zone_lower or "1hr" in zone_lower:
            timeframe = "1H"
        elif "15m" in zone_lower or "15min" in zone_lower:
            timeframe = "15M"
        elif "5m" in zone_lower or "5min" in zone_lower:
            timeframe = "5M"
        elif zone_label != "Unclear":
            timeframe = "HTF"
        else:
            timeframe = "unclear"

    zone_type = str(active_zone.get("type") or "").strip()
    if not zone_type:
        zone_type = "FVG" if "fvg" in zone_label.lower() else "reaction_zone"

    return {
        "htf_reaction_zone": zone_label,
        "reaction_zone_timeframe": timeframe,
        "reaction_zone_type": zone_type,
        "reaction_zone_status": reaction_zone_status,
    }


def _structure_confirmation_state(record: dict) -> str:
    behavior = record.get("behavior_classification") or {}
    structure = str(behavior.get("structure_confirmation") or "5M unclear").strip()
    return structure or "5M unclear"


def _has_structure_confirmation(record: dict) -> bool:
    return "5m confirms" in _structure_confirmation_state(record).lower()


def _has_continuation_confirmation(record: dict) -> bool:
    behavior = record.get("behavior_classification") or {}
    expansion_match = behavior.get("expansion_pattern_match") or {}
    classification = str(behavior.get("classification") or "unknown").lower()
    confidence = str(behavior.get("confidence") or "low").lower()

    return bool(
        classification == "bullish_continuation_expansion"
        and expansion_match.get("matched")
        and confidence in {"medium", "high"}
    )


def _has_invalidation_evidence(record: dict) -> bool:
    behavior = record.get("behavior_classification") or {}
    guardrail = behavior.get("stale_csv_guardrail") or _stale_csv_zone_guardrail(record)
    if guardrail.get("applies"):
        return True

    if record.get("invalidation_evidence") or behavior.get("invalidation_evidence"):
        return True

    text_parts = []
    for key in ["evidence", "missing_confirmation", "data_limitations"]:
        value = behavior.get(key) or []
        if isinstance(value, list):
            text_parts.extend(str(item) for item in value)
        else:
            text_parts.append(str(value))

    text = " ".join(text_parts).lower()
    invalidation_terms = [
        "draw failed",
        "failed draw",
        "opposite reclaim",
        "invalidated",
        "invalidation",
        "continuation failed",
        "failed continuation",
    ]

    return _contains_any(text, invalidation_terms)


def _narrative_missing_confirmations(record: dict, phase: str) -> list[str]:
    behavior = record.get("behavior_classification") or {}
    opportunity = record.get("opportunity_watch") or {}
    missing = []

    missing.extend(behavior.get("missing_confirmation") or [])
    missing.extend(opportunity.get("next_confirmation_needed") or [])

    phase_missing = {
        "no_clear_narrative": ["Need a clean liquidity draw and HTF reaction-zone context."],
        "draw_identified": ["Need price to approach or interact with a mapped HTF reaction zone."],
        "approaching_reaction_zone": ["Need live behavior inside/around the reaction zone."],
        "interacting_with_reaction_zone": ["Need acceptance, rejection, reclaim, sweep, or displacement evidence."],
        "behavior_forming": ["Need MSS/BOS or 5M structure confirmation."],
        "structure_confirming": ["Need liquidity, behavior, and structure to align before execution watch."],
        "execution_watch": ["Need expansion or continuation confirmation before marking continuation confirmed."],
        "continuation_confirmed": ["Monitor for sustained hold and target-liquidity continuation."],
        "narrative_invalidated": ["Narrative invalidated; wait for a fresh draw and reaction-zone sequence."],
    }
    missing.extend(phase_missing.get(phase, []))

    return _dedupe_text(missing)


def derive_narrative_scanner_state(record: dict) -> dict:
    liquidity_draw = record.get("liquidity_draw") or {}
    primary_draw = liquidity_draw.get("primary_draw") or {}
    behavior = record.get("behavior_classification") or {}

    reaction_zone_status = _reaction_zone_status(record)
    behavior_confirmation = _behavior_confirmation_state(record)
    liquidity_draw_alignment = _liquidity_draw_alignment_state(record)
    behavior_classification = str(behavior.get("classification") or "unknown").lower()
    behavior_confidence = str(behavior.get("confidence") or "low").lower()
    stale_zone_guardrail = behavior.get("stale_csv_guardrail") or _stale_csv_zone_guardrail(record)
    structure_confirmation = _structure_confirmation_state(record)
    has_draw = bool(primary_draw.get("label") or primary_draw.get("key"))
    invalidated_zone_statuses = {"below_zone", "above_zone", "failed_support", "failed_resistance"}
    has_reaction_zone = reaction_zone_status in {"mapped", "nearby", "interacting", "reclaim_needed", "reject_needed"}
    has_behavior = behavior_confirmation != "none" or behavior_classification in {
        "acceptance",
        "rejection",
        "reclaim",
        "sweep",
        "displacement",
        "bullish_continuation_compression",
        "bullish_continuation_expansion",
    }
    has_meaningful_behavior = _has_meaningful_behavior_confirmation(record)
    has_structure = _has_structure_confirmation(record)
    has_alignment = liquidity_draw_alignment == "aligned"

    phase = "no_clear_narrative"
    if stale_zone_guardrail.get("applies") and reaction_zone_status in invalidated_zone_statuses:
        phase = "narrative_invalidated"
    elif _has_invalidation_evidence(record):
        phase = "narrative_invalidated"
    elif _has_continuation_confirmation(record):
        phase = "continuation_confirmed"
    elif has_meaningful_behavior and has_structure and has_alignment:
        phase = "execution_watch"
    elif has_behavior and has_structure:
        phase = "structure_confirming"
    elif has_behavior:
        phase = "behavior_forming"
    elif reaction_zone_status == "interacting":
        phase = "interacting_with_reaction_zone"
    elif reaction_zone_status in {"mapped", "nearby"} and has_draw:
        phase = "approaching_reaction_zone"
    elif has_draw:
        phase = "draw_identified"

    confidence = "low"
    if phase in {"continuation_confirmed", "execution_watch"}:
        confidence = "high" if behavior_confidence == "high" and has_alignment else "medium"
    elif phase in {"behavior_forming", "structure_confirming"}:
        confidence = "medium" if behavior_confidence in {"medium", "high"} else "low"
    elif phase in {"draw_identified", "approaching_reaction_zone", "interacting_with_reaction_zone"}:
        confidence = str(liquidity_draw.get("confidence") or "low").lower()
    elif phase == "narrative_invalidated":
        confidence = "medium"

    zone_details = _reaction_zone_details(record, reaction_zone_status)
    behavior_inside_zone = (
        behavior_confirmation
        if behavior_confirmation != "none"
        else (behavior_classification if behavior_classification != "unknown" else "none")
    )
    execution_readiness_by_phase = {
        "no_clear_narrative": "not_ready",
        "draw_identified": "not_ready",
        "approaching_reaction_zone": "watch",
        "interacting_with_reaction_zone": "watch",
        "behavior_forming": "forming",
        "structure_confirming": "forming",
        "execution_watch": "ready_for_review",
        "continuation_confirmed": "confirmed",
        "narrative_invalidated": "invalidated",
    }

    narrative = {
        "liquidity_draw": _format_narrative_draw(primary_draw),
        "liquidity_draw_direction": primary_draw.get("side") or "unclear",
        **zone_details,
        "behavior_inside_zone": behavior_inside_zone,
        "structure_confirmation": structure_confirmation,
        "execution_readiness": (
            stale_zone_guardrail.get("execution_readiness")
            or execution_readiness_by_phase.get(phase, "not_ready")
        ),
        "target_liquidity": _format_narrative_draw(primary_draw),
        "invalidation_context": (
            "Stale CSV guardrail: live price invalidated the referenced CSV reaction zone; reclaim/reject is needed before execution review."
            if stale_zone_guardrail.get("applies")
            else "Invalidation evidence detected in behavior context."
            if phase == "narrative_invalidated"
            else "No invalidation evidence detected."
        ),
        "narrative_phase": phase,
        "narrative_confidence": confidence if confidence in {"low", "medium", "high"} else "low",
        "missing_confirmations": _narrative_missing_confirmations(record, phase),
        "does_not_generate_trade_signals": True,
    }

    return narrative


def normalize_narrative_scanner_state(record: dict) -> dict:
    narrative = record.get("narrative") or {}

    if not isinstance(narrative, dict):
        narrative = {}

    defaults = {
        "liquidity_draw": "None identified",
        "liquidity_draw_direction": "unclear",
        "htf_reaction_zone": "Unclear",
        "reaction_zone_timeframe": "unclear",
        "reaction_zone_type": "reaction_zone",
        "reaction_zone_status": record.get("reaction_zone_status") or "unclear",
        "behavior_inside_zone": record.get("behavior_confirmation") or "none",
        "structure_confirmation": "5M unclear",
        "execution_readiness": "not_ready",
        "target_liquidity": "None identified",
        "invalidation_context": "No invalidation evidence detected.",
        "narrative_phase": record.get("narrative_phase") or record.get("narrative_state") or "no_clear_narrative",
        "narrative_confidence": "low",
        "missing_confirmations": [],
        "does_not_generate_trade_signals": True,
    }
    defaults.update(narrative)

    if defaults["narrative_phase"] not in NARRATIVE_PHASES:
        defaults["narrative_phase"] = "no_clear_narrative"

    if not isinstance(defaults.get("missing_confirmations"), list):
        defaults["missing_confirmations"] = [str(defaults.get("missing_confirmations"))]

    record["narrative"] = defaults
    record["narrative_phase"] = defaults["narrative_phase"]
    record["narrative_confidence"] = defaults["narrative_confidence"]
    record.setdefault("narrative_state", defaults["narrative_phase"])
    return record


def format_narrative_scanner_section(narrative: dict) -> str:
    missing = narrative.get("missing_confirmations") or ["No missing confirmations recorded."]
    lines = [
        "## Narrative Scanner",
        f"Narrative Phase: {str(narrative.get('narrative_phase') or 'no_clear_narrative').replace('_', ' ')}",
        f"Liquidity Draw: {narrative.get('liquidity_draw') or 'None identified'}",
        f"Liquidity Draw Direction: {narrative.get('liquidity_draw_direction') or 'unclear'}",
        f"Reaction Zone: {narrative.get('htf_reaction_zone') or 'Unclear'}",
        f"Reaction Zone Timeframe: {narrative.get('reaction_zone_timeframe') or 'unclear'}",
        f"Reaction Zone Type: {narrative.get('reaction_zone_type') or 'reaction zone'}",
        f"Reaction Zone Status: {str(narrative.get('reaction_zone_status') or 'unclear').replace('_', ' ')}",
        f"Behavior: {str(narrative.get('behavior_inside_zone') or 'none').replace('_', ' ')}",
        f"Structure Confirmation: {narrative.get('structure_confirmation') or '5M unclear'}",
        f"Execution Readiness: {str(narrative.get('execution_readiness') or 'not_ready').replace('_', ' ')}",
        f"Target Liquidity: {narrative.get('target_liquidity') or 'None identified'}",
        f"Invalidation Context: {narrative.get('invalidation_context') or 'No invalidation evidence detected.'}",
        f"Narrative Confidence: {str(narrative.get('narrative_confidence') or 'low').capitalize()}",
        "",
        "Missing Confirmations:",
    ]
    lines.extend(f"- {item}" for item in missing)
    return "\n".join(lines)


def attach_narrative_scanner_state(record: dict) -> None:
    narrative = derive_narrative_scanner_state(record)
    record["narrative"] = narrative
    record["narrative_phase"] = narrative["narrative_phase"]
    record["narrative_confidence"] = narrative["narrative_confidence"]
    record["narrative_state"] = narrative["narrative_phase"]
    record["message"] = (
        (record.get("message") or "")
        + "\n\n"
        + format_narrative_scanner_section(narrative)
    ).strip()


# -------------------------
# Scanner signal tiering
# -------------------------
def _signal_level_rank(level: str) -> int:
    try:
        return SCAN_SIGNAL_LEVELS.index(str(level or "").lower())
    except ValueError:
        return 0


def _at_or_above_signal_level(level: str, minimum: str) -> bool:
    return _signal_level_rank(level) >= _signal_level_rank(minimum)


def _presence_notification_decision(record: dict, current_presence: dict | None = None) -> dict:
    current_presence = current_presence or get_presence()
    mode = str(current_presence.get("mode") or "home")
    label = str(current_presence.get("label") or mode.title())
    signal_level = str(record.get("signal_level") or "informational").lower()
    scanner_min = str(current_presence.get("scanner_min_signal_level") or "review").lower()
    notifications_allowed = bool(current_presence.get("notifications_allowed"))

    if not notifications_allowed:
        allowed = False
        reason = f"{label} mode disables scanner notifications."
    elif not _at_or_above_signal_level(signal_level, scanner_min):
        allowed = False
        reason = (
            f"{label} mode requires {scanner_min} signal or stronger; "
            f"current signal is {signal_level}."
        )
    else:
        allowed = True
        reason = f"{label} mode allows notification eligibility for {signal_level} signal."

    return {
        "presence_mode": mode,
        "presence_config": current_presence,
        "notification_allowed_by_presence": allowed,
        "presence_reason": reason,
    }


def format_presence_scan_section(decision: dict) -> str:
    config = decision.get("presence_config") or {}
    label = str(config.get("label") or decision.get("presence_mode") or "Home")
    return "\n".join(
        [
            "## Presence Mode",
            f"Mode: {label}",
            f"Noise Profile: {str(config.get('scan_noise_profile') or 'normal').replace('_', ' ')}",
            f"Scanner Minimum Signal: {config.get('scanner_min_signal_level') or 'review'}",
            f"Notifications Allowed By Presence: {'Yes' if decision.get('notification_allowed_by_presence') else 'No'}",
            f"Reason: {decision.get('presence_reason') or 'No presence decision recorded.'}",
        ]
    )


def _behavior_confirmation_state(record: dict) -> str:
    behavior = record.get("behavior_classification") or {}
    classification = str(behavior.get("classification") or "unknown").lower()
    confidence = str(behavior.get("confidence") or "low").lower()
    structure_confirmation = str(behavior.get("structure_confirmation") or "").lower()
    continuation_match = behavior.get("continuation_pattern_match") or {}
    expansion_match = behavior.get("expansion_pattern_match") or {}

    if classification in {"acceptance", "rejection", "reclaim", "sweep", "displacement"}:
        if confidence in {"medium", "high"} or "5m confirms" in structure_confirmation:
            return classification
        return f"forming_{classification}"

    if classification == "bullish_continuation_expansion" and expansion_match.get("matched"):
        return "continuation_expansion"

    if classification == "bullish_continuation_compression" and continuation_match.get("matched"):
        return "continuation_compression"

    return "none"


def _has_meaningful_behavior_confirmation(record: dict) -> bool:
    confirmation = _behavior_confirmation_state(record)
    return confirmation not in {"none"} and not confirmation.startswith("forming_")


def _liquidity_draw_alignment_state(record: dict) -> str:
    state = record.get("state") or extract_structured_state(record)
    htf_bias = str(state.get("htf_bias") or "unknown").lower()
    liquidity_draw = record.get("liquidity_draw") or {}
    primary = liquidity_draw.get("primary_draw") or {}
    confidence = str(liquidity_draw.get("confidence") or "unknown").lower()
    side = str(primary.get("side") or "unknown").lower()
    label = primary.get("label")

    if not label or htf_bias not in {"bullish", "bearish"} or side not in {"above", "below"}:
        return "unclear"

    aligned = (htf_bias == "bullish" and side == "above") or (htf_bias == "bearish" and side == "below")
    if aligned and confidence in {"medium", "high"}:
        return "aligned"
    if aligned:
        return "weakly_aligned"
    return "counter"


def _reaction_zone_status(record: dict) -> str:
    state = record.get("state") or extract_structured_state(record)
    behavior = record.get("behavior_classification") or {}
    reaction_zone = str(behavior.get("reaction_zone") or "").strip()
    behavior_location = str(behavior.get("behavior_location") or "").lower()
    price_relation = str(state.get("price_relation") or "unknown")
    guardrail = behavior.get("stale_csv_guardrail") or _stale_csv_zone_guardrail(record)

    if guardrail.get("applies"):
        return str(guardrail.get("zone_status") or "reclaim_needed")

    if price_relation == "inside_active_zone":
        return "interacting"

    if "inside active" in behavior_location or "around visual" in behavior_location:
        return "interacting"

    if reaction_zone and reaction_zone.lower() != "unclear":
        if price_relation in {"above_active_zone", "below_active_zone"}:
            return "nearby"
        return "mapped"

    if state.get("visual_4h_fvg") or state.get("visual_15m_fvg"):
        return "mapped"

    return "unclear"


def _narrative_state(record: dict) -> str:
    narrative = record.get("narrative") or {}
    narrative_phase = narrative.get("narrative_phase") or record.get("narrative_phase")
    if narrative_phase in NARRATIVE_PHASES:
        return narrative_phase

    opportunity = record.get("opportunity_watch") or {}
    opportunity_type = str(opportunity.get("opportunity_type") or "no_opportunity")
    behavior = record.get("behavior_classification") or {}
    classification = str(behavior.get("classification") or "unknown")
    state = record.get("state") or extract_structured_state(record)
    htf_bias = str(state.get("htf_bias") or "unknown")
    execution_bias = str(state.get("execution_bias") or "unknown")

    if opportunity_type != "no_opportunity":
        return opportunity_type
    if classification != "unknown":
        return classification
    if htf_bias != "unknown" or execution_bias != "unknown":
        return f"htf_{htf_bias}_execution_{execution_bias}"
    return "no_clear_narrative"


def _signal_repeat_signature(record: dict) -> dict:
    state = record.get("state") or extract_structured_state(record)
    behavior = record.get("behavior_classification") or {}
    liquidity_draw = record.get("liquidity_draw") or {}
    primary_draw = liquidity_draw.get("primary_draw") or {}

    return {
        "symbol": record.get("symbol") or SYMBOL,
        "narrative_state": record.get("narrative_state") or _narrative_state(record),
        "reaction_zone_status": record.get("reaction_zone_status") or _reaction_zone_status(record),
        "behavior_confirmation": record.get("behavior_confirmation") or _behavior_confirmation_state(record),
        "liquidity_draw_alignment": record.get("liquidity_draw_alignment") or _liquidity_draw_alignment_state(record),
        "htf_bias": state.get("htf_bias"),
        "execution_bias": state.get("execution_bias"),
        "price_relation": state.get("price_relation"),
        "behavior_classification": behavior.get("classification"),
        "primary_draw": primary_draw.get("key") or primary_draw.get("label"),
    }


def _parse_scan_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=TIMEZONE)

    return parsed.astimezone(TIMEZONE)


def _same_scan_state(previous: dict | None, current: dict) -> bool:
    if not previous:
        return False
    return _signal_repeat_signature(previous) == _signal_repeat_signature(current)


def _repeat_suppressed(previous: dict | None, current: dict, now: datetime) -> bool:
    if SCAN_SUPPRESS_REPEATS_MINUTES <= 0 or not _same_scan_state(previous, current):
        return False

    previous_timestamp = _parse_scan_timestamp(previous.get("timestamp"))
    if previous_timestamp is None:
        return False

    return now - previous_timestamp <= timedelta(minutes=SCAN_SUPPRESS_REPEATS_MINUTES)


def evaluate_scanner_signal(record: dict, previous_scan: dict | None = None, now: datetime | None = None) -> dict:
    now = now or datetime.now(TIMEZONE)
    reaction_zone_status = _reaction_zone_status(record)
    behavior_confirmation = _behavior_confirmation_state(record)
    liquidity_draw_alignment = _liquidity_draw_alignment_state(record)
    narrative = record.get("narrative") or derive_narrative_scanner_state(record)
    narrative_state = str(narrative.get("narrative_phase") or _narrative_state(record))
    narrative_confidence = str(narrative.get("narrative_confidence") or "low").lower()
    behavior = record.get("behavior_classification") or {}
    behavior_classification = str(behavior.get("classification") or "unknown").lower()
    behavior_confidence = str(behavior.get("confidence") or "low").lower()
    opportunity = record.get("opportunity_watch") or {}
    opportunity_confidence = str(opportunity.get("confidence") or "low").lower()
    comparison = record.get("comparison") or {}
    major_change, major_change_reasons = _major_state_change(comparison)
    meaningful_behavior = _has_meaningful_behavior_confirmation(record)
    reasons = []

    level = "informational"
    reasons.append("Normal Liquidity Narrative Continuation scan update.")

    phase_signal_floor = {
        "no_clear_narrative": "informational",
        "draw_identified": "informational",
        "approaching_reaction_zone": "watch",
        "interacting_with_reaction_zone": "watch",
        "behavior_forming": "review",
        "structure_confirming": "review",
        "execution_watch": "alert" if narrative_confidence == "high" else "review",
        "continuation_confirmed": "alert",
        "narrative_invalidated": "review",
    }
    phase_floor = phase_signal_floor.get(narrative_state, "informational")
    level = max(level, phase_floor, key=_signal_level_rank)
    reasons.append(f"Narrative phase is {narrative_state.replace('_', ' ')}.")

    if reaction_zone_status in {"mapped", "nearby"} or liquidity_draw_alignment in {"aligned", "weakly_aligned"}:
        level = "watch"
        reasons.append("Price is approaching important liquidity or an FVG reaction zone; no confirmation yet.")

    if reaction_zone_status == "interacting":
        level = "watch"
        reasons.append(
            "Price is interacting with a reaction zone; behavior must confirm acceptance/rejection before alert eligibility."
        )

    if behavior_confirmation.startswith("forming_"):
        level = max(level, "watch", key=_signal_level_rank)
        reasons.append(f"Behavior is forming but not confirmed: {behavior_confirmation.removeprefix('forming_')}.")

    if meaningful_behavior or behavior_confirmation == "continuation_compression":
        level = "review"
        reasons.append(f"Behavior confirmation is present: {behavior_confirmation}.")

    if liquidity_draw_alignment == "aligned" and meaningful_behavior:
        level = "review"
        reasons.append("Liquidity draw alignment supports the behavior read.")

    if (
        meaningful_behavior
        and liquidity_draw_alignment == "aligned"
        and (
            behavior_confidence == "high"
            or behavior_confirmation == "continuation_expansion"
            or (major_change and opportunity_confidence in {"medium", "high"})
        )
    ):
        level = "alert"
        reasons.append("Stronger narrative shift or confirmation is present.")

    if major_change and not meaningful_behavior:
        level = max(level, "watch", key=_signal_level_rank)
        reasons.extend(major_change_reasons)
        reasons.append("Market state changed, but meaningful behavior confirmation is still required for review/alert.")

    if behavior_classification in {"consolidation", "unknown"} and not meaningful_behavior:
        if narrative_state in {
            "no_clear_narrative",
            "draw_identified",
            "approaching_reaction_zone",
            "interacting_with_reaction_zone",
        }:
            level = min(level, "watch", key=_signal_level_rank)
        reasons.append(f"Behavior is {behavior_classification}; FVG contact alone is not alert-worthy.")

    repeat_suppressed = _repeat_suppressed(previous_scan, record, now)
    vision_quality_status = str(record.get("vision_quality_status") or "unknown").lower()
    vision_quality_score = record.get("vision_quality_score")

    if vision_quality_status == "unreliable":
        level = min(level, "watch", key=_signal_level_rank)
        reasons.append(
            f"Vision extraction quality is unreliable ({vision_quality_score}); scanner confidence is capped at Watch."
        )
    elif vision_quality_status == "degraded":
        if level == "alert":
            level = "review"
        reasons.append(
            f"Vision extraction quality is degraded ({vision_quality_score}); scanner confidence is capped below Alert."
        )

    if repeat_suppressed and _at_or_above_signal_level(level, SCAN_ALERT_MIN_LEVEL):
        reasons.append(
            f"Repeated same-state scan suppressed for {SCAN_SUPPRESS_REPEATS_MINUTES} minutes."
        )

    return {
        "signal_level": level,
        "signal_reason": " ".join(_dedupe_text(reasons)),
        "narrative_state": narrative_state,
        "reaction_zone_status": reaction_zone_status,
        "behavior_confirmation": behavior_confirmation,
        "liquidity_draw_alignment": liquidity_draw_alignment,
        "repeat_suppressed": repeat_suppressed,
        "min_alert_level": SCAN_ALERT_MIN_LEVEL,
    }


def format_scanner_signal_section(signal: dict) -> str:
    return "\n".join(
        [
            "## Scanner Signal",
            f"Signal Level: {str(signal.get('signal_level') or 'informational').capitalize()}",
            f"Narrative State: {str(signal.get('narrative_state') or 'no_clear_narrative').replace('_', ' ')}",
            f"Reaction Zone Status: {str(signal.get('reaction_zone_status') or 'unclear').replace('_', ' ')}",
            f"Behavior Confirmation: {str(signal.get('behavior_confirmation') or 'none').replace('_', ' ')}",
            f"Liquidity Draw Alignment: {str(signal.get('liquidity_draw_alignment') or 'unclear').replace('_', ' ')}",
            f"Repeat Suppressed: {'Yes' if signal.get('repeat_suppressed') else 'No'}",
            "",
            f"Reason: {signal.get('signal_reason') or 'Normal scan update.'}",
        ]
    )


def attach_scanner_signal(record: dict, previous_scan: dict | None = None, now: datetime | None = None) -> None:
    signal = evaluate_scanner_signal(record, previous_scan=previous_scan, now=now)
    record.update(signal)
    record["message"] = (
        (record.get("message") or "")
        + "\n\n"
        + format_scanner_signal_section(signal)
    ).strip()


# -------------------------
# Alert eligibility v1
# -------------------------
ALERT_ELIGIBILITY_LEVELS = ["none", "low", "medium", "high"]


def _level_rank(level: str) -> int:
    try:
        return ALERT_ELIGIBILITY_LEVELS.index(level)
    except ValueError:
        return 0


def _min_level(level: str, cap: str) -> str:
    return level if _level_rank(level) <= _level_rank(cap) else cap


def _major_state_change(comparison: dict | None) -> tuple[bool, list[str]]:
    comparison = comparison or {}
    market_changes = comparison.get("market_changes") or []

    changes = [
        str(item).strip()
        for item in market_changes
        if item
        and "No major market structure change detected" not in str(item)
        and "No previous successful scan found for comparison" not in str(item)
    ]

    return bool(changes), changes


def _strong_visual_evidence(record: dict) -> bool:
    behavior = record.get("behavior_classification") or {}
    classification = str(behavior.get("classification") or "unknown").lower()
    confidence = str(behavior.get("confidence") or "low").lower()
    structure_confirmation = str(behavior.get("structure_confirmation") or "").lower()
    expansion_match = behavior.get("expansion_pattern_match") or {}

    directional_confirmation = (
        classification in [
            "acceptance",
            "rejection",
            "reclaim",
            "sweep",
            "displacement",
            "bullish_continuation_compression",
            "bullish_continuation_expansion",
        ]
        and confidence in ["medium", "high"]
        and "5m confirms" in structure_confirmation
    )
    expansion_confirmation = (
        classification == "bullish_continuation_expansion"
        and confidence in ["medium", "high"]
        and bool(expansion_match.get("matched"))
    )

    return directional_confirmation or expansion_confirmation


def evaluate_chart_alert_eligibility(record: dict) -> dict:
    """
    Classifies whether Jadin should be notified to look at the chart.

    This is notification triage only. It does not create trade signals, entries,
    stop losses, targets, or any outbound message.
    """
    if (
        record.get("success") is False
        or not structural_csv_available(record)
        or not has_partial_live_vision(record)
    ):
        return {
            "level": "none",
            "should_notify": False,
            "reasons": ["No chart-review alert: current scanner attempt has system/data failures."],
            "blockers": ["Review scanner system_health before using this attempt as market context."],
            "what_to_watch_next": ["Fix scanner system health, then rerun chart review."],
            "signal_level": record.get("signal_level") or "informational",
            "behavior_confirmation": record.get("behavior_confirmation") or "none",
            "does_not_generate_trade_signals": True,
        }

    opportunity = record.get("opportunity_watch") or {}
    behavior = record.get("behavior_classification") or {}
    liquidity_draw = record.get("liquidity_draw") or {}
    state = record.get("state") or extract_structured_state(record)
    comparison = record.get("comparison") or {}

    opportunity_type = str(opportunity.get("opportunity_type") or "no_opportunity")
    opportunity_confidence = str(opportunity.get("confidence") or "low").lower()
    behavior_classification = str(behavior.get("classification") or "unknown").lower()
    behavior_confidence = str(behavior.get("confidence") or "low").lower()
    structure_confirmation = str(behavior.get("structure_confirmation") or "5M unclear")
    has_5m_confirmation = "5m confirms" in structure_confirmation.lower()
    htf_bias = state.get("htf_bias") or "unknown"
    execution_bias = state.get("execution_bias") or "unknown"
    news_risk_level = _news_risk_level(record)
    csv_stale = _csv_is_stale(record)
    strong_visual = _strong_visual_evidence(record)
    major_change, major_change_reasons = _major_state_change(comparison)
    signal_level = str(record.get("signal_level") or "informational").lower()
    reaction_zone_status = str(record.get("reaction_zone_status") or "unclear").lower()
    behavior_confirmation = str(record.get("behavior_confirmation") or "none").lower()
    liquidity_draw_alignment = str(record.get("liquidity_draw_alignment") or "unclear").lower()
    repeat_suppressed = bool(record.get("repeat_suppressed"))
    partial_live_vision = has_partial_live_vision(record) and not has_full_live_vision(record)
    live_status = live_vision_timeframe_status(record)

    clean_behavior = behavior_classification in [
        "acceptance",
        "rejection",
        "reclaim",
        "sweep",
        "displacement",
        "bullish_continuation_compression",
        "bullish_continuation_expansion",
    ]

    reasons = []
    blockers = []
    what_to_watch_next = []

    if opportunity_type == "no_opportunity":
        level = "none"
        blockers.append("Opportunity Watch is No Opportunity.")
        what_to_watch_next.extend(opportunity.get("next_confirmation_needed") or [])
    elif opportunity_confidence == "low":
        level = "medium" if major_change else "low"
        reasons.append(f"Opportunity Watch is {OPPORTUNITY_TYPE_LABELS.get(opportunity_type, opportunity_type)} with low confidence.")
        if major_change:
            reasons.extend(major_change_reasons)
        else:
            blockers.append("Low-confidence opportunity keeps notification eligibility low without a major state change.")
    elif opportunity_confidence == "medium" and clean_behavior:
        level = "medium"
        reasons.append(f"Opportunity Watch is {OPPORTUNITY_TYPE_LABELS.get(opportunity_type, opportunity_type)} with medium confidence.")
        reasons.append(f"Behavior is clean enough to review: {behavior_classification}.")
    elif opportunity_confidence == "high" and clean_behavior and news_risk_level == "low":
        level = "high"
        reasons.append(f"Opportunity Watch is {OPPORTUNITY_TYPE_LABELS.get(opportunity_type, opportunity_type)} with high confidence.")
        reasons.append(f"Behavior is clean enough to review: {behavior_classification}.")
        reasons.append("News Risk is Low.")
    elif clean_behavior:
        level = "low"
        reasons.append(f"Opportunity Watch is {OPPORTUNITY_TYPE_LABELS.get(opportunity_type, opportunity_type)}.")
        blockers.append(f"Opportunity confidence is {opportunity_confidence}, below the threshold for medium eligibility.")
    else:
        level = "low"
        reasons.append(f"Opportunity Watch is {OPPORTUNITY_TYPE_LABELS.get(opportunity_type, opportunity_type)}.")
        blockers.append(f"Behavior classification is {behavior_classification}, not clean directional behavior.")

    if behavior_classification in ["consolidation", "unknown"]:
        level = _min_level(level, "low")
        blockers.append(f"Behavior classification is {behavior_classification}, which caps eligibility at Low.")

    if not _has_meaningful_behavior_confirmation(record):
        level = _min_level(level, "low")
        if reaction_zone_status == "interacting":
            blockers.append(
                "Price is interacting with a reaction zone, but behavior has not confirmed acceptance/rejection."
            )
        else:
            blockers.append("Meaningful behavior confirmation is required before scanner eligibility can exceed Low.")

    if behavior_classification == "bullish_continuation_compression" and not major_change:
        level = _min_level(level, "low")
        blockers.append("Bullish continuation compression is watch context only until expansion or a major state change appears.")

    if news_risk_level == "high":
        level = _min_level(level, "medium")
        blockers.append("News Risk is High, which caps eligibility at Medium.")
    elif news_risk_level == "medium":
        blockers.append("News Risk is Medium; notification requires cleaner confirmation.")

    if csv_stale:
        if strong_visual:
            reasons.append("CSV is stale, but visual evidence is strong enough to avoid the Low cap.")
        else:
            level = _min_level(level, "low")
            blockers.append("CSV is stale and visual evidence is not strong enough to exceed Low eligibility.")

    if behavior_classification == "bullish_continuation_expansion":
        expansion_can_notify = (
            opportunity_type != "no_opportunity"
            and news_risk_level in ["low", "medium"]
            and (_csv_fresh_or_recent(record) or strong_visual)
        )

        if expansion_can_notify and _level_rank(level) < _level_rank("medium"):
            level = "medium"
            reasons.append("Bullish continuation expansion is matched with sufficient freshness or strong visual evidence.")
            blockers = [
                blocker for blocker in blockers
                if "keeps notification eligibility low" not in blocker
            ]
        elif not expansion_can_notify:
            level = _min_level(level, "low")
            blockers.append("Bullish continuation expansion needs Low/Medium news risk plus fresh/recent CSV or strong visuals before notification.")

    if not has_5m_confirmation:
        if level == "high":
            level = "medium"
        elif level == "medium" and behavior_confidence == "low":
            level = "low"
        blockers.append("5M structure confirmation is unclear, so eligibility is capped at Low/Medium.")
    else:
        reasons.append(structure_confirmation)

    if partial_live_vision:
        level = _min_level(level, "low")
        failed_timeframes = [
            timeframe for timeframe, item in live_status.items()
            if not item.get("capture_success") or not item.get("vision_success")
        ]
        blockers.append(
            "Partial live visual context caps scanner confidence at Low: "
            + ", ".join(failed_timeframes)
            + " failed."
        )
        if not live_status.get("5M", {}).get("vision_success"):
            blockers.append("5M vision is missing, so execution readiness cannot exceed watch/review.")

    vision_quality_status = str(record.get("vision_quality_status") or "").lower()
    if vision_quality_status == "degraded":
        if level == "high":
            level = "medium"
        blockers.append("Vision extraction quality is degraded, so confidence is capped. Treat this as review/watch context, not an alert.")
    elif vision_quality_status == "unreliable":
        level = _min_level(level, "low")
        blockers.append("Vision extraction quality is unreliable, so notification eligibility is disabled.")

    primary_draw = (liquidity_draw.get("primary_draw") or {}).get("label")
    liquidity_confidence = liquidity_draw.get("confidence")
    if primary_draw:
        reasons.append(f"Liquidity Draw points to {primary_draw} with {liquidity_confidence or 'unknown'} confidence.")

    if htf_bias != "unknown" or execution_bias != "unknown":
        reasons.append(f"Bias context: HTF {htf_bias}, execution {execution_bias}.")

    if liquidity_draw_alignment in ["aligned", "weakly_aligned"]:
        reasons.append(f"Liquidity draw alignment is {liquidity_draw_alignment.replace('_', ' ')}.")

    if (
        behavior_classification != "bullish_continuation_expansion"
        and htf_bias != execution_bias
        and htf_bias in ["bullish", "bearish"]
        and execution_bias in ["bullish", "bearish"]
    ):
        blockers.append("HTF bias and execution bias conflict; chart review needs structure resolution.")

    what_to_watch_next.extend(opportunity.get("next_confirmation_needed") or [])
    what_to_watch_next.extend(behavior.get("missing_confirmation") or [])

    if primary_draw:
        what_to_watch_next.append(f"Watch whether price continues toward, sweeps, rejects, or reclaims {primary_draw}.")

    if not what_to_watch_next:
        what_to_watch_next.append("Wait for clearer opportunity, behavior, and 5M structure confirmation.")

    if not reasons and level == "none":
        reasons.append("No notification-worthy chart-review context is active.")

    if not _at_or_above_signal_level(signal_level, SCAN_ALERT_MIN_LEVEL):
        blockers.append(
            f"Scanner signal level is {signal_level}; minimum alert level is {SCAN_ALERT_MIN_LEVEL}."
        )

    if repeat_suppressed:
        blockers.append(f"Repeated same-state scan suppressed for {SCAN_SUPPRESS_REPEATS_MINUTES} minutes.")

    blockers = _dedupe_text(blockers)
    reasons = _dedupe_text(reasons)
    what_to_watch_next = _dedupe_text(what_to_watch_next)
    should_notify = (
        level in ["medium", "high"]
        and _at_or_above_signal_level(signal_level, SCAN_ALERT_MIN_LEVEL)
        and _has_meaningful_behavior_confirmation(record)
        and not repeat_suppressed
        and vision_quality_status not in {"degraded", "unreliable"}
    )

    return {
        "level": level,
        "should_notify": should_notify,
        "reasons": reasons,
        "blockers": blockers,
        "what_to_watch_next": what_to_watch_next,
        "signal_level": signal_level,
        "behavior_confirmation": behavior_confirmation,
        "does_not_generate_trade_signals": True,
    }


def format_alert_eligibility_section(alert_eligibility: dict) -> str:
    level = str(alert_eligibility.get("level") or "none").capitalize()
    notify = "Yes" if alert_eligibility.get("should_notify") else "No"
    reasons = alert_eligibility.get("reasons") or ["No notification-worthy chart-review context is active."]
    blockers = alert_eligibility.get("blockers") or ["No blocker recorded."]
    what_to_watch_next = alert_eligibility.get("what_to_watch_next") or [
        "Wait for clearer opportunity, behavior, and 5M structure confirmation."
    ]

    lines = [
        "## Alert Eligibility",
        f"Level: {level}",
        f"Notify: {notify}",
        "",
        "Reasons:",
    ]
    lines.extend(f"- {item}" for item in reasons)
    lines.extend(["", "Blockers:"])
    lines.extend(f"- {item}" for item in blockers)
    lines.extend(["", "What to watch next:"])
    lines.extend(f"- {item}" for item in what_to_watch_next)

    return "\n".join(lines)


def attach_alert_eligibility(record: dict) -> None:
    alert_eligibility = evaluate_chart_alert_eligibility(record)
    record["alert_eligibility"] = alert_eligibility
    record["message"] = (
        (record.get("message") or "")
        + "\n\n"
        + format_alert_eligibility_section(alert_eligibility)
    ).strip()


def attach_presence_notification_eligibility(record: dict) -> None:
    decision = _presence_notification_decision(record)
    alert_eligibility = record.get("alert_eligibility") or {}
    should_notify_before_presence = bool(alert_eligibility.get("should_notify"))

    record["presence_mode"] = decision["presence_mode"]
    record["notification_allowed_by_presence"] = decision["notification_allowed_by_presence"]
    record["presence_reason"] = decision["presence_reason"]

    if not decision["notification_allowed_by_presence"]:
        blockers = alert_eligibility.get("blockers") or []
        blockers.append(decision["presence_reason"])
        alert_eligibility["blockers"] = _dedupe_text(blockers)

    alert_eligibility["should_notify_before_presence"] = should_notify_before_presence
    alert_eligibility["notification_allowed_by_presence"] = decision["notification_allowed_by_presence"]
    alert_eligibility["presence_mode"] = decision["presence_mode"]
    alert_eligibility["presence_reason"] = decision["presence_reason"]
    alert_eligibility["should_notify"] = (
        should_notify_before_presence and decision["notification_allowed_by_presence"]
    )
    record["alert_eligibility"] = alert_eligibility

    record["message"] = (
        (record.get("message") or "")
        + "\n\n"
        + format_presence_scan_section(decision)
    ).strip()


# -------------------------
# Smart scan notifications
# -------------------------
def _default_notification_status(record: dict | None = None) -> dict:
    alert_eligibility = (record or {}).get("alert_eligibility") or {}

    return {
        "enabled": bool(SCAN_NOTIFY_ENABLED),
        "should_notify": bool(alert_eligibility.get("should_notify")),
        "presence_mode": (record or {}).get("presence_mode"),
        "notification_allowed_by_presence": bool(
            (record or {}).get("notification_allowed_by_presence", True)
        ),
        "presence_reason": (record or {}).get("presence_reason"),
        "imessage_sent": False,
        "tts_spoken": False,
        "errors": [],
    }


def _format_notification_behavior_label(classification: str) -> str:
    return classification.replace("_", " ").title()


def _format_notification_draw(liquidity_draw: dict) -> str:
    primary_draw = liquidity_draw.get("primary_draw") or {}
    label = primary_draw.get("label") or "Unclear"
    price = primary_draw.get("price")

    if price is None:
        return str(label)

    return f"{label} {_fmt_draw_price(price)}"


def build_scan_notification_payload(record: dict) -> dict:
    alert_eligibility = record.get("alert_eligibility") or {}
    behavior = record.get("behavior_classification") or {}
    liquidity_draw = record.get("liquidity_draw") or {}

    return {
        "symbol": record.get("symbol") or SYMBOL,
        "timestamp": record.get("timestamp"),
        "level": str(alert_eligibility.get("level") or "none").capitalize(),
        "behavior_classification": str(behavior.get("classification") or "unknown"),
        "liquidity_draw": _format_notification_draw(liquidity_draw),
        "what_to_watch_next": alert_eligibility.get("what_to_watch_next") or [],
        "screenshot_path": record.get("screenshot_path"),
    }


def format_scan_notification_message(payload: dict) -> str:
    behavior = _format_notification_behavior_label(str(payload.get("behavior_classification") or "unknown"))
    watch_items = payload.get("what_to_watch_next") or []
    watch = str(watch_items[0]) if watch_items else "Watch for 5M continuation and key-level hold."

    if len(watch) > 90:
        watch = watch[:87].rstrip() + "..."

    lines = [
        f"{payload.get('symbol') or SYMBOL} Alert: {behavior}",
        f"Level: {payload.get('level') or 'None'}",
        f"Draw: {payload.get('liquidity_draw') or 'Unclear'}",
        f"Watch: {watch}",
    ]

    if payload.get("screenshot_path"):
        lines.append(f"Screenshot: {payload.get('screenshot_path')}")

    return "\n".join(lines)


def _send_scan_imessage(text: str) -> None:
    from imessage_bridge import send_imessage

    recipient_config = get_default_imessage_recipient()
    recipient = recipient_config["recipient"]

    if not recipient:
        raise ValueError("No iMessage recipient provided or configured.")

    try:
        send_imessage(recipient, text)
    except Exception as e:
        raise RuntimeError(f"iMessage send failed: {type(e).__name__}") from e


def _speak_scan_notification(text: str) -> None:
    subprocess.Popen(
        ["say", text[:500]],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def deliver_scan_notification(record: dict) -> dict:
    status = _default_notification_status(record)

    if not status["enabled"] or not status["should_notify"]:
        record["notification_status"] = status
        return status

    current_presence = get_presence()
    payload = build_scan_notification_payload(record)
    message = format_scan_notification_message(payload)

    if SCAN_NOTIFY_IMESSAGE_ENABLED and current_presence.get("imessage_allowed"):
        try:
            _send_scan_imessage(message)
            status["imessage_sent"] = True
        except Exception as e:
            status["errors"].append(f"iMessage notification failed: {e}")
    elif SCAN_NOTIFY_IMESSAGE_ENABLED:
        status["errors"].append(f"iMessage blocked by {current_presence.get('label')} presence mode.")

    if SCAN_NOTIFY_TTS_ENABLED and current_presence.get("tts_allowed"):
        try:
            _speak_scan_notification(message)
            status["tts_spoken"] = True
        except Exception as e:
            status["errors"].append(f"TTS notification failed: {e}")
    elif SCAN_NOTIFY_TTS_ENABLED:
        status["errors"].append(f"TTS blocked by {current_presence.get('label')} presence mode.")

    if not SCAN_NOTIFY_IMESSAGE_ENABLED and not SCAN_NOTIFY_TTS_ENABLED:
        status["errors"].append("Notifications enabled, but no delivery channel is enabled.")

    record["notification_status"] = status
    return status


# -------------------------
# Runtime scanner status
# -------------------------
def _process_is_running(process_id: int | None) -> bool:
    if not process_id:
        return False

    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False

    return True


def write_scanner_runtime_status(
    *,
    scanner_enabled: bool,
    symbol: str | None = None,
    timeframe: str = SCAN_TIMEFRAME,
    running_scan: bool = False,
    last_scan_timestamp: str | None = None,
    latest_scan_success: bool | None = None,
) -> None:
    now = datetime.now(TIMEZONE)
    sessions = get_active_sessions(now)
    symbol = normalize_scanner_symbol(symbol or get_default_scanner_symbol())

    status = {
        "scanner_enabled": scanner_enabled,
        "process_id": os.getpid(),
        "process_running": True,
        "heartbeat_timestamp": now.isoformat(),
        "timestamp": now.isoformat(),
        "timezone": "America/Denver",
        "symbol": symbol,
        "timeframe": timeframe,
        "htf_source": "CSV",
        "live_vision_timeframes": list(SCHEDULED_SCAN_TIMEFRAMES),
        "conditional_execution_timeframes": list(CONDITIONAL_EXECUTION_TIMEFRAMES),
        "active_sessions": sessions,
        "should_scan_now": should_scan_now(now),
        "scheduled_scan_allowed": scanner_enabled and should_scan_now(now),
        "automatic_scans_paused": not scanner_enabled,
        "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
        "running_scan": running_scan,
        "last_scan_timestamp": last_scan_timestamp,
        "latest_scan_success": latest_scan_success,
    }

    SCAN_RUNTIME_STATUS_PATH.write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _csv_automation_status(scanner_enabled: bool) -> dict:
    try:
        from csv_refresh import get_csv_refresh_status

        csv_status = get_csv_refresh_status()
    except Exception as e:
        return {
            "csv_automation_paused": not scanner_enabled,
            "csv_automation_status": "unknown",
            "csv_automation_message": f"CSV refresh status unavailable: {e}",
            "csv_refresh": None,
        }

    paused = bool(csv_status.get("automation_paused")) or not scanner_enabled
    if paused:
        status_label = "paused"
        message = (
            "CSV refresh paused because scanner is off."
            if not scanner_enabled
            else str(csv_status.get("status_message") or "CSV refresh automation is paused.")
        )
    else:
        status_label = "enabled"
        message = str(csv_status.get("status_message") or "CSV refresh automation is enabled.")

    return {
        "csv_automation_paused": paused,
        "csv_automation_status": status_label,
        "csv_automation_message": message,
        "csv_refresh_last_attempt_result": csv_status.get("last_attempt_result"),
        "csv_refresh_last_attempt_reason": csv_status.get("last_attempt_reason"),
        "csv_refresh_last_success": csv_status.get("last_success"),
        "csv_refresh_last_success_timeframes": csv_status.get("last_success_timeframes") or [],
        "csv_refresh_last_success_files": csv_status.get("last_success_files") or [],
        "csv_refresh": csv_status,
    }


def get_scanner_runtime_status() -> dict:
    now = datetime.now(TIMEZONE)
    sessions = get_active_sessions(now)
    settings = get_scanner_settings()
    symbol = str(settings.get("default_symbol") or get_default_scanner_symbol())
    scanner_enabled = bool(settings.get("scanner_enabled", True))
    latest_scan = load_latest_scan(symbol=symbol)

    runtime_status = {}

    if SCAN_RUNTIME_STATUS_PATH.exists():
        try:
            runtime_status = json.loads(SCAN_RUNTIME_STATUS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            runtime_status = {}

    process_id = runtime_status.get("process_id")
    process_running = _process_is_running(process_id)
    latest_scan_timestamp = latest_scan.get("timestamp") if latest_scan else None
    latest_scan_success = latest_scan.get("success") if latest_scan else None
    session_window_open = should_scan_now(now)
    csv_automation = _csv_automation_status(scanner_enabled)

    return {
        "success": True,
        "symbol": symbol,
        "default_symbol": symbol,
        "supported_symbols": settings.get("supported_symbols") or [],
        "timestamp": now.isoformat(),
        "timezone": "America/Denver",
        "scanner_enabled": scanner_enabled,
        "automatic_scans_paused": not scanner_enabled,
        "process_running": process_running,
        "process_id": process_id,
        "heartbeat_timestamp": runtime_status.get("heartbeat_timestamp"),
        "runtime_status_path": str(SCAN_RUNTIME_STATUS_PATH),
        "active_sessions": sessions,
        "should_scan_now": session_window_open,
        "scheduled_scan_allowed": scanner_enabled and session_window_open,
        "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
        "timeframe": runtime_status.get("timeframe") or SCAN_TIMEFRAME,
        "htf_source": "CSV",
        "live_vision_timeframes": list(SCHEDULED_SCAN_TIMEFRAMES),
        "conditional_execution_timeframes": list(CONDITIONAL_EXECUTION_TIMEFRAMES),
        "running_scan": runtime_status.get("running_scan", False) if process_running else False,
        "last_scan_timestamp": latest_scan_timestamp,
        "latest_scan_success": latest_scan_success,
    } | csv_automation


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
    state = current_record.get("state", {})

    reasons = []
    alert_type = "none"
    severity = "none"

    if (
        current_record.get("success") is False
        or not structural_csv_available(current_record)
        or not has_partial_live_vision(current_record)
    ):
        return {
            "should_alert": False,
            "alert_type": "none",
            "severity": "none",
            "reasons": ["No market alert decision: scanner system health is degraded or failed."],
        }

    # -------------------------
    # Market structure alerts
    # -------------------------
    meaningful_market_change = [
        item for item in market_changes
        if "No major market structure change detected" not in item
        and "No previous successful scan found for comparison" not in item
    ]

    if meaningful_market_change:
        alert_type = "market_state_change"
        severity = "watch"
        reasons.extend(meaningful_market_change)
        reasons.append("Market state changed; behavior confirmation is required before this becomes alert-worthy.")

    # -------------------------
    # Price relation alerts
    # -------------------------
    price_relation = state.get("price_relation")

    if price_relation == "inside_active_zone":
        alert_type = "reaction_zone_interaction" if alert_type == "none" else alert_type
        severity = "watch" if severity == "none" else severity
        reasons.append(
            "Price is interacting with a reaction zone; behavior must confirm acceptance/rejection."
        )

    # -------------------------
    # Visual-only changes
    # -------------------------
    visual_only_change = [
        item for item in visual_context_changes
        if "No major visual context change detected" not in item
    ]

    if visual_only_change:
        # Save it, but do not alert from visual flicker alone.
        reasons.extend(
            f"Visual-only change, no alert: {item}"
            for item in visual_only_change
        )

    if not reasons:
        reasons.append("No alert-worthy change detected.")

    return {
        "should_alert": False,
        "alert_type": alert_type,
        "severity": severity,
        "reasons": reasons,
    }


def _vision_success_by_timeframe(record: dict) -> dict[str, dict]:
    status = live_vision_timeframe_status(record)
    primary_timeframe = record.get("timeframe")
    if primary_timeframe:
        status.setdefault(
            str(primary_timeframe),
            {
                "capture_success": bool(record.get("screenshot_path")),
                "vision_success": bool(record.get("vision_success")),
                "error": record.get("vision_error"),
            },
        )

    for timeframe, capture in (record.get("timeframe_captures") or {}).items():
        capture = capture or {}
        status[str(timeframe)] = {
            "capture_success": bool(capture.get("screenshot_path")),
            "vision_success": bool(capture.get("vision_success")),
            "error": capture.get("vision_error") or capture.get("error"),
        }

    return status


def evaluate_system_health(record: dict) -> dict:
    issues = []
    recovered_issues = []
    affected_sources = set()
    severity_rank = {"none": 0, "low": 1, "medium": 2, "high": 3}
    severity = "none"

    def add_issue(source: str, issue_type: str, message: str, issue_severity: str = "medium") -> None:
        nonlocal severity
        affected_sources.add(source)
        issues.append({
            "source": source,
            "type": issue_type,
            "message": message,
            "severity": issue_severity,
        })
        if severity_rank.get(issue_severity, 0) > severity_rank.get(severity, 0):
            severity = issue_severity

    def add_recovered_issue(source: str, issue_type: str, message: str) -> None:
        recovered_issues.append({
            "source": source,
            "type": issue_type,
            "message": message,
            "recovered": True,
        })

    csv_available = structural_csv_available(record)
    live_success_count = live_vision_success_count(record)
    live_status = live_vision_timeframe_status(record)
    vision_quality_status = str(record.get("vision_quality_status") or "").lower()
    vision_quality_score = record.get("vision_quality_score")

    if not csv_available:
        csv_analysis = record.get("csv_analysis") or {}
        error_text = str(csv_analysis.get("error") or csv_analysis.get("message") or "")
        if "missing" in error_text.lower():
            csv_issue_type = "csv_timeframe_missing"
        elif "refresh" in error_text.lower():
            csv_issue_type = "csv_refresh_failed"
        else:
            csv_issue_type = "csv_analysis_failed"
        add_issue(
            "CSV",
            csv_issue_type,
            error_text or "CSV structural analysis failed.",
            "high",
        )

    if record.get("vision_success") is False and live_success_count == 0:
        add_issue(
            "Vision",
            "primary_vision_failed",
            record.get("vision_error") or "Primary vision extraction failed.",
            "medium",
        )

    if not record.get("screenshot_path") and live_success_count == 0:
        add_issue(
            "Screenshot",
            "primary_screenshot_missing",
            "Primary TradingView screenshot was not captured.",
            "medium",
        )

    if live_success_count == 0:
        add_issue(
            "Vision",
            "all_live_timeframes_failed",
            "Both required live vision timeframes failed.",
            "high",
        )
    elif live_success_count < len(SCHEDULED_SCAN_TIMEFRAMES):
        failed_timeframes = [
            timeframe for timeframe, item in live_status.items()
            if not item.get("capture_success") or not item.get("vision_success")
        ]
        add_issue(
            "Vision",
            "partial_live_timeframe_failure",
            (
                "Partial live visual context only; scanner confidence is capped because "
                f"{', '.join(failed_timeframes)} failed."
            ),
            "medium",
        )

    if vision_quality_status == "unreliable":
        add_issue(
            "Vision",
            "vision_quality_unreliable",
            f"Vision extraction quality score is unreliable ({vision_quality_score}); behavior interpretation is not trusted.",
            "medium",
        )
    elif vision_quality_status == "degraded":
        add_issue(
            "Vision",
            "vision_quality_degraded",
            f"Vision extraction quality score is degraded ({vision_quality_score}); scanner confidence is capped.",
            "low",
        )

    for timeframe, capture in (record.get("timeframe_captures") or {}).items():
        capture = capture or {}
        if not capture.get("screenshot_path"):
            issue_type = str(capture.get("error") or "").lower()
            add_issue(
                "TradingView" if "profile lock" in issue_type or "singletonlock" in issue_type else "Screenshot",
                "timeframe_screenshot_failed",
                f"{timeframe}: {capture.get('error') or 'screenshot was not captured.'}",
                "medium",
            )
        elif capture.get("vision_success") is False:
            add_issue(
                "Vision",
                "timeframe_vision_failed",
                f"{timeframe}: {capture.get('vision_error') or 'vision extraction failed.'}",
                "low",
            )

        if capture.get("system_health_issue") == "tradingview_profile_lock_busy":
            add_issue(
                "TradingView",
                "tradingview_profile_lock_busy",
                f"{timeframe}: {capture.get('error') or 'TradingView profile lock was busy.'}",
                "medium",
            )
        elif capture.get("system_health_issue") == "capture_result_missing_but_file_found":
            add_recovered_issue(
                "Screenshot",
                "capture_result_missing_but_file_found",
                f"{timeframe}: {capture.get('capture_warning') or 'Screenshot capture result was missing, but saved screenshot was found and used.'}",
            )

    error_text = str(record.get("error") or "")
    if error_text:
        source = "TradingView" if "profile lock" in error_text.lower() or "singletonlock" in error_text.lower() else "Scanner"
        add_issue(source, "scan_failed", error_text, "high")

    if record.get("system_health_issue") == "tradingview_profile_lock_busy":
        add_issue(
            "TradingView",
            "tradingview_profile_lock_busy",
            record.get("error") or "TradingView profile lock was busy.",
            "medium",
        )

    if _csv_is_stale(record):
        add_issue(
            "CSV",
            "csv_available_but_stale",
            "CSV is stale; using it only for structural context.",
            "medium",
        )

    status = "healthy"
    if severity in {"low", "medium"}:
        status = "degraded"
    elif severity == "high":
        status = "failed"

    deduped_issues = []
    seen_issues = set()
    for issue in issues:
        key = (
            issue.get("source"),
            issue.get("type"),
            issue.get("message"),
        )
        if key in seen_issues:
            continue
        seen_issues.add(key)
        deduped_issues.append(issue)

    return {
        "status": status,
        "issues": deduped_issues,
        "recovered_issues": recovered_issues,
        "should_notify": status == "failed",
        "severity": severity,
        "affected_sources": sorted(affected_sources),
        "vision_success_by_timeframe": _vision_success_by_timeframe(record),
    }


def attach_system_health(record: dict) -> None:
    record["system_health"] = evaluate_system_health(record)
    record["vision_success_by_timeframe"] = record["system_health"].get("vision_success_by_timeframe") or {}
    record["recovered_issues"] = record["system_health"].get("recovered_issues") or []
    issues = record["system_health"].get("issues") or []
    issue_lines = [
        f"- {issue.get('source')}: {issue.get('message')}"
        for issue in issues
    ] or ["- No scanner system health issues detected."]
    record["message"] = (
        (record.get("message") or "")
        + "\n\n"
        + "## Scanner System Health\n"
        + f"Status: {str(record['system_health'].get('status') or 'healthy').capitalize()}\n"
        + f"Severity: {str(record['system_health'].get('severity') or 'none').capitalize()}\n"
        + "Issues:\n"
        + "\n".join(issue_lines)
    ).strip()


def attach_market_alert(record: dict) -> None:
    eligibility = record.get("alert_eligibility") or {}
    record["market_alert"] = {
        "level": eligibility.get("level") or "none",
        "notify": bool(eligibility.get("should_notify")),
        "signal_level": record.get("signal_level") or "informational",
        "reasons": eligibility.get("reasons") or [],
        "blockers": eligibility.get("blockers") or [],
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
    symbol: str = SYMBOL,
    comparison: dict | None = None,
    alert: dict | None = None,
) -> dict:
    symbol = normalize_scanner_symbol(symbol)
    visual_extraction = result.get("visual_extraction", {}) or {}
    csv_analysis = result.get("csv_analysis", {}) or {}

    record = {
        "timestamp": now.isoformat(),
        "timezone": "America/Denver",
        "symbol": symbol,
        "timeframe": result.get("timeframe"),
        "sessions": sessions,
        "session_label": " + ".join(sessions),
        "success": result.get("success", False),
        "error": result.get("error"),
        "system_health_issue": result.get("system_health_issue"),
        "affected_source": result.get("affected_source"),
        "screenshot_path": result.get("screenshot_path"),
        "timeframe_captures": result.get("timeframe_captures") or {},
        "screenshots_requested": result.get("screenshots_requested") or list(SCHEDULED_SCAN_TIMEFRAMES),
        "screenshots_captured": result.get("screenshots_captured")
        or _captured_timeframes(result.get("timeframe_captures") or {}),
        "csv_timeframes_used": result.get("csv_timeframes_used") or list(HTF_CSV_TIMEFRAMES),
        "one_minute_capture_reason": result.get("one_minute_capture_reason"),
        "scanner_source_roles": result.get("scanner_source_roles") or scanner_source_roles(),
        "scanner_mode": "htf_map",
        "scanner_state": "htf_map",
        "scanner_mode_label": "Htf Map",
        "vision_success": visual_extraction.get("success", False),
        "vision_error": visual_extraction.get("error"),
        "vision_model": visual_extraction.get("model"),
        "vision_quality_score": visual_extraction.get("vision_quality_score"),
        "vision_quality_status": visual_extraction.get("vision_quality_status"),
        "vision_quality_issues": visual_extraction.get("vision_quality_issues") or [],
        "csv_success": csv_analysis.get("success", False),
        "csv_analysis": csv_analysis,
        "csv_freshness": csv_analysis.get("csv_freshness")
        or csv_analysis.get("analysis", {}).get("csv_freshness"),
        "news_risk": result.get("news_risk"),
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
        "market_alert": {
            "level": "none",
            "notify": False,
            "signal_level": "informational",
            "reasons": [],
            "blockers": [],
        },
        "system_health": {
            "status": "healthy",
            "issues": [],
            "should_notify": False,
            "severity": "none",
            "affected_sources": [],
            "vision_success_by_timeframe": {},
        },
        "vision_success_by_timeframe": {},
        "alert_eligibility": {
            "level": "none",
            "should_notify": False,
            "reasons": [],
            "blockers": [],
            "what_to_watch_next": [],
            "does_not_generate_trade_signals": True,
        },
        "signal_level": "informational",
        "signal_reason": "Normal Liquidity Narrative Continuation scan update.",
        "narrative_state": "no_clear_narrative",
        "narrative_phase": "no_clear_narrative",
        "narrative_confidence": "low",
        "narrative": {
            "liquidity_draw": "None identified",
            "liquidity_draw_direction": "unclear",
            "htf_reaction_zone": "Unclear",
            "reaction_zone_timeframe": "unclear",
            "reaction_zone_type": "reaction_zone",
            "reaction_zone_status": "unclear",
            "behavior_inside_zone": "none",
            "structure_confirmation": "5M unclear",
            "execution_readiness": "not_ready",
            "target_liquidity": "None identified",
            "invalidation_context": "No invalidation evidence detected.",
            "narrative_phase": "no_clear_narrative",
            "narrative_confidence": "low",
            "missing_confirmations": [],
            "does_not_generate_trade_signals": True,
        },
        "reaction_zone_status": "unclear",
        "behavior_confirmation": "none",
        "liquidity_draw_alignment": "unclear",
        "repeat_suppressed": False,
        "presence_mode": "home",
        "notification_allowed_by_presence": False,
        "presence_reason": "Home mode requires review signal or stronger; current signal is informational.",
        "notification_status": {
            "enabled": bool(SCAN_NOTIFY_ENABLED),
            "should_notify": False,
            "presence_mode": "home",
            "notification_allowed_by_presence": False,
            "presence_reason": "Home mode requires review signal or stronger; current signal is informational.",
            "imessage_sent": False,
            "tts_spoken": False,
            "errors": [],
        },
        "current_attempt_valid_market_state": False,
        "screenshot_cleanup": _default_screenshot_cleanup_result(),
    }

    record["state"] = extract_structured_state(record)

    return record


def is_valid_market_scan(record: dict | None) -> bool:
    if not record:
        return False
    if not structural_csv_available(record):
        return False
    if not has_partial_live_vision(record):
        return False
    system_health = record.get("system_health") or {}
    if system_health.get("status") == "failed":
        return False
    return True


def promote_partial_scan_result_if_possible(result: dict, timeframe_captures: dict | None, symbol: str) -> dict:
    if not isinstance(result, dict):
        result = {
            "success": False,
            "symbol": normalize_scanner_symbol(symbol),
            "timeframe": SCAN_TIMEFRAME,
            "error": "Primary TradingView analysis returned no result.",
            "message": "Primary TradingView analysis returned no result.",
        }

    result["timeframe_captures"] = timeframe_captures or {}

    if result.get("csv_analysis"):
        return result

    live_successes = [
        capture for capture in (timeframe_captures or {}).values()
        if isinstance(capture, dict)
        and capture.get("screenshot_path")
        and capture.get("vision_success")
    ]
    if not live_successes:
        return result

    csv_result = analyze_market_csv(symbol=symbol)
    result["csv_analysis"] = csv_result
    result["csv_freshness"] = csv_result.get("csv_freshness") or (csv_result.get("analysis") or {}).get("csv_freshness")

    if not csv_result.get("success"):
        return result

    partial_capture = live_successes[0]
    result.update({
        "success": True,
        "partial_live_context": True,
        "partial_scan_error": result.get("error"),
        "error": None,
        "timeframe": partial_capture.get("timeframe") or result.get("timeframe"),
        "screenshot_path": partial_capture.get("screenshot_path"),
        "visual_extraction": partial_capture.get("visual_extraction") or {},
        "message": (
            "Partial scanner scan completed with HTF CSV structure and one live vision timeframe. "
            "Scanner confidence is capped because another live timeframe failed."
        ),
    })
    return result


# -------------------------
# Scan history lookup
# -------------------------
def load_latest_scan(symbol: str | None = None) -> dict | None:
    if not SCAN_HISTORY_PATH.exists():
        return None

    symbol = normalize_scanner_symbol(symbol or get_default_scanner_symbol())
    latest = None

    with SCAN_HISTORY_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if record.get("symbol") != symbol:
                continue

            latest = normalize_narrative_scanner_state(record)

    return latest


def load_last_successful_scan(
    current_timestamp: str | None = None,
    symbol: str | None = None,
) -> dict | None:
    if not SCAN_HISTORY_PATH.exists():
        return None

    symbol = normalize_scanner_symbol(symbol or get_default_scanner_symbol())
    last_scan = None

    with SCAN_HISTORY_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if current_timestamp and record.get("timestamp") == current_timestamp:
                continue

            if record.get("symbol") != symbol:
                continue

            if not is_valid_market_scan(record):
                continue

            last_scan = normalize_narrative_scanner_state(record)

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
def run_scan(
    force: bool = False,
    update_runtime_status: bool = False,
    timeframe: str = SCAN_TIMEFRAME,
    multi_timeframe: bool = False,
    symbol: str | None = None,
) -> dict | None:
    now = datetime.now(TIMEZONE)
    sessions = get_active_sessions(now)
    scan_symbol = normalize_scanner_symbol(symbol or get_default_scanner_symbol())
    timeframe = timeframe.upper()
    primary_timeframe = SCAN_TIMEFRAME if multi_timeframe else timeframe
    status_timeframe = scheduled_timeframe_label() if multi_timeframe else primary_timeframe

    if not force and not sessions:
        print(f"[{now.isoformat()}] Outside scan window. No scan ran.")
        return None

    session_label = " + ".join(sessions) if sessions else "Forced Scan"
    screenshot_cleanup = _default_screenshot_cleanup_result()

    print(f"[{now.isoformat()}] Running {scan_symbol} {status_timeframe} scan during: {session_label}")

    try:
        if update_runtime_status:
            write_scanner_runtime_status(
                scanner_enabled=True,
                symbol=scan_symbol,
                timeframe=status_timeframe,
                running_scan=True,
            )

        screenshot_cleanup = cleanup_scan_screenshots(symbol=scan_symbol)
        print("Screenshot cleanup mode:", screenshot_cleanup.get("mode"))
        print("Screenshot cleanup deleted:", screenshot_cleanup.get("deleted_count", 0))
        for error in screenshot_cleanup.get("errors", []):
            print("Screenshot cleanup error:", error)

        result = analyze_tradingview(
            symbol=scan_symbol,
            timeframe=primary_timeframe,
            prompt=f"Scheduled {scan_symbol} scan during {session_label}. Analyze with marked levels.",
        )

        if multi_timeframe:
            timeframe_captures = collect_scheduled_timeframe_captures(
                symbol=scan_symbol,
                primary_timeframe=primary_timeframe,
                primary_result=result,
                session_label=session_label,
            )
        else:
            timeframe_captures = {}

        if multi_timeframe:
            result = promote_partial_scan_result_if_possible(
                result,
                timeframe_captures,
                scan_symbol,
            )

        attach_news_risk(result, now)

        if multi_timeframe:
            attach_timeframe_screenshots_section(result, timeframe_captures)

        previous_scan = load_last_successful_scan(symbol=scan_symbol)

        temporary_record = build_scan_record(
            result=result,
            now=now,
            sessions=sessions if sessions else ["Forced Scan"],
            symbol=scan_symbol,
        )

        comparison = compare_structured_states(previous_scan, temporary_record)

        temporary_record["comparison"] = comparison
        alert = evaluate_alert_eligibility(comparison, temporary_record)

        record = build_scan_record(
            result=result,
            now=now,
            sessions=sessions if sessions else ["Forced Scan"],
            symbol=scan_symbol,
            comparison=comparison,
            alert=alert,
        )

        attach_liquidity_draw(record)
        attach_behavior_classification(record)
        attach_opportunity_watch(record)
        attach_narrative_scanner_state(record)
        _append_one_minute_execution_context(
            record,
            symbol=scan_symbol,
            session_label=session_label,
        )
        attach_system_health(record)
        attach_scanner_signal(record, previous_scan=previous_scan, now=now)
        attach_alert_eligibility(record)
        attach_market_alert(record)
        attach_scanner_mode(record)
        attach_presence_notification_eligibility(record)
        record["current_attempt_valid_market_state"] = bool(is_valid_market_scan(record))
        deliver_scan_notification(record)
        record["screenshot_cleanup"] = screenshot_cleanup

        save_scan_record(record)

        if update_runtime_status:
            write_scanner_runtime_status(
                scanner_enabled=True,
                symbol=scan_symbol,
                timeframe=status_timeframe,
                running_scan=False,
                last_scan_timestamp=record.get("timestamp"),
                latest_scan_success=record.get("success"),
            )

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

        print()
        print("Alert eligibility:")
        alert_eligibility = record.get("alert_eligibility", {})
        print("Level:", alert_eligibility.get("level"))
        print("Notify:", alert_eligibility.get("should_notify"))
        print("Signal level:", record.get("signal_level"))
        print("Repeat suppressed:", record.get("repeat_suppressed"))
        print("Reasons:")
        for item in alert_eligibility.get("reasons", []):
            print("-", item)
        print("Blockers:")
        for item in alert_eligibility.get("blockers", []):
            print("-", item)

        return record

    except Exception as e:
        error_record = {
            "timestamp": now.isoformat(),
            "timezone": "America/Denver",
            "symbol": scan_symbol,
            "timeframe": primary_timeframe,
            "timeframe_captures": {},
            "screenshots_requested": list(SCHEDULED_SCAN_TIMEFRAMES),
            "screenshots_captured": [],
            "csv_timeframes_used": list(HTF_CSV_TIMEFRAMES),
            "one_minute_capture_reason": None,
            "scanner_source_roles": scanner_source_roles(),
            "scanner_mode": "htf_map",
            "scanner_state": "htf_map",
            "scanner_mode_label": "Htf Map",
            "sessions": sessions if sessions else ["Forced Scan"],
            "session_label": session_label,
            "success": False,
            "error": str(e),
            "alert_eligibility": {
                "level": "none",
                "should_notify": False,
                "reasons": ["Scan failed before alert eligibility could be evaluated."],
                "blockers": [str(e)],
                "what_to_watch_next": [f"Fix the scan failure, then rerun {scan_symbol} chart review."],
                "does_not_generate_trade_signals": True,
            },
            "signal_level": "informational",
            "signal_reason": "Scan failed before scanner signal could be evaluated.",
            "narrative_state": "scan_failed",
            "narrative_phase": "no_clear_narrative",
            "narrative_confidence": "low",
            "narrative": {
                "liquidity_draw": "None identified",
                "liquidity_draw_direction": "unclear",
                "htf_reaction_zone": "Unclear",
                "reaction_zone_timeframe": "unclear",
                "reaction_zone_type": "reaction_zone",
                "reaction_zone_status": "unclear",
                "behavior_inside_zone": "none",
                "structure_confirmation": "5M unclear",
                "execution_readiness": "not_ready",
                "target_liquidity": "None identified",
                "invalidation_context": "Scan failed before narrative state could be evaluated.",
                "narrative_phase": "no_clear_narrative",
                "narrative_confidence": "low",
                "missing_confirmations": [f"Fix the scan failure, then rerun {scan_symbol} chart review."],
                "does_not_generate_trade_signals": True,
            },
            "reaction_zone_status": "unclear",
            "behavior_confirmation": "none",
            "liquidity_draw_alignment": "unclear",
            "repeat_suppressed": False,
            "presence_mode": "home",
            "notification_allowed_by_presence": False,
            "presence_reason": "Home mode requires review signal or stronger; current signal is informational.",
            "notification_status": {
                "enabled": bool(SCAN_NOTIFY_ENABLED),
                "should_notify": False,
                "presence_mode": "home",
                "notification_allowed_by_presence": False,
                "presence_reason": "Home mode requires review signal or stronger; current signal is informational.",
                "imessage_sent": False,
                "tts_spoken": False,
                "errors": [],
            },
            "current_attempt_valid_market_state": False,
            "screenshot_cleanup": screenshot_cleanup,
        }
        attach_system_health(error_record)
        attach_market_alert(error_record)
        error_record["current_attempt_valid_market_state"] = False
        attach_presence_notification_eligibility(error_record)

        save_scan_record(error_record)

        if update_runtime_status:
            write_scanner_runtime_status(
                scanner_enabled=True,
                symbol=scan_symbol,
                timeframe=status_timeframe,
                running_scan=False,
                last_scan_timestamp=error_record.get("timestamp"),
                latest_scan_success=False,
            )

        print("Scan failed:", e)
        return error_record


def run_scheduled_scan_iteration(timeframe: str = SCAN_TIMEFRAME) -> dict | None:
    settings = get_scanner_settings()
    loop_symbol = normalize_scanner_symbol(
        str(settings.get("default_symbol") or get_default_scanner_symbol())
    )
    scanner_enabled = bool(settings.get("scanner_enabled", True))
    latest_scan = load_latest_scan(symbol=loop_symbol)

    if not scanner_enabled:
        print(
            f"[{datetime.now(TIMEZONE).isoformat()}] Scanner paused in settings. "
            "Skipping automatic scan."
        )
        write_scanner_runtime_status(
            scanner_enabled=False,
            symbol=loop_symbol,
            timeframe=scheduled_timeframe_label(),
            running_scan=False,
            last_scan_timestamp=latest_scan.get("timestamp") if latest_scan else None,
            latest_scan_success=latest_scan.get("success") if latest_scan else None,
        )
        return None

    record = run_scan(
        force=False,
        update_runtime_status=True,
        timeframe=timeframe,
        multi_timeframe=True,
        symbol=loop_symbol,
    )
    latest_scan = load_latest_scan(symbol=loop_symbol)
    write_scanner_runtime_status(
        scanner_enabled=True,
        symbol=loop_symbol,
        timeframe=scheduled_timeframe_label(),
        last_scan_timestamp=latest_scan.get("timestamp") if latest_scan else None,
        latest_scan_success=latest_scan.get("success") if latest_scan else None,
    )
    return record


def run_loop(timeframe: str = SCAN_TIMEFRAME) -> None:
    timeframe = SCAN_TIMEFRAME
    initial_settings = get_scanner_settings()
    initial_symbol = str(initial_settings.get("default_symbol") or get_default_scanner_symbol())
    initial_enabled = bool(initial_settings.get("scanner_enabled", True))

    print("Scheduled scanner started.")
    print(f"Default symbol: {initial_symbol}")
    print(f"Timeframes: {scheduled_timeframe_label()}")
    print(f"Primary analysis timeframe: {timeframe}")
    print(f"Interval: {SCAN_INTERVAL_SECONDS // 60} minutes")
    print(f"History file: {SCAN_HISTORY_PATH}")
    print("Press CTRL+C to stop.")
    print()

    latest_scan = load_latest_scan(symbol=initial_symbol)
    write_scanner_runtime_status(
        scanner_enabled=initial_enabled,
        symbol=initial_symbol,
        timeframe=scheduled_timeframe_label(),
        last_scan_timestamp=latest_scan.get("timestamp") if latest_scan else None,
        latest_scan_success=latest_scan.get("success") if latest_scan else None,
    )

    try:
        while True:
            run_scheduled_scan_iteration(timeframe=timeframe)
            time.sleep(SCAN_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Scheduled scanner stopped.")
    finally:
        final_symbol = get_default_scanner_symbol()
        latest_scan = load_latest_scan(symbol=final_symbol)
        write_scanner_runtime_status(
            scanner_enabled=False,
            symbol=final_symbol,
            timeframe=scheduled_timeframe_label(),
            last_scan_timestamp=latest_scan.get("timestamp") if latest_scan else None,
            latest_scan_success=latest_scan.get("success") if latest_scan else None,
        )


# -------------------------
# CLI entrypoint
# -------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scheduled futures chart scanner.")
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
    parser.add_argument(
        "--timeframe",
        default=SCAN_TIMEFRAME,
        help=(
            "TradingView timeframe for forced manual scans. "
            f"Scheduled scans always collect {scheduled_timeframe_label()} with {SCAN_TIMEFRAME} primary analysis."
        ),
    )
    parser.add_argument(
        "--symbol",
        default=None,
        help="Scanner symbol for this run. Defaults to scanner_settings.json default_symbol.",
    )

    args = parser.parse_args()

    if args.force:
        run_scan(force=True, timeframe=args.timeframe, symbol=args.symbol)
    elif args.once:
        run_scan(force=False, timeframe=SCAN_TIMEFRAME, multi_timeframe=True, symbol=args.symbol)
    else:
        run_loop()
