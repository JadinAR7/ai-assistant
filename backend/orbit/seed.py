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
INBOX_MILESTONE_TITLE = "Inbox / General"
INBOX_GOAL_TITLE = "Inbox"
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

READINESS_CATEGORIES = [
    "Financial",
    "Trading",
    "Business",
    "Personal",
]


def _get_major_event_id(cursor: Any, title: str) -> int | None:
    cursor.execute("SELECT id FROM major_events WHERE title = ? ORDER BY id LIMIT 1", (title,))
    row = cursor.fetchone()
    if row is None:
        return None
    return int(row["id"])


def _get_milestone_id(cursor: Any, major_event_id: int, title: str) -> int | None:
    cursor.execute(
        """
        SELECT id
        FROM milestones
        WHERE major_event_id = ? AND title = ?
        ORDER BY id
        LIMIT 1
        """,
        (major_event_id, title),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    return int(row["id"])


def _get_goal_id(cursor: Any, milestone_id: int, title: str) -> int | None:
    cursor.execute(
        """
        SELECT id
        FROM goals
        WHERE milestone_id = ? AND title = ?
        ORDER BY id
        LIMIT 1
        """,
        (milestone_id, title),
    )
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


def _seed_inbox(cursor: Any, event_id: int) -> None:
    milestone_id = _get_milestone_id(cursor, event_id, INBOX_MILESTONE_TITLE)
    if milestone_id is None:
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
                INBOX_MILESTONE_TITLE,
                "Default catch-all milestone for loose Orbit goals and tasks.",
                "active",
            ),
        )
        milestone_id = int(cursor.lastrowid)

    goal_id = _get_goal_id(cursor, milestone_id, INBOX_GOAL_TITLE)
    if goal_id is None:
        cursor.execute(
            """
            INSERT INTO goals (
                milestone_id,
                title,
                description,
                status,
                priority
            )
            VALUES (?, ?, ?, ?, 0)
            """,
            (
                milestone_id,
                INBOX_GOAL_TITLE,
                "Default catch-all goal for loose Orbit tasks.",
                "active",
            ),
        )
        return


def _seed_readiness_categories(cursor: Any, event_id: int) -> None:
    for category_name in READINESS_CATEGORIES:
        cursor.execute(
            """
            SELECT id
            FROM readiness_categories
            WHERE major_event_id = ? AND category_name = ?
            ORDER BY id
            LIMIT 1
            """,
            (event_id, category_name),
        )
        row = cursor.fetchone()

        if row is None:
            cursor.execute(
                """
                INSERT INTO readiness_categories (
                    major_event_id,
                    category_name,
                    current_score,
                    target_score,
                    notes
                )
                VALUES (?, ?, 0, 100, NULL)
                """,
                (event_id, category_name),
            )


def seed() -> None:
    init_orbit_db()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        event_id = _seed_major_event(cursor)
        _seed_milestones(cursor, event_id)
        _seed_inbox(cursor, event_id)
        _seed_readiness_categories(cursor, event_id)
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    seed()
    print("Seeded Orbit Corporate Escape data.")
