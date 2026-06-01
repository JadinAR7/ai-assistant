import csv
import json
import shutil
import tempfile
from datetime import datetime, time as dt_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


# -------------------------
# CSV refresh configuration
# -------------------------
TIMEZONE = ZoneInfo("America/Denver")
BASE_DIR = Path(__file__).resolve().parent
CSV_DATA_DIR = BASE_DIR / "csv_data"
CSV_REFRESH_STATUS_PATH = BASE_DIR / "csv_refresh_status.json"
CSV_REFRESH_TEMP_ROOT = BASE_DIR / "downloads" / "csv_refresh_tmp"

DEFAULT_SYMBOL = "MES"
REFRESH_TIMEFRAMES = ["1D", "4H", "1H", "15M", "1M"]

REQUIRED_CSV_COLUMNS = {"open", "high", "low", "close"}


# -------------------------
# Schedule logic
# -------------------------
def _normalize_now(now: datetime | None = None) -> datetime:
    if now is None:
        return datetime.now(TIMEZONE)

    if now.tzinfo is None:
        return now.replace(tzinfo=TIMEZONE)

    return now.astimezone(TIMEZONE)


def _minute_matches(now: datetime, hour: int, minute: int = 0) -> bool:
    return now.hour == hour and now.minute == minute


def _refresh_reason_for_time(now: datetime) -> str | None:
    now = _normalize_now(now)
    weekday = now.weekday()
    current_time = now.time()

    # Monday-Friday, hourly during New York session.
    if weekday in [0, 1, 2, 3, 4]:
        in_new_york_session = dt_time(7, 30) <= current_time <= dt_time(14, 0)

        if in_new_york_session and (
            (now.hour == 7 and now.minute == 30)
            or (now.minute == 0 and 8 <= now.hour <= 14)
        ):
            return "hourly_new_york_session"

    # Sunday-Thursday after futures reopen.
    if weekday in [6, 0, 1, 2, 3] and _minute_matches(now, 17, 0):
        return "futures_reopen_refresh"

    # Friday post-close review refresh.
    if weekday == 4 and _minute_matches(now, 15, 0):
        return "friday_post_close_review_refresh"

    return None


def should_refresh_csv_now(now: datetime | None = None) -> bool:
    return _refresh_reason_for_time(_normalize_now(now)) is not None


def _scheduled_times_for_date(day) -> list[tuple[datetime, str]]:
    weekday = day.weekday()
    scheduled = []

    if weekday in [0, 1, 2, 3, 4]:
        scheduled.append((
            datetime.combine(day, dt_time(7, 30), tzinfo=TIMEZONE),
            "hourly_new_york_session",
        ))

        for hour in range(8, 15):
            scheduled.append((
                datetime.combine(day, dt_time(hour, 0), tzinfo=TIMEZONE),
                "hourly_new_york_session",
            ))

    if weekday in [6, 0, 1, 2, 3]:
        scheduled.append((
            datetime.combine(day, dt_time(17, 0), tzinfo=TIMEZONE),
            "futures_reopen_refresh",
        ))

    if weekday == 4:
        scheduled.append((
            datetime.combine(day, dt_time(15, 0), tzinfo=TIMEZONE),
            "friday_post_close_review_refresh",
        ))

    return sorted(scheduled, key=lambda item: item[0])


def _next_expected_window(now: datetime | None = None) -> dict:
    now = _normalize_now(now)

    for day_offset in range(8):
        day = (now + timedelta(days=day_offset)).date()

        for scheduled_time, reason in _scheduled_times_for_date(day):
            if scheduled_time > now:
                return {
                    "timestamp": scheduled_time.isoformat(),
                    "reason": reason,
                    "timezone": "America/Denver",
                }

    return {
        "timestamp": None,
        "reason": None,
        "timezone": "America/Denver",
    }


# -------------------------
# Status storage
# -------------------------
def _default_status(now: datetime | None = None) -> dict:
    return {
        "enabled": True,
        "last_attempt": None,
        "last_success": None,
        "last_error": None,
        "last_refresh_reason": None,
        "next_expected_window": _next_expected_window(now),
        "files_refreshed": [],
    }


def _read_status() -> dict:
    if not CSV_REFRESH_STATUS_PATH.exists():
        return _default_status()

    try:
        with CSV_REFRESH_STATUS_PATH.open("r", encoding="utf-8") as f:
            stored = json.load(f)
    except (OSError, json.JSONDecodeError):
        stored = {}

    status = _default_status()
    status.update(stored if isinstance(stored, dict) else {})
    status["next_expected_window"] = _next_expected_window()

    return status


def _write_status(status: dict) -> None:
    CSV_REFRESH_STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)

    with CSV_REFRESH_STATUS_PATH.open("w", encoding="utf-8") as f:
        json.dump(status, f, indent=2)


def get_csv_refresh_status() -> dict:
    status = _read_status()
    _write_status(status)
    return status


# -------------------------
# Future-safe file handling
# -------------------------
def _expected_csv_names(symbol: str = DEFAULT_SYMBOL) -> dict[str, str]:
    symbol = symbol.upper()
    return {
        timeframe: f"{symbol}_{timeframe}.csv"
        for timeframe in REFRESH_TIMEFRAMES
    }


def _verify_csv_file(path: Path) -> tuple[bool, str | None]:
    if not path.exists():
        return False, "file does not exist"

    if path.stat().st_size <= 0:
        return False, "file is empty"

    try:
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            columns = {str(column).strip().lower() for column in (reader.fieldnames or [])}

            if not REQUIRED_CSV_COLUMNS.issubset(columns):
                missing = sorted(REQUIRED_CSV_COLUMNS - columns)
                return False, f"missing required columns: {missing}"

            first_row = next(reader, None)

            if not first_row:
                return False, "file has headers but no rows"

    except Exception as e:
        return False, f"could not read CSV: {e}"

    return True, None


def _verify_replacement_set(temp_dir: Path, symbol: str = DEFAULT_SYMBOL) -> tuple[bool, dict, dict]:
    verified = {}
    failures = {}

    for timeframe, filename in _expected_csv_names(symbol).items():
        path = temp_dir / filename
        ok, error = _verify_csv_file(path)

        if ok:
            verified[timeframe] = str(path)
        else:
            failures[timeframe] = error

    return len(verified) == len(REFRESH_TIMEFRAMES), verified, failures


def _replace_active_csvs_after_verification(verified_files: dict, symbol: str = DEFAULT_SYMBOL) -> list[str]:
    """
    Future use only: active CSVs are replaced after all replacements verify.
    Existing CSVs are never deleted first; each verified file is copied into place.
    """
    refreshed = []
    expected_names = _expected_csv_names(symbol)
    CSV_DATA_DIR.mkdir(parents=True, exist_ok=True)

    for timeframe, source in verified_files.items():
        destination = CSV_DATA_DIR / expected_names[timeframe]
        shutil.copyfile(source, destination)
        refreshed.append(str(destination))

    return refreshed


# -------------------------
# Refresh runner
# -------------------------
def _run_placeholder_export(temp_dir: Path, symbol: str = DEFAULT_SYMBOL) -> dict:
    return {
        "success": False,
        "implemented": False,
        "symbol": symbol,
        "temp_dir": str(temp_dir),
        "files_refreshed": [],
        "message": (
            "CSV refresh scheduler foundation is installed, but safe TradingView "
            "CSV export is not implemented yet. Existing CSVs were left untouched."
        ),
    }


def run_csv_refresh(force: bool = False) -> dict:
    now = _normalize_now()
    status = _read_status()

    if not status.get("enabled", True):
        status.update({
            "last_attempt": now.isoformat(),
            "last_error": "CSV refresh is disabled.",
            "last_refresh_reason": "disabled",
            "next_expected_window": _next_expected_window(now),
            "files_refreshed": [],
        })
        _write_status(status)

        return {
            "success": False,
            "skipped": True,
            "status": status,
            "message": "CSV refresh is disabled.",
        }

    scheduled_reason = _refresh_reason_for_time(now)

    if not force and not scheduled_reason:
        status.update({
            "last_attempt": now.isoformat(),
            "last_error": None,
            "last_refresh_reason": "outside_refresh_window",
            "next_expected_window": _next_expected_window(now),
            "files_refreshed": [],
        })
        _write_status(status)

        return {
            "success": True,
            "skipped": True,
            "status": status,
            "message": "Outside CSV refresh window. No CSV refresh ran.",
        }

    refresh_reason = "manual_force" if force else scheduled_reason
    CSV_REFRESH_TEMP_ROOT.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="csv_refresh_", dir=CSV_REFRESH_TEMP_ROOT) as temp_path:
        temp_dir = Path(temp_path)
        export_result = _run_placeholder_export(temp_dir, DEFAULT_SYMBOL)

        # The verification/replacement path is ready for a real exporter, but
        # remains inactive until exports are downloaded into temp_dir.
        verified_all, verified_files, verification_failures = _verify_replacement_set(
            temp_dir,
            DEFAULT_SYMBOL,
        )
        files_refreshed = []

        if export_result.get("success") and verified_all:
            files_refreshed = _replace_active_csvs_after_verification(
                verified_files,
                DEFAULT_SYMBOL,
            )

    success = bool(export_result.get("success") and files_refreshed)
    error = None if success else export_result.get("message")

    status.update({
        "last_attempt": now.isoformat(),
        "last_success": now.isoformat() if success else status.get("last_success"),
        "last_error": error,
        "last_refresh_reason": refresh_reason,
        "next_expected_window": _next_expected_window(now),
        "files_refreshed": files_refreshed,
    })
    _write_status(status)

    return {
        "success": success,
        "implemented": bool(export_result.get("implemented")),
        "refresh_reason": refresh_reason,
        "status": status,
        "files_refreshed": files_refreshed,
        "verification": {
            "verified_all": verified_all,
            "verified_files": verified_files,
            "failures": verification_failures,
        },
        "message": export_result.get("message"),
    }
