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
    (
        "Web Search Agent",
        "web_search",
        "Researches current/external information for approved tasks, milestones, and recommendations.",
    ),
    (
        "Readiness Advisory Agent",
        "readiness_advisory",
        "Reviews Orbit evidence and suggests readiness score improvements that require manual approval.",
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
            status TEXT NOT NULL DEFAULT 'active',
            progress_percent INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (status IN ('active', 'paused', 'completed', 'archived')),
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
        CREATE TABLE IF NOT EXISTS trade_journal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT NOT NULL DEFAULT CURRENT_DATE,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL,
            stop_loss REAL,
            take_profit REAL,
            exit_price REAL,
            result_dollars REAL,
            result_r REAL,
            contracts INTEGER,
            session TEXT,
            htf_bias TEXT,
            strategy_profile TEXT NOT NULL DEFAULT 'Liquidity Narrative Continuation',
            strategy_mode TEXT NOT NULL DEFAULT 'Hybrid / Review',
            draw_on_liquidity TEXT NOT NULL DEFAULT '[]',
            reaction_zone TEXT,
            behavior_tags TEXT NOT NULL DEFAULT '[]',
            execution_tags TEXT NOT NULL DEFAULT '[]',
            why_taken TEXT,
            price_intent TEXT,
            liquidity_target TEXT,
            went_well TEXT,
            went_wrong TEXT,
            lesson_learned TEXT,
            screenshot_path TEXT,
            csv_path TEXT,
            entry_type TEXT NOT NULL DEFAULT 'journal',
            include_in_journal INTEGER NOT NULL DEFAULT 1,
            include_in_strategy_review INTEGER NOT NULL DEFAULT 1,
            include_in_scanner_match INTEGER NOT NULL DEFAULT 1,
            include_in_patterns INTEGER NOT NULL DEFAULT 1,
            include_in_performance_calendar INTEGER NOT NULL DEFAULT 1,
            source_import_key TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (direction IN ('Long', 'Short')),
            CHECK (contracts IS NULL OR contracts >= 0),
            CHECK (session IS NULL OR session IN ('Asia', 'London', 'New York', 'After Hours')),
            CHECK (htf_bias IS NULL OR htf_bias IN ('Bullish', 'Bearish', 'Neutral')),
            CHECK (entry_type IN ('journal', 'calendar_only')),
            CHECK (include_in_journal IN (0, 1)),
            CHECK (include_in_strategy_review IN (0, 1)),
            CHECK (include_in_scanner_match IN (0, 1)),
            CHECK (include_in_patterns IN (0, 1)),
            CHECK (include_in_performance_calendar IN (0, 1)),
            CHECK (strategy_mode IN ('Scalp', 'Day Trade', 'Hybrid / Review'))
        )
    """)

    cursor.execute("PRAGMA table_info(trade_journal)")
    trade_journal_columns = {row["name"] for row in cursor.fetchall()}
    if "strategy_profile" not in trade_journal_columns:
        cursor.execute(
            "ALTER TABLE trade_journal "
            "ADD COLUMN strategy_profile TEXT NOT NULL DEFAULT 'Liquidity Narrative Continuation'"
        )
    if "strategy_mode" not in trade_journal_columns:
        cursor.execute(
            "ALTER TABLE trade_journal "
            "ADD COLUMN strategy_mode TEXT NOT NULL DEFAULT 'Hybrid / Review'"
        )
    if "entry_type" not in trade_journal_columns:
        cursor.execute(
            "ALTER TABLE trade_journal ADD COLUMN entry_type TEXT NOT NULL DEFAULT 'journal'"
        )
    if "include_in_journal" not in trade_journal_columns:
        cursor.execute(
            "ALTER TABLE trade_journal ADD COLUMN include_in_journal INTEGER NOT NULL DEFAULT 1"
        )
    if "include_in_strategy_review" not in trade_journal_columns:
        cursor.execute(
            "ALTER TABLE trade_journal ADD COLUMN include_in_strategy_review INTEGER NOT NULL DEFAULT 1"
        )
    if "include_in_scanner_match" not in trade_journal_columns:
        cursor.execute(
            "ALTER TABLE trade_journal ADD COLUMN include_in_scanner_match INTEGER NOT NULL DEFAULT 1"
        )
    if "include_in_patterns" not in trade_journal_columns:
        cursor.execute(
            "ALTER TABLE trade_journal ADD COLUMN include_in_patterns INTEGER NOT NULL DEFAULT 1"
        )
    if "include_in_performance_calendar" not in trade_journal_columns:
        cursor.execute(
            "ALTER TABLE trade_journal ADD COLUMN include_in_performance_calendar INTEGER NOT NULL DEFAULT 1"
        )
    if "source_import_key" not in trade_journal_columns:
        cursor.execute("ALTER TABLE trade_journal ADD COLUMN source_import_key TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schedule_blocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            block_type TEXT NOT NULL,
            category TEXT NOT NULL,
            day_of_week TEXT,
            specific_date TEXT,
            start_time TEXT,
            end_time TEXT,
            duration_minutes INTEGER,
            recurrence TEXT,
            recurrence_end_type TEXT DEFAULT 'never',
            recurrence_end_date TEXT,
            recurrence_count INTEGER,
            recurrence_weeks INTEGER,
            preferred_days TEXT,
            time_preference TEXT DEFAULT 'anytime',
            flexible_placement_mode TEXT DEFAULT 'preferred_day',
            priority TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'upcoming',
            notes TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            started_at TEXT,
            completed_at TEXT,
            rolled_at TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CHECK (block_type IN ('fixed', 'flexible')),
            CHECK (category IN (
                'boxing',
                'family',
                'reading',
                'work',
                'trading',
                'milestone',
                'leisure',
                'personal',
                'other'
            )),
            CHECK (
                day_of_week IS NULL OR day_of_week IN (
                    'monday',
                    'tuesday',
                    'wednesday',
                    'thursday',
                    'friday',
                    'saturday',
                    'sunday'
                )
            ),
            CHECK (duration_minutes IS NULL OR duration_minutes > 0),
            CHECK (
                time_preference IS NULL OR time_preference IN (
                    'anytime',
                    'morning',
                    'afternoon',
                    'evening',
                    'night'
                )
            ),
            CHECK (
                flexible_placement_mode IS NULL OR flexible_placement_mode IN (
                    'whenever_free',
                    'preferred_day'
                )
            ),
            CHECK (priority IN ('low', 'medium', 'high')),
            CHECK (active IN (0, 1))
        )
    """)

    cursor.execute("PRAGMA table_info(schedule_blocks)")
    schedule_block_columns = {row["name"] for row in cursor.fetchall()}
    if "specific_date" not in schedule_block_columns:
        cursor.execute("ALTER TABLE schedule_blocks ADD COLUMN specific_date TEXT")
    if "time_preference" not in schedule_block_columns:
        cursor.execute(
            "ALTER TABLE schedule_blocks ADD COLUMN time_preference TEXT DEFAULT 'anytime'"
        )
    if "flexible_placement_mode" not in schedule_block_columns:
        cursor.execute(
            "ALTER TABLE schedule_blocks ADD COLUMN flexible_placement_mode TEXT DEFAULT 'preferred_day'"
        )
    if "recurrence_end_type" not in schedule_block_columns:
        cursor.execute(
            "ALTER TABLE schedule_blocks ADD COLUMN recurrence_end_type TEXT DEFAULT 'never'"
        )
    if "recurrence_end_date" not in schedule_block_columns:
        cursor.execute("ALTER TABLE schedule_blocks ADD COLUMN recurrence_end_date TEXT")
    if "recurrence_count" not in schedule_block_columns:
        cursor.execute("ALTER TABLE schedule_blocks ADD COLUMN recurrence_count INTEGER")
    if "recurrence_weeks" not in schedule_block_columns:
        cursor.execute("ALTER TABLE schedule_blocks ADD COLUMN recurrence_weeks INTEGER")
    if "preferred_days" not in schedule_block_columns:
        cursor.execute("ALTER TABLE schedule_blocks ADD COLUMN preferred_days TEXT")
    if "status" not in schedule_block_columns:
        cursor.execute("ALTER TABLE schedule_blocks ADD COLUMN status TEXT NOT NULL DEFAULT 'upcoming'")
    if "started_at" not in schedule_block_columns:
        cursor.execute("ALTER TABLE schedule_blocks ADD COLUMN started_at TEXT")
    if "completed_at" not in schedule_block_columns:
        cursor.execute("ALTER TABLE schedule_blocks ADD COLUMN completed_at TEXT")
    if "rolled_at" not in schedule_block_columns:
        cursor.execute("ALTER TABLE schedule_blocks ADD COLUMN rolled_at TEXT")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mobile_reminders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT,
            due_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            completed_at TEXT,
            dismissed_at TEXT,
            CHECK (status IN ('pending', 'done', 'dismissed')),
            CHECK (source IN ('chat', 'manual', 'schedule', 'scanner', 'system'))
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS mobile_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            body TEXT,
            type TEXT NOT NULL DEFAULT 'system',
            status TEXT NOT NULL DEFAULT 'unread',
            priority TEXT NOT NULL DEFAULT 'normal',
            target_kind TEXT,
            target_value TEXT,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            acknowledged_at TEXT,
            completed_at TEXT,
            dismissed_at TEXT,
            CHECK (type IN ('trading', 'schedule', 'task', 'system')),
            CHECK (status IN ('unread', 'read', 'dismissed', 'completed')),
            CHECK (priority IN ('low', 'normal', 'high'))
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
        UPDATE major_events
        SET status = 'active'
        WHERE status NOT IN ('active', 'paused', 'completed', 'archived')
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
        CREATE TRIGGER IF NOT EXISTS update_trade_journal_updated_at
        AFTER UPDATE ON trade_journal
        FOR EACH ROW
        BEGIN
            UPDATE trade_journal
            SET updated_at = CURRENT_TIMESTAMP
            WHERE id = OLD.id;
        END
    """)

    cursor.execute("""
        CREATE TRIGGER IF NOT EXISTS update_schedule_blocks_updated_at
        AFTER UPDATE ON schedule_blocks
        FOR EACH ROW
        BEGIN
            UPDATE schedule_blocks
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
