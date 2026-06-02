from __future__ import annotations

import json
from datetime import date, datetime, timezone
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


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _hours_since(value: Any, now: datetime) -> float | None:
    parsed = _parse_datetime(value)
    if parsed is None:
        return None
    return max(0.0, (now - parsed).total_seconds() / 3600)


def _days_since_date(value: Any, today: date) -> int | None:
    parsed = _parse_date(value)
    if parsed is None:
        return None
    return max(0, (today - parsed).days)


def _latest_run_started_at(agent: dict[str, Any]) -> Any:
    last_run = agent.get("last_run")
    if isinstance(last_run, dict):
        return last_run.get("started_at")
    return None


def _score_recent_run_penalty(agent: dict[str, Any], now: datetime) -> tuple[int, str | None]:
    hours = _hours_since(_latest_run_started_at(agent), now)
    if hours is None:
        return 0, None
    if hours < 12:
        return -25, "Ran in the last 12 hours."
    if hours < 24:
        return -18, "Ran in the last day."
    if hours < 72:
        return -10, "Ran in the last three days."
    return 0, None


def _contains_external_context_signal(records: list[dict[str, Any]]) -> bool:
    keywords = {
        "business launch",
        "launch plan",
        "capital checkpoint",
        "capital",
        "law",
        "laws",
        "legal",
        "rule",
        "rules",
        "policy",
        "policies",
        "travel",
        "news",
        "current",
        "external",
        "market",
        "requirements",
        "benchmark",
        "research",
        "official",
    }
    return any(_matches_any(_text_for_record(record), list(keywords)) for record in records)


def _clamp_priority(score: int) -> int:
    return max(0, min(100, score))


def _make_rank(
    agent: dict[str, Any],
    score: int,
    reasons: list[str],
) -> dict[str, Any]:
    return {
        "agent_type": str(agent.get("agent_type") or ""),
        "agent_name": str(agent.get("name") or "Agent"),
        "priority_score": _clamp_priority(score),
        "reasons": reasons,
    }


def prioritize_agents() -> dict[str, Any]:
    """Recommend the next manual agent to run without taking any actions."""
    now = datetime.now(timezone.utc)
    today = now.date()
    agents = [agent for agent in list_agents() if agent.get("enabled")]
    agents_by_type = {str(agent.get("agent_type")): agent for agent in agents}

    readiness = orbit_service.get_readiness_categories()
    strategic_gaps = orbit_service.list_strategic_gaps()
    tasks = orbit_service.list_records("tasks")
    open_tasks = [task for task in tasks if orbit_service._is_open(task)]
    priority_tasks = sorted(open_tasks, key=orbit_service._priority_sort_key)
    reviews = sorted(
        orbit_service.list_records("reviews"),
        key=lambda review: str(review.get("created_at") or ""),
        reverse=True,
    )
    recent_review_count = sum(
        1
        for review in reviews
        if (
            _days_since_date(review.get("created_at"), today) is not None
            and (_days_since_date(review.get("created_at"), today) or 0) <= 7
        )
    )
    closeout_review_today = any(
        str(review.get("review_type") or "").casefold() == "daily_closeout"
        and _days_since_date(review.get("created_at"), today) == 0
        for review in reviews
    )
    trade_sessions = orbit_service.list_trade_sessions()
    progress_history = orbit_service.list_recent_milestone_progress_history(limit=20)
    recommendations_output = orbit_service.generate_recommendations(
        top_priority_tasks=priority_tasks[:5],
        strategic_gaps=strategic_gaps[:5],
        blockers=[],
        milestone_progress_history=progress_history,
        readiness={
            "overall": (
                round(
                    sum(int(category.get("current_score") or 0) for category in readiness)
                    / len(readiness)
                )
                if readiness
                else 0
            ),
            "categories": readiness,
        },
    )
    recommendations = recommendations_output.get("recommendations") or []

    ranked_agents: list[dict[str, Any]] = []

    def add_agent_score(agent_type: str, base_score: int, reasons: list[str]) -> None:
        agent = agents_by_type.get(agent_type)
        if agent is None:
            return
        score = base_score
        penalty, penalty_reason = _score_recent_run_penalty(agent, now)
        if penalty_reason:
            score += penalty
            reasons = [*reasons, penalty_reason]
        ranked_agents.append(_make_rank(agent, score, reasons))

    low_readiness = [
        category
        for category in readiness
        if int(category.get("current_score") or 0) < 30
    ]
    stale_readiness = [
        category
        for category in readiness
        if (
            _hours_since(category.get("last_updated"), now) is None
            or (_hours_since(category.get("last_updated"), now) or 0) > 24 * 14
        )
    ]
    readiness_score = 35
    readiness_reasons = ["Readiness evidence can be reviewed without changing scores."]
    if low_readiness:
        readiness_score = 90
        readiness_reasons.insert(
            0,
            f"{len(low_readiness)} readiness categor{'y is' if len(low_readiness) == 1 else 'ies are'} below 30.",
        )
    elif stale_readiness:
        readiness_score = 75
        readiness_reasons.insert(0, "Readiness has not been reviewed recently.")
    add_agent_score("readiness_advisory", readiness_score, readiness_reasons)

    external_context_records = [*strategic_gaps, *recommendations, *priority_tasks[:10]]
    web_score = 30
    web_reasons = ["No urgent external-information need was detected."]
    if _contains_external_context_signal(external_context_records):
        web_score = 82
        web_reasons = [
            "Strategic gaps or recommendations may need current or external information."
        ]
    elif strategic_gaps or recommendations:
        web_score = 60
        web_reasons = ["Open strategic gaps or recommendations may benefit from research."]
    add_agent_score("web_search", web_score, web_reasons)

    blocker_count = sum(
        1
        for task in open_tasks
        if _matches_any(_text_for_record(task), ["blocker", "blocked", "waiting"])
    )
    executive_score = 45
    executive_reasons = ["Open Orbit work can be summarized for manual planning."]
    if priority_tasks or strategic_gaps or blocker_count:
        executive_score = min(
            88,
            62
            + min(len(priority_tasks), 5) * 3
            + min(len(strategic_gaps), 4) * 3
            + blocker_count * 4,
        )
        executive_reasons = [
            f"{len(priority_tasks)} open task(s), {len(strategic_gaps)} strategic gap(s), and {blocker_count} blocker signal(s) need planning attention."
        ]
    if recent_review_count == 0:
        executive_score += 8
        executive_reasons.append("No recent reviews are available for planning context.")
    add_agent_score("executive_assistant", executive_score, executive_reasons)

    morning_agent = agents_by_type.get("morning_review")
    morning_ran_today = (
        morning_agent is not None
        and _days_since_date(_latest_run_started_at(morning_agent), today) == 0
    )
    morning_score = 35
    morning_reasons = ["Morning briefing is useful but not time-critical right now."]
    if 5 <= now.astimezone().hour < 12 and not morning_ran_today:
        morning_score = 82
        morning_reasons = ["It is morning and no morning review agent run is logged today."]
    elif not morning_ran_today:
        morning_score = 55
        morning_reasons = ["No morning review agent run is logged today."]
    add_agent_score("morning_review", morning_score, morning_reasons)

    evening_agent = agents_by_type.get("evening_review")
    evening_ran_today = (
        evening_agent is not None
        and _days_since_date(_latest_run_started_at(evening_agent), today) == 0
    )
    evening_score = 35
    evening_reasons = ["Daily closeout is useful but not time-critical right now."]
    if now.astimezone().hour >= 16 and not evening_ran_today:
        evening_score = 82
        evening_reasons = ["It is late day and no evening review agent run is logged today."]
    elif not evening_ran_today:
        evening_score = 50
        evening_reasons = ["No evening review agent run is logged today."]
    if closeout_review_today:
        evening_score = min(evening_score, 35)
        evening_reasons.append("A daily closeout review is already logged today.")
    add_agent_score("evening_review", evening_score, evening_reasons)

    recent_trade_sessions = [
        session
        for session in trade_sessions[:10]
        if (
            _days_since_date(session.get("session_date"), today) is None
            or (_days_since_date(session.get("session_date"), today) or 0) <= 7
        )
    ]
    trading_score = 30
    trading_reasons = ["No recent trade sessions need coaching review."]
    if recent_trade_sessions:
        trading_score = 78
        trading_reasons = [
            f"{len(recent_trade_sessions)} recent trade session(s) are available for review."
        ]
    add_agent_score("trading_coach", trading_score, trading_reasons)

    ranked_agents.sort(
        key=lambda rank: (-int(rank["priority_score"]), str(rank["agent_name"]))
    )
    recommended = ranked_agents[0] if ranked_agents else {
        "agent_type": "none",
        "agent_name": "No enabled agent",
        "priority_score": 0,
        "reasons": ["No enabled agents are available."],
    }
    reason = (
        recommended["reasons"][0]
        if recommended.get("reasons")
        else "No prioritization reason available."
    )

    return {
        "recommended_agent_type": recommended["agent_type"],
        "recommended_agent_name": recommended["agent_name"],
        "priority_score": recommended["priority_score"],
        "reason": reason,
        "ranked_agents": ranked_agents,
        "actions_taken": [],
    }


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


def _text_for_record(record: dict[str, Any]) -> str:
    return " ".join(
        str(record.get(field) or "")
        for field in (
            "title",
            "description",
            "summary",
            "notes",
            "category_name",
            "recommendation",
            "review_type",
        )
    ).casefold()


def _is_complete(record: dict[str, Any]) -> bool:
    status = str(record.get("status") or "").casefold()
    return status in {"complete", "completed", "done"} or bool(record.get("completed_at"))


def _matches_any(text: str, keywords: list[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def _linked_milestones_for_task(task: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return orbit_service.list_milestones_linked_to_task(int(task.get("id") or 0))
    except (TypeError, ValueError):
        return []


def _readiness_category_keywords(category_name: str) -> list[str]:
    category = category_name.casefold()
    keywords = {
        "financial": [
            "financial",
            "finance",
            "income",
            "replacement",
            "capital",
            "savings",
            "runway",
            "cash",
            "fund",
        ],
        "trading": [
            "trading",
            "trade",
            "journal",
            "review cadence",
            "session",
            "scanner",
            "setup",
        ],
        "business": [
            "business",
            "launch",
            "client",
            "customer",
            "offer",
            "research",
            "market",
            "revenue",
        ],
        "personal": [
            "personal",
            "health",
            "habit",
            "family",
            "life",
            "routine",
        ],
    }
    for key, values in keywords.items():
        if key in category:
            return values
    return [category]


def _score_readiness_evidence(
    category_name: str,
    current_score: int,
    evidence: list[str],
    strong_evidence_types: set[str],
    weak_evidence_count: int,
    trade_session_count: int,
) -> int:
    strong_count = len(strong_evidence_types)
    if strong_count >= 4:
        evidence_score = 60
    elif strong_count >= 3:
        evidence_score = 45
    elif strong_count >= 2:
        evidence_score = 30
    elif strong_count >= 1:
        evidence_score = 20
    elif weak_evidence_count > 0:
        evidence_score = 10
    else:
        evidence_score = current_score

    if (
        "trading" in category_name.casefold()
        and trade_session_count >= 5
        and strong_count >= 2
    ):
        evidence_score = max(evidence_score, 45)

    if evidence_score <= current_score:
        return current_score
    return min(100, ((evidence_score + 4) // 5) * 5)


def _confidence_for_evidence(
    strong_evidence_types: set[str],
    weak_evidence_count: int,
    observations: list[str],
) -> str:
    strong_count = len(strong_evidence_types)
    if strong_count >= 4:
        return "high"
    if strong_count >= 2:
        return "medium"
    if strong_count >= 1 or weak_evidence_count > 0:
        return "low"
    return "low" if observations else "none"


def _max_increase_for_confidence(confidence: str) -> int:
    return {
        "high": 30,
        "medium": 20,
        "low": 10,
    }.get(confidence, 0)


def _collect_readiness_evidence(
    category: dict[str, Any],
    tasks: list[dict[str, Any]],
    milestones: list[dict[str, Any]],
    progress_history: list[dict[str, Any]],
    reviews: list[dict[str, Any]],
    trade_sessions: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
    strategic_gaps: list[dict[str, Any]],
) -> tuple[list[str], list[str], set[str], int]:
    category_name = str(category.get("category_name") or "Readiness")
    keywords = _readiness_category_keywords(category_name)
    evidence: list[str] = []
    observations: list[str] = []
    strong_evidence_types: set[str] = set()
    weak_evidence_count = 0

    def add_evidence(text: str, evidence_type: str = "weak") -> None:
        nonlocal weak_evidence_count
        is_new_evidence = text not in evidence
        if text not in evidence:
            evidence.append(text)
        if evidence_type in {
            "completed_task",
            "milestone_progress",
            "review",
            "trade_session",
        }:
            strong_evidence_types.add(evidence_type)
        elif is_new_evidence:
            weak_evidence_count += 1

    def add_observation(text: str) -> None:
        if text not in observations:
            observations.append(text)

    matching_milestones = [
        milestone
        for milestone in milestones
        if _matches_any(_text_for_record(milestone), keywords)
    ]
    for milestone in matching_milestones[:4]:
        title = str(milestone.get("title") or "Milestone")
        progress = int(milestone.get("progress_percent") or 0)
        status = str(milestone.get("status") or "").casefold()
        if _is_complete(milestone):
            add_evidence(f"{title} milestone completed", "milestone_progress")
        elif progress > 0:
            add_evidence(f"{title} milestone progressing at {progress}%", "milestone_progress")
        elif status in {"active", "in_progress"}:
            add_evidence(f"{title} milestone active")
        else:
            add_observation(f"{title} milestone exists but has no recorded progress")

    matching_tasks = []
    for task in tasks:
        task_text = _text_for_record(task)
        linked_text = " ".join(
            _text_for_record(milestone) for milestone in _linked_milestones_for_task(task)
        )
        if _matches_any(f"{task_text} {linked_text}", keywords):
            matching_tasks.append(task)
    completed_tasks = [task for task in matching_tasks if _is_complete(task)]
    open_tasks = [task for task in matching_tasks if not _is_complete(task)]
    if completed_tasks:
        add_evidence(
            f"{len(completed_tasks)} {category_name} task(s) completed",
            "completed_task",
        )
    if open_tasks:
        add_evidence(f"{len(open_tasks)} {category_name} task(s) queued or in progress")

    matching_history = [
        history
        for history in progress_history
        if _matches_any(str(history.get("milestone_title") or "").casefold(), keywords)
        or any(
            int(milestone.get("id") or 0) == int(history.get("milestone_id") or -1)
            for milestone in matching_milestones
        )
    ]
    positive_history = [
        history
        for history in matching_history
        if int(history.get("change_amount") or 0) > 0
    ]
    if positive_history:
        add_evidence(
            f"{len(positive_history)} recent {category_name} milestone progress update(s)",
            "milestone_progress",
        )

    matching_reviews = [
        review
        for review in reviews
        if _matches_any(_text_for_record(review), keywords)
        or (
            "personal" in category_name.casefold()
            and str(review.get("review_type") or "").casefold()
            in {"daily_closeout", "daily", "weekly"}
        )
    ]
    if matching_reviews:
        add_evidence(
            f"{len(matching_reviews)} {category_name} review(s) completed",
            "review",
        )

    matching_recommendations = [
        recommendation
        for recommendation in recommendations
        if _matches_any(_text_for_record(recommendation), keywords)
    ]
    if matching_recommendations:
        add_evidence(
            f"{len(matching_recommendations)} {category_name} recommendation(s) generated",
            "recommendation",
        )

    matching_gaps = [
        gap for gap in strategic_gaps if _matches_any(_text_for_record(gap), keywords)
    ]
    if matching_gaps:
        add_observation(
            f"{len(matching_gaps)} {category_name} strategic gap(s) still need execution"
        )

    category_key = category_name.casefold()
    if "trading" in category_key:
        if trade_sessions:
            add_evidence(f"{len(trade_sessions)} trade session(s) logged", "trade_session")
        reviewed_sessions = [
            session
            for session in trade_sessions
            if session.get("rule_adherence") is not None
            or session.get("confidence") is not None
            or str(session.get("notes") or "").strip()
        ]
        if reviewed_sessions:
            add_evidence(
                f"{len(reviewed_sessions)} trade session(s) include review data",
                "trade_session",
            )
        losing_sessions = [
            session for session in trade_sessions if float(session.get("pnl") or 0) < 0
        ]
        if losing_sessions:
            add_observation(
                f"{len(losing_sessions)} recent losing trade session(s) noted without reducing readiness"
            )

    if "financial" in category_key:
        complete_financial_milestones = [
            milestone for milestone in matching_milestones if _is_complete(milestone)
        ]
        if complete_financial_milestones:
            add_evidence("Financial milestone completion recorded", "milestone_progress")
        if any(
            _matches_any(_text_for_record(milestone), ["income replacement"])
            and _is_complete(milestone)
            for milestone in matching_milestones
        ):
            add_evidence("Income replacement target completed", "milestone_progress")
        if any(
            _matches_any(_text_for_record(milestone), ["capital", "savings", "runway"])
            for milestone in matching_milestones
        ):
            add_evidence("Capital accumulation milestone exists")

    if "business" in category_key:
        if any(
            _matches_any(_text_for_record(milestone), ["launch"])
            for milestone in matching_milestones
        ):
            add_evidence("Business launch milestone exists")
        if matching_recommendations:
            add_evidence("Business recommendation generated", "recommendation")

    if "personal" in category_key and matching_milestones:
        add_evidence("Personal goal progress exists in Orbit")

    return evidence, observations, strong_evidence_types, weak_evidence_count


def _summarize_readiness_advisory() -> tuple[str, dict[str, Any]]:
    readiness = orbit_service.get_readiness_categories()
    tasks = orbit_service.list_records("tasks")
    milestones = orbit_service.list_records("milestones")
    progress_history = orbit_service.list_recent_milestone_progress_history(limit=30)
    reviews = orbit_service.list_records("reviews")
    trade_sessions = orbit_service.list_trade_sessions()[:20]
    strategic_gaps = orbit_service.list_strategic_gaps()
    recommendations_output = orbit_service.generate_recommendations(
        strategic_gaps=strategic_gaps[:5],
        milestone_progress_history=progress_history,
        readiness={
            "overall": (
                round(
                    sum(int(category.get("current_score") or 0) for category in readiness)
                    / len(readiness)
                )
                if readiness
                else 0
            ),
            "categories": readiness,
        },
    )
    recommendations = recommendations_output.get("recommendations") or []

    suggestions: list[dict[str, Any]] = []
    observations_by_category: dict[str, list[str]] = {}
    for category in readiness:
        category_name = str(category.get("category_name") or "Readiness")
        current_score = int(category.get("current_score") or 0)
        target_score = int(category.get("target_score") or 100)
        (
            evidence,
            observations,
            strong_evidence_types,
            weak_evidence_count,
        ) = _collect_readiness_evidence(
            category,
            tasks,
            milestones,
            progress_history,
            reviews,
            trade_sessions,
            recommendations,
            strategic_gaps,
        )
        observations_by_category[category_name] = observations
        confidence = _confidence_for_evidence(
            strong_evidence_types,
            weak_evidence_count,
            observations,
        )
        uncapped_suggested_score = min(
            target_score,
            _score_readiness_evidence(
                category_name,
                current_score,
                evidence,
                strong_evidence_types,
                weak_evidence_count,
                len(trade_sessions),
            ),
        )
        suggested_score = min(
            uncapped_suggested_score,
            current_score + _max_increase_for_confidence(confidence),
        )
        if current_score == 0 and len(strong_evidence_types) < 3:
            suggested_score = min(suggested_score, 30)
        if suggested_score <= current_score:
            continue

        suggestions.append(
            {
                "category": category_name,
                "current_score": current_score,
                "suggested_score": suggested_score,
                "confidence": confidence,
                "evidence": evidence,
                "rationale": [
                    "Evidence suggests progress beyond current score.",
                    "Suggested increase requires manual approval before any readiness update.",
                ],
            }
        )

    suggestion_lines = [
        f"{suggestion['category']}:\n"
        f"{suggestion['current_score']} → {suggestion['suggested_score']}"
        for suggestion in suggestions[:4]
    ] or ["No readiness score increases suggested."]
    summary = (
        "Readiness Suggestions\n\n"
        + "\n\n".join(suggestion_lines)
        + "\n\nApproval Required:\nYes"
    )
    output = {
        "suggestions": suggestions,
        "approval_required": True,
        "actions_taken": [],
        "readiness_updated": False,
        "tasks_created": False,
        "reviews_created": False,
        "notifications_sent": False,
        "observations": observations_by_category,
        "evidence_reviewed": {
            "readiness_category_count": len(readiness),
            "task_count": len(tasks),
            "milestone_count": len(milestones),
            "milestone_progress_history_count": len(progress_history),
            "review_count": len(reviews),
            "trade_session_count": len(trade_sessions),
            "recommendation_count": len(recommendations),
            "strategic_gap_count": len(strategic_gaps),
        },
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

    if agent_type == "readiness_advisory":
        return _summarize_readiness_advisory()

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
