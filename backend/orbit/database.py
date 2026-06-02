from pathlib import Path
import sqlite3


DB_PATH = Path(__file__).resolve().parents[1] / "assistant.db"


INITIAL_AGENT_DEFINITIONS = [
    (
        "Morning Review Agent",
        "morning_review",
        "Generates the Orbit morning briefing and records the result.",
    ),
    (
        "Evening Review Agent",
        "evening_review",
        "Generates the Orbit daily closeout and records the result.",
    ),
    (
        "Executive Assistant Agent",
        "executive_assistant",
        "Summarizes open tasks, blockers, and milestone progress history without taking actions.",
    ),
    (
        "Trading Coach Agent",
        "trading_coach",
        "Summarizes recent trade sessions and readiness evidence without scanner changes or trading signals.",
    ),
]


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
        CREATE TABLE IF NOT EXISTS task_milestone_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL,
            milestone_id INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (task_id, milestone_id),
            FOREIGN KEY (task_id)
                REFERENCES tasks (id)
                ON DELETE CASCADE,
            FOREIGN KEY (milestone_id)
                REFERENCES milestones (id)
                ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS milestone_progress_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            milestone_id INTEGER NOT NULL,
            previous_progress INTEGER NOT NULL,
            new_progress INTEGER NOT NULL,
            change_amount INTEGER NOT NULL,
            reason TEXT,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (previous_progress >= 0 AND previous_progress <= 100),
            CHECK (new_progress >= 0 AND new_progress <= 100),
            CHECK (source IN ('manual', 'task_advisory', 'helix_tool', 'system')),
            FOREIGN KEY (milestone_id)
                REFERENCES milestones (id)
                ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            review_type TEXT NOT NULL,
            summary TEXT,
            rating REAL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS readiness_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            major_event_id INTEGER NOT NULL,
            category_name TEXT NOT NULL,
            current_score INTEGER NOT NULL DEFAULT 0,
            target_score INTEGER NOT NULL DEFAULT 100,
            notes TEXT,
            last_updated TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (current_score >= 0 AND current_score <= 100),
            CHECK (target_score >= 0 AND target_score <= 100),
            UNIQUE (major_event_id, category_name),
            FOREIGN KEY (major_event_id)
                REFERENCES major_events (id)
                ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trade_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            symbol TEXT NOT NULL,
            pnl REAL NOT NULL,
            notes TEXT,
            rule_adherence INTEGER,
            confidence INTEGER,
            session_grade TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (rule_adherence IS NULL OR (rule_adherence >= 0 AND rule_adherence <= 100)),
            CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 10))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_definitions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            agent_type TEXT NOT NULL UNIQUE,
            description TEXT,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS agent_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            summary TEXT,
            output_json TEXT,
            error TEXT,
            CHECK (status IN ('running', 'completed', 'failed')),
            FOREIGN KEY (agent_id)
                REFERENCES agent_definitions (id)
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

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS update_readiness_categories_last_updated
        AFTER UPDATE ON readiness_categories
        FOR EACH ROW
        BEGIN
            UPDATE readiness_categories
            SET last_updated = CURRENT_TIMESTAMP
            WHERE id = OLD.id;
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS update_trade_sessions_updated_at
        AFTER UPDATE ON trade_sessions
        FOR EACH ROW
        BEGIN
            UPDATE trade_sessions
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = OLD.id;
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS update_agent_definitions_updated_at
        AFTER UPDATE ON agent_definitions
        FOR EACH ROW
        BEGIN
            UPDATE agent_definitions
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = OLD.id;
        END
    """)

    cursor.executemany(
        """
        INSERT INTO agent_definitions (name, agent_type, description, enabled)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(agent_type) DO UPDATE SET
            name = excluded.name,
            description = excluded.description
        """,
        INITIAL_AGENT_DEFINITIONS,
    )

    conn.commit()
    conn.close()
