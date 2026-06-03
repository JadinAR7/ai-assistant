from __future__ import annotations

import re
from datetime import datetime
from typing import Any


STRATEGY_PROFILE_NAME = "Liquidity Narrative Continuation"
SCALP_MODE = "Scalp"
DAY_TRADE_MODE = "Day Trade"
HYBRID_REVIEW_MODE = "Hybrid / Review"

MAJOR_LIQUIDITY_TERMS = [
    "pdh",
    "previous day high",
    "pdl",
    "previous day low",
    "pdnyh",
    "pdnyl",
    "asia high",
    "asia low",
    "london high",
    "london low",
    "weekly high",
    "weekly low",
    "previous week high",
    "previous week low",
    "pwh",
    "pwl",
]

SCALP_TERMS = [
    "quick scalp",
    "scalp",
    "immediate liquidity",
    "rebuild",
    "small target",
    "small controlled target",
]


def get_strategy_profile() -> dict[str, Any]:
    return {
        "name": STRATEGY_PROFILE_NAME,
        "core_thesis": (
            "Price seeks liquidity. FVGs are not automatic entries. They are "
            "reaction zones where price reveals whether it intends to continue "
            "toward or away from liquidity."
        ),
        "primary_question": "Where is price trying to go?",
        "framework": [
            {
                "step": "Determine HTF bias",
                "items": ["Daily", "4H", "1H"],
            },
            {
                "step": "Identify draw on liquidity",
                "items": [
                    "PDH",
                    "PDL",
                    "PDNYH",
                    "PDNYL",
                    "Asia High",
                    "Asia Low",
                    "London High",
                    "London Low",
                    "Previous Week High",
                    "Previous Week Low",
                ],
            },
            {
                "step": "Mark HTF reaction zones",
                "items": ["Daily FVG", "4H FVG", "1H FVG", "15M FVG"],
            },
            {
                "step": "Evaluate behavior inside the zone",
                "items": [
                    "Acceptance",
                    "Rejection",
                    "Sweep",
                    "Reclaim",
                    "Displacement",
                    "Consolidation",
                ],
            },
            {
                "step": "Confirm structure",
                "items": ["15M MSS/BOS", "5M MSS/BOS"],
            },
            {
                "step": "Execute",
                "items": [
                    "1M BRTC",
                    "1M FVG retest",
                    "Sweep + reclaim",
                    "MSS after displacement",
                ],
            },
            {
                "step": "Target liquidity",
                "items": [
                    "Nearest liquidity",
                    "Session liquidity",
                    "PDH/PDL",
                    "Weekly liquidity",
                    "Fixed RR only when liquidity is unclear or too far",
                ],
            },
        ],
    }


def get_strategy_modes() -> dict[str, dict[str, Any]]:
    return {
        SCALP_MODE: {
            "name": SCALP_MODE,
            "hold_time": "Usually 1-5 minutes",
            "description": (
                "Short hold time, uses HTF context but targets immediate liquidity, "
                "and allows more aggressive execution."
            ),
            "best_for": (
                "Funded-account rebuilds or small controlled targets where the "
                "objective is nearby liquidity."
            ),
        },
        DAY_TRADE_MODE: {
            "name": DAY_TRADE_MODE,
            "hold_time": "Usually 15-90+ minutes",
            "description": (
                "Longer hold time where the HTF narrative drives the trade, larger "
                "liquidity pools are the target, and execution is more selective."
            ),
            "best_for": "Trades where the draw on liquidity is larger and the narrative has room to develop.",
        },
    }


def classify_trade_mode_from_journal_entry(entry: dict[str, Any]) -> str:
    text = _journal_text(entry)
    if _contains_any(text, MAJOR_LIQUIDITY_TERMS):
        return DAY_TRADE_MODE
    if _contains_any(text, SCALP_TERMS):
        return SCALP_MODE

    duration_minutes = _duration_minutes(entry)
    if duration_minutes is None:
        return HYBRID_REVIEW_MODE
    if duration_minutes <= 5:
        return SCALP_MODE
    if duration_minutes >= 15:
        return DAY_TRADE_MODE
    return HYBRID_REVIEW_MODE


def format_strategy_profile_summary(topic: str | None = None) -> str:
    profile = get_strategy_profile()
    modes = get_strategy_modes()
    normalized_topic = str(topic or "").casefold()

    if "scalp" in normalized_topic:
        mode = modes[SCALP_MODE]
        return (
            "Scalp Mode\n\n"
            f"Model: {profile['name']}.\n"
            f"Hold time: {mode['hold_time']}.\n"
            f"Use: {mode['description']}\n"
            f"Best for: {mode['best_for']}"
        )

    if "day trade" in normalized_topic or "daytrade" in normalized_topic:
        mode = modes[DAY_TRADE_MODE]
        return (
            "Day Trade Mode\n\n"
            f"Model: {profile['name']}.\n"
            f"Hold time: {mode['hold_time']}.\n"
            f"Use: {mode['description']}\n"
            f"Best for: {mode['best_for']}"
        )

    framework_lines = [
        f"{index}. {section['step']}: {', '.join(section['items'])}"
        for index, section in enumerate(profile["framework"], start=1)
    ]
    return (
        f"{profile['name']}\n\n"
        f"Core thesis: {profile['core_thesis']}\n\n"
        f"Primary question: {profile['primary_question']}\n\n"
        "Framework:\n"
        + "\n".join(framework_lines)
        + "\n\nModes: Scalp for immediate-liquidity, short-duration execution; "
        "Day Trade for larger liquidity pools where the HTF narrative drives the trade."
    )


def _journal_text(entry: dict[str, Any]) -> str:
    values: list[str] = []
    for key in (
        "target",
        "liquidity_target",
        "narrative",
        "why_taken",
        "price_intent",
        "notes",
        "went_well",
        "went_wrong",
        "lesson_learned",
    ):
        value = entry.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value is not None:
            values.append(str(value))

    for key in ("draw_on_liquidity", "behavior_tags", "execution_tags"):
        value = entry.get(key)
        if isinstance(value, list):
            values.extend(str(item) for item in value)
        elif value is not None:
            values.append(str(value))

    return " ".join(values).casefold()


def _contains_any(value: str, terms: list[str]) -> bool:
    return any(term in value for term in terms)


def _duration_minutes(entry: dict[str, Any]) -> float | None:
    for key in ("duration_minutes", "hold_minutes", "trade_duration_minutes"):
        value = entry.get(key)
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, str) and value.strip():
            try:
                return float(value)
            except ValueError:
                pass

    for key in ("duration", "hold_time", "trade_duration"):
        parsed = _parse_duration_text(entry.get(key))
        if parsed is not None:
            return parsed

    return _duration_from_timestamps(entry.get("entry_time"), entry.get("exit_time"))


def _parse_duration_text(value: Any) -> float | None:
    if value is None:
        return None

    text = str(value).strip().casefold()
    if not text:
        return None

    hhmmss = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{2})", text)
    if hhmmss:
        hours = int(hhmmss.group(1) or 0)
        minutes = int(hhmmss.group(2))
        seconds = int(hhmmss.group(3))
        return hours * 60 + minutes + seconds / 60

    minutes = 0.0
    matched = False
    for amount, unit in re.findall(r"(\d+(?:\.\d+)?)\s*(hours?|hrs?|h|minutes?|mins?|m|seconds?|secs?|s)\b", text):
        matched = True
        number = float(amount)
        if unit.startswith(("hour", "hr", "h")):
            minutes += number * 60
        elif unit.startswith(("second", "sec", "s")):
            minutes += number / 60
        else:
            minutes += number

    if matched:
        return minutes

    try:
        return float(text)
    except ValueError:
        return None


def _duration_from_timestamps(entry_time: Any, exit_time: Any) -> float | None:
    if not entry_time or not exit_time:
        return None

    start = _parse_datetime(entry_time)
    end = _parse_datetime(exit_time)
    if start is None or end is None:
        return None

    minutes = (end - start).total_seconds() / 60
    return minutes if minutes >= 0 else None


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value).strip()
    if not text:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None
