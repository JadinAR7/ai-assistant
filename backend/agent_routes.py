from fastapi import APIRouter, HTTPException, status

import agent_service
from orbit.models import AgentDefinition, AgentPrioritizationResult, AgentRun


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
