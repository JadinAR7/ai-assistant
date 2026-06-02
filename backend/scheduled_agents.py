from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import date, datetime, time as datetime_time, timezone
from pathlib import Path
from typing import Any

import agent_service
import morning_checkin


STATUS_FILE = Path(__file__).resolve().parent / ".scheduled_agents_status.json"
MORNING_AGENT_TYPE = "morning_review"
EVENING_AGENT_TYPE = "evening_review"
SCHEDULED_AGENT_TYPES = {MORNING_AGENT_TYPE, EVENING_AGENT_TYPE}


@dataclass(frozen=True)
class ScheduleWindow:
    label: str
    agent_type: str
    start: datetime_time
    end: datetime_time


SCHEDULE_WINDOWS = {
    "morning": ScheduleWindow(
        label="morning",
        agent_type=MORNING_AGENT_TYPE,
        start=datetime_time(hour=6),
        end=datetime_time(hour=9),
    ),
    "evening": ScheduleWindow(
        label="evening",
        agent_type=EVENING_AGENT_TYPE,
        start=datetime_time(hour=18),
        end=datetime_time(hour=22),
    ),
}


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


def _enabled_agents_by_type() -> dict[str, dict[str, Any]]:
    agents = agent_service.list_agents()
    return {
        str(agent.get("agent_type")): agent
        for agent in agents
        if agent.get("enabled")
    }


def _latest_run_for_agent_type(agent_type: str) -> dict[str, Any] | None:
    agent = _enabled_agents_by_type().get(agent_type)
    last_run = agent.get("last_run") if agent else None
    return last_run if isinstance(last_run, dict) else None


def _has_run_today(agent: dict[str, Any], today: date) -> bool:
    last_run = agent.get("last_run")
    if not isinstance(last_run, dict):
        return False
    return _run_date(last_run.get("started_at")) == today


def _is_window_due(
    window: ScheduleWindow,
    agent: dict[str, Any] | None,
    now: datetime,
) -> tuple[bool, str]:
    if agent is None:
        return False, "Agent is missing or disabled."
    if _has_run_today(agent, now.date()):
        return False, "Already ran today."
    current_time = now.time()
    if window.start <= current_time <= window.end:
        return True, "Due inside scheduled window."
    return False, "Outside scheduled window."


def _prioritization_snapshot_due(status_file: dict[str, Any], today: date) -> bool:
    snapshot = status_file.get("prioritization_snapshot")
    if not isinstance(snapshot, dict):
        return True
    return str(snapshot.get("snapshot_date") or "") != today.isoformat()


def _record_prioritization_snapshot(now: datetime) -> dict[str, Any]:
    snapshot = agent_service.prioritize_agents()
    status_file = _read_status_file()
    status_file["prioritization_snapshot"] = {
        "snapshot_date": now.date().isoformat(),
        "created_at": now.isoformat(),
        "result": snapshot,
    }
    _write_status_file(status_file)
    return status_file["prioritization_snapshot"]


def get_status() -> dict[str, Any]:
    now = _now_local()
    agents_by_type = _enabled_agents_by_type()
    status_file = _read_status_file()
    morning_window = SCHEDULE_WINDOWS["morning"]
    evening_window = SCHEDULE_WINDOWS["evening"]
    morning_due, morning_reason = _is_window_due(
        morning_window,
        agents_by_type.get(morning_window.agent_type),
        now,
    )
    evening_due, evening_reason = _is_window_due(
        evening_window,
        agents_by_type.get(evening_window.agent_type),
        now,
    )

    return {
        "current_local_time": now.isoformat(),
        "scheduler_enabled": True,
        "scheduler_status": "available",
        "morning": {
            "agent_type": MORNING_AGENT_TYPE,
            "window_start": "06:00",
            "window_end": "09:00",
            "due": morning_due,
            "reason": morning_reason,
            "last_run": _latest_run_for_agent_type(MORNING_AGENT_TYPE),
        },
        "evening": {
            "agent_type": EVENING_AGENT_TYPE,
            "window_start": "18:00",
            "window_end": "22:00",
            "due": evening_due,
            "reason": evening_reason,
            "last_run": _latest_run_for_agent_type(EVENING_AGENT_TYPE),
        },
        "last_scheduled_morning_run": _latest_run_for_agent_type(
            MORNING_AGENT_TYPE
        ),
        "last_scheduled_evening_run": _latest_run_for_agent_type(
            EVENING_AGENT_TYPE
        ),
        "prioritization_snapshot_due": _prioritization_snapshot_due(
            status_file,
            now.date(),
        ),
        "last_prioritization_snapshot": status_file.get(
            "prioritization_snapshot"
        ),
    }


def run_due_once() -> dict[str, Any]:
    now = _now_local()
    agents_by_type = _enabled_agents_by_type()
    actions: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []

    for window in SCHEDULE_WINDOWS.values():
        agent = agents_by_type.get(window.agent_type)
        due, reason = _is_window_due(window, agent, now)
        if not due:
            actions.append(
                {
                    "schedule": window.label,
                    "agent_type": window.agent_type,
                    "status": "skipped",
                    "reason": reason,
                }
            )
            continue

        run = agent_service.run_agent(int(agent["id"]))
        runs.append(run)
        actions.append(
            {
                "schedule": window.label,
                "agent_type": window.agent_type,
                "status": "ran",
                "agent_run_id": run.get("id"),
                "result_status": run.get("status"),
            }
        )

    status_file = _read_status_file()
    if _prioritization_snapshot_due(status_file, now.date()):
        snapshot = _record_prioritization_snapshot(now)
        actions.append(
            {
                "schedule": "prioritization_snapshot",
                "status": "captured",
                "snapshot_date": snapshot.get("snapshot_date"),
            }
        )
    else:
        actions.append(
            {
                "schedule": "prioritization_snapshot",
                "status": "skipped",
                "reason": "Already captured today.",
            }
        )

    try:
        fallback_result = morning_checkin.fallback_check()
        actions.append(
            {
                "schedule": "morning_fallback",
                "status": "sent" if fallback_result.get("fallback_sent") else "skipped",
                "reason": fallback_result.get("reason"),
                "agent_run_id": (
                    fallback_result.get("agent_run") or {}
                ).get("id"),
            }
        )
    except Exception as exc:
        actions.append(
            {
                "schedule": "morning_fallback",
                "status": "failed",
                "reason": f"Fallback check failed: {type(exc).__name__}",
            }
        )

    return {
        "checked_at": now.isoformat(),
        "actions": actions,
        "runs": runs,
        "status": get_status(),
    }


def run_loop(interval_seconds: int = 300) -> None:
    while True:
        result = run_due_once()
        print(json.dumps(result, indent=2, sort_keys=True), flush=True)
        time.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Helix scheduled agents.")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Check scheduled agents once, then exit.",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=300,
        help="Loop interval when running continuously.",
    )
    args = parser.parse_args()

    if args.once:
        print(json.dumps(run_due_once(), indent=2, sort_keys=True))
        return

    run_loop(max(60, args.interval_seconds))


if __name__ == "__main__":
    main()
