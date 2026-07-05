from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any, Callable

try:
    import agent_service
    import morning_checkin
    import pattern_discovery
    import presence
    import trading_coach
    import trading_correlation
    import trading_strategy
    from orbit.models import InboxTaskCreate, MobileReminderCreate, ScheduleBlockCreate
    from orbit import service as orbit_service
except ImportError:
    from . import agent_service
    from . import morning_checkin
    from . import pattern_discovery
    from . import presence
    from . import trading_coach
    from . import trading_correlation
    from . import trading_strategy
    from .orbit.models import InboxTaskCreate, MobileReminderCreate, ScheduleBlockCreate
    from .orbit import service as orbit_service


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

    reminder_action = _parse_reminder_action(normalized)
    if reminder_action is not None:
        return _reminder_action_response(reminder_action)

    day_plan = _parse_multi_task_day_plan(normalized)
    if day_plan is not None:
        return _multi_task_day_plan_response(day_plan)

    schedule_action = _parse_schedule_action(normalized)
    if schedule_action is not None:
        return _schedule_action_response(schedule_action)

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

    if _is_trading_correlation_intent(normalized):
        return _trading_correlation_response()

    if _is_pattern_discovery_intent(normalized):
        return _pattern_discovery_response()

    if _is_trading_coach_intent(normalized):
        return _trading_coach_response(normalized)

    if _is_trading_strategy_intent(normalized):
        return _trading_strategy_response(normalized)

    return None


def _normalize(message: str) -> str:
    normalized = message.casefold().replace("’", "'").replace("‘", "'")
    return re.sub(r"\s+", " ", normalized).strip()


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


_SCHEDULE_ACTION_VERBS = {"add", "schedule", "block", "put", "create"}
_SCHEDULE_CONTEXT_WORDS = {"schedule", "calendar", "time", "block", "free"}
_SCHEDULE_STOP_WORDS = {
    "my",
    "the",
    "a",
    "an",
    "to",
    "on",
    "in",
    "for",
    "of",
    "please",
    "can",
    "could",
    "you",
    "would",
    "this",
}
_SCHEDULE_DAYS = {
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
}
_SCHEDULE_TIME_PREFERENCES = {
    "morning": "morning",
    "afternoon": "afternoon",
    "evening": "evening",
    "night": "night",
}
_DURATION_PATTERN = re.compile(
    r"\b(?P<amount>\d+(?:\.\d+)?)\s*(?P<unit>minutes?|mins?|min|m|hours?|hrs?|hr|h)\b"
)
_REMINDER_PREFIX_PATTERN = re.compile(
    r"^(?:please\s+)?(?:can|could|would)?\s*(?:you\s+)?"
    r"(?:(?:set|create|add)\s+(?:a\s+)?reminder\s+(?:for\s+me\s+)?(?:to\s+)?|"
    r"remind\s+me\s+(?:to\s+)?)"
)
_REMINDER_RELATIVE_PATTERN = re.compile(
    r"\bin\s+(?P<amount>\d+)\s*(?P<unit>minutes?|mins?|min|hours?|hrs?|hr)\b"
)
_REMINDER_EXACT_TIME_PATTERN = re.compile(
    r"\bat\s+(?P<hour>\d{1,2})(?::(?P<minute>\d{2}))?\s*(?P<period>a\.?m\.?|p\.?m\.?|am|pm)?\b"
)
_REMINDER_DAYPART_HOURS = {
    "morning": 8,
    "afternoon": 15,
    "evening": 19,
    "tonight": 19,
}
_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_DAY_PLAN_TRIGGERS = [
    "things done today",
    "get these done today",
    "schedule these today",
    "need to do today",
    "do today",
    "done today",
]
_DAY_PLAN_ITEM_PATTERN = re.compile(
    r"(?:^|\s)(?:[-*•]|\d+[\.\)])\s+"
    r"(?P<item>.*?)(?=\s+(?:[-*•]|\d+[\.\)])\s+|$)"
)
_SPLIT_SESSION_PATTERN = re.compile(
    r"\b(?P<sessions>\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+"
    r"(?P<duration>\d+)\s*[- ]?min(?:ute)?s?\s+sessions?\b"
)
_DURATION_PHRASES = [
    re.compile(r"\bfor\s+an?\s+hour\b"),
    re.compile(r"\bfor\s+(?P<amount>\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+hours?\b"),
    re.compile(r"\bfor\s+(?P<amount>\d+)\s*(?:minutes?|mins?|min)\b"),
]


def _parse_reminder_action(message: str) -> dict[str, Any] | None:
    if not _REMINDER_PREFIX_PATTERN.search(message):
        return None

    due_at = _parse_reminder_due_at(message)
    title = _extract_reminder_title(message)

    return {
        "title": title,
        "due_at": due_at,
        "message": message,
    }


def _parse_reminder_due_at(message: str) -> datetime | None:
    now = datetime.now(orbit_service.ORBIT_LOCAL_TIMEZONE)

    relative_match = _REMINDER_RELATIVE_PATTERN.search(message)
    if relative_match:
        amount = int(relative_match.group("amount"))
        unit = relative_match.group("unit")
        return now + (
            timedelta(hours=amount)
            if unit.startswith(("h", "hr", "hour"))
            else timedelta(minutes=amount)
        )

    for daypart, hour in _REMINDER_DAYPART_HOURS.items():
        if re.search(rf"\b{daypart}\b", message):
            base = now + timedelta(days=1) if "tomorrow" in message else now
            due = base.replace(hour=hour, minute=0, second=0, microsecond=0)
            if due <= now:
                due += timedelta(days=1)
            return due

    exact_match = _REMINDER_EXACT_TIME_PATTERN.search(message)
    if exact_match:
        hour = int(exact_match.group("hour"))
        minute = int(exact_match.group("minute") or "0")
        period = (exact_match.group("period") or "").replace(".", "")
        if period == "pm" and hour < 12:
            hour += 12
        elif period == "am" and hour == 12:
            hour = 0
        elif not period and 1 <= hour <= 11:
            morning_due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            evening_due = now.replace(
                hour=hour + 12,
                minute=minute,
                second=0,
                microsecond=0,
            )
            if morning_due > now:
                return morning_due
            if evening_due > now:
                return evening_due
            return morning_due + timedelta(days=1)

        if hour > 23 or minute > 59:
            return None

        due = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if "tomorrow" in message or due <= now:
            due += timedelta(days=1)
        return due

    return None


def _extract_reminder_title(message: str) -> str:
    title = _REMINDER_PREFIX_PATTERN.sub("", message).strip()
    title = _REMINDER_RELATIVE_PATTERN.sub("", title)
    title = _REMINDER_EXACT_TIME_PATTERN.sub("", title)
    title = re.sub(
        r"\b(?:tomorrow|today|tonight|this\s+)?(?:morning|afternoon|evening)\b",
        "",
        title,
    )
    title = re.sub(r"\s+", " ", title).strip(" .,:;-")
    return title or "Reminder"


def _parse_multi_task_day_plan(message: str) -> dict[str, Any] | None:
    has_today_plan_trigger = _contains_any(message, _DAY_PLAN_TRIGGERS)
    raw_items = [
        match.group("item").strip(" ;,.")
        for match in _DAY_PLAN_ITEM_PATTERN.finditer(message)
    ]
    items = [_parse_day_plan_item(item) for item in raw_items if item]
    items = [item for item in items if item.get("title")]

    if len(items) < 2:
        return None

    duration_count = sum(1 for item in items if item.get("duration_minutes"))
    if not has_today_plan_trigger and duration_count < 2:
        return None

    return {
        "items": items,
        "today": "today" in message,
        "raw_message": message,
    }


def _parse_day_plan_item(text: str) -> dict[str, Any]:
    split = _parse_split_sessions(text)
    duration_minutes = _parse_day_plan_duration(text)
    priority = "highest" if "highest priority" in text else "normal"
    if priority == "normal" and "high priority" in text:
        priority = "high"

    title = _clean_day_plan_title(text)
    return {
        "title": title,
        "duration_minutes": duration_minutes,
        "split": split,
        "priority": priority,
        "raw_text": text,
    }


def _parse_split_sessions(text: str) -> dict[str, int] | None:
    match = _SPLIT_SESSION_PATTERN.search(text)
    if not match:
        return None

    sessions = _parse_small_number(match.group("sessions"))
    duration = int(match.group("duration"))
    if sessions is None or sessions < 1 or duration < 1:
        return None
    return {"sessions": sessions, "duration_minutes": duration}


def _parse_day_plan_duration(text: str) -> int | None:
    split = _parse_split_sessions(text)
    if split:
        return split["sessions"] * split["duration_minutes"]

    if re.search(r"\bfor\s+an?\s+hour\b", text):
        return 60

    hour_match = re.search(
        r"\bfor\s+(?P<amount>\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+hours?\b",
        text,
    )
    if hour_match:
        amount = _parse_small_number(hour_match.group("amount"))
        return amount * 60 if amount is not None else None

    minute_match = re.search(r"\bfor\s+(?P<amount>\d+)\s*(?:minutes?|mins?|min)\b", text)
    if minute_match:
        return int(minute_match.group("amount"))

    return None


def _parse_small_number(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    return _NUMBER_WORDS.get(value)


def _clean_day_plan_title(text: str) -> str:
    title = text
    for pattern in _DURATION_PHRASES:
        title = pattern.sub("", title)
    title = _SPLIT_SESSION_PATTERN.sub("", title)
    title = re.sub(r"\b(?:highest|high)\s+priority\b", "", title)
    title = re.sub(
        r"\bmy\s+(?=japanese|trading strategy|trades?|schedule|tasks?)",
        "",
        title,
    )
    title = re.sub(r"\s+", " ", title)
    title = title.strip(" ;,.-")
    if not title:
        return ""
    title = title[0].upper() + title[1:]
    return re.sub(r"\bjapanese\b", "Japanese", title, flags=re.IGNORECASE)


def _parse_schedule_action(message: str) -> dict[str, Any] | None:
    words = set(re.findall(r"[a-z0-9']+", message))
    has_action_verb = bool(words & _SCHEDULE_ACTION_VERBS)
    duration_match = _DURATION_PATTERN.search(message)
    has_schedule_context = bool(words & _SCHEDULE_CONTEXT_WORDS)
    has_day_or_time_hint = bool(words & _SCHEDULE_DAYS) or bool(words & set(_SCHEDULE_TIME_PREFERENCES))

    if not has_action_verb:
        return None

    looks_schedulable = has_schedule_context or duration_match is not None or has_day_or_time_hint
    if not looks_schedulable:
        return None

    duration_minutes = _parse_schedule_duration(duration_match)
    activity = _extract_schedule_activity(message, duration_match)
    preferred_days = [day for day in _SCHEDULE_DAYS if day in words]
    time_preference = next(
        (
            preference
            for word, preference in _SCHEDULE_TIME_PREFERENCES.items()
            if word in words
        ),
        "anytime",
    )

    return {
        "duration_minutes": duration_minutes,
        "activity": activity,
        "preferred_days": sorted(
            preferred_days,
            key=[
                "monday",
                "tuesday",
                "wednesday",
                "thursday",
                "friday",
                "saturday",
                "sunday",
            ].index,
        ),
        "time_preference": time_preference,
    }


def _parse_schedule_duration(match: re.Match[str] | None) -> int | None:
    if match is None:
        return None
    amount = float(match.group("amount"))
    unit = match.group("unit")
    minutes = amount * 60 if unit.startswith(("h", "hour")) else amount
    return int(minutes) if minutes.is_integer() else round(minutes)


def _extract_schedule_activity(message: str, duration_match: re.Match[str] | None) -> str | None:
    activity_text = ""
    if duration_match is not None:
        activity_text = message[duration_match.end() :].strip()
        activity_text = re.sub(r"^(?:of|for|to)\s+", "", activity_text)
    else:
        activity_text = re.sub(
            r"^(?:can|could|would)?\s*(?:you\s+)?(?:please\s+)?(?:add|schedule|block|put|create)\s+",
            "",
            message,
        )

    activity_text = re.split(
        r"\b(?:to|on|in)\s+my\s+(?:schedule|calendar)\b|"
        r"\b(?:whenever|when)\s+i(?:'| a)?m\s+free\b|"
        r"\b(?:tomorrow|today|tonight|morning|afternoon|evening|night|monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        activity_text,
        maxsplit=1,
    )[0]
    activity_text = re.sub(r"^(?:of|for|to)\s+", "", activity_text)
    activity_text = re.sub(r"\b(?:schedule|calendar|time|block)\b", "", activity_text)
    activity_text = re.sub(r"[^a-z0-9' ]+", " ", activity_text)
    activity_text = re.sub(r"\s+", " ", activity_text).strip()

    words = [word for word in activity_text.split() if word not in _SCHEDULE_STOP_WORDS]
    if not words:
        return None

    activity = " ".join(words)
    if activity == "read":
        activity = "reading"
    return activity


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


def _is_trading_coach_intent(message: str) -> bool:
    return _contains_any(
        message,
        [
            "review my trades",
            "how did i trade today",
            "what did i do well trading",
            "what should i improve in my trading",
            "review my trade journal",
            "trading coach review",
        ],
    )


def _is_trading_correlation_intent(message: str) -> bool:
    return _contains_any(
        message,
        [
            "compare my trades to the scanner",
            "did my trades align with helix",
            "scanner journal review",
            "trade scanner correlation",
            "did i follow the scanner narrative",
        ],
    )


def _is_pattern_discovery_intent(message: str) -> bool:
    return _contains_any(
        message,
        [
            "find patterns in my trades",
            "what patterns do you see",
            "what trading patterns are showing up",
            "where am i doing best",
            "where am i struggling",
            "pattern discovery",
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


def _reminder_action_response(action: dict[str, Any]) -> dict[str, Any]:
    due_at = action.get("due_at")
    if due_at is None:
        return _success_response(
            "reminder_clarify",
            "What time should I remind you?",
            {"missing": "time", "reminder_action": action},
        )

    title = str(action.get("title") or "Reminder").strip()
    payload = MobileReminderCreate(
        title=title,
        body=None,
        due_at=due_at,
        source="chat",
    )

    try:
        reminder = orbit_service.create_mobile_reminder(payload)
    except Exception as exc:
        return _success_response(
            "reminder_error",
            f"Couldn't create that reminder because {exc}.",
            {"error": str(exc), "reminder_action": action},
        )

    message = f"Reminder set for {_format_reminder_due_at(due_at)}: {title}."
    return _success_response(
        "reminder_create",
        message,
        {"reminder": reminder},
    )


def _multi_task_day_plan_response(plan: dict[str, Any]) -> dict[str, Any]:
    items = plan.get("items") or []
    today = datetime.now(orbit_service.ORBIT_LOCAL_TIMEZONE).date()
    created_tasks = []
    created_blocks = []
    missing_duration_items = []

    try:
        for item in items:
            title = str(item.get("title") or "").strip()
            if not title:
                continue

            duration = item.get("duration_minutes")
            priority = str(item.get("priority") or "normal")
            description_parts = ["Captured from mobile day planning."]
            if duration:
                description_parts.append(f"Duration: {duration} minutes.")
            if priority in {"high", "highest"}:
                description_parts.append(f"Priority: {priority}.")

            task = orbit_service.create_inbox_task(
                InboxTaskCreate(
                    title=title,
                    description=" ".join(description_parts),
                    status="queued",
                    due_date=today,
                )
            )
            created_tasks.append(task)

            if not duration:
                missing_duration_items.append(item)
                continue

            for block_title, block_duration in _day_plan_schedule_blocks_for_item(item):
                block = orbit_service.create_schedule_block(
                    ScheduleBlockCreate(
                        title=block_title,
                        block_type="flexible",
                        category=_day_plan_schedule_category(title),
                        specific_date=today,
                        duration_minutes=block_duration,
                        recurrence="once",
                        time_preference="anytime",
                        flexible_placement_mode="preferred_day",
                        priority="high" if priority in {"high", "highest"} else "medium",
                        notes="Created from mobile day planning chat intent.",
                        active=True,
                    )
                )
                created_blocks.append(block)
    except Exception as exc:
        return _success_response(
            "day_plan_error",
            f"Couldn't create that day plan because {exc}.",
            {"error": str(exc), "day_plan": plan},
        )

    message = _format_day_plan_response(created_blocks, missing_duration_items)
    return _success_response(
        "day_plan_create",
        message,
        {
            "items": items,
            "created_tasks": created_tasks,
            "created_schedule_blocks": created_blocks,
            "missing_duration_items": missing_duration_items,
        },
    )


def _day_plan_schedule_blocks_for_item(item: dict[str, Any]) -> list[tuple[str, int]]:
    title = str(item.get("title") or "").strip()
    split = item.get("split")
    if isinstance(split, dict):
        sessions = int(split.get("sessions") or 0)
        duration = int(split.get("duration_minutes") or 0)
        if sessions > 1 and duration > 0:
            return [
                (f"{title} Session {index}", duration)
                for index in range(1, sessions + 1)
            ]

    duration_minutes = int(item.get("duration_minutes") or 0)
    return [(title, duration_minutes)] if duration_minutes > 0 else []


def _day_plan_schedule_category(title: str) -> str:
    text = title.casefold()
    if "family" in text:
        return "family"
    if "read" in text or "japanese" in text:
        return "reading"
    if "trade" in text or "backtest" in text:
        return "trading"
    if "workout" in text or "exercise" in text:
        return "personal"
    return "personal"


def _format_day_plan_response(
    created_blocks: list[dict[str, Any]],
    missing_duration_items: list[dict[str, Any]],
) -> str:
    lines = []
    if created_blocks:
        lines.append("I created today schedule blocks for:")
        lines.append("")
        for block in created_blocks:
            lines.append(
                f"- {block.get('title')} - {block.get('duration_minutes')} min"
            )
        lines.append("")
        lines.append(
            "I added them as flexible blocks for today so you can place them around your day."
        )
    else:
        lines.append("I found your list, but I need durations before I schedule it.")

    if missing_duration_items:
        lines.append("")
        high_missing = [
            item for item in missing_duration_items if item.get("priority") == "highest"
        ]
        if high_missing:
            high_titles = ", ".join(str(item.get("title")) for item in high_missing)
            lines.append(f"I marked {high_titles} as highest priority.")
            lines.append("")
        lines.append("I need durations for:")
        for item in missing_duration_items:
            lines.append(f"- {item.get('title')}")
        lines.append("")
        lines.append(
            'Reply with durations like: "house 90, car 45" or say "estimate them."'
        )

    return "\n".join(lines).strip()


def _schedule_action_response(action: dict[str, Any]) -> dict[str, Any]:
    duration_minutes = action.get("duration_minutes")
    activity = action.get("activity")

    if duration_minutes is None:
        return _success_response(
            "schedule_clarify",
            "How long should I schedule for that?",
            {"missing": "duration", "schedule_action": action},
        )

    if not activity:
        return _success_response(
            "schedule_clarify",
            "What should I add to your schedule?",
            {"missing": "activity", "schedule_action": action},
        )

    title = _titleize_schedule_activity(str(activity))
    preferred_days = action.get("preferred_days") or []
    placement_mode = "preferred_day" if preferred_days else "whenever_free"

    payload = ScheduleBlockCreate(
        title=title,
        block_type="flexible",
        category="personal",
        duration_minutes=int(duration_minutes),
        recurrence="once",
        preferred_days=preferred_days,
        time_preference=action.get("time_preference") or "anytime",
        flexible_placement_mode=placement_mode,
        priority="medium",
        active=True,
    )

    try:
        before_ids = {
            int(block.get("id"))
            for block in orbit_service.list_schedule_blocks()
            if block.get("id") is not None
        }
        block = orbit_service.create_schedule_block(payload)
    except Exception as exc:
        return _success_response(
            "schedule_error",
            f"Couldn't add the {str(activity).strip()} block because {exc}.",
            {"error": str(exc), "schedule_action": action},
        )

    created = int(block.get("id") or 0) not in before_ids
    duration_text = _format_schedule_action_duration(duration_minutes)

    if not created:
        message = (
            f"{title} is already on your schedule as a "
            f"{_format_schedule_action_duration(duration_minutes, adjectival=True)} flexible block."
        )
    else:
        placement_text = (
            _format_preferred_days(preferred_days)
            if preferred_days
            else "whenever you're free"
        )
        message = (
            f"Added {duration_text} of {title} as a flexible schedule block "
            f"{placement_text}."
        )

    return _success_response(
        "schedule_create_block",
        message,
        {"schedule_block": block, "created": created},
    )


def _format_reminder_due_at(due_at: datetime) -> str:
    now = datetime.now(orbit_service.ORBIT_LOCAL_TIMEZONE)
    date_prefix = ""
    if due_at.date() == now.date():
        date_prefix = "today "
    elif due_at.date() == (now + timedelta(days=1)).date():
        date_prefix = "tomorrow "
    else:
        date_prefix = due_at.strftime("%b %-d ")
    return f"{date_prefix}{due_at.strftime('%-I:%M %p')}".strip()


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


def _trading_coach_response(message_text: str) -> dict[str, Any]:
    review = trading_coach.generate_trading_coach_review(
        today_only="today" in message_text,
    )
    return _success_response(
        "trading_coach_review",
        str(review.get("readable_summary") or "").strip(),
        {"trading_coach_review": review},
    )


def _trading_correlation_response() -> dict[str, Any]:
    review = trading_correlation.generate_trading_correlation_review()
    return _success_response(
        "trading_correlation_review",
        str(review.get("readable_summary") or "").strip(),
        {"trading_correlation_review": review},
    )


def _pattern_discovery_response() -> dict[str, Any]:
    review = pattern_discovery.generate_pattern_discovery_review()
    return _success_response(
        "pattern_discovery_review",
        str(review.get("readable_summary") or "").strip(),
        {"pattern_discovery_review": review},
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


def _titleize_schedule_activity(activity: str) -> str:
    return " ".join(word.capitalize() for word in activity.split())


def _format_preferred_days(days: list[str]) -> str:
    labels = [_day_label(day) for day in days]
    if not labels:
        return "whenever you're free"
    if len(labels) == 1:
        return f"on {labels[0]}"
    return "on " + ", ".join(labels[:-1]) + f" and {labels[-1]}"


def _format_schedule_action_duration(duration: Any, adjectival: bool = False) -> str:
    try:
        minutes = int(duration)
    except (TypeError, ValueError):
        return "scheduled" if adjectival else "some time"

    if adjectival:
        return f"{minutes}-minute" if minutes < 60 else f"{minutes // 60}-hour"

    hours = minutes // 60
    remainder = minutes % 60
    if hours and remainder:
        return f"{hours} hour{'s' if hours != 1 else ''} {remainder} minute{'s' if remainder != 1 else ''}"
    if hours:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{minutes} minute{'s' if minutes != 1 else ''}"


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
