from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

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
    RecommendationTaskDraft,
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
MILESTONE_PROGRESS_SOURCES = {"manual", "task_advisory", "helix_tool", "system"}
ORBIT_LOCAL_TIMEZONE = ZoneInfo("America/Denver")
STRATEGIC_GAP_RECENT_ACTIVITY_DAYS = 7
STRATEGIC_GAP_RECOMMENDATION_PREFIX = "strategic-gap-"


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


def _normalize_progress_source(value: Any) -> str:
    source = str(value or "manual").casefold()
    if source not in MILESTONE_PROGRESS_SOURCES:
        return "manual"
    return source


def create_milestone_progress_history(
    milestone_id: int,
    previous_progress: int,
    new_progress: int,
    source: str = "manual",
    reason: str | None = None,
) -> dict[str, Any]:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO milestone_progress_history (
            milestone_id,
            previous_progress,
            new_progress,
            change_amount,
            reason,
            source
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            milestone_id,
            previous_progress,
            new_progress,
            new_progress - previous_progress,
            reason,
            _normalize_progress_source(source),
        ),
    )
    history_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return get_milestone_progress_history_record(int(history_id))


def get_milestone_progress_history_record(record_id: int) -> dict[str, Any] | None:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT milestone_progress_history.*, milestones.title AS milestone_title
        FROM milestone_progress_history
        JOIN milestones ON milestones.id = milestone_progress_history.milestone_id
        WHERE milestone_progress_history.id = ?
        """,
        (record_id,),
    )
    row = cursor.fetchone()
    conn.close()

    return _row_to_dict(row)


def list_milestone_progress_history(milestone_id: int) -> list[dict[str, Any]]:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT milestone_progress_history.*, milestones.title AS milestone_title
        FROM milestone_progress_history
        JOIN milestones ON milestones.id = milestone_progress_history.milestone_id
        WHERE milestone_progress_history.milestone_id = ?
        ORDER BY milestone_progress_history.created_at DESC, milestone_progress_history.id DESC
        """,
        (milestone_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def list_recent_milestone_progress_history(limit: int = 20) -> list[dict[str, Any]]:
    """Recent progress events for closeouts and future review agents."""
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT milestone_progress_history.*, milestones.title AS milestone_title
        FROM milestone_progress_history
        JOIN milestones ON milestones.id = milestone_progress_history.milestone_id
        ORDER BY milestone_progress_history.created_at DESC, milestone_progress_history.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def update_milestone(record_id: int, payload: MilestoneUpdate) -> dict[str, Any] | None:
    existing = get_record("milestones", record_id)
    if existing is None:
        return None

    data = _model_data(payload, exclude_unset=True)
    source = _normalize_progress_source(data.pop("progress_update_source", None))
    reason = data.pop("progress_update_reason", None)
    previous_progress = int(existing.get("progress_percent") or 0)
    updated = _update_record("milestones", record_id, data)

    if updated is None:
        return None

    if "progress_percent" in data:
        new_progress = int(updated.get("progress_percent") or 0)
        if new_progress != previous_progress:
            create_milestone_progress_history(
                milestone_id=record_id,
                previous_progress=previous_progress,
                new_progress=new_progress,
                source=source,
                reason=reason,
            )

    return updated


def create_goal(payload: GoalCreate) -> dict[str, Any]:
    return _create_record("goals", _model_data(payload))


def update_goal(record_id: int, payload: GoalUpdate) -> dict[str, Any] | None:
    return _update_record("goals", record_id, _model_data(payload, exclude_unset=True))


def create_task(payload: TaskCreate) -> dict[str, Any]:
    return _create_record("tasks", _model_data(payload))


def update_task(record_id: int, payload: TaskUpdate) -> dict[str, Any] | None:
    return _update_record("tasks", record_id, _model_data(payload, exclude_unset=True))


def link_task_to_milestone(task_id: int, milestone_id: int) -> dict[str, Any] | None:
    init_orbit_db()

    if get_record("tasks", task_id) is None or get_record("milestones", milestone_id) is None:
        return None

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR IGNORE INTO task_milestone_links (task_id, milestone_id)
        VALUES (?, ?)
        """,
        (task_id, milestone_id),
    )
    conn.commit()
    cursor.execute(
        """
        SELECT *
        FROM task_milestone_links
        WHERE task_id = ? AND milestone_id = ?
        """,
        (task_id, milestone_id),
    )
    row = cursor.fetchone()
    conn.close()

    return _row_to_dict(row)


def unlink_task_from_milestone(task_id: int, milestone_id: int) -> bool:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM task_milestone_links
        WHERE task_id = ? AND milestone_id = ?
        """,
        (task_id, milestone_id),
    )
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()

    return deleted


def list_milestones_linked_to_task(task_id: int) -> list[dict[str, Any]]:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT milestones.*, major_events.title AS major_event_title
        FROM task_milestone_links
        JOIN milestones ON milestones.id = task_milestone_links.milestone_id
        JOIN major_events ON major_events.id = milestones.major_event_id
        WHERE task_milestone_links.task_id = ?
        ORDER BY milestones.id
        """,
        (task_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def list_tasks_linked_to_milestone(milestone_id: int) -> list[dict[str, Any]]:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT tasks.*
        FROM task_milestone_links
        JOIN tasks ON tasks.id = task_milestone_links.task_id
        WHERE task_milestone_links.milestone_id = ?
        ORDER BY tasks.id
        """,
        (milestone_id,),
    )
    rows = cursor.fetchall()
    conn.close()

    return sorted(
        [_with_linked_milestones(dict(row)) for row in rows],
        key=_priority_sort_key,
    )


def get_milestone_progress_advisory(milestone_id: int) -> dict[str, Any] | None:
    if get_record("milestones", milestone_id) is None:
        return None

    tasks = list_tasks_linked_to_milestone(milestone_id)
    total_linked_tasks = len(tasks)
    completed_linked_tasks = sum(1 for task in tasks if not _is_open(task))
    in_progress_linked_tasks = sum(
        1
        for task in tasks
        if str(task.get("status") or "").casefold() == "in_progress"
    )
    queued_linked_tasks = sum(
        1
        for task in tasks
        if str(task.get("status") or "").casefold() == "queued"
    )
    open_linked_tasks = total_linked_tasks - completed_linked_tasks
    suggested_percent = (
        round((completed_linked_tasks / total_linked_tasks) * 100)
        if total_linked_tasks > 0
        else None
    )

    return {
        "milestone_id": milestone_id,
        "total_linked_tasks": total_linked_tasks,
        "completed_linked_tasks": completed_linked_tasks,
        "open_linked_tasks": open_linked_tasks,
        "in_progress_linked_tasks": in_progress_linked_tasks,
        "queued_linked_tasks": queued_linked_tasks,
        "suggested_task_completion_percent": suggested_percent,
        "reason": None
        if total_linked_tasks > 0
        else "No linked tasks yet.",
    }


def list_milestone_progress_advisories() -> list[dict[str, Any]]:
    return [
        advisory
        for milestone in list_records("milestones")
        if (advisory := get_milestone_progress_advisory(int(milestone["id"])))
        is not None
    ]


def _summarize_linked_milestone(milestone: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": milestone.get("id"),
        "title": milestone.get("title"),
        "status": milestone.get("status"),
        "progress_percent": milestone.get("progress_percent"),
        "major_event_id": milestone.get("major_event_id"),
        "major_event_title": milestone.get("major_event_title"),
    }


def _priority_factor(
    factors: list[str],
    label: str,
    points: int,
) -> int:
    if label not in factors:
        factors.append(label)
        return points
    return 0


def _milestone_text_matches(milestone: dict[str, Any], keywords: set[str]) -> bool:
    text = " ".join(
        str(milestone.get(field) or "")
        for field in ["title", "description", "major_event_title"]
    ).casefold()
    return any(keyword in text for keyword in keywords)


def calculate_task_priority(task: dict[str, Any]) -> dict[str, Any]:
    """Explainable Orbit Priority Scoring Engine v1."""
    today = datetime.now(ORBIT_LOCAL_TIMEZONE).date()
    score = 0
    factors: list[str] = []
    milestones = task.get("milestones")
    if milestones is None:
        milestones = list_milestones_linked_to_task(int(task.get("id")))

    if milestones:
        score += _priority_factor(factors, "Milestone linked", 50)

    has_corporate_escape_milestone = any(
        str(milestone.get("major_event_title") or "").casefold()
        == ORBIT_CORPORATE_ESCAPE_TITLE.casefold()
        for milestone in milestones
    )
    if has_corporate_escape_milestone:
        score += _priority_factor(factors, "Corporate Escape", 30)

    has_active_milestone = any(
        str(milestone.get("status") or "").casefold() in {"active", "in_progress"}
        and _is_open(milestone)
        for milestone in milestones
    )
    if has_active_milestone:
        score += _priority_factor(factors, "Active milestone", 20)

    due_date = _parse_date(task.get("due_date"))
    if due_date == today:
        score += _priority_factor(factors, "Due today", 20)
    elif due_date is not None and due_date < today:
        score += _priority_factor(factors, "Overdue", 40)

    status = str(task.get("status") or "").casefold()
    if status == "in_progress":
        score += _priority_factor(factors, "Task in progress", 10)
    elif status == "queued":
        score += _priority_factor(factors, "Task queued", 5)

    if any(
        _milestone_text_matches(milestone, {"trading", "trade", "scanner", "chart"})
        for milestone in milestones
    ):
        score += _priority_factor(factors, "Trading milestone", 15)

    if any(
        _milestone_text_matches(
            milestone,
            {"business", "revenue", "client", "offer", "product", "income"},
        )
        for milestone in milestones
    ):
        score += _priority_factor(factors, "Business milestone", 15)

    return {
        "priority_score": score,
        "factors": factors,
    }


def _priority_sort_key(task: dict[str, Any]) -> tuple[int, date, int]:
    return (
        -int(task.get("priority_score") or 0),
        _parse_date(task.get("due_date")) or date.max,
        int(task.get("id") or 0),
    )


def _with_linked_milestones(task: dict[str, Any]) -> dict[str, Any]:
    full_milestones = list_milestones_linked_to_task(int(task.get("id")))
    priority = calculate_task_priority({**task, "milestones": full_milestones})
    linked_task = {
        **task,
        "milestones": [
            _summarize_linked_milestone(milestone)
            for milestone in full_milestones
        ],
        "priority_score": priority["priority_score"],
        "priority_factors": priority["factors"],
    }
    return linked_task


def _get_major_event_title(major_event_id: Any) -> str | None:
    if major_event_id is None:
        return None

    event = get_record("major_events", int(major_event_id))
    return str(event.get("title")) if event else None


def _latest_milestone_activity_at(milestone_id: int) -> datetime | None:
    history = list_milestone_progress_history(milestone_id)
    if not history:
        return None

    return _parse_datetime(history[0].get("created_at"), assume_naive_utc=True)


def _has_recent_milestone_activity(milestone_id: int) -> bool:
    latest_activity = _latest_milestone_activity_at(milestone_id)
    if latest_activity is None:
        return False

    now = datetime.now(ORBIT_LOCAL_TIMEZONE)
    if latest_activity.tzinfo is None:
        latest_activity = latest_activity.replace(tzinfo=timezone.utc)

    age_days = (now - latest_activity.astimezone(ORBIT_LOCAL_TIMEZONE)).days
    return age_days < STRATEGIC_GAP_RECENT_ACTIVITY_DAYS


def _milestone_priority_sort_key(milestone: dict[str, Any]) -> tuple[int, int]:
    return (
        -int(milestone.get("priority_score") or 0),
        int(milestone.get("milestone_id") or milestone.get("id") or 0),
    )


def calculate_milestone_priority(milestone: dict[str, Any]) -> dict[str, Any]:
    """Explainable Strategic Gap milestone scoring v1."""
    milestone_id = int(milestone.get("id") or milestone.get("milestone_id"))
    status = str(milestone.get("status") or "").casefold()
    progress = int(milestone.get("progress_percent") or 0)
    linked_tasks = milestone.get("linked_tasks")
    if linked_tasks is None:
        linked_tasks = list_tasks_linked_to_milestone(milestone_id)

    open_linked_tasks = [
        task
        for task in linked_tasks
        if _is_open(task)
    ]
    major_event_title = milestone.get("major_event_title") or _get_major_event_title(
        milestone.get("major_event_id"),
    )
    has_recent_activity = milestone.get("has_recent_activity")
    if has_recent_activity is None:
        has_recent_activity = _has_recent_milestone_activity(milestone_id)

    score = 0
    reasons: list[str] = []

    if status == "active":
        score += _priority_factor(reasons, "Active milestone", 50)
    elif status == "in_progress":
        score += _priority_factor(reasons, "In progress milestone", 40)

    if str(major_event_title or "").casefold() == ORBIT_CORPORATE_ESCAPE_TITLE.casefold():
        score += _priority_factor(reasons, "Corporate Escape milestone", 30)

    if progress <= 10:
        score += _priority_factor(
            reasons,
            "Progress remains 0%" if progress == 0 else "Progress <= 10%",
            25,
        )

    if not open_linked_tasks:
        score += _priority_factor(reasons, "No linked open tasks", 30)

    if not linked_tasks:
        score += _priority_factor(reasons, "No linked tasks", 40)

    if has_recent_activity:
        score -= 10
        reasons.append("Recent progress activity")
    else:
        reasons.append("No recent progress activity")

    if status in {"complete", "completed", "done"}:
        score -= 100
        reasons.append("Completed milestone")

    return {
        "priority_score": score,
        "reasons": reasons,
        "linked_task_count": len(linked_tasks),
        "open_linked_task_count": len(open_linked_tasks),
        "has_recent_activity": bool(has_recent_activity),
    }


def _with_milestone_priority(milestone: dict[str, Any]) -> dict[str, Any]:
    major_event_title = _get_major_event_title(milestone.get("major_event_id"))
    linked_tasks = list_tasks_linked_to_milestone(int(milestone["id"]))
    priority = calculate_milestone_priority(
        {
            **milestone,
            "major_event_title": major_event_title,
            "linked_tasks": linked_tasks,
        },
    )
    return {
        **milestone,
        "major_event_title": major_event_title,
        "priority_score": priority["priority_score"],
        "priority_reasons": priority["reasons"],
        "linked_task_count": priority["linked_task_count"],
        "open_linked_task_count": priority["open_linked_task_count"],
        "has_recent_activity": priority["has_recent_activity"],
    }


def _is_strategic_gap(milestone: dict[str, Any]) -> bool:
    status = str(milestone.get("status") or "").casefold()
    progress = int(milestone.get("progress_percent") or 0)
    is_active_status = status in {"active", "in_progress"}
    no_open_linked_tasks = int(milestone.get("open_linked_task_count") or 0) == 0
    no_linked_tasks = int(milestone.get("linked_task_count") or 0) == 0
    no_recent_activity = not bool(milestone.get("has_recent_activity"))

    return (
        (is_active_status and no_open_linked_tasks)
        or (progress <= 10 and no_recent_activity)
        or no_linked_tasks
    )


def _compact_strategic_gap_reasons(reasons: list[str]) -> list[str]:
    preferred = [
        "No linked tasks",
        "Progress remains 0%",
        "Progress <= 10%",
        "No recent progress activity",
        "No linked open tasks",
        "Active milestone",
        "In progress milestone",
    ]
    ordered = [reason for reason in preferred if reason in reasons]
    ordered.extend(reason for reason in reasons if reason not in ordered)
    return ordered


def list_strategic_gaps() -> list[dict[str, Any]]:
    gaps = [
        {
            "milestone_id": milestone.get("id"),
            "title": milestone.get("title"),
            "priority_score": milestone.get("priority_score"),
            "reasons": milestone.get("priority_reasons") or [],
        }
        for milestone in (
            _with_milestone_priority(milestone)
            for milestone in list_records("milestones")
            if str(milestone.get("title") or "") != ORBIT_INBOX_MILESTONE_TITLE
        )
        if _is_strategic_gap(milestone)
        and str(milestone.get("status") or "").casefold()
        not in {"complete", "completed", "done", "cancelled"}
    ]
    return sorted(gaps, key=_milestone_priority_sort_key)


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
    return sorted([
        _with_linked_milestones(task)
        for task in list_records("tasks")
        if task.get("goal_id") == inbox_goal_id
    ], key=_priority_sort_key)


def list_task_priorities() -> list[dict[str, Any]]:
    return [
        {
            "id": task.get("id"),
            "title": task.get("title"),
            "priority_score": task.get("priority_score"),
            "factors": task.get("priority_factors") or [],
        }
        for task in sorted(
            [
                _with_linked_milestones(task)
                for task in list_records("tasks")
                if _is_open(task)
            ],
            key=_priority_sort_key,
        )
    ]


def create_inbox_task(payload: Any) -> dict[str, Any]:
    inbox_goal = get_or_create_inbox_goal()
    data = _model_data(payload)
    task = _create_record(
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
    for milestone_id in data.get("milestone_ids") or []:
        link_task_to_milestone(int(task["id"]), int(milestone_id))

    return _with_linked_milestones(task)


def _get_strategic_gap_milestone(
    recommendation_id: str,
) -> dict[str, Any] | None:
    if not recommendation_id.startswith(STRATEGIC_GAP_RECOMMENDATION_PREFIX):
        return None

    milestone_id_text = recommendation_id.removeprefix(
        STRATEGIC_GAP_RECOMMENDATION_PREFIX,
    )
    try:
        milestone_id = int(milestone_id_text)
    except ValueError:
        return None

    milestone = get_record("milestones", milestone_id)
    if milestone is None:
        return None

    matching_gap = next(
        (
            gap
            for gap in list_strategic_gaps()
            if int(gap.get("milestone_id") or 0) == milestone_id
        ),
        None,
    )
    if matching_gap is None:
        return None

    return milestone


def get_recommendation_task_draft(
    recommendation_id: str,
) -> dict[str, Any] | None:
    milestone = _get_strategic_gap_milestone(recommendation_id)
    if milestone is None:
        return None

    return _model_data(
        RecommendationTaskDraft(
            title=f"Create first review checklist for {milestone.get('title')}",
            description=(
                "Define what should be reviewed after each trading session: setup, "
                "entry, exit, rule adherence, emotion, and lesson learned."
            ),
            milestone_ids=[int(milestone["id"])],
        ),
    )


def create_task_from_recommendation(
    recommendation_id: str,
) -> dict[str, Any] | None:
    draft = get_recommendation_task_draft(recommendation_id)
    if draft is None:
        return None

    return create_inbox_task(
        {
            **draft,
            "status": "queued",
            "due_date": None,
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


def _is_today(value: str | None, today: date) -> bool:
    parsed_date = _parse_date(value)
    return parsed_date == today


def _parse_datetime(value: str | None, assume_naive_utc: bool = False) -> datetime | None:
    if not value:
        return None

    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None

    if parsed.tzinfo is None and assume_naive_utc:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed


def _is_local_day(
    value: str | None,
    local_day: date,
    assume_naive_utc: bool = False,
) -> bool:
    parsed = _parse_datetime(value, assume_naive_utc=assume_naive_utc)
    if parsed is None:
        return False

    if parsed.tzinfo is None:
        return parsed.date() == local_day

    return parsed.astimezone(ORBIT_LOCAL_TIMEZONE).date() == local_day


def _excerpt(value: str | None, limit: int = 150) -> str | None:
    if not value:
        return None

    compact = " ".join(value.split())
    if len(compact) <= limit:
        return compact

    return compact[: limit - 3].rstrip() + "..."


def _format_briefing_text(
    major_event: dict[str, Any] | None,
    readiness: dict[str, Any],
    top_tasks: list[dict[str, Any]],
    strategic_gaps: list[dict[str, Any]],
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

    top_task = top_tasks[0] if top_tasks else None
    top_task_line = (
        f"{top_task.get('title')} (P{top_task.get('priority_score')})"
        + (f" - {top_task.get('milestone_title')}" if top_task.get("milestone_title") else "")
        if top_task
        else "No priority task"
    )
    secondary_lines = [
        f"{index}. {task.get('title')} (P{task.get('priority_score')})"
        + (f" - {task.get('milestone_title')}" if task.get("milestone_title") else "")
        for index, task in enumerate(top_tasks[1:4], start=1)
    ] or ["No secondary tasks"]
    gap_lines: list[str] = []
    for index, gap in enumerate(strategic_gaps[:3], start=1):
        gap_lines.append(
            f"{index}. {gap.get('title')} (P{gap.get('priority_score')})",
        )
        gap_lines.extend(
            f"   - {reason}"
            for reason in _compact_strategic_gap_reasons(gap.get("reasons") or [])[:2]
        )
    if not gap_lines:
        gap_lines = ["No strategic gaps"]
    blocker_lines = current_blockers[:3] or ["No active blockers"]

    return (
        "Morning Briefing\n\n"
        f"{event_line}\n"
        f"Readiness: {readiness.get('overall')}% overall.\n\n"
        "Top Priority Task:\n"
        + top_task_line
        + "\n\nSecondary Tasks:\n"
        + "\n".join(secondary_lines)
        + "\n\nStrategic Gaps:\n"
        + "\n".join(gap_lines)
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
    priority_milestones = []
    for milestone in sorted(
        [
            milestone
            for milestone in event_milestones
            if str(milestone.get("status") or "").casefold()
            in {"active", "in_progress"}
            and _is_open(milestone)
        ],
        key=lambda milestone: (
            int(milestone.get("progress_percent") or 0),
            _parse_date(milestone.get("due_date")) or date.max,
            int(milestone.get("id") or 0),
        ),
    )[:3]:
        summary = _summary(
            milestone,
            ["id", "title", "status", "progress_percent", "due_date"],
        )
        summary["progress_advisory"] = get_milestone_progress_advisory(
            int(milestone["id"]),
        )
        priority_milestones.append(summary)

    linked_milestones_by_task_id = {
        task.get("id"): list_milestones_linked_to_task(int(task.get("id")))
        for task in tasks
    }
    open_tasks = [task for task in tasks if _is_open(task)]

    def _task_with_briefing_milestones(task: dict[str, Any]) -> dict[str, Any]:
        full_milestones = linked_milestones_by_task_id.get(task.get("id"), [])
        linked_milestones = [
            _summarize_linked_milestone(milestone)
            for milestone in full_milestones
        ]
        summary = _summary(task, ["id", "title", "status", "due_date", "goal_id"])
        summary["milestones"] = linked_milestones
        summary["milestone_title"] = (
            linked_milestones[0].get("title") if linked_milestones else None
        )
        priority = calculate_task_priority({**summary, "milestones": full_milestones})
        return {
            **summary,
            "priority_score": priority["priority_score"],
            "priority_factors": priority["factors"],
        }

    top_tasks = sorted(
        [_task_with_briefing_milestones(task) for task in open_tasks],
        key=_priority_sort_key,
    )[:5]
    strategic_gaps = list_strategic_gaps()[:5]

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

    stalled_milestones_with_completed_tasks = [
        milestone
        for milestone in event_milestones
        if _is_open(milestone)
        and str(milestone.get("status") or "").casefold() in {"active", "in_progress"}
        and int(milestone.get("progress_percent") or 0) == 0
        and (
            advisory := get_milestone_progress_advisory(int(milestone["id"]))
        ) is not None
        and int(advisory.get("completed_linked_tasks") or 0) > 0
    ]
    if stalled_milestones_with_completed_tasks:
        current_blockers.append(
            "Milestone has completed linked tasks but progress is still 0%."
        )

    stalled_milestones = [
        milestone
        for milestone in event_milestones
        if _is_open(milestone)
        and str(milestone.get("status") or "").casefold() in {"active", "in_progress"}
        and int(milestone.get("progress_percent") or 0) == 0
        and milestone not in stalled_milestones_with_completed_tasks
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
        strategic_gaps=strategic_gaps,
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
        "strategic_gaps": strategic_gaps,
        "current_blockers": current_blockers,
        "suggested_next_action": suggested_next_action,
        "recent_reviews": recent_reviews,
        "recent_trade_sessions": recent_trade_sessions,
        "briefing_text": briefing_text,
    }


def _format_daily_closeout_text(
    completed_today: list[dict[str, Any]],
    open_tasks: list[dict[str, Any]],
    strategic_gaps: list[dict[str, Any]],
    milestone_progress: list[dict[str, Any]],
    readiness: dict[str, Any],
    trade_summary: dict[str, Any],
    recent_reviews: list[dict[str, Any]],
    recommended_review_prompt: str,
) -> str:
    completed_lines = [
        f"- {task.get('title')}"
        + (f" ({task.get('milestone_title')})" if task.get("milestone_title") else "")
        for task in completed_today[:5]
    ] or ["- No tasks completed today"]
    open_lines = [
        f"- {task.get('title')} (P{task.get('priority_score')})"
        + (f" ({task.get('milestone_title')})" if task.get("milestone_title") else "")
        for task in open_tasks[:5]
    ] or ["- No open tasks remaining"]
    strategic_gap_lines: list[str] = []
    for gap in strategic_gaps[:5]:
        strategic_gap_lines.append(
            f"- {gap.get('title')} (P{gap.get('priority_score')})",
        )
        strategic_gap_lines.extend(
            f"  - {reason}"
            for reason in _compact_strategic_gap_reasons(gap.get("reasons") or [])[:2]
        )
    if not strategic_gap_lines:
        strategic_gap_lines = ["- No strategic gaps"]
    milestone_lines = [
        (
            f"- {milestone.get('milestone_title')}: "
            f"{milestone.get('previous_progress')}% -> {milestone.get('new_progress')}% "
            f"({milestone.get('source')})"
            + (f" — {milestone.get('reason')}" if milestone.get("reason") else "")
        )
        for milestone in milestone_progress[:5]
    ] or ["- No milestone progress changes available"]
    trade_lines = [
        f"- {session.get('symbol')}: PnL {session.get('pnl')}, grade {session.get('session_grade') or 'not graded'}"
        for session in trade_summary.get("sessions", [])[:5]
    ] or ["- No trade sessions logged today"]
    review_lines = [
        f"- {review.get('title') or review.get('review_type')}: {review.get('summary') or 'No summary'}"
        for review in recent_reviews[:3]
    ] or ["- No recent reviews"]

    return (
        "Daily Closeout\n\n"
        f"Readiness: {readiness.get('overall')}% overall.\n\n"
        "Completed today:\n"
        + "\n".join(completed_lines)
        + "\n\nStill open:\n"
        + "\n".join(open_lines)
        + "\n\nStrategic gaps:\n"
        + "\n".join(strategic_gap_lines)
        + "\n\nMilestone progress:\n"
        + "\n".join(milestone_lines)
        + "\n\nTrade sessions:\n"
        + "\n".join(trade_lines)
        + "\n\nRecent reviews:\n"
        + "\n".join(review_lines)
        + f"\n\nReview prompt: {recommended_review_prompt}"
    )


def generate_daily_closeout() -> dict[str, Any]:
    """Build an Orbit closeout. A future Evening Review Agent can call this unchanged."""
    init_orbit_db()

    today = datetime.now(ORBIT_LOCAL_TIMEZONE).date()
    generated_at = datetime.now(timezone.utc).isoformat()

    tasks = list_records("tasks")
    milestones = list_records("milestones")
    reviews = list_records("reviews")
    readiness_categories = get_readiness_categories()
    trade_sessions = list_trade_sessions()

    linked_milestones_by_task_id = {
        task.get("id"): list_milestones_linked_to_task(int(task.get("id")))
        for task in tasks
    }

    def task_summary(task: dict[str, Any]) -> dict[str, Any]:
        full_milestones = linked_milestones_by_task_id.get(task.get("id"), [])
        linked_milestones = [
            _summarize_linked_milestone(milestone)
            for milestone in full_milestones
        ]
        summary = _summary(
            task,
            ["id", "title", "description", "status", "due_date", "completed_at", "goal_id"],
        )
        summary["milestones"] = linked_milestones
        summary["milestone_title"] = (
            linked_milestones[0].get("title") if linked_milestones else None
        )
        priority = calculate_task_priority({**summary, "milestones": full_milestones})
        return {
            **summary,
            "priority_score": priority["priority_score"],
            "priority_factors": priority["factors"],
        }

    completed_today = [
        task_summary(task)
        for task in tasks
        if not _is_open(task) and _is_today(task.get("completed_at"), today)
    ]
    open_tasks = sorted(
        [task_summary(task) for task in tasks if _is_open(task)],
        key=_priority_sort_key,
    )
    strategic_gaps = list_strategic_gaps()[:5]

    milestone_progress = [
        _summary(
            history,
            [
                "id",
                "milestone_id",
                "milestone_title",
                "previous_progress",
                "new_progress",
                "change_amount",
                "source",
                "reason",
                "created_at",
            ],
        )
        for history in list_recent_milestone_progress_history(limit=50)
        if _is_local_day(history.get("created_at"), today, assume_naive_utc=True)
    ]

    readiness_overall = (
        round(
            sum(int(category.get("current_score") or 0) for category in readiness_categories)
            / len(readiness_categories)
        )
        if readiness_categories
        else 0
    )
    readiness = {
        "overall": readiness_overall,
        "categories": [
            _summary(
                category,
                ["id", "category_name", "current_score", "target_score", "notes", "last_updated"],
            )
            for category in readiness_categories
        ],
    }

    todays_trade_sessions = [
        session
        for session in trade_sessions
        if _is_today(session.get("session_date"), today)
    ]
    pnl_total = sum(float(session.get("pnl") or 0) for session in todays_trade_sessions)
    trade_summary = {
        "sessions_logged_today": len(todays_trade_sessions),
        "total_pnl": pnl_total,
        "average_rule_adherence": (
            round(
                sum(int(session.get("rule_adherence") or 0) for session in todays_trade_sessions)
                / len([session for session in todays_trade_sessions if session.get("rule_adherence") is not None])
            )
            if any(session.get("rule_adherence") is not None for session in todays_trade_sessions)
            else None
        ),
        "sessions": [
            _summary(
                session,
                [
                    "id",
                    "session_date",
                    "symbol",
                    "pnl",
                    "notes",
                    "rule_adherence",
                    "confidence",
                    "session_grade",
                    "created_at",
                ],
            )
            for session in todays_trade_sessions
        ],
    }

    recent_reviews = [
        {
            **_summary(
                review,
                ["id", "title", "review_type", "rating", "created_at"],
            ),
            "summary": _excerpt(review.get("summary")),
        }
        for review in _latest_records(reviews, 3)
    ]
    recommended_review_prompt = (
        "What did today complete, what still needs tomorrow's attention, "
        "and what should Helix watch for in the next morning briefing?"
    )
    closeout_text = _format_daily_closeout_text(
        completed_today=completed_today,
        open_tasks=open_tasks,
        strategic_gaps=strategic_gaps,
        milestone_progress=milestone_progress,
        readiness=readiness,
        trade_summary=trade_summary,
        recent_reviews=recent_reviews,
        recommended_review_prompt=recommended_review_prompt,
    )

    return {
        "success": True,
        "generated_at": generated_at,
        "completed_today": completed_today,
        "open_tasks": open_tasks,
        "strategic_gaps": strategic_gaps,
        "milestone_progress": milestone_progress,
        "readiness": readiness,
        "trade_summary": trade_summary,
        "recommended_review_prompt": recommended_review_prompt,
        "closeout_text": closeout_text,
    }


def create_daily_closeout_review(payload: Any) -> dict[str, Any]:
    closeout = generate_daily_closeout()
    data = _model_data(payload)
    user_summary = (data.get("summary") or "").strip()
    summary = closeout["closeout_text"]
    if user_summary:
        summary = f"{summary}\n\nUser notes: {user_summary}"

    return create_review({
        "title": f"Daily Closeout - {datetime.now().date().isoformat()}",
        "review_type": "daily_closeout",
        "summary": summary,
        "rating": data.get("rating"),
    })
