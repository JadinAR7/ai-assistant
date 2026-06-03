from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


TIMEZONE = ZoneInfo("America/Denver")
BASE_DIR = Path(__file__).resolve().parent
SCANNER_SETTINGS_PATH = BASE_DIR / "scanner_settings.json"
SUPPORTED_SCANNER_SYMBOLS = ["MES", "MNQ", "ES", "NQ"]
DEFAULT_SCANNER_SYMBOL = "MES"


def _now_iso() -> str:
    return datetime.now(TIMEZONE).isoformat()


def _state_for_symbol(symbol: str, updated_at: str | None = None) -> dict:
    return {
        "default_symbol": symbol,
        "supported_symbols": deepcopy(SUPPORTED_SCANNER_SYMBOLS),
        "updated_at": updated_at or _now_iso(),
    }


def normalize_scanner_symbol(symbol: str | None) -> str:
    normalized = str(symbol or "").strip().upper()
    if normalized not in SUPPORTED_SCANNER_SYMBOLS:
        allowed = ", ".join(SUPPORTED_SCANNER_SYMBOLS)
        raise ValueError(f"Invalid scanner symbol '{symbol}'. Allowed symbols: {allowed}.")
    return normalized


def get_scanner_settings() -> dict:
    if not SCANNER_SETTINGS_PATH.exists():
        return _state_for_symbol(DEFAULT_SCANNER_SYMBOL)

    try:
        state = json.loads(SCANNER_SETTINGS_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _state_for_symbol(DEFAULT_SCANNER_SYMBOL)

    symbol = str(state.get("default_symbol") or DEFAULT_SCANNER_SYMBOL).strip().upper()
    if symbol not in SUPPORTED_SCANNER_SYMBOLS:
        symbol = DEFAULT_SCANNER_SYMBOL

    return _state_for_symbol(symbol, updated_at=state.get("updated_at"))


def get_default_scanner_symbol() -> str:
    return str(get_scanner_settings().get("default_symbol") or DEFAULT_SCANNER_SYMBOL)


def set_scanner_settings(default_symbol: str) -> dict:
    normalized = normalize_scanner_symbol(default_symbol)
    state = {
        "default_symbol": normalized,
        "updated_at": _now_iso(),
    }
    SCANNER_SETTINGS_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return get_scanner_settings()
