"""Seed initial Orbit data.

Run from the repository root with:
    python3 backend/orbit/seed.py

Or run from the backend directory with:
    python3 -m orbit.seed
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from orbit.database import get_connection, init_orbit_db
else:
    from .database import get_connection, init_orbit_db


EVENT_TITLE = "Corporate Escape"
EVENT_DATA = {
    "title": EVENT_TITLE,
    "description": (
        "Leave corporate employment and replace income through trading, "
        "business, and other ventures."
    ),
    "target_date": "2027-02-28",
    "status": "active",
    "progress_percent": 18,
}

MILESTONES = [
    {
        "title": "Define income replacement target",
        "description": "Finalize monthly runway and baseline expense number.",
        "status": "in_progress",
    },
    {
        "title": "Build trading review cadence",
        "description": "Weekly performance review and rule adherence score.",
        "status": "active",
    },
    {
        "title": "Create business launch plan",
        "description": "Outline first offer, audience, and launch steps.",
        "status": "queued",
    },
    {
        "title": "Set capital accumulation checkpoints",
        "description": "Track funding, reserves, and minimum safety buffer.",
        "status": "queued",
    },
]


def _get_major_event_id(cursor: Any, title: str) -> int | None:
    cursor.execute("SELECT id FROM major_events WHERE title = ? ORDER BY id LIMIT 1", (title,))
    row = cursor.fetchone()
    if row is None:
        return None
    return int(row["id"])


def _seed_major_event(cursor: Any) -> int:
    event_id = _get_major_event_id(cursor, EVENT_TITLE)
    if event_id is None:
        cursor.execute(
            """
            INSERT INTO major_events (
                title,
                description,
                target_date,
                status,
                progress_percent
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                EVENT_DATA["title"],
                EVENT_DATA["description"],
                EVENT_DATA["target_date"],
                EVENT_DATA["status"],
                EVENT_DATA["progress_percent"],
            ),
        )
        return int(cursor.lastrowid)

    cursor.execute(
        """
        UPDATE major_events
        SET
            description = ?,
            target_date = ?,
            status = ?,
            progress_percent = ?
        WHERE id = ?
        """,
        (
            EVENT_DATA["description"],
            EVENT_DATA["target_date"],
            EVENT_DATA["status"],
            EVENT_DATA["progress_percent"],
            event_id,
        ),
    )
    return event_id


def _seed_milestones(cursor: Any, event_id: int) -> None:
    for milestone in MILESTONES:
        cursor.execute(
            """
            SELECT id
            FROM milestones
            WHERE major_event_id = ? AND title = ?
            ORDER BY id
            LIMIT 1
            """,
            (event_id, milestone["title"]),
        )
        row = cursor.fetchone()

        if row is None:
            cursor.execute(
                """
                INSERT INTO milestones (
                    major_event_id,
                    title,
                    description,
                    status,
                    progress_percent
                )
                VALUES (?, ?, ?, ?, 0)
                """,
                (
                    event_id,
                    milestone["title"],
                    milestone["description"],
                    milestone["status"],
                ),
            )
            continue

        cursor.execute(
            """
            UPDATE milestones
            SET
                description = ?,
                status = ?
            WHERE id = ?
            """,
            (milestone["description"], milestone["status"], int(row["id"])),
        )


def seed() -> None:
    init_orbit_db()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        event_id = _seed_major_event(cursor)
        _seed_milestones(cursor, event_id)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
    print("Seeded Orbit Corporate Escape data.")
