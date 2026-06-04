from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import Any

from orbit import service as orbit_service


BASE_DIR = Path(__file__).resolve().parent
SCAN_HISTORY_PATH = BASE_DIR / "scan_history.jsonl"
ALIGNMENT_LABELS = ("aligned", "partially_aligned", "conflicted", "insufficient_data")


def generate_trading_correlation_review(
    *,
    limit: int = 20,
    symbol: str | None = None,
    session: str | None = None,
    strategy_mode: str | None = None,
    entries: list[dict[str, Any]] | None = None,
    scan_records: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    journal_entries = _filtered_entries(
        entries if entries is not None else orbit_service.list_trade_journal_entries(),
        limit=max(1, min(int(limit or 20), 100)),
        symbol=symbol,
        session=session,
        strategy_mode=strategy_mode,
    )

    if not journal_entries:
        message = "No journal entries available yet. Import or create trades first."
        return _empty_response(message, scan_records_found=True)

    scans = scan_records if scan_records is not None else load_scan_history_records()
    if not scans:
        message = "No scanner records found yet. Run scanner during trading sessions first."
        return _empty_response(
            message,
            trades_reviewed=len(journal_entries),
            scan_records_found=False,
        )

    correlations = [
        correlate_trade_to_scans(entry, scans)
        for entry in journal_entries
    ]
    summary = _summary(correlations)
    response = {
        "summary": summary,
        "correlations": correlations,
        "suggested_data_to_capture": summary["suggested_data_to_capture"],
        "warnings": [
            "This is read-only scanner/journal correlation. It does not create signals, update scanner behavior, or change the strategy model."
        ],
    }
    response["readable_summary"] = format_trading_correlation_summary(response)
    return response


def load_scan_history_records(path: Path = SCAN_HISTORY_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(record, dict):
                records.append(record)
    return records


def correlate_trade_to_scans(
    entry: dict[str, Any],
    scan_records: list[dict[str, Any]],
    *,
    before_minutes: int = 90,
    after_minutes: int = 30,
) -> dict[str, Any]:
    trade_time = _entry_datetime(entry)
    candidates = [
        scan
        for scan in scan_records
        if _same_symbol(entry, scan)
        and _same_trade_date(entry, scan, trade_time)
        and _same_session_if_needed(entry, scan, trade_time)
    ]
    before_scan = None
    after_scan = None
    missing_data: list[str] = []

    if trade_time is not None:
        before_cutoff = trade_time - timedelta(minutes=before_minutes)
        after_cutoff = trade_time + timedelta(minutes=after_minutes)
        before_scan = _nearest_scan(
            [
                scan
                for scan in candidates
                if (scan_time := _scan_datetime(scan)) is not None
                and before_cutoff <= scan_time <= trade_time
            ],
            trade_time,
        )
        after_scan = _nearest_scan(
            [
                scan
                for scan in candidates
                if (scan_time := _scan_datetime(scan)) is not None
                and trade_time <= scan_time <= after_cutoff
            ],
            trade_time,
        )
    else:
        missing_data.append("Entry time missing; matched by symbol/date/session only.")
        same_session_scans = [
            scan
            for scan in candidates
            if _entry_session(entry)
            and _entry_session(entry) == _scan_session(scan)
        ]
        session_candidates = same_session_scans or candidates
        before_scan = _latest_scan(session_candidates)

    selected_scan = before_scan or after_scan
    scanner_fields = _scanner_fields(selected_scan)
    alignment_label, alignment_reasons, mismatch_reasons, alignment_missing = _alignment(
        entry,
        selected_scan,
        trade_time=trade_time,
    )
    missing_data.extend(alignment_missing)
    confidence = _match_confidence(
        trade_time=trade_time,
        before_scan=before_scan,
        after_scan=after_scan,
        selected_scan=selected_scan,
        scanner_fields=scanner_fields,
    )

    return {
        "journal_entry_id": entry.get("id"),
        "symbol": entry.get("symbol"),
        "trade_date": str(entry.get("trade_date") or "")[:10] or None,
        "direction": entry.get("direction"),
        "session": entry.get("session"),
        "result_dollars": entry.get("result_dollars"),
        "strategy_mode": entry.get("strategy_mode"),
        "entry_time": trade_time.isoformat() if trade_time else None,
        "matched_scan_before": _compact_scan(before_scan),
        "matched_scan_after": _compact_scan(after_scan),
        "match_confidence": confidence,
        **scanner_fields,
        "alignment_label": alignment_label,
        "alignment_reasons": alignment_reasons,
        "mismatch_reasons": mismatch_reasons,
        "missing_data": _dedupe(missing_data),
    }


def format_trading_correlation_summary(review: dict[str, Any]) -> str:
    summary = review.get("summary") or {}
    if summary.get("trades_reviewed", 0) == 0:
        return "No journal entries available yet. Import or create trades first."
    if not summary.get("scan_records_found", True):
        return "No scanner records found yet. Run scanner during trading sessions first."

    lines = [
        "Scanner + Journal Correlation",
        "",
        (
            f"Reviewed {summary.get('trades_reviewed', 0)} trade"
            f"{'s' if summary.get('trades_reviewed', 0) != 1 else ''}; "
            f"{summary.get('trades_with_scan_match', 0)} had nearby scanner context."
        ),
        (
            "Alignment: "
            f"{summary.get('aligned_count', 0)} aligned, "
            f"{summary.get('partially_aligned_count', 0)} partial, "
            f"{summary.get('conflicted_count', 0)} conflicted, "
            f"{summary.get('insufficient_data_count', 0)} insufficient."
        ),
    ]
    mismatches = summary.get("common_mismatches") or []
    if mismatches:
        lines.extend(["", "Common mismatches:", *[f"- {item['reason']} ({item['count']})" for item in mismatches[:4]]])
    suggested = summary.get("suggested_data_to_capture") or []
    if suggested:
        lines.extend(["", "Suggested data to capture:", *[f"- {item}" for item in suggested[:4]]])
    return "\n".join(lines)


def _empty_response(
    message: str,
    *,
    trades_reviewed: int = 0,
    scan_records_found: bool = True,
) -> dict[str, Any]:
    summary = {
        "trades_reviewed": trades_reviewed,
        "trades_with_scan_match": 0,
        "aligned_count": 0,
        "partially_aligned_count": 0,
        "conflicted_count": 0,
        "insufficient_data_count": trades_reviewed,
        "common_mismatches": [],
        "suggested_data_to_capture": [message],
        "scan_records_found": scan_records_found,
    }
    return {
        "summary": summary,
        "correlations": [],
        "suggested_data_to_capture": summary["suggested_data_to_capture"],
        "warnings": [],
        "readable_summary": message,
    }


def _filtered_entries(
    entries: list[dict[str, Any]],
    *,
    limit: int,
    symbol: str | None,
    session: str | None,
    strategy_mode: str | None,
) -> list[dict[str, Any]]:
    symbol_filter = symbol.strip().upper() if symbol else None
    session_filter = session.strip().casefold() if session else None
    mode_filter = strategy_mode.strip().casefold() if strategy_mode else None
    filtered: list[dict[str, Any]] = []
    for entry in entries:
        if symbol_filter and str(entry.get("symbol") or "").upper() != symbol_filter:
            continue
        if session_filter and str(entry.get("session") or "").casefold() != session_filter:
            continue
        if mode_filter and str(entry.get("strategy_mode") or "").casefold() != mode_filter:
            continue
        filtered.append(entry)
        if len(filtered) >= limit:
            break
    return filtered


def _summary(correlations: list[dict[str, Any]]) -> dict[str, Any]:
    labels = Counter(correlation["alignment_label"] for correlation in correlations)
    mismatches = Counter(
        reason
        for correlation in correlations
        for reason in correlation.get("mismatch_reasons", [])
    )
    missing = Counter(
        item
        for correlation in correlations
        for item in correlation.get("missing_data", [])
    )
    suggested = [
        "Capture trade entry time so scanner records can be matched by the 90m/30m window."
        if any("Entry time missing" in item for item in missing)
        else "",
        "Capture session consistently on journal entries and scanner context."
        if any("session" in item.casefold() for item in missing)
        else "",
        "Keep scanner running during trading sessions so there is before/after context."
        if labels.get("insufficient_data", 0)
        else "",
    ]
    return {
        "trades_reviewed": len(correlations),
        "trades_with_scan_match": sum(
            1
            for correlation in correlations
            if correlation.get("matched_scan_before") or correlation.get("matched_scan_after")
        ),
        "aligned_count": labels.get("aligned", 0),
        "partially_aligned_count": labels.get("partially_aligned", 0),
        "conflicted_count": labels.get("conflicted", 0),
        "insufficient_data_count": labels.get("insufficient_data", 0),
        "common_mismatches": [
            {"reason": reason, "count": count}
            for reason, count in mismatches.most_common(5)
        ],
        "suggested_data_to_capture": [item for item in suggested if item]
        or ["Capture entry time, session, journal narrative, and scanner context near active trades."],
        "scan_records_found": True,
    }


def _alignment(
    entry: dict[str, Any],
    scan: dict[str, Any] | None,
    *,
    trade_time: datetime | None,
) -> tuple[str, list[str], list[str], list[str]]:
    if scan is None:
        return "insufficient_data", [], ["No nearby scanner record found."], ["No nearby scanner record found."]

    narrative = _scan_narrative(scan)
    phase = str(narrative.get("narrative_phase") or scan.get("narrative_phase") or "").lower()
    direction = str(entry.get("direction") or "").lower()
    draw_direction = str(narrative.get("liquidity_draw_direction") or "").lower()
    signal_level = str(scan.get("signal_level") or "").lower()
    structure = str(narrative.get("structure_confirmation") or "").lower()
    behavior = str(narrative.get("behavior_inside_zone") or scan.get("behavior_confirmation") or "").lower()
    execution = str(narrative.get("execution_readiness") or "").lower()
    missing: list[str] = []
    alignment_reasons: list[str] = []
    mismatch_reasons: list[str] = []

    if trade_time is None:
        missing.append("Entry time missing; time-window confidence is lower.")
    if phase in {"", "no_clear_narrative"}:
        missing.append("Scanner narrative phase missing or unclear.")
    if draw_direction not in {"above", "below"}:
        missing.append("Scanner liquidity draw direction missing.")

    if phase == "narrative_invalidated" or execution == "invalidated":
        mismatch_reasons.append("Scanner narrative was invalidated near the trade.")
        return "conflicted", alignment_reasons, mismatch_reasons, missing

    direction_supports_draw = (
        (direction == "long" and draw_direction == "above")
        or (direction == "short" and draw_direction == "below")
    )
    direction_opposes_draw = (
        (direction == "long" and draw_direction == "below")
        or (direction == "short" and draw_direction == "above")
    )

    if direction_supports_draw:
        alignment_reasons.append("Trade direction supports scanner liquidity draw direction.")
    elif direction_opposes_draw:
        mismatch_reasons.append("Trade direction opposes scanner liquidity draw direction.")

    if phase in {"execution_watch", "continuation_confirmed"}:
        alignment_reasons.append(f"Scanner phase was {phase.replace('_', ' ')}.")
    elif phase:
        mismatch_reasons.append(f"Scanner phase was only {phase.replace('_', ' ')}.")

    if "5m confirms" in structure or "confirmed" in execution:
        alignment_reasons.append("Scanner structure/execution readiness supported continuation.")
    elif structure:
        mismatch_reasons.append(f"Scanner structure confirmation was {structure}.")

    if behavior and behavior not in {"none", "unknown"}:
        alignment_reasons.append(f"Scanner behavior showed {behavior.replace('_', ' ')}.")
    else:
        missing.append("Scanner behavior confirmation missing.")

    if direction_opposes_draw:
        return "conflicted", alignment_reasons, mismatch_reasons, missing
    if len(missing) >= 3:
        return "insufficient_data", alignment_reasons, mismatch_reasons, missing
    if direction_supports_draw and phase in {"execution_watch", "continuation_confirmed"}:
        return "aligned", alignment_reasons, mismatch_reasons, missing
    if direction_supports_draw or signal_level in {"watch", "review", "alert"}:
        return "partially_aligned", alignment_reasons, mismatch_reasons, missing
    if missing:
        return "insufficient_data", alignment_reasons, mismatch_reasons, missing
    return "partially_aligned", alignment_reasons, mismatch_reasons, missing


def _scanner_fields(scan: dict[str, Any] | None) -> dict[str, Any]:
    if scan is None:
        return {
            "scanner_narrative_phase": None,
            "scanner_signal_level": None,
            "scanner_liquidity_draw": None,
            "scanner_reaction_zone": None,
            "scanner_behavior": None,
            "scanner_structure_confirmation": None,
            "scanner_execution_readiness": None,
        }
    narrative = _scan_narrative(scan)
    return {
        "scanner_narrative_phase": narrative.get("narrative_phase") or scan.get("narrative_phase"),
        "scanner_signal_level": scan.get("signal_level"),
        "scanner_liquidity_draw": narrative.get("liquidity_draw"),
        "scanner_reaction_zone": narrative.get("htf_reaction_zone"),
        "scanner_behavior": narrative.get("behavior_inside_zone") or scan.get("behavior_confirmation"),
        "scanner_structure_confirmation": narrative.get("structure_confirmation"),
        "scanner_execution_readiness": narrative.get("execution_readiness"),
    }


def _scan_narrative(scan: dict[str, Any]) -> dict[str, Any]:
    narrative = scan.get("narrative")
    return narrative if isinstance(narrative, dict) else {}


def _entry_datetime(entry: dict[str, Any]) -> datetime | None:
    date_text = str(entry.get("trade_date") or "")[:10]
    time_value = (
        entry.get("entry_time")
        or entry.get("entry_datetime")
        or entry.get("opened_at")
    )
    if not date_text or not time_value:
        return None
    if isinstance(time_value, datetime):
        return time_value.replace(tzinfo=None)
    text = str(time_value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            parsed_time = datetime.strptime(text, fmt).time()
            return datetime.combine(datetime.fromisoformat(date_text).date(), parsed_time)
        except ValueError:
            continue
    return None


def _scan_datetime(scan: dict[str, Any]) -> datetime | None:
    value = scan.get("timestamp") or scan.get("created_at") or scan.get("scan_time")
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=None)


def _same_symbol(entry: dict[str, Any], scan: dict[str, Any]) -> bool:
    return str(entry.get("symbol") or "").upper() == str(scan.get("symbol") or "").upper()


def _same_trade_date(entry: dict[str, Any], scan: dict[str, Any], trade_time: datetime | None) -> bool:
    scan_time = _scan_datetime(scan)
    entry_date = trade_time.date().isoformat() if trade_time else str(entry.get("trade_date") or "")[:10]
    return bool(entry_date and scan_time and scan_time.date().isoformat() == entry_date)


def _same_session_if_needed(entry: dict[str, Any], scan: dict[str, Any], trade_time: datetime | None) -> bool:
    if trade_time is not None:
        return True
    entry_session = _entry_session(entry)
    return not entry_session or entry_session == _scan_session(scan)


def _entry_session(entry: dict[str, Any]) -> str:
    return str(entry.get("session") or "").casefold().strip()


def _scan_session(scan: dict[str, Any]) -> str:
    return str(scan.get("session_label") or "").casefold().strip()


def _nearest_scan(scans: list[dict[str, Any]], trade_time: datetime) -> dict[str, Any] | None:
    if not scans:
        return None
    return min(
        scans,
        key=lambda scan: abs((_scan_datetime(scan) or datetime.combine(trade_time.date(), time.min)) - trade_time),
    )


def _latest_scan(scans: list[dict[str, Any]]) -> dict[str, Any] | None:
    scans_with_times = [(scan, _scan_datetime(scan)) for scan in scans]
    scans_with_times = [(scan, scan_time) for scan, scan_time in scans_with_times if scan_time is not None]
    if not scans_with_times:
        return None
    return max(scans_with_times, key=lambda item: item[1])[0]


def _match_confidence(
    *,
    trade_time: datetime | None,
    before_scan: dict[str, Any] | None,
    after_scan: dict[str, Any] | None,
    selected_scan: dict[str, Any] | None,
    scanner_fields: dict[str, Any],
) -> str:
    if selected_scan is None:
        return "none"
    if trade_time is None:
        return "low"
    if before_scan and after_scan and scanner_fields.get("scanner_narrative_phase"):
        return "high"
    return "medium"


def _compact_scan(scan: dict[str, Any] | None) -> dict[str, Any] | None:
    if scan is None:
        return None
    narrative = _scan_narrative(scan)
    return {
        "timestamp": scan.get("timestamp"),
        "symbol": scan.get("symbol"),
        "session": scan.get("session_label"),
        "narrative_phase": narrative.get("narrative_phase") or scan.get("narrative_phase"),
        "signal_level": scan.get("signal_level"),
        "liquidity_draw": narrative.get("liquidity_draw"),
    }


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped
