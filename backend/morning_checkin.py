from __future__ import annotations

import json
import subprocess
from datetime import date, datetime, time as datetime_time, timezone
from pathlib import Path
from typing import Any, Literal

import agent_service
from notification_config import get_default_imessage_recipient


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


def _speak_summary(summary: str) -> bool:
    subprocess.run(["say", summary[:500]], check=True)
    return True


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


def check_in(source: Source = "manual", speak: bool = False) -> dict[str, Any]:
    now = _now_local()
    run = ensure_morning_review_output(now)
    summary = _summary_from_run(run)
    day_state = _get_day_state(now)
    channel = "tts" if source == "voice" and speak else source

    day_state.update(
        {
            "morning_acknowledged": True,
            "morning_acknowledged_at": now.isoformat(),
            "morning_agent_run_id": run.get("id"),
            "delivery_channel": channel,
        }
    )

    tts_spoken = False
    if speak:
        _speak_summary(summary)
        tts_spoken = True

    _save_day_state(day_state)

    return {
        "success": True,
        "summary": summary,
        "agent_run": run,
        "status": get_status(),
        "delivery_channel": channel,
        "tts_spoken": tts_spoken,
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
