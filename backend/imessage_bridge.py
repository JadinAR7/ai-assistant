import sqlite3
import time
import subprocess
import requests
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


# -------------------------
# Configuration
# -------------------------
CHAT_DB = Path.home() / "Library/Messages/chat.db"

BACKEND_CHAT_URL = "http://127.0.0.1:8000/chat"
BACKEND_SCAN_LATEST_URL = "http://127.0.0.1:8000/scan/latest"
BACKEND_SCAN_FORCE_URL = "http://127.0.0.1:8000/scan/force"

ALLOWED_SENDER = "jadinrobinson05@hotmail.com"

TIMEZONE = ZoneInfo("America/Denver")
POLL_SECONDS = 3
MAX_REPLY_CHARS = 1500

# Stores replies Helix just sent so the bridge does not process its own messages.
RECENT_SENT_REPLIES = []
MAX_RECENT_SENT_REPLIES = 20


# -------------------------
# Text helpers
# -------------------------
def normalize_text(text: str) -> str:
    return " ".join(str(text or "").strip().split())


def remember_sent_reply(text: str) -> None:
    RECENT_SENT_REPLIES.append(normalize_text(text))

    while len(RECENT_SENT_REPLIES) > MAX_RECENT_SENT_REPLIES:
        RECENT_SENT_REPLIES.pop(0)


def was_recently_sent_by_helix(text: str) -> bool:
    return normalize_text(text) in RECENT_SENT_REPLIES


def has_any(text: str, phrases: list[str]) -> bool:
    return any(phrase in text for phrase in phrases)


# -------------------------
# iMessage database helpers
# -------------------------
def open_messages_db():
    if not CHAT_DB.exists():
        raise FileNotFoundError(f"Messages database not found: {CHAT_DB}")

    return sqlite3.connect(f"file:{CHAT_DB}?mode=ro", uri=True)


def get_latest_inbound_rowid() -> int | None:
    """
    Gets the latest inbound message ROWID at startup.

    This prevents Helix from responding to old messages when the bridge starts.
    """
    conn = open_messages_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT message.ROWID
        FROM message
        JOIN handle ON message.handle_id = handle.ROWID
        WHERE message.is_from_me = 0
          AND message.text IS NOT NULL
          AND handle.id = ?
        ORDER BY message.ROWID DESC
        LIMIT 1
        """,
        (ALLOWED_SENDER,),
    )

    row = cursor.fetchone()
    conn.close()

    return row[0] if row else None


def get_new_inbound_messages(after_rowid: int | None):
    """
    Reads new inbound messages after the last processed ROWID.
    """
    conn = open_messages_db()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            message.ROWID,
            message.text,
            handle.id,
            message.date
        FROM message
        JOIN handle ON message.handle_id = handle.ROWID
        WHERE message.is_from_me = 0
          AND message.text IS NOT NULL
          AND handle.id = ?
          AND (? IS NULL OR message.ROWID > ?)
        ORDER BY message.ROWID ASC
        LIMIT 10
        """,
        (ALLOWED_SENDER, after_rowid, after_rowid),
    )

    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "rowid": row[0],
            "text": row[1],
            "sender": row[2],
            "date": row[3],
        }
        for row in rows
    ]


# -------------------------
# iMessage sender
# -------------------------
def send_imessage(recipient: str, text: str):
    """
    Sends an iMessage using the first available iMessage service.
    """
    safe_text = text.replace("\\", "\\\\").replace('"', '\\"')
    safe_recipient = recipient.replace("\\", "\\\\").replace('"', '\\"')

    script = f'''
    tell application "Messages"
        set targetService to 1st service whose service type = iMessage
        send "{safe_text}" to buddy "{safe_recipient}" of targetService
    end tell
    '''

    # Remember before sending so the sync echo gets ignored.
    remember_sent_reply(text)

    subprocess.run(["osascript", "-e", script], check=True)


# -------------------------
# Backend helpers
# -------------------------
def ask_helix(message: str) -> str:
    response = requests.post(
        BACKEND_CHAT_URL,
        json={
            "message": message,
            "tool_mode": "auto",
        },
        timeout=180,
    )

    response.raise_for_status()
    data = response.json()

    return data.get("message", "No response returned from Helix.")


def get_latest_scan_summary() -> str:
    response = requests.get(BACKEND_SCAN_LATEST_URL, timeout=60)
    response.raise_for_status()
    data = response.json()

    record = data.get("record")

    if not record:
        return "No latest MES scan found yet."

    state = record.get("state", {}) or {}
    alert = record.get("alert", {}) or {}
    comparison = record.get("comparison", {}) or {}

    market_changes = comparison.get("market_changes", []) or []
    alert_reasons = alert.get("reasons", []) or []

    return (
        "Latest MES scan:\n"
        f"HTF: {state.get('htf_bias', 'unknown')}\n"
        f"Execution: {state.get('execution_bias', 'unknown')}\n"
        f"Price relation: {state.get('price_relation', 'unknown')}\n"
        f"Alert: {alert.get('should_alert', False)} "
        f"({alert.get('severity', 'none')})\n\n"
        "Market changes:\n"
        + "\n".join(f"- {item}" for item in market_changes[:3])
        + "\n\nReasons:\n"
        + "\n".join(f"- {item}" for item in alert_reasons[:3])
    )


def force_mes_scan() -> str:
    response = requests.post(BACKEND_SCAN_FORCE_URL, timeout=300)
    response.raise_for_status()
    record = response.json()

    state = record.get("state", {}) or {}
    alert = record.get("alert", {}) or {}

    return (
        "MES scan complete:\n"
        f"HTF: {state.get('htf_bias', 'unknown')}\n"
        f"Execution: {state.get('execution_bias', 'unknown')}\n"
        f"Price relation: {state.get('price_relation', 'unknown')}\n"
        f"Alert: {alert.get('should_alert', False)} "
        f"({alert.get('severity', 'none')})"
    )


# -------------------------
# Command router
# -------------------------
def route_message(text: str) -> str:
    """
    Handles simple assistant commands locally before falling back to /chat.
    """
    clean = text.strip()
    lower = clean.lower()

    # -------------------------
    # Help intent
    # -------------------------
    if lower in ["help", "commands", "what can you do", "what can you do?"]:
        return (
            "Helix commands:\n"
            "- What time is it?\n"
            "- What's the latest scan?\n"
            "- Scan MES\n"
            "- Help\n\n"
            "You can also ask regular questions."
        )

    # -------------------------
    # Time intent
    # -------------------------
    time_phrases = [
        "time",
        "what time",
        "current time",
        "what's the time",
        "whats the time",
        "tell me the time",
    ]

    if has_any(lower, time_phrases):
        now = datetime.now(TIMEZONE)
        return now.strftime("It is %I:%M %p MT on %b %d.").replace(" 0", " ")

    # -------------------------
    # Latest scan intent
    # -------------------------
    latest_scan_phrases = [
        "latest scan",
        "latest mes scan",
        "last scan",
        "recent scan",
        "what changed",
        "market update",
    ]

    if has_any(lower, latest_scan_phrases) or ("latest" in lower and "scan" in lower):
        return get_latest_scan_summary()

    # -------------------------
    # Force MES scan intent
    # -------------------------
    wants_scan = has_any(lower, ["scan", "analyze", "run analysis", "check"])
    mentions_mes = "mes" in lower

    if wants_scan and mentions_mes:
        return force_mes_scan()

    return ask_helix(clean)


# -------------------------
# Main loop
# -------------------------
def run_bridge():
    print("Helix iMessage bridge started.")
    print(f"Allowed sender: {ALLOWED_SENDER}")
    print("Initializing from latest existing message so old messages are ignored...")

    last_seen_rowid = get_latest_inbound_rowid()

    print(f"Starting after ROWID: {last_seen_rowid}")
    print("Text Helix from your phone to test.")
    print("Press CTRL+C to stop.")
    print()

    while True:
        try:
            messages = get_new_inbound_messages(last_seen_rowid)

            if not messages:
                time.sleep(POLL_SECONDS)
                continue

            for msg in messages:
                rowid = msg["rowid"]
                sender = msg["sender"]
                text = msg["text"]

                last_seen_rowid = rowid

                if was_recently_sent_by_helix(text):
                    print(f"Ignored Helix echo: {text[:80]}")
                    continue

                print(f"Incoming from {sender}: {text}")

                reply = route_message(text)

                if len(reply) > MAX_REPLY_CHARS:
                    reply = reply[:MAX_REPLY_CHARS] + "\n\n[Truncated]"

                send_imessage(sender, reply)

                print("Reply sent.")
                print()

            time.sleep(POLL_SECONDS)

        except KeyboardInterrupt:
            print("Bridge stopped.")
            break

        except Exception as e:
            print("Bridge error:", e)
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    run_bridge()