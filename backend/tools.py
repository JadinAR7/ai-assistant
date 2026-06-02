from datetime import date, datetime, timezone
import subprocess
import os
import json
import re
import shutil
import time
import requests
import pandas as pd
import base64
from pathlib import Path
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

try:
    from orbit import service as orbit_service
    from orbit.database import get_connection as get_orbit_connection
except ImportError:
    from backend.orbit import service as orbit_service
    from backend.orbit.database import get_connection as get_orbit_connection


load_dotenv()

BASE_DIR = os.path.abspath(".")
MAX_OUTPUT_CHARS = 4000
MIN_FVG_SIZE = 1.0
DISPLACEMENT_MULTIPLIER = 1.5

CSV_DATA_DIR = os.path.join(BASE_DIR, "csv_data")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "pictures", "tradingview_screenshots")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads", "tradingview_csv")
USER_DOWNLOADS_DIR = Path.home() / "Downloads"
TRADINGVIEW_EXPORT_DOWNLOAD_TIMEOUT_SECONDS = 45
DEBUG_EXPORTS_DIR = Path(__file__).resolve().parent / "downloads" / "debug_exports"

os.makedirs(CSV_DATA_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)
DEBUG_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
TEXT_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
VISION_MODEL = os.getenv("VISION_MODEL", "qwen2.5vl:7b")
ORBIT_CORPORATE_ESCAPE_TITLE = "Corporate Escape"
ORBIT_INBOX_MILESTONE_TITLE = "Inbox / General"
ORBIT_INBOX_GOAL_TITLE = "Inbox"


SYMBOL_CONFIG = {
    "MNQ": {
        "tv_symbol": "CME_MINI:MNQ1!",
        "csv_root": "CME_MINI_MNQ1!",
        "csv_prefix": "MNQ",
    },
    "NQ": {
        "tv_symbol": "CME_MINI:NQ1!",
        "csv_root": "CME_MINI_NQ1!",
        "csv_prefix": "NQ",
    },
    "MES": {
        "tv_symbol": "CME_MINI:MES1!",
        "csv_root": "CME_MINI_MES1!",
        "csv_prefix": "MES",
    },
    "ES": {
        "tv_symbol": "CME_MINI:ES1!",
        "csv_root": "CME_MINI_ES1!",
        "csv_prefix": "ES",
    },
}


TRADINGVIEW_TIMEFRAMES = {
    "1M": "1",
    "5M": "5",
    "15M": "15",
    "1H": "60",
    "4H": "240",
    "1D": "1D",
}


TIMEFRAME_LABELS = {
    "1M": "1 minute",
    "5M": "5 minutes",
    "15M": "15 minutes",
    "1H": "1 hour",
    "4H": "4 hours",
    "1D": "1 day",
}


CSV_STALENESS_THRESHOLDS_MINUTES = {
    "1M": 15,
    "5M": 20,
    "15M": 45,
    "1H": 90,
    "4H": 6 * 60,
    "1D": 36 * 60,
}


TIMEFRAME_WEIGHTS = {
    "1D": 50,
    "4H": 40,
    "1H": 30,
    "15M": 20,
    "1M": 10,
}


# ---------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------

def ollama_generate(
    model: str,
    prompt: str,
    images: list[str] | None = None,
    timeout: int = 180,
    num_ctx: int = 8192,
):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    if images:
        # Keep vision payload minimal. This matches the direct qwen2.5vl test that worked.
        # Some local vision models can 500 when image input is combined with extra options.
        payload["images"] = images
    else:
        # Text-only calls can keep the extra controls.
        payload["think"] = False
        payload["options"] = {"num_ctx": num_ctx}

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=timeout,
    )

    response.raise_for_status()
    data = response.json()

    return data.get("response", "").strip()


def parse_json_from_text(text: str):
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError("No JSON object found in model response.")

    return json.loads(match.group(0))


def get_symbol_config(symbol: str):
    symbol = symbol.upper()

    if symbol not in SYMBOL_CONFIG:
        raise ValueError(
            f"Unsupported symbol: {symbol}. Supported: {', '.join(SYMBOL_CONFIG.keys())}"
        )

    return SYMBOL_CONFIG[symbol]


def safe_path(path: str):
    os.makedirs(CSV_DATA_DIR, exist_ok=True)

    full_path = os.path.abspath(os.path.join(CSV_DATA_DIR, path))

    if not full_path.startswith(os.path.abspath(CSV_DATA_DIR)):
        raise ValueError("Access denied: outside csv_data directory")

    return full_path


def read_file(path: str = ""):
    try:
        full_path = os.path.abspath(os.path.join(BASE_DIR, path))

        if not full_path.startswith(BASE_DIR):
            raise ValueError("Access denied: outside base directory")

        with open(full_path, "r") as f:
            content = f.read()

        return {
            "success": True,
            "path": path,
            "content": content[:MAX_OUTPUT_CHARS],
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def write_file(path: str = "", content: str = "", mode: str = "w"):
    try:
        full_path = os.path.abspath(os.path.join(BASE_DIR, path))

        if not full_path.startswith(BASE_DIR):
            raise ValueError("Access denied: outside base directory")

        with open(full_path, mode) as f:
            f.write(content)

        return {
            "success": True,
            "path": path,
            "mode": mode,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def get_time():
    return {
        "success": True,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def echo(text: str = ""):
    return {
        "success": True,
        "echo": text,
    }


ALLOWED_COMMANDS = {
    "pwd": ["pwd"],
    "list_files": ["ls", "-la"],
    "disk_usage": ["df", "-h"],
}


def run_command(command: str = ""):
    if command not in ALLOWED_COMMANDS:
        return {
            "success": False,
            "error": f"Command not allowed: {command}",
        }

    try:
        result = subprocess.run(
            ALLOWED_COMMANDS[command],
            capture_output=True,
            text=True,
            timeout=10,
        )

        stdout = result.stdout[:MAX_OUTPUT_CHARS]
        stderr = result.stderr[:MAX_OUTPUT_CHARS]

        return {
            "success": True,
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": result.returncode,
            "truncated": (
                len(result.stdout) > MAX_OUTPUT_CHARS
                or len(result.stderr) > MAX_OUTPUT_CHARS
            ),
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timed out.",
        }


def open_url(url: str = ""):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded")

            title = page.title()
            text = page.locator("body").inner_text()[:MAX_OUTPUT_CHARS]

            browser.close()

            return {
                "success": True,
                "url": url,
                "title": title,
                "text": text,
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def extract_links(url: str = ""):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded")

            links = page.locator("a").evaluate_all("""
                elements => elements.map(a => ({
                    text: a.innerText,
                    href: a.href
                }))
            """)

            browser.close()

            return {
                "success": True,
                "url": url,
                "links": links[:50],
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


def create_reminder(title: str = "", reminder_time: str = ""):
    try:
        title = title.replace("_", " ")
        reminder_time = reminder_time.replace("_", " ")

        if reminder_time:
            script = f'''
tell application "Reminders"
    tell default list
        make new reminder with properties {{name:"{title}", remind me date:date "{reminder_time}"}}
    end tell
end tell
'''
        else:
            script = f'''
tell application "Reminders"
    tell default list
        make new reminder with properties {{name:"{title}"}}
    end tell
end tell
'''

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )

        return {
            "success": result.returncode == 0,
            "title": title,
            "time": reminder_time,
            "stderr": result.stderr,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


def web_search(query: str = ""):
    api_key = os.getenv("BRAVE_API_KEY")

    if not api_key:
        return {
            "success": False,
            "error": "BRAVE_API_KEY is missing.",
        }

    try:
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
            params={
                "q": query.replace("_", " "),
                "count": 5,
            },
            timeout=10,
        )

        response.raise_for_status()
        data = response.json()

        results = []

        for item in data.get("web", {}).get("results", []):
            results.append({
                "title": item.get("title"),
                "url": item.get("url"),
                "description": item.get("description"),
            })

        return {
            "success": True,
            "query": query,
            "results": results,
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------------------------------------------------------------------
# Orbit planning tools
# ---------------------------------------------------------------------

def get_orbit_major_events():
    try:
        return {
            "success": True,
            "major_events": orbit_service.list_records("major_events"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_orbit_milestones():
    try:
        return {
            "success": True,
            "milestones": orbit_service.list_records("milestones"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_orbit_goals():
    try:
        return {
            "success": True,
            "goals": orbit_service.list_records("goals"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def get_orbit_tasks():
    try:
        return {
            "success": True,
            "tasks": orbit_service.list_records("tasks"),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _orbit_text(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("_", " ").strip()


def _parse_required_int(value: str | int | None, field_name: str) -> tuple[int | None, str | None]:
    if value is None or value == "":
        return None, f"Missing required field: {field_name}."

    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, f"{field_name} must be a valid integer."


def _parse_optional_int(value: str | int | None, field_name: str) -> tuple[int | None, str | None]:
    if value is None or value == "":
        return None, None

    try:
        return int(value), None
    except (TypeError, ValueError):
        return None, f"{field_name} must be a valid integer."


def _parse_optional_float(value: str | int | float | None, field_name: str) -> tuple[float | None, str | None]:
    if value is None or value == "":
        return None, None

    try:
        return float(value), None
    except (TypeError, ValueError):
        return None, f"{field_name} must be a valid number."


def _parse_progress_percent(value: str | int | None) -> tuple[int | None, str | None]:
    if isinstance(value, str):
        value = value.strip().removesuffix("%")

    progress_percent, error = _parse_required_int(value, "progress_percent")
    if error:
        return None, error

    if progress_percent < 0 or progress_percent > 100:
        return None, "progress_percent must be between 0 and 100."

    return progress_percent, None


def _orbit_column_allows_missing(table: str, column: str) -> bool:
    conn = get_orbit_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table})")
        for row in cursor.fetchall():
            if row["name"] == column:
                return not bool(row["notnull"])
    finally:
        conn.close()

    return False


def _orbit_summary(record: dict, fields: list[str]) -> dict:
    return {field: record.get(field) for field in fields}


def _parse_orbit_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None


def _parse_orbit_date(value: str | None) -> date | None:
    parsed = _parse_orbit_datetime(value)
    if parsed is not None:
        return parsed.date()

    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _orbit_table_exists(table: str) -> bool:
    conn = get_orbit_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table,),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def _find_orbit_record(table: str, **matches) -> dict | None:
    for record in orbit_service.list_records(table):
        if all(record.get(key) == value for key, value in matches.items()):
            return record
    return None


def _get_corporate_escape_event() -> dict | None:
    return _find_orbit_record("major_events", title=ORBIT_CORPORATE_ESCAPE_TITLE)


def _get_or_create_inbox_milestone() -> tuple[dict | None, str | None]:
    event = _get_corporate_escape_event()
    if event is None:
        return None, "Corporate Escape major event not found; cannot create default Orbit Inbox milestone."

    milestone = _find_orbit_record(
        "milestones",
        major_event_id=event.get("id"),
        title=ORBIT_INBOX_MILESTONE_TITLE,
    )
    if milestone is not None:
        return milestone, None

    try:
        milestone = orbit_service.create_milestone({
            "major_event_id": event.get("id"),
            "title": ORBIT_INBOX_MILESTONE_TITLE,
            "description": "Default catch-all milestone for loose Orbit goals and tasks.",
            "status": "active",
            "progress_percent": 0,
            "target_value": None,
            "current_value": None,
            "due_date": None,
        })
    except Exception as e:
        return None, f"Unable to create default Orbit Inbox milestone: {e}"

    return milestone, None


def _get_or_create_inbox_goal() -> tuple[dict | None, str | None]:
    milestone, error = _get_or_create_inbox_milestone()
    if error:
        return None, error

    goal = _find_orbit_record(
        "goals",
        milestone_id=milestone.get("id"),
        title=ORBIT_INBOX_GOAL_TITLE,
    )
    if goal is not None:
        return goal, None

    try:
        goal = orbit_service.create_goal({
            "milestone_id": milestone.get("id"),
            "title": ORBIT_INBOX_GOAL_TITLE,
            "description": "Default catch-all goal for loose Orbit tasks.",
            "status": "active",
            "priority": 0,
        })
    except Exception as e:
        return None, f"Unable to create default Orbit Inbox goal: {e}"

    return goal, None


def create_orbit_task(
    title: str = "",
    description: str | None = None,
    goal_id: str | int | None = None,
    due_date: str | None = None,
    milestone_id: str | int | None = None,
    milestone_title: str | None = None,
):
    if not title:
        return {"success": False, "error": "Missing required field: title."}

    parsed_goal_id, error = _parse_optional_int(goal_id, "goal_id")
    if error:
        return {"success": False, "error": error}
    parsed_milestone_id, error = _parse_optional_int(milestone_id, "milestone_id")
    if error:
        return {"success": False, "error": error}

    try:
        matched_milestone = None
        search_milestone_title = _orbit_text(milestone_title)
        if parsed_milestone_id is not None:
            matched_milestone = orbit_service.get_record("milestones", parsed_milestone_id)
            if matched_milestone is None:
                return {
                    "success": False,
                    "error": f"No Orbit milestone found with id {parsed_milestone_id}.",
                }
        elif search_milestone_title:
            normalized_milestone_title = search_milestone_title.casefold()
            milestone_matches = [
                milestone
                for milestone in orbit_service.list_records("milestones")
                if normalized_milestone_title
                in str(milestone.get("title") or "").casefold()
            ]
            if len(milestone_matches) == 1:
                matched_milestone = milestone_matches[0]
                parsed_milestone_id = int(matched_milestone["id"])

        if parsed_goal_id is None:
            inbox_goal, error = _get_or_create_inbox_goal()
            if error:
                return {"success": False, "error": error}
            parsed_goal_id = inbox_goal.get("id")

        if parsed_goal_id is None and not _orbit_column_allows_missing("tasks", "goal_id"):
            return {
                "success": False,
                "error": "goal_id is required by the current Orbit database schema.",
            }

        payload = {
            "goal_id": parsed_goal_id,
            "title": _orbit_text(title),
            "description": _orbit_text(description),
            "status": "not_started",
            "due_date": due_date,
            "completed_at": None,
        }
        task = orbit_service.create_task(payload)
        linked_milestones = []
        if parsed_milestone_id is not None:
            orbit_service.link_task_to_milestone(int(task["id"]), parsed_milestone_id)
            linked_milestones = orbit_service.list_milestones_linked_to_task(int(task["id"]))

        return {
            "success": True,
            "task_id": task.get("id"),
            "title": task.get("title"),
            "due_date": task.get("due_date"),
            "goal_id": task.get("goal_id"),
            "linked_milestones": [
                _orbit_summary(milestone, ["id", "title", "status", "progress_percent"])
                for milestone in linked_milestones
            ],
        }
    except Exception as e:
        return {"success": False, "error": f"Unable to create Orbit task: {e}"}


def _complete_orbit_task_record(task: dict) -> dict:
    completed_at = datetime.now().isoformat()
    updated_task = orbit_service.update_task(
        task["id"],
        {
            "status": "completed",
            "completed_at": completed_at,
        },
    )

    if updated_task is None:
        return {
            "success": False,
            "error": f"Orbit task {task['id']} could not be updated.",
        }

    return {
        "success": True,
        "task_id": updated_task.get("id"),
        "title": updated_task.get("title"),
        "status": updated_task.get("status"),
        "completed_at": updated_task.get("completed_at"),
    }


def complete_orbit_task(
    task_id: str | int | None = None,
    title: str | None = None,
):
    parsed_task_id, error = _parse_optional_int(task_id, "task_id")
    if error:
        return {"success": False, "error": error}

    try:
        if parsed_task_id is not None:
            task = orbit_service.get_record("tasks", parsed_task_id)
            if task is None:
                return {
                    "success": False,
                    "error": f"No Orbit task found with id {parsed_task_id}.",
                }
            return _complete_orbit_task_record(task)

        search_title = _orbit_text(title)
        if not search_title:
            return {
                "success": False,
                "error": "Provide either task_id or title to complete an Orbit task.",
            }

        normalized_search = search_title.casefold()
        matches = [
            task
            for task in orbit_service.list_records("tasks")
            if normalized_search in str(task.get("title") or "").casefold()
        ]

        if not matches:
            return {
                "success": False,
                "error": f"No Orbit task title matched '{search_title}'.",
            }

        if len(matches) > 1:
            matching_tasks = [
                {
                    "task_id": task.get("id"),
                    "title": task.get("title"),
                }
                for task in matches
            ]
            return {
                "success": False,
                "error": "Multiple Orbit tasks matched that title. Provide task_id to choose one.",
                "matches": matching_tasks,
            }

        return _complete_orbit_task_record(matches[0])
    except Exception as e:
        return {"success": False, "error": f"Unable to complete Orbit task: {e}"}


def create_orbit_goal(
    title: str = "",
    description: str | None = None,
    milestone_id: str | int | None = None,
    priority: str | int | None = None,
):
    if not title:
        return {"success": False, "error": "Missing required field: title."}

    parsed_milestone_id, error = _parse_optional_int(milestone_id, "milestone_id")
    if error:
        return {"success": False, "error": error}

    parsed_priority, error = _parse_optional_int(priority, "priority")
    if error:
        return {"success": False, "error": error}

    try:
        if parsed_milestone_id is None:
            inbox_milestone, error = _get_or_create_inbox_milestone()
            if error:
                return {"success": False, "error": error}
            parsed_milestone_id = inbox_milestone.get("id")

        if parsed_milestone_id is None and not _orbit_column_allows_missing("goals", "milestone_id"):
            return {
                "success": False,
                "error": "milestone_id is required by the current Orbit database schema.",
            }

        payload = {
            "milestone_id": parsed_milestone_id,
            "title": _orbit_text(title),
            "description": _orbit_text(description),
            "status": "not_started",
            "priority": parsed_priority if parsed_priority is not None else 0,
        }
        goal = orbit_service.create_goal(payload)

        return {
            "success": True,
            "goal_id": goal.get("id"),
            "title": goal.get("title"),
            "priority": goal.get("priority"),
            "milestone_id": goal.get("milestone_id"),
        }
    except Exception as e:
        return {"success": False, "error": f"Unable to create Orbit goal: {e}"}


def update_orbit_milestone_progress(
    milestone_id: str | int | None = None,
    progress_percent: str | int | None = None,
    status: str | None = None,
    reason: str | None = None,
):
    parsed_milestone_id, error = _parse_required_int(milestone_id, "milestone_id")
    if error:
        return {"success": False, "error": error}

    parsed_progress, error = _parse_progress_percent(progress_percent)
    if error:
        return {"success": False, "error": error}

    try:
        payload = {
            "progress_percent": parsed_progress,
            "progress_update_source": "helix_tool",
        }
        if reason:
            payload["progress_update_reason"] = _orbit_text(reason)
        if status:
            payload["status"] = status

        milestone = orbit_service.update_milestone(parsed_milestone_id, payload)
        if milestone is None:
            return {
                "success": False,
                "error": f"Orbit milestone {parsed_milestone_id} not found.",
            }

        return {
            "success": True,
            "milestone": _orbit_summary(
                milestone,
                ["id", "title", "status", "progress_percent", "due_date"],
            ),
        }
    except Exception as e:
        return {"success": False, "error": f"Unable to update Orbit milestone: {e}"}


def update_orbit_major_event_progress(
    event_id: str | int | None = None,
    progress_percent: str | int | None = None,
    status: str | None = None,
):
    parsed_event_id, error = _parse_required_int(event_id, "event_id")
    if error:
        return {"success": False, "error": error}

    parsed_progress, error = _parse_progress_percent(progress_percent)
    if error:
        return {"success": False, "error": error}

    try:
        payload = {"progress_percent": parsed_progress}
        if status:
            payload["status"] = status

        event = orbit_service.update_major_event(parsed_event_id, payload)
        if event is None:
            return {
                "success": False,
                "error": f"Orbit major event {parsed_event_id} not found.",
            }

        return {
            "success": True,
            "major_event": _orbit_summary(
                event,
                ["id", "title", "status", "progress_percent", "target_date"],
            ),
        }
    except Exception as e:
        return {"success": False, "error": f"Unable to update Orbit major event: {e}"}


def get_corporate_escape_status():
    try:
        major_events = orbit_service.list_records("major_events")
        event = next(
            (
                item
                for item in major_events
                if item.get("title", "").lower() == "corporate escape"
            ),
            None,
        )

        if event is None:
            return {
                "success": False,
                "error": "Corporate Escape major event not found.",
            }

        milestones = [
            {
                "id": milestone.get("id"),
                "title": milestone.get("title"),
                "status": milestone.get("status"),
                "progress_percent": milestone.get("progress_percent"),
                "due_date": milestone.get("due_date"),
            }
            for milestone in orbit_service.list_records("milestones")
            if milestone.get("major_event_id") == event.get("id")
        ]

        summary = {
            "event_title": event.get("title"),
            "target_date": event.get("target_date"),
            "progress_percent": event.get("progress_percent"),
            "status": event.get("status"),
            "milestones": milestones,
        }

        milestone_lines = "\n".join(
            f"- {milestone['title']}: {milestone['status']} "
            f"({milestone['progress_percent']}%)"
            for milestone in milestones
        )

        return {
            "success": True,
            "summary": summary,
            "message": (
                f"Corporate Escape is {summary['status']} at "
                f"{summary['progress_percent']}% progress, targeting "
                f"{summary['target_date']}.\n\n"
                f"Linked milestones:\n{milestone_lines if milestone_lines else '- None'}"
            ),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_corporate_escape_readiness_categories() -> tuple[dict | None, list[dict], str | None]:
    event = _get_corporate_escape_event()
    if event is None:
        return None, [], "Corporate Escape major event not found."

    categories = orbit_service.get_readiness_categories(event.get("id"))
    return event, categories, None


def get_corporate_escape_readiness():
    try:
        event, categories, error = _get_corporate_escape_readiness_categories()
        if error:
            return {"success": False, "error": error}

        category_order = ["Financial", "Trading", "Business", "Personal"]
        order_index = {name: index for index, name in enumerate(category_order)}
        categories.sort(
            key=lambda category: (
                order_index.get(str(category.get("category_name")), len(order_index)),
                str(category.get("category_name") or ""),
            )
        )

        readiness = [
            _orbit_summary(
                category,
                ["id", "category_name", "current_score", "target_score", "notes", "last_updated"],
            )
            for category in categories
        ]

        category_lines = "\n".join(
            f"{category.get('category_name')}: "
            f"{category.get('current_score')}% / {category.get('target_score')}%"
            f"{' - ' + category.get('notes') if category.get('notes') else ''}"
            for category in readiness
        )

        return {
            "success": True,
            "event_id": event.get("id"),
            "title": "Corporate Escape Readiness",
            "readiness": readiness,
            "message": (
                "Corporate Escape Readiness\n\n"
                f"{category_lines if category_lines else 'No readiness categories found.'}"
            ),
        }
    except Exception as e:
        return {"success": False, "error": f"Unable to read Corporate Escape readiness: {e}"}


def update_readiness_category(
    readiness_id: str | int | None = None,
    category_name: str | None = None,
    current_score: str | int | None = None,
    target_score: str | int | None = None,
    notes: str | None = None,
):
    parsed_readiness_id, error = _parse_optional_int(readiness_id, "readiness_id")
    if error:
        return {"success": False, "error": error}

    if current_score is None and target_score is None and notes is None:
        return {
            "success": False,
            "error": "Provide current_score, target_score, or notes to update readiness.",
        }

    payload = {}
    if current_score is not None:
        parsed_current_score, error = _parse_progress_percent(current_score)
        if error:
            return {"success": False, "error": error.replace("progress_percent", "current_score")}
        payload["current_score"] = parsed_current_score

    if target_score is not None:
        parsed_target_score, error = _parse_progress_percent(target_score)
        if error:
            return {"success": False, "error": error.replace("progress_percent", "target_score")}
        payload["target_score"] = parsed_target_score

    if notes is not None:
        payload["notes"] = _orbit_text(notes)

    try:
        if parsed_readiness_id is None:
            search_name = _orbit_text(category_name)
            if not search_name:
                return {
                    "success": False,
                    "error": "Provide readiness_id or category_name to update readiness.",
                }

            _, categories, error = _get_corporate_escape_readiness_categories()
            if error:
                return {"success": False, "error": error}

            normalized_search = search_name.casefold()
            matches = [
                category
                for category in categories
                if str(category.get("category_name") or "").casefold() == normalized_search
            ]
            if not matches:
                return {
                    "success": False,
                    "error": f"No Corporate Escape readiness category matched '{search_name}'.",
                }
            parsed_readiness_id = matches[0].get("id")

        category = orbit_service.update_readiness_category(parsed_readiness_id, payload)
        if category is None:
            return {
                "success": False,
                "error": f"Readiness category {parsed_readiness_id} not found.",
            }

        return {
            "success": True,
            "readiness_category": _orbit_summary(
                category,
                ["id", "category_name", "current_score", "target_score", "notes", "last_updated"],
            ),
        }
    except Exception as e:
        return {"success": False, "error": f"Unable to update readiness category: {e}"}


def _get_trading_readiness_category(categories: list[dict]) -> dict | None:
    for category in categories:
        if str(category.get("category_name") or "").casefold() == "trading":
            return category
    return None


def _grade_to_score(grade: str | None) -> int | None:
    if not grade:
        return None

    normalized = str(grade).strip().upper().replace(" ", "")
    grade_scores = {
        "A+": 100,
        "A": 92,
        "A-": 88,
        "B+": 82,
        "B": 76,
        "B-": 70,
        "C+": 64,
        "C": 58,
        "C-": 52,
        "D": 40,
        "F": 20,
    }
    return grade_scores.get(normalized)


def _average(values: list[int | float | None]) -> float | None:
    present_values = [value for value in values if value is not None]
    if not present_values:
        return None
    return sum(present_values) / len(present_values)


def _clamp_score(value: int | float) -> int:
    return max(0, min(100, round(value)))


def _evidence_strength(total_sessions: int) -> str:
    if total_sessions < 5:
        return "weak"
    if total_sessions < 10:
        return "moderate"
    return "strong"


def _readiness_confidence(total_sessions: int) -> str:
    if total_sessions < 5:
        return "low"
    if total_sessions < 10:
        return "medium"
    return "high"


def _common_note_themes(trade_sessions: list[dict], limit: int = 5) -> list[str]:
    stop_words = {
        "about",
        "after",
        "again",
        "because",
        "before",
        "early",
        "followed",
        "from",
        "into",
        "just",
        "notes",
        "plan",
        "session",
        "that",
        "this",
        "trade",
        "with",
    }
    counts: dict[str, int] = {}
    for trade_session in trade_sessions:
        note = str(trade_session.get("notes") or "").lower()
        for word in re.findall(r"[a-z][a-z']{3,}", note):
            if word in stop_words:
                continue
            counts[word] = counts.get(word, 0) + 1

    return [
        word
        for word, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def suggest_trading_readiness_update(recent_limit: str | int | None = 20):
    parsed_limit, error = _parse_optional_int(recent_limit, "recent_limit")
    if error:
        return {"success": False, "error": error}

    if parsed_limit is None:
        parsed_limit = 20

    if parsed_limit < 1:
        return {"success": False, "error": "recent_limit must be at least 1."}

    parsed_limit = min(parsed_limit, 50)

    try:
        event, categories, error = _get_corporate_escape_readiness_categories()
        if error:
            return {"success": False, "error": error}

        trading_category = _get_trading_readiness_category(categories)
        if trading_category is None:
            return {
                "success": False,
                "error": "Trading readiness category not found.",
            }

        current_score = int(trading_category.get("current_score") or 0)
        trade_sessions = orbit_service.list_trade_sessions()[:parsed_limit]
        total_sessions = len(trade_sessions)
        total_pnl = sum(float(trade_session.get("pnl") or 0) for trade_session in trade_sessions)
        rule_values = [trade_session.get("rule_adherence") for trade_session in trade_sessions]
        confidence_values = [trade_session.get("confidence") for trade_session in trade_sessions]
        grade_values = [
            _grade_to_score(trade_session.get("session_grade"))
            for trade_session in trade_sessions
        ]
        average_rule_adherence = _average(rule_values)
        average_confidence = _average(confidence_values)
        average_grade_score = _average(grade_values)
        profitable_sessions = [
            trade_session
            for trade_session in trade_sessions
            if float(trade_session.get("pnl") or 0) > 0
        ]
        losing_sessions = [
            trade_session
            for trade_session in trade_sessions
            if float(trade_session.get("pnl") or 0) < 0
        ]
        positive_pnl_rate = (
            len(profitable_sessions) / total_sessions
            if total_sessions
            else None
        )
        disciplined_session_rate = (
            len([
                value
                for value in rule_values
                if value is not None and value >= 75
            ])
            / len([value for value in rule_values if value is not None])
            if any(value is not None for value in rule_values)
            else None
        )
        recent_session_grades = [
            trade_session.get("session_grade")
            for trade_session in trade_sessions[:5]
            if trade_session.get("session_grade")
        ]
        common_themes = _common_note_themes(trade_sessions)
        evidence_strength = _evidence_strength(total_sessions)
        confidence_level = _readiness_confidence(total_sessions)

        positive_signals = []
        concerns = []
        delta = 0

        if evidence_strength == "weak":
            concerns.append(
                f"Only {total_sessions} recent trade session(s) are available; readiness should not increase from this sample."
            )
        else:
            if average_rule_adherence is None:
                concerns.append("Rule adherence is missing from all recent sessions.")
            elif average_rule_adherence >= 85:
                delta += 6
                positive_signals.append(
                    f"Average rule adherence is strong at {average_rule_adherence:.1f}%."
                )
            elif average_rule_adherence >= 75:
                delta += 3
                positive_signals.append(
                    f"Average rule adherence is constructive at {average_rule_adherence:.1f}%."
                )
            elif average_rule_adherence < 60:
                delta -= 8
                concerns.append(f"Average rule adherence is weak at {average_rule_adherence:.1f}%.")
            elif average_rule_adherence < 70:
                delta -= 4
                concerns.append(
                    f"Average rule adherence is below target at {average_rule_adherence:.1f}%."
                )

            if disciplined_session_rate is not None:
                if disciplined_session_rate >= 0.7:
                    delta += 4
                    positive_signals.append(
                        f"{round(disciplined_session_rate * 100)}% of sessions met the rule-adherence threshold."
                    )
                elif disciplined_session_rate < 0.5:
                    delta -= 4
                    concerns.append(
                        f"Only {round(disciplined_session_rate * 100)}% of sessions met the rule-adherence threshold."
                    )

            if average_confidence is None:
                concerns.append("Confidence is missing from all recent sessions.")
            elif average_confidence >= 7:
                delta += 3
                positive_signals.append(f"Average confidence is healthy at {average_confidence:.1f}/10.")
            elif average_confidence < 4:
                delta -= 4
                concerns.append(f"Average confidence is low at {average_confidence:.1f}/10.")

            if positive_pnl_rate is not None:
                if positive_pnl_rate >= 0.65 and total_pnl > 0:
                    delta += 4
                    positive_signals.append(
                        f"{len(profitable_sessions)} of {total_sessions} sessions were profitable."
                    )
                elif positive_pnl_rate <= 0.35 and total_pnl < 0:
                    delta -= 5
                    concerns.append(
                        f"{len(losing_sessions)} of {total_sessions} sessions were losing sessions."
                    )
                elif total_pnl > 0:
                    positive_signals.append(
                        f"Recent total PnL is positive at {total_pnl:.2f}, but performance is not yet dominant across sessions."
                    )
                elif total_pnl < 0:
                    concerns.append(
                        f"Recent total PnL is negative at {total_pnl:.2f}, but readiness impact is based on repeated behavior first."
                    )
                else:
                    concerns.append("Recent total PnL is flat.")

            if average_grade_score is None:
                concerns.append("Session grades are missing from all recent sessions.")
            elif average_grade_score >= 80:
                delta += 3
                positive_signals.append("Recent session grades skew strong.")
            elif average_grade_score < 60:
                delta -= 3
                concerns.append("Recent session grades skew weak.")

        if total_sessions == 0:
            concerns.append("No trade sessions are available yet.")
        elif total_sessions < 5:
            concerns.append("At least 5 trade sessions are needed before confidence can rise above low.")

        missing_rule_count = sum(1 for value in rule_values if value is None)
        missing_confidence_count = sum(1 for value in confidence_values if value is None)
        missing_grade_count = sum(1 for value in grade_values if value is None)
        notes_count = sum(1 for trade_session in trade_sessions if trade_session.get("notes"))

        if missing_rule_count:
            concerns.append(f"{missing_rule_count} session(s) are missing rule adherence.")
        if missing_confidence_count:
            concerns.append(f"{missing_confidence_count} session(s) are missing confidence.")
        if missing_grade_count:
            concerns.append(f"{missing_grade_count} session(s) are missing usable grades.")
        if total_sessions > 0 and notes_count < max(2, total_sessions // 2):
            concerns.append("Notes/themes are limited, so behavior patterns may be under-evidenced.")

        if evidence_strength == "weak":
            delta = 0
            suggested_score = current_score
        else:
            max_change = 5 if evidence_strength == "moderate" else 15
            delta = max(-max_change, min(max_change, delta))
            suggested_score = _clamp_score(current_score + delta)

        if suggested_score > current_score:
            suggested_action = "Increase"
        elif suggested_score < current_score:
            suggested_action = "Decrease"
        else:
            suggested_action = "Hold"

        if suggested_action == "Hold":
            recommended_next_action = (
                "Hold the current Trading readiness score and keep logging complete sessions until repeated behavior is clearer."
            )
        elif suggested_action == "Increase":
            recommended_next_action = (
                f"Consider a manual Trading readiness increase to {suggested_score}% after reviewing the repeated evidence."
            )
        else:
            recommended_next_action = (
                f"Consider lowering Trading readiness to {suggested_score}% or reviewing the sessions before updating."
            )

        if not positive_signals:
            positive_signals.append("No strong positive readiness signal was found.")
        if not concerns:
            concerns.append("No major concerns found in the available sample.")

        return {
            "success": True,
            "event_id": event.get("id"),
            "readiness_id": trading_category.get("id"),
            "category_name": "Trading",
            "current_trading_readiness": current_score,
            "current_score": current_score,
            "suggested_action": suggested_action,
            "suggested_score": suggested_score,
            "evidence_strength": evidence_strength,
            "confidence": confidence_level,
            "confidence_level": confidence_level,
            "signals": {
                "recent_limit": parsed_limit,
                "total_sessions": total_sessions,
                "total_pnl": round(total_pnl, 2),
                "average_rule_adherence": (
                    round(average_rule_adherence, 1)
                    if average_rule_adherence is not None
                    else None
                ),
                "average_confidence": (
                    round(average_confidence, 1)
                    if average_confidence is not None
                    else None
                ),
                "recent_session_grades": recent_session_grades,
                "common_notes_themes": common_themes,
                "profitable_sessions": len(profitable_sessions),
                "losing_sessions": len(losing_sessions),
                "positive_pnl_rate": (
                    round(positive_pnl_rate, 2)
                    if positive_pnl_rate is not None
                    else None
                ),
                "disciplined_session_rate": (
                    round(disciplined_session_rate, 2)
                    if disciplined_session_rate is not None
                    else None
                ),
            },
            "positive_signals": positive_signals,
            "concerns": concerns,
            "reasons": positive_signals,
            "risks_missing_evidence": concerns,
            "recommended_next_action": recommended_next_action,
            "message": (
                f"Current Trading Readiness: {current_score}%. "
                f"Suggested Action: {suggested_action}. "
                f"Suggested Score: {suggested_score}%. "
                f"Evidence Strength: {evidence_strength}. "
                f"Confidence: {confidence_level}. "
                "No readiness value was updated."
            ),
        }
    except Exception as e:
        return {"success": False, "error": f"Unable to suggest Trading readiness update: {e}"}


def _get_latest_orbit_reviews(limit: int = 3) -> list[dict]:
    orbit_service.list_records("reviews")

    conn = get_orbit_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(reviews)")
        columns = {row["name"] for row in cursor.fetchall()}
        order_column = "created_at" if "created_at" in columns else "id"
        cursor.execute(
            f"SELECT * FROM reviews ORDER BY {order_column} DESC LIMIT ?",
            (limit,),
        )

        reviews = []
        for row in cursor.fetchall():
            review = dict(row)
            reviews.append({
                "id": review.get("id"),
                "title": review.get("title"),
                "review_type": review.get("review_type"),
                "summary": review.get("summary"),
                "rating": review.get("rating"),
                "created_at": review.get("created_at"),
            })
        return reviews
    finally:
        conn.close()


def create_orbit_review(
    review_type: str = "",
    title: str | None = None,
    summary: str | None = None,
    rating: str | int | float | None = None,
):
    if not review_type:
        return {"success": False, "error": "Missing required field: review_type."}

    parsed_rating, error = _parse_optional_float(rating, "rating")
    if error:
        return {"success": False, "error": error}

    try:
        review = orbit_service.create_review({
            "title": _orbit_text(title),
            "review_type": _orbit_text(review_type),
            "summary": _orbit_text(summary),
            "rating": parsed_rating,
        })

        return {
            "success": True,
            "review": _orbit_summary(
                review,
                ["id", "title", "review_type", "summary", "rating", "created_at"],
            ),
        }
    except Exception as e:
        return {"success": False, "error": f"Unable to create Orbit review: {e}"}


def get_orbit_reviews(limit: str | int | None = 10):
    parsed_limit, error = _parse_optional_int(limit, "limit")
    if error:
        return {"success": False, "error": error}

    if parsed_limit is None:
        parsed_limit = 10

    if parsed_limit < 1:
        return {"success": False, "error": "limit must be at least 1."}

    try:
        return {
            "success": True,
            "reviews": _get_latest_orbit_reviews(limit=parsed_limit),
        }
    except Exception as e:
        return {"success": False, "error": f"Unable to get Orbit reviews: {e}"}


def create_trade_session(
    session_date: str | None = None,
    symbol: str = "",
    pnl: str | int | float | None = None,
    notes: str | None = None,
    rule_adherence: str | int | None = None,
    confidence: str | int | None = None,
    session_grade: str | None = None,
    grade: str | None = None,
):
    if not symbol:
        return {"success": False, "error": "Missing required field: symbol."}

    if pnl is None or pnl == "":
        return {"success": False, "error": "Missing required field: pnl."}

    parsed_pnl, error = _parse_optional_float(pnl, "pnl")
    if error:
        return {"success": False, "error": error}

    parsed_rule_adherence, error = _parse_optional_int(rule_adherence, "rule_adherence")
    if error:
        return {"success": False, "error": error}
    if parsed_rule_adherence is not None and not 0 <= parsed_rule_adherence <= 100:
        return {"success": False, "error": "rule_adherence must be between 0 and 100."}

    parsed_confidence, error = _parse_optional_int(confidence, "confidence")
    if error:
        return {"success": False, "error": error}
    if parsed_confidence is not None and not 0 <= parsed_confidence <= 10:
        return {"success": False, "error": "confidence must be between 0 and 10."}

    trade_date = session_date or datetime.now().date().isoformat()
    resolved_grade = session_grade if session_grade is not None else grade

    try:
        trade_session = orbit_service.create_trade_session({
            "session_date": trade_date,
            "symbol": symbol.upper(),
            "pnl": parsed_pnl,
            "notes": _orbit_text(notes),
            "rule_adherence": parsed_rule_adherence,
            "confidence": parsed_confidence,
            "session_grade": _orbit_text(resolved_grade),
        })
        summary = _orbit_summary(
            trade_session,
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

        return {
            "success": True,
            "trade_session_id": trade_session.get("id"),
            "trade_session": summary,
            "message": (
                "Trade session logged successfully. "
                f"Saved session id {trade_session.get('id')} for "
                f"{trade_session.get('symbol')} on {trade_session.get('session_date')} "
                f"with PnL {trade_session.get('pnl')}."
            ),
        }
    except Exception as e:
        return {"success": False, "error": f"Unable to create trade session: {e}"}


def get_trade_sessions(limit: str | int | None = 10):
    parsed_limit, error = _parse_optional_int(limit, "limit")
    if error:
        return {"success": False, "error": error}

    if parsed_limit is None:
        parsed_limit = 10

    if parsed_limit < 1:
        return {"success": False, "error": "limit must be at least 1."}

    try:
        trade_sessions = orbit_service.list_trade_sessions()[:parsed_limit]
        return {
            "success": True,
            "trade_sessions": [
                _orbit_summary(
                    trade_session,
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
                for trade_session in trade_sessions
            ],
        }
    except Exception as e:
        return {"success": False, "error": f"Unable to get trade sessions: {e}"}


def generate_morning_briefing():
    try:
        return orbit_service.generate_morning_briefing()
    except Exception as e:
        return {
            "success": False,
            "error": f"Unable to generate morning briefing: {e}",
        }


def generate_daily_closeout():
    try:
        return orbit_service.generate_daily_closeout()
    except Exception as e:
        return {
            "success": False,
            "error": f"Unable to generate daily closeout: {e}",
        }


def generate_recommendations():
    try:
        return orbit_service.generate_recommendations()
    except Exception as e:
        return {
            "success": False,
            "error": f"Unable to generate recommendations: {e}",
        }


def generate_orbit_daily_summary():
    try:
        event = _get_corporate_escape_event()
        milestones = orbit_service.list_records("milestones")
        if event is not None:
            milestones = [
                milestone
                for milestone in milestones
                if milestone.get("major_event_id") == event.get("id")
            ]

        tasks = orbit_service.list_records("tasks")
        today = datetime.now().date()
        completed_today = []
        open_tasks = []

        for task in tasks:
            status = str(task.get("status") or "").casefold()
            if status == "completed":
                completed_at = _parse_orbit_datetime(task.get("completed_at"))
                if completed_at is not None and completed_at.date() == today:
                    completed_today.append(
                        _orbit_summary(task, ["id", "title", "status", "completed_at"])
                    )
            else:
                prioritized_task = orbit_service._with_linked_milestones(task)
                open_tasks.append(
                    _orbit_summary(
                        prioritized_task,
                        [
                            "id",
                            "title",
                            "status",
                            "due_date",
                            "priority_score",
                            "priority_factors",
                        ],
                    )
                )

        open_tasks = sorted(
            open_tasks,
            key=orbit_service._priority_sort_key,
        )

        key_milestones = [
            _orbit_summary(
                milestone,
                ["id", "title", "status", "progress_percent", "due_date"],
            )
            for milestone in milestones
        ]
        latest_reviews = _get_latest_orbit_reviews(limit=3)

        progress_snapshot = {
            "event_title": event.get("title") if event else ORBIT_CORPORATE_ESCAPE_TITLE,
            "status": event.get("status") if event else "not_found",
            "progress_percent": event.get("progress_percent") if event else None,
            "target_date": event.get("target_date") if event else None,
        }
        suggested_review_prompt = (
            "What moved Corporate Escape forward today, what stayed open, "
            "and what is the single highest-leverage next action for tomorrow?"
        )
        completed_lines = [
            f"- {task.get('title')}"
            for task in completed_today[:5]
        ] or ["- None logged today"]
        open_lines = [
            f"- {task.get('title')} (P{task.get('priority_score')})"
            for task in open_tasks[:5]
        ] or ["- No priority tasks"]
        milestone_lines = [
            f"- {milestone.get('title')}: {milestone.get('status')} ({milestone.get('progress_percent')}%)"
            for milestone in key_milestones[:5]
        ] or ["- No milestones found"]
        review_lines = [
            f"- {review.get('title') or review.get('review_type')}: {review.get('summary') or 'No summary'}"
            for review in latest_reviews
        ] or ["- No recent reviews"]
        message = (
            "## Orbit Daily Summary\n\n"
            f"**Progress:** {progress_snapshot['event_title']} is "
            f"{progress_snapshot['status']} at {progress_snapshot['progress_percent']}%.\n\n"
            "**Completed today:**\n"
            + "\n".join(completed_lines)
            + "\n\n**Still open:**\n"
            + "\n".join(open_lines)
            + "\n\n**Key milestones:**\n"
            + "\n".join(milestone_lines)
            + "\n\n**Latest reviews:**\n"
            + "\n".join(review_lines)
            + f"\n\n**Review prompt:** {suggested_review_prompt}"
        )

        return {
            "success": True,
            "progress_snapshot": progress_snapshot,
            "completed_today": completed_today,
            "still_open": open_tasks,
            "key_milestones": key_milestones,
            "latest_reviews": latest_reviews,
            "suggested_review_prompt": suggested_review_prompt,
            "message": message,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unable to generate Orbit daily summary: {e}",
        }


def _is_orbit_complete(record: dict) -> bool:
    return str(record.get("status") or "").casefold() in {
        "complete",
        "completed",
        "done",
    }


def _is_orbit_active(record: dict) -> bool:
    return str(record.get("status") or "").casefold() in {
        "active",
        "in_progress",
        "not_started",
        "queued",
    }


def _days_until(value: str | None) -> int | None:
    parsed_date = _parse_orbit_date(value)
    if parsed_date is None:
        return None

    return (parsed_date - datetime.now().date()).days


def _score_orbit_task(
    task: dict,
    goal: dict | None,
    milestone: dict | None,
    event: dict | None,
) -> int:
    score = 0

    if event is not None and _is_orbit_active(event):
        score += 25

    if milestone is not None:
        status = str(milestone.get("status") or "").casefold()
        if status == "in_progress":
            score += 24
        elif status == "active":
            score += 18
        elif status in {"not_started", "queued"}:
            score += 8

        progress = milestone.get("progress_percent")
        if isinstance(progress, int) and progress < 100:
            score += max(0, 20 - progress // 5)

        days_to_milestone = _days_until(milestone.get("due_date"))
        if days_to_milestone is not None:
            if days_to_milestone < 0:
                score += 25
            elif days_to_milestone <= 7:
                score += 20
            elif days_to_milestone <= 30:
                score += 10

    if goal is not None:
        try:
            score += int(goal.get("priority") or 0) * 6
        except (TypeError, ValueError):
            pass

    task_status = str(task.get("status") or "").casefold()
    if task_status == "in_progress":
        score += 18
    elif task_status == "active":
        score += 12
    elif task_status in {"not_started", "queued"}:
        score += 5

    days_to_task = _days_until(task.get("due_date"))
    if days_to_task is not None:
        if days_to_task < 0:
            score += 35
        elif days_to_task == 0:
            score += 30
        elif days_to_task <= 3:
            score += 20
        elif days_to_task <= 7:
            score += 10

    return score


def _format_orbit_task_action(task_context: dict) -> str:
    task = task_context["task"]
    milestone = task_context.get("milestone")
    action = task.get("title") or "Untitled Orbit task"

    if milestone and milestone.get("title"):
        return f"{action} ({milestone.get('title')})"

    return action


def _suggest_orbit_blocker(
    active_events: list[dict],
    incomplete_tasks: list[dict],
    milestones: list[dict],
    latest_reviews: list[dict],
) -> str:
    today = datetime.now().date()
    overdue_tasks = []

    for task in incomplete_tasks:
        due_date = _parse_orbit_date(task.get("due_date"))
        if due_date is not None and due_date < today:
            overdue_tasks.append(task)

    if overdue_tasks:
        return f"{len(overdue_tasks)} overdue Orbit task(s) are competing for attention."

    stalled_milestones = [
        milestone
        for milestone in milestones
        if not _is_orbit_complete(milestone)
        and int(milestone.get("progress_percent") or 0) == 0
        and str(milestone.get("status") or "").casefold() in {"active", "in_progress"}
    ]
    if stalled_milestones:
        return f"Milestone momentum is thin: {stalled_milestones[0].get('title')} is active but still at 0%."

    if not incomplete_tasks:
        return "No incomplete Orbit tasks are available to pull the plan forward."

    if not latest_reviews:
        return "There are no recent Orbit reviews, so today's focus has limited reflection context."

    if not active_events:
        return "No active major event is available, so task priority is less anchored."

    return "No active blockers"


def generate_orbit_focus():
    try:
        major_events = orbit_service.list_records("major_events")
        goals = orbit_service.list_records("goals")
        milestones = orbit_service.list_records("milestones")
        tasks = orbit_service.list_records("tasks")
        latest_reviews = _get_latest_orbit_reviews(limit=3)

        active_events = [
            event
            for event in major_events
            if _is_orbit_active(event) and not _is_orbit_complete(event)
        ]
        incomplete_tasks = [
            task
            for task in tasks
            if not _is_orbit_complete(task)
        ]

        goals_by_id = {goal.get("id"): goal for goal in goals}
        milestones_by_id = {milestone.get("id"): milestone for milestone in milestones}
        active_event_ids = {event.get("id") for event in active_events}

        task_contexts = []
        for task in incomplete_tasks:
            goal = goals_by_id.get(task.get("goal_id"))
            milestone = milestones_by_id.get(goal.get("milestone_id")) if goal else None
            event = None
            if milestone:
                event = next(
                    (
                        active_event
                        for active_event in active_events
                        if active_event.get("id") == milestone.get("major_event_id")
                    ),
                    None,
                )

            task_contexts.append({
                "score": _score_orbit_task(task, goal, milestone, event),
                "task": task,
                "goal": goal,
                "milestone": milestone,
                "major_event": event,
            })

        task_contexts.sort(
            key=lambda context: (
                context["score"],
                -(_days_until(context["task"].get("due_date")) or 9999),
                int(context["task"].get("id") or 0) * -1,
            ),
            reverse=True,
        )

        top_context = task_contexts[0] if task_contexts else None
        top_actions = [
            _format_orbit_task_action(context)
            for context in task_contexts[:3]
        ]

        active_milestones = [
            milestone
            for milestone in milestones
            if milestone.get("major_event_id") in active_event_ids
            and not _is_orbit_complete(milestone)
        ]
        active_milestones.sort(
            key=lambda milestone: (
                str(milestone.get("status") or "").casefold() != "in_progress",
                _days_until(milestone.get("due_date")) is None,
                _days_until(milestone.get("due_date")) or 9999,
                -(int(milestone.get("progress_percent") or 0)),
            )
        )

        suggested_milestone = None
        if top_context and top_context.get("milestone"):
            suggested_milestone = top_context["milestone"]
        elif active_milestones:
            suggested_milestone = active_milestones[0]

        highest_leverage_priority = (
            _format_orbit_task_action(top_context)
            if top_context
            else "No suggested action yet"
        )

        biggest_blocker = _suggest_orbit_blocker(
            active_events,
            incomplete_tasks,
            milestones,
            latest_reviews,
        )

        suggested_next_milestone = (
            {
                "id": suggested_milestone.get("id"),
                "title": suggested_milestone.get("title"),
                "status": suggested_milestone.get("status"),
                "progress_percent": suggested_milestone.get("progress_percent"),
                "due_date": suggested_milestone.get("due_date"),
            }
            if suggested_milestone
            else None
        )

        suggested_milestone_title = (
            suggested_next_milestone["title"]
            if suggested_next_milestone
            else "No suggested action yet"
        )
        action_lines = [
            f"{index}. {action}"
            for index, action in enumerate(top_actions[:3], start=1)
        ] or ["No priority tasks"]
        message = (
            "## Today’s Orbit Focus\n\n"
            f"**Highest leverage priority:** {highest_leverage_priority}\n\n"
            "**Top 3 actions:**\n"
            + "\n".join(action_lines)
            + f"\n\n**Biggest blocker:** {biggest_blocker}\n\n"
            f"**Suggested next milestone:** {suggested_milestone_title}"
        )

        return {
            "success": True,
            "highest_leverage_priority": highest_leverage_priority,
            "top_3_actions_for_today": top_actions[:3],
            "biggest_blocker": biggest_blocker,
            "suggested_next_milestone": suggested_next_milestone,
            "source_data": {
                "active_major_events": [
                    _orbit_summary(
                        event,
                        ["id", "title", "status", "progress_percent", "target_date"],
                    )
                    for event in active_events
                ],
                "incomplete_tasks": [
                    _orbit_summary(task, ["id", "title", "status", "due_date", "goal_id"])
                    for task in incomplete_tasks
                ],
                "milestones": [
                    _orbit_summary(
                        milestone,
                        ["id", "title", "status", "progress_percent", "due_date", "major_event_id"],
                    )
                    for milestone in milestones
                ],
                "latest_reviews": latest_reviews,
            },
            "message": message,
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Unable to generate Orbit focus: {e}",
        }


# ---------------------------------------------------------------------
# TradingView capture / CSV refresh
# ---------------------------------------------------------------------

def get_tradingview_profile_dir():
    return os.path.join(BASE_DIR, "playwright_tradingview_profile")


def capture_tradingview(symbol: str = "MNQ", timeframe: str | None = None):
    try:
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        symbol = symbol.upper()
        timeframe = timeframe.upper() if timeframe else None

        suffix = f"_{timeframe.upper()}" if timeframe else ""
        screenshot_path = os.path.join(
            SCREENSHOTS_DIR,
            f"{symbol}{suffix}_{timestamp}.png",
        )

        config = get_symbol_config(symbol)
        tv_symbol = config["tv_symbol"]
        profile_dir = get_tradingview_profile_dir()

        capture_timeframes = {**TRADINGVIEW_TIMEFRAMES, "5M": "5"}
        interval = capture_timeframes.get(timeframe) if timeframe else None
        chart_url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}"

        if interval:
            chart_url += f"&interval={interval}"

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                viewport={"width": 1600, "height": 900},
                accept_downloads=True,
            )

            page = context.pages[0] if context.pages else context.new_page()
            page.goto(chart_url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(15000)
            page.screenshot(path=screenshot_path, full_page=False)

            context.close()

        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "tv_symbol": tv_symbol,
            "screenshot_path": screenshot_path,
            "message": f"TradingView screenshot captured: {screenshot_path}",
        }

    except Exception as e:
        return {
            "success": False,
            "symbol": symbol,
            "timeframe": timeframe,
            "error": str(e),
            "message": f"TradingView capture failed: {e}",
        }


def setup_tradingview_profile():
    profile_dir = get_tradingview_profile_dir()
    os.makedirs(profile_dir, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            viewport={"width": 1600, "height": 900},
            accept_downloads=True,
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.tradingview.com/chart/", wait_until="domcontentloaded")

        print("\nTradingView browser is open.")
        print("Log in, load your layout, and make sure CSV export is available.")
        print("You have 5 minutes...")

        page.wait_for_timeout(300000)
        context.close()

    return {
        "success": True,
        "message": "TradingView profile setup complete.",
        "profile_dir": profile_dir,
    }


def set_tradingview_interval(page, timeframe: str):
    interval = TRADINGVIEW_TIMEFRAMES[timeframe]

    # Best-effort URL interval control. TradingView usually respects interval query param
    # after page navigation. If not, the active chart layout may override it.
    return interval


def _try_open_export_menu(page):
    """
    Best-effort TradingView export opener.

    TradingView changes UI often. This tries common paths but returns False
    instead of crashing if selectors fail.
    """
    candidates = [
        "button[aria-label*='More']",
        "button[aria-label*='Menu']",
        "button[data-name='header-toolbar-more']",
    ]

    for selector in candidates:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0:
                locator.click(timeout=3000)
                page.wait_for_timeout(1000)
                return True
        except Exception:
            continue

    try:
        page.keyboard.press("Alt+F")
        page.wait_for_timeout(1000)
        return True
    except Exception:
        return False


def _try_click_export_chart_data(page):
    export_texts = [
        "Export chart data",
        "Export data",
        "Export",
    ]

    for text in export_texts:
        try:
            item = page.get_by_text(text, exact=False).first
            if item.count() > 0:
                item.click(timeout=3000)
                page.wait_for_timeout(1000)
                return True
        except Exception:
            continue

    return False


def _save_export_debug_screenshot(page, symbol: str, timeframe: str, reason: str) -> str | None:
    try:
        clean_reason = re.sub(r"[^a-zA-Z0-9_-]+", "_", reason).strip("_")[:60] or "failure"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = DEBUG_EXPORTS_DIR / f"{symbol}_{timeframe}_{clean_reason}_{timestamp}.png"
        page.screenshot(path=str(path), full_page=False)
        return str(path)
    except Exception:
        return None


def _locator_is_top_chart_toolbar_target(page, locator) -> bool:
    try:
        box = locator.bounding_box(timeout=1500)
    except Exception:
        box = None

    if not box:
        return False

    viewport = page.viewport_size or {"width": 1600, "height": 900}

    # The chart layout dropdown lives in the top toolbar, away from the logo
    # and away from the profile/account area on the far right.
    if box["y"] > 140:
        return False
    if box["x"] < 80:
        return False
    if box["x"] > viewport["width"] - 260:
        return False

    return True


def _click_first_top_chart_toolbar_target(page, candidates: list) -> bool:
    for locator in candidates:
        try:
            count = min(locator.count(), 5)
        except Exception:
            continue

        for index in range(count):
            item = locator.nth(index)
            try:
                if not item.is_visible(timeout=1000):
                    continue
                if not _locator_is_top_chart_toolbar_target(page, item):
                    continue

                item.click(timeout=5000)
                page.wait_for_timeout(750)
                return True
            except Exception:
                continue

    return False


def _visible_menu_item_texts(page) -> list[str]:
    texts = []
    candidates = [
        page.locator("[role='menuitem']"),
        page.locator("[data-name*='menu']"),
    ]

    for locator in candidates:
        try:
            count = min(locator.count(), 20)
        except Exception:
            continue

        for index in range(count):
            try:
                item = locator.nth(index)
                if item.is_visible(timeout=500):
                    text = " ".join(item.inner_text(timeout=1000).split())
                    if text and text not in texts:
                        texts.append(text)
            except Exception:
                continue

    return texts[:20]


def _click_tradingview_layout_dropdown(page) -> dict:
    logs = []
    layout_name_pattern = re.compile(r"Trade day(?:\s+\d{1,2}/\d{1,2})?", re.I)

    layout_name = page.get_by_text(layout_name_pattern).first
    try:
        if layout_name.count() > 0 and layout_name.is_visible(timeout=2000):
            found_text = " ".join(layout_name.inner_text(timeout=1000).split())
            logs.append(f"found layout name: {found_text}")

            anchored_candidates = [
                layout_name.locator("xpath=ancestor-or-self::*[self::button][1]"),
                layout_name.locator("xpath=ancestor::*[self::button][1]"),
                layout_name.locator("xpath=ancestor::*[contains(@data-name, 'layout')][1]"),
                layout_name.locator("xpath=ancestor::*[1]/following-sibling::button[1]"),
                layout_name.locator("xpath=ancestor::*[1]//button").last,
                layout_name.locator("xpath=following::button[1]"),
            ]

            if _click_first_top_chart_toolbar_target(page, anchored_candidates):
                logs.append("clicked chart layout dropdown")
                logs.append(f"menu items visible after click: {_visible_menu_item_texts(page)}")
                return {"success": True, "logs": logs}
    except Exception as e:
        logs.append(f"layout-name anchored selector failed: {e}")

    logs.append("layout name not found; trying scoped top-toolbar layout selectors")

    top_toolbar = page.locator(
        "[data-name='top-toolbar'], [data-name='header-toolbar'], "
        ".chart-toolbar, .layout__area--top"
    )
    scoped_candidates = [
        top_toolbar.locator("button[data-name='header-toolbar-layouts']"),
        top_toolbar.locator("[data-name='header-toolbar-layouts']"),
        top_toolbar.get_by_role("button", name=re.compile(r"Manage layouts", re.I)),
        top_toolbar.get_by_role("button", name=re.compile(r"Trade day", re.I)),
        page.locator("button[data-name='header-toolbar-layouts']"),
        page.locator("[data-name='header-toolbar-layouts']"),
    ]

    if _click_first_top_chart_toolbar_target(page, scoped_candidates):
        logs.append("clicked chart layout dropdown")
        logs.append(f"menu items visible after click: {_visible_menu_item_texts(page)}")
        return {"success": True, "logs": logs}

    logs.append("chart layout dropdown not found in top toolbar")
    return {"success": False, "logs": logs}


def _click_download_chart_data_menu_item(page) -> bool:
    candidates = [
        page.get_by_role("menuitem", name=re.compile(r"Download chart data", re.I)).first,
        page.get_by_text(re.compile(r"Download chart data", re.I)).first,
        page.locator("text=/Download chart data/i").first,
    ]

    for locator in candidates:
        try:
            if locator.count() > 0:
                locator.click(timeout=5000)
                page.wait_for_timeout(750)
                return True
        except Exception:
            continue

    return False


def _wait_for_download_chart_data_modal(page) -> bool:
    candidates = [
        page.get_by_role("heading", name=re.compile(r"Download chart data", re.I)).first,
        page.get_by_role("dialog").filter(has_text=re.compile(r"Download chart data", re.I)).first,
        page.get_by_text(re.compile(r"Download chart data", re.I)).first,
    ]

    for locator in candidates:
        try:
            locator.wait_for(state="visible", timeout=8000)
            return True
        except Exception:
            continue

    return False


def _download_chart_data_button(page):
    dialog = page.get_by_role("dialog").filter(has_text=re.compile(r"Download chart data", re.I)).first

    candidates = [
        dialog.get_by_role("button", name=re.compile(r"^Download$", re.I)).first,
        page.get_by_role("button", name=re.compile(r"^Download$", re.I)).first,
        page.locator("button:has-text('Download')").last,
    ]

    for locator in candidates:
        try:
            if locator.count() > 0:
                return locator
        except Exception:
            continue

    return None


def _download_snapshot(downloads_dir: Path = USER_DOWNLOADS_DIR) -> set[Path]:
    downloads_dir.mkdir(parents=True, exist_ok=True)
    return {path.resolve() for path in downloads_dir.iterdir() if path.is_file()}


def _completed_csv_candidates(downloads_dir: Path, snapshot: set[Path]) -> list[Path]:
    candidates = []

    for path in downloads_dir.glob("*.csv"):
        resolved = path.resolve()

        if resolved in snapshot:
            continue

        if path.name.endswith((".crdownload", ".download", ".tmp")):
            continue

        candidates.append(path)

    return sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)


def _wait_for_new_downloaded_csv(
    snapshot: set[Path],
    timeout_seconds: int = TRADINGVIEW_EXPORT_DOWNLOAD_TIMEOUT_SECONDS,
    downloads_dir: Path = USER_DOWNLOADS_DIR,
) -> tuple[Path | None, list[Path]]:
    deadline = time.time() + timeout_seconds

    while time.time() < deadline:
        candidates = _completed_csv_candidates(downloads_dir, snapshot)

        if candidates:
            selected = candidates[0]
            last_size = -1

            for _ in range(5):
                current_size = selected.stat().st_size
                if current_size > 0 and current_size == last_size:
                    return selected, candidates

                last_size = current_size
                time.sleep(0.5)

        time.sleep(0.5)

    return None, []


def move_new_downloaded_csv_to_temp(
    symbol: str,
    timeframe: str,
    temp_dir: Path,
    snapshot: set[Path],
    downloads_dir: Path = USER_DOWNLOADS_DIR,
    timeout_seconds: int = TRADINGVIEW_EXPORT_DOWNLOAD_TIMEOUT_SECONDS,
) -> dict:
    symbol = symbol.upper()
    timeframe = timeframe.upper()
    temp_dir.mkdir(parents=True, exist_ok=True)

    downloaded_path, new_csvs = _wait_for_new_downloaded_csv(
        snapshot=snapshot,
        timeout_seconds=timeout_seconds,
        downloads_dir=downloads_dir,
    )

    if not downloaded_path:
        return {
            "success": False,
            "symbol": symbol,
            "timeframe": timeframe,
            "downloads_dir": str(downloads_dir),
            "error": (
                f"No new CSV appeared in {downloads_dir} within "
                f"{timeout_seconds} seconds."
            ),
            "new_csvs": [],
        }

    final_path = temp_dir / f"{symbol}_{timeframe}.csv"
    if final_path.exists():
        final_path.unlink()

    shutil.move(str(downloaded_path), final_path)

    return {
        "success": True,
        "symbol": symbol,
        "timeframe": timeframe,
        "downloads_dir": str(downloads_dir),
        "downloaded_path": str(downloaded_path),
        "temp_path": str(final_path),
        "new_csvs": [str(path) for path in new_csvs],
        "warning": (
            f"Multiple new CSV downloads appeared; used newest: {downloaded_path.name}"
            if len(new_csvs) > 1
            else None
        ),
    }


def export_tradingview_csv(symbol: str, timeframe: str, temp_dir: Path) -> dict:
    """
    Export one TradingView chart CSV through the confirmed layout dropdown flow.

    Playwright's download event is primary because persistent browser profiles do
    not always write downloads to the user's normal ~/Downloads folder.
    """
    symbol = symbol.upper()
    timeframe = timeframe.upper()
    temp_dir = Path(temp_dir)
    final_path = temp_dir / f"{symbol}_{timeframe}.csv"
    logs = []

    try:
        interval = TRADINGVIEW_TIMEFRAMES.get(timeframe)
        if not interval:
            return {
                "success": False,
                "symbol": symbol,
                "timeframe": timeframe,
                "logs": logs,
                "error": f"Unsupported TradingView timeframe: {timeframe}",
            }

        config = get_symbol_config(symbol)
        tv_symbol = config["tv_symbol"]
        profile_dir = get_tradingview_profile_dir()
        snapshot = _download_snapshot(USER_DOWNLOADS_DIR)
        logs.append(f"{timeframe}: existing downloads snapshot count: {len(snapshot)}")
        chart_url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}&interval={interval}"
        temp_dir.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                viewport={"width": 1600, "height": 900},
                accept_downloads=True,
            )

            page = context.pages[0] if context.pages else context.new_page()
            page.bring_to_front()
            page.goto(chart_url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(12000)

            layout_click = _click_tradingview_layout_dropdown(page)
            logs.extend(f"{timeframe}: {message}" for message in layout_click.get("logs") or [])

            if not layout_click.get("success"):
                screenshot_path = _save_export_debug_screenshot(
                    page,
                    symbol,
                    timeframe,
                    "layout_dropdown_not_found",
                )
                context.close()
                return {
                    "success": False,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "logs": logs + [
                        f"{timeframe}: failed to click layout dropdown",
                        *([f"{timeframe}: failure screenshot: {screenshot_path}"] if screenshot_path else []),
                    ],
                    "error": (
                        "Could not find TradingView layout dropdown / Manage layouts button. "
                        "UI may have changed or export may require manual action."
                    ),
                    "debug_screenshot": screenshot_path,
                }

            if not _click_download_chart_data_menu_item(page):
                screenshot_path = _save_export_debug_screenshot(
                    page,
                    symbol,
                    timeframe,
                    "download_chart_data_menu_not_found",
                )
                context.close()
                return {
                    "success": False,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "logs": logs + [
                        f"{timeframe}: failed to click Download chart data",
                        *([f"{timeframe}: failure screenshot: {screenshot_path}"] if screenshot_path else []),
                    ],
                    "error": "Could not find TradingView menu item: Download chart data...",
                    "debug_screenshot": screenshot_path,
                }

            logs.append(f"{timeframe}: clicked Download chart data")

            if not _wait_for_download_chart_data_modal(page):
                screenshot_path = _save_export_debug_screenshot(
                    page,
                    symbol,
                    timeframe,
                    "download_chart_data_modal_not_found",
                )
                context.close()
                return {
                    "success": False,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "logs": logs + [
                        f"{timeframe}: Download chart data modal did not appear",
                        *([f"{timeframe}: failure screenshot: {screenshot_path}"] if screenshot_path else []),
                    ],
                    "error": "TradingView Download chart data modal did not appear.",
                    "debug_screenshot": screenshot_path,
                }

            logs.append(f"{timeframe}: modal appeared")

            download_button = _download_chart_data_button(page)
            if not download_button:
                screenshot_path = _save_export_debug_screenshot(
                    page,
                    symbol,
                    timeframe,
                    "modal_download_button_not_found",
                )
                context.close()
                return {
                    "success": False,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "logs": logs + [
                        f"{timeframe}: modal Download button not found",
                        *([f"{timeframe}: failure screenshot: {screenshot_path}"] if screenshot_path else []),
                    ],
                    "error": "TradingView Download chart data modal opened, but Download button was not found.",
                    "debug_screenshot": screenshot_path,
                }

            try:
                with page.expect_download(timeout=TRADINGVIEW_EXPORT_DOWNLOAD_TIMEOUT_SECONDS * 1000) as download_info:
                    download_button.click(timeout=5000)

                download = download_info.value
                logs.append(f"{timeframe}: download event captured")

                if final_path.exists():
                    final_path.unlink()

                download.save_as(str(final_path))
                logs.append(f"{timeframe}: saved CSV path: {final_path}")
                context.close()

                return {
                    "success": True,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "downloaded_path": download.suggested_filename,
                    "temp_path": str(final_path),
                    "logs": logs,
                }

            except PlaywrightTimeoutError:
                logs.append(
                    f"{timeframe}: Playwright download event timed out; checking Downloads fallback"
                )

                handoff = move_new_downloaded_csv_to_temp(
                    symbol=symbol,
                    timeframe=timeframe,
                    temp_dir=temp_dir,
                    snapshot=snapshot,
                    downloads_dir=USER_DOWNLOADS_DIR,
                )
                if not handoff.get("success"):
                    screenshot_path = _save_export_debug_screenshot(
                        page,
                        symbol,
                        timeframe,
                        "download_event_and_fallback_failed",
                    )
                    if screenshot_path:
                        handoff["debug_screenshot"] = screenshot_path
                        logs.append(f"{timeframe}: failure screenshot: {screenshot_path}")

                context.close()

                if not handoff.get("success"):
                    logs.append(f"{timeframe}: {handoff.get('error')}")
                    handoff["logs"] = logs
                    return handoff

                logs.append(f"{timeframe}: downloaded file detected: {handoff['downloaded_path']}")
                if handoff.get("warning"):
                    logs.append(f"{timeframe}: warning: {handoff['warning']}")
                logs.append(f"{timeframe}: saved CSV path: {handoff['temp_path']}")
                handoff["logs"] = logs
                return handoff

            except Exception as e:
                screenshot_path = _save_export_debug_screenshot(
                    page,
                    symbol,
                    timeframe,
                    "download_click_failed",
                )
                context.close()

                return {
                    "success": False,
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "logs": logs + [
                        f"{timeframe}: failed while clicking modal Download: {e}",
                        *([f"{timeframe}: failure screenshot: {screenshot_path}"] if screenshot_path else []),
                    ],
                    "error": f"TradingView modal Download click failed: {e}",
                    "debug_screenshot": screenshot_path,
                }

    except Exception as e:
        return {
            "success": False,
            "symbol": symbol,
            "timeframe": timeframe,
            "logs": logs,
            "error": str(e),
            "message": f"TradingView CSV export failed for {symbol} {timeframe}: {e}",
        }


def _normalize_downloaded_csv(download_path: str, symbol: str, timeframe: str, destination_dir: str | None = None):
    clean_name = f"{symbol.upper()}_{timeframe.upper()}.csv"
    if destination_dir:
        os.makedirs(destination_dir, exist_ok=True)
        destination = os.path.abspath(os.path.join(destination_dir, clean_name))
        destination_root = os.path.abspath(destination_dir)

        if os.path.commonpath([destination, destination_root]) != destination_root:
            raise ValueError("Access denied: outside CSV export directory")
    else:
        destination = safe_path(clean_name)

    shutil.copyfile(download_path, destination)

    return clean_name


def export_market_csvs_to_directory(symbol: str = "MNQ", output_dir: str | None = None, timeframes: list[str] | None = None):
    """
    Best-effort TradingView CSV export into output_dir.

    This depends on TradingView UI and account permissions.
    If output_dir is omitted, files are written into backend/csv_data using:
        MNQ_1D.csv
        MNQ_4H.csv
        MNQ_1H.csv
        MNQ_15M.csv
        MNQ_5M.csv
        MNQ_1M.csv
    """
    symbol = symbol.upper()
    requested_timeframes = [item.upper() for item in (timeframes or list(TRADINGVIEW_TIMEFRAMES.keys()))]

    try:
        config = get_symbol_config(symbol)
        tv_symbol = config["tv_symbol"]
        profile_dir = get_tradingview_profile_dir()
        output_dir = output_dir or CSV_DATA_DIR

        exported = {}
        failures = {}

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                viewport={"width": 1600, "height": 900},
                accept_downloads=True,
            )

            page = context.pages[0] if context.pages else context.new_page()

            for timeframe in requested_timeframes:
                interval = TRADINGVIEW_TIMEFRAMES.get(timeframe)

                if not interval:
                    failures[timeframe] = f"Unsupported TradingView timeframe: {timeframe}"
                    continue

                chart_url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}&interval={interval}"

                try:
                    page.goto(chart_url, wait_until="domcontentloaded", timeout=90000)
                    page.wait_for_timeout(12000)

                    opened = _try_open_export_menu(page)
                    clicked = _try_click_export_chart_data(page)

                    if not opened or not clicked:
                        failures[timeframe] = (
                            "Could not find TradingView export menu/button. "
                            "UI may have changed or export may require manual action."
                        )
                        continue

                    try:
                        with page.expect_download(timeout=15000) as download_info:
                            # Some TradingView dialogs require confirming export.
                            for label in ["Export", "Download", "Save"]:
                                try:
                                    confirm = page.get_by_text(label, exact=False).first
                                    if confirm.count() > 0:
                                        confirm.click(timeout=3000)
                                        break
                                except Exception:
                                    pass

                        download = download_info.value
                        temp_path = os.path.join(
                            DOWNLOADS_DIR,
                            f"{symbol}_{timeframe}_{int(time.time())}.csv",
                        )
                        download.save_as(temp_path)

                        clean_name = _normalize_downloaded_csv(
                            temp_path,
                            symbol=symbol,
                            timeframe=timeframe,
                            destination_dir=output_dir,
                        )

                        exported[timeframe] = clean_name

                    except PlaywrightTimeoutError:
                        failures[timeframe] = (
                            "Export dialog opened, but no CSV download was detected."
                        )

                except Exception as e:
                    failures[timeframe] = str(e)

            context.close()

        success = len(exported) > 0

        return {
            "success": success,
            "implemented": True,
            "symbol": symbol,
            "output_dir": output_dir,
            "exported": exported,
            "failures": failures,
            "message": (
                f"CSV refresh completed. Exported: {exported}. Failures: {failures}"
                if success
                else (
                    "CSV refresh failed. TradingView export automation is brittle. "
                    "Manually export CSVs into backend/csv_data as SYMBOL_1D.csv, "
                    "SYMBOL_4H.csv, SYMBOL_1H.csv, SYMBOL_15M.csv, SYMBOL_5M.csv, SYMBOL_1M.csv."
                )
            ),
        }

    except Exception as e:
        return {
            "success": False,
            "symbol": symbol,
            "error": str(e),
            "message": f"CSV refresh failed: {e}",
        }


def refresh_market_csvs(symbol: str = "MNQ"):
    return export_market_csvs_to_directory(symbol=symbol, output_dir=CSV_DATA_DIR)


# ---------------------------------------------------------------------
# CSV / market state engine
# ---------------------------------------------------------------------

def load_market_csv(path: str):
    full_path = safe_path(path)
    df = pd.read_csv(full_path)

    df.columns = [col.lower().strip() for col in df.columns]

    required = ["open", "high", "low", "close"]

    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df = df.dropna(subset=required)

    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=required)

    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
        df["time"] = df["time"].dt.tz_localize(None)
        df = df.dropna(subset=["time"])
        df = df.sort_values("time")

    return df


def resolve_market_csv(symbol: str, timeframe: str):
    symbol = symbol.upper()
    timeframe = timeframe.upper()

    config = get_symbol_config(symbol)

    clean_name = f"{config['csv_prefix']}_{timeframe}.csv"
    tv_tf = TRADINGVIEW_TIMEFRAMES.get(timeframe)

    possible_names = [clean_name]

    if tv_tf:
        possible_names.append(f"{config['csv_root']}, {tv_tf}.csv")
        possible_names.append(f"{config['csv_root']},{tv_tf}.csv")

    for name in possible_names:
        full_path = safe_path(name)
        if os.path.exists(full_path):
            return name

    raise FileNotFoundError(
        f"No CSV found for {symbol} {timeframe}. Tried: {possible_names}"
    )


def classify_location(current_price: float, low: float, high: float):
    if current_price < low:
        return "above_price"
    if current_price > high:
        return "below_price"
    return "inside_zone"


def zone_relation_to_price(current_price: float, low: float, high: float):
    if current_price < low:
        return "overhead"
    if current_price > high:
        return "below_market"
    return "inside"


def get_csv_freshness(df, timeframe: str) -> dict:
    timeframe = timeframe.upper()
    threshold_minutes = CSV_STALENESS_THRESHOLDS_MINUTES.get(timeframe)

    if "time" not in df.columns:
        return {
            "timeframe": timeframe,
            "latest_csv_time": None,
            "age_minutes": None,
            "threshold_minutes": threshold_minutes,
            "is_stale": True,
            "stale_reason": "CSV has no time column; freshness cannot be verified.",
        }

    latest_time = df["time"].max()

    if pd.isna(latest_time):
        return {
            "timeframe": timeframe,
            "latest_csv_time": None,
            "age_minutes": None,
            "threshold_minutes": threshold_minutes,
            "is_stale": True,
            "stale_reason": "CSV time column has no valid timestamps.",
        }

    latest_time = latest_time.to_pydatetime() if hasattr(latest_time, "to_pydatetime") else latest_time
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    age_minutes = max((now_utc - latest_time).total_seconds() / 60, 0)

    is_stale = threshold_minutes is not None and age_minutes > threshold_minutes
    stale_reason = None

    if is_stale:
        stale_reason = (
            f"{timeframe} CSV latest row is {round(age_minutes, 1)} minutes old; "
            f"threshold is {threshold_minutes} minutes."
        )

    return {
        "timeframe": timeframe,
        "latest_csv_time": f"{latest_time.isoformat()}Z",
        "age_minutes": round(age_minutes, 1),
        "threshold_minutes": threshold_minutes,
        "is_stale": is_stale,
        "stale_reason": stale_reason,
    }


def analyze_dataframe(df):
    current_price = float(df.iloc[-1]["close"])

    recent_20 = df.tail(20)
    recent_50 = df.tail(50)

    recent_high_20 = float(recent_20["high"].max())
    recent_low_20 = float(recent_20["low"].min())
    recent_high_50 = float(recent_50["high"].max())
    recent_low_50 = float(recent_50["low"].min())

    avg_range = float((df["high"] - df["low"]).tail(20).mean())

    if current_price > recent_high_20:
        bias = "bullish"
        structure = "bullish_breakout"
    elif current_price < recent_low_20:
        bias = "bearish"
        structure = "bearish_breakdown"
    elif recent_20["close"].iloc[-1] > recent_20["close"].iloc[0]:
        bias = "bullish"
        structure = "bullish_internal_structure"
    elif recent_20["close"].iloc[-1] < recent_20["close"].iloc[0]:
        bias = "bearish"
        structure = "bearish_internal_structure"
    else:
        bias = "neutral"
        structure = "balanced_or_choppy"

    fvgs = []

    for i in range(2, len(df)):
        candle_1 = df.iloc[i - 2]
        candle_2 = df.iloc[i - 1]
        candle_3 = df.iloc[i]

        middle_range = float(candle_2["high"] - candle_2["low"])
        displacement = middle_range >= avg_range * DISPLACEMENT_MULTIPLIER

        # Bullish FVG: candle 3 low > candle 1 high
        if candle_3["low"] > candle_1["high"]:
            low = float(candle_1["high"])
            high = float(candle_3["low"])
            size = high - low

            if size >= MIN_FVG_SIZE:
                midpoint = float((low + high) / 2)

                fvgs.append({
                    "type": "bullish",
                    "low": low,
                    "high": high,
                    "midpoint": midpoint,
                    "size": float(size),
                    "displacement": displacement,
                    "distance_from_price": float(abs(current_price - midpoint)),
                    "index": i,
                    "status": classify_location(current_price, low, high),
                    "relation_to_price": zone_relation_to_price(current_price, low, high),
                    "time": str(candle_3["time"]) if "time" in df.columns else None,
                })

        # Bearish FVG: candle 3 high < candle 1 low
        if candle_3["high"] < candle_1["low"]:
            low = float(candle_3["high"])
            high = float(candle_1["low"])
            size = high - low

            if size >= MIN_FVG_SIZE:
                midpoint = float((low + high) / 2)

                fvgs.append({
                    "type": "bearish",
                    "low": low,
                    "high": high,
                    "midpoint": midpoint,
                    "size": float(size),
                    "displacement": displacement,
                    "distance_from_price": float(abs(current_price - midpoint)),
                    "index": i,
                    "status": classify_location(current_price, low, high),
                    "relation_to_price": zone_relation_to_price(current_price, low, high),
                    "time": str(candle_3["time"]) if "time" in df.columns else None,
                })

    for zone in fvgs:
        zone["score"] = 0

        zone["score"] += min(zone["size"], 40)

        if zone["displacement"]:
            zone["score"] += 15

        if zone["distance_from_price"] <= 25:
            zone["score"] += 30
        elif zone["distance_from_price"] <= 50:
            zone["score"] += 20
        elif zone["distance_from_price"] <= 100:
            zone["score"] += 10
        else:
            zone["score"] -= 50

        zone["age"] = len(df) - zone["index"]

        if zone["age"] <= 20:
            zone["score"] += 25
        elif zone["age"] <= 50:
            zone["score"] += 15
        elif zone["age"] <= 100:
            zone["score"] += 5
        else:
            zone["score"] -= 25

    relevant_fvgs = [
        zone for zone in fvgs
        if zone["distance_from_price"] <= 150 and zone["age"] <= 150
    ]

    ranked_fvgs = sorted(
        relevant_fvgs,
        key=lambda z: z["score"],
        reverse=True,
    )

    return {
        "current_price": current_price,
        "bias": bias,
        "structure": structure,
        "recent_high_20": recent_high_20,
        "recent_low_20": recent_low_20,
        "recent_high_50": recent_high_50,
        "recent_low_50": recent_low_50,
        "recent_fvgs": fvgs[-10:],
        "ranked_fvgs": ranked_fvgs[:10],
        "bullish_fvgs": [z for z in ranked_fvgs if z["type"] == "bullish"][:5],
        "bearish_fvgs": [z for z in ranked_fvgs if z["type"] == "bearish"][:5],
    }


def rank_fvg_zones(current_price: float, zones_by_timeframe: dict):
    all_zones = []

    for timeframe, zones in zones_by_timeframe.items():
        tf_weight = TIMEFRAME_WEIGHTS.get(timeframe, 0)

        for zone in zones:
            midpoint = zone.get("midpoint")
            distance = abs(current_price - midpoint)

            score = 0
            reasons = []

            score += tf_weight
            reasons.append(f"{timeframe} timeframe carries weight.")

            if distance <= 25:
                score += 30
                reasons.append("Zone is very close to current price.")
            elif distance <= 75:
                score += 20
                reasons.append("Zone is near current price.")
            elif distance <= 150:
                score += 10
                reasons.append("Zone is still within reasonable reach.")
            else:
                score -= 20
                reasons.append("Zone is far from current price.")

            if zone.get("displacement"):
                score += 15
                reasons.append("Created with displacement.")

            score += min(zone.get("size", 0), 40)

            if zone.get("status") == "inside_zone":
                score += 25
                reasons.append("Price is currently inside this zone.")
            elif zone.get("status") in ["below_price", "above_price"]:
                score += 5

            ranked_zone = {
                **zone,
                "timeframe": timeframe,
                "score": round(score, 2),
                "ranking_reasons": reasons,
            }

            all_zones.append(ranked_zone)

    ranked = sorted(all_zones, key=lambda z: z["score"], reverse=True)

    active_zone = ranked[0] if ranked else None
    backup_zones = ranked[1:4] if len(ranked) > 1 else []

    return {
        "active_zone": active_zone,
        "backup_zones": backup_zones,
        "all_ranked_zones": ranked[:10],
    }


def get_best_zone(analysis_block: dict, preferred_type: str | None = None):
    if not analysis_block:
        return None

    zones = analysis_block.get("ranked_fvgs", [])

    if not zones:
        return None

    if preferred_type:
        matching = [z for z in zones if z.get("type") == preferred_type]

        if matching:
            return matching[0]

    return zones[0]


def get_directional_targets(current_price: float, analysis: dict):
    daily = analysis.get("daily", {})
    h4 = analysis.get("h4", {})
    htf = analysis.get("htf", {})
    mtf = analysis.get("mtf", {})

    raw_above = [
        htf.get("recent_high_20"),
        htf.get("recent_high_50"),
        h4.get("recent_high_20"),
        daily.get("recent_high_20"),
        mtf.get("recent_high_20"),
    ]

    raw_below = [
        htf.get("recent_low_20"),
        htf.get("recent_low_50"),
        h4.get("recent_low_20"),
        daily.get("recent_low_20"),
        mtf.get("recent_low_20"),
    ]

    above = sorted({
        float(x) for x in raw_above
        if x is not None and float(x) > current_price
    })

    below = sorted({
        float(x) for x in raw_below
        if x is not None and float(x) < current_price
    }, reverse=True)

    return {
        "above": above[:5],
        "below": below[:5],
    }


def format_zone_line(label: str, zone: dict, role: str):
    if not zone:
        return f"- **{label}:** No clean FVG found."

    timeframe = zone.get("timeframe", label)
    zone_type = zone.get("type", "unknown").capitalize()

    return (
        f"- **{timeframe} {zone_type} FVG:** "
        f"{zone['low']} - {zone['high']} "
        f"(midpoint {zone['midpoint']}) — {role}"
    )


def format_market_response(analysis: dict) -> str:
    if not analysis.get("success"):
        return f"I couldn't analyze the market data: {analysis.get('error', 'Unknown error')}"

    symbol = analysis.get("symbol", "the market")
    context = analysis.get("context", {})
    trade_plan = analysis.get("trade_plan", {})

    context_bias = context.get("bias", "neutral")
    context_tf = context.get("bias_timeframe", "1D")
    current_price = context.get("current_price")
    csv_freshness = analysis.get("csv_freshness", {})
    stale_warning = _csv_stale_warning(csv_freshness)
    freshness_note = _csv_recent_context_note(csv_freshness)

    daily = analysis.get("daily")
    h4 = analysis.get("h4")
    htf = analysis.get("htf", {})
    mtf = analysis.get("mtf", {})
    ltf = analysis.get("ltf", {})

    preferred_type = (
        "bullish" if context_bias == "bullish"
        else "bearish" if context_bias == "bearish"
        else None
    )

    daily_zone = get_best_zone(daily, preferred_type)
    h4_zone = get_best_zone(h4, preferred_type)
    h1_zone = get_best_zone(htf, preferred_type)
    m15_zone = get_best_zone(mtf, preferred_type)
    m1_zone = get_best_zone(ltf, preferred_type)

    response = []

    response.append(
        f"**{symbol} Data Read:** Main context is **{context_bias}** from the "
        f"**{context_tf}**. CSV 1M close is around **{current_price}**."
    )

    if stale_warning:
        response.append(f"**Data Freshness:** {stale_warning}")
    elif freshness_note:
        response.append(f"**Data Freshness:** {freshness_note}")

    response.append("## Computed Zones")

    if daily:
        response.append(format_zone_line("1D", daily_zone, "strategic HTF context"))

    if h4:
        response.append(format_zone_line("4H", h4_zone, "primary HTF battlefield"))

    response.append(format_zone_line("1H", h1_zone, "HTF confirmation / draw"))
    response.append(format_zone_line("15M", m15_zone, "setup/refinement"))
    response.append(format_zone_line("1M", m1_zone, "execution trigger only"))

    targets = trade_plan.get("targets", {})
    above = targets.get("above", [])
    below = targets.get("below", [])

    response.append("## Liquidity / Targets")
    response.append(f"- **Above:** {above if above else 'No clean upside target from CSV.'}")
    response.append(f"- **Below:** {below if below else 'No clean downside target from CSV.'}")

    response.append("## Trade Logic")
    response.append(
        "- **Bullish:** Needs price to respect/reclaim a meaningful bullish zone, "
        "then confirm with 1M MSS/BOS and BRTC."
    )
    response.append(
        "- **Bearish:** Needs price to reject a meaningful bearish/overhead zone or fail "
        "a bullish zone, then confirm with 1M MSS/BOS and BRTC."
    )

    response.append(
        "**Bottom Line:** CSV controls historical structure/FVG mapping. "
        "Vision controls live visible chart context when CSV is stale."
    )

    return "\n\n".join(response)


def analyze_market_csv(
    daily: str = "",
    h4: str = "",
    htf: str = "",
    mtf: str = "",
    ltf: str = "",
    symbol: str = "",
):
    try:
        symbol = symbol.upper() if symbol else "MNQ"

        daily = daily or resolve_market_csv(symbol, "1D")
        h4 = h4 or resolve_market_csv(symbol, "4H")
        htf = htf or resolve_market_csv(symbol, "1H")
        mtf = mtf or resolve_market_csv(symbol, "15M")
        ltf = ltf or resolve_market_csv(symbol, "1M")

        daily_df = load_market_csv(daily)
        h4_df = load_market_csv(h4)
        htf_df = load_market_csv(htf)
        mtf_df = load_market_csv(mtf)
        ltf_df = load_market_csv(ltf)

        csv_freshness = {
            "1D": get_csv_freshness(daily_df, "1D"),
            "4H": get_csv_freshness(h4_df, "4H"),
            "1H": get_csv_freshness(htf_df, "1H"),
            "15M": get_csv_freshness(mtf_df, "15M"),
            "1M": get_csv_freshness(ltf_df, "1M"),
        }

        daily_analysis = analyze_dataframe(daily_df)
        h4_analysis = analyze_dataframe(h4_df)
        htf_analysis = analyze_dataframe(htf_df)
        mtf_analysis = analyze_dataframe(mtf_df)
        ltf_analysis = analyze_dataframe(ltf_df)

        current_price = ltf_analysis["current_price"]

        zones_by_timeframe = {
            "1D": daily_analysis.get("bullish_fvgs", []) + daily_analysis.get("bearish_fvgs", []),
            "4H": h4_analysis.get("bullish_fvgs", []) + h4_analysis.get("bearish_fvgs", []),
            "1H": htf_analysis.get("bullish_fvgs", []) + htf_analysis.get("bearish_fvgs", []),
            "15M": mtf_analysis.get("bullish_fvgs", []) + mtf_analysis.get("bearish_fvgs", []),
            "1M": ltf_analysis.get("bullish_fvgs", []) + ltf_analysis.get("bearish_fvgs", []),
        }

        zone_ranking = rank_fvg_zones(
            current_price=current_price,
            zones_by_timeframe=zones_by_timeframe,
        )

        context_bias = daily_analysis["bias"]
        context_timeframe = "1D"
        execution_bias = ltf_analysis["bias"]

        targets = get_directional_targets(
            current_price=current_price,
            analysis={
                "daily": daily_analysis,
                "h4": h4_analysis,
                "htf": htf_analysis,
                "mtf": mtf_analysis,
            },
        )

        active_zone = zone_ranking.get("active_zone")
        backup_zones = zone_ranking.get("backup_zones", [])

        bullish_zones = [
            zone for zone in zone_ranking.get("all_ranked_zones", [])
            if zone.get("type") == "bullish"
        ]

        bearish_zones = [
            zone for zone in zone_ranking.get("all_ranked_zones", [])
            if zone.get("type") == "bearish"
        ]

        if context_bias == "bullish":
            trade_direction = "long"
            candidate_entries = bullish_zones[:3]
            invalidation = "Below the active bullish FVG or below the sweep low."
        elif context_bias == "bearish":
            trade_direction = "short"
            candidate_entries = bearish_zones[:3]
            invalidation = "Above the active bearish FVG or above the sweep high."
        else:
            trade_direction = "neutral"
            candidate_entries = []
            invalidation = "No high-probability setup until structure resolves."

        analysis = {
            "success": True,
            "symbol": symbol,

            "files_used": {
                "daily": daily,
                "h4": h4,
                "htf": htf,
                "mtf": mtf,
                "ltf": ltf,
            },

            "context": {
                "bias_timeframe": context_timeframe,
                "bias": context_bias,
                "execution_bias": execution_bias,
                "current_price": current_price,
            },

            "daily": {"timeframe": "1D", **daily_analysis},
            "h4": {"timeframe": "4H", **h4_analysis},
            "htf": {"timeframe": "1H", **htf_analysis},
            "mtf": {"timeframe": "15M", **mtf_analysis},
            "ltf": {"timeframe": "1M", **ltf_analysis},

            "zone_ranking": zone_ranking,
            "csv_freshness": csv_freshness,

            "trade_plan": {
                "direction": trade_direction,
                "active_zone": active_zone,
                "backup_zones": backup_zones,
                "candidate_entry_zones": candidate_entries,
                "targets": targets,
                "invalidation": invalidation,
                "ltf_confirmation": {
                    "bias": execution_bias,
                    "structure": ltf_analysis["structure"],
                    "entry_model": "Liquidity sweep -> MSS/BOS -> BRTC retest.",
                },
                "bullish_plan": {
                    "idea": "Only look for longs after respect/reclaim of a meaningful bullish zone.",
                    "zones": bullish_zones[:3],
                    "confirmation": "Wait for 1M bullish MSS/BOS, then BRTC retest.",
                    "invalidation": "Failure to reclaim or clean acceptance below the FVG low.",
                },
                "bearish_plan": {
                    "idea": "Look for shorts after rejection from an overhead bearish zone or failed bullish zone.",
                    "zones": bearish_zones[:3],
                    "confirmation": "Wait for 1M bearish MSS/BOS, then BRTC retest.",
                    "invalidation": "Reclaim above the rejected zone or break above rejection high.",
                },
            },

            "analysis_rules": {
                "model": "ICT-based",
                "source_of_truth": "CSV controls historical structure/FVG mapping.",
                "screenshot_role": "Vision controls live visible chart context when CSV is stale.",
                "timeframe_priority": "1D > 4H > 1H > 15M > 1M",
                "entry_model": "Liquidity sweep -> MSS/BOS -> BRTC retest -> continuation",
                "do_not_use": "VWAP",
                "note": "Conditional analysis only. Not financial advice.",
            },
        }

        return {
            "success": True,
            "symbol": symbol,
            "analysis": analysis,
            "zone_ranking": zone_ranking,
            "csv_freshness": csv_freshness,
            "message": format_market_response(analysis),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"I couldn't analyze the market CSVs: {str(e)}",
        }


# ---------------------------------------------------------------------
# Vision extractor — NOT final analyst
# ---------------------------------------------------------------------

def build_tradingview_visual_extraction_prompt(
    prompt: str = "",
    symbol: str = "",
    source: str = "TradingView screenshot",
):
    return f"""
You are a visual extraction agent.

Your only job is to extract visible chart markings from this {source}.
Do not provide trading advice.
Do not determine bias.
Do not calculate market structure.
Do not invent exact levels.

Return valid JSON only.

Extract:
- visible_timeframe
- current_price_marker if clearly visible, otherwise null
- visible_labels exactly as shown
- horizontal_lines with label/color/approx_price if visible
- drawn_boxes with label/color/location/approx_low/approx_high if visible
- arrows_or_annotations
- notes_about_user_markings
- uncertainty_flags

Hard label discipline rules:
- Preserve labels exactly. Do not reinterpret, rename, or translate them.
- If the chart says "5min FVG", output "5min FVG" only.
- Never call an FVG a Fibonacci retracement unless the exact visible text says "Fibonacci", "Fib", or "retracement".
- Never call a line support/resistance unless the chart label explicitly says that.
- Never convert session levels into FVGs.
- Never convert ranges/averages into trade signals.
- If uncertain, put the uncertainty in uncertainty_flags instead of guessing.

Rules:
- User-drawn boxes, rectangles, horizontal lines, arrows, and labels matter most.
- If a number is unclear, use null.
- If a zone boundary is unclear, use null.
- Do not classify bias as bullish or bearish.
- Do not say price is above/below/inside unless visually obvious.
- CSV data will handle all numeric truth later.

JSON schema:
{{
  "symbol": "{symbol or "Unknown"}",
  "source": "{source}",
  "visible_timeframe": null,
  "current_price_marker": null,
  "visible_labels": [],
  "horizontal_lines": [
    {{
      "label": null,
      "color": null,
      "approx_price": null
    }}
  ],
  "drawn_boxes": [
    {{
      "label": null,
      "color": null,
      "approx_low": null,
      "approx_high": null,
      "location_notes": null
    }}
  ],
  "arrows_or_annotations": [],
  "notes_about_user_markings": [],
  "uncertainty_flags": []
}}

User request:
{prompt or "Extract the visible chart markings."}
"""


def build_simple_visual_fallback_prompt(
    prompt: str = "",
    symbol: str = "",
    source: str = "TradingView screenshot",
):
    return f"""
Extract the visible TradingView chart markings from this {source}.

Return JSON only. Keep it simple.

Rules:
- Preserve labels exactly as visible.
- If text says "5min FVG", write "5min FVG".
- Do not use the word Fibonacci unless that exact word, "Fib", or "retracement" is visibly shown.
- Do not give trade advice.
- Do not determine bias.
- If unsure, use null or add an uncertainty flag.

JSON schema:
{{
  "symbol": "{symbol or "Unknown"}",
  "source": "{source}",
  "visible_timeframe": null,
  "current_price_marker": null,
  "visible_labels": [],
  "horizontal_lines": [],
  "drawn_boxes": [],
  "arrows_or_annotations": [],
  "notes_about_user_markings": [],
  "uncertainty_flags": []
}}

User request:
{prompt or "Extract visible chart markings."}
"""


def normalize_visual_extraction(visuals: dict):
    """
    Clean obvious vision-label drift before the narrator sees it.

    Example: if the chart label says "5min FVG", the vision model should not
    reframe it as Fibonacci unless Fibonacci/Fib/retracement is visibly present.
    """
    if not isinstance(visuals, dict):
        return visuals

    labels = visuals.get("visible_labels", []) or []
    horizontal_lines = visuals.get("horizontal_lines", []) or []
    drawn_boxes = visuals.get("drawn_boxes", []) or []

    visible_text_parts = []
    visible_text_parts.extend([str(label) for label in labels])

    for item in horizontal_lines + drawn_boxes:
        if isinstance(item, dict):
            visible_text_parts.append(str(item.get("label", "")))
            visible_text_parts.append(str(item.get("location_notes", "")))

    visible_text = " ".join(visible_text_parts).lower()
    fibonacci_is_visible = any(
        term in visible_text
        for term in ["fibonacci", "fib", "retracement"]
    )

    if not fibonacci_is_visible:
        cleaned_notes = []
        for note in visuals.get("notes_about_user_markings", []) or []:
            note_text = str(note)
            if any(term in note_text.lower() for term in ["fibonacci", "fib", "retracement"]):
                continue
            cleaned_notes.append(note)

        visuals["notes_about_user_markings"] = cleaned_notes
        if cleaned_notes != (visuals.get("notes_about_user_markings", []) or []):
            visuals.setdefault("uncertainty_flags", []).append(
                "Removed a vision note that reinterpreted a visible label."
            )

    return visuals


def extract_tradingview_visuals_from_image(
    image_base64: str,
    prompt: str = "",
    symbol: str = "",
    source: str = "TradingView screenshot",
):
    raw_response = ""
    used_fallback_prompt = False

    try:
        extraction_prompt = build_tradingview_visual_extraction_prompt(
            prompt=prompt,
            symbol=symbol,
            source=source,
        )

        try:
            raw_response = ollama_generate(
                model=VISION_MODEL,
                prompt=extraction_prompt,
                images=[image_base64],
                timeout=180,
                num_ctx=4096,
            )
        except requests.exceptions.RequestException:
            used_fallback_prompt = True
            fallback_prompt = build_simple_visual_fallback_prompt(
                prompt=prompt,
                symbol=symbol,
                source=source,
            )

            raw_response = ollama_generate(
                model=VISION_MODEL,
                prompt=fallback_prompt,
                images=[image_base64],
                timeout=180,
                num_ctx=2048,
            )

        try:
            extracted = parse_json_from_text(raw_response)
        except Exception:
            extracted = {
                "symbol": symbol,
                "source": source,
                "visible_timeframe": None,
                "current_price_marker": None,
                "visible_labels": [],
                "horizontal_lines": [],
                "drawn_boxes": [],
                "arrows_or_annotations": [],
                "notes_about_user_markings": [],
                "uncertainty_flags": [
                    "Vision model responded, but did not return parseable JSON.",
                    raw_response[:500],
                ],
            }

        extracted = normalize_visual_extraction(extracted)

        if used_fallback_prompt:
            extracted.setdefault("uncertainty_flags", []).append(
                "Strict vision extraction failed once; simple fallback prompt was used."
            )

        return {
            "success": True,
            "model": VISION_MODEL,
            "raw_response": raw_response,
            "used_fallback_prompt": used_fallback_prompt,
            "visuals": extracted,
        }

    except Exception as e:
        return {
            "success": False,
            "model": VISION_MODEL,
            "error": str(e),
            "raw_response": raw_response,
            "visuals": {
                "symbol": symbol,
                "source": source,
                "visible_timeframe": None,
                "current_price_marker": None,
                "visible_labels": [],
                "horizontal_lines": [],
                "drawn_boxes": [],
                "arrows_or_annotations": [],
                "notes_about_user_markings": [],
                "uncertainty_flags": [f"Vision extraction failed: {e}"],
            },
        }


def extract_tradingview_visuals_from_path(
    image_path: str,
    prompt: str = "",
    symbol: str = "",
    source: str = "TradingView screenshot",
):
    with open(image_path, "rb") as image_file:
        image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

    return extract_tradingview_visuals_from_image(
        image_base64=image_base64,
        prompt=prompt,
        symbol=symbol,
        source=source,
    )


# Backward-compatible name for main.py imports.
def build_tradingview_vision_prompt(
    prompt: str = "",
    symbol: str = "",
    source: str = "TradingView screenshot",
):
    return build_tradingview_visual_extraction_prompt(
        prompt=prompt,
        symbol=symbol,
        source=source,
    )


# ---------------------------------------------------------------------
# Merge + narrator
# ---------------------------------------------------------------------

def build_merged_market_state(
    csv_analysis: dict,
    visual_extraction: dict | None = None,
):
    if not csv_analysis.get("success"):
        return {
            "success": False,
            "error": csv_analysis.get("error", "CSV analysis failed."),
            "csv_analysis": csv_analysis,
            "visual_extraction": visual_extraction,
        }

    analysis = csv_analysis["analysis"]
    visuals = {}

    if visual_extraction:
        visuals = visual_extraction.get("visuals", {})

    merged = {
        "success": True,
        "source_priority": [
            "CSV controls historical structure/FVG mapping.",
            "Vision controls live visible chart context when CSV is stale.",
            "If LTF CSV is stale, do not treat CSV close as live current price.",
        ],
        "symbol": analysis.get("symbol"),
        "csv_state": {
            "context": analysis.get("context"),
            "files_used": analysis.get("files_used"),
            "csv_freshness": analysis.get("csv_freshness"),
            "zone_ranking": analysis.get("zone_ranking"),
            "trade_plan": analysis.get("trade_plan"),
            "targets": analysis.get("trade_plan", {}).get("targets"),
            "daily": analysis.get("daily"),
            "h4": analysis.get("h4"),
            "htf": analysis.get("htf"),
            "mtf": analysis.get("mtf"),
            "ltf": analysis.get("ltf"),
        },
        "visual_state": visuals,
    }

    return merged


def _compact_zone(zone: dict | None):
    if not zone:
        return None

    return {
        "timeframe": zone.get("timeframe"),
        "type": zone.get("type"),
        "low": zone.get("low"),
        "high": zone.get("high"),
        "midpoint": zone.get("midpoint"),
        "status": zone.get("status"),
        "relation_to_price": zone.get("relation_to_price"),
        "distance_from_price": zone.get("distance_from_price"),
        "displacement": zone.get("displacement"),
    }


def _compact_zones(zones: list[dict] | None, limit: int = 3):
    if not zones:
        return []

    return [_compact_zone(zone) for zone in zones[:limit]]


def build_compact_market_state(merged_state: dict):
    """
    Reduce the merged state before sending it to the narrator model.

    The narrator does not need raw candles, full FVG history, scores, ages,
    ranking reasons, file paths, or every nested analysis object.
    It only needs the confirmed market state and a few relevant zones.
    """
    csv_state = merged_state.get("csv_state", {})
    visual_state = merged_state.get("visual_state", {})

    context = csv_state.get("context", {})
    trade_plan = csv_state.get("trade_plan", {})
    targets = csv_state.get("targets") or trade_plan.get("targets", {})
    zone_ranking = csv_state.get("zone_ranking", {})
    csv_freshness = csv_state.get("csv_freshness", {})

    current_price = context.get("current_price")

    all_ranked_zones = zone_ranking.get("all_ranked_zones", [])

    overhead_zones = [
        zone for zone in all_ranked_zones
        if zone.get("relation_to_price") == "overhead"
    ]

    below_market_zones = [
        zone for zone in all_ranked_zones
        if zone.get("relation_to_price") == "below_market"
    ]

    inside_zones = [
        zone for zone in all_ranked_zones
        if zone.get("relation_to_price") == "inside"
    ]

    visual_labels = visual_state.get("visible_labels", [])
    horizontal_lines = visual_state.get("horizontal_lines", [])
    drawn_boxes = visual_state.get("drawn_boxes", [])
    uncertainty_flags = visual_state.get("uncertainty_flags", [])

    # Keep the visual payload small. The narrator only needs enough to judge
    # whether Jadin's drawings line up with CSV structure.
    compact_visual_state = {
        "visible_timeframe": visual_state.get("visible_timeframe"),
        "current_price_marker": visual_state.get("current_price_marker"),
        "visible_labels": visual_labels[:20],
        "horizontal_lines": horizontal_lines[:12],
        "drawn_boxes": drawn_boxes[:8],
        "uncertainty_flags": uncertainty_flags[:5],
    }

    return {
        "symbol": merged_state.get("symbol"),
        "source_priority": merged_state.get("source_priority", []),
        "csv_freshness": csv_freshness,
        "context": {
            "current_price": current_price,
            "htf_bias_timeframe": context.get("bias_timeframe"),
            "htf_bias": context.get("bias"),
            "execution_bias": context.get("execution_bias"),
        },
        "structure": {
            "daily": {
                "bias": csv_state.get("daily", {}).get("bias"),
                "structure": csv_state.get("daily", {}).get("structure"),
                "recent_high_20": csv_state.get("daily", {}).get("recent_high_20"),
                "recent_low_20": csv_state.get("daily", {}).get("recent_low_20"),
            },
            "h4": {
                "bias": csv_state.get("h4", {}).get("bias"),
                "structure": csv_state.get("h4", {}).get("structure"),
                "recent_high_20": csv_state.get("h4", {}).get("recent_high_20"),
                "recent_low_20": csv_state.get("h4", {}).get("recent_low_20"),
            },
            "h1": {
                "bias": csv_state.get("htf", {}).get("bias"),
                "structure": csv_state.get("htf", {}).get("structure"),
                "recent_high_20": csv_state.get("htf", {}).get("recent_high_20"),
                "recent_low_20": csv_state.get("htf", {}).get("recent_low_20"),
            },
            "m15": {
                "bias": csv_state.get("mtf", {}).get("bias"),
                "structure": csv_state.get("mtf", {}).get("structure"),
                "recent_high_20": csv_state.get("mtf", {}).get("recent_high_20"),
                "recent_low_20": csv_state.get("mtf", {}).get("recent_low_20"),
            },
            "m1": {
                "bias": csv_state.get("ltf", {}).get("bias"),
                "structure": csv_state.get("ltf", {}).get("structure"),
                "recent_high_20": csv_state.get("ltf", {}).get("recent_high_20"),
                "recent_low_20": csv_state.get("ltf", {}).get("recent_low_20"),
            },
        },
        "zones": {
            "active_zone": _compact_zone(zone_ranking.get("active_zone")),
            "inside_zones": _compact_zones(inside_zones, limit=3),
            "overhead_zones": _compact_zones(overhead_zones, limit=3),
            "below_market_zones": _compact_zones(below_market_zones, limit=3),
            "candidate_bullish_zones": _compact_zones(
                trade_plan.get("bullish_plan", {}).get("zones", []),
                limit=3,
            ),
            "candidate_bearish_zones": _compact_zones(
                trade_plan.get("bearish_plan", {}).get("zones", []),
                limit=3,
            ),
        },
        "targets": {
            "above": targets.get("above", [])[:5],
            "below": targets.get("below", [])[:5],
        },
        "execution_model": trade_plan.get("ltf_confirmation", {}),
        "visual_state": compact_visual_state,
    }



BANNED_NARRATOR_TERMS = [
    "recommended strategy",
    "recommendation",
    "strategy:",
    "action:",
    "entry:",
    "entry ",
    "stop loss",
    "take profit",
    "risk/reward",
    "target:",
    "targets:",
    "score",
    "age of",
    "json",
    "buy side",
    "sell side",
    "buy now",
    "sell now",
    "do not buy",
    "do not sell",
    "do not chase",
    "look for longs",
    "look for shorts",
    "consider long",
    "consider short",
    "short scalp",
    "long scalp",
    "selling opportunity",
    "buying opportunity",
    "institutional involvement",
    "algorithms",
    "volume spike",
]

BANNED_NARRATOR_PATTERNS = [
    r"\bscore\s*(of|is|=|:)\s*\d",
    r"\bage\s*(of|is|=|:)\s*\d",
    r"\bwait for .* to enter\b",
    r"\benter a\b",
    r"\benter an\b",
    r"\bto enter\b",
    r"\btarget(?:ing)?\s+\d",
    r"\bstop\s*(?:below|above)\b",
]


def validate_market_narration(message: str):
    """
    Keep the narrator in-bounds.

    If Qwen outputs advisory language, raw scoring internals, or a bloated
    response, the caller should retry or use deterministic fallback text.
    """
    lowered = (message or "").lower()
    violations = []

    for term in BANNED_NARRATOR_TERMS:
        if term in lowered:
            violations.append(term)

    for pattern in BANNED_NARRATOR_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            violations.append(f"pattern:{pattern}")

    word_count = len((message or "").split())

    if word_count > 240:
        violations.append(f"too_long:{word_count}_words")

    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "word_count": word_count,
    }


def _fmt_price(value):
    if value is None:
        return "unknown"

    try:
        return f"{float(value):.2f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def _fmt_zone(zone: dict | None):
    if not zone:
        return "None identified"

    timeframe = zone.get("timeframe") or "?"
    zone_type = zone.get("type") or "unknown"
    low = _fmt_price(zone.get("low"))
    high = _fmt_price(zone.get("high"))
    relation = zone.get("relation_to_price") or zone.get("status") or "unknown relation"

    return f"{timeframe} {zone_type} FVG {low}–{high} ({relation})"


def _fmt_zone_list(zones: list[dict] | None, limit: int = 2):
    if not zones:
        return "None nearby"

    return "; ".join(_fmt_zone(zone) for zone in zones[:limit])


def _fmt_targets(values: list | None, limit: int = 3):
    if not values:
        return "None identified"

    return ", ".join(_fmt_price(value) for value in values[:limit])


def _csv_refresh_last_success_age_minutes() -> float | None:
    try:
        from csv_refresh import get_csv_refresh_status

        status = get_csv_refresh_status()
        last_success = status.get("last_success") if isinstance(status, dict) else None
        if not last_success:
            return None

        parsed = datetime.fromisoformat(str(last_success))
        now = datetime.now(parsed.tzinfo) if parsed.tzinfo else datetime.now()
        return max((now - parsed).total_seconds() / 60, 0)
    except Exception:
        return None


def _csv_recent_context_note(csv_freshness: dict) -> str | None:
    ltf_freshness = (csv_freshness or {}).get("1M", {})

    if ltf_freshness.get("is_stale"):
        return None

    age = ltf_freshness.get("age_minutes")
    threshold = CSV_STALENESS_THRESHOLDS_MINUTES.get("1M")

    if age is None or threshold is None:
        return None

    if age <= 5:
        return None

    return (
        f"1M CSV is recent CSV context ({age} minutes old; "
        f"stale threshold is {threshold} minutes)."
    )


def _csv_stale_warning(csv_freshness: dict) -> str | None:
    ltf_freshness = (csv_freshness or {}).get("1M", {})

    if not ltf_freshness.get("is_stale"):
        return None

    latest_time = ltf_freshness.get("latest_csv_time") or "unknown time"
    age = ltf_freshness.get("age_minutes")
    threshold = CSV_STALENESS_THRESHOLDS_MINUTES.get("1M")

    if age is not None and threshold is not None:
        last_success_age = _csv_refresh_last_success_age_minutes()
        if age <= threshold and last_success_age is not None and last_success_age <= 20:
            return (
                f"1M CSV is recent CSV context ({age} minutes old; "
                f"stale threshold is {threshold} minutes)."
            )

    age_text = f"{age} minutes old" if age is not None else "age unknown"

    return (
        f"Warning: 1M CSV is stale ({latest_time}, {age_text}). "
        "CSV close is historical context, not confirmed live price; live chart price may differ."
    )


def _is_ltf_csv_stale(csv_freshness: dict) -> bool:
    return bool((csv_freshness or {}).get("1M", {}).get("is_stale"))


def _visual_marking_summary(
    visual: dict,
    current_price=None,
    active_zone=None,
    overhead_zones=None,
    below_zones=None,
    ltf_csv_stale: bool = False,
) -> str:
    if not isinstance(visual, dict):
        return "No usable screenshot markings were detected, so this read is CSV-only."

    overhead_zones = overhead_zones or []
    below_zones = below_zones or []

    visible_labels = visual.get("visible_labels") or []
    horizontal_lines = visual.get("horizontal_lines") or []
    drawn_boxes = visual.get("drawn_boxes") or []
    uncertainty_flags = visual.get("uncertainty_flags") or []

    has_visual_context = bool(visible_labels or horizontal_lines or drawn_boxes)

    if not has_visual_context:
        if uncertainty_flags:
            return "No usable screenshot markings were detected, so this read is CSV-only."
        return "No visible chart markings were detected."

    # -------------------------
    # Local helpers
    # -------------------------
    def _dedupe_keep_order(items):
        seen = set()
        cleaned = []

        for item in items:
            text = str(item).strip()
            key = text.lower()

            if not key or key in seen:
                continue

            seen.add(key)
            cleaned.append(text)

        return cleaned

    def _normalize_session_label(text: str) -> list[str]:
        text_lower = str(text).lower()
        sessions = []

        if "tokyo" in text_lower:
            sessions.append("Tokyo")

        if "london" in text_lower:
            sessions.append("London")

        if "new york" in text_lower:
            sessions.append("New York")

        return sessions

    def _is_plain_price_label(text: str) -> bool:
        cleaned = (
            str(text)
            .replace(",", "")
            .replace(".", "")
            .replace(" ", "")
            .strip()
        )

        return cleaned.isdigit()

    def _is_noise_label(text: str) -> bool:
        text_lower = str(text).lower()

        return any(
            skip in text_lower
            for skip in [
                "buy",
                "sell",
                "range:",
                "avg:",
                "%",
                "vol",
                "500",
                "tradingview",
            ]
        )

    def _is_relevant_label(text: str) -> bool:
        text_lower = str(text).lower()

        return any(
            keep in text_lower
            for keep in [
                "fvg",
                "pdh",
                "pdnyh",
                "pwh",
                "previous week",
                "asia",
                "london",
                "tokyo",
                "new york",
                "high",
                "low",
            ]
        )

    def _is_ltf_fvg_label(text: str) -> bool:
        text_lower = str(text).lower()

        return any(
            token in text_lower
            for token in [
                "1min fvg",
                "1m fvg",
                "3min fvg",
                "3m fvg",
                "5min fvg",
                "5m fvg",
                "15min fvg",
                "15m fvg",
                "15 min fvg",
            ]
        )

    def _has_htf_or_compressed_context(text: str) -> bool:
        text_lower = str(text).lower()

        return any(
            token in text_lower
            for token in [
                "4hr fvg",
                "4h fvg",
                "pdh",
                "pdnyh",
                "previous week high",
                "pwh",
            ]
        )

    def _normalize_uncertain_ltf_fvg_label(label: str, context_text: str) -> str:
        text = str(label or "").strip()
        text_lower = text.lower()

        if not text:
            return text

        # If vision clearly reads 15M, keep it. Do not downgrade it.
        if any(token in text_lower for token in ["15min fvg", "15m fvg", "15 min fvg"]):
            return "15min FVG"

        # If vision reads smaller LTF FVG on a compressed HTF/level-heavy view,
        # avoid false precision instead of guessing the timeframe.
        suspicious_ltf = any(
            token in text_lower
            for token in [
                "1min fvg",
                "1m fvg",
                "3min fvg",
                "3m fvg",
                "5min fvg",
                "5m fvg",
            ]
        )

        if suspicious_ltf and _has_htf_or_compressed_context(context_text):
            return "LTF FVG label visible, exact timeframe unclear from this view"

        return text

    def _zone_contains_price(zone: dict, price) -> bool:
        if not zone or price is None:
            return False

        low = zone.get("low")
        high = zone.get("high")

        if low is None or high is None:
            return False

        zone_low = min(low, high)
        zone_high = max(low, high)

        return zone_low <= price <= zone_high

    def _zone_distance(zone: dict, price):
        if not zone or price is None:
            return None

        low = zone.get("low")
        high = zone.get("high")

        if low is None or high is None:
            return None

        zone_low = min(low, high)
        zone_high = max(low, high)

        if zone_low <= price <= zone_high:
            return 0

        if price < zone_low:
            return zone_low - price

        return price - zone_high

    def _stale_relation_text(distance, relation_text: str) -> str:
        return (
            f"Stale CSV relation: last CSV close was {_fmt_price(distance)} points {relation_text}. "
            "Confirm live price from the screenshot/TradingView before treating this as current."
        )

    parts = []

    # -------------------------
    # Clean visible labels
    # -------------------------
    important_labels = []

    for label in visible_labels:
        if not isinstance(label, str):
            continue

        label = label.strip()

        if not label:
            continue

        if _is_noise_label(label):
            continue

        session_labels = _normalize_session_label(label)

        if session_labels:
            important_labels.extend(session_labels)
        elif _is_relevant_label(label):
            important_labels.append(label)

    important_labels = _dedupe_keep_order(important_labels)

    if important_labels:
        parts.append(
            "Detected labels: "
            + ", ".join(important_labels[:8])
            + "."
        )

    # -------------------------
    # Clean horizontal levels
    # -------------------------
    clean_lines = []

    for line in horizontal_lines:
        if not isinstance(line, dict):
            continue

        label = str(line.get("label") or "horizontal level").strip()
        price = line.get("approx_price")
        label_lower = label.lower()

        if not label or _is_noise_label(label):
            continue

        if not _is_relevant_label(label):
            continue

        # FVGs are zones, not horizontal levels.
        # They should be reported under "Marked zones" instead.
        if "fvg" in label_lower:
            continue

        # If vision extracts a suspicious price for a major reference level,
        # keep the label but downgrade confidence in the numeric value.
        if price is not None and current_price is not None:
            try:
                distance_from_current = abs(float(price) - float(current_price))

                is_major_reference = any(
                    token in label_lower
                    for token in [
                        "previous week high",
                        "pwh",
                        "pdh",
                        "pdnyh",
                        "asia high",
                        "asia low",
                        "london high",
                        "london low",
                    ]
                )

                if is_major_reference and distance_from_current > 75:
                    clean_lines.append(f"{label}; extracted price may be unreliable")
                    continue

            except (TypeError, ValueError):
                clean_lines.append(f"{label}; extracted price may be unreliable")
                continue

        if price is not None:
            clean_lines.append(f"{label} near {_fmt_price(price)}")
        else:
            clean_lines.append(label)

    clean_lines = _dedupe_keep_order(clean_lines)

    if clean_lines:
        parts.append(
            "Visible levels: "
            + "; ".join(clean_lines[:5])
            + "."
        )

    # -------------------------
    # Build pre-box visual context
    # -------------------------
    pre_box_visual_text = " ".join(
        str(item).lower()
        for item in important_labels + clean_lines
    )

    # -------------------------
    # Clean drawn boxes / zones
    # -------------------------
    clean_boxes = []

    for box in drawn_boxes:
        if not isinstance(box, dict):
            continue

        raw_label = str(box.get("label") or "marked box").strip()
        low = box.get("approx_low")
        high = box.get("approx_high")

        label = _normalize_uncertain_ltf_fvg_label(
            raw_label,
            pre_box_visual_text,
        )

        if not label or _is_noise_label(label):
            continue

        label_lower = label.lower()

        is_generic_box = label_lower in [
            "marked box",
            "box",
            "marked zone",
            "visual box",
            "drawn box",
            "unlabeled box",
            "unlabeled zone",
        ]

        is_meaningful_zone = any(
            token in label_lower
            for token in [
                "fvg",
                "pdh",
                "pdnyh",
                "pwh",
                "previous week",
                "asia",
                "london",
                "tokyo",
                "new york",
                "high",
                "low",
            ]
        )

        # If vision only sees a generic box with no useful label,
        # ignore it. This avoids treating empty price space as a real zone.
        if is_generic_box and not is_meaningful_zone:
            continue

        # If vision labels a drawn box as only a raw price, ignore it.
        # These are usually price-marker artifacts, not real marked zones.
        if _is_plain_price_label(label):
            continue

        if low is not None and high is not None and low != high:
            clean_boxes.append(f"{label} around {_fmt_price(low)}–{_fmt_price(high)}")
        elif low is not None:
            clean_boxes.append(f"{label} near {_fmt_price(low)}")
        elif high is not None:
            clean_boxes.append(f"{label} near {_fmt_price(high)}")
        else:
            clean_boxes.append(label)

    clean_boxes = _dedupe_keep_order(clean_boxes)

    if clean_boxes:
        parts.append(
            "Marked zones: "
            + "; ".join(clean_boxes[:3])
            + "."
        )

    # -------------------------
    # Build full visual context
    # -------------------------
    visual_text = " ".join(
        str(item).lower()
        for item in important_labels + clean_lines + clean_boxes
    )

    active_zone_text = _fmt_zone(active_zone) if active_zone else None

    # -------------------------
    # Compare visual FVG markings to CSV zones
    # -------------------------
    if "4hr fvg" in visual_text or "4h fvg" in visual_text:
        if active_zone and active_zone_text and "4H" in active_zone_text:
            parts.append(
                f"Visual 4H FVG appears aligned with the active computed zone: {active_zone_text}."
            )
        elif below_zones:
            parts.append(
                f"Visual 4H FVG was detected; nearest below-market CSV zone is {_fmt_zone(below_zones[0])}."
            )
        else:
            parts.append(
                "Visual 4H FVG was detected, but no matching below-market CSV zone was found."
            )

    if "15min fvg" in visual_text or "15m fvg" in visual_text:
        parts.append(
            "Visual 15M FVG was detected and should be treated as execution/context confirmation, not HTF source of truth."
        )

    if "ltf fvg label visible" in visual_text:
        parts.append(
            "LTF FVG label appears compressed on this screenshot, so exact timeframe should be confirmed on the lower timeframe."
        )

    # -------------------------
    # Compare current price to active zone
    # -------------------------
    if active_zone and current_price is not None:
        if _zone_contains_price(active_zone, current_price):
            if ltf_csv_stale:
                parts.append(
                    "Stale CSV relation: last CSV close was inside the active computed zone. "
                    "Confirm live price from the screenshot/TradingView before treating this as current."
                )
            else:
                parts.append(
                    "Current price is inside the active computed zone."
                )
        else:
            distance = _zone_distance(active_zone, current_price)
            relation = active_zone.get("relation_to_price", "away from price")

            if relation == "below_market":
                relation_text = "above the active computed zone"
            elif relation == "overhead":
                relation_text = "below the active computed zone"
            elif relation == "inside":
                relation_text = "inside the active computed zone"
            else:
                relation_text = f"from the active computed zone ({relation})"

            if distance is not None:
                if ltf_csv_stale:
                    parts.append(_stale_relation_text(distance, relation_text))
                else:
                    parts.append(
                        f"Current price is {_fmt_price(distance)} points {relation_text}."
                    )

    # -------------------------
    # Compare current price to nearest CSV zones
    # -------------------------
    if overhead_zones and current_price is not None:
        nearest_overhead = overhead_zones[0]
        distance = _zone_distance(nearest_overhead, current_price)

        if distance is not None:
            if ltf_csv_stale:
                parts.append(
                    _stale_relation_text(
                        distance,
                        f"below the nearest overhead CSV zone: {_fmt_zone(nearest_overhead)}",
                    )
                )
            else:
                parts.append(
                    f"Nearest overhead CSV zone is {_fmt_price(distance)} points away: {_fmt_zone(nearest_overhead)}."
                )

    if below_zones and current_price is not None:
        nearest_below = below_zones[0]
        distance = _zone_distance(nearest_below, current_price)

        if distance is not None:
            if ltf_csv_stale:
                parts.append(
                    _stale_relation_text(
                        distance,
                        f"above the nearest below-market CSV zone: {_fmt_zone(nearest_below)}",
                    )
                )
            else:
                parts.append(
                    f"Nearest below-market CSV zone is {_fmt_price(distance)} points away: {_fmt_zone(nearest_below)}."
                )

    # -------------------------
    # Add session context
    # -------------------------
    if "tokyo" in visual_text or "london" in visual_text or "new york" in visual_text:
        parts.append(
            "Session labels are visible and can be used as context around the active levels."
        )

    # -------------------------
    # Return final visual summary
    # -------------------------
    if not parts:
        return "Screenshot markings were detected, but no clean trading-relevant markings were extracted."

    return " ".join(parts)


def format_deterministic_market_summary(merged_state: dict) -> str:
    """
    Stable final market summary.

    This intentionally does not call the text model. CSV controls the numeric
    state; vision only adds visible drawing/label confirmation.
    """
    state = build_compact_market_state(merged_state)

    symbol = state.get("symbol") or "Market"
    context = state.get("context", {})
    structure = state.get("structure", {})
    zones = state.get("zones", {})
    targets = state.get("targets", {})
    visual = state.get("visual_state", {})
    csv_freshness = state.get("csv_freshness", {})

    current_price = context.get("current_price")
    ltf_csv_stale = _is_ltf_csv_stale(csv_freshness)
    stale_warning = _csv_stale_warning(csv_freshness)
    freshness_note = _csv_recent_context_note(csv_freshness)
    htf_bias = context.get("htf_bias") or "neutral"
    htf_tf = context.get("htf_bias_timeframe") or "HTF"
    execution_bias = context.get("execution_bias") or "neutral"

    active_zone = zones.get("active_zone")
    overhead_zones = zones.get("overhead_zones", [])
    below_zones = zones.get("below_market_zones", [])

    m15 = structure.get("m15", {})
    m1 = structure.get("m1", {})
    h4 = structure.get("h4", {})
    h1 = structure.get("h1", {})

    if execution_bias != htf_bias:
        bias_line = (
            f"HTF remains {htf_bias}, but execution is {execution_bias}; "
            f"short-term read should respect the {execution_bias} structure until reclaimed."
        )
    else:
        bias_line = f"HTF and execution are aligned {htf_bias}."

    if overhead_zones:
        scenario_up = (
            f"Upside continuation requires reclaim/acceptance through {_fmt_zone(overhead_zones[0])}."
        )
    else:
        upside_refs = _fmt_targets(targets.get("above", []), 2)
        scenario_up = (
            f"Upside continuation requires holding above the current range/PDH area and delivery toward {upside_refs}."
            if targets.get("above")
            else "Upside continuation requires holding above the current range and forming fresh bullish structure."
        )

    first_below_target = _fmt_targets(targets.get("below", []), 1)
    scenario_down = (
        f"Downside continuation requires failure to hold the current range/PDH area and rotation toward {first_below_target}."
        if targets.get("below")
        else "Downside continuation requires rejection from the current range and fresh bearish structure."
    )

    lines = [
        "## HTF Context",
        f"{symbol} CSV 1M close is around {_fmt_price(current_price)}. {htf_tf} bias is {htf_bias}. H4 is {h4.get('bias', 'unknown')} and H1 is {h1.get('bias', 'unknown')}.",
    ]

    if stale_warning:
        lines.extend([
            "",
            "## Data Freshness",
            stale_warning,
        ])
    elif freshness_note:
        lines.extend([
            "",
            "## Data Freshness",
            freshness_note,
        ])

    lines.extend([
        "",
        "## Current Structure",
        f"Execution bias is {execution_bias}. M15 structure is {m15.get('structure', 'unknown')}; M1 structure is {m1.get('structure', 'unknown')}.",
        f"Active computed zone: {_fmt_zone(active_zone)}.",
        "",
        "## Liquidity / Levels",
        f"Overhead: {_fmt_zone_list(overhead_zones, 2)}.",
        f"Below market: {_fmt_zone_list(below_zones, 2)}.",
        f"Upside references: {_fmt_targets(targets.get('above', []))}. Downside references: {_fmt_targets(targets.get('below', []))}.",
        "",
        "## Visual Markings Check",
        _visual_marking_summary(
            visual,
            current_price=current_price,
            active_zone=active_zone,
            overhead_zones=overhead_zones,
            below_zones=below_zones,
            ltf_csv_stale=ltf_csv_stale,
        ),
        "",
        "## Bias",
        bias_line,
        "",
        "## Scenarios",
        f"- Bullish scenario: {scenario_up}",
        f"- Bearish scenario: {scenario_down}",
        "",
        "## Bottom Line",
        "CSV controls historical structure/FVG mapping. Vision controls live visible chart context when CSV is stale.",
    ])

    return "\n".join(lines)


# Backward-compatible fallback name used by older narration guardrails.
def build_deterministic_market_summary(merged_state: dict):
    return format_deterministic_market_summary(merged_state)

def build_narration_repair_prompt(
    original_message: str,
    validation: dict,
    merged_state: dict,
    user_prompt: str = "",
):
    compact_state = build_compact_market_state(merged_state)
    compact_state_json = json.dumps(compact_state, indent=2, default=str)

    return f"""
Rewrite the market narration because it violated output rules.

Violations:
{validation.get("violations", [])}

Original message:
{original_message}

Hard rules for rewrite:
- Under 220 words.
- Do not mention JSON.
- Do not mention scores.
- Do not say buy, sell, short, long as instructions.
- Do not use "entry", "stop loss", "take profit", "recommended", or "recommendation".
- Do not give financial advice.
- Do not invent labels or indicators.
- Use conditional market narration only.
- If HTF and execution bias differ, explain both briefly.

Required sections only:
## HTF Context
## Current Structure
## Liquidity / Levels
## Visual Markings Check
## Bias
## Scenarios
## Bottom Line

Compact market state:
{compact_state_json}

User request:
{user_prompt or "Analyze the current market state."}
"""


def build_market_narrator_prompt(
    merged_state: dict,
    user_prompt: str = "",
):
    compact_state = build_compact_market_state(merged_state)
    compact_state_json = json.dumps(compact_state, indent=2, default=str)

    return f"""
You are Helix, Jadin's professional futures market narrator.

Your job is to describe:
- market structure
- liquidity
- HTF/LTF alignment
- imbalance reactions
- key levels
- execution context

Use this source priority:
1. CSV controls historical structure/FVG mapping.
2. Vision controls live visible chart context when CSV is stale.
3. If LTF CSV is stale, do not describe CSV close or CSV-derived zone distances as live current price.

DO NOT:
- invent indicators
- invent volume analysis
- mention Fibonacci unless the visual_state explicitly labels Fibonacci
- mention smart money concepts unless explicitly visible
- give financial advice
- tell the user to buy or sell
- use buy/sell/short/long as direct instructions
- say "enter here"
- say "entry"
- say "take profit"
- say "stop loss"
- say "recommended strategy"
- say "recommendation"
- mention FVG scores
- mention JSON
- hallucinate chart labels

Bias handling:
- If HTF bias and execution bias differ, explain both.
- Identify which bias is dominant short term.
- Identify which bias remains intact long term.
- Do not force bullish and bearish scenarios to have equal weight if structure is clearly favoring one side.

Language rules:
- Use conditional language.
- If information is uncertain, say "appears", "likely", "potential", or "currently reacting".
- Do not claim certainty.
- Do not tell Jadin to enter immediately.

Response style:
- concise
- structured
- trader-focused
- no fluff
- no motivational language
- total response under 220 words

Required sections:
## HTF Context
## Current Structure
## Liquidity / Levels
## Visual Markings Check
## Bias
## Scenarios
## Bottom Line

Compact market state:
{compact_state_json}

User request:
{user_prompt or "Analyze the current market state."}
"""
def narrate_market_state(
    merged_state: dict,
    prompt: str = "",
):
    try:
        narrator_prompt = build_market_narrator_prompt(
            merged_state=merged_state,
            user_prompt=prompt,
        )

        message = ollama_generate(
            model=TEXT_MODEL,
            prompt=narrator_prompt,
            images=None,
            timeout=180,
            num_ctx=8192,
        )

        validation = validate_market_narration(message)

        if not validation["valid"]:
            repair_prompt = build_narration_repair_prompt(
                original_message=message,
                validation=validation,
                merged_state=merged_state,
                user_prompt=prompt,
            )

            repaired_message = ollama_generate(
                model=TEXT_MODEL,
                prompt=repair_prompt,
                images=None,
                timeout=180,
                num_ctx=4096,
            )

            repaired_validation = validate_market_narration(repaired_message)

            if not repaired_validation["valid"]:
                fallback_message = build_deterministic_market_summary(merged_state)
                fallback_validation = validate_market_narration(fallback_message)

                return {
                    "success": True,
                    "model": "deterministic_fallback",
                    "message": fallback_message,
                    "validation": fallback_validation,
                    "repaired": True,
                    "fallback_used": True,
                    "original_validation": validation,
                    "repaired_validation": repaired_validation,
                }

            return {
                "success": True,
                "model": TEXT_MODEL,
                "message": repaired_message,
                "validation": repaired_validation,
                "repaired": True,
                "fallback_used": False,
                "original_validation": validation,
            }

        return {
            "success": True,
            "model": TEXT_MODEL,
            "message": message,
            "validation": validation,
            "repaired": False,
        }

    except Exception as e:
        return {
            "success": False,
            "model": TEXT_MODEL,
            "error": str(e),
            "message": f"Market narration failed: {e}",
        }


# ---------------------------------------------------------------------
# Full trading analysis pipeline
# ---------------------------------------------------------------------

def analyze_tradingview(symbol: str = "MNQ", prompt: str = "", timeframe: str | None = None):
    """
    Full pipeline:
    1. Capture TradingView screenshot.
    2. Extract visual markings with vision model.
    3. Analyze CSV data with deterministic Python.
    4. Merge states.
    5. Narrate with text model.
    """
    symbol = symbol.upper()
    timeframe = timeframe.upper() if timeframe else None

    try:
        capture_result = capture_tradingview(symbol=symbol, timeframe=timeframe)

        if not capture_result.get("success"):
            return capture_result

        screenshot_path = capture_result["screenshot_path"]
        captured_timeframe = capture_result.get("timeframe")

        visual_result = extract_tradingview_visuals_from_path(
            image_path=screenshot_path,
            prompt=prompt,
            symbol=symbol,
            source="live TradingView capture",
        )

        csv_result = analyze_market_csv(symbol=symbol)

        if not csv_result.get("success"):
            return {
                "success": False,
                "symbol": symbol,
                "timeframe": captured_timeframe,
                "screenshot_path": screenshot_path,
                "visual_extraction": visual_result,
                "csv_analysis": csv_result,
                "csv_freshness": csv_result.get("csv_freshness"),
                "message": (
                    "Screenshot was captured and visual markings were extracted, "
                    "but CSV analysis failed.\n\n"
                    f"CSV error: {csv_result.get('error')}\n\n"
                    "Refresh or manually export CSV files for 1D, 4H, 1H, 15M, and 1M."
                ),
            }

        merged_state = build_merged_market_state(
            csv_analysis=csv_result,
            visual_extraction=visual_result,
        )

        message = format_deterministic_market_summary(merged_state)

        return {
            "success": True,
            "symbol": symbol,
            "timeframe": captured_timeframe,
            "models": {
                "vision": VISION_MODEL,
                "narrator": "deterministic_formatter",
            },
            "screenshot_path": screenshot_path,
            "visual_extraction": visual_result,
            "csv_analysis": csv_result,
            "csv_freshness": csv_result.get("csv_freshness"),
            "merged_state": merged_state,
            "message": message + f"\n\nScreenshot saved: `{screenshot_path}`",
        }

    except Exception as e:
        return {
            "success": False,
            "symbol": symbol,
            "timeframe": timeframe,
            "error": str(e),
            "message": f"TradingView pipeline failed: {e}",
        }


def analyze_uploaded_chart_image(
    image_base64: str,
    prompt: str = "",
    symbol: str = "",
):
    """
    Uploaded-image pipeline:
    - Vision extracts markings.
    - CSV analyzes real data.
    - Text model narrates.
    """
    try:
        symbol = symbol.upper() if symbol else "MNQ"

        visual_result = extract_tradingview_visuals_from_image(
            image_base64=image_base64,
            prompt=prompt,
            symbol=symbol,
            source="uploaded chart image",
        )

        csv_result = analyze_market_csv(symbol=symbol)

        if not csv_result.get("success"):
            return {
                "success": False,
                "symbol": symbol,
                "visual_extraction": visual_result,
                "csv_analysis": csv_result,
                "csv_freshness": csv_result.get("csv_freshness"),
                "message": (
                    "Image visual extraction ran, but CSV analysis failed. "
                    f"CSV error: {csv_result.get('error')}"
                ),
            }

        merged_state = build_merged_market_state(
            csv_analysis=csv_result,
            visual_extraction=visual_result,
        )

        message = format_deterministic_market_summary(merged_state)

        return {
            "success": True,
            "symbol": symbol,
            "models": {
                "vision": VISION_MODEL,
                "narrator": "deterministic_formatter",
            },
            "visual_extraction": visual_result,
            "csv_analysis": csv_result,
            "csv_freshness": csv_result.get("csv_freshness"),
            "merged_state": merged_state,
            "message": message,
        }

    except Exception as e:
        return {
            "success": False,
            "symbol": symbol if symbol else None,
            "error": str(e),
            "message": f"Uploaded chart pipeline failed: {e}",
        }


TOOLS = {
    "get_time": get_time,
    "echo": echo,
    "run_command": run_command,
    "read_file": read_file,
    "write_file": write_file,
    "open_url": open_url,
    "extract_links": extract_links,
    "create_reminder": create_reminder,
    "web_search": web_search,

    # Orbit planning tools
    "get_orbit_major_events": get_orbit_major_events,
    "get_orbit_milestones": get_orbit_milestones,
    "get_orbit_goals": get_orbit_goals,
    "get_orbit_tasks": get_orbit_tasks,
    "create_orbit_task": create_orbit_task,
    "complete_orbit_task": complete_orbit_task,
    "create_orbit_goal": create_orbit_goal,
    "create_orbit_review": create_orbit_review,
    "get_orbit_reviews": get_orbit_reviews,
    "create_trade_session": create_trade_session,
    "get_trade_sessions": get_trade_sessions,
    "update_orbit_milestone_progress": update_orbit_milestone_progress,
    "update_orbit_major_event_progress": update_orbit_major_event_progress,
    "get_corporate_escape_status": get_corporate_escape_status,
    "get_corporate_escape_readiness": get_corporate_escape_readiness,
    "update_readiness_category": update_readiness_category,
    "suggest_trading_readiness_update": suggest_trading_readiness_update,
    "generate_morning_briefing": generate_morning_briefing,
    "generate_daily_closeout": generate_daily_closeout,
    "generate_recommendations": generate_recommendations,
    "generate_orbit_daily_summary": generate_orbit_daily_summary,
    "generate_orbit_focus": generate_orbit_focus,

    # Trading / market tools
    "refresh_market_csvs": refresh_market_csvs,
    "analyze_market_csv": analyze_market_csv,
    "capture_tradingview": capture_tradingview,
    "setup_tradingview_profile": setup_tradingview_profile,
    "extract_tradingview_visuals_from_path": extract_tradingview_visuals_from_path,
    "analyze_tradingview": analyze_tradingview,
    "analyze_uploaded_chart_image": analyze_uploaded_chart_image,
}
