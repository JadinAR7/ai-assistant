from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from orbit.database import get_connection, init_orbit_db
from orbit import service as orbit_service


class AgentNotFoundError(ValueError):
    pass


class AgentDisabledError(ValueError):
    pass


def _row_to_dict(row: Any | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def _decode_output_json(record: dict[str, Any]) -> dict[str, Any]:
    output_json = record.get("output_json")
    if isinstance(output_json, str) and output_json:
        try:
            record["output_json"] = json.loads(output_json)
        except json.JSONDecodeError:
            record["output_json"] = {"raw": output_json}
    elif output_json is None:
        record["output_json"] = None
    return record


def _get_latest_run_for_agent(agent_id: int) -> dict[str, Any] | None:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT agent_runs.*, agent_definitions.name AS agent_name
        FROM agent_runs
        JOIN agent_definitions ON agent_definitions.id = agent_runs.agent_id
        WHERE agent_runs.agent_id = ?
        ORDER BY agent_runs.started_at DESC, agent_runs.id DESC
        LIMIT 1
        """,
        (agent_id,),
    )
    row = cursor.fetchone()
    conn.close()

    record = _row_to_dict(row)
    return _decode_output_json(record) if record else None


def _with_last_run(agent: dict[str, Any]) -> dict[str, Any]:
    return {
        **agent,
        "enabled": bool(agent.get("enabled")),
        "last_run": _get_latest_run_for_agent(int(agent["id"])),
    }


def list_agents() -> list[dict[str, Any]]:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agent_definitions ORDER BY id")
    rows = cursor.fetchall()
    conn.close()

    return [_with_last_run(dict(row)) for row in rows]


def get_agent(agent_id: int) -> dict[str, Any] | None:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM agent_definitions WHERE id = ?", (agent_id,))
    row = cursor.fetchone()
    conn.close()

    agent = _row_to_dict(row)
    if agent is None:
        return None

    return _with_last_run(agent)


def list_recent_agent_runs(limit: int = 20) -> list[dict[str, Any]]:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT agent_runs.*, agent_definitions.name AS agent_name
        FROM agent_runs
        JOIN agent_definitions ON agent_definitions.id = agent_runs.agent_id
        ORDER BY agent_runs.started_at DESC, agent_runs.id DESC
        LIMIT ?
        """,
        (limit,),
    )
    rows = cursor.fetchall()
    conn.close()

    return [_decode_output_json(dict(row)) for row in rows]


def _create_agent_run(agent_id: int) -> int:
    init_orbit_db()

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO agent_runs (agent_id, status, started_at)
        VALUES (?, 'running', ?)
        """,
        (agent_id, datetime.now(timezone.utc).isoformat()),
    )
    run_id = int(cursor.lastrowid)
    conn.commit()
    conn.close()

    return run_id


def _complete_agent_run(
    run_id: int,
    status: str,
    summary: str | None = None,
    output: dict[str, Any] | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE agent_runs
        SET
            status = ?,
            completed_at = ?,
            summary = ?,
            output_json = ?,
            error = ?
        WHERE id = ?
        """,
        (
            status,
            datetime.now(timezone.utc).isoformat(),
            summary,
            json.dumps(output) if output is not None else None,
            error,
            run_id,
        ),
    )
    conn.commit()
    cursor.execute(
        """
        SELECT agent_runs.*, agent_definitions.name AS agent_name
        FROM agent_runs
        JOIN agent_definitions ON agent_definitions.id = agent_runs.agent_id
        WHERE agent_runs.id = ?
        """,
        (run_id,),
    )
    row = cursor.fetchone()
    conn.close()

    record = _row_to_dict(row)
    if record is None:
        raise RuntimeError(f"Unable to load agent run {run_id}.")

    return _decode_output_json(record)


def _summarize_executive_assistant() -> tuple[str, dict[str, Any]]:
    briefing = orbit_service.generate_morning_briefing()
    open_tasks = [
        orbit_service._with_linked_milestones(task)
        for task in orbit_service.list_records("tasks")
        if orbit_service._is_open(task)
    ]
    priority_tasks = sorted(open_tasks, key=orbit_service._priority_sort_key)
    progress_history = orbit_service.list_recent_milestone_progress_history(limit=10)
    blockers = briefing.get("current_blockers") or []
    strategic_gaps = orbit_service.list_strategic_gaps()
    highest_priority_task = priority_tasks[0] if priority_tasks else None
    highest_strategic_gap = strategic_gaps[0] if strategic_gaps else None
    highest_priority_milestone = None
    if highest_priority_task:
        linked_milestones = highest_priority_task.get("milestones") or []
        if linked_milestones:
            highest_priority_milestone = linked_milestones[0]
    if highest_priority_milestone is None:
        priority_milestones = briefing.get("priority_milestones") or []
        highest_priority_milestone = priority_milestones[0] if priority_milestones else None
    top_open_tasks = [
        {
            "id": task.get("id"),
            "title": task.get("title"),
            "status": task.get("status"),
            "due_date": task.get("due_date"),
            "priority_score": task.get("priority_score"),
            "priority_factors": task.get("priority_factors") or [],
        }
        for task in priority_tasks[:10]
    ]

    highest_task_title = (
        highest_priority_task.get("title") if highest_priority_task else "none"
    )
    highest_task_score = (
        f" (P{highest_priority_task.get('priority_score')})"
        if highest_priority_task
        else ""
    )
    highest_milestone_title = (
        highest_priority_milestone.get("title")
        if highest_priority_milestone
        else "none"
    )
    highest_gap_title = (
        highest_strategic_gap.get("title") if highest_strategic_gap else "none"
    )
    highest_gap_score = (
        f" (P{highest_strategic_gap.get('priority_score')})"
        if highest_strategic_gap
        else ""
    )

    summary = (
        f"Highest priority task: "
        f"{highest_task_title}{highest_task_score}. "
        f"Highest strategic gap: {highest_gap_title}{highest_gap_score}. "
        f"Highest priority milestone: {highest_milestone_title}. "
        f"Top blockers: {blockers[0] if blockers else 'none'}. "
        f"{len(open_tasks)} open task(s) and {len(progress_history)} recent milestone progress event(s) reviewed. "
        f"Next action: {briefing.get('suggested_next_action')}"
    )
    output = {
        "open_task_count": len(open_tasks),
        "highest_priority_task": (
            {
                "id": highest_priority_task.get("id"),
                "title": highest_priority_task.get("title"),
                "status": highest_priority_task.get("status"),
                "due_date": highest_priority_task.get("due_date"),
                "priority_score": highest_priority_task.get("priority_score"),
                "priority_factors": highest_priority_task.get("priority_factors") or [],
            }
            if highest_priority_task
            else None
        ),
        "highest_priority_milestone": highest_priority_milestone,
        "highest_strategic_gap": highest_strategic_gap,
        "strategic_gaps": strategic_gaps[:10],
        "top_open_tasks": top_open_tasks,
        "top_blockers": blockers[:5],
        "blockers": blockers,
        "milestone_progress_history": progress_history,
        "suggested_next_action": briefing.get("suggested_next_action"),
        "actions_taken": [],
    }
    return summary, output


def _summarize_trading_coach() -> tuple[str, dict[str, Any]]:
    recent_sessions = orbit_service.list_trade_sessions()[:10]
    readiness = orbit_service.get_readiness_categories()
    pnl_total = sum(float(session.get("pnl") or 0) for session in recent_sessions)
    rule_values = [
        int(session["rule_adherence"])
        for session in recent_sessions
        if session.get("rule_adherence") is not None
    ]
    confidence_values = [
        int(session["confidence"])
        for session in recent_sessions
        if session.get("confidence") is not None
    ]
    average_rule_adherence = (
        round(sum(rule_values) / len(rule_values)) if rule_values else None
    )
    average_confidence = (
        round(sum(confidence_values) / len(confidence_values), 1)
        if confidence_values
        else None
    )
    trading_readiness = [
        category
        for category in readiness
        if "trading" in str(category.get("category_name") or "").casefold()
    ]

    summary = (
        f"{len(recent_sessions)} recent trade session(s) reviewed. "
        f"Total PnL: {pnl_total}. "
        f"Average rule adherence: {average_rule_adherence if average_rule_adherence is not None else 'not logged'}."
    )
    output = {
        "recent_session_count": len(recent_sessions),
        "total_pnl": pnl_total,
        "average_rule_adherence": average_rule_adherence,
        "average_confidence": average_confidence,
        "recent_sessions": recent_sessions,
        "trading_readiness": trading_readiness,
        "scanner_changes": False,
        "trading_signals": [],
        "actions_taken": [],
    }
    return summary, output


def _run_agent_body(agent: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    agent_type = agent.get("agent_type")

    if agent_type == "morning_review":
        output = orbit_service.generate_morning_briefing()
        return output.get("briefing_text") or "Morning briefing generated.", output

    if agent_type == "evening_review":
        output = orbit_service.generate_daily_closeout()
        return output.get("closeout_text") or "Daily closeout generated.", output

    if agent_type == "executive_assistant":
        return _summarize_executive_assistant()

    if agent_type == "trading_coach":
        return _summarize_trading_coach()

    raise ValueError(f"Unsupported agent type: {agent_type}")


def run_agent(agent_id: int) -> dict[str, Any]:
    """Run one agent manually.

    Future scheduled/background automation should call this function rather than
    duplicating agent behavior. This v1 intentionally does not schedule itself,
    create tasks, update readiness, send notifications, or change scanner state.
    """
    agent = get_agent(agent_id)
    if agent is None:
        raise AgentNotFoundError(f"Agent {agent_id} not found.")
    if not agent.get("enabled"):
        raise AgentDisabledError(f"Agent {agent_id} is disabled.")

    run_id = _create_agent_run(agent_id)

    try:
        summary, output = _run_agent_body(agent)
    except Exception as exc:
        return _complete_agent_run(
            run_id,
            status="failed",
            error=str(exc),
        )

    return _complete_agent_run(
        run_id,
        status="completed",
        summary=summary,
        output=output,
    )
