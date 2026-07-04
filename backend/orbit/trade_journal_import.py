from __future__ import annotations

from datetime import date, datetime
import importlib.util
import re
import shutil
import tempfile
from pathlib import Path
import subprocess
import zlib
from typing import Any

from .models import (
    TradeJournalCreate,
    TradeJournalDailySummary,
    TradeJournalCalendarImportSaveResponse,
    TradeJournalImportDraft,
    TradeJournalImportPreview,
    TradeJournalImportSaveRequest,
    TradeJournalImportSaveResponse,
    TradeJournalOrderImport,
)
from .service import create_trade_journal_entry, list_trade_journal_entries


MONEY_RE = r"[-+]?(?:\$?\(?|\(\$?)-?\d[\d,]*(?:\.\d+)?\)?"
PRICE_RE = r"\d[\d,]*(?:\.\d+)?"
TIME_RE = r"\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?"
DATE_RE = r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|\d{4}-\d{2}-\d{2}"
DATETIME_RE = rf"(?:{DATE_RE})\s+{TIME_RE}"


def preview_trade_journal_pdf_import(
    performance_pdf: tuple[str, bytes] | None = None,
    orders_pdf: tuple[str, bytes] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    source_files = {
        "performance_pdf": performance_pdf[0] if performance_pdf else None,
        "orders_pdf": orders_pdf[0] if orders_pdf else None,
    }

    performance_text = ""
    orders_text = ""

    if performance_pdf is None and orders_pdf is None:
        warnings.append("No Performance PDF or Orders PDF was provided.")

    if performance_pdf is not None:
        performance_text, performance_warnings = _extract_pdf_text(
            performance_pdf[1],
            performance_pdf[0],
        )
        warnings.extend(performance_warnings)

    if orders_pdf is not None:
        orders_text, orders_warnings = _extract_pdf_text(orders_pdf[1], orders_pdf[0])
        warnings.extend(orders_warnings)

    daily_summary = _parse_daily_summary(performance_text, warnings)
    performance_trades = _parse_performance_trades(performance_text, warnings)
    orders = _parse_orders(orders_text, warnings)

    trade_drafts, matched_order_ids = _enrich_trade_drafts(performance_trades, orders, warnings)
    unmatched_orders = [
        order
        for order in orders
        if order.order_id is None or order.order_id not in matched_order_ids
    ]

    if performance_pdf is not None and not performance_text.strip():
        warnings.append("Performance PDF text could not be extracted.")
    if orders_pdf is not None and not orders_text.strip():
        warnings.append("Orders PDF text could not be extracted.")
    if performance_pdf is not None and not performance_trades:
        if any(value is not None for value in daily_summary.model_dump().values()):
            warnings.append("Performance PDF parsed daily summary but no trade rows were found.")
        else:
            warnings.append("Performance PDF text was extracted but no trade rows were found.")
    if orders_pdf is not None and not orders:
        warnings.append("No order-level records were detected.")
    if orders_pdf is not None and orders and not performance_pdf:
        warnings.append(
            f"Orders PDF parsed {len(orders)} orders. Add a Performance PDF to create matched trade drafts."
        )

    return TradeJournalImportPreview(
        daily_summary=daily_summary,
        trade_drafts=trade_drafts,
        unmatched_orders=unmatched_orders,
        warnings=_unique(warnings),
        source_files=source_files,
    ).model_dump()


def save_trade_journal_import(
    payload: TradeJournalImportSaveRequest,
) -> dict[str, Any]:
    created_entries: list[dict[str, Any]] = []
    warnings: list[str] = []

    for draft in payload.trade_drafts:
        if not draft.selected:
            continue
        if not draft.symbol:
            warnings.append(f"Draft {draft.draft_id} skipped because symbol is missing.")
            continue

        entry = create_trade_journal_entry(
            TradeJournalCreate(
                trade_date=draft.trade_date or date.today(),
                symbol=draft.symbol,
                direction=draft.direction,
                entry_price=draft.entry_price,
                exit_price=draft.exit_price,
                result_dollars=draft.pnl,
                contracts=draft.contracts or draft.quantity,
                session=draft.session,
                htf_bias=draft.htf_bias,
                draw_on_liquidity=draft.draw_on_liquidity,
                reaction_zone=draft.reaction_zone,
                behavior_tags=draft.behavior_tags,
                execution_tags=draft.execution_tags,
                why_taken=draft.why_taken,
                price_intent=draft.price_intent,
                liquidity_target=draft.liquidity_target,
                went_well=draft.went_well,
                went_wrong=draft.went_wrong,
                lesson_learned=draft.lesson_learned,
                screenshot_path=draft.screenshot_path,
                csv_path=draft.csv_path,
            )
        )
        created_entries.append(entry)

    if not created_entries:
        warnings.append("No selected import drafts were saved.")

    return TradeJournalImportSaveResponse(
        created_entries=created_entries,
        warnings=warnings,
    ).model_dump()


def save_trade_journal_calendar_import(
    payload: TradeJournalImportSaveRequest,
) -> dict[str, Any]:
    created_entries: list[dict[str, Any]] = []
    warnings: list[str] = []
    skipped_duplicates = 0
    existing_keys = {
        str(entry.get("source_import_key"))
        for entry in list_trade_journal_entries(include_calendar_only=True)
        if entry.get("source_import_key")
    }

    for draft in payload.trade_drafts:
        if not draft.selected:
            continue
        if not draft.symbol:
            warnings.append(f"Draft {draft.draft_id} skipped because symbol is missing.")
            continue
        if draft.pnl is None:
            warnings.append(f"Draft {draft.draft_id} skipped because PnL is missing.")
            continue

        source_key = _calendar_import_key(draft, payload.source_files)
        if source_key in existing_keys:
            skipped_duplicates += 1
            continue

        entry = create_trade_journal_entry(
            TradeJournalCreate(
                trade_date=draft.trade_date or date.today(),
                symbol=draft.symbol,
                direction=draft.direction,
                entry_price=draft.entry_price,
                exit_price=draft.exit_price,
                result_dollars=draft.pnl,
                contracts=draft.contracts or draft.quantity,
                session=draft.session,
                strategy_profile="Calendar PnL Only",
                strategy_mode="Hybrid / Review",
                why_taken="Calendar-only performance import.",
                entry_type="calendar_only",
                include_in_journal=False,
                include_in_strategy_review=False,
                include_in_scanner_match=False,
                include_in_patterns=False,
                include_in_performance_calendar=True,
                source_import_key=source_key,
            )
        )
        created_entries.append(entry)
        existing_keys.add(source_key)

    if not created_entries and skipped_duplicates == 0:
        warnings.append("No selected calendar trades were saved.")

    return TradeJournalCalendarImportSaveResponse(
        created_entries=created_entries,
        imported=len(created_entries),
        skipped_duplicates=skipped_duplicates,
        updated=0,
        warnings=warnings,
    ).model_dump()


def _calendar_import_key(
    draft: TradeJournalImportDraft,
    source_files: dict[str, str | None],
) -> str:
    source_fingerprint = "|".join(
        f"{key}:{value or ''}" for key, value in sorted(source_files.items())
    )
    parts = [
        source_fingerprint,
        draft.draft_id,
        str(draft.trade_date or ""),
        draft.symbol.strip().upper(),
        draft.direction,
        str(draft.quantity or ""),
        str(draft.contracts or ""),
        str(draft.entry_price or ""),
        str(draft.exit_price or ""),
        str(draft.pnl or ""),
    ]
    return "calendar-only:" + zlib.crc32("|".join(parts).encode("utf-8")).to_bytes(
        4,
        "big",
    ).hex()


def _extract_pdf_text(pdf_bytes: bytes, filename: str) -> tuple[str, list[str]]:
    warnings: list[str] = []

    for extractor in (_extract_with_pypdf, _extract_with_pypdf2, _extract_with_pdftotext):
        text, error = extractor(pdf_bytes)
        if text.strip():
            return text, warnings
        if error:
            warnings.append(f"{filename}: {error}")

    text = _extract_with_minimal_pdf_reader(pdf_bytes)
    if text.strip():
        return text, warnings

    return "", warnings


def _extract_with_pypdf(pdf_bytes: bytes) -> tuple[str, str | None]:
    if importlib.util.find_spec("pypdf") is None:
        return "", None

    try:
        from io import BytesIO
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(pdf_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages), None
    except Exception as exc:  # pragma: no cover - optional dependency path
        return "", f"pypdf extraction failed: {exc}"


def _extract_with_pypdf2(pdf_bytes: bytes) -> tuple[str, str | None]:
    if importlib.util.find_spec("PyPDF2") is None:
        return "", None

    try:
        from io import BytesIO
        from PyPDF2 import PdfReader

        reader = PdfReader(BytesIO(pdf_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages), None
    except Exception as exc:  # pragma: no cover - optional dependency path
        return "", f"PyPDF2 extraction failed: {exc}"


def _extract_with_pdftotext(pdf_bytes: bytes) -> tuple[str, str | None]:
    if not _command_exists("pdftotext"):
        return "", None

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = Path(tmpdir) / "input.pdf"
            txt_path = Path(tmpdir) / "output.txt"
            pdf_path.write_bytes(pdf_bytes)
            subprocess.run(
                ["pdftotext", "-layout", str(pdf_path), str(txt_path)],
                check=True,
                capture_output=True,
                timeout=10,
            )
            return txt_path.read_text(encoding="utf-8", errors="ignore"), None
    except Exception as exc:  # pragma: no cover - depends on local binary
        return "", f"pdftotext extraction failed: {exc}"


def _command_exists(command: str) -> bool:
    return shutil.which(command) is not None


def _extract_with_minimal_pdf_reader(pdf_bytes: bytes) -> str:
    parts: list[str] = []
    raw = pdf_bytes.decode("latin-1", errors="ignore")

    for match in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", pdf_bytes, re.S):
        header = pdf_bytes[max(0, match.start() - 500) : match.start()]
        stream = match.group(1).strip(b"\r\n")
        if b"FlateDecode" in header:
            try:
                stream = zlib.decompress(stream)
            except zlib.error:
                pass
        decoded = stream.decode("latin-1", errors="ignore")
        parts.append(_extract_pdf_text_operators(decoded))

    if not parts:
        parts.append(_extract_pdf_text_operators(raw))

    text = "\n".join(part for part in parts if part.strip())
    return _clean_text(text)


def _extract_pdf_text_operators(value: str) -> str:
    strings: list[str] = []
    for literal in re.findall(r"\((?:\\.|[^\\)])*\)", value, re.S):
        strings.append(_decode_pdf_literal(literal[1:-1]))

    for hex_value in re.findall(r"<([0-9A-Fa-f\s]+)>\s*Tj", value):
        try:
            strings.append(bytes.fromhex(re.sub(r"\s+", "", hex_value)).decode("utf-16-be"))
        except Exception:
            try:
                strings.append(bytes.fromhex(re.sub(r"\s+", "", hex_value)).decode("latin-1"))
            except Exception:
                pass

    return "\n".join(strings)


def _decode_pdf_literal(value: str) -> str:
    replacements = {
        r"\n": "\n",
        r"\r": "\n",
        r"\t": "\t",
        r"\b": "\b",
        r"\f": "\f",
        r"\(": "(",
        r"\)": ")",
        r"\\": "\\",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return value


def _clean_text(value: str) -> str:
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in value.splitlines()]
    return "\n".join(line for line in lines if line)


def _trades_section(text: str) -> str:
    match = re.search(
        r"\bTRADES\b(?P<section>.*?)(?:\bORDERS\b|\bSUMMARY\b|\bDISCLAIMER\b|$)",
        text,
        re.I | re.S,
    )
    return match.group("section") if match else text


def _normalize_table_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _normalize_datetime_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalize_duration(value: str | None) -> str | None:
    if not value:
        return None
    compact = re.sub(r"\s+", " ", value).strip()
    return compact or None


def _section_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _looks_like_duration_cell(value: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:\d+\s*(?:day|days|hr|hrs|hour|hours|min|mins|minute|minutes|sec|secs|second|seconds)\s*)+",
            value.strip(),
            re.I,
        )
    )


def _join_datetime_cells(values: list[str]) -> str | None:
    if len(values) < 2:
        return None
    if re.fullmatch(DATE_RE, values[0]) and re.fullmatch(TIME_RE, values[1]):
        return f"{values[0]} {values[1]}"
    candidate = " ".join(values[:2])
    if re.fullmatch(DATETIME_RE, candidate):
        return candidate
    return None


def _parse_daily_summary(text: str, warnings: list[str]) -> TradeJournalDailySummary:
    summary = TradeJournalDailySummary(
        gross_pnl=_find_money(text, ["Gross P/L", "Gross PnL", "Gross P&L", "Gross Profit"]),
        total_pnl=_find_money(text, ["Total P/L", "Total PnL", "Total P&L", "Net PnL", "Net P&L"]),
        fees_commissions=_find_money(text, ["Trade Fees & Comm.", "Fees Commissions", "Fees & Commissions", "Commissions"]),
        trade_count=_find_int(text, ["# of Trades", "Trade Count"]),
        contract_count=_find_int(text, ["# of Contracts", "Contract Count"]),
        win_rate=_find_percent(text, ["% Profitable Trades", "Win Rate", "Win %"]),
        expectancy=_find_money(text, ["Expectancy", "Expected Value"]),
        average_trade_time=_find_text_value(text, ["Avg. Trade Time", "Average Trade Time", "Avg Trade Time"]),
        longest_trade_time=_find_text_value(text, ["Longest Trade Time", "Max Trade Time"]),
    )

    if text.strip() and not any(value is not None for value in summary.model_dump().values()):
        warnings.append("Performance daily summary was not recognized.")

    return summary


def _parse_performance_trades(
    text: str,
    warnings: list[str],
) -> list[TradeJournalImportDraft]:
    drafts: list[TradeJournalImportDraft] = []
    line_drafts = _parse_performance_trade_lines_from_cells(text)
    if line_drafts:
        return line_drafts

    table_drafts = _parse_performance_trade_table(text)
    if table_drafts:
        return table_drafts

    blocks = re.split(r"(?=\bTrade\s+\d+\b)", text, flags=re.I)

    for block in blocks:
        if not re.search(r"\bTrade\s+\d+\b", block, re.I):
            continue
        symbol = _find_symbol(block)
        if not symbol:
            continue
        buy_price = _find_money(block, ["Buy Price", "Entry Price", "Buy"])
        sell_price = _find_money(block, ["Sell Price", "Exit Price", "Sell"])
        quantity = _find_int(block, ["Quantity", "Qty", "Contracts"])
        buy_time = _find_text_value(block, ["Buy Time", "Entry Time"])
        sell_time = _find_text_value(block, ["Sell Time", "Exit Time"])
        pnl = _find_money(block, ["PnL", "P&L", "Profit"])
        duration = _find_text_value(block, ["Duration", "Trade Time"])
        trade_date = _find_date(block) or _date_from_text(buy_time) or _date_from_text(sell_time)
        direction = _infer_direction_from_times(buy_time, sell_time)
        entry_price = buy_price if direction == "Long" else sell_price
        exit_price = sell_price if direction == "Long" else buy_price
        entry_time = buy_time if direction == "Long" else sell_time

        drafts.append(
            TradeJournalImportDraft(
                draft_id=f"performance-{len(drafts) + 1}",
                trade_date=trade_date,
                symbol=symbol,
                direction=direction,
                quantity=quantity,
                contracts=quantity,
                entry_price=entry_price,
                entry_time=entry_time,
                exit_price=exit_price,
                exit_time=sell_time if direction == "Long" else buy_time,
                duration=duration,
                pnl=pnl,
                session=_infer_session(entry_time),
            )
        )

    if drafts:
        return drafts

    for line in text.splitlines():
        draft = _parse_performance_trade_line(line, len(drafts) + 1)
        if draft is not None:
            drafts.append(draft)

    return drafts


def _parse_performance_trade_lines_from_cells(text: str) -> list[TradeJournalImportDraft]:
    lines = _section_lines(_trades_section(text))
    drafts: list[TradeJournalImportDraft] = []
    index = 0

    while index < len(lines):
        if not re.fullmatch(r"[A-Z]{1,6}[A-Z]\d", lines[index]):
            index += 1
            continue

        start = index
        try:
            symbol = lines[index].upper()
            quantity = _parse_int(lines[index + 1])
            buy_price = _parse_number(lines[index + 2])
            buy_time = _join_datetime_cells(lines[index + 3 : index + 5])
            cursor = index + 4
            if buy_time is not None:
                cursor = index + 5
            else:
                buy_time = lines[index + 3]

            duration_parts: list[str] = []
            while cursor < len(lines) and _looks_like_duration_cell(lines[cursor]):
                duration_parts.append(lines[cursor])
                cursor += 1

            sell_time = _join_datetime_cells(lines[cursor : cursor + 2])
            if sell_time is not None:
                cursor += 2
            else:
                sell_time = lines[cursor]
                cursor += 1

            sell_price = _parse_number(lines[cursor])
            pnl = _parse_number(lines[cursor + 1])
        except (IndexError, TypeError):
            index = start + 1
            continue

        if quantity is None or buy_price is None or sell_price is None:
            index = start + 1
            continue

        direction = _infer_direction_from_times(buy_time, sell_time)
        entry_price = buy_price if direction == "Long" else sell_price
        exit_price = sell_price if direction == "Long" else buy_price
        entry_time = buy_time if direction == "Long" else sell_time
        exit_time = sell_time if direction == "Long" else buy_time

        drafts.append(
            TradeJournalImportDraft(
                draft_id=f"performance-{len(drafts) + 1}",
                trade_date=_date_from_text(entry_time) or _date_from_text(exit_time),
                symbol=symbol,
                direction=direction,
                quantity=quantity,
                contracts=quantity,
                entry_price=entry_price,
                entry_time=entry_time,
                exit_price=exit_price,
                exit_time=exit_time,
                duration=_normalize_duration(" ".join(duration_parts)),
                pnl=pnl,
                session=_infer_session(entry_time),
            )
        )
        index = cursor + 2

    return drafts


def _parse_performance_trade_table(text: str) -> list[TradeJournalImportDraft]:
    normalized = _normalize_table_text(_trades_section(text))
    pattern = re.compile(
        rf"(?P<symbol>[A-Z]{{1,6}}[A-Z]\d)\s+"
        rf"(?P<qty>-?\d+)\s+"
        rf"(?P<buy>{PRICE_RE})\s+"
        rf"(?P<buy_time>{DATETIME_RE})\s+"
        rf"(?P<duration>(?:\d+\s*(?:day|days|hr|hrs|hour|hours|min|mins|minute|minutes|sec|secs|second|seconds)\s*)+)"
        rf"(?P<sell_time>{DATETIME_RE})\s+"
        rf"(?P<sell>{PRICE_RE})\s+"
        rf"(?P<pnl>{MONEY_RE})",
        re.I,
    )
    drafts: list[TradeJournalImportDraft] = []

    for match in pattern.finditer(normalized):
        buy_time = _normalize_datetime_text(match.group("buy_time"))
        sell_time = _normalize_datetime_text(match.group("sell_time"))
        direction = _infer_direction_from_times(buy_time, sell_time)
        buy_price = _parse_number(match.group("buy"))
        sell_price = _parse_number(match.group("sell"))
        entry_price = buy_price if direction == "Long" else sell_price
        exit_price = sell_price if direction == "Long" else buy_price
        entry_time = buy_time if direction == "Long" else sell_time
        exit_time = sell_time if direction == "Long" else buy_time
        quantity = _parse_int(match.group("qty"))

        drafts.append(
            TradeJournalImportDraft(
                draft_id=f"performance-{len(drafts) + 1}",
                trade_date=_date_from_text(entry_time) or _date_from_text(exit_time),
                symbol=match.group("symbol").upper(),
                direction=direction,
                quantity=quantity,
                contracts=quantity,
                entry_price=entry_price,
                entry_time=entry_time,
                exit_price=exit_price,
                exit_time=exit_time,
                duration=_normalize_duration(match.group("duration")),
                pnl=_parse_number(match.group("pnl")),
                session=_infer_session(entry_time),
            )
        )

    return drafts


def _parse_performance_trade_line(line: str, index: int) -> TradeJournalImportDraft | None:
    pattern = re.compile(
        rf"^(?P<symbol>[A-Z]{{1,6}})\s+"
        rf"(?P<qty>-?\d+)\s+"
        rf"(?P<buy>{MONEY_RE})\s+"
        rf"(?P<buy_time>(?:{DATE_RE}\s+)?{TIME_RE})\s+"
        rf"(?P<sell>{MONEY_RE})\s+"
        rf"(?P<sell_time>(?:{DATE_RE}\s+)?{TIME_RE})\s+"
        rf"(?P<duration>\S+)\s+"
        rf"(?P<pnl>{MONEY_RE})$",
        re.I,
    )
    match = pattern.search(line.strip())
    if match is None:
        return None

    buy_price = _parse_number(match.group("buy"))
    sell_price = _parse_number(match.group("sell"))
    pnl = _parse_number(match.group("pnl"))
    buy_time = match.group("buy_time")
    sell_time = match.group("sell_time")
    quantity = _parse_int(match.group("qty"))
    direction = _infer_direction_from_times(buy_time, sell_time)
    entry_price = buy_price if direction == "Long" else sell_price
    exit_price = sell_price if direction == "Long" else buy_price
    entry_time = buy_time if direction == "Long" else sell_time
    exit_time = sell_time if direction == "Long" else buy_time

    return TradeJournalImportDraft(
        draft_id=f"performance-{index}",
        trade_date=_date_from_text(entry_time) or _date_from_text(exit_time),
        symbol=match.group("symbol").upper(),
        direction=direction,
        quantity=quantity,
        contracts=quantity,
        entry_price=entry_price,
        entry_time=entry_time,
        exit_price=exit_price,
        exit_time=exit_time,
        duration=match.group("duration"),
        pnl=pnl,
        session=_infer_session(entry_time),
    )


def _parse_orders(text: str, warnings: list[str]) -> list[TradeJournalOrderImport]:
    orders: list[TradeJournalOrderImport] = []
    cell_orders = _parse_orders_from_cells(text)
    if cell_orders:
        return cell_orders

    table_orders = _parse_order_table(text)
    if table_orders:
        return table_orders

    blocks = re.split(r"(?=\bOrder\s+\d+\b|\bOrder ID\b)", text, flags=re.I)

    for block in blocks:
        if not re.search(r"\bOrder\s+\d+\b|\bOrder ID\b", block, re.I):
            continue
        order = _parse_order_block(block)
        if order.order_id or order.contract:
            orders.append(order)

    if orders:
        return orders

    for line in text.splitlines():
        order = _parse_order_line(line)
        if order is not None:
            orders.append(order)

    return orders


def _parse_orders_from_cells(text: str) -> list[TradeJournalOrderImport]:
    lines = _section_lines(text)
    orders: list[TradeJournalOrderImport] = []
    index = 0

    while index < len(lines):
        if not re.fullmatch(r"\d{6,}", lines[index]):
            index += 1
            continue

        start = index
        try:
            order_id = lines[index]
            side = lines[index + 1].title()
            quantity = _parse_int(lines[index + 2])
            contract = lines[index + 3].upper()
            order_type = lines[index + 4].title()
        except IndexError:
            break

        if side not in {"Buy", "Sell"} or quantity is None or not re.fullmatch(r"[A-Z]{1,6}[A-Z]\d", contract):
            index = start + 1
            continue

        cursor = index + 5
        limit_price: float | None = None
        stop_price: float | None = None
        if cursor < len(lines) and _parse_number(lines[cursor]) is not None:
            if "stop" in order_type.lower():
                stop_price = _parse_number(lines[cursor])
            elif "limit" in order_type.lower():
                limit_price = _parse_number(lines[cursor])
            cursor += 1

        if cursor >= len(lines):
            break
        status = lines[cursor].title()
        cursor += 1

        text_value = None
        if cursor < len(lines) and not re.fullmatch(r"\d+", lines[cursor]) and not re.fullmatch(DATE_RE, lines[cursor]):
            text_value = lines[cursor]
            cursor += 1

        filled_qty = None
        fill_time = None
        average_fill_price = None
        if cursor < len(lines) and re.fullmatch(r"\d+", lines[cursor]):
            filled_qty = _parse_int(lines[cursor])
            cursor += 1
            fill_time = _join_datetime_cells(lines[cursor : cursor + 2])
            if fill_time is not None:
                cursor += 2
            if cursor < len(lines) and _parse_number(lines[cursor]) is not None:
                average_fill_price = _parse_number(lines[cursor])
                cursor += 1

        timestamp = _join_datetime_cells(lines[cursor : cursor + 2])
        if timestamp is not None:
            cursor += 2

        account = lines[cursor] if cursor < len(lines) else None
        venue = lines[cursor + 1] if cursor + 1 < len(lines) else None
        notional_value = None
        if (
            cursor + 3 < len(lines)
            and lines[cursor + 2] == "USD"
            and not _is_order_start(lines, cursor + 3)
        ):
            notional_value = _parse_number(lines[cursor + 3])
            cursor += 4
        else:
            cursor += 2

        orders.append(
            TradeJournalOrderImport(
                order_id=order_id,
                side=side,
                quantity=quantity,
                contract=contract,
                order_type=order_type,
                limit_price=limit_price,
                stop_price=stop_price,
                status=status,
                filled_qty=filled_qty,
                fill_time=fill_time,
                average_fill_price=average_fill_price,
                timestamp=timestamp,
                account=account,
                venue=venue,
                notional_value=notional_value,
            )
        )
        index = max(cursor, start + 1)

    return orders


def _is_order_start(lines: list[str], index: int) -> bool:
    return (
        index + 4 < len(lines)
        and re.fullmatch(r"\d{6,}", lines[index]) is not None
        and lines[index + 1] in {"Buy", "Sell"}
        and re.fullmatch(r"\d+", lines[index + 2]) is not None
        and re.fullmatch(r"[A-Z]{1,6}[A-Z]\d", lines[index + 3]) is not None
    )


def _parse_order_table(text: str) -> list[TradeJournalOrderImport]:
    normalized = _normalize_table_text(text)
    order_type_re = r"Stop\s+Limit|Stop\s+Market|Market|Limit|MKT|LMT|STP"
    status_re = r"Filled|Cancelled|Canceled|Working|Rejected|Submitted|Accepted"
    pattern = re.compile(
        rf"(?P<id>[A-Z0-9][A-Z0-9._-]{{2,}})\s+"
        rf"(?P<side>Buy|Sell|BUY|SELL)\s+"
        rf"(?P<qty>\d+)\s+"
        rf"(?P<contract>[A-Z]{{1,6}}[A-Z]\d)\s+"
        rf"(?P<type>{order_type_re})\s+"
        rf"(?P<price1>{PRICE_RE}|--|-)?\s*"
        rf"(?P<price2>{PRICE_RE}|--|-)?\s*"
        rf"(?P<status>{status_re})\s+"
        rf"(?P<filled>\d+)\s*"
        rf"(?P<fill_time>{DATETIME_RE})?\s*"
        rf"(?P<avg>{PRICE_RE}|--|-)?\s*"
        rf"(?P<timestamp>{DATETIME_RE})?",
        re.I,
    )
    orders: list[TradeJournalOrderImport] = []

    for match in pattern.finditer(normalized):
        order_type = _normalize_table_text(match.group("type")).title()
        price1 = _parse_number(match.group("price1"))
        price2 = _parse_number(match.group("price2"))
        is_stop = "stop" in order_type.lower()
        is_limit = "limit" in order_type.lower()

        orders.append(
            TradeJournalOrderImport(
                order_id=match.group("id"),
                side=match.group("side").title(),
                quantity=_parse_int(match.group("qty")),
                contract=match.group("contract").upper(),
                order_type=order_type,
                limit_price=price1 if is_limit else None,
                stop_price=price1 if is_stop and price1 is not None else price2 if is_stop else None,
                status=match.group("status").title(),
                filled_qty=_parse_int(match.group("filled")),
                fill_time=_normalize_datetime_text(match.group("fill_time")) if match.group("fill_time") else None,
                average_fill_price=_parse_number(match.group("avg")),
                timestamp=_normalize_datetime_text(match.group("timestamp")) if match.group("timestamp") else None,
            )
        )

    return orders


def _parse_order_block(block: str) -> TradeJournalOrderImport:
    return TradeJournalOrderImport(
        order_id=_find_text_value(block, ["Order ID", "OrderId", "ID"]),
        side=_find_side(block),
        quantity=_find_int(block, ["Quantity", "Qty"]),
        contract=_find_text_value(block, ["Contract", "Symbol"]),
        order_type=_find_text_value(block, ["Order Type", "Type"]),
        limit_price=_find_money(block, ["Limit Price", "Limit"]),
        stop_price=_find_money(block, ["Stop Price", "Stop"]),
        status=_find_text_value(block, ["Status"]),
        filled_qty=_find_int(block, ["Filled Qty", "Filled Quantity", "Filled"]),
        fill_time=_find_text_value(block, ["Fill Time", "Filled Time"]),
        average_fill_price=_find_money(block, ["Average Fill Price", "Avg Fill Price", "Average Price"]),
        timestamp=_find_text_value(block, ["Timestamp", "Time"]),
        account=_find_text_value(block, ["Account"]),
        venue=_find_text_value(block, ["Venue"]),
        notional_value=_find_money(block, ["Notional Value", "Notional"]),
    )


def _parse_order_line(line: str) -> TradeJournalOrderImport | None:
    pattern = re.compile(
        rf"^(?P<id>\S+)\s+"
        rf"(?P<side>BUY|SELL|Buy|Sell)\s+"
        rf"(?P<qty>\d+)\s+"
        rf"(?P<contract>[A-Z]{{1,6}}[A-Z0-9]*)\s+"
        rf"(?P<type>Stop Market|Stop Limit|Market|Limit|Stop|MKT|LMT|STP)\s+"
        rf"(?P<status>\w+)\s+"
        rf"(?P<filled>\d+)\s+"
        rf"(?P<price>{MONEY_RE})\s+"
        rf"(?P<time>(?:{DATE_RE}\s+)?{TIME_RE})",
        re.I,
    )
    match = pattern.search(line.strip())
    if match is None:
        return None

    return TradeJournalOrderImport(
        order_id=match.group("id"),
        side=match.group("side").title(),
        quantity=_parse_int(match.group("qty")),
        contract=match.group("contract").upper(),
        order_type=match.group("type"),
        status=match.group("status"),
        filled_qty=_parse_int(match.group("filled")),
        fill_time=match.group("time"),
        average_fill_price=_parse_number(match.group("price")),
        timestamp=match.group("time"),
    )


def _draft_trades_from_orders(
    orders: list[TradeJournalOrderImport],
    warnings: list[str],
) -> list[TradeJournalImportDraft]:
    filled = [
        order
        for order in orders
        if (order.filled_qty or 0) > 0
        and (order.average_fill_price is not None or order.limit_price is not None)
        and order.side in {"Buy", "Sell"}
    ]
    filled.sort(key=lambda order: order.fill_time or order.timestamp or "")

    drafts: list[TradeJournalImportDraft] = []
    used_ids: set[str] = set()
    for index, entry in enumerate(filled):
        if entry.order_id in used_ids:
            continue
        exit_order = next(
            (
                order
                for order in filled[index + 1 :]
                if order.order_id not in used_ids
                and _symbol_key(order.contract) == _symbol_key(entry.contract)
                and not _same_side(order.side, entry.side)
            ),
            None,
        )
        if exit_order is None:
            continue

        if entry.order_id:
            used_ids.add(entry.order_id)
        if exit_order.order_id:
            used_ids.add(exit_order.order_id)

        entry_price = entry.average_fill_price or entry.limit_price
        exit_price = exit_order.average_fill_price or exit_order.limit_price
        direction = "Long" if entry.side == "Buy" else "Short"
        pnl = _estimate_pnl(direction, entry_price, exit_price, entry.filled_qty or entry.quantity)

        drafts.append(
            TradeJournalImportDraft(
                draft_id=f"orders-{len(drafts) + 1}",
                trade_date=_date_from_text(entry.fill_time) or _date_from_text(entry.timestamp),
                symbol=_contract_symbol(entry.contract),
                direction=direction,
                quantity=entry.filled_qty or entry.quantity,
                contracts=entry.filled_qty or entry.quantity,
                entry_price=entry_price,
                entry_time=entry.fill_time or entry.timestamp,
                exit_price=exit_price,
                exit_time=exit_order.fill_time or exit_order.timestamp,
                pnl=pnl,
                session=_infer_session(entry.fill_time or entry.timestamp),
                related_order_ids=[
                    value
                    for value in [entry.order_id, exit_order.order_id]
                    if value is not None
                ],
            )
        )

    if orders and not drafts:
        warnings.append("Orders PDF was parsed, but filled entry/exit pairs could not be matched confidently.")

    return drafts


def _enrich_trade_drafts(
    drafts: list[TradeJournalImportDraft],
    orders: list[TradeJournalOrderImport],
    warnings: list[str],
) -> tuple[list[TradeJournalImportDraft], set[str]]:
    matched_order_ids: set[str] = set()

    for draft in drafts:
        related = _related_orders_for_draft(draft, orders)
        if not related and orders:
            draft.warnings.append("No related orders matched this trade confidently.")
            continue

        order_ids = [order.order_id for order in related if order.order_id]
        matched_order_ids.update(order_ids)
        draft.related_order_ids = _unique([*draft.related_order_ids, *order_ids])

        stop_orders = [order for order in related if _order_type_contains(order, "stop") or order.stop_price is not None]
        draft.stop_detected = bool(stop_orders)
        draft.stop_canceled = any((order.status or "").lower().startswith("cancel") for order in stop_orders)

        entry_side = "Buy" if draft.direction == "Long" else "Sell"
        exit_side = "Sell" if draft.direction == "Long" else "Buy"
        entry_orders = [order for order in related if order.side == entry_side and (order.filled_qty or 0) > 0]
        exit_orders = [order for order in related if order.side == exit_side and (order.filled_qty or 0) > 0]
        draft.market_entry = any(_order_type_contains(order, "market") or _order_type_contains(order, "mkt") for order in entry_orders)
        draft.market_exit = any(_order_type_contains(order, "market") or _order_type_contains(order, "mkt") for order in exit_orders)
        draft.limit_entry = any(_order_type_contains(order, "limit") or _order_type_contains(order, "lmt") for order in entry_orders)
        draft.limit_exit = any(_order_type_contains(order, "limit") or _order_type_contains(order, "lmt") for order in exit_orders)

        if len(related) > 6:
            draft.warnings.append("Many related orders matched this trade; review order IDs before saving.")

    if drafts and orders and not matched_order_ids:
        warnings.append("Orders were parsed, but no order IDs could be attached to trade drafts confidently.")

    return drafts, matched_order_ids


def _related_orders_for_draft(
    draft: TradeJournalImportDraft,
    orders: list[TradeJournalOrderImport],
) -> list[TradeJournalOrderImport]:
    symbol = _symbol_key(draft.symbol)
    candidates = [
        order
        for order in orders
        if order.contract and _symbol_key(order.contract) == symbol
    ]
    if not candidates:
        return []

    entry_side = "Buy" if draft.direction == "Long" else "Sell"
    exit_side = "Sell" if draft.direction == "Long" else "Buy"
    entry_dt = _datetime_from_text(draft.entry_time)
    exit_dt = _datetime_from_text(draft.exit_time)
    related: list[TradeJournalOrderImport] = []

    entry_order = _best_filled_order_match(
        candidates,
        side=entry_side,
        quantity=draft.quantity or draft.contracts,
        price=draft.entry_price,
        target_time=entry_dt,
    )
    exit_order = _best_filled_order_match(
        candidates,
        side=exit_side,
        quantity=draft.quantity or draft.contracts,
        price=draft.exit_price,
        target_time=exit_dt,
        exclude_id=entry_order.order_id if entry_order else None,
    )

    if entry_order is not None:
        related.append(entry_order)
    if exit_order is not None:
        related.append(exit_order)

    stop_orders = [
        order
        for order in candidates
        if _is_stop_order(order)
        and _same_side(order.side, exit_side)
        and _quantity_matches(order.quantity or order.filled_qty, draft.quantity or draft.contracts)
        and _order_between(order, entry_dt, exit_dt)
    ]
    related.extend(stop_orders)

    return _dedupe_orders(related)


def _find_money(text: str, labels: list[str]) -> float | None:
    for label in labels:
        value = _find_labeled_raw(text, label, MONEY_RE)
        if value is not None:
            return _parse_number(value)
    return None


def _find_int(text: str, labels: list[str]) -> int | None:
    for label in labels:
        value = _find_labeled_raw(text, label, r"-?\d[\d,]*")
        if value is not None:
            return _parse_int(value)
    return None


def _find_percent(text: str, labels: list[str]) -> float | None:
    for label in labels:
        value = _find_labeled_raw(text, label, r"-?\d+(?:\.\d+)?%?")
        if value is not None:
            return _parse_number(value)
    return None


def _find_text_value(text: str, labels: list[str]) -> str | None:
    for label in labels:
        escaped = re.escape(label)
        match = re.search(
            rf"{escaped}\s*[:\-]?\s*([^\n\r]+?)(?=\s+(?:[A-Z][A-Za-z /%&]+)\s*[:\-]|\n|$)",
            text,
            re.I,
        )
        if match:
            value = match.group(1).strip(" :,-")
            return value or None
    return None


def _find_labeled_raw(text: str, label: str, value_pattern: str) -> str | None:
    match = re.search(rf"{re.escape(label)}\s*[:\-]?\s*({value_pattern})", text, re.I)
    return match.group(1) if match else None


def _find_symbol(text: str) -> str | None:
    value = _find_text_value(text, ["Symbol", "Contract"])
    if value:
        return _contract_symbol(value)
    match = re.search(r"\b(MES[A-Z]\d|MNQ[A-Z]\d|NQ[A-Z]\d|ES[A-Z]\d|MES|MNQ|NQ|ES|YM|RTY|CL|GC)\b", text, re.I)
    return match.group(1).upper() if match else None


def _find_side(text: str) -> str | None:
    value = _find_text_value(text, ["Buy/Sell", "Side", "Action"])
    if not value:
        match = re.search(r"\b(BUY|SELL|Buy|Sell)\b", text)
        value = match.group(1) if match else None
    if not value:
        return None
    return "Buy" if value.lower().startswith("buy") else "Sell" if value.lower().startswith("sell") else value


def _find_date(text: str) -> date | None:
    match = re.search(DATE_RE, text)
    return _date_from_text(match.group(0)) if match else None


def _date_from_text(value: str | None) -> date | None:
    if not value:
        return None

    match = re.search(DATE_RE, value)
    if not match:
        return None

    raw = match.group(0)
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%m-%d-%Y", "%m-%d-%y"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            pass
    return None


def _datetime_from_text(value: str | None) -> datetime | None:
    if not value:
        return None

    match = re.search(DATETIME_RE, value)
    if not match:
        return None

    raw = _normalize_datetime_text(match.group(0))
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%y %H:%M:%S",
        "%m/%d/%y %H:%M",
        "%m/%d/%Y %I:%M:%S %p",
        "%m/%d/%Y %I:%M %p",
        "%m/%d/%y %I:%M:%S %p",
        "%m/%d/%y %I:%M %p",
    ):
        try:
            return datetime.strptime(raw.upper(), fmt)
        except ValueError:
            pass
    return None


def _parse_number(value: str | None) -> float | None:
    if value is None:
        return None
    cleaned = value.strip().replace("$", "").replace(",", "").replace("%", "")
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    cleaned = cleaned.strip("()")
    try:
        number = float(cleaned)
    except ValueError:
        return None
    return -number if negative else number


def _parse_int(value: str | None) -> int | None:
    number = _parse_number(value)
    return int(number) if number is not None else None


def _infer_direction_from_times(
    buy_time: str | None,
    sell_time: str | None,
) -> str:
    buy_dt = _datetime_from_text(buy_time)
    sell_dt = _datetime_from_text(sell_time)
    if buy_dt is not None and sell_dt is not None and sell_dt < buy_dt:
        return "Short"
    return "Long"


def _infer_session(value: str | None) -> str | None:
    if not value:
        return None

    match = re.search(TIME_RE, value)
    if not match:
        return None

    raw = match.group(0).strip()
    for fmt in ("%H:%M:%S", "%H:%M", "%I:%M:%S %p", "%I:%M %p"):
        try:
            hour = datetime.strptime(raw.upper(), fmt).hour
            if 18 <= hour or hour < 2:
                return "Asia"
            if 2 <= hour < 7:
                return "London"
            if 7 <= hour < 14:
                return "New York"
            return "After Hours"
        except ValueError:
            pass
    return None


def _contract_symbol(contract: str | None) -> str:
    if not contract:
        return ""
    match = re.search(r"\b([A-Z]{1,6}[A-Z]?\d?)\b", contract.upper())
    return match.group(1) if match else contract.upper().strip()


def _symbol_key(contract: str | None) -> str:
    value = _contract_symbol(contract)
    month_code_pattern = r"^(MES|MNQ|NQ|ES|YM|RTY|CL|GC)[FGHJKMNQUVXZ]\d+$"
    match = re.match(month_code_pattern, value)
    if match:
        return match.group(1)
    return value


def _order_type_contains(order: TradeJournalOrderImport, value: str) -> bool:
    return value.lower() in (order.order_type or "").lower()


def _is_stop_order(order: TradeJournalOrderImport) -> bool:
    return _order_type_contains(order, "stop") or order.stop_price is not None


def _is_filled_order(order: TradeJournalOrderImport) -> bool:
    if (order.filled_qty or 0) > 0:
        return True
    return "fill" in (order.status or "").lower() and not _is_canceled_order(order)


def _is_canceled_order(order: TradeJournalOrderImport) -> bool:
    return (order.status or "").lower().startswith(("cancel", "reject"))


def _same_side(left: str | None, right: str | None) -> bool:
    if not left or not right:
        return False
    return left.lower().startswith(right.lower()) or right.lower().startswith(left.lower())


def _quantity_matches(order_quantity: int | None, trade_quantity: int | None) -> bool:
    return order_quantity is None or trade_quantity is None or abs(order_quantity) == abs(trade_quantity)


def _price_matches(order_price: float | None, trade_price: float | None, tolerance: float = 0.01) -> bool:
    if order_price is None or trade_price is None:
        return True
    return abs(order_price - trade_price) <= tolerance


def _seconds_apart(left: datetime | None, right: datetime | None) -> float | None:
    if left is None or right is None:
        return None
    return abs((left - right).total_seconds())


def _best_filled_order_match(
    orders: list[TradeJournalOrderImport],
    *,
    side: str,
    quantity: int | None,
    price: float | None,
    target_time: datetime | None,
    exclude_id: str | None = None,
) -> TradeJournalOrderImport | None:
    scored: list[tuple[float, TradeJournalOrderImport]] = []

    for order in orders:
        if exclude_id is not None and order.order_id == exclude_id:
            continue
        if not _same_side(order.side, side) or not _is_filled_order(order):
            continue
        if not _quantity_matches(order.filled_qty or order.quantity, quantity):
            continue

        order_price = order.average_fill_price or order.limit_price
        if not _price_matches(order_price, price, tolerance=0.25):
            continue

        order_time = _datetime_from_text(order.fill_time) or _datetime_from_text(order.timestamp)
        seconds = _seconds_apart(order_time, target_time)
        if seconds is not None and seconds > 180:
            continue

        score = 0.0
        if order_price is not None and price is not None:
            score += abs(order_price - price)
        if seconds is not None:
            score += seconds / 1000
        scored.append((score, order))

    if not scored:
        return None

    scored.sort(key=lambda item: item[0])
    return scored[0][1]


def _order_between(
    order: TradeJournalOrderImport,
    entry_dt: datetime | None,
    exit_dt: datetime | None,
) -> bool:
    if entry_dt is None or exit_dt is None:
        return True

    order_dt = _datetime_from_text(order.timestamp) or _datetime_from_text(order.fill_time)
    if order_dt is None:
        return True

    start = min(entry_dt, exit_dt)
    end = max(entry_dt, exit_dt)
    return start <= order_dt <= end


def _dedupe_orders(orders: list[TradeJournalOrderImport]) -> list[TradeJournalOrderImport]:
    seen: set[str] = set()
    unique_orders: list[TradeJournalOrderImport] = []
    for order in orders:
        key = order.order_id or f"{order.side}-{order.contract}-{order.timestamp}-{order.average_fill_price}"
        if key in seen:
            continue
        seen.add(key)
        unique_orders.append(order)
    return unique_orders


def _estimate_pnl(
    direction: str,
    entry_price: float | None,
    exit_price: float | None,
    quantity: int | None,
) -> float | None:
    if entry_price is None or exit_price is None:
        return None
    multiplier = quantity or 1
    if direction == "Short":
        return round((entry_price - exit_price) * multiplier, 2)
    return round((exit_price - entry_price) * multiplier, 2)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            unique_values.append(value)
    return unique_values
