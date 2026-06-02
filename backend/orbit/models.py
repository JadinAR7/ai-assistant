from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class MajorEventBase(BaseModel):
    title: str
    description: Optional[str] = None
    target_date: Optional[date] = None
    status: str = "not_started"
    progress_percent: int = Field(default=0, ge=0, le=100)


class MajorEventCreate(MajorEventBase):
    pass


class MajorEventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    target_date: Optional[date] = None
    status: Optional[str] = None
    progress_percent: Optional[int] = Field(default=None, ge=0, le=100)


class MajorEvent(MajorEventBase):
    id: int
    created_at: datetime
    updated_at: datetime


class MilestoneBase(BaseModel):
    major_event_id: int
    title: str
    description: Optional[str] = None
    status: str = "not_started"
    progress_percent: int = Field(default=0, ge=0, le=100)
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    due_date: Optional[date] = None


class MilestoneCreate(MilestoneBase):
    pass


class MilestoneUpdate(BaseModel):
    major_event_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    progress_percent: Optional[int] = Field(default=None, ge=0, le=100)
    progress_update_source: Optional[
        Literal["manual", "task_advisory", "helix_tool", "system"]
    ] = None
    progress_update_reason: Optional[str] = None
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    due_date: Optional[date] = None


class Milestone(MilestoneBase):
    id: int


class MilestoneProgressHistory(BaseModel):
    id: int
    milestone_id: int
    milestone_title: Optional[str] = None
    previous_progress: int
    new_progress: int
    change_amount: int
    reason: Optional[str] = None
    source: Literal["manual", "task_advisory", "helix_tool", "system"]
    created_at: datetime


class GoalBase(BaseModel):
    milestone_id: int
    title: str
    description: Optional[str] = None
    status: str = "not_started"
    priority: int = 0


class GoalCreate(GoalBase):
    pass


class GoalUpdate(BaseModel):
    milestone_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[int] = None


class Goal(GoalBase):
    id: int


class TaskBase(BaseModel):
    goal_id: int
    title: str
    description: Optional[str] = None
    status: str = "not_started"
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    goal_id: Optional[int] = None
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None


class Task(TaskBase):
    id: int


class LinkedMilestone(BaseModel):
    id: int
    title: str
    status: str
    progress_percent: int
    major_event_id: Optional[int] = None
    major_event_title: Optional[str] = None


class TaskWithMilestones(Task):
    milestones: list[LinkedMilestone] = Field(default_factory=list)
    priority_score: int = 0
    priority_factors: list[str] = Field(default_factory=list)


class TaskPriority(BaseModel):
    id: int
    title: str
    priority_score: int
    factors: list[str] = Field(default_factory=list)


class StrategicGap(BaseModel):
    milestone_id: int
    title: str
    priority_score: int
    reasons: list[str] = Field(default_factory=list)


class RecommendationTaskDraft(BaseModel):
    title: str
    description: Optional[str] = None
    milestone_ids: list[int] = Field(default_factory=list)
class Recommendation(BaseModel):
    id: str
    category: Literal[
        "task_execution",
        "strategic_gap",
        "blocker_resolution",
        "readiness_improvement",
    ]
    recommendation: str
    score: int
    rationale: list[str] = Field(default_factory=list)


class RecommendationSet(BaseModel):
    success: bool
    generated_at: datetime
    recommendations: list[Recommendation] = Field(default_factory=list)
    rationale: list[str] = Field(default_factory=list)


class TaskMilestoneLink(BaseModel):
    id: int
    task_id: int
    milestone_id: int
    created_at: datetime


class MilestoneProgressAdvisory(BaseModel):
    milestone_id: int
    total_linked_tasks: int
    completed_linked_tasks: int
    open_linked_tasks: int
    in_progress_linked_tasks: int
    queued_linked_tasks: int
    suggested_task_completion_percent: Optional[int] = None
    reason: Optional[str] = None


class InboxTaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: str = "queued"
    due_date: Optional[date] = None
    milestone_ids: list[int] = Field(default_factory=list)


class ReviewBase(BaseModel):
    title: Optional[str] = None
    review_type: str
    summary: Optional[str] = None
    rating: Optional[float] = None


class ReviewCreate(ReviewBase):
    pass


class DailyCloseoutReviewCreate(BaseModel):
    rating: Optional[float] = Field(default=None, ge=1, le=10)
    summary: Optional[str] = None


class Review(ReviewBase):
    id: int
    created_at: datetime


class ReadinessCategoryBase(BaseModel):
    major_event_id: int
    category_name: str
    current_score: int = Field(default=0, ge=0, le=100)
    target_score: int = Field(default=100, ge=0, le=100)
    notes: Optional[str] = None


class ReadinessCategoryCreate(ReadinessCategoryBase):
    pass


class ReadinessCategoryUpdate(BaseModel):
    major_event_id: Optional[int] = None
    category_name: Optional[str] = None
    current_score: Optional[int] = Field(default=None, ge=0, le=100)
    target_score: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = None


class ReadinessCategory(ReadinessCategoryBase):
    id: int
    last_updated: datetime


class TradeSessionBase(BaseModel):
    session_date: date
    symbol: str
    pnl: float
    notes: Optional[str] = None
    rule_adherence: Optional[int] = Field(default=None, ge=0, le=100)
    confidence: Optional[int] = Field(default=None, ge=0, le=10)
    session_grade: Optional[str] = None


class TradeSessionCreate(TradeSessionBase):
    pass


class TradeSessionUpdate(BaseModel):
    session_date: Optional[date] = None
    symbol: Optional[str] = None
    pnl: Optional[float] = None
    notes: Optional[str] = None
    rule_adherence: Optional[int] = Field(default=None, ge=0, le=100)
    confidence: Optional[int] = Field(default=None, ge=0, le=10)
    session_grade: Optional[str] = None


class TradeSessionRead(TradeSessionBase):
    id: int
    created_at: datetime
    updated_at: datetime


class AgentRun(BaseModel):
    id: int
    agent_id: int
    agent_name: Optional[str] = None
    status: Literal["running", "completed", "failed"]
    started_at: datetime
    completed_at: Optional[datetime] = None
    summary: Optional[str] = None
    output_json: Optional[dict] = None
    error: Optional[str] = None


class AgentPriorityRank(BaseModel):
    agent_type: str
    agent_name: str
    priority_score: int
    reasons: list[str] = Field(default_factory=list)


class AgentPrioritizationResult(BaseModel):
    recommended_agent_type: str
    recommended_agent_name: str
    priority_score: int
    reason: str
    ranked_agents: list[AgentPriorityRank] = Field(default_factory=list)
    actions_taken: list[str] = Field(default_factory=list)


class AgentDefinition(BaseModel):
    id: int
    name: str
    agent_type: str
    description: Optional[str] = None
    enabled: bool
    created_at: datetime
    updated_at: datetime
    last_run: Optional[AgentRun] = None
