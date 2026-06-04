from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from typing import Any

import trading_strategy
from orbit import service as orbit_service


MODEL_FIELDS = {
    "htf_bias": "HTF bias",
    "draw_on_liquidity": "draw on liquidity",
    "reaction_zone": "reaction zone",
    "behavior_tags": "behavior tags",
    "execution_tags": "execution tags",
    "why_taken": "narrative explanation",
    "liquidity_target": "target liquidity",
    "lesson_learned": "review/lesson",
}

SESSIONS = ("Asia", "London", "New York", "After Hours")
STRATEGY_MODES = ("Scalp", "Day Trade", "Hybrid / Review")


def generate_trading_coach_review(
    *,
    limit: int = 20,
    symbol: str | None = None,
    session: str | None = None,
    strategy_mode: str | None = None,
    today_only: bool = False,
    entries: list[dict[str, Any]] | None = None,
    strategy_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Review saved journal entries without changing scanner or strategy state."""
    profile = strategy_profile or trading_strategy.get_strategy_profile()
    filtered_entries = _filtered_entries(
        entries if entries is not None else orbit_service.list_trade_journal_entries(),
        limit=max(1, min(int(limit or 20), 100)),
        symbol=symbol,
        session=session,
        strategy_mode=strategy_mode,
        today_only=today_only,
    )

    if not filtered_entries:
        message = "No journal entries available yet. Import or create trades first."
        return {
            "summary": {
                "total_trades_reviewed": 0,
                "wins": None,
                "losses": None,
                "total_pnl": None,
                "average_pnl": None,
                "strategy_mode_distribution": _zero_distribution(STRATEGY_MODES),
                "session_distribution": _zero_distribution(SESSIONS),
                "strategy_profile": profile.get("name", trading_strategy.STRATEGY_PROFILE_NAME),
            },
            "strengths": [],
            "weaknesses": [],
            "missing_data": [message],
            "model_alignment": {
                "label": "No data",
                "score": 0,
                "complete_context_trades": 0,
                "weak_context_trades": 0,
                "required_fields": list(MODEL_FIELDS.values()),
            },
            "suggested_focus": [message],
            "recent_trades_reviewed": [],
            "warnings": [],
            "readable_summary": message,
        }

    counts = _review_counts(filtered_entries)
    alignment = _model_alignment(filtered_entries)
    missing_data = _missing_data_guidance(filtered_entries)
    common_behavior = _common_list_values(filtered_entries, "behavior_tags")
    common_execution = _common_list_values(filtered_entries, "execution_tags")
    common_draws = _common_list_values(filtered_entries, "draw_on_liquidity")
    common_zones = _common_scalar_values(filtered_entries, "reaction_zone")
    lessons = _recurring_lessons(filtered_entries)
    strengths = _strengths(counts, alignment, common_behavior, common_execution, common_draws, common_zones)
    weaknesses = _weaknesses(counts, alignment, missing_data)
    warnings = _warnings(filtered_entries, missing_data)
    suggested_focus = _suggested_focus(alignment, missing_data, common_draws, common_zones)

    summary = {
        **counts,
        "common_behavior_tags": common_behavior,
        "common_execution_tags": common_execution,
        "common_liquidity_draws": common_draws,
        "common_reaction_zones": common_zones,
        "recurring_lessons_learned": lessons,
        "strategy_profile": profile.get("name", trading_strategy.STRATEGY_PROFILE_NAME),
    }
    response = {
        "summary": summary,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "missing_data": missing_data,
        "model_alignment": alignment,
        "suggested_focus": suggested_focus,
        "recent_trades_reviewed": [_compact_trade(entry) for entry in filtered_entries],
        "warnings": warnings,
    }
    correlation = _optional_scanner_correlation(
        limit=len(filtered_entries),
        symbol=symbol,
        session=session,
        strategy_mode=strategy_mode,
        entries=filtered_entries,
    )
    if correlation is not None:
        response["scanner_correlation"] = correlation
    response["readable_summary"] = format_trading_coach_summary(response)
    return response


def format_trading_coach_summary(review: dict[str, Any]) -> str:
    summary = review.get("summary") or {}
    total = summary.get("total_trades_reviewed") or 0
    if total == 0:
        return "No journal entries available yet. Import or create trades first."

    alignment = review.get("model_alignment") or {}
    pnl_line = "PnL data is incomplete."
    if summary.get("total_pnl") is not None:
        pnl_line = (
            f"PnL: ${summary['total_pnl']:.2f} total, "
            f"${summary['average_pnl']:.2f} average."
        )
        if summary.get("wins") is not None and summary.get("losses") is not None:
            pnl_line += f" Wins/losses: {summary['wins']}/{summary['losses']}."

    lines = [
        "Trading Coach Review",
        "",
        f"Reviewed {total} trade{'s' if total != 1 else ''}. {pnl_line}",
        f"Model alignment: {alignment.get('label', 'No data')} ({alignment.get('score', 0)}%).",
    ]

    for heading, key in (
        ("Strengths", "strengths"),
        ("Weaknesses", "weaknesses"),
        ("Suggested focus", "suggested_focus"),
        ("Missing data", "missing_data"),
    ):
        values = [str(value) for value in review.get(key, []) if str(value).strip()]
        if values:
            lines.extend(["", f"{heading}:", *[f"- {value}" for value in values[:4]]])

    correlation = review.get("scanner_correlation") or {}
    if correlation:
        lines.extend(
            [
                "",
                "Scanner Correlation:",
                (
                    f"- {correlation.get('trades_with_scan_match', 0)} matched scans; "
                    f"{correlation.get('aligned_count', 0)} aligned, "
                    f"{correlation.get('partially_aligned_count', 0)} partial, "
                    f"{correlation.get('conflicted_count', 0)} conflicted."
                ),
            ]
        )

    warnings = [str(value) for value in review.get("warnings", []) if str(value).strip()]
    if warnings:
        lines.extend(["", "Warnings:", *[f"- {value}" for value in warnings[:3]]])

    return "\n".join(lines)


def _filtered_entries(
    entries: list[dict[str, Any]],
    *,
    limit: int,
    symbol: str | None,
    session: str | None,
    strategy_mode: str | None,
    today_only: bool,
) -> list[dict[str, Any]]:
    today = date.today().isoformat()
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
        if today_only and str(entry.get("trade_date") or "")[:10] != today:
            continue
        filtered.append(entry)
        if len(filtered) >= limit:
            break

    return filtered


def _review_counts(entries: list[dict[str, Any]]) -> dict[str, Any]:
    pnls = [
        float(entry["result_dollars"])
        for entry in entries
        if entry.get("result_dollars") is not None
    ]
    total_pnl = round(sum(pnls), 2) if pnls else None
    average_pnl = round(total_pnl / len(pnls), 2) if pnls and total_pnl is not None else None
    mode_counter = Counter(str(entry.get("strategy_mode") or "Hybrid / Review") for entry in entries)
    session_counter = Counter(str(entry.get("session") or "Unspecified") for entry in entries)

    return {
        "total_trades_reviewed": len(entries),
        "wins": sum(1 for pnl in pnls if pnl > 0) if pnls else None,
        "losses": sum(1 for pnl in pnls if pnl < 0) if pnls else None,
        "total_pnl": total_pnl,
        "average_pnl": average_pnl,
        "strategy_mode_distribution": {
            mode: mode_counter.get(mode, 0) for mode in STRATEGY_MODES
        },
        "session_distribution": {
            **{session: session_counter.get(session, 0) for session in SESSIONS},
            "Unspecified": session_counter.get("Unspecified", 0),
        },
    }


def _model_alignment(entries: list[dict[str, Any]]) -> dict[str, Any]:
    per_trade: list[dict[str, Any]] = []
    total_present = 0
    required_count = len(MODEL_FIELDS)

    for entry in entries:
        present = [label for key, label in MODEL_FIELDS.items() if _has_value(entry.get(key))]
        missing = [label for label in MODEL_FIELDS.values() if label not in present]
        total_present += len(present)
        per_trade.append(
            {
                "entry_id": entry.get("id"),
                "symbol": entry.get("symbol"),
                "present": present,
                "missing": missing,
                "score": round((len(present) / required_count) * 100),
            }
        )

    score = round((total_present / (len(entries) * required_count)) * 100)
    if score >= 80:
        label = "Strong alignment"
    elif score >= 50:
        label = "Moderate alignment"
    else:
        label = "Weak alignment"

    return {
        "label": label,
        "score": score,
        "complete_context_trades": sum(1 for item in per_trade if not item["missing"]),
        "weak_context_trades": sum(1 for item in per_trade if item["score"] < 50),
        "required_fields": list(MODEL_FIELDS.values()),
        "per_trade": per_trade,
    }


def _missing_data_guidance(entries: list[dict[str, Any]]) -> list[str]:
    missing_counts: Counter[str] = Counter()
    for entry in entries:
        for key, label in MODEL_FIELDS.items():
            if not _has_value(entry.get(key)):
                missing_counts[label] += 1

    total = len(entries)
    return [
        f"{label} missing on {count}/{total} reviewed trades."
        for label, count in missing_counts.most_common()
        if count > 0
    ]


def _strengths(
    counts: dict[str, Any],
    alignment: dict[str, Any],
    behavior: list[dict[str, Any]],
    execution: list[dict[str, Any]],
    draws: list[dict[str, Any]],
    zones: list[dict[str, Any]],
) -> list[str]:
    strengths: list[str] = []
    if alignment.get("score", 0) >= 80:
        strengths.append("Most trades include the Liquidity Narrative Continuation context needed for review.")
    if draws:
        strengths.append(f"Liquidity draw is being tracked, most often {draws[0]['value']}.")
    if zones:
        strengths.append(f"Reaction zones are being recorded, led by {zones[0]['value']}.")
    if behavior and execution:
        strengths.append("Behavior and execution tags are both present, so review can separate setup context from trigger quality.")
    if counts.get("wins") is not None:
        strengths.append("Result data is present, so wins, losses, and PnL can be reviewed without guessing.")
    return strengths or ["Journal entries exist and can now be used as coaching source data."]


def _weaknesses(
    counts: dict[str, Any],
    alignment: dict[str, Any],
    missing_data: list[str],
) -> list[str]:
    weaknesses: list[str] = []
    if alignment.get("score", 0) < 50:
        weaknesses.append("Too many entries are PnL-first instead of narrative-first.")
    elif alignment.get("score", 0) < 80:
        weaknesses.append("Some trades have enough context to review, but the model checklist is not consistent yet.")
    if counts.get("total_pnl") is None:
        weaknesses.append("PnL fields are missing, so performance review is limited.")
    if missing_data:
        weaknesses.append("Missing context fields reduce the usefulness of the review.")
    return weaknesses


def _suggested_focus(
    alignment: dict[str, Any],
    missing_data: list[str],
    draws: list[dict[str, Any]],
    zones: list[dict[str, Any]],
) -> list[str]:
    focus: list[str] = []
    if missing_data:
        focus.append("Before saving a trade, complete the missing model fields instead of only recording the result.")
    if alignment.get("score", 0) < 80:
        focus.append("Write the draw, reaction zone, behavior, execution trigger, and why before judging the PnL.")
    if not draws:
        focus.append("Add the draw on liquidity for each trade so the review can judge whether the target made sense.")
    if not zones:
        focus.append("Record the reaction zone so entries can be checked against the model instead of treated as isolated executions.")
    return focus or ["Keep using the current journal structure and review whether execution tags match the stated draw."]


def _warnings(entries: list[dict[str, Any]], missing_data: list[str]) -> list[str]:
    warnings: list[str] = []
    if any(entry.get("result_dollars") is None for entry in entries):
        warnings.append("Some trades do not have result data; PnL stats only use completed result fields.")
    if missing_data:
        warnings.append("This is a journal review only. It does not create signals, update scanner behavior, or change the strategy model.")
    return warnings


def _common_list_values(entries: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for entry in entries:
        for value in entry.get(key) or []:
            if str(value).strip():
                counter[str(value).strip()] += 1
    return _counter_items(counter)


def _common_scalar_values(entries: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    counter = Counter(
        str(entry.get(key)).strip()
        for entry in entries
        if str(entry.get(key) or "").strip()
    )
    return _counter_items(counter)


def _counter_items(counter: Counter[str], limit: int = 5) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": count}
        for value, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))[:limit]
    ]


def _recurring_lessons(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: defaultdict[str, int] = defaultdict(int)
    original: dict[str, str] = {}
    for entry in entries:
        lesson = str(entry.get("lesson_learned") or "").strip()
        if not lesson:
            continue
        key = " ".join(lesson.casefold().split())
        grouped[key] += 1
        original.setdefault(key, lesson)
    return [
        {"lesson": original[key], "count": count}
        for key, count in sorted(grouped.items(), key=lambda item: (-item[1], item[0]))[:5]
    ]


def _compact_trade(entry: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": entry.get("id"),
        "trade_date": entry.get("trade_date"),
        "symbol": entry.get("symbol"),
        "direction": entry.get("direction"),
        "result_dollars": entry.get("result_dollars"),
        "session": entry.get("session"),
        "strategy_mode": entry.get("strategy_mode"),
        "model_fields_present": [
            label for key, label in MODEL_FIELDS.items() if _has_value(entry.get(key))
        ],
        "model_fields_missing": [
            label for key, label in MODEL_FIELDS.items() if not _has_value(entry.get(key))
        ],
    }


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(str(item).strip() for item in value)
    return True


def _zero_distribution(values: tuple[str, ...]) -> dict[str, int]:
    return {value: 0 for value in values}


def _optional_scanner_correlation(
    *,
    limit: int,
    symbol: str | None,
    session: str | None,
    strategy_mode: str | None,
    entries: list[dict[str, Any]],
) -> dict[str, Any] | None:
    try:
        import trading_correlation

        review = trading_correlation.generate_trading_correlation_review(
            limit=limit,
            symbol=symbol,
            session=session,
            strategy_mode=strategy_mode,
            entries=entries,
        )
    except Exception:
        return None

    summary = review.get("summary") or {}
    if int(summary.get("trades_with_scan_match") or 0) <= 0:
        return None
    return {
        "trades_reviewed": summary.get("trades_reviewed", 0),
        "trades_with_scan_match": summary.get("trades_with_scan_match", 0),
        "aligned_count": summary.get("aligned_count", 0),
        "partially_aligned_count": summary.get("partially_aligned_count", 0),
        "conflicted_count": summary.get("conflicted_count", 0),
        "insufficient_data_count": summary.get("insufficient_data_count", 0),
    }
