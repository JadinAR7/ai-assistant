from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import trading_correlation
import trading_strategy
from orbit import service as orbit_service


SAMPLE_WARNING = "Sample size is small. Treat these as early observations, not conclusions."
SESSIONS = ("Asia", "London", "New York", "After Hours")
STRATEGY_MODES = ("Scalp", "Day Trade", "Hybrid / Review")
CONTEXT_FIELDS = {
    "htf_bias": "HTF bias",
    "draw_on_liquidity": "draw on liquidity",
    "reaction_zone": "reaction zone",
    "behavior_tags": "behavior tags",
    "execution_tags": "execution tags",
    "why_taken": "why trade was taken",
    "price_intent": "what price was trying to do",
    "liquidity_target": "target liquidity",
    "went_well": "what went well",
    "went_wrong": "what went wrong",
    "lesson_learned": "lesson learned",
}


def generate_pattern_discovery_review(
    *,
    limit: int = 50,
    symbol: str | None = None,
    session: str | None = None,
    strategy_mode: str | None = None,
    entries: list[dict[str, Any]] | None = None,
    correlation_review: dict[str, Any] | None = None,
    strategy_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = strategy_profile or trading_strategy.get_strategy_profile()
    filtered_entries = _filtered_entries(
        entries if entries is not None else orbit_service.list_trade_journal_entries(),
        limit=max(1, min(int(limit or 50), 200)),
        symbol=symbol,
        session=session,
        strategy_mode=strategy_mode,
    )

    if not filtered_entries:
        message = "No journal entries available yet. Import or create trades first."
        return {
            "summary": {
                "trades_reviewed": 0,
                "strategy_profile": profile.get("name", trading_strategy.STRATEGY_PROFILE_NAME),
            },
            "sample_size_warning": message,
            "recurring_strengths": [],
            "recurring_weaknesses": [],
            "profitable_contexts": [],
            "weak_contexts": [],
            "best_session_so_far": None,
            "weakest_session_so_far": None,
            "best_strategy_mode_so_far": None,
            "weakest_strategy_mode_so_far": None,
            "scanner_alignment_observations": [],
            "missing_data_patterns": [message],
            "suggested_next_review_questions": [message],
            "pattern_confidence": "low",
            "readable_summary": message,
        }

    correlations = _correlations(
        filtered_entries,
        correlation_review,
        limit=len(filtered_entries),
        symbol=symbol,
        session=session,
        strategy_mode=strategy_mode,
    )
    confidence = _pattern_confidence(len(filtered_entries))
    sample_warning = SAMPLE_WARNING if len(filtered_entries) < 10 else None
    missing_patterns = _missing_data_patterns(filtered_entries)
    sparse_context = len(missing_patterns) >= 5 or len(filtered_entries) < 3
    recurring_strengths = _recurring_review_text(filtered_entries, "went_well", "strength")
    recurring_weaknesses = _recurring_review_text(filtered_entries, "went_wrong", "weakness")
    profitable_contexts = [] if sparse_context else _context_patterns(filtered_entries, profitable=True)
    weak_contexts = [] if sparse_context else _context_patterns(filtered_entries, profitable=False)

    response = {
        "summary": _summary(filtered_entries, profile),
        "sample_size_warning": sample_warning,
        "recurring_strengths": recurring_strengths,
        "recurring_weaknesses": recurring_weaknesses,
        "profitable_contexts": profitable_contexts,
        "weak_contexts": weak_contexts,
        "best_session_so_far": _best_group(filtered_entries, "session", positive=True),
        "weakest_session_so_far": _best_group(filtered_entries, "session", positive=False),
        "best_strategy_mode_so_far": _best_group(filtered_entries, "strategy_mode", positive=True),
        "weakest_strategy_mode_so_far": _best_group(filtered_entries, "strategy_mode", positive=False),
        "scanner_alignment_observations": _scanner_alignment_observations(correlations),
        "missing_data_patterns": missing_patterns,
        "suggested_next_review_questions": _review_questions(missing_patterns, correlations),
        "pattern_confidence": confidence,
    }
    response["readable_summary"] = format_pattern_discovery_summary(response)
    return response


def format_pattern_discovery_summary(review: dict[str, Any]) -> str:
    summary = review.get("summary") or {}
    total = summary.get("trades_reviewed", 0)
    if total == 0:
        return "No journal entries available yet. Import or create trades first."

    lines = [
        "Pattern Discovery",
        "",
        (
            f"Reviewed {total} trade{'s' if total != 1 else ''}. "
            f"Pattern confidence: {review.get('pattern_confidence', 'low')}."
        ),
    ]
    if review.get("sample_size_warning"):
        lines.extend(["", str(review["sample_size_warning"])])

    for heading, key in (
        ("Recurring strengths", "recurring_strengths"),
        ("Recurring weaknesses", "recurring_weaknesses"),
        ("Profitable contexts so far", "profitable_contexts"),
        ("Weak contexts so far", "weak_contexts"),
        ("Scanner alignment observations", "scanner_alignment_observations"),
        ("Missing data patterns", "missing_data_patterns"),
        ("Suggested next review questions", "suggested_next_review_questions"),
    ):
        values = [str(value) for value in review.get(key, []) if str(value).strip()]
        if values:
            lines.extend(["", f"{heading}:", *[f"- {value}" for value in values[:4]]])
    return "\n".join(lines)


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


def _summary(entries: list[dict[str, Any]], profile: dict[str, Any]) -> dict[str, Any]:
    pnls = [float(entry["result_dollars"]) for entry in entries if entry.get("result_dollars") is not None]
    return {
        "trades_reviewed": len(entries),
        "trades_with_pnl": len(pnls),
        "total_pnl": round(sum(pnls), 2) if pnls else None,
        "average_pnl": round(sum(pnls) / len(pnls), 2) if pnls else None,
        "wins": sum(1 for pnl in pnls if pnl > 0) if pnls else None,
        "losses": sum(1 for pnl in pnls if pnl < 0) if pnls else None,
        "strategy_profile": profile.get("name", trading_strategy.STRATEGY_PROFILE_NAME),
    }


def _pattern_confidence(total: int) -> str:
    if total < 10:
        return "low"
    if total <= 30:
        return "medium"
    return "higher"


def _missing_data_patterns(entries: list[dict[str, Any]]) -> list[str]:
    missing = Counter()
    for entry in entries:
        for key, label in CONTEXT_FIELDS.items():
            if not _has_value(entry.get(key)):
                missing[label] += 1
    total = len(entries)
    return [
        f"{label} is missing on {count}/{total} trades; pattern confidence stays lower until this is captured consistently."
        for label, count in missing.most_common()
        if count > 0
    ]


def _recurring_review_text(entries: list[dict[str, Any]], key: str, label: str) -> list[str]:
    counter = Counter(_normalize_text(entry.get(key)) for entry in entries if _normalize_text(entry.get(key)))
    if not counter:
        return []
    return [
        f"Early {label}: {text} appeared on {count} trade{'s' if count != 1 else ''}."
        for text, count in counter.most_common(4)
    ]


def _context_patterns(entries: list[dict[str, Any]], *, profitable: bool) -> list[str]:
    contexts: list[tuple[str, str, float]] = []
    for key, label in (
        ("session", "session"),
        ("strategy_mode", "strategy mode"),
        ("symbol", "symbol"),
        ("direction", "direction"),
        ("htf_bias", "HTF bias"),
        ("reaction_zone", "reaction zone"),
    ):
        contexts.extend(_scalar_context(entries, key, label, profitable=profitable))
    for key, label in (
        ("draw_on_liquidity", "liquidity draw"),
        ("behavior_tags", "behavior tag"),
        ("execution_tags", "execution tag"),
    ):
        contexts.extend(_list_context(entries, key, label, profitable=profitable))

    sorted_contexts = sorted(
        contexts,
        key=lambda item: (item[2], item[1]),
        reverse=profitable,
    )
    return [
        f"{label} '{value}' appears {'profitable' if profitable else 'weak'} so far: average PnL ${average:.2f}."
        for label, value, average in sorted_contexts[:5]
    ]


def _scalar_context(entries: list[dict[str, Any]], key: str, label: str, *, profitable: bool) -> list[tuple[str, str, float]]:
    grouped: defaultdict[str, list[float]] = defaultdict(list)
    for entry in entries:
        value = str(entry.get(key) or "").strip()
        pnl = entry.get("result_dollars")
        if not value or pnl is None:
            continue
        grouped[value].append(float(pnl))
    return _context_group_items(grouped, label, profitable=profitable)


def _list_context(entries: list[dict[str, Any]], key: str, label: str, *, profitable: bool) -> list[tuple[str, str, float]]:
    grouped: defaultdict[str, list[float]] = defaultdict(list)
    for entry in entries:
        pnl = entry.get("result_dollars")
        if pnl is None:
            continue
        for value in entry.get(key) or []:
            text = str(value).strip()
            if text:
                grouped[text].append(float(pnl))
    return _context_group_items(grouped, label, profitable=profitable)


def _context_group_items(grouped: defaultdict[str, list[float]], label: str, *, profitable: bool) -> list[tuple[str, str, float]]:
    items: list[tuple[str, str, float]] = []
    for value, pnls in grouped.items():
        if len(pnls) < 2:
            continue
        average = round(sum(pnls) / len(pnls), 2)
        if profitable and average > 0:
            items.append((label, value, average))
        if not profitable and average < 0:
            items.append((label, value, average))
    return items


def _best_group(entries: list[dict[str, Any]], key: str, *, positive: bool) -> dict[str, Any] | None:
    grouped: defaultdict[str, list[float]] = defaultdict(list)
    for entry in entries:
        value = str(entry.get(key) or "").strip()
        pnl = entry.get("result_dollars")
        if value and pnl is not None:
            grouped[value].append(float(pnl))
    if not grouped:
        return None
    items = [
        {
            "value": value,
            "trade_count": len(pnls),
            "average_pnl": round(sum(pnls) / len(pnls), 2),
            "total_pnl": round(sum(pnls), 2),
        }
        for value, pnls in grouped.items()
    ]
    return max(items, key=lambda item: item["average_pnl"]) if positive else min(items, key=lambda item: item["average_pnl"])


def _correlations(
    entries: list[dict[str, Any]],
    correlation_review: dict[str, Any] | None,
    *,
    limit: int,
    symbol: str | None,
    session: str | None,
    strategy_mode: str | None,
) -> list[dict[str, Any]]:
    if correlation_review is None:
        try:
            correlation_review = trading_correlation.generate_trading_correlation_review(
                limit=limit,
                symbol=symbol,
                session=session,
                strategy_mode=strategy_mode,
                entries=entries,
            )
        except Exception:
            correlation_review = {}
    correlations = correlation_review.get("correlations") if isinstance(correlation_review, dict) else []
    return correlations if isinstance(correlations, list) else []


def _scanner_alignment_observations(correlations: list[dict[str, Any]]) -> list[str]:
    if not correlations:
        return []
    labels = Counter(_alignment_key(item.get("alignment_label")) for item in correlations)
    observations = [
        f"Scanner alignment so far: {labels.get('aligned', 0)} aligned, {labels.get('partially_aligned', 0)} partial, {labels.get('conflicted', 0)} conflicted, {labels.get('insufficient_data', 0)} insufficient."
    ]
    phase_counter = Counter(str(item.get("scanner_narrative_phase") or "").replace("_", " ") for item in correlations if item.get("scanner_narrative_phase"))
    signal_counter = Counter(str(item.get("scanner_signal_level") or "") for item in correlations if item.get("scanner_signal_level"))
    behavior_counter = Counter(str(item.get("scanner_behavior") or "").replace("_", " ") for item in correlations if item.get("scanner_behavior"))
    if phase_counter:
        phase, count = phase_counter.most_common(1)[0]
        observations.append(f"Most common scanner phase in matched trades appears to be {phase} ({count}).")
    if signal_counter:
        signal, count = signal_counter.most_common(1)[0]
        observations.append(f"Most common scanner signal level in matched trades appears to be {signal} ({count}).")
    if behavior_counter:
        behavior, count = behavior_counter.most_common(1)[0]
        observations.append(f"Most common scanner behavior in matched trades appears to be {behavior} ({count}).")
    return observations


def _alignment_key(value: Any) -> str:
    label = str(value or "insufficient_data").casefold().strip().replace(" ", "_").replace("-", "_")
    if label in {"aligned", "strong_alignment", "strongly_aligned"}:
        return "aligned"
    if label in {"partial", "partially_aligned", "partial_alignment"}:
        return "partially_aligned"
    if label in {"conflict", "conflicted", "misaligned"}:
        return "conflicted"
    return "insufficient_data"


def _review_questions(missing_patterns: list[str], correlations: list[dict[str, Any]]) -> list[str]:
    questions = [
        "Which repeated setup should be watched for the next 5-10 trades without changing the model yet?",
        "Are the profitable contexts tied to clean narrative alignment or only to outcome variance?",
    ]
    if missing_patterns:
        questions.append("Which missing journal field would improve the next review the most?")
    if correlations:
        questions.append("When scanner alignment is partial or conflicted, what did the journal narrative say that Helix did not see?")
    return questions


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip()
    return " ".join(text.split())


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(str(item).strip() for item in value)
    return True
