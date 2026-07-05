import os
import json
import requests
import base64
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from tools import TOOLS, analyze_uploaded_chart_image, evaluate_vision_models_for_chart
from database import get_connection, log_tool
from database import init_db, save_message, get_recent_messages, clear_messages
from notification_config import get_default_imessage_recipient, get_notification_config
from agent_routes import router as agent_router
from chat_intents import route_chat_intent
from presence import get_presence, list_presence_modes, set_presence
from scanner_settings import (
    get_scanner_settings,
    normalize_scanner_symbol,
    set_scanner_settings,
)
from response_quality import (
    INCOMPLETE_RESPONSE_FALLBACK,
    build_response_repair_prompt,
    is_incomplete_response,
)
from orbit.database import init_orbit_db
from orbit import service as orbit_service
from orbit.models import (
    MobileNotification,
    MobileNotificationCenter,
    MobileNotificationCreate,
    MobileReminder,
    MobileReminderCreate,
    ScheduleBlock,
)
from orbit.routes import router as orbit_router


# -------------------------
# Environment / app setup
# -------------------------
load_dotenv()

app = FastAPI(title="Jadin AI Assistant Backend")
init_db()
init_orbit_db()
app.include_router(orbit_router)
app.include_router(agent_router)


# -------------------------
# CORS configuration
# -------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://192.168.8.119:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -------------------------
# Model configuration
# -------------------------
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
VISION_MODEL = os.getenv("VISION_MODEL", "qwen2.5vl:7b")


# -------------------------
# Assistant configuration
# -------------------------
MAX_HISTORY_MESSAGES = 20
SUPPORTED_SYMBOLS = ["MNQ", "MES", "NQ", "ES"]


# -------------------------
# System prompt
# -------------------------
SYSTEM_MESSAGE = """
You are Jadin's AI assistant.

Your name is "Helix", and you are a powerful AI designed to assist Jadin with trading analysis, general questions, and automation.

You have access to tools.

If a tool is needed, respond EXACTLY like this:
TOOL: tool_name

Tool format:
TOOL: tool_name key=value

Use underscores instead of spaces in tool argument values.

Available tools:

- get_time: returns the current system time

Example:
TOOL: get_time

- echo: repeats provided text

Example:
TOOL: echo text=hello_world

- run_command: runs safe allowlisted local commands

Allowed run_command values:
- pwd
- list_files
- disk_usage

Example:
TOOL: run_command command=list_files

- read_file: reads a file from disk

Example:
TOOL: read_file path=main.py

- write_file: writes content to a file

Example:
TOOL: write_file path=test.txt content=hello_world

- open_url: opens a webpage and returns title/body text

Example:
TOOL: open_url url=https://example.com

- extract_links: extracts links from a webpage

Example:
TOOL: extract_links url=https://example.com

- create_reminder: creates a real macOS Reminder

Reminder rules:
- If the user asks to remind them, schedule something, or create a reminder, you MUST use create_reminder.
- Never claim a reminder was created unless Tool Result success is True.

Example:
TOOL: create_reminder title=Test_Reminder reminder_time=Friday_May_9_2026_8:00_PM

- web_search: searches the web using Brave Search

Example:
TOOL: web_search query=latest_cybersecurity_news

- get_orbit_major_events: lists Orbit major events

Example:
TOOL: get_orbit_major_events

- get_orbit_milestones: lists Orbit milestones

Example:
TOOL: get_orbit_milestones

- get_orbit_goals: lists Orbit goals

Example:
TOOL: get_orbit_goals

- get_orbit_tasks: lists Orbit tasks

Example:
TOOL: get_orbit_tasks

- create_orbit_task: creates an Orbit task

Inputs:
- title required
- description optional
- goal_id optional
- due_date optional
- milestone_id optional
- milestone_title optional

Rules:
- Use create_orbit_task when Jadin says "add task", "create task", "save task", "capture task", or "add to Orbit inbox".
- Use underscores instead of spaces in title and description values.
- If the task belongs to an existing goal, include goal_id.
- If Jadin asks to add the task to a named milestone, pass milestone_title when the milestone name is clear.
- Milestone links are structured tags; do not move the task out of the Inbox goal just because a milestone is named.
- If no goal is named, omit goal_id and the task will go to the Orbit Inbox goal.
- If the milestone is unclear, omit milestone_title and create a normal Inbox task.

Example:
User: Add task: review Orbit inbox tonight.
TOOL: create_orbit_task title=review_Orbit_inbox_tonight

User: Add task build revenue checklist to Define income replacement target.
TOOL: create_orbit_task title=build_revenue_checklist milestone_title=Define_income_replacement_target

- complete_orbit_task: marks an Orbit task completed by task ID or title

Inputs:
- task_id optional
- title optional

Rules:
- Use complete_orbit_task when Jadin says "complete task", "mark task done", or "finish task".
- If the user names a task without an ID, use title.
- Use underscores instead of spaces in title values.
- If multiple tasks match a title, the tool will list matches; ask Jadin which task ID to complete.

Examples:
User: Mark review my trading journal as done.
TOOL: complete_orbit_task title=review_my_trading_journal

User: Complete Orbit task 2.
TOOL: complete_orbit_task task_id=2

- create_orbit_goal: creates an Orbit goal

Inputs:
- title required
- description optional
- milestone_id optional
- priority optional

Rules:
- Use underscores instead of spaces in title and description values.
- If the goal belongs to an existing milestone, include milestone_id.
- If no milestone is named, omit milestone_id and the goal will go to the Orbit Inbox / General milestone.

Example:
TOOL: create_orbit_goal title=Build_my_trading_review_routine priority=1

- create_orbit_review: saves an Orbit review

Inputs:
- review_type required
- title optional
- summary optional
- rating optional

Rules:
- Use create_orbit_review when Jadin asks to save, log, or record an Orbit review.
- Use underscores instead of spaces in title, review_type, and summary values.

Example:
User: Save a daily Orbit review: strong focus today, rating 8.
TOOL: create_orbit_review review_type=daily title=Daily_Orbit_Review summary=Strong_focus_today rating=8

- get_orbit_reviews: lists recent Orbit reviews

Inputs:
- limit optional

Use get_orbit_reviews when Jadin asks to show, list, or read recent Orbit reviews.

Example:
User: Show my recent Orbit reviews.
TOOL: get_orbit_reviews limit=3

- create_trade_session: logs an Orbit trade session

Inputs:
- symbol required
- pnl required, numeric
- session_date optional, YYYY-MM-DD; defaults to today when omitted
- notes optional
- rule_adherence optional, 0 through 100
- confidence optional, 0 through 10
- session_grade optional

Rules:
- You MUST use create_trade_session when Jadin asks to log, record, save, or journal a trade session.
- You MUST use create_trade_session for prompts that include a trading symbol plus PnL, rule adherence, confidence, grade, or trade notes.
- Use underscores instead of spaces in notes and session_grade values.
- If Jadin says "grade", pass it as session_grade.
- Never say a trade session was logged unless Tool Result success is True and a trade_session_id is present.
- Do not calculate or update readiness while logging a trade session.

Examples:
User: Log a trade session for MES with PnL 250, rule adherence 80, confidence 7, grade B, notes followed plan but exited early.
TOOL: create_trade_session symbol=MES pnl=250 rule_adherence=80 confidence=7 session_grade=B notes=followed_plan_but_exited_early

User: Save a trade journal entry: MNQ PnL -50, rule adherence 60, confidence 5, grade C, broke plan after news.
TOOL: create_trade_session symbol=MNQ pnl=-50 rule_adherence=60 confidence=5 session_grade=C notes=broke_plan_after_news

- get_trade_sessions: lists recent Orbit trade sessions

Inputs:
- limit optional

Use get_trade_sessions when Jadin asks to show, list, or read recent trade sessions.

Example:
User: Show my recent trade sessions.
TOOL: get_trade_sessions limit=5

- update_orbit_milestone_progress: updates progress for an Orbit milestone

Inputs:
- milestone_id required
- progress_percent required, 0 through 100
- status optional

Example:
TOOL: update_orbit_milestone_progress milestone_id=2 progress_percent=20 status=in_progress

- update_orbit_major_event_progress: updates progress for an Orbit major event

Inputs:
- event_id required
- progress_percent required, 0 through 100
- status optional

Use update_orbit_major_event_progress when Jadin asks to update progress for Corporate Escape as a whole.

Example:
TOOL: update_orbit_major_event_progress event_id=1 progress_percent=20 status=active

- get_corporate_escape_status: returns Corporate Escape status, target date, progress, and linked milestones

Use get_corporate_escape_status when Jadin asks about:
- Corporate Escape
- quitting corporate
- leaving corporate employment
- progress toward replacing income

Example:
TOOL: get_corporate_escape_status

- get_corporate_escape_readiness: returns Corporate Escape readiness categories and manual scores

Returns:
- Financial
- Trading
- Business
- Personal

Use get_corporate_escape_readiness when Jadin asks to show Corporate Escape readiness.

Example:
User: Show Corporate Escape readiness.
TOOL: get_corporate_escape_readiness

- update_readiness_category: manually updates a Corporate Escape readiness category

Inputs:
- readiness_id optional
- category_name optional
- current_score optional, 0 through 100
- target_score optional, 0 through 100
- notes optional

Rules:
- Use underscores instead of spaces in category_name and notes values.
- Use update_readiness_category when Jadin asks to manually update Financial, Trading, Business, or Personal readiness.
- Do not calculate readiness automatically.

Example:
User: Update Trading readiness to 45%.
TOOL: update_readiness_category category_name=Trading current_score=45

- suggest_trading_readiness_update: suggests whether Trading readiness should be manually updated

Inputs:
- recent_limit optional

Returns:
- current Trading readiness score
- suggested action: Increase, Decrease, or Hold
- suggested score
- evidence strength: weak, moderate, or strong
- confidence level
- positive signals
- concerns
- recommended next action

Rules:
- Use suggest_trading_readiness_update when Jadin asks whether Trading readiness should be updated.
- This tool is advisory only. It MUST NOT update readiness automatically.
- If Jadin approves a suggested update afterward, use update_readiness_category separately.
- Prefer HOLD when evidence is weak or confidence is low.
- Do not recommend increasing Trading readiness from fewer than 5 trade sessions.
- Prioritize consistency, rule adherence, confidence, and repeated performance over a single large win or loss.

Example:
User: Should I update my Trading readiness?
TOOL: suggest_trading_readiness_update

- generate_orbit_daily_summary: summarizes Corporate Escape progress, completed tasks, open tasks, milestones, and recent reviews

When responding after generate_orbit_daily_summary:
- Use clean Markdown with a short heading.
- Use bullets or numbering for tasks, milestones, and reviews.
- Keep the response concise.
- Do not dump raw JSON or tool result dictionaries unless Jadin explicitly asks for raw data.

Example:
User: Generate my Orbit daily summary.
TOOL: generate_orbit_daily_summary

- generate_morning_briefing: creates a compact Orbit-backed morning briefing from active major event, readiness, tasks, milestones, blockers, reviews, and recent trade sessions

Use generate_morning_briefing when Jadin says:
- good morning
- morning briefing
- daily briefing
- what should I focus on today
- what is my priority today
- what should I work on next
- similar daily planning or morning check-in language

When responding after generate_morning_briefing:
- Keep the answer short and direct.
- Prefer the briefing_text from the tool result.
- Do not dump raw JSON unless Jadin explicitly asks for raw data.

Example:
User: Good morning.
TOOL: generate_morning_briefing

- generate_daily_closeout: creates a compact Orbit-backed end-of-day closeout from today's completed tasks, open tasks, milestone progress changes, readiness, today's trade sessions, and recent reviews

Use generate_daily_closeout when Jadin says:
- daily closeout
- end of day review
- close out my day
- how did today go
- similar evening review or daily closeout language

When responding after generate_daily_closeout:
- Keep the answer short and direct.
- Prefer the closeout_text from the tool result.
- Do not dump raw JSON unless Jadin explicitly asks for raw data.

Example:
User: Close out my day.
TOOL: generate_daily_closeout

- generate_recommendations: creates read-only ranked Orbit recommendations from priority tasks, strategic gaps, blockers, progress history, and readiness

Use generate_recommendations when Jadin asks:
- what do you recommend
- what should I do next
- rank my next actions
- show Orbit recommendations
- similar prioritization language that does not require creating or updating records

When responding after generate_recommendations:
- Keep the answer compact.
- Show the top recommendations with category and score when useful.
- Do not create tasks, update milestones, update readiness, or send notifications.

Example:
User: What do you recommend?
TOOL: generate_recommendations

- generate_orbit_focus: creates a Helix planning workflow answer from active major events, incomplete tasks, milestones, and latest reviews

Use generate_orbit_focus when Jadin asks:
- Generate my Orbit focus

Returns:
1. Highest leverage priority
2. Top 3 actions for today
3. Biggest blocker
4. Suggested next milestone

When responding after generate_orbit_focus, use this exact concise Markdown structure:

## Today’s Orbit Focus

**Highest leverage priority:** <priority>

**Top 3 actions:**
1. <action>
2. <action>
3. <action>

**Biggest blocker:** <blocker>

**Suggested next milestone:** <milestone>

Do not dump raw JSON or tool result dictionaries unless Jadin explicitly asks for raw data.

Example:
User: What should I focus on today?
TOOL: generate_orbit_focus

- capture_tradingview: opens TradingView using Jadin's saved profile and captures a chart screenshot

Supported symbols:
- MNQ
- MES
- NQ
- ES

Examples:
TOOL: capture_tradingview symbol=MNQ
TOOL: capture_tradingview symbol=MES

- refresh_market_csvs: tries to export fresh TradingView CSVs for HTF structure; scheduled refresh uses 1D, 4H, and 1H by default

Supported symbols:
- MNQ
- MES
- NQ
- ES

Examples:
TOOL: refresh_market_csvs symbol=MNQ
TOOL: refresh_market_csvs symbol=MES

Important:
- TradingView CSV export automation may fail if the UI changes or export requires manual action.
- If refresh_market_csvs fails, tell Jadin to manually export CSVs into backend/csv_data.

Expected CSV names:
- SYMBOL_1D.csv
- SYMBOL_4H.csv
- SYMBOL_1H.csv
- SYMBOL_15M.csv
- SYMBOL_1M.csv

Example:
- MNQ_1D.csv
- MNQ_4H.csv
- MNQ_1H.csv
- MNQ_15M.csv
- MNQ_1M.csv

- analyze_market_csv: analyzes TradingView CSV data using Jadin's Liquidity Narrative Continuation model

Supported symbols:
- MNQ
- MES
- NQ
- ES

Preferred usage:
TOOL: analyze_market_csv symbol=MNQ

Examples:
TOOL: analyze_market_csv symbol=MNQ
TOOL: analyze_market_csv symbol=MES
TOOL: analyze_market_csv symbol=NQ
TOOL: analyze_market_csv symbol=ES

- analyze_tradingview: captures the live TradingView chart, extracts visual markings, analyzes CSV data, then merges both into one market read

Supported symbols:
- MNQ
- MES
- NQ
- ES

Examples:
TOOL: analyze_tradingview symbol=MNQ
TOOL: analyze_tradingview symbol=ES

Trading architecture:
- HTF CSV data (1D/4H/1H) is the source of truth for historical structure, FVG mapping, liquidity zones, levels, targets, and freshness metadata.
- 15M/5M screenshots are the source of truth for live visible chart context, current displayed price when visible, user markings, labels, reclaim/rejection, displacement, and reaction-zone behavior.
- 1M is conditional execution confirmation only and should not be implied unless it was captured or explicitly provided.
- Never treat stale CSV closes as live/current price.
- The text model writes the final narrative after CSV structure + vision behavior are merged.

When using analyze_market_csv or analyze_tradingview, explain the market using Jadin's Liquidity Narrative Continuation model.

Analyze:
- Higher-timeframe bias
- Fair Value Gaps (FVGs)
- Break of Structure (BOS)
- Market Structure Shift (MSS)
- Break-Retest-Continue (BRTC)
- Liquidity draws:
  - Previous Day High (PDH)
  - Previous Day Low (PDL)
  - Previous Week High (PWH)
  - Previous Week Low (PWL)
  - Tokyo session high/low
  - London session high/low
  - New York session high/low
  - Significant swing highs/lows

Always provide:
1. Bias
2. Key liquidity
3. FVG zones
4. Long setup conditions
5. Short setup conditions
6. Entry zone
7. Invalidation
8. Targets

Rules for market analysis:
- Use if/then language.
- Do not claim certainty.
- Do not tell Jadin to enter immediately without confirmation.
- Never use read_file for CSV market analysis. Always use analyze_market_csv.
- If the user asks to analyze MNQ, MES, NQ, ES, or any futures chart and does not provide file names, use analyze_market_csv or analyze_tradingview with the requested symbol.
- Use analyze_tradingview when the user wants screenshot markings included.
- Use analyze_market_csv when the user wants pure data/structure analysis.
- When discussing FVGs, always include the timeframe.
- Prioritize HTF CSV zones first:
  1D > 4H > 1H.
- Use 15M/5M vision for live execution context.
- 1M is conditional execution confirmation only.
- Do not use VWAP.

General rules:
- When using web_search, include the source title and URL in your answer.
- Do not invent details beyond tool results.
- If the user asks for current, recent, latest, news, prices, schedules, or anything that may have changed recently, use web_search.
- If web_search is unavailable or cannot verify a current/news-like claim, say you cannot verify it live and frame the reasoning conditionally.
- If no tool is needed, respond normally.
- Do not explain tool usage.
- After receiving a Tool Result, respond normally to the user.
- Do not output TOOL: after a Tool Result.
"""


# -------------------------
# Request models
# -------------------------
class ChatRequest(BaseModel):
    message: str
    tool_mode: str = "auto"


class VisionChartEvaluationRequest(BaseModel):
    image_path: str
    symbol: str = "MES"
    timeframe: str = "15M"
    expected_context: dict | None = None
    debug: bool = False


class PresenceRequest(BaseModel):
    mode: str


class ScannerSettingsRequest(BaseModel):
    default_symbol: str | None = None
    scanner_enabled: bool | None = None


# -------------------------
# Utility helpers
# -------------------------
def detect_symbol(message: str, default: str = "ES") -> str:
    message_upper = message.upper()

    for candidate in ["MNQ", "MES", "NQ", "ES"]:
        if candidate in message_upper:
            return candidate

    return default


def build_prompt():
    messages = get_recent_messages(MAX_HISTORY_MESSAGES)

    history_text = "\n".join(
        [f"{role}: {content}" for role, content in messages]
    )

    return SYSTEM_MESSAGE + "\n\n" + history_text + "\nAssistant:"


# -------------------------
# Ollama helpers
# -------------------------
def call_ollama(prompt: str, stream: bool = False, timeout: int = 120):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": stream,
            "think": False,
        },
        timeout=timeout,
    )

    response.raise_for_status()
    return response


# -------------------------
# Tool parsing / execution
# -------------------------
def parse_tool_call(assistant_message: str):
    if "TOOL:" not in assistant_message:
        return None, {}

    raw = assistant_message.split("TOOL:", 1)[1].strip().splitlines()[0]
    parts = raw.split()

    if not parts:
        return None, {}

    tool_name = parts[0]
    args = {}

    for part in parts[1:]:
        if "=" in part:
            key, value = part.split("=", 1)
            args[key] = value

    return tool_name, args


def run_tool(tool_name: str, args: dict):
    if tool_name not in TOOLS:
        return {
            "success": False,
            "error": f"Unknown tool: {tool_name}",
        }

    return TOOLS[tool_name](**args)


def build_followup_prompt(base_prompt: str, tool_result):
    tool_message = (
        tool_result.get("message")
        if isinstance(tool_result, dict)
        else None
    )


def repair_incomplete_model_response(
    *,
    assistant_message: str,
    base_prompt: str,
    user_message: str,
    allow_short_response: bool = False,
) -> tuple[str, bool]:
    if not is_incomplete_response(
        assistant_message,
        user_message=user_message,
        allow_short_response=allow_short_response,
    ):
        return assistant_message, False

    repair_prompt = build_response_repair_prompt(
        base_prompt=base_prompt,
        user_message=user_message,
        bad_response=assistant_message,
    )

    try:
        response = call_ollama(
            prompt=repair_prompt,
            stream=False,
            timeout=120,
        )
        repaired_message = response.json().get("response", "").strip()
    except requests.exceptions.RequestException:
        return INCOMPLETE_RESPONSE_FALLBACK, True

    if is_incomplete_response(
        repaired_message,
        user_message=user_message,
        allow_short_response=allow_short_response,
    ):
        return INCOMPLETE_RESPONSE_FALLBACK, True

    return repaired_message, True

    return (
        base_prompt
        + f"\nTool Result: {tool_result}\n"
        + (
            f"Use this preformatted response as your answer:\n{tool_message}\n"
            if tool_message
            else "Use the Tool Result to answer the user normally. "
        )
        + "Do not call another tool. Do not output TOOL: again.\n"
        + "Assistant:"
    )


# -------------------------
# Health endpoint
# -------------------------
@app.get("/")
def health_check():
    return {"status": "backend running"}


@app.get("/presence")
def presence_status():
    current = get_presence()
    return {
        "success": True,
        "current": current,
        "updated_at": current.get("updated_at"),
        "modes": list_presence_modes(),
    }


@app.post("/presence")
def update_presence(request: PresenceRequest):
    try:
        current = set_presence(request.mode)
        return {
            "success": True,
            "current": current,
            "updated_at": current.get("updated_at"),
            "modes": list_presence_modes(),
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# -------------------------
# Mobile reminder / notification facade
# -------------------------
@app.get("/mobile/notifications", response_model=MobileNotificationCenter)
def get_mobile_notifications():
    return orbit_service.get_mobile_notification_center()


@app.post("/mobile/notifications", response_model=MobileNotification, status_code=201)
def create_mobile_notification(payload: MobileNotificationCreate):
    return orbit_service.create_mobile_notification(payload)


@app.post("/mobile/notifications/{notification_id}/ack", response_model=MobileNotification)
def ack_mobile_notification(notification_id: int):
    notification = orbit_service.acknowledge_mobile_notification(notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail=f"Notification {notification_id} not found.")
    return notification


@app.post("/mobile/notifications/{notification_id}/complete", response_model=MobileNotification)
def complete_mobile_notification(notification_id: int):
    notification = orbit_service.complete_mobile_notification(notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail=f"Notification {notification_id} not found.")
    return notification


@app.post("/mobile/notifications/{notification_id}/dismiss", response_model=MobileNotification)
def dismiss_mobile_notification(notification_id: int):
    notification = orbit_service.dismiss_mobile_notification(notification_id)
    if notification is None:
        raise HTTPException(status_code=404, detail=f"Notification {notification_id} not found.")
    return notification


@app.get("/mobile/reminders", response_model=list[MobileReminder])
def list_mobile_reminders(status: str | None = "pending"):
    return orbit_service.list_mobile_reminders(status=status)


@app.post("/mobile/reminders", response_model=MobileReminder, status_code=201)
def create_mobile_reminder(payload: MobileReminderCreate):
    return orbit_service.create_mobile_reminder(payload)


@app.post("/mobile/reminders/{reminder_id}/complete", response_model=MobileReminder)
def complete_mobile_reminder(reminder_id: int):
    reminder = orbit_service.complete_mobile_reminder(reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail=f"Reminder {reminder_id} not found.")
    return reminder


@app.post("/mobile/reminders/{reminder_id}/dismiss", response_model=MobileReminder)
def dismiss_mobile_reminder(reminder_id: int):
    reminder = orbit_service.dismiss_mobile_reminder(reminder_id)
    if reminder is None:
        raise HTTPException(status_code=404, detail=f"Reminder {reminder_id} not found.")
    return reminder


@app.post("/mobile/schedule-blocks/{schedule_block_id}/done", response_model=ScheduleBlock)
def complete_mobile_schedule_block(schedule_block_id: int):
    block = orbit_service.complete_schedule_block_for_mobile(schedule_block_id)
    if block is None:
        raise HTTPException(status_code=404, detail=f"Schedule block {schedule_block_id} not found.")
    return block


@app.post("/mobile/schedule-blocks/{schedule_block_id}/start", response_model=ScheduleBlock)
def start_mobile_schedule_block(schedule_block_id: int):
    try:
        return orbit_service.start_schedule_block_for_mobile(schedule_block_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/mobile/schedule-blocks/{schedule_block_id}/roll-later", response_model=ScheduleBlock)
def roll_mobile_schedule_block_later(schedule_block_id: int):
    try:
        return orbit_service.roll_schedule_block_later_for_mobile(schedule_block_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/mobile/schedule-blocks/{schedule_block_id}/roll-tomorrow", response_model=ScheduleBlock)
def roll_mobile_schedule_block_tomorrow(schedule_block_id: int):
    try:
        return orbit_service.roll_schedule_block_tomorrow_for_mobile(schedule_block_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# -------------------------
# Chat endpoint
# -------------------------
@app.post("/chat")
def chat(request: ChatRequest):
    try:
        save_message("User", request.message)

        # -------------------------
        # Manual mode: CSV market analysis
        # -------------------------
        if request.tool_mode == "market_csv":
            symbol = detect_symbol(request.message, default="ES")

            tool_result = TOOLS["analyze_market_csv"](symbol=symbol)

            log_tool(
                "analyze_market_csv",
                str({"symbol": symbol}),
                str(tool_result),
            )

            assistant_message = tool_result.get("message", str(tool_result))
            save_message("Assistant", assistant_message)

            messages = get_recent_messages(MAX_HISTORY_MESSAGES)

            return {
                "success": True,
                "model": "tool:analyze_market_csv",
                "message": assistant_message,
                "history_length": len(messages),
            }

        # -------------------------
        # Manual mode: refresh CSV exports
        # -------------------------
        if request.tool_mode == "refresh_market_csvs":
            symbol = detect_symbol(request.message)

            tool_result = TOOLS["refresh_market_csvs"](symbol=symbol)

            log_tool(
                "refresh_market_csvs",
                str({"symbol": symbol}),
                str(tool_result),
            )

            assistant_message = tool_result.get("message", str(tool_result))
            save_message("Assistant", assistant_message)

            messages = get_recent_messages(MAX_HISTORY_MESSAGES)

            return {
                "success": True,
                "model": "tool:refresh_market_csvs",
                "message": assistant_message,
                "history_length": len(messages),
            }

        # -------------------------
        # Manual mode: TradingView screenshot + CSV analysis
        # -------------------------
        if request.tool_mode == "analyze_tradingview":
            symbol = detect_symbol(request.message)

            tool_result = TOOLS["analyze_tradingview"](
                symbol=symbol,
                prompt=request.message,
            )

            log_tool(
                "analyze_tradingview",
                str({"symbol": symbol, "prompt": request.message}),
                str(tool_result),
            )

            assistant_message = tool_result.get("message", str(tool_result))
            save_message("Assistant", assistant_message)

            messages = get_recent_messages(MAX_HISTORY_MESSAGES)

            return {
                "success": True,
                "model": "pipeline:vision+csv+narrator",
                "message": assistant_message,
                "history_length": len(messages),
            }

        # -------------------------
        # Auto mode: deterministic Command Center intent routing
        # -------------------------
        intent_response = route_chat_intent(request.message)
        if intent_response is not None:
            assistant_message = intent_response["message"]
            save_message("Assistant", assistant_message)

            messages = get_recent_messages(MAX_HISTORY_MESSAGES)

            return {
                "success": True,
                "model": intent_response["model"],
                "message": assistant_message,
                "data": intent_response.get("data", {}),
                "route": intent_response.get("data", {}).get("route", "deterministic_intent"),
                "used_model": False,
                "history_length": len(messages),
            }

        # -------------------------
        # Auto mode: ask text model, then run tool if requested
        # -------------------------
        prompt = build_prompt()

        response = call_ollama(
            prompt=prompt,
            stream=False,
            timeout=120,
        )

        data = response.json()
        assistant_message = data.get("response", "").strip()
        response_quality_repaired = False

        tool_name, args = parse_tool_call(assistant_message)

        if tool_name:
            tool_result = run_tool(tool_name, args)

            log_tool(tool_name, str(args), str(tool_result))
            save_message("Tool", f"{tool_name}: {tool_result}")

            followup_prompt = build_followup_prompt(
                base_prompt=prompt,
                tool_result=tool_result,
            )

            response = call_ollama(
                prompt=followup_prompt,
                stream=False,
                timeout=120,
            )

            data = response.json()
            assistant_message = data.get("response", "").strip()

            assistant_message, response_quality_repaired = repair_incomplete_model_response(
                assistant_message=assistant_message,
                base_prompt=followup_prompt,
                user_message=request.message,
            )
        else:
            assistant_message, response_quality_repaired = repair_incomplete_model_response(
                assistant_message=assistant_message,
                base_prompt=prompt,
                user_message=request.message,
            )

        save_message("Assistant", assistant_message)

        messages = get_recent_messages(MAX_HISTORY_MESSAGES)

        return {
            "success": True,
            "model": OLLAMA_MODEL,
            "message": assistant_message,
            "response_quality_repaired": response_quality_repaired,
            "history_length": len(messages),
        }

    except requests.exceptions.RequestException as e:
        print("OLLAMA ERROR:", e)
        raise HTTPException(status_code=500, detail=f"Ollama request failed: {e}")

    except Exception as e:
        print("CHAT ERROR:", repr(e))
        raise HTTPException(status_code=500, detail=f"Chat failed: {e}")


# -------------------------
# Streaming chat endpoint
# -------------------------
@app.post("/chat/stream")
def chat_stream(request: ChatRequest):
    def generate():
        try:
            save_message("User", request.message)

            prompt = build_prompt()

            with requests.post(
                OLLAMA_URL,
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": True,
                    "think": False,
                },
                stream=True,
                timeout=300,
            ) as response:
                response.raise_for_status()

                full_response = ""

                for line in response.iter_lines():
                    if line:
                        chunk = json.loads(line.decode("utf-8"))
                        token = chunk.get("response", "")

                        full_response += token
                        yield token

                assistant_message = full_response.strip()
                if is_incomplete_response(
                    assistant_message,
                    user_message=request.message,
                ):
                    repaired_message, _ = repair_incomplete_model_response(
                        assistant_message=assistant_message,
                        base_prompt=prompt,
                        user_message=request.message,
                    )
                    save_message("Assistant", repaired_message)
                    yield "\n\n" + repaired_message
                else:
                    save_message("Assistant", assistant_message)

        except requests.exceptions.RequestException as e:
            yield f"\n[ERROR] Ollama request failed: {e}"

    return StreamingResponse(generate(), media_type="text/plain")


# -------------------------
# Image / chart analysis endpoint
# -------------------------
@app.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    prompt: str = Form("Analyze this chart using Jadin's Liquidity Narrative Continuation model."),
    debug: bool = Form(False),
):
    try:
        image_bytes = await file.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        symbol = detect_symbol(prompt, default="ES")

        tool_result = analyze_uploaded_chart_image(
            image_base64=image_base64,
            prompt=prompt,
            symbol=symbol,
        )

        message = tool_result.get("message", str(tool_result))
        visual_extraction = tool_result.get("visual_extraction", {})
        csv_analysis = tool_result.get("csv_analysis", {})

        save_message("User", f"[Image uploaded] {file.filename}: {prompt}")
        save_message("Assistant", message)

        compact_response = {
            "success": tool_result.get("success", False),
            "model": "pipeline:vision+csv+deterministic",
            "symbol": symbol,
            "message": message,
            "vision_success": visual_extraction.get("success", False),
            "vision_error": visual_extraction.get("error"),
            "csv_success": csv_analysis.get("success", False),
        }

        if debug:
            compact_response["result"] = tool_result

        return compact_response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {e}")


@app.post("/vision/evaluate-chart")
def evaluate_chart_vision(request: VisionChartEvaluationRequest):
    try:
        image_path = request.image_path.strip()
        if not image_path:
            raise HTTPException(status_code=400, detail="image_path is required.")
        if not os.path.exists(image_path):
            raise HTTPException(status_code=404, detail=f"Screenshot not found: {image_path}")

        return evaluate_vision_models_for_chart(
            image_path=image_path,
            symbol=normalize_scanner_symbol(request.symbol),
            timeframe=request.timeframe.upper(),
            expected_context=request.expected_context,
            debug=request.debug,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Vision model evaluation failed: {e}")


# -------------------------
# Scan endpoints
# -------------------------
@app.get("/scanner/settings")
def scanner_settings():
    current = get_scanner_settings()
    return {
        "success": True,
        "default_symbol": current.get("default_symbol"),
        "scanner_enabled": current.get("scanner_enabled", True),
        "supported_symbols": current.get("supported_symbols"),
        "updated_at": current.get("updated_at"),
        "settings": current,
    }


@app.post("/scanner/settings")
def update_scanner_settings(request: ScannerSettingsRequest):
    try:
        current = set_scanner_settings(
            default_symbol=request.default_symbol,
            scanner_enabled=request.scanner_enabled,
        )
        return {
            "success": True,
            "default_symbol": current.get("default_symbol"),
            "scanner_enabled": current.get("scanner_enabled", True),
            "supported_symbols": current.get("supported_symbols"),
            "updated_at": current.get("updated_at"),
            "settings": current,
        }
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.post("/scan/force")
def force_scan(
    timeframe: str | None = None,
    multi_timeframe: bool = True,
    symbol: str | None = None,
):
    from scheduled_scan import SCAN_TIMEFRAME, run_scan

    try:
        record = run_scan(
            force=True,
            timeframe=timeframe or SCAN_TIMEFRAME,
            multi_timeframe=multi_timeframe,
            symbol=symbol,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not record:
        return {
            "success": False,
            "message": "No scan record returned.",
        }

    return record


@app.get("/scan/latest")
def latest_scan(symbol: str | None = None):
    from scheduled_scan import SCAN_HISTORY_PATH, is_valid_market_scan, load_last_successful_scan, load_latest_scan

    try:
        scan_symbol = normalize_scanner_symbol(
            symbol or str(get_scanner_settings().get("default_symbol") or "")
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not SCAN_HISTORY_PATH.exists():
        return {
            "success": False,
            "symbol": scan_symbol,
            "message": "No scan history found yet.",
            "record": None,
            "latest_attempt": None,
            "latest_successful_market_scan": None,
            "last_valid_record": None,
            "current_attempt_valid_market_state": False,
            "system_health": None,
        }

    latest = load_latest_scan(symbol=scan_symbol)
    latest_successful = load_last_successful_scan(symbol=scan_symbol)

    if not latest:
        return {
            "success": False,
            "symbol": scan_symbol,
            "message": "No scan records found for symbol.",
            "record": None,
            "latest_attempt": None,
            "latest_successful_market_scan": None,
            "last_valid_record": None,
            "current_attempt_valid_market_state": False,
            "system_health": None,
        }

    record = latest if is_valid_market_scan(latest) else latest_successful

    return {
        "success": True,
        "symbol": scan_symbol,
        "record": record,
        "latest_attempt": latest,
        "latest_successful_market_scan": latest_successful,
        "last_valid_record": latest_successful,
        "current_attempt_valid_market_state": is_valid_market_scan(latest),
        "system_health": (latest or {}).get("system_health"),
    }


@app.get("/scan/status")
def scan_status():
    from scheduled_scan import get_scanner_runtime_status

    return get_scanner_runtime_status()


# -------------------------
# CSV refresh endpoints
# -------------------------
@app.get("/csv-refresh/status")
def csv_refresh_status():
    from csv_refresh import get_csv_refresh_status

    return get_csv_refresh_status()


@app.post("/csv-refresh/force")
def force_csv_refresh(symbol: str | None = None):
    from csv_refresh import run_csv_refresh

    try:
        return run_csv_refresh(force=True, symbol=symbol)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


# -------------------------
# Memory / history endpoints
# -------------------------
@app.post("/reset")
def reset_memory():
    clear_messages()

    return {
        "success": True,
        "message": "Conversation memory reset.",
        "history_length": 0,
    }


@app.get("/history")
def chat_history():
    messages = get_recent_messages(MAX_HISTORY_MESSAGES)

    return {
        "success": True,
        "history": [
            {"role": role, "content": content}
            for role, content in messages
        ],
        "history_length": len(messages),
    }


# -------------------------
# Tool log endpoint
# -------------------------
@app.get("/tool-logs")
def get_tool_logs():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT tool_name, arguments, result, created_at FROM tool_logs ORDER BY id DESC LIMIT 20"
    )

    rows = cursor.fetchall()
    conn.close()

    return {
        "success": True,
        "logs": [
            {
                "tool": row[0],
                "arguments": row[1],
                "result": row[2],
                "created_at": row[3],
            }
            for row in rows
        ],
    }

# -------------------------
# TTS endpoints
# -------------------------
class TTSRequest(BaseModel):
    text: str


def _speak_text(text: str) -> str:
    from tts import speak_text

    return speak_text(text)


@app.get("/tts/voices")
def tts_voices():
    from tts import list_macos_voices

    try:
        voices = list_macos_voices()
    except Exception as e:
        return {
            "success": False,
            "voices": [],
            "error": f"Could not load macOS voices: {type(e).__name__}",
        }
    return {
        "success": True,
        "voices": voices,
    }


@app.get("/tts/config")
def tts_config():
    from tts import get_tts_config

    return {
        "success": True,
        **get_tts_config(),
    }


@app.post("/tts/say")
def tts_say(request: TTSRequest):
    try:
        from tts import speak_text_with_metadata

        speech = speak_text_with_metadata(request.text)
    except ValueError as e:
        return {
            "success": False,
            "message": str(e),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")
    else:
        return {
            "success": True,
            "message": "TTS started.",
            "original_text": speech["original_text"],
            "formatted_text": speech["formatted_text"],
            "spoken_text": speech["spoken_text"],
            "voice": speech["voice"],
            "rate": speech["rate"],
        }


@app.post("/notify/test-tts")
def notify_test_tts(message: str | None = None):
    """Manual-only TTS notification test; bypasses scan alert eligibility."""
    text = (message or "Helix TTS test is online.").strip()

    try:
        spoken_text = _speak_text(text)
    except Exception as e:
        return {
            "success": False,
            "error": f"TTS failed: {e}",
        }

    return {
        "success": True,
        "message": "Manual TTS notification test started.",
        "original_text": text,
        "spoken_text": spoken_text,
    }


@app.post("/notify/test-imessage")
def notify_test_imessage(message: str | None = None, recipient: str | None = None):
    """Manual-only iMessage notification test; bypasses scan alert eligibility."""
    from imessage_bridge import send_imessage

    text = (message or "Helix iMessage test is online.").strip()
    recipient_config = get_default_imessage_recipient(recipient)
    recipient_used = recipient_config["recipient"]

    if not text:
        text = "Helix iMessage test is online."

    if not recipient_used:
        return {
            "success": False,
            "error": "No iMessage recipient provided or configured.",
        }

    try:
        send_imessage(recipient_used, text)
    except Exception as e:
        return {
            "success": False,
            "recipient": recipient_config["masked_recipient"],
            "recipient_source": recipient_config["source"],
            "error": f"iMessage test failed: {type(e).__name__}",
        }

    return {
        "success": True,
        "message": "Manual iMessage notification test sent.",
        "recipient": recipient_config["masked_recipient"],
        "recipient_source": recipient_config["source"],
    }


@app.get("/notify/config")
def get_notify_config():
    return get_notification_config()


@app.post("/notify/test-all")
def notify_test_all(message: str | None = None, recipient: str | None = None):
    """Manual-only notification test; sends iMessage and TTS without scan eligibility."""
    from imessage_bridge import send_imessage

    text = (message or "Helix notification test is online.").strip()
    if not text:
        text = "Helix notification test is online."

    recipient_config = get_default_imessage_recipient(recipient)
    imessage_sent = False
    tts_spoken = False
    errors = []

    if recipient_config["recipient"]:
        try:
            send_imessage(recipient_config["recipient"], text)
            imessage_sent = True
        except Exception as e:
            errors.append(f"iMessage test failed: {type(e).__name__}")
    else:
        errors.append("No iMessage recipient provided or configured.")

    try:
        _speak_text(text)
        tts_spoken = True
    except Exception as e:
        errors.append(f"TTS failed: {e}")

    return {
        "success": imessage_sent and tts_spoken,
        "imessage_sent": imessage_sent,
        "tts_spoken": tts_spoken,
        "recipient": recipient_config["masked_recipient"],
        "recipient_source": recipient_config["source"],
        "errors": errors,
    }
