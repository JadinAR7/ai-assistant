import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests


TIMEZONE = ZoneInfo("America/Denver")
BASE_DIR = Path(__file__).resolve().parent

CALENDAR_LOOKAHEAD_DAYS = 7
REQUEST_TIMEOUT_SECONDS = 5

MAJOR_KEYWORDS = [
    "fomc",
    "federal funds",
    "fed interest rate",
    "powell",
    "non-farm",
    "nonfarm",
    "nfp",
    "employment",
    "unemployment",
    "average hourly earnings",
    "cpi",
    "consumer price",
    "ppi",
    "producer price",
    "gdp",
    "ism",
    "pmi",
]

FED_SPEAKER_KEYWORDS = [
    "fed",
    "fomc",
    "powell",
    "waller",
    "bowman",
    "jefferson",
    "barr",
    "cook",
    "kugler",
    "williams",
    "barkin",
    "bostic",
    "collins",
    "daly",
    "goolsbee",
    "hammack",
    "kashkari",
    "logan",
    "musalem",
    "schmid",
]


def _parse_datetime(value) -> datetime | None:
    if not value:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value).strip()

        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"

        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=TIMEZONE)

    return parsed.astimezone(TIMEZONE)


def _load_json_file(path: Path) -> list[dict]:
    if not path.exists():
        return []

    data = json.loads(path.read_text(encoding="utf-8"))

    if isinstance(data, dict):
        data = data.get("events") or data.get("items") or data.get("news") or []

    return data if isinstance(data, list) else []


def _load_json_url(url: str | None) -> list[dict]:
    if not url:
        return []

    response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    data = response.json()

    if isinstance(data, dict):
        data = data.get("events") or data.get("items") or data.get("news") or []

    return data if isinstance(data, list) else []


def _event_title(event: dict) -> str:
    return str(
        event.get("title")
        or event.get("name")
        or event.get("event")
        or "Untitled event"
    )


def _event_time(event: dict) -> datetime | None:
    return _parse_datetime(
        event.get("time")
        or event.get("timestamp")
        or event.get("datetime")
        or event.get("date")
    )


def _event_importance(event: dict) -> str:
    raw = str(
        event.get("importance")
        or event.get("impact")
        or event.get("folder")
        or ""
    ).lower()

    if "red" in raw or "high" in raw:
        return "red"

    if "orange" in raw or "medium" in raw:
        return "orange"

    return raw or "unknown"


def _is_usd_event(event: dict) -> bool:
    currency = str(event.get("currency") or event.get("country") or "").upper()
    return not currency or currency == "USD" or "UNITED STATES" in currency or currency == "US"


def _has_keyword(text: str, keywords: list[str]) -> bool:
    lowered = text.lower()
    return any(keyword in lowered for keyword in keywords)


def _event_category(event: dict) -> str:
    title = _event_title(event)
    raw_category = str(event.get("category") or event.get("type") or "").lower()
    combined = f"{title} {raw_category}"

    if _has_keyword(combined, FED_SPEAKER_KEYWORDS) and any(
        word in combined.lower()
        for word in ["speaks", "speech", "remarks", "testifies", "speaker"]
    ):
        return "fed_speaker"

    if "fomc" in combined.lower():
        return "fomc"

    if _has_keyword(combined, MAJOR_KEYWORDS):
        return "major"

    return "scheduled"


def _normalize_event(event: dict) -> dict | None:
    event_time = _event_time(event)

    if not event_time or not _is_usd_event(event):
        return None

    title = _event_title(event)
    importance = _event_importance(event)
    category = _event_category(event)

    include = importance in ["red", "orange"] or category in ["fed_speaker", "fomc", "major"]

    if not include:
        return None

    return {
        "title": title,
        "time": event_time.isoformat(),
        "importance": importance,
        "category": category,
        "source": event.get("source"),
    }


def _time_until(now: datetime, event_time: datetime) -> str:
    delta = event_time - now

    if delta.total_seconds() < 0:
        return "now"

    minutes = int(delta.total_seconds() // 60)

    if minutes < 60:
        return f"in {minutes} min"

    hours = minutes // 60

    if hours < 24:
        return f"in {hours}h {minutes % 60}m"

    days = hours // 24
    return f"in {days}d {hours % 24}h"


def _display_time(now: datetime, event: dict) -> str:
    event_time = _parse_datetime(event.get("time"))

    if not event_time:
        return "time unknown"

    if event_time.date() == now.date():
        day_text = "today"
    elif event_time.date() == (now + timedelta(days=1)).date():
        day_text = "tomorrow"
    else:
        day_text = event_time.strftime("%a %b %-d")

    return f"{day_text} {event_time.strftime('%-I:%M %p %Z')}"


def _load_calendar_events() -> tuple[list[dict], list[str]]:
    statuses = []
    events = []

    local_path = Path(os.getenv("NEWS_RISK_CALENDAR_PATH", BASE_DIR / "news_calendar.json"))
    calendar_url = os.getenv("NEWS_RISK_CALENDAR_URL")

    try:
        local_events = _load_json_file(local_path)
        if local_events:
            statuses.append(f"loaded local calendar: {local_path}")
            events.extend(local_events)
    except Exception as e:
        statuses.append(f"local calendar unavailable: {e}")

    try:
        url_events = _load_json_url(calendar_url)
        if url_events:
            statuses.append("loaded calendar URL")
            events.extend(url_events)
    except Exception as e:
        statuses.append(f"calendar URL unavailable: {e}")

    if not events:
        statuses.append("no calendar events available")

    return events, statuses


def _load_breaking_news() -> tuple[list[dict], list[str]]:
    statuses = []
    items = []

    local_path = Path(os.getenv("NEWS_RISK_BREAKING_PATH", BASE_DIR / "breaking_news.json"))
    breaking_url = os.getenv("NEWS_RISK_BREAKING_URL")

    try:
        local_items = _load_json_file(local_path)
        if local_items:
            statuses.append(f"loaded local breaking news: {local_path}")
            items.extend(local_items)
    except Exception as e:
        statuses.append(f"local breaking news unavailable: {e}")

    try:
        url_items = _load_json_url(breaking_url)
        if url_items:
            statuses.append("loaded breaking news URL")
            items.extend(url_items)
    except Exception as e:
        statuses.append(f"breaking news URL unavailable: {e}")

    if not items:
        statuses.append("no breaking news available")

    return items, statuses


def build_news_risk_summary(now: datetime | None = None) -> dict:
    now = now.astimezone(TIMEZONE) if now else datetime.now(TIMEZONE)
    window_end = now + timedelta(days=CALENDAR_LOOKAHEAD_DAYS)

    raw_events, calendar_status = _load_calendar_events()
    raw_breaking, breaking_status = _load_breaking_news()

    events = []

    for raw_event in raw_events:
        normalized = _normalize_event(raw_event)

        if not normalized:
            continue

        event_time = _parse_datetime(normalized.get("time"))

        if now <= event_time <= window_end:
            events.append(normalized)

    events = sorted(events, key=lambda event: event["time"])

    red_events = [event for event in events if event["importance"] == "red"]
    orange_events = [event for event in events if event["importance"] == "orange"]
    fed_speakers = [event for event in events if event["category"] == "fed_speaker"]
    major_events = [
        event for event in events
        if event["importance"] == "red" or event["category"] in ["fomc", "major"]
    ]

    next_major_event = major_events[0] if major_events else None
    risk = "Low"

    if next_major_event:
        event_time = _parse_datetime(next_major_event.get("time"))
        hours_until = (event_time - now).total_seconds() / 3600

        if hours_until <= 24 or next_major_event.get("importance") == "red":
            risk = "High"
        else:
            risk = "Medium"
    elif orange_events or fed_speakers:
        risk = "Medium"

    breaking_items = []

    for item in raw_breaking:
        title = _event_title(item)

        if title and title != "Untitled event":
            breaking_items.append({
                "title": title,
                "source": item.get("source"),
                "time": str(item.get("time") or item.get("timestamp") or ""),
            })

    return {
        "success": True,
        "timestamp": now.isoformat(),
        "timezone": "America/Denver",
        "risk": risk,
        "next_major_event": next_major_event,
        "time_until_event": (
            _time_until(now, _parse_datetime(next_major_event["time"]))
            if next_major_event
            else None
        ),
        "event_importance": next_major_event.get("importance") if next_major_event else None,
        "upcoming_events": events,
        "upcoming_red_usd_events": red_events,
        "upcoming_orange_usd_events": orange_events,
        "fed_speakers": fed_speakers,
        "fomc_related_events": [event for event in events if event["category"] == "fomc"],
        "employment_events": [event for event in events if _has_keyword(event["title"], ["employment", "unemployment", "nfp", "non-farm", "nonfarm"])],
        "inflation_events": [event for event in events if _has_keyword(event["title"], ["cpi", "ppi", "consumer price", "producer price"])],
        "gdp_events": [event for event in events if _has_keyword(event["title"], ["gdp"])],
        "ism_events": [event for event in events if _has_keyword(event["title"], ["ism", "pmi"])],
        "nfp_events": [event for event in events if _has_keyword(event["title"], ["nfp", "non-farm", "nonfarm"])],
        "breaking_news": breaking_items,
        "provider_status": {
            "calendar": calendar_status,
            "breaking_news": breaking_status,
        },
    }


def format_news_risk_section(summary: dict) -> str:
    now = _parse_datetime(summary.get("timestamp")) or datetime.now(TIMEZONE)
    upcoming = summary.get("upcoming_events", [])
    upcoming = sorted(upcoming, key=lambda event: event["time"])[:5]
    fed_speakers = summary.get("fed_speakers", [])[:3]
    breaking_news = summary.get("breaking_news", [])[:5]

    lines = [
        "## News Risk",
        f"News Risk: {summary.get('risk', 'Low')}",
        "",
        "Upcoming:",
    ]

    if upcoming:
        for event in upcoming:
            lines.append(
                f"- {event['title']} ({_display_time(now, event)}, {event.get('importance', 'unknown')})"
            )
    else:
        lines.append("- None detected")

    next_major = summary.get("next_major_event")

    if next_major:
        lines.extend([
            "",
            f"Next major event: {next_major['title']} ({summary.get('time_until_event')}, {summary.get('event_importance')})",
        ])
    else:
        lines.extend([
            "",
            "Next major event: None detected",
        ])

    lines.extend([
        "",
        "Fed Speakers:",
    ])

    if fed_speakers:
        for event in fed_speakers:
            lines.append(f"- {event['title']} ({_display_time(now, event)})")
    else:
        lines.append("- None detected")

    lines.extend([
        "",
        "Breaking News:",
    ])

    if breaking_news:
        for item in breaking_news:
            lines.append(f"- {item['title']}")
    else:
        lines.append("- None detected")

    return "\n".join(lines)
