from __future__ import annotations

import json
import re
from datetime import date, datetime, time as datetime_time, timezone
from pathlib import Path
from typing import Any, Literal

import agent_service
from notification_config import get_default_imessage_recipient
from tts import format_text_for_speech, speak_text


STATUS_FILE = Path(__file__).resolve().parent / ".morning_checkin_status.json"
MORNING_AGENT_TYPE = "morning_review"
DEFAULT_CUTOFF = datetime_time(hour=6, minute=30)
Source = Literal["ui", "imessage", "voice", "manual"]


def _now_local() -> datetime:
    return datetime.now().astimezone()


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc).astimezone()
    return parsed.astimezone()


def _run_date(value: Any) -> date | None:
    parsed = _parse_datetime(value)
    return parsed.date() if parsed else None


def _read_status_file() -> dict[str, Any]:
    if not STATUS_FILE.exists():
        return {}
    try:
        content = json.loads(STATUS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return content if isinstance(content, dict) else {}


def _write_status_file(status: dict[str, Any]) -> None:
    STATUS_FILE.write_text(
        json.dumps(status, indent=2, sort_keys=True),
        encoding="utf-8",
    )


def _default_day_state(day: date) -> dict[str, Any]:
    return {
        "date": day.isoformat(),
        "morning_acknowledged": False,
        "morning_acknowledged_at": None,
        "morning_fallback_sent": False,
        "morning_fallback_sent_at": None,
        "morning_agent_run_id": None,
        "delivery_channel": None,
    }


def _get_day_state(now: datetime | None = None) -> dict[str, Any]:
    current = now or _now_local()
    status = _read_status_file()
    today_key = current.date().isoformat()
    day_state = status.get(today_key)
    if not isinstance(day_state, dict):
        return _default_day_state(current.date())
    return {**_default_day_state(current.date()), **day_state, "date": today_key}


def _save_day_state(day_state: dict[str, Any]) -> None:
    status = _read_status_file()
    status[str(day_state["date"])] = day_state
    _write_status_file(status)


def _morning_agent() -> dict[str, Any] | None:
    for agent in agent_service.list_agents():
        if agent.get("agent_type") == MORNING_AGENT_TYPE and agent.get("enabled"):
            return agent
    return None


def _latest_morning_run_today(now: datetime) -> dict[str, Any] | None:
    agent = _morning_agent()
    last_run = agent.get("last_run") if agent else None
    if not isinstance(last_run, dict):
        return None
    if _run_date(last_run.get("started_at")) != now.date():
        return None
    return last_run


def ensure_morning_review_output(now: datetime | None = None) -> dict[str, Any]:
    current = now or _now_local()
    existing = _latest_morning_run_today(current)
    if existing is not None:
        return existing

    agent = _morning_agent()
    if agent is None:
        raise RuntimeError("Morning Review Agent is missing or disabled.")
    return agent_service.run_agent(int(agent["id"]))


def _summary_from_run(run: dict[str, Any]) -> str:
    summary = str(run.get("summary") or "").strip()
    if summary:
        return summary
    output = run.get("output_json")
    if isinstance(output, dict):
        briefing_text = str(output.get("briefing_text") or "").strip()
        if briefing_text:
            return briefing_text
    return "Morning review is available, but no summary text was returned."


def _sentence_case(value: str) -> str:
    value = value.strip().rstrip(".")
    if not value:
        return value
    return value[0].lower() + value[1:]


def _extract_line_value(summary: str, label: str) -> str | None:
    pattern = re.compile(rf"^{re.escape(label)}:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(summary)
    if not match:
        return None
    return match.group(1).strip()


def _extract_label_value(summary: str, label: str) -> str | None:
    value = _extract_line_value(summary, label)
    if value:
        return value
    return _first_item_after_heading(summary, label)


def _first_item_after_heading(summary: str, heading: str) -> str | None:
    lines = summary.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() != f"{heading.lower()}:":
            continue
        for next_line in lines[index + 1 :]:
            cleaned = next_line.strip()
            if not cleaned:
                continue
            if cleaned.endswith(":") and not cleaned.startswith(("-", "*")):
                return None
            cleaned = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s*", "", cleaned).strip()
            if cleaned:
                return cleaned
        return None
    return None


def _clean_morning_task_for_speech(task: str) -> str:
    task = re.sub(r"\s*\(P\d+\)\s*", " ", task).strip()
    if " - " in task:
        task_text, context = [part.strip() for part in task.split(" - ", 1)]
        if context and context.lower() not in task_text.lower():
            task = f"{task_text} for {context}"
        else:
            task = task_text
    task = re.sub(
        r"\bCreate first review checklist for Build trading review cadence\b",
        "create the first review checklist for your trading review cadence",
        task,
        flags=re.IGNORECASE,
    )
    task = re.sub(r"\bCreate first task supporting\b", "create the first task for", task)
    return _sentence_case(task)


def _clean_status_for_speech(value: str) -> str:
    value = re.sub(r"\s*\(P\d+\)\s*", "", value).strip()
    value = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"\1 percent", value)
    return _sentence_case(value)


def condense_morning_summary_for_speech(summary: str) -> str:
    parts: list[str] = ["Good morning."]

    corporate_match = re.search(
        r"Corporate Escape is\s+(\d+(?:\.\d+)?)%\s+complete(?:\s+with\s+([^.\n]+))?",
        summary,
        re.IGNORECASE,
    )
    if corporate_match:
        progress = corporate_match.group(1)
        days_text = corporate_match.group(2)
        if days_text:
            parts.append(
                f"Corporate Escape is {progress} percent complete, with {days_text}."
            )
        else:
            parts.append(f"Corporate Escape is {progress} percent complete.")

    readiness = _extract_label_value(summary, "Readiness")
    if readiness:
        parts.append(f"Overall readiness is {_clean_status_for_speech(readiness)}.")

    top_task = _extract_label_value(summary, "Top Priority Task")
    if top_task:
        parts.append(f"Your top priority is to {_clean_morning_task_for_speech(top_task)}.")

    blocker = _first_item_after_heading(summary, "Blockers")
    if blocker and blocker.lower() != "no active blockers":
        parts.append(f"The biggest blocker is {_clean_status_for_speech(blocker)}.")
    else:
        gap = _first_item_after_heading(summary, "Strategic Gaps")
        if gap and gap.lower() != "no strategic gaps":
            parts.append(
                f"The biggest strategic gap is {_clean_morning_task_for_speech(gap)}."
            )

    next_action = _extract_label_value(summary, "Next action")
    if next_action:
        parts.append(f"For focus, {_clean_morning_task_for_speech(next_action)}.")

    return format_text_for_speech(" ".join(parts))


def format_morning_summary_for_speech(summary: str) -> str:
    return condense_morning_summary_for_speech(summary)


def _should_speak(source: Source, speak: bool | None) -> bool:
    if speak is not None:
        return speak
    return source == "voice"


def _delivery_channel(source: Source, should_speak: bool) -> str:
    if not should_speak:
        return source
    if source == "voice":
        return "tts"
    return f"{source}+tts"


def _send_imessage_summary(summary: str) -> dict[str, Any]:
    from imessage_bridge import send_imessage

    recipient_config = get_default_imessage_recipient()
    recipient = recipient_config["recipient"]
    if not recipient:
        raise RuntimeError("No iMessage recipient provided or configured.")

    send_imessage(recipient, summary)
    return {
        "recipient": recipient_config["masked_recipient"],
        "recipient_source": recipient_config["source"],
    }


def get_status() -> dict[str, Any]:
    now = _now_local()
    day_state = _get_day_state(now)
    cutoff_due = now.time() >= DEFAULT_CUTOFF
    return {
        **day_state,
        "current_local_time": now.isoformat(),
        "cutoff_time": "06:30",
        "cutoff_due": cutoff_due,
    }


def check_in(source: Source = "manual", speak: bool | None = None) -> dict[str, Any]:
    now = _now_local()
    run = ensure_morning_review_output(now)
    summary = _summary_from_run(run)
    day_state = _get_day_state(now)
    should_speak = _should_speak(source, speak)
    channel = _delivery_channel(source, should_speak)

    day_state.update(
        {
            "morning_acknowledged": True,
            "morning_acknowledged_at": now.isoformat(),
            "morning_agent_run_id": run.get("id"),
            "delivery_channel": channel,
        }
    )

    spoken = False
    spoken_text = None
    original_text = None
    tts_success = False
    tts_error = None
    full_spoken_text_available = False
    if should_speak:
        original_text = summary
        spoken_text = condense_morning_summary_for_speech(summary)
        full_spoken_text_available = True
        try:
            spoken_text = speak_text(spoken_text)
            spoken = True
            tts_success = True
        except Exception as exc:
            tts_error = f"{type(exc).__name__}: {exc}"

    _save_day_state(day_state)

    return {
        "success": True,
        "summary": summary,
        "agent_run": run,
        "status": get_status(),
        "delivery_channel": channel,
        "spoken": spoken,
        "spoken_text": spoken_text,
        "full_spoken_text_available": full_spoken_text_available,
        "original_text": original_text,
        "tts_success": tts_success,
        "tts_error": tts_error,
        "tts_spoken": spoken,
        "fallback_sent": False,
        "actions_taken": [],
    }


def fallback_check() -> dict[str, Any]:
    now = _now_local()
    day_state = _get_day_state(now)

    if day_state["morning_acknowledged"]:
        return {
            "success": True,
            "fallback_sent": False,
            "reason": "Morning check-in already acknowledged today.",
            "status": get_status(),
            "agent_run": None,
            "summary": None,
        }

    if day_state["morning_fallback_sent"]:
        return {
            "success": True,
            "fallback_sent": False,
            "reason": "Morning fallback already sent today.",
            "status": get_status(),
            "agent_run": None,
            "summary": None,
        }

    if now.time() < DEFAULT_CUTOFF:
        return {
            "success": True,
            "fallback_sent": False,
            "reason": "Morning fallback cutoff has not passed.",
            "status": get_status(),
            "agent_run": None,
            "summary": None,
        }

    run = ensure_morning_review_output(now)
    summary = _summary_from_run(run)
    delivery = _send_imessage_summary(summary)

    day_state.update(
        {
            "morning_fallback_sent": True,
            "morning_fallback_sent_at": now.isoformat(),
            "morning_agent_run_id": run.get("id"),
            "delivery_channel": "imessage",
        }
    )
    _save_day_state(day_state)

    return {
        "success": True,
        "fallback_sent": True,
        "reason": "Morning fallback summary sent.",
        "status": get_status(),
        "agent_run": run,
        "summary": summary,
        "delivery": delivery,
    }
