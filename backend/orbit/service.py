from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any

from .database import get_connection, init_orbit_db
from .models import (
    GoalCreate,
    GoalUpdate,
    MajorEventCreate,
    MajorEventUpdate,
    MilestoneCreate,
    MilestoneUpdate,
    ReadinessCategoryCreate,
    ReadinessCategoryUpdate,
    ReviewCreate,
    TaskCreate,
    TaskUpdate,
    TradeSessionCreate,
    TradeSessionUpdate,
)


TABLE_COLUMNS = {
    "major_events": [
        "title",
        "description",
        "target_date",
        "status",
        "progress_percent",
    ],
    "milestones": [
        "major_event_id",
        "title",
        "description",
        "status",
        "progress_percent",
        "target_value",
        "current_value",
        "due_date",
    ],
    "goals": [
        "milestone_id",
        "title",
        "description",
        "status",
        "priority",
    ],
    "tasks": [
        "goal_id",
        "title",
        "description",
        "status",
        "due_date",
        "completed_at",
    ],
    "reviews": [
        "title",
        "review_type",
        "summary",
        "rating",
    ],
    "readiness_categories": [
        "major_event_id",
        "category_name",
        "current_score",
        "target_score",
        "notes",
    ],
    "trade_sessions": [
        "session_date",
        "symbol",
        "pnl",
        "notes",
        "rule_adherence",
        "confidence",
        "session_grade",
    ],
}


ORBIT_CORPORATE_ESCAPE_TITLE = "Corporate Escape"
ORBIT_INBOX_MILESTONE_TITLE = "Inbox / General"
ORBIT_INBOX_GOAL_TITLE = "Inbox"


def _serialize_value(value: Any) -> Any:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _model_data(model: Any, exclude_unset: bool = False) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        data = model.model_dump(exclude_unset=exclude_unset)
    else:
        data = dict(model)

    return {key: _serialize_value(value) for key, value in data.items()}


def _row_to_dict(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _create_record(table: str, data: dict[str, Any]) -> dict[str, Any]:
    init_orbit_db()

    columns = TABLE_COLUMNS[table]
    values = [_serialize_value(data.get(column)) for column in columns]
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})",
        values,
    )
    record_id = cursor.lastrowid
    conn.commit()
    conn.close()

    record = get_record(table, record_id)
    if record is None:
        raise RuntimeError(f"Unable to load created {table} record.")
    return record


def _update_record(table: str, record_id: int, data: dict[str, Any]) -> dict[str, Any] | None:
    init_orbit_db()

    update_data = {
        key: _serialize_value(value)
        for key, value in data.items()
        if key in TABLE_COLUMNS[table]
    }

    if not update_data:
        return get_record(table, record_id)

    assignments = ", ".join(f"{column} = ?" for column in update_data)
    values = list(update_data.values()) + [record_id]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"UPDATE {table} SET {assignments} WHERE id = ?",
        values,
    )
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()

    if not updated:
        return None

    return get_record(table, record_id)


def list_records(table: str) -> list[dict[str, Any]]:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table} ORDER BY id")
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_record(table: str, record_id: int) -> dict[str, Any] | None:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table} WHERE id = ?", (record_id,))
    row = cursor.fetchone()
    conn.close()

    return _row_to_dict(row)


def delete_record(table: str, record_id: int) -> bool:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"DELETE FROM {table} WHERE id = ?", (record_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()

    return deleted


def _list_records_ordered(table: str, order_by: str) -> list[dict[str, Any]]:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table} ORDER BY {order_by}")
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def create_major_event(payload: MajorEventCreate) -> dict[str, Any]:
    return _create_record("major_events", _model_data(payload))


def update_major_event(record_id: int, payload: MajorEventUpdate) -> dict[str, Any] | None:
    return _update_record("major_events", record_id, _model_data(payload, exclude_unset=True))


def create_milestone(payload: MilestoneCreate) -> dict[str, Any]:
    return _create_record("milestones", _model_data(payload))


def update_milestone(record_id: int, payload: MilestoneUpdate) -> dict[str, Any] | None:
    return _update_record("milestones", record_id, _model_data(payload, exclude_unset=True))


def create_goal(payload: GoalCreate) -> dict[str, Any]:
    return _create_record("goals", _model_data(payload))


def update_goal(record_id: int, payload: GoalUpdate) -> dict[str, Any] | None:
    return _update_record("goals", record_id, _model_data(payload, exclude_unset=True))


def create_task(payload: TaskCreate) -> dict[str, Any]:
    return _create_record("tasks", _model_data(payload))


def update_task(record_id: int, payload: TaskUpdate) -> dict[str, Any] | None:
    return _update_record("tasks", record_id, _model_data(payload, exclude_unset=True))


def _find_record(table: str, **matches: Any) -> dict[str, Any] | None:
    for record in list_records(table):
        if all(record.get(key) == value for key, value in matches.items()):
            return record
    return None


def _get_corporate_escape_event() -> dict[str, Any] | None:
    return _find_record("major_events", title=ORBIT_CORPORATE_ESCAPE_TITLE)


def get_or_create_inbox_goal() -> dict[str, Any]:
    event = _get_corporate_escape_event()
    if event is None:
        raise RuntimeError("Corporate Escape major event not found.")

    milestone = _find_record(
        "milestones",
        major_event_id=event.get("id"),
        title=ORBIT_INBOX_MILESTONE_TITLE,
    )
    if milestone is None:
        milestone = _create_record(
            "milestones",
            {
                "major_event_id": event.get("id"),
                "title": ORBIT_INBOX_MILESTONE_TITLE,
                "description": "Default catch-all milestone for loose Orbit goals and tasks.",
                "status": "active",
                "progress_percent": 0,
                "target_value": None,
                "current_value": None,
                "due_date": None,
            },
        )

    goal = _find_record(
        "goals",
        milestone_id=milestone.get("id"),
        title=ORBIT_INBOX_GOAL_TITLE,
    )
    if goal is not None:
        return goal

    return _create_record(
        "goals",
        {
            "milestone_id": milestone.get("id"),
            "title": ORBIT_INBOX_GOAL_TITLE,
            "description": "Default catch-all goal for loose Orbit tasks.",
            "status": "active",
            "priority": 0,
        },
    )


def list_inbox_tasks() -> list[dict[str, Any]]:
    inbox_goal = get_or_create_inbox_goal()
    inbox_goal_id = inbox_goal.get("id")
    return [
        task
        for task in list_records("tasks")
        if task.get("goal_id") == inbox_goal_id
    ]


def create_inbox_task(payload: Any) -> dict[str, Any]:
    inbox_goal = get_or_create_inbox_goal()
    data = _model_data(payload)
    return _create_record(
        "tasks",
        {
            "goal_id": inbox_goal.get("id"),
            "title": data.get("title"),
            "description": data.get("description"),
            "status": data.get("status") or "queued",
            "due_date": data.get("due_date"),
            "completed_at": None,
        },
    )


def create_review(payload: ReviewCreate) -> dict[str, Any]:
    return _create_record("reviews", _model_data(payload))


def get_readiness_categories(major_event_id: int | None = None) -> list[dict[str, Any]]:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    if major_event_id is None:
        cursor.execute("SELECT * FROM readiness_categories ORDER BY major_event_id, id")
    else:
        cursor.execute(
            """
            SELECT *
            FROM readiness_categories
            WHERE major_event_id = ?
            ORDER BY id
            """,
            (major_event_id,),
        )
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def create_readiness_category(payload: ReadinessCategoryCreate) -> dict[str, Any]:
    return _create_record("readiness_categories", _model_data(payload))


def update_readiness_category(
    record_id: int,
    payload: ReadinessCategoryUpdate,
) -> dict[str, Any] | None:
    return _update_record(
        "readiness_categories",
        record_id,
        _model_data(payload, exclude_unset=True),
    )


def create_trade_session(payload: TradeSessionCreate) -> dict[str, Any]:
    return _create_record("trade_sessions", _model_data(payload))


def list_trade_sessions() -> list[dict[str, Any]]:
    return _list_records_ordered("trade_sessions", "session_date DESC, id DESC")


def get_trade_session(record_id: int) -> dict[str, Any] | None:
    return get_record("trade_sessions", record_id)


def update_trade_session(
    record_id: int,
    payload: TradeSessionUpdate,
) -> dict[str, Any] | None:
    return _update_record(
        "trade_sessions",
        record_id,
        _model_data(payload, exclude_unset=True),
    )


def delete_trade_session(record_id: int) -> bool:
    return delete_record("trade_sessions", record_id)


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None


def _is_open(record: dict[str, Any]) -> bool:
    return str(record.get("status") or "").casefold() not in {
        "complete",
        "completed",
        "done",
        "cancelled",
    }


def _is_active(record: dict[str, Any]) -> bool:
    return str(record.get("status") or "").casefold() in {
        "active",
        "in_progress",
        "not_started",
        "queued",
    }


def _days_remaining(value: str | None, today: date) -> int | None:
    target_date = _parse_date(value)
    if target_date is None:
        return None
    return max((target_date - today).days, 0)


def _summary(record: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    return {field: record.get(field) for field in fields}


def _latest_records(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    return sorted(
        records,
        key=lambda record: str(record.get("created_at") or record.get("id") or ""),
        reverse=True,
    )[:limit]


def _format_briefing_text(
    major_event: dict[str, Any] | None,
    readiness: dict[str, Any],
    top_tasks: list[dict[str, Any]],
    current_blockers: list[str],
    suggested_next_action: str,
) -> str:
    event_line = "No active major event found."
    if major_event:
        days = major_event.get("days_remaining")
        days_text = f"{days} days remaining" if days is not None else "no target date"
        event_line = (
            f"{major_event.get('title')} is {major_event.get('progress_percent')}% complete "
            f"with {days_text}."
        )

    task_lines = [
        f"{index}. {task.get('title')}"
        for index, task in enumerate(top_tasks[:3], start=1)
    ] or ["No priority tasks"]
    blocker_lines = current_blockers[:3] or ["No active blockers"]

    return (
        "Morning Briefing\n\n"
        f"{event_line}\n"
        f"Readiness: {readiness.get('overall')}% overall.\n\n"
        "Top tasks:\n"
        + "\n".join(task_lines)
        + "\n\nBlockers:\n"
        + "\n".join(f"- {blocker}" for blocker in blocker_lines)
        + f"\n\nNext action: {suggested_next_action}"
    )


def generate_morning_briefing() -> dict[str, Any]:
    """Build a compact Orbit briefing. A future Morning Review Agent can call this unchanged."""
    init_orbit_db()

    today = datetime.now().date()
    generated_at = datetime.now(timezone.utc).isoformat()

    major_events = list_records("major_events")
    milestones = list_records("milestones")
    goals = list_records("goals")
    tasks = list_records("tasks")
    reviews = list_records("reviews")
    readiness_categories = get_readiness_categories()
    trade_sessions = list_trade_sessions()

    active_events = [
        event
        for event in major_events
        if _is_active(event) and _is_open(event)
    ]
    active_event = active_events[0] if active_events else (major_events[0] if major_events else None)
    active_event_id = active_event.get("id") if active_event else None

    major_event = None
    if active_event:
        major_event = {
            "id": active_event.get("id"),
            "title": active_event.get("title"),
            "days_remaining": _days_remaining(active_event.get("target_date"), today),
            "progress_percent": active_event.get("progress_percent"),
            "status": active_event.get("status"),
        }

    event_readiness = [
        category
        for category in readiness_categories
        if active_event_id is None or category.get("major_event_id") == active_event_id
    ]
    readiness_overall = (
        round(
            sum(int(category.get("current_score") or 0) for category in event_readiness)
            / len(event_readiness)
        )
        if event_readiness
        else 0
    )
    readiness = {
        "overall": readiness_overall,
        "categories": [
            _summary(
                category,
                ["id", "category_name", "current_score", "target_score", "notes"],
            )
            for category in event_readiness
        ],
    }

    event_milestones = [
        milestone
        for milestone in milestones
        if active_event_id is None or milestone.get("major_event_id") == active_event_id
    ]
    priority_milestones = [
        _summary(
            milestone,
            ["id", "title", "status", "progress_percent", "due_date"],
        )
        for milestone in sorted(
            [
                milestone
                for milestone in event_milestones
                if str(milestone.get("status") or "").casefold() in {"active", "in_progress"}
                and _is_open(milestone)
            ],
            key=lambda milestone: (
                int(milestone.get("progress_percent") or 0),
                _parse_date(milestone.get("due_date")) or date.max,
                int(milestone.get("id") or 0),
            ),
        )[:3]
    ]

    goals_by_id = {goal.get("id"): goal for goal in goals}
    milestones_by_id = {milestone.get("id"): milestone for milestone in milestones}
    inbox_goal_ids = {
        goal.get("id")
        for goal in goals
        if str(goal.get("title") or "").casefold() == "inbox"
    }
    open_tasks = [task for task in tasks if _is_open(task)]

    def task_sort_key(task: dict[str, Any]) -> tuple[int, int, date, int, int]:
        due_date = _parse_date(task.get("due_date"))
        goal = goals_by_id.get(task.get("goal_id"))
        milestone = milestones_by_id.get(goal.get("milestone_id")) if goal else None
        is_inbox = task.get("goal_id") in inbox_goal_ids
        is_event_task = (
            active_event_id is not None
            and milestone is not None
            and milestone.get("major_event_id") == active_event_id
        )
        is_urgent = due_date is not None and due_date <= today
        return (
            0 if is_inbox else 1,
            0 if is_urgent else 1,
            due_date or date.max,
            0 if is_event_task else 1,
            int(task.get("id") or 0),
        )

    top_tasks = [
        _summary(task, ["id", "title", "status", "due_date", "goal_id"])
        for task in sorted(open_tasks, key=task_sort_key)[:5]
    ]

    recent_reviews = [
        _summary(review, ["id", "title", "review_type", "summary", "rating", "created_at"])
        for review in _latest_records(reviews, 3)
    ]
    recent_trade_sessions = [
        _summary(
            session,
            [
                "id",
                "session_date",
                "symbol",
                "pnl",
                "rule_adherence",
                "confidence",
                "session_grade",
            ],
        )
        for session in trade_sessions[:3]
    ]

    current_blockers: list[str] = []
    overdue_tasks = [
        task
        for task in open_tasks
        if (due_date := _parse_date(task.get("due_date"))) is not None and due_date < today
    ]
    if overdue_tasks:
        current_blockers.append(f"{len(overdue_tasks)} overdue task(s) need attention.")

    stalled_milestones = [
        milestone
        for milestone in event_milestones
        if _is_open(milestone)
        and str(milestone.get("status") or "").casefold() in {"active", "in_progress"}
        and int(milestone.get("progress_percent") or 0) == 0
    ]
    if stalled_milestones:
        current_blockers.append(
            f"Milestone is active but still at 0%: {stalled_milestones[0].get('title')}."
        )

    low_readiness = [
        category
        for category in event_readiness
        if int(category.get("current_score") or 0) < 50
    ]
    if low_readiness:
        names = ", ".join(str(category.get("category_name")) for category in low_readiness[:3])
        current_blockers.append(f"Low readiness categories: {names}.")

    latest_review_date = _parse_date(recent_reviews[0].get("created_at")) if recent_reviews else None
    if latest_review_date is None or (today - latest_review_date).days > 2:
        current_blockers.append("No recent Orbit review within the last 2 days.")

    if top_tasks:
        suggested_next_action = f"Complete or advance: {top_tasks[0].get('title')}."
    elif current_blockers:
        suggested_next_action = f"Clear blocker: {current_blockers[0]}"
    elif priority_milestones:
        suggested_next_action = f"Move milestone forward: {priority_milestones[0].get('title')}."
    else:
        suggested_next_action = "No suggested action yet"

    briefing_text = _format_briefing_text(
        major_event=major_event,
        readiness=readiness,
        top_tasks=top_tasks,
        current_blockers=current_blockers,
        suggested_next_action=suggested_next_action,
    )

    return {
        "success": True,
        "generated_at": generated_at,
        "major_event": major_event,
        "readiness": readiness,
        "priority_milestones": priority_milestones,
        "top_tasks": top_tasks,
        "current_blockers": current_blockers,
        "suggested_next_action": suggested_next_action,
        "recent_reviews": recent_reviews,
        "recent_trade_sessions": recent_trade_sessions,
        "briefing_text": briefing_text,
    }
