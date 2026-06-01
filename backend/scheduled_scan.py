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
from tools import (
    analyze_tradingview,
    capture_tradingview,
    extract_tradingview_visuals_from_path,
)


# -------------------------
# Scan configuration
# -------------------------
SYMBOL = "MES"
SCAN_TIMEFRAME = "15M"
SCHEDULED_SCAN_TIMEFRAMES = ["4H", "1H", "15M", "5M"]
SCAN_INTERVAL_SECONDS = 5 * 60
TIMEZONE = ZoneInfo("America/Denver")


SCAN_NOTIFY_ENABLED = os.getenv("SCAN_NOTIFY_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
SCAN_NOTIFY_IMESSAGE_ENABLED = os.getenv("SCAN_NOTIFY_IMESSAGE_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
SCAN_NOTIFY_TTS_ENABLED = os.getenv("SCAN_NOTIFY_TTS_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}

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


def cleanup_scan_screenshots() -> dict:
    result = _default_screenshot_cleanup_result()

    try:
        if not SCAN_SCREENSHOTS_DIR.exists():
            return result

        screenshot_files = [
            path
            for path in SCAN_SCREENSHOTS_DIR.glob(f"{SYMBOL}_*.png")
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
def _build_timeframe_capture_from_result(timeframe: str, result: dict) -> dict:
    visual_extraction = result.get("visual_extraction") or {}

    return {
        "timeframe": timeframe,
        "success": bool(result.get("screenshot_path")),
        "screenshot_path": result.get("screenshot_path"),
        "visual_extraction": visual_extraction,
        "vision_success": visual_extraction.get("success", False),
        "vision_error": visual_extraction.get("error"),
        "error": result.get("error"),
    }


def _capture_timeframe_context(
    *,
    timeframe: str,
    prompt: str,
) -> dict:
    capture_result = capture_tradingview(symbol=SYMBOL, timeframe=timeframe)

    if not capture_result.get("success"):
        return {
            "timeframe": timeframe,
            "success": False,
            "screenshot_path": None,
            "visual_extraction": None,
            "vision_success": False,
            "vision_error": None,
            "error": capture_result.get("error") or capture_result.get("message"),
        }

    screenshot_path = capture_result.get("screenshot_path")
    visual_extraction = extract_tradingview_visuals_from_path(
        image_path=screenshot_path,
        prompt=prompt,
        symbol=SYMBOL,
        source=f"scheduled {timeframe} TradingView capture",
    )

    return {
        "timeframe": timeframe,
        "success": True,
        "screenshot_path": screenshot_path,
        "visual_extraction": visual_extraction,
        "vision_success": visual_extraction.get("success", False),
        "vision_error": visual_extraction.get("error"),
        "error": None,
    }


def collect_scheduled_timeframe_captures(
    *,
    primary_timeframe: str,
    primary_result: dict,
    session_label: str,
) -> dict:
    prompt = (
        f"Scheduled {SYMBOL} scan during {session_label}. "
        "Extract visible user markings only."
    )
    captures = {}

    for timeframe in SCHEDULED_SCAN_TIMEFRAMES:
        if timeframe == primary_timeframe:
            captures[timeframe] = _build_timeframe_capture_from_result(
                timeframe=timeframe,
                result=primary_result,
            )
            continue

        try:
            captures[timeframe] = _capture_timeframe_context(
                timeframe=timeframe,
                prompt=prompt,
            )
        except Exception as e:
            captures[timeframe] = {
                "timeframe": timeframe,
                "success": False,
                "screenshot_path": None,
                "visual_extraction": None,
                "vision_success": False,
                "vision_error": None,
                "error": str(e),
            }

    return captures


def format_timeframe_screenshots_section(timeframe_captures: dict | None) -> str:
    lines = ["## Timeframe Screenshots"]

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
        for timeframe in ["15M", "5M", "1H", "4H"]
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

    for capture_timeframe in ["4H", "1H", "15M", "5M"]:
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

    capture_priority = ["4H", "1H", "15M", "5M"]
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

    timeframe_label = "/".join(timeframes) if timeframes else "Visual"

    return {
        "source": "visual",
        "label": f"Visual {timeframe_label} FVG{_format_visual_zone_bounds(all_prices)}",
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
    for timeframe in ["4H", "1H", "15M"]:
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
        "inside_active_zone": "inside active FVG",
        "above_active_zone": "above active FVG",
        "below_active_zone": "below active FVG",
    }

    if active_zone and active_zone.get("source") == "visual":
        timeframes = "/".join(active_zone.get("timeframes") or []) or "visual"
        parts.append(f"around Visual {timeframes} FVG")
    elif price_relation in relation_labels:
        parts.append(relation_labels[price_relation])
    elif active_zone and active_zone.get("relation_to_price"):
        relation = str(active_zone.get("relation_to_price")).replace("_", " ")
        parts.append(f"{relation} relative to active FVG")

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

    for timeframe in ["15M", "1M"]:
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
    visual_text_htf = " ".join(
        text for timeframe, text in text_by_timeframe.items()
        if timeframe in ["1H", "4H"] and text
    )
    visual_text_all = " ".join(text for text in text_by_timeframe.values() if text)

    evidence = []
    missing_confirmation = []
    data_limitations = []
    reaction_zone, active_zone, reaction_zone_source = _active_reaction_zone(record, visual_text_all)
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
        "1H/4H": 1,
    }
    weighted_scores = {classification: 0 for classification in BEHAVIOR_CLASSIFICATIONS}

    for classification, terms in behavior_terms.items():
        matches_15m = _behavior_term_matches(visual_text_15m, terms)
        matches_5m = _behavior_term_matches(visual_text_5m, terms)
        matches_htf = _behavior_term_matches(visual_text_htf, terms)
        weighted_scores[classification] = (
            len(matches_15m) * timeframe_weights["15M"]
            + min(len(matches_5m), 2) * timeframe_weights["5M"]
            + len(matches_htf) * timeframe_weights["1H/4H"]
        )

        if matches_15m:
            evidence.append(f"15M behavior evidence for {classification}: {', '.join(matches_15m[:4])}.")
        if matches_5m:
            evidence.append(f"5M structure evidence for {classification}: {', '.join(matches_5m[:4])}.")
        if matches_htf:
            evidence.append(f"1H/4H context evidence for {classification}: {', '.join(matches_htf[:4])}.")

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
    has_htf_context = bool(visual_text_htf)

    evidence.append(f"Framework hierarchy: liquidity draw -> HTF reaction zone -> behavior -> 15M context -> 5M structure.")
    evidence.append(f"Reaction zone is treated as decision context, not an entry signal: {reaction_zone}.")

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

    if expansion_pattern_match.get("matched"):
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
    elif classification_score >= 7 and has_15m_directional_behavior and (has_5m_confirmation or has_htf_context):
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
        missing_confirmation.append("Need cleaner directional behavior around the marked level or FVG.")
    else:
        missing_confirmation.append("Need clearer live visual behavior around the marked level or zone.")

    if htf_bias != execution_bias and htf_bias in ["bullish", "bearish"] and execution_bias in ["bullish", "bearish"]:
        missing_confirmation.append("HTF and execution bias conflict; confidence is capped until structure resolves.")

    if not has_5m_confirmation:
        missing_confirmation.append("Missing 5M confirmation caps confidence at Medium.")

    if not record.get("vision_success"):
        data_limitations.append("Primary visual extraction did not succeed.")

    missing_visual_tfs = [
        timeframe for timeframe in ["15M", "5M", "1H", "4H"]
        if not text_by_timeframe.get(timeframe)
    ]

    if missing_visual_tfs:
        data_limitations.append(f"Missing readable visual context for: {', '.join(missing_visual_tfs)}.")

    if csv_stale:
        data_limitations.append("CSV is stale; live acceptance/rejection is not classified from CSV close.")

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
        has_15m_directional_behavior and (has_5m_confirmation or has_htf_context)
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
    lines.extend(["", format_golden_pattern_check_section(golden_pattern_match)])
    lines.extend(["", format_continuation_pattern_check_section(continuation_pattern_match)])
    lines.extend(["", format_expansion_pattern_check_section(expansion_pattern_match)])

    return "\n".join(lines)


def attach_behavior_classification(record: dict) -> None:
    behavior = classify_behavior(record)
    record["behavior_classification"] = behavior
    record["message"] = (
        (record.get("message") or "")
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

        for timeframe in ["1M", "15M"]:
            item = freshness.get(timeframe) or {}
            if isinstance(item, dict) and item.get("is_stale"):
                return True

    return False


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
        risks.append("CSV freshness is stale, so computed current price should be treated as historical context.")

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

    primary_draw = (liquidity_draw.get("primary_draw") or {}).get("label")
    liquidity_confidence = liquidity_draw.get("confidence")
    if primary_draw:
        reasons.append(f"Liquidity Draw points to {primary_draw} with {liquidity_confidence or 'unknown'} confidence.")

    if htf_bias != "unknown" or execution_bias != "unknown":
        reasons.append(f"Bias context: HTF {htf_bias}, execution {execution_bias}.")

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

    blockers = _dedupe_text(blockers)
    reasons = _dedupe_text(reasons)
    what_to_watch_next = _dedupe_text(what_to_watch_next)
    should_notify = level in ["medium", "high"]

    return {
        "level": level,
        "should_notify": should_notify,
        "reasons": reasons,
        "blockers": blockers,
        "what_to_watch_next": what_to_watch_next,
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


# -------------------------
# Smart scan notifications
# -------------------------
def _default_notification_status(record: dict | None = None) -> dict:
    alert_eligibility = (record or {}).get("alert_eligibility") or {}

    return {
        "enabled": bool(SCAN_NOTIFY_ENABLED),
        "should_notify": bool(alert_eligibility.get("should_notify")),
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

    payload = build_scan_notification_payload(record)
    message = format_scan_notification_message(payload)

    if SCAN_NOTIFY_IMESSAGE_ENABLED:
        try:
            _send_scan_imessage(message)
            status["imessage_sent"] = True
        except Exception as e:
            status["errors"].append(f"iMessage notification failed: {e}")

    if SCAN_NOTIFY_TTS_ENABLED:
        try:
            _speak_scan_notification(message)
            status["tts_spoken"] = True
        except Exception as e:
            status["errors"].append(f"TTS notification failed: {e}")

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
    timeframe: str = SCAN_TIMEFRAME,
    running_scan: bool = False,
    last_scan_timestamp: str | None = None,
    latest_scan_success: bool | None = None,
) -> None:
    now = datetime.now(TIMEZONE)
    sessions = get_active_sessions(now)

    status = {
        "scanner_enabled": scanner_enabled,
        "process_id": os.getpid(),
        "process_running": scanner_enabled,
        "heartbeat_timestamp": now.isoformat(),
        "timestamp": now.isoformat(),
        "timezone": "America/Denver",
        "symbol": SYMBOL,
        "timeframe": timeframe,
        "active_sessions": sessions,
        "should_scan_now": should_scan_now(now),
        "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
        "running_scan": running_scan,
        "last_scan_timestamp": last_scan_timestamp,
        "latest_scan_success": latest_scan_success,
    }

    SCAN_RUNTIME_STATUS_PATH.write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_scanner_runtime_status() -> dict:
    now = datetime.now(TIMEZONE)
    sessions = get_active_sessions(now)
    latest_scan = load_latest_scan()

    runtime_status = {}

    if SCAN_RUNTIME_STATUS_PATH.exists():
        try:
            runtime_status = json.loads(SCAN_RUNTIME_STATUS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            runtime_status = {}

    process_id = runtime_status.get("process_id")
    process_running = _process_is_running(process_id)
    scanner_enabled = bool(runtime_status.get("scanner_enabled") and process_running)

    latest_scan_timestamp = latest_scan.get("timestamp") if latest_scan else None
    latest_scan_success = latest_scan.get("success") if latest_scan else None

    return {
        "success": True,
        "symbol": SYMBOL,
        "timestamp": now.isoformat(),
        "timezone": "America/Denver",
        "scanner_enabled": scanner_enabled,
        "process_running": process_running,
        "process_id": process_id,
        "heartbeat_timestamp": runtime_status.get("heartbeat_timestamp"),
        "runtime_status_path": str(SCAN_RUNTIME_STATUS_PATH),
        "active_sessions": sessions,
        "should_scan_now": should_scan_now(now),
        "scan_interval_seconds": SCAN_INTERVAL_SECONDS,
        "timeframe": runtime_status.get("timeframe") or SCAN_TIMEFRAME,
        "running_scan": runtime_status.get("running_scan", False) if process_running else False,
        "last_scan_timestamp": latest_scan_timestamp,
        "latest_scan_success": latest_scan_success,
    }


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
        "timeframe": result.get("timeframe"),
        "sessions": sessions,
        "session_label": " + ".join(sessions),
        "success": result.get("success", False),
        "screenshot_path": result.get("screenshot_path"),
        "timeframe_captures": result.get("timeframe_captures") or {},
        "vision_success": visual_extraction.get("success", False),
        "vision_error": visual_extraction.get("error"),
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
        "alert_eligibility": {
            "level": "none",
            "should_notify": False,
            "reasons": [],
            "blockers": [],
            "what_to_watch_next": [],
            "does_not_generate_trade_signals": True,
        },
        "notification_status": {
            "enabled": bool(SCAN_NOTIFY_ENABLED),
            "should_notify": False,
            "imessage_sent": False,
            "tts_spoken": False,
            "errors": [],
        },
        "screenshot_cleanup": _default_screenshot_cleanup_result(),
    }

    record["state"] = extract_structured_state(record)

    return record


# -------------------------
# Scan history lookup
# -------------------------
def load_latest_scan() -> dict | None:
    if not SCAN_HISTORY_PATH.exists():
        return None

    latest = None

    with SCAN_HISTORY_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if record.get("symbol") != SYMBOL:
                continue

            latest = record

    return latest


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
def run_scan(
    force: bool = False,
    update_runtime_status: bool = False,
    timeframe: str = SCAN_TIMEFRAME,
    multi_timeframe: bool = False,
) -> dict | None:
    now = datetime.now(TIMEZONE)
    sessions = get_active_sessions(now)
    timeframe = timeframe.upper()
    primary_timeframe = SCAN_TIMEFRAME if multi_timeframe else timeframe
    status_timeframe = scheduled_timeframe_label() if multi_timeframe else primary_timeframe

    if not force and not sessions:
        print(f"[{now.isoformat()}] Outside scan window. No scan ran.")
        return None

    session_label = " + ".join(sessions) if sessions else "Forced Scan"
    screenshot_cleanup = _default_screenshot_cleanup_result()

    print(f"[{now.isoformat()}] Running {SYMBOL} {status_timeframe} scan during: {session_label}")

    try:
        if update_runtime_status:
            write_scanner_runtime_status(
                scanner_enabled=True,
                timeframe=status_timeframe,
                running_scan=True,
            )

        screenshot_cleanup = cleanup_scan_screenshots()
        print("Screenshot cleanup mode:", screenshot_cleanup.get("mode"))
        print("Screenshot cleanup deleted:", screenshot_cleanup.get("deleted_count", 0))
        for error in screenshot_cleanup.get("errors", []):
            print("Screenshot cleanup error:", error)

        result = analyze_tradingview(
            symbol=SYMBOL,
            timeframe=primary_timeframe,
            prompt=f"Scheduled {SYMBOL} scan during {session_label}. Analyze with marked levels.",
        )

        if multi_timeframe:
            timeframe_captures = collect_scheduled_timeframe_captures(
                primary_timeframe=primary_timeframe,
                primary_result=result,
                session_label=session_label,
            )
        else:
            timeframe_captures = {}

        attach_news_risk(result, now)

        if multi_timeframe:
            attach_timeframe_screenshots_section(result, timeframe_captures)

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

        attach_liquidity_draw(record)
        attach_behavior_classification(record)
        attach_opportunity_watch(record)
        attach_alert_eligibility(record)
        deliver_scan_notification(record)
        record["screenshot_cleanup"] = screenshot_cleanup

        save_scan_record(record)

        if update_runtime_status:
            write_scanner_runtime_status(
                scanner_enabled=True,
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
            "symbol": SYMBOL,
            "timeframe": primary_timeframe,
            "timeframe_captures": {},
            "sessions": sessions if sessions else ["Forced Scan"],
            "session_label": session_label,
            "success": False,
            "error": str(e),
            "alert_eligibility": {
                "level": "none",
                "should_notify": False,
                "reasons": ["Scan failed before alert eligibility could be evaluated."],
                "blockers": [str(e)],
                "what_to_watch_next": ["Fix the scan failure, then rerun MES chart review."],
                "does_not_generate_trade_signals": True,
            },
            "notification_status": {
                "enabled": bool(SCAN_NOTIFY_ENABLED),
                "should_notify": False,
                "imessage_sent": False,
                "tts_spoken": False,
                "errors": [],
            },
            "screenshot_cleanup": screenshot_cleanup,
        }

        save_scan_record(error_record)

        if update_runtime_status:
            write_scanner_runtime_status(
                scanner_enabled=True,
                timeframe=status_timeframe,
                running_scan=False,
                last_scan_timestamp=error_record.get("timestamp"),
                latest_scan_success=False,
            )

        print("Scan failed:", e)
        return error_record


def run_loop(timeframe: str = SCAN_TIMEFRAME) -> None:
    timeframe = SCAN_TIMEFRAME

    print("Scheduled scanner started.")
    print(f"Symbol: {SYMBOL}")
    print(f"Timeframes: {scheduled_timeframe_label()}")
    print(f"Primary analysis timeframe: {timeframe}")
    print(f"Interval: {SCAN_INTERVAL_SECONDS // 60} minutes")
    print(f"History file: {SCAN_HISTORY_PATH}")
    print("Press CTRL+C to stop.")
    print()

    latest_scan = load_latest_scan()
    write_scanner_runtime_status(
        scanner_enabled=True,
        timeframe=scheduled_timeframe_label(),
        last_scan_timestamp=latest_scan.get("timestamp") if latest_scan else None,
        latest_scan_success=latest_scan.get("success") if latest_scan else None,
    )

    try:
        while True:
            run_scan(
                force=False,
                update_runtime_status=True,
                timeframe=timeframe,
                multi_timeframe=True,
            )
            latest_scan = load_latest_scan()
            write_scanner_runtime_status(
                scanner_enabled=True,
                timeframe=scheduled_timeframe_label(),
                last_scan_timestamp=latest_scan.get("timestamp") if latest_scan else None,
                latest_scan_success=latest_scan.get("success") if latest_scan else None,
            )
            time.sleep(SCAN_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("Scheduled scanner stopped.")
    finally:
        latest_scan = load_latest_scan()
        write_scanner_runtime_status(
            scanner_enabled=False,
            timeframe=scheduled_timeframe_label(),
            last_scan_timestamp=latest_scan.get("timestamp") if latest_scan else None,
            latest_scan_success=latest_scan.get("success") if latest_scan else None,
        )


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
    parser.add_argument(
        "--timeframe",
        default=SCAN_TIMEFRAME,
        help=(
            "TradingView timeframe for forced manual scans. "
            f"Scheduled scans always collect {scheduled_timeframe_label()} with {SCAN_TIMEFRAME} primary analysis."
        ),
    )

    args = parser.parse_args()

    if args.force:
        run_scan(force=True, timeframe=args.timeframe)
    elif args.once:
        run_scan(force=False, timeframe=SCAN_TIMEFRAME, multi_timeframe=True)
    else:
        run_loop()
