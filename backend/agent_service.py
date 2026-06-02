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


def _summarize_priority_task(task: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": task.get("id"),
        "title": task.get("title"),
        "status": task.get("status"),
        "due_date": task.get("due_date"),
        "priority_score": task.get("priority_score"),
        "priority_factors": task.get("priority_factors") or [],
    }


def _compact_title(record: dict[str, Any] | None, fallback: str) -> str:
    if not record:
        return fallback
    title = record.get("title") or record.get("recommendation")
    return str(title or fallback)


def _recommendation_from_strategic_gap(gap: dict[str, Any]) -> dict[str, Any]:
    recommendation_id = f"strategic-gap-{gap.get('milestone_id')}"
    draft = orbit_service.get_recommendation_task_draft(recommendation_id)
    recommendation_title = f"Create first task supporting {gap.get('title')}"
    if draft:
        recommendation_title = str(draft.get("title") or recommendation_title)

    return {
        "id": recommendation_id,
        "category": "strategic_gap",
        "title": recommendation_title,
        "recommendation": recommendation_title,
        "score": gap.get("priority_score"),
        "milestone_id": gap.get("milestone_id"),
        "milestone_title": gap.get("title"),
        "priority_score": gap.get("priority_score"),
        "rationale": gap.get("reasons") or [],
        "reasons": gap.get("reasons") or [],
        "task_draft": draft,
        "requires_user_approval": True,
    }


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
    recommendations_output = orbit_service.generate_recommendations(
        top_priority_tasks=priority_tasks[:5],
        strategic_gaps=strategic_gaps[:5],
        blockers=blockers,
        milestone_progress_history=progress_history,
        readiness=briefing.get("readiness") or {},
    )
    recommendations = recommendations_output.get("recommendations") or []
    highest_priority_task = priority_tasks[0] if priority_tasks else None
    highest_strategic_gap = strategic_gaps[0] if strategic_gaps else None
    recommendations = [
        _recommendation_from_strategic_gap(gap)
        for gap in strategic_gaps[:10]
    ]
    top_recommendation = recommendations[0] if recommendations else None
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
            **_summarize_priority_task(task),
        }
        for task in priority_tasks[:10]
    ]

    highest_task_title = (
        highest_priority_task.get("title")
        if highest_priority_task
        else "No active priority task"
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
    top_recommendation_title = (
        top_recommendation.get("title")
        if top_recommendation
        else "No recommendations"
    )
    top_recommendation_score = (
        f" (P{top_recommendation.get('priority_score')})"
        if top_recommendation
        else ""
    )
    top_3_recommendation_titles = [
        str(recommendation.get("title"))
        + (
            f" (P{recommendation.get('priority_score')})"
            if recommendation.get("priority_score") is not None
            else ""
        )
        for recommendation in recommendations[:3]
    ]
    top_3_recommendations_text = (
        "; ".join(top_3_recommendation_titles)
        if top_3_recommendation_titles
        else "No recommendations"
    )

    recommendation_lines = [
        f"{index}. {_compact_title(recommendation, 'Recommendation unavailable')}"
        for index, recommendation in enumerate(recommendations[:3], start=1)
    ] or ["No recommendations yet."]
    summary = (
        "Highest Priority Task:\n"
        f"{highest_task_title}{highest_task_score}\n\n"
        "Highest Strategic Gap:\n"
        f"{highest_gap_title}{highest_gap_score}\n\n"
        "Top Recommendation:\n"
        f"{top_recommendation_title}{top_recommendation_score}\n\n"
        "Recommendations:\n"
        + "\n".join(recommendation_lines)
    )
    output = {
        "open_task_count": len(open_tasks),
        "highest_priority_task": (
            _summarize_priority_task(highest_priority_task)
            if highest_priority_task
            else None
        ),
        "highest_priority_milestone": highest_priority_milestone,
        "highest_strategic_gap": highest_strategic_gap,
        "strategic_gaps": strategic_gaps[:10],
        "top_recommendation": top_recommendation,
        "top_3_recommendations": recommendations[:3],
        "recommendations": recommendations,
        "task_creation_enabled": False,
        "automatic_task_creation": False,
        "top_open_tasks": top_open_tasks,
        "top_blockers": blockers[:5],
        "blockers": blockers,
        "milestone_progress_history": progress_history,
        "top_recommendations": recommendations[:3],
        "recommendations": recommendations,
        "recommendation_rationale": recommendations_output.get("rationale") or [],
        "suggested_next_action": (
            recommendations[0].get("recommendation")
            if recommendations
            else briefing.get("suggested_next_action")
        ),
        "actions_taken": [],
    }
    return summary, output


def _string_list(values: Any, limit: int = 3) -> list[str]:
    if not isinstance(values, list):
        return []
    return [
        str(value)
        for value in values[:limit]
        if value is not None and str(value).strip()
    ]


def _research_queries_for_target(
    target: str,
    category: str,
    reasons: list[str],
) -> list[str]:
    target_text = target.strip() or "priority milestone"
    base_queries = [
        f"{target_text} current best practices 2026",
        f"{target_text} checklist examples",
        f"{target_text} risks requirements current information",
    ]

    category_queries = {
        "readiness_improvement": [
            f"{target_text} readiness benchmark",
            f"{target_text} preparation checklist current guidance",
        ],
        "strategic_gap": [
            f"{target_text} launch plan current examples",
            f"{target_text} business plan current requirements",
        ],
        "blocker_resolution": [
            f"{target_text} common blockers solutions",
            f"{target_text} current requirements",
        ],
        "task_execution": [
            f"{target_text} implementation guide current best practices",
            f"{target_text} examples checklist",
        ],
    }

    queries = [*category_queries.get(category, []), *base_queries]
    if any("readiness" in reason.casefold() for reason in reasons):
        queries.insert(0, f"{target_text} readiness requirements")
    return list(dict.fromkeys(queries))[:5]


def _sources_required_for_category(category: str) -> list[str]:
    if category == "readiness_improvement":
        return [
            "Current official guidance or requirements",
            "Recent benchmark or checklist source",
            "At least one practical implementation example",
        ]
    if category == "strategic_gap":
        return [
            "Current official or primary source where applicable",
            "Recent expert or industry reference",
            "Comparable launch or planning example",
        ]
    return [
        "Current authoritative source",
        "Recent secondary source for context",
        "Practical checklist or example",
    ]


def _select_web_research_target(
    recommendations: list[dict[str, Any]],
    strategic_gaps: list[dict[str, Any]],
    readiness: dict[str, Any],
) -> dict[str, Any]:
    research_categories = {
        "strategic_gap",
        "readiness_improvement",
        "blocker_resolution",
    }
    for recommendation in recommendations:
        category = str(recommendation.get("category") or "")
        if category in research_categories:
            target = _compact_title(recommendation, "Priority recommendation")
            return {
                "target": target,
                "category": category,
                "reason": (
                    "This recommendation would benefit from current or external "
                    "context before Jadin turns it into execution work."
                ),
                "rationale": _string_list(
                    recommendation.get("rationale") or recommendation.get("reasons"),
                ),
                "source": "recommendation",
            }

    if strategic_gaps:
        gap = strategic_gaps[0]
        target = str(gap.get("title") or "Strategic gap")
        return {
            "target": target,
            "category": "strategic_gap",
            "reason": (
                "This strategic gap is a strong candidate for external research "
                "before selecting the next milestone-linked action."
            ),
            "rationale": _string_list(gap.get("reasons")),
            "source": "strategic_gap",
            "milestone_id": gap.get("milestone_id"),
        }

    readiness_categories = readiness.get("categories") or []
    low_readiness = sorted(
        [
            category
            for category in readiness_categories
            if int(category.get("current_score") or 0)
            < int(category.get("target_score") or 100)
        ],
        key=lambda category: int(category.get("current_score") or 0),
    )
    if low_readiness:
        category = low_readiness[0]
        target = f"{category.get('category_name') or 'Readiness'} readiness"
        return {
            "target": target,
            "category": "readiness_improvement",
            "reason": (
                "This readiness category is below target and may need current "
                "requirements, benchmarks, or examples."
            ),
            "rationale": _string_list([category.get("notes")]),
            "source": "readiness",
            "readiness_category_id": category.get("id"),
        }

    return {
        "target": "Current external context for Orbit priorities",
        "category": "general_research",
        "reason": (
            "No urgent research-dependent gap was detected, so the agent prepared "
            "a general research plan for future priority work."
        ),
        "rationale": [],
        "source": "fallback",
    }


def _summarize_web_search_agent() -> tuple[str, dict[str, Any]]:
    briefing = orbit_service.generate_morning_briefing()
    strategic_gaps = orbit_service.list_strategic_gaps()
    recommendations_output = orbit_service.generate_recommendations(
        strategic_gaps=strategic_gaps[:5],
        blockers=briefing.get("current_blockers") or [],
        readiness=briefing.get("readiness") or {},
    )
    recommendations = (
        recommendations_output.get("recommendations")
        or briefing.get("recommendations")
        or []
    )
    target = _select_web_research_target(
        recommendations[:5],
        strategic_gaps[:5],
        briefing.get("readiness") or {},
    )
    research_target = str(target.get("target"))
    category = str(target.get("category") or "")
    reason = str(target.get("reason") or "Research could help clarify next steps.")
    rationale = _string_list(target.get("rationale"))
    suggested_queries = _research_queries_for_target(
        research_target,
        category,
        rationale,
    )
    sources_required = _sources_required_for_category(category)

    summary = (
        "Research Target:\n"
        f"{research_target}\n\n"
        "Suggested Queries:\n"
        + "\n".join(f"- {query}" for query in suggested_queries[:3])
        + "\n\nWeb search performed: No"
    )
    output = {
        "research_target": research_target,
        "reason": reason,
        "suggested_queries": suggested_queries,
        "sources_required": sources_required,
        "actions_taken": [],
        "web_search_performed": False,
        "research_target_source": target.get("source"),
        "research_category": category,
        "rationale": rationale,
        "top_recommendations_reviewed": recommendations[:5],
        "strategic_gaps_reviewed": strategic_gaps[:5],
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

    if agent_type == "web_search":
        return _summarize_web_search_agent()

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
