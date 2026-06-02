from fastapi import APIRouter, HTTPException, status

import agent_service
import morning_checkin
import scheduled_agents
from orbit.models import (
    AgentDefinition,
    AgentPrioritizationResult,
    AgentRun,
    MorningCheckInRequest,
    MorningCheckInResult,
    MorningCheckInStatus,
    ScheduledAgentRunOnceResult,
    ScheduledAgentStatus,
)


router = APIRouter(prefix="/agents", tags=["agents"])


def _not_found(agent_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"Agent {agent_id} not found.",
    )


@router.get("", response_model=list[AgentDefinition])
def list_agents():
    return agent_service.list_agents()


@router.get("/runs/recent", response_model=list[AgentRun])
def list_recent_agent_runs():
    return agent_service.list_recent_agent_runs()


@router.get("/prioritize", response_model=AgentPrioritizationResult)
def prioritize_agents():
    return agent_service.prioritize_agents()


@router.get("/scheduled/status", response_model=ScheduledAgentStatus)
def get_scheduled_agent_status():
    return scheduled_agents.get_status()


@router.post("/scheduled/run-once", response_model=ScheduledAgentRunOnceResult)
def run_scheduled_agents_once():
    return scheduled_agents.run_due_once()


@router.get("/morning/status", response_model=MorningCheckInStatus)
def get_morning_checkin_status():
    return morning_checkin.get_status()


@router.post("/morning/check-in", response_model=MorningCheckInResult)
def run_morning_checkin(request: MorningCheckInRequest):
    try:
        return morning_checkin.check_in(
            source=request.source,
            speak=request.speak,
        )
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.post("/morning/fallback-check", response_model=MorningCheckInResult)
def run_morning_fallback_check():
    try:
        return morning_checkin.fallback_check()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc


@router.get("/{agent_id}", response_model=AgentDefinition)
def get_agent(agent_id: int):
    agent = agent_service.get_agent(agent_id)
    if agent is None:
        raise _not_found(agent_id)
    return agent


@router.post("/{agent_id}/run", response_model=AgentRun)
def run_agent(agent_id: int):
    try:
        return agent_service.run_agent(agent_id)
    except agent_service.AgentNotFoundError:
        raise _not_found(agent_id)
    except agent_service.AgentDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
