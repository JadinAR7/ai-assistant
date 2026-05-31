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
def force_scan():
    from scheduled_scan import run_scan

    record = run_scan(force=True)

    if not record:
        return {
            "success": False,
            "message": "No scan record returned.",
        }

    return record


@app.get("/scan/latest")
def latest_scan():
    from scheduled_scan import SCAN_HISTORY_PATH, SYMBOL

    if not SCAN_HISTORY_PATH.exists():
        return {
            "success": False,
            "message": "No scan history found yet.",
            "record": None,
        }

    latest = None

    with SCAN_HISTORY_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            if record.get("symbol") != SYMBOL:
                continue

            latest = record

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
    from datetime import datetime
    from scheduled_scan import TIMEZONE, get_active_sessions, should_scan_now, SYMBOL

    now = datetime.now(TIMEZONE)
    sessions = get_active_sessions(now)

    return {
        "success": True,
        "symbol": SYMBOL,
        "timestamp": now.isoformat(),
        "timezone": "America/Denver",
        "active_sessions": sessions,
        "should_scan_now": should_scan_now(now),
    }


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
# TTS endpoint
# -------------------------
class TTSRequest(BaseModel):
    text: str


@app.post("/tts/say")
def tts_say(request: TTSRequest):
    import subprocess

    text = request.text.strip()

    if not text:
        return {
            "success": False,
            "message": "No text provided.",
        }

    # Keep it reasonable so the Mac doesn't start reading a dissertation.
    if len(text) > 500:
        text = text[:500] + "..."

    try:
        subprocess.Popen(
            ["say", text],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        return {
            "success": True,
            "message": "TTS started.",
            "spoken_text": text,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS failed: {e}")
