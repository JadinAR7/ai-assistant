import os
import json
import requests
import base64
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware

from tools import TOOLS, analyze_uploaded_chart_image
from database import get_connection, log_tool
from database import init_db, save_message, get_recent_messages, clear_messages
from notification_config import get_default_imessage_recipient, get_notification_config
from orbit.database import init_orbit_db
from orbit.routes import router as orbit_router


# -------------------------
# Environment / app setup
# -------------------------
load_dotenv()

app = FastAPI(title="Jadin AI Assistant Backend")
init_db()
init_orbit_db()
app.include_router(orbit_router)


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

Rules:
- Use create_orbit_task when Jadin says "add task", "create task", "save task", "capture task", or "add to Orbit inbox".
- Use underscores instead of spaces in title and description values.
- If the task belongs to an existing goal, include goal_id.
- If no goal is named, omit goal_id and the task will go to the Orbit Inbox goal.

Example:
User: Add task: review Orbit inbox tonight.
TOOL: create_orbit_task title=review_Orbit_inbox_tonight

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

- refresh_market_csvs: tries to export fresh TradingView CSVs for 1D, 4H, 1H, 15M, and 1M

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

- analyze_market_csv: analyzes TradingView CSV data using Jadin's ICT-based trading model

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
- CSV data is the source of truth for current price, FVGs, levels, targets, and structure.
- Screenshot/vision is only for visible user markings, drawn boxes, labels, and chart context.
- If CSV and screenshot disagree numerically, trust CSV.
- The vision model should not be treated as the final analyst.
- The text model writes the final narrative after CSV + vision are merged.

When using analyze_market_csv or analyze_tradingview, explain the market using Jadin's ICT-based trading model.

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
- Prioritize higher timeframe zones first:
  1D > 4H > 1H > 15M > 1M.
- 1M is for execution only.
- Do not use VWAP.

General rules:
- When using web_search, include the source title and URL in your answer.
- Do not invent details beyond tool results.
- If the user asks for current, recent, latest, news, prices, schedules, or anything that may have changed recently, use web_search.
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

        save_message("Assistant", assistant_message)

        messages = get_recent_messages(MAX_HISTORY_MESSAGES)

        return {
            "success": True,
            "model": OLLAMA_MODEL,
            "message": assistant_message,
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

                save_message("Assistant", full_response.strip())

        except requests.exceptions.RequestException as e:
            yield f"\n[ERROR] Ollama request failed: {e}"

    return StreamingResponse(generate(), media_type="text/plain")


# -------------------------
# Image / chart analysis endpoint
# -------------------------
@app.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    prompt: str = Form("Analyze this chart using Jadin's ICT trading model."),
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


# -------------------------
# Scan endpoints
# -------------------------
@app.post("/scan/force")
def force_scan(timeframe: str | None = None, multi_timeframe: bool = True):
    from scheduled_scan import SCAN_TIMEFRAME, run_scan

    record = run_scan(
        force=True,
        timeframe=timeframe or SCAN_TIMEFRAME,
        multi_timeframe=multi_timeframe,
    )

    if not record:
        return {
            "success": False,
            "message": "No scan record returned.",
        }

    return record


@app.get("/scan/latest")
def latest_scan():
    from scheduled_scan import SCAN_HISTORY_PATH, load_latest_scan

    if not SCAN_HISTORY_PATH.exists():
        return {
            "success": False,
            "message": "No scan history found yet.",
            "record": None,
        }

    latest = load_latest_scan()

    if not latest:
        return {
            "success": False,
            "message": "No scan records found for symbol.",
            "record": None,
        }

    return {
        "success": True,
        "record": latest,
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
def force_csv_refresh():
    from csv_refresh import run_csv_refresh

    return run_csv_refresh(force=True)


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
    import subprocess

    spoken_text = text.strip()

    if not spoken_text:
        raise ValueError("No text provided.")

    # Keep it reasonable so the Mac doesn't start reading a dissertation.
    if len(spoken_text) > 500:
        spoken_text = spoken_text[:500] + "..."

    subprocess.Popen(
        ["say", spoken_text],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return spoken_text


@app.post("/tts/say")
def tts_say(request: TTSRequest):
    try:
        spoken_text = _speak_text(request.text)
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
            "spoken_text": spoken_text,
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
