from fastapi import APIRouter, File, HTTPException, UploadFile, status

from . import service
from . import trade_journal_import
from .models import (
    DailyCloseoutReviewCreate,
    Goal,
    GoalCreate,
    GoalUpdate,
    InboxTaskCreate,
    MajorEvent,
    MajorEventCreate,
    MajorEventUpdate,
    Milestone,
    MilestoneCreate,
    MilestoneProgressAdvisory,
    MilestoneProgressHistory,
    MilestoneUpdate,
    ReadinessCategory,
    ReadinessCategoryUpdate,
    RecommendationTaskDraft,
    RecommendationSet,
    Review,
    ReviewCreate,
    ScheduleBlock,
    ScheduleBlockCreate,
    ScheduleBlockUpdate,
    ScheduleIntelligence,
    StrategicGap,
    Task,
    TaskCreate,
    TaskMilestoneLink,
    TaskPriority,
    TaskUpdate,
    TradeJournalCreate,
    TradeJournalImportPreview,
    TradeJournalImportSaveRequest,
    TradeJournalImportSaveResponse,
    TradeJournalRead,
    TradeJournalUpdate,
    TaskWithMilestones,
    TradeSessionCreate,
    TradeSessionRead,
    TradeSessionUpdate,
)


router = APIRouter(prefix="/orbit", tags=["orbit"])


@router.get("/health")
def orbit_health_check():
    return {"status": "orbit routes mounted"}


@router.get("/morning-briefing")
def get_morning_briefing():
    return service.generate_morning_briefing()


@router.get("/daily-closeout")
def get_daily_closeout():
    return service.generate_daily_closeout()


@router.get("/recommendations", response_model=RecommendationSet)
def get_recommendations():
    return service.generate_recommendations()


@router.post("/daily-closeout/review", response_model=Review, status_code=status.HTTP_201_CREATED)
def create_daily_closeout_review(payload: DailyCloseoutReviewCreate):
    return service.create_daily_closeout_review(payload)


def _not_found(name: str, record_id: int) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"{name} {record_id} not found.",
    )


def _validation_error(message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail=message,
    )


@router.get("/schedule-blocks", response_model=list[ScheduleBlock])
def list_schedule_blocks():
    return service.list_schedule_blocks()


@router.get("/schedule/intelligence", response_model=ScheduleIntelligence)
def get_schedule_intelligence():
    return service.get_schedule_intelligence()


@router.post("/schedule-blocks", response_model=ScheduleBlock, status_code=status.HTTP_201_CREATED)
def create_schedule_block(payload: ScheduleBlockCreate):
    try:
        return service.create_schedule_block(payload)
    except ValueError as error:
        raise _validation_error(str(error)) from error


@router.patch("/schedule-blocks/{schedule_block_id}", response_model=ScheduleBlock)
def update_schedule_block(schedule_block_id: int, payload: ScheduleBlockUpdate):
    try:
        record = service.update_schedule_block(schedule_block_id, payload)
    except ValueError as error:
        raise _validation_error(str(error)) from error

    if record is None:
        raise _not_found("Schedule block", schedule_block_id)
    return record


@router.delete("/schedule-blocks/{schedule_block_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule_block(schedule_block_id: int):
    if not service.delete_record("schedule_blocks", schedule_block_id):
        raise _not_found("Schedule block", schedule_block_id)


@router.post("/major-events", response_model=MajorEvent, status_code=status.HTTP_201_CREATED)
def create_major_event(payload: MajorEventCreate):
    return service.create_major_event(payload)


@router.get("/major-events", response_model=list[MajorEvent])
def list_major_events():
    return service.list_major_events()


@router.get("/major-events/{event_id}", response_model=MajorEvent)
def get_major_event(event_id: int):
    record = service.get_major_event(event_id)
    if record is None:
        raise _not_found("Major event", event_id)
    return record


@router.patch("/major-events/{event_id}", response_model=MajorEvent)
def update_major_event(event_id: int, payload: MajorEventUpdate):
    record = service.update_major_event(event_id, payload)
    if record is None:
        raise _not_found("Major event", event_id)
    return record


@router.delete("/major-events/{event_id}", response_model=MajorEvent)
def archive_major_event(event_id: int):
    record = service.archive_major_event(event_id)
    if record is None:
        raise _not_found("Major event", event_id)
    return record


@router.post("/milestones", response_model=Milestone, status_code=status.HTTP_201_CREATED)
def create_milestone(payload: MilestoneCreate):
    return service.create_milestone(payload)


@router.get("/milestones", response_model=list[Milestone])
def list_milestones():
    return service.list_records("milestones")


@router.get("/milestones/progress-advisory", response_model=list[MilestoneProgressAdvisory])
def list_milestone_progress_advisories():
    return service.list_milestone_progress_advisories()


@router.get("/progress-history/recent", response_model=list[MilestoneProgressHistory])
def list_recent_progress_history():
    return service.list_recent_milestone_progress_history()


@router.get("/milestones/{milestone_id}", response_model=Milestone)
def get_milestone(milestone_id: int):
    record = service.get_record("milestones", milestone_id)
    if record is None:
        raise _not_found("Milestone", milestone_id)
    return record


@router.patch("/milestones/{milestone_id}", response_model=Milestone)
def update_milestone(milestone_id: int, payload: MilestoneUpdate):
    record = service.update_milestone(milestone_id, payload)
    if record is None:
        raise _not_found("Milestone", milestone_id)
    return record


@router.get(
    "/milestones/{milestone_id}/progress-advisory",
    response_model=MilestoneProgressAdvisory,
)
def get_milestone_progress_advisory(milestone_id: int):
    record = service.get_milestone_progress_advisory(milestone_id)
    if record is None:
        raise _not_found("Milestone", milestone_id)
    return record


@router.get(
    "/milestones/{milestone_id}/progress-history",
    response_model=list[MilestoneProgressHistory],
)
def list_milestone_progress_history(milestone_id: int):
    if service.get_record("milestones", milestone_id) is None:
        raise _not_found("Milestone", milestone_id)
    return service.list_milestone_progress_history(milestone_id)


@router.delete("/milestones/{milestone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_milestone(milestone_id: int):
    if not service.delete_record("milestones", milestone_id):
        raise _not_found("Milestone", milestone_id)


@router.post("/goals", response_model=Goal, status_code=status.HTTP_201_CREATED)
def create_goal(payload: GoalCreate):
    return service.create_goal(payload)


@router.get("/goals", response_model=list[Goal])
def list_goals():
    return service.list_records("goals")


@router.get("/goals/{goal_id}", response_model=Goal)
def get_goal(goal_id: int):
    record = service.get_record("goals", goal_id)
    if record is None:
        raise _not_found("Goal", goal_id)
    return record


@router.patch("/goals/{goal_id}", response_model=Goal)
def update_goal(goal_id: int, payload: GoalUpdate):
    record = service.update_goal(goal_id, payload)
    if record is None:
        raise _not_found("Goal", goal_id)
    return record


@router.delete("/goals/{goal_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_goal(goal_id: int):
    if not service.delete_record("goals", goal_id):
        raise _not_found("Goal", goal_id)


@router.post("/tasks", response_model=Task, status_code=status.HTTP_201_CREATED)
def create_task(payload: TaskCreate):
    return service.create_task(payload)


@router.get("/inbox-tasks", response_model=list[TaskWithMilestones])
def list_inbox_tasks():
    return service.list_inbox_tasks()


@router.post("/inbox-tasks", response_model=TaskWithMilestones, status_code=status.HTTP_201_CREATED)
def create_inbox_task(payload: InboxTaskCreate):
    return service.create_inbox_task(payload)


@router.get("/tasks", response_model=list[Task])
def list_tasks():
    return service.list_records("tasks")


@router.get("/task-priorities", response_model=list[TaskPriority])
def list_task_priorities():
    return service.list_task_priorities()


@router.get("/strategic-gaps", response_model=list[StrategicGap])
def list_strategic_gaps():
    return service.list_strategic_gaps()


@router.post(
    "/recommendations/{recommendation_id}/task-draft",
    response_model=RecommendationTaskDraft,
)
def get_recommendation_task_draft(recommendation_id: str):
    record = service.get_recommendation_task_draft(recommendation_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation {recommendation_id} not found.",
        )
    return record


@router.post(
    "/recommendations/{recommendation_id}/create-task",
    response_model=TaskWithMilestones,
    status_code=status.HTTP_201_CREATED,
)
def create_task_from_recommendation(recommendation_id: str):
    record = service.create_task_from_recommendation(recommendation_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation {recommendation_id} not found.",
        )
    return record


@router.get("/tasks/{task_id}", response_model=Task)
def get_task(task_id: int):
    record = service.get_record("tasks", task_id)
    if record is None:
        raise _not_found("Task", task_id)
    return record


@router.patch("/tasks/{task_id}", response_model=Task)
def update_task(task_id: int, payload: TaskUpdate):
    record = service.update_task(task_id, payload)
    if record is None:
        raise _not_found("Task", task_id)
    return record


@router.post(
    "/tasks/{task_id}/milestones/{milestone_id}",
    response_model=TaskMilestoneLink,
    status_code=status.HTTP_201_CREATED,
)
def link_task_to_milestone(task_id: int, milestone_id: int):
    record = service.link_task_to_milestone(task_id, milestone_id)
    if record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task or milestone not found.",
        )
    return record


@router.delete(
    "/tasks/{task_id}/milestones/{milestone_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def unlink_task_from_milestone(task_id: int, milestone_id: int):
    if not service.unlink_task_from_milestone(task_id, milestone_id):
        raise _not_found("Task milestone link", milestone_id)


@router.get("/tasks/{task_id}/milestones", response_model=list[Milestone])
def list_milestones_linked_to_task(task_id: int):
    if service.get_record("tasks", task_id) is None:
        raise _not_found("Task", task_id)
    return service.list_milestones_linked_to_task(task_id)


@router.get("/milestones/{milestone_id}/tasks", response_model=list[TaskWithMilestones])
def list_tasks_linked_to_milestone(milestone_id: int):
    if service.get_record("milestones", milestone_id) is None:
        raise _not_found("Milestone", milestone_id)
    return service.list_tasks_linked_to_milestone(milestone_id)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: int):
    if not service.delete_record("tasks", task_id):
        raise _not_found("Task", task_id)


@router.post("/reviews", response_model=Review, status_code=status.HTTP_201_CREATED)
def create_review(payload: ReviewCreate):
    return service.create_review(payload)


@router.get("/reviews", response_model=list[Review])
def list_reviews():
    return service.list_records("reviews")


@router.get("/readiness", response_model=list[ReadinessCategory])
def get_readiness_categories():
    return service.get_readiness_categories()


@router.patch("/readiness/{readiness_id}", response_model=ReadinessCategory)
def update_readiness_category(readiness_id: int, payload: ReadinessCategoryUpdate):
    record = service.update_readiness_category(readiness_id, payload)
    if record is None:
        raise _not_found("Readiness category", readiness_id)
    return record


@router.post("/trade-sessions", response_model=TradeSessionRead, status_code=status.HTTP_201_CREATED)
def create_trade_session(payload: TradeSessionCreate):
    return service.create_trade_session(payload)


@router.get("/trade-sessions", response_model=list[TradeSessionRead])
def list_trade_sessions():
    return service.list_trade_sessions()


@router.get("/trade-sessions/{trade_session_id}", response_model=TradeSessionRead)
def get_trade_session(trade_session_id: int):
    record = service.get_trade_session(trade_session_id)
    if record is None:
        raise _not_found("Trade session", trade_session_id)
    return record


@router.patch("/trade-sessions/{trade_session_id}", response_model=TradeSessionRead)
def update_trade_session(trade_session_id: int, payload: TradeSessionUpdate):
    record = service.update_trade_session(trade_session_id, payload)
    if record is None:
        raise _not_found("Trade session", trade_session_id)
    return record


@router.delete("/trade-sessions/{trade_session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trade_session(trade_session_id: int):
    if not service.delete_trade_session(trade_session_id):
        raise _not_found("Trade session", trade_session_id)


@router.post("/trade-journal", response_model=TradeJournalRead, status_code=status.HTTP_201_CREATED)
def create_trade_journal_entry(payload: TradeJournalCreate):
    return service.create_trade_journal_entry(payload)


@router.get("/trade-journal", response_model=list[TradeJournalRead])
def list_trade_journal_entries():
    return service.list_trade_journal_entries()


@router.post("/trade-journal/import-pdf", response_model=TradeJournalImportPreview)
async def preview_trade_journal_pdf_import(
    performance_pdf: UploadFile | None = File(default=None),
    orders_pdf: UploadFile | None = File(default=None),
):
    performance_payload = None
    orders_payload = None

    if performance_pdf is not None:
        performance_payload = (
            performance_pdf.filename or "performance.pdf",
            await performance_pdf.read(),
        )

    if orders_pdf is not None:
        orders_payload = (
            orders_pdf.filename or "orders.pdf",
            await orders_pdf.read(),
        )

    return trade_journal_import.preview_trade_journal_pdf_import(
        performance_pdf=performance_payload,
        orders_pdf=orders_payload,
    )


@router.post(
    "/trade-journal/import-pdf/save",
    response_model=TradeJournalImportSaveResponse,
    status_code=status.HTTP_201_CREATED,
)
def save_trade_journal_pdf_import(payload: TradeJournalImportSaveRequest):
    return trade_journal_import.save_trade_journal_import(payload)


@router.get("/trade-journal/{entry_id}", response_model=TradeJournalRead)
def get_trade_journal_entry(entry_id: int):
    record = service.get_trade_journal_entry(entry_id)
    if record is None:
        raise _not_found("Trade journal entry", entry_id)
    return record


@router.patch("/trade-journal/{entry_id}", response_model=TradeJournalRead)
def update_trade_journal_entry(entry_id: int, payload: TradeJournalUpdate):
    record = service.update_trade_journal_entry(entry_id, payload)
    if record is None:
        raise _not_found("Trade journal entry", entry_id)
    return record


@router.delete("/trade-journal/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_trade_journal_entry(entry_id: int):
    if not service.delete_trade_journal_entry(entry_id):
        raise _not_found("Trade journal entry", entry_id)
