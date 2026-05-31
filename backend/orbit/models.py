from datetime import date, datetime
from typing import Optional

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
    target_value: Optional[float] = None
    current_value: Optional[float] = None
    due_date: Optional[date] = None


class Milestone(MilestoneBase):
    id: int


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


class ReviewBase(BaseModel):
    title: Optional[str] = None
    review_type: str
    summary: Optional[str] = None
    rating: Optional[float] = None


class ReviewCreate(ReviewBase):
    pass


class Review(ReviewBase):
    id: int
    created_at: datetime
