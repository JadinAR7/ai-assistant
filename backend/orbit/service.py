from collections.abc import Mapping
from datetime import date, datetime
from typing import Any

from .database import get_connection, init_orbit_db
from .models import (
    GoalCreate,
    GoalUpdate,
    MajorEventCreate,
    MajorEventUpdate,
    MilestoneCreate,
    MilestoneUpdate,
    TaskCreate,
    TaskUpdate,
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
}


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

