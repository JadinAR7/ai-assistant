from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


TIMEZONE = ZoneInfo("America/Denver")
BASE_DIR = Path(__file__).resolve().parent
PRESENCE_STATE_PATH = BASE_DIR / "presence_status.json"
DEFAULT_MODE = "home"

PRESENCE_MODES: dict[str, dict] = {
    "home": {
        "mode": "home",
        "label": "Home",
        "description": "Normal local mode. Scanner can notify on review-level or stronger context.",
        "scanner_min_signal_level": "review",
        "notifications_allowed": True,
        "tts_allowed": False,
        "imessage_allowed": True,
        "scan_noise_profile": "normal",
    },
    "trading": {
        "mode": "trading",
        "label": "Trading",
        "description": "Quiet trading mode. Scanner only notifies on alert-level context.",
        "scanner_min_signal_level": "alert",
        "notifications_allowed": True,
        "tts_allowed": False,
        "imessage_allowed": True,
        "scan_noise_profile": "quiet",
    },
    "away": {
        "mode": "away",
        "label": "Away",
        "description": "Away mode. Scanner can notify on review-level or stronger context.",
        "scanner_min_signal_level": "review",
        "notifications_allowed": True,
        "tts_allowed": False,
        "imessage_allowed": True,
        "scan_noise_profile": "active",
    },
    "focus": {
        "mode": "focus",
        "label": "Focus",
        "description": "Focus mode. Scanner continues running and saving history, but outbound notifications are muted.",
        "scanner_min_signal_level": "alert",
        "notifications_allowed": False,
        "tts_allowed": False,
        "imessage_allowed": False,
        "scan_noise_profile": "silent",
    },
}


def _now_iso() -> str:
    return datetime.now(TIMEZONE).isoformat()


def _mode_config(mode: str) -> dict:
    return deepcopy(PRESENCE_MODES[mode])


def _state_for_mode(mode: str, updated_at: str | None = None) -> dict:
    config = _mode_config(mode)
    config["updated_at"] = updated_at or _now_iso()
    return config


def list_presence_modes() -> list[dict]:
    return [_mode_config(mode) for mode in PRESENCE_MODES]


def get_presence() -> dict:
    if not PRESENCE_STATE_PATH.exists():
        return _state_for_mode(DEFAULT_MODE)

    try:
        state = json.loads(PRESENCE_STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _state_for_mode(DEFAULT_MODE)

    mode = str(state.get("mode") or DEFAULT_MODE).lower()
    if mode not in PRESENCE_MODES:
        mode = DEFAULT_MODE

    return _state_for_mode(mode, updated_at=state.get("updated_at"))


def set_presence(mode: str) -> dict:
    normalized = str(mode or "").strip().lower()
    if normalized not in PRESENCE_MODES:
        allowed = ", ".join(PRESENCE_MODES)
        raise ValueError(f"Invalid presence mode '{mode}'. Allowed modes: {allowed}.")

    state = {
        "mode": normalized,
        "updated_at": _now_iso(),
    }
    PRESENCE_STATE_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return get_presence()
