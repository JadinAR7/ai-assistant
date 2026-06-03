from collections.abc import Mapping
from datetime import date, datetime, timedelta, timezone
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
    ScheduleBlockCreate,
    ScheduleBlockUpdate,
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
    "schedule_blocks": [
        "title",
        "block_type",
        "category",
        "day_of_week",
        "specific_date",
        "start_time",
        "end_time",
        "duration_minutes",
        "recurrence",
        "priority",
        "notes",
        "active",
    ],
}


ORBIT_CORPORATE_ESCAPE_TITLE = "Corporate Escape"
ORBIT_INBOX_MILESTONE_TITLE = "Inbox / General"
ORBIT_INBOX_GOAL_TITLE = "Inbox"
MILESTONE_PROGRESS_SOURCES = {"manual", "task_advisory", "helix_tool", "system"}
ORBIT_LOCAL_TIMEZONE = ZoneInfo("America/Denver")
STRATEGIC_GAP_RECENT_ACTIVITY_DAYS = 7
MAJOR_EVENT_ACTIVITY_DAYS = 7
STRATEGIC_GAP_RECOMMENDATION_PREFIX = "strategic-gap-"
SCHEDULE_PLANNING_DAY_START_MINUTE = 8 * 60
SCHEDULE_PLANNING_DAY_END_MINUTE = 22 * 60
SCHEDULE_DAY_ORDER = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]


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


def _validate_schedule_block_data(data: dict[str, Any]) -> None:
    block_type = data.get("block_type")
    duration_minutes = data.get("duration_minutes")
    specific_date = data.get("specific_date")

    if specific_date not in (None, ""):
        try:
            date.fromisoformat(str(specific_date))
        except ValueError as exc:
            raise ValueError("specific_date must use YYYY-MM-DD format.") from exc

    if block_type == "fixed":
        has_schedule_anchor = data.get("day_of_week") not in (None, "") or specific_date not in (None, "")
        missing_time = data.get("start_time") in (None, "") or data.get("end_time") in (None, "")
        if not has_schedule_anchor or missing_time:
            raise ValueError(
                "Fixed schedule blocks require day_of_week or specific_date, plus start_time and end_time."
            )

    if block_type == "flexible" and data.get("duration_minutes") is None:
        raise ValueError("Flexible schedule blocks require duration_minutes.")

    if duration_minutes is not None and int(duration_minutes) > 480:
        raise ValueError("Schedule block duration cannot exceed 480 minutes.")


def _normalize_schedule_block_data(data: dict[str, Any]) -> dict[str, Any]:
    if "title" in data and data.get("title") is None:
        return {**data, "title": ""}
    return data


def _list_records_ordered(table: str, order_by: str) -> list[dict[str, Any]]:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM {table} ORDER BY {order_by}")
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def create_major_event(payload: MajorEventCreate) -> dict[str, Any]:
    return _with_calculated_major_event_progress(
        _create_record("major_events", _model_data(payload)),
    )


def list_major_events() -> list[dict[str, Any]]:
    records = _list_records_ordered(
        "major_events",
        """
        CASE status
            WHEN 'active' THEN 1
            WHEN 'paused' THEN 2
            WHEN 'completed' THEN 3
            WHEN 'archived' THEN 4
            ELSE 5
        END,
        id
        """,
    )
    return [_with_calculated_major_event_progress(record) for record in records]


def get_major_event(record_id: int) -> dict[str, Any] | None:
    record = get_record("major_events", record_id)
    if record is None:
        return None
    return _with_calculated_major_event_progress(record)


def update_major_event(record_id: int, payload: MajorEventUpdate) -> dict[str, Any] | None:
    record = _update_record("major_events", record_id, _model_data(payload, exclude_unset=True))
    if record is None:
        return None
    return _with_calculated_major_event_progress(record)


def archive_major_event(record_id: int) -> dict[str, Any] | None:
    payload = MajorEventUpdate(status="archived")
    return update_major_event(record_id, payload)


def calculate_major_event_progress(major_event_id: int) -> int:
    init_orbit_db()

    cutoff = datetime.now(ORBIT_LOCAL_TIMEZONE).date()
    cutoff = cutoff.fromordinal(cutoff.toordinal() - MAJOR_EVENT_ACTIVITY_DAYS)

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id, progress_percent FROM milestones WHERE major_event_id = ?",
        (major_event_id,),
    )
    milestones = [dict(row) for row in cursor.fetchall()]
    milestone_ids = [int(milestone["id"]) for milestone in milestones]

    cursor.execute(
        "SELECT current_score FROM readiness_categories WHERE major_event_id = ?",
        (major_event_id,),
    )
    readiness = [dict(row) for row in cursor.fetchall()]

    milestone_average = (
        sum(int(milestone.get("progress_percent") or 0) for milestone in milestones)
        / len(milestones)
        if milestones
        else 0
    )
    readiness_average = (
        sum(int(category.get("current_score") or 0) for category in readiness)
        / len(readiness)
        if readiness
        else 0
    )

    recent_activity_exists = False
    if milestone_ids:
        milestone_placeholders = ", ".join("?" for _ in milestone_ids)
        cursor.execute(
            f"""
            SELECT tasks.completed_at
            FROM tasks
            JOIN task_milestone_links ON task_milestone_links.task_id = tasks.id
            WHERE task_milestone_links.milestone_id IN ({milestone_placeholders})
                AND tasks.completed_at IS NOT NULL
            """,
            milestone_ids,
        )
        recent_activity_exists = any(
            _date_is_on_or_after(row["completed_at"], cutoff)
            for row in cursor.fetchall()
        )

        if not recent_activity_exists:
            cursor.execute(
                f"""
                SELECT milestone_progress_history.created_at
                FROM milestone_progress_history
                WHERE milestone_id IN ({milestone_placeholders})
                """,
                milestone_ids,
            )
            recent_activity_exists = any(
                _date_is_on_or_after(row["created_at"], cutoff)
                for row in cursor.fetchall()
            )

    has_event_evidence = bool(milestones or readiness)
    if has_event_evidence and not recent_activity_exists:
        cursor.execute("SELECT created_at FROM reviews")
        recent_activity_exists = any(
            _date_is_on_or_after(row["created_at"], cutoff)
            for row in cursor.fetchall()
        )

    if has_event_evidence and not recent_activity_exists:
        cursor.execute("SELECT session_date FROM trade_sessions")
        recent_activity_exists = any(
            _date_is_on_or_after(row["session_date"], cutoff)
            for row in cursor.fetchall()
        )

    conn.close()

    activity_score = 100 if recent_activity_exists else 0
    return round(
        (milestone_average * 0.5)
        + (readiness_average * 0.4)
        + (activity_score * 0.1),
    )


def _with_calculated_major_event_progress(record: dict[str, Any]) -> dict[str, Any]:
    return {
        **record,
        "calculated_progress_percent": calculate_major_event_progress(int(record["id"])),
    }


def _date_is_on_or_after(value: str | None, cutoff: date) -> bool:
    parsed = _parse_date(value)
    return parsed is not None and parsed >= cutoff


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


def list_schedule_blocks() -> list[dict[str, Any]]:
    return _list_records_ordered(
        "schedule_blocks",
        """
        active DESC,
        CASE day_of_week
            WHEN 'monday' THEN 1
            WHEN 'tuesday' THEN 2
            WHEN 'wednesday' THEN 3
            WHEN 'thursday' THEN 4
            WHEN 'friday' THEN 5
            WHEN 'saturday' THEN 6
            WHEN 'sunday' THEN 7
            ELSE 8
        END,
        category,
        start_time,
        id
        """,
    )


def create_schedule_block(payload: ScheduleBlockCreate) -> dict[str, Any]:
    data = _normalize_schedule_block_data(_model_data(payload))
    _validate_schedule_block_data(data)
    return _create_record("schedule_blocks", data)


def update_schedule_block(
    record_id: int,
    payload: ScheduleBlockUpdate,
) -> dict[str, Any] | None:
    existing = get_record("schedule_blocks", record_id)
    if existing is None:
        return None

    data = _normalize_schedule_block_data(_model_data(payload, exclude_unset=True))
    merged = {**existing, **data}
    _validate_schedule_block_data(merged)
    return _update_record("schedule_blocks", record_id, data)


def get_schedule_intelligence() -> dict[str, Any]:
    today = datetime.now(ORBIT_LOCAL_TIMEZONE).date()
    week_start = today - timedelta(days=today.weekday())
    week_dates = [week_start + timedelta(days=index) for index in range(7)]
    active_blocks = [
        block for block in list_schedule_blocks() if _truthy(block.get("active"))
    ]
    fixed_instances = _schedule_fixed_instances(active_blocks, week_dates)
    flexible_blocks = [
        block
        for block in active_blocks
        if str(block.get("block_type") or "").casefold() == "flexible"
    ]
    flexible_blocks_by_date = _schedule_flexible_blocks_by_date(
        flexible_blocks,
        week_dates,
    )
    unplaced_flexible_blocks = [
        block
        for block in flexible_blocks
        if not block.get("day_of_week") and not block.get("specific_date")
    ]
    high_priority_due_by_date = _schedule_high_priority_due_counts(week_dates)

    day_summaries: list[dict[str, Any]] = []
    available_windows: list[dict[str, Any]] = []
    for index, current_date in enumerate(week_dates):
        day = SCHEDULE_DAY_ORDER[index]
        day_fixed_instances = fixed_instances.get(current_date.isoformat(), [])
        scheduled_minutes = sum(
            instance["duration_minutes"] for instance in day_fixed_instances
        )
        flexible_count = len(flexible_blocks_by_date.get(current_date.isoformat(), []))
        high_priority_commitments = (
            sum(
                1
                for instance in day_fixed_instances
                if str(instance["block"].get("priority") or "").casefold() == "high"
            )
            + high_priority_due_by_date.get(current_date.isoformat(), 0)
        )
        remaining_minutes = max(
            SCHEDULE_PLANNING_DAY_END_MINUTE
            - SCHEDULE_PLANNING_DAY_START_MINUTE
            - scheduled_minutes,
            0,
        )
        summary = {
            "day": day,
            "date": current_date.isoformat(),
            "total_scheduled_minutes": scheduled_minutes,
            "total_scheduled_hours": round(scheduled_minutes / 60, 1),
            "remaining_available_minutes": remaining_minutes,
            "remaining_available_hours": round(remaining_minutes / 60, 1),
            "high_priority_commitments": high_priority_commitments,
            "flexible_blocks": flexible_count,
            "status": _schedule_day_status(scheduled_minutes),
        }
        day_summaries.append(summary)
        available_windows.extend(
            _schedule_available_windows_for_day(
                day=day,
                current_date=current_date,
                fixed_instances=day_fixed_instances,
            )
        )

    overloaded_days = [
        summary for summary in day_summaries if summary["status"] == "overloaded"
    ]
    underutilized_days = [
        summary for summary in day_summaries if summary["total_scheduled_minutes"] < 120
    ]
    most_available_day = max(
        day_summaries,
        key=lambda summary: (
            summary["remaining_available_minutes"],
            -summary["total_scheduled_minutes"],
        ),
        default=None,
    )
    most_overloaded_day = max(
        day_summaries,
        key=lambda summary: (
            summary["total_scheduled_minutes"],
            summary["high_priority_commitments"],
        ),
        default=None,
    )
    recommendations = _schedule_recommendations(
        available_windows=available_windows,
        overloaded_days=overloaded_days,
        flexible_blocks=flexible_blocks,
        unplaced_flexible_blocks=unplaced_flexible_blocks,
    )

    return {
        "week_start": week_start.isoformat(),
        "week_end": week_dates[-1].isoformat(),
        "day_summaries": day_summaries,
        "overloaded_days": overloaded_days,
        "underutilized_days": underutilized_days,
        "available_windows": available_windows,
        "recommendations": recommendations,
        "most_available_day": most_available_day,
        "most_overloaded_day": most_overloaded_day,
        "recommended_placement": recommendations[0] if recommendations else None,
        "unplaced_flexible_blocks": len(unplaced_flexible_blocks),
    }


def _truthy(value: Any) -> bool:
    return value in (True, 1, "1", "true", "True")


def _schedule_fixed_instances(
    blocks: list[dict[str, Any]],
    week_dates: list[date],
) -> dict[str, list[dict[str, Any]]]:
    instances = {current_date.isoformat(): [] for current_date in week_dates}
    day_by_date = {
        current_date.isoformat(): SCHEDULE_DAY_ORDER[index]
        for index, current_date in enumerate(week_dates)
    }

    for block in blocks:
        if str(block.get("block_type") or "").casefold() != "fixed":
            continue
        start_minute = _schedule_time_to_minutes(block.get("start_time"))
        end_minute = _schedule_time_to_minutes(block.get("end_time"))
        if start_minute is None or end_minute is None or end_minute <= start_minute:
            continue

        specific_date = str(block.get("specific_date") or "")
        if specific_date in instances:
            target_dates = [specific_date]
        else:
            block_day = str(block.get("day_of_week") or "").casefold()
            target_dates = [
                current_date
                for current_date, day in day_by_date.items()
                if day == block_day
            ]

        for target_date in target_dates:
            instances[target_date].append(
                {
                    "block": block,
                    "start_minute": start_minute,
                    "end_minute": end_minute,
                    "duration_minutes": end_minute - start_minute,
                }
            )

    for date_key, date_instances in instances.items():
        instances[date_key] = sorted(
            date_instances,
            key=lambda instance: (
                instance["start_minute"],
                str(instance["block"].get("title") or ""),
            ),
        )
    return instances


def _schedule_flexible_blocks_by_date(
    blocks: list[dict[str, Any]],
    week_dates: list[date],
) -> dict[str, list[dict[str, Any]]]:
    blocks_by_date = {current_date.isoformat(): [] for current_date in week_dates}
    day_by_date = {
        current_date.isoformat(): SCHEDULE_DAY_ORDER[index]
        for index, current_date in enumerate(week_dates)
    }

    for block in blocks:
        specific_date = str(block.get("specific_date") or "")
        if specific_date in blocks_by_date:
            blocks_by_date[specific_date].append(block)
            continue

        block_day = str(block.get("day_of_week") or "").casefold()
        for date_key, day in day_by_date.items():
            if day == block_day:
                blocks_by_date[date_key].append(block)
                break

    return blocks_by_date


def _schedule_high_priority_due_counts(week_dates: list[date]) -> dict[str, int]:
    counts = {current_date.isoformat(): 0 for current_date in week_dates}
    for task in list_records("tasks"):
        due_date = _parse_date(task.get("due_date"))
        if due_date is None or due_date.isoformat() not in counts or not _is_open(task):
            continue
        priority = calculate_task_priority(_with_linked_milestones(task))
        if int(priority.get("priority_score") or 0) >= 70:
            counts[due_date.isoformat()] += 1

    for milestone in list_records("milestones"):
        due_date = _parse_date(milestone.get("due_date"))
        if (
            due_date is not None
            and due_date.isoformat() in counts
            and _is_open(milestone)
            and str(milestone.get("status") or "").casefold() in {"active", "in_progress"}
        ):
            counts[due_date.isoformat()] += 1

    return counts


def _schedule_day_status(scheduled_minutes: int) -> str:
    if scheduled_minutes >= 8 * 60:
        return "overloaded"
    if scheduled_minutes >= 4 * 60:
        return "busy"
    return "healthy"


def _schedule_available_windows_for_day(
    day: str,
    current_date: date,
    fixed_instances: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    windows: list[dict[str, Any]] = []
    cursor = SCHEDULE_PLANNING_DAY_START_MINUTE
    clipped_instances = [
        {
            **instance,
            "start_minute": max(instance["start_minute"], SCHEDULE_PLANNING_DAY_START_MINUTE),
            "end_minute": min(instance["end_minute"], SCHEDULE_PLANNING_DAY_END_MINUTE),
        }
        for instance in fixed_instances
        if instance["end_minute"] > SCHEDULE_PLANNING_DAY_START_MINUTE
        and instance["start_minute"] < SCHEDULE_PLANNING_DAY_END_MINUTE
    ]

    for instance in clipped_instances:
        if instance["start_minute"] > cursor:
            windows.append(
                _schedule_window(
                    day=day,
                    current_date=current_date,
                    start_minute=cursor,
                    end_minute=instance["start_minute"],
                    before_block=instance["block"],
                )
            )
        cursor = max(cursor, instance["end_minute"])

    if cursor < SCHEDULE_PLANNING_DAY_END_MINUTE:
        windows.append(
            _schedule_window(
                day=day,
                current_date=current_date,
                start_minute=cursor,
                end_minute=SCHEDULE_PLANNING_DAY_END_MINUTE,
                after_block=clipped_instances[-1]["block"] if clipped_instances else None,
            )
        )

    return [window for window in windows if window["duration_minutes"] >= 30]


def _schedule_window(
    day: str,
    current_date: date,
    start_minute: int,
    end_minute: int,
    after_block: dict[str, Any] | None = None,
    before_block: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "day": day,
        "date": current_date.isoformat(),
        "start_time": _schedule_minutes_to_time(start_minute),
        "end_time": _schedule_minutes_to_time(end_minute),
        "duration_minutes": end_minute - start_minute,
        "after_block_title": _schedule_block_title(after_block) if after_block else None,
        "before_block_title": _schedule_block_title(before_block) if before_block else None,
    }


def _schedule_recommendations(
    available_windows: list[dict[str, Any]],
    overloaded_days: list[dict[str, Any]],
    flexible_blocks: list[dict[str, Any]],
    unplaced_flexible_blocks: list[dict[str, Any]],
) -> list[str]:
    recommendations: list[str] = []
    top_windows = sorted(
        available_windows,
        key=lambda window: window["duration_minutes"],
        reverse=True,
    )

    if top_windows:
        window = top_windows[0]
        anchor = (
            f" after {window['after_block_title']}"
            if window.get("after_block_title")
            else ""
        )
        recommendations.append(
            f"{_schedule_day_label(window['day'])} has a "
            f"{_schedule_duration_text(window['duration_minutes'])} opening{anchor}."
        )

    candidate_blocks = sorted(
        unplaced_flexible_blocks,
        key=lambda block: (
            -_schedule_priority_rank(block.get("priority")),
            str(block.get("title") or block.get("category") or ""),
        ),
    )
    if candidate_blocks and top_windows:
        block = candidate_blocks[0]
        fitting_window = next(
            (
                window
                for window in top_windows
                if window["duration_minutes"] >= int(block.get("duration_minutes") or 0)
            ),
            top_windows[0],
        )
        recommendations.append(
            f"{_schedule_block_title(block)} could fit on "
            f"{_schedule_day_label(fitting_window['day'])} "
            f"{_schedule_time_of_day_label(fitting_window['start_time'])}."
        )

    for summary in overloaded_days[:2]:
        movable = next(
            (
                block
                for block in flexible_blocks
                if str(block.get("day_of_week") or "").casefold() == summary["day"]
                or str(block.get("specific_date") or "") == summary["date"]
            ),
            None,
        )
        suffix = (
            f" Consider moving {_schedule_block_title(movable)}."
            if movable is not None
            else " Consider moving a flexible block."
        )
        recommendations.append(
            f"{_schedule_day_label(summary['day'])} appears overloaded.{suffix}"
        )

    return recommendations[:5]


def _schedule_time_to_minutes(value: Any) -> int | None:
    if not value:
        return None
    parts = str(value).split(":")
    if len(parts) < 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        return None
    return hour * 60 + minute


def _schedule_minutes_to_time(minutes: int) -> str:
    hour = minutes // 60
    minute = minutes % 60
    return f"{hour:02d}:{minute:02d}"


def _schedule_day_label(day: Any) -> str:
    text = str(day or "")
    return text[:1].upper() + text[1:]


def _schedule_block_title(block: dict[str, Any] | None) -> str:
    if not block:
        return "Flexible block"
    return str(block.get("title") or block.get("category") or "Flexible block").strip()


def _schedule_duration_text(minutes: int) -> str:
    if minutes < 60:
        return f"{minutes}-minute"
    hours = minutes / 60
    return f"{hours:g}-hour"


def _schedule_time_of_day_label(value: str) -> str:
    minutes = _schedule_time_to_minutes(value)
    if minutes is None:
        return "window"
    if minutes >= 17 * 60:
        return "evening"
    if minutes >= 12 * 60:
        return "afternoon"
    return "morning"


def _schedule_priority_rank(priority: Any) -> int:
    return {"high": 3, "medium": 2, "low": 1}.get(str(priority or "").casefold(), 0)


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


def _lowest_readiness_category(readiness: dict[str, Any]) -> dict[str, Any] | None:
    categories = readiness.get("categories") or []
    if not categories:
        return None

    return sorted(
        categories,
        key=lambda category: (
            int(category.get("current_score") or 0),
            int(category.get("id") or 0),
        ),
    )[0]


def _recommendation_sort_key(recommendation: dict[str, Any]) -> tuple[int, str]:
    return (
        -int(recommendation.get("score") or 0),
        str(recommendation.get("id") or ""),
    )


def _dedupe_recommendations(
    recommendations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for recommendation in sorted(recommendations, key=_recommendation_sort_key):
        text = str(recommendation.get("recommendation") or "").casefold()
        category = str(recommendation.get("category") or "")
        key = f"{category}:{text}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(recommendation)
    return deduped


def generate_recommendations(
    top_priority_tasks: list[dict[str, Any]] | None = None,
    strategic_gaps: list[dict[str, Any]] | None = None,
    blockers: list[str] | None = None,
    milestone_progress_history: list[dict[str, Any]] | None = None,
    readiness: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Rank read-only Orbit recommendations from existing operating signals."""
    init_orbit_db()

    generated_at = datetime.now(timezone.utc).isoformat()
    if top_priority_tasks is None:
        top_priority_tasks = [
            _with_linked_milestones(task)
            for task in list_records("tasks")
            if _is_open(task)
        ]
        top_priority_tasks = sorted(top_priority_tasks, key=_priority_sort_key)[:5]
    if strategic_gaps is None:
        strategic_gaps = list_strategic_gaps()[:5]
    if blockers is None:
        blockers = []
    if milestone_progress_history is None:
        milestone_progress_history = list_recent_milestone_progress_history(limit=20)
    if readiness is None:
        readiness_categories = get_readiness_categories()
        readiness = {
            "overall": (
                round(
                    sum(
                        int(category.get("current_score") or 0)
                        for category in readiness_categories
                    )
                    / len(readiness_categories)
                )
                if readiness_categories
                else 0
            ),
            "categories": [
                _summary(
                    category,
                    ["id", "category_name", "current_score", "target_score", "notes"],
                )
                for category in readiness_categories
            ],
        }

    recommendations: list[dict[str, Any]] = []
    rationale: list[str] = []

    if top_priority_tasks:
        task = top_priority_tasks[0]
        score = 50 + int(task.get("priority_score") or 0)
        title = str(task.get("title") or "highest priority task")
        recommendations.append(
            {
                "id": f"task-{task.get('id')}",
                "category": "task_execution",
                "recommendation": f"Complete or advance {title}.",
                "score": score,
                "rationale": [
                    f"Highest ranked open task with priority score {task.get('priority_score') or 0}.",
                    *[
                        str(factor)
                        for factor in (task.get("priority_factors") or [])[:3]
                    ],
                ],
            },
        )
        rationale.append(f"Top task recommendation is based on {title}.")

    for gap in strategic_gaps[:3]:
        reasons = gap.get("reasons") or []
        compact_reasons = _compact_strategic_gap_reasons(reasons)
        score = 45 + int(gap.get("priority_score") or 0)
        title = str(gap.get("title") or "strategic gap")
        if "No linked tasks" in reasons:
            recommendation_text = f"Create first task supporting {title}."
            score += 25
        elif "No linked open tasks" in reasons:
            recommendation_text = f"Queue a next open task for {title}."
            score += 15
        elif "Progress remains 0%" in reasons or "Progress <= 10%" in reasons:
            recommendation_text = f"Resolve milestone stuck at 0%: {title}."
            score += 10
        else:
            recommendation_text = f"Close strategic gap: {title}."
        recommendations.append(
            {
                "id": f"strategic-gap-{gap.get('milestone_id')}",
                "category": "strategic_gap",
                "recommendation": recommendation_text,
                "score": score,
                "rationale": [
                    f"Strategic gap priority score {gap.get('priority_score') or 0}.",
                    *compact_reasons[:3],
                ],
            },
        )
    if strategic_gaps:
        rationale.append("Strategic gap recommendations favor active milestones with low progress or missing linked work.")

    for index, blocker in enumerate(blockers[:3], start=1):
        text = str(blocker)
        score = 80 - (index - 1) * 5
        if "overdue" in text.casefold():
            score += 15
        if "0%" in text:
            score += 10
        recommendations.append(
            {
                "id": f"blocker-{index}",
                "category": "blocker_resolution",
                "recommendation": f"Clear blocker: {text}",
                "score": score,
                "rationale": ["Current blocker from Orbit briefing signals."],
            },
        )
    if blockers:
        rationale.append("Blocker recommendations prioritize overdue, stalled, and low-readiness friction.")

    lowest_readiness = _lowest_readiness_category(readiness)
    if lowest_readiness is not None:
        current_score = int(lowest_readiness.get("current_score") or 0)
        target_score = int(lowest_readiness.get("target_score") or 100)
        gap_to_target = max(target_score - current_score, 0)
        if gap_to_target > 0:
            category_name = str(lowest_readiness.get("category_name") or "readiness")
            notes = _excerpt(lowest_readiness.get("notes"), 90)
            recommendations.append(
                {
                    "id": f"readiness-{lowest_readiness.get('id')}",
                    "category": "readiness_improvement",
                    "recommendation": f"Improve {category_name} readiness.",
                    "score": 40 + gap_to_target,
                    "rationale": [
                        f"Lowest readiness category at {current_score}% toward target {target_score}%.",
                        *([notes] if notes else []),
                    ],
                },
            )
            rationale.append(f"Readiness recommendation targets the lowest category: {category_name}.")

    progress_history_count = len(milestone_progress_history or [])
    rationale.append(
        f"Reviewed {len(top_priority_tasks or [])} priority task(s), "
        f"{len(strategic_gaps or [])} strategic gap(s), "
        f"{len(blockers or [])} blocker(s), and "
        f"{progress_history_count} progress event(s)."
    )

    return {
        "success": True,
        "generated_at": generated_at,
        "recommendations": _dedupe_recommendations(recommendations),
        "rationale": rationale,
    }


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
    recommendations: list[dict[str, Any]],
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
    recommendation_lines = [
        f"{index}. {recommendation.get('recommendation')}"
        for index, recommendation in enumerate(recommendations[:3], start=1)
    ] or ["No recommendations yet"]

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
        + "\n\nRecommended Actions:\n"
        + "\n".join(recommendation_lines)
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

    recommendations_output = generate_recommendations(
        top_priority_tasks=top_tasks,
        strategic_gaps=strategic_gaps,
        blockers=current_blockers,
        milestone_progress_history=list_recent_milestone_progress_history(limit=20),
        readiness=readiness,
    )
    recommendations = recommendations_output.get("recommendations") or []
    if recommendations:
        suggested_next_action = str(recommendations[0].get("recommendation"))
    elif top_tasks:
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
        recommendations=recommendations,
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
        "recommendations": recommendations,
        "recommendation_rationale": recommendations_output.get("rationale") or [],
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
    tomorrow_focus: list[dict[str, Any]],
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
    tomorrow_focus_lines = [
        f"{index}. {recommendation.get('recommendation')}"
        for index, recommendation in enumerate(tomorrow_focus[:3], start=1)
    ] or ["No tomorrow focus yet"]

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
        + "\n\nTomorrow Focus:\n"
        + "\n".join(tomorrow_focus_lines)
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
    recommendations_output = generate_recommendations(
        top_priority_tasks=open_tasks[:5],
        strategic_gaps=strategic_gaps,
        blockers=[],
        milestone_progress_history=list_recent_milestone_progress_history(limit=20),
        readiness=readiness,
    )
    tomorrow_focus = (recommendations_output.get("recommendations") or [])[:3]
    closeout_text = _format_daily_closeout_text(
        completed_today=completed_today,
        open_tasks=open_tasks,
        strategic_gaps=strategic_gaps,
        milestone_progress=milestone_progress,
        readiness=readiness,
        trade_summary=trade_summary,
        recent_reviews=recent_reviews,
        tomorrow_focus=tomorrow_focus,
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
        "tomorrow_focus": tomorrow_focus,
        "recommendations": recommendations_output.get("recommendations") or [],
        "recommendation_rationale": recommendations_output.get("rationale") or [],
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
