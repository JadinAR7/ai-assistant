from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any, Callable

import agent_service
import morning_checkin
import presence
import trading_strategy
from orbit import service as orbit_service


IntentHandler = Callable[[str], dict[str, Any]]


def route_chat_intent(message: str) -> dict[str, Any] | None:
    """Handle common Command Center requests before falling back to the LLM."""
    normalized = _normalize(message)
    if not normalized:
        return None

    if _is_morning_checkin_intent(normalized):
        return _morning_checkin_response()

    if _is_morning_briefing_intent(normalized):
        return _morning_briefing_response()

    if _is_schedule_intent(normalized):
        return _schedule_response()

    presence_mode = _presence_set_mode(normalized)
    if presence_mode:
        return _presence_set_response(presence_mode)

    if _is_presence_get_intent(normalized):
        return _presence_get_response()

    if _is_agent_priority_intent(normalized):
        return _agent_priority_response()

    if _is_major_event_intent(normalized):
        return _major_event_response(normalized)

    if _is_readiness_advisory_intent(normalized):
        return _readiness_advisory_response()

    if _is_readiness_status_intent(normalized):
        return _readiness_status_response()

    if _is_trading_strategy_intent(normalized):
        return _trading_strategy_response(normalized)

    return None


def _normalize(message: str) -> str:
    return re.sub(r"\s+", " ", message.casefold()).strip()


def _contains_any(message: str, phrases: list[str]) -> bool:
    return any(phrase in message for phrase in phrases)


def _is_morning_checkin_intent(message: str) -> bool:
    return _contains_any(
        message,
        [
            "good morning helix",
            "good morning",
            "start my day",
        ],
    )


def _is_morning_briefing_intent(message: str) -> bool:
    return _contains_any(
        message,
        [
            "morning briefing",
            "daily briefing",
            "what should i focus on today",
            "what should i work on today",
            "what is my priority today",
        ],
    )


def _is_schedule_intent(message: str) -> bool:
    return _contains_any(
        message,
        [
            "what does my schedule look like",
            "where do i have free time",
            "is my day packed",
            "is my schedule packed",
            "what should i schedule next",
            "show my schedule",
            "schedule look like",
            "free time",
            "day packed",
            "schedule packed",
            "schedule next",
        ],
    )


def _is_agent_priority_intent(message: str) -> bool:
    return _contains_any(
        message,
        [
            "which agent should run",
            "what should helix check next",
            "prioritize agents",
            "prioritise agents",
        ],
    )


def _presence_set_mode(message: str) -> str | None:
    exact_map = {
        "i'm home": "home",
        "im home": "home",
        "i am home": "home",
        "i'm trading": "trading",
        "im trading": "trading",
        "i am trading": "trading",
        "i'm away": "away",
        "im away": "away",
        "i am away": "away",
        "focus mode": "focus",
        "turn on focus mode": "focus",
    }
    if message in exact_map:
        return exact_map[message]

    if message in {"home mode", "trading mode", "away mode"}:
        return message.removesuffix(" mode")

    return None


def _is_presence_get_intent(message: str) -> bool:
    return _contains_any(
        message,
        [
            "what mode is helix in",
            "what is my presence mode",
        ],
    )


def _is_major_event_intent(message: str) -> bool:
    return _contains_any(
        message,
        [
            "show my major events",
            "major events",
            "corporate escape status",
            "how close am i to corporate escape",
        ],
    )


def _is_readiness_advisory_intent(message: str) -> bool:
    return _contains_any(message, ["readiness advisory", "run readiness"])


def _is_readiness_status_intent(message: str) -> bool:
    return _contains_any(
        message,
        [
            "how ready am i",
            "check readiness",
            "show readiness",
            "readiness status",
        ],
    )


def _is_trading_strategy_intent(message: str) -> bool:
    return _contains_any(
        message,
        [
            "what is my trading model",
            "explain my trading strategy",
            "what is liquidity narrative continuation",
            "what is scalp mode",
            "what is day trade mode",
            "what is daytrade mode",
        ],
    )


def _success_response(intent: str, message: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "success": True,
        "model": f"intent:{intent}",
        "message": message,
        "data": data or {},
    }


def _morning_checkin_response() -> dict[str, Any]:
    result = morning_checkin.check_in(source="manual", speak=False)
    summary = str(result.get("summary") or "").strip()
    message = summary or "Good morning. Morning check-in is acknowledged, but no summary was returned."
    return _success_response("morning_checkin", message, {"result": result})


def _morning_briefing_response() -> dict[str, Any]:
    briefing = orbit_service.generate_morning_briefing()
    message = str(briefing.get("briefing_text") or "").strip()
    if not message:
        message = "Morning briefing generated, but no briefing text was returned."
    return _success_response("morning_briefing", message, {"briefing": briefing})


def _schedule_response() -> dict[str, Any]:
    intelligence = orbit_service.get_schedule_intelligence()
    message = _format_schedule_intelligence_summary(intelligence)
    return _success_response("schedule", message, {"schedule_intelligence": intelligence})


def _agent_priority_response() -> dict[str, Any]:
    prioritization = agent_service.prioritize_agents()
    recommended_name = prioritization.get("recommended_agent_name") or "No enabled agent"
    score = prioritization.get("priority_score") or 0
    reason = prioritization.get("reason") or "No prioritization reason available."
    ranked = prioritization.get("ranked_agents") or []
    ranked_lines = [
        f"{index}. {agent.get('agent_name')} - P{agent.get('priority_score')}: "
        f"{_first_reason(agent)}"
        for index, agent in enumerate(ranked[:3], start=1)
    ]
    message = (
        "Agent Priority\n\n"
        f"Recommended: {recommended_name} (P{score}).\n"
        f"Why: {reason}"
    )
    if ranked_lines:
        message += "\n\nTop agents:\n" + "\n".join(ranked_lines)
    return _success_response("agents_prioritize", message, {"prioritization": prioritization})


def _presence_set_response(mode: str) -> dict[str, Any]:
    current = presence.set_presence(mode)
    message = _format_presence_summary(current, prefix="Presence mode set")
    return _success_response("presence_set", message, {"presence": current})


def _presence_get_response() -> dict[str, Any]:
    current = presence.get_presence()
    message = _format_presence_summary(current, prefix="Current presence mode")
    return _success_response("presence_get", message, {"presence": current})


def _format_presence_summary(current: dict[str, Any], prefix: str) -> str:
    label = current.get("label") or str(current.get("mode") or "home").title()
    mode = current.get("mode") or "home"
    scanner_min = current.get("scanner_min_signal_level") or "review"
    notifications = "on" if current.get("notifications_allowed") else "off"
    imessage = "on" if current.get("imessage_allowed") else "off"
    tts = "on" if current.get("tts_allowed") else "off"
    noise = current.get("scan_noise_profile") or "normal"

    return (
        f"{prefix}: {label} ({mode}).\n\n"
        f"Scanner notifications require {scanner_min} signal or stronger. "
        f"Notifications: {notifications}. iMessage: {imessage}. TTS: {tts}. "
        f"Noise profile: {noise}."
    )


def _major_event_response(message_text: str) -> dict[str, Any]:
    events = orbit_service.list_major_events()
    active_events = [
        event
        for event in events
        if str(event.get("status") or "").casefold() == "active"
    ]
    selected = _select_major_event(events, active_events, message_text)

    if not events:
        message = "No major events are saved in Orbit yet."
    elif selected is not None and "corporate escape" in message_text:
        message = _format_single_major_event(selected, heading="Corporate Escape Status")
    elif selected is not None and "show my major events" not in message_text and "major events" not in message_text:
        message = _format_single_major_event(selected, heading="Major Event Status")
    else:
        message = _format_major_events(events, selected)

    return _success_response(
        "major_events",
        message,
        {"major_events": events, "selected_major_event": selected},
    )


def _readiness_status_response() -> dict[str, Any]:
    categories = orbit_service.get_readiness_categories()
    events = orbit_service.list_major_events()
    message = _format_readiness_status(categories, events)
    return _success_response(
        "readiness_status",
        message,
        {"readiness_categories": categories},
    )


def _readiness_advisory_response() -> dict[str, Any]:
    agent = _find_agent_by_type("readiness_advisory")
    if agent is None:
        return _success_response(
            "readiness_advisory",
            "Readiness Advisory Agent is not available or is disabled.",
        )

    run = agent_service.run_agent(int(agent["id"]))
    summary = str(run.get("summary") or "").strip()
    message = summary or "Readiness Advisory Agent ran, but no summary was returned."
    return _success_response("readiness_advisory", message, {"agent_run": run})


def _trading_strategy_response(message_text: str) -> dict[str, Any]:
    profile = trading_strategy.get_strategy_profile()
    modes = trading_strategy.get_strategy_modes()
    message = trading_strategy.format_strategy_profile_summary(message_text)
    return _success_response(
        "trading_strategy",
        message,
        {"strategy_profile": profile, "strategy_modes": modes},
    )


def _format_schedule_summary(blocks: list[dict[str, Any]]) -> str:
    if not blocks:
        return (
            "Schedule\n\n"
            "No active schedule blocks are saved in Orbit yet.\n\n"
            "TODO: When schedule intelligence lands, Helix can summarize free-time windows and day density."
        )

    fixed_blocks = [
        block
        for block in blocks
        if str(block.get("block_type") or "").casefold() == "fixed"
    ]
    flexible_blocks = [
        block
        for block in blocks
        if str(block.get("block_type") or "").casefold() == "flexible"
    ]
    today_blocks = _blocks_for_today(fixed_blocks)
    fixed_lines = [
        f"- {_format_block_title(block)}: {_format_block_time(block)}"
        for block in (today_blocks or fixed_blocks[:6])
    ]
    flexible_lines = [
        f"- {_format_block_title(block)}: {_format_duration(block.get('duration_minutes'))}"
        for block in flexible_blocks[:5]
    ]

    message = (
        "Schedule\n\n"
        f"Orbit has {len(blocks)} active schedule block{'s' if len(blocks) != 1 else ''}: "
        f"{len(fixed_blocks)} fixed and {len(flexible_blocks)} flexible."
    )
    if fixed_lines:
        heading = "Today fixed blocks" if today_blocks else "Fixed blocks"
        message += f"\n\n{heading}:\n" + "\n".join(fixed_lines)
    if flexible_lines:
        message += "\n\nFlexible blocks:\n" + "\n".join(flexible_lines)
    message += (
        "\n\nTODO: When schedule intelligence lands, Helix can summarize free-time windows and day density."
    )
    return message


def _format_schedule_intelligence_summary(intelligence: dict[str, Any]) -> str:
    day_summaries = intelligence.get("day_summaries") or []
    if not day_summaries:
        return "Schedule Intelligence\n\nNo schedule data is available yet."

    most_available = intelligence.get("most_available_day") or {}
    most_overloaded = intelligence.get("most_overloaded_day") or {}
    overloaded_days = intelligence.get("overloaded_days") or []
    windows = sorted(
        intelligence.get("available_windows") or [],
        key=lambda window: int(window.get("duration_minutes") or 0),
        reverse=True,
    )
    recommendations = intelligence.get("recommendations") or []

    message = (
        "Schedule Intelligence\n\n"
        f"Most available: {_format_schedule_day_summary(most_available)}.\n"
        f"Most loaded: {_format_schedule_day_summary(most_overloaded)}.\n"
        f"Unplaced flexible blocks: {intelligence.get('unplaced_flexible_blocks') or 0}."
    )

    if overloaded_days:
        message += (
            "\n\nOverloaded days:\n"
            + "\n".join(
                f"- {_day_label(day.get('day'))}: {_format_duration(day.get('total_scheduled_minutes'))} scheduled"
                for day in overloaded_days[:3]
            )
        )
    else:
        message += "\n\nNo overloaded days detected this week."

    if windows:
        message += (
            "\n\nBest available windows:\n"
            + "\n".join(
                f"- {_day_label(window.get('day'))} {window.get('start_time')}-{window.get('end_time')}: "
                f"{_format_duration(window.get('duration_minutes'))}"
                for window in windows[:3]
            )
        )

    if recommendations:
        message += "\n\nRecommendations:\n" + "\n".join(
            f"- {recommendation}" for recommendation in recommendations[:3]
        )

    return message


def _format_schedule_day_summary(day: dict[str, Any]) -> str:
    if not day:
        return "Unavailable"
    return (
        f"{_day_label(day.get('day'))} "
        f"({_format_duration(day.get('remaining_available_minutes'))} open, "
        f"{day.get('status')})"
    )


def _blocks_for_today(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    today = date.today()
    weekday = today.strftime("%A").casefold()
    today_iso = today.isoformat()
    return [
        block
        for block in blocks
        if str(block.get("day_of_week") or "").casefold() == weekday
        or str(block.get("specific_date") or "") == today_iso
    ]


def _format_block_title(block: dict[str, Any]) -> str:
    return str(block.get("title") or block.get("category") or "Schedule block")


def _format_block_time(block: dict[str, Any]) -> str:
    day = str(block.get("specific_date") or block.get("day_of_week") or "unscheduled")
    start = block.get("start_time") or "?"
    end = block.get("end_time") or "?"
    return f"{day} {start}-{end}"


def _format_duration(duration: Any) -> str:
    try:
        minutes = int(duration)
    except (TypeError, ValueError):
        return "duration not set"
    hours = minutes // 60
    remainder = minutes % 60
    if hours and remainder:
        return f"{hours}h {remainder}m"
    if hours:
        return f"{hours}h"
    return f"{minutes}m"


def _day_label(value: Any) -> str:
    text = str(value or "")
    return text[:1].upper() + text[1:]


def _format_major_events(events: list[dict[str, Any]], selected: dict[str, Any] | None) -> str:
    active_count = sum(1 for event in events if str(event.get("status") or "").casefold() == "active")
    lines = [
        f"- {event.get('title')}: {_event_progress(event)}%, {event.get('status')}"
        + _target_date_text(event)
        for event in events[:6]
    ]
    message = (
        "Major Events\n\n"
        f"{len(events)} major event{'s' if len(events) != 1 else ''} saved; {active_count} active.\n"
        + "\n".join(lines)
    )
    if selected:
        message += f"\n\nSelected active event: {selected.get('title')} at {_event_progress(selected)}%."
    return message


def _format_single_major_event(event: dict[str, Any], heading: str) -> str:
    target = event.get("target_date")
    target_text = f" Target date: {target}." if target else " No target date is set."
    return (
        f"{heading}\n\n"
        f"{event.get('title')} is {_event_progress(event)}% complete "
        f"and currently {event.get('status')}.{target_text}"
    )


def _select_major_event(
    events: list[dict[str, Any]],
    active_events: list[dict[str, Any]],
    message_text: str,
) -> dict[str, Any] | None:
    if "corporate escape" in message_text:
        for event in events:
            if str(event.get("title") or "").casefold() == "corporate escape":
                return event
    if active_events:
        return active_events[0]
    return events[0] if events else None


def _event_progress(event: dict[str, Any]) -> Any:
    return event.get("calculated_progress_percent", event.get("progress_percent", 0))


def _target_date_text(event: dict[str, Any]) -> str:
    target = event.get("target_date")
    if not target:
        return ""
    days = _days_until(str(target))
    if days is None:
        return f", target {target}"
    if days >= 0:
        return f", target {target} ({days} days out)"
    return f", target {target} ({abs(days)} days ago)"


def _format_readiness_status(
    categories: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> str:
    if not categories:
        return "Readiness\n\nNo readiness categories are saved in Orbit yet."

    event_names = {event.get("id"): event.get("title") for event in events}
    overall = round(
        sum(int(category.get("current_score") or 0) for category in categories)
        / len(categories)
    )
    low_categories = sorted(
        categories,
        key=lambda category: int(category.get("current_score") or 0),
    )[:4]
    lines = [
        f"- {category.get('category_name')}: {category.get('current_score')}%"
        + (
            f" / target {category.get('target_score')}%"
            if category.get("target_score") is not None
            else ""
        )
        + (
            f" ({event_names.get(category.get('major_event_id'))})"
            if event_names.get(category.get("major_event_id"))
            else ""
        )
        for category in low_categories
    ]
    return (
        "Readiness\n\n"
        f"Overall readiness is {overall}% across {len(categories)} categor"
        f"{'y' if len(categories) == 1 else 'ies'}.\n\n"
        "Lowest categories:\n"
        + "\n".join(lines)
    )


def _find_agent_by_type(agent_type: str) -> dict[str, Any] | None:
    for agent in agent_service.list_agents():
        if agent.get("agent_type") == agent_type and agent.get("enabled"):
            return agent
    return None


def _first_reason(agent: dict[str, Any]) -> str:
    reasons = agent.get("reasons") or []
    return str(reasons[0]) if reasons else "No reason provided."


def _days_until(value: str) -> int | None:
    try:
        target = datetime.fromisoformat(value).date()
    except ValueError:
        return None
    return (target - date.today()).days


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.casefold() not in {"", "0", "false", "no"}
    return bool(value)
