from pathlib import Path
import sqlite3


DB_PATH = Path(__file__).resolve().parents[1] / "assistant.db"


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_orbit_db() -> None:
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS major_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            target_date TEXT,
            status TEXT NOT NULL DEFAULT 'not_started',
            progress_percent INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (progress_percent >= 0 AND progress_percent <= 100)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS milestones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            major_event_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'not_started',
            progress_percent INTEGER NOT NULL DEFAULT 0,
            target_value REAL,
            current_value REAL,
            due_date TEXT,
            CHECK (progress_percent >= 0 AND progress_percent <= 100),
            FOREIGN KEY (major_event_id)
                REFERENCES major_events (id)
                ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            milestone_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'not_started',
            priority INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (milestone_id)
                REFERENCES milestones (id)
                ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            goal_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            status TEXT NOT NULL DEFAULT 'not_started',
            due_date TEXT,
            completed_at TEXT,
            FOREIGN KEY (goal_id)
                REFERENCES goals (id)
                ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS update_major_events_updated_at
        AFTER UPDATE ON major_events
        FOR EACH ROW
        BEGIN
            UPDATE major_events
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = OLD.id;
        END
    """)

    conn.commit()
    conn.close()

