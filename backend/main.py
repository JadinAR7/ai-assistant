import os
import json
import requests
import base64
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from tools import TOOLS
from database import get_connection, log_tool
from database import init_db, save_message, get_recent_messages, clear_messages

load_dotenv()

app = FastAPI(title="Jadin AI Assistant Backend")
init_db()

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

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
MAX_HISTORY_MESSAGES = 20

SYSTEM_MESSAGE = """
You are Jadin's AI assistant.

Your name is "Helix", and you are a powerful AI designed to assist Jadin with a wide range of tasks, including trading analysis, general questions, and more.

You have access to tools.

If a tool is needed, respond EXACTLY like this:
TOOL: tool_name

Tool format:
TOOL: tool_name key=value

Use underscores instead of spaces in tool argument values.

Example:
TOOL: echo text=hello_world

Available tools:

- get_time: returns the current system time

- echo: repeats provided text

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

- analyze_tradingview: captures the live TradingView chart and analyzes it using the vision model

Supported symbols:
- MNQ
- MES
- NQ
- ES

Examples:
TOOL: analyze_tradingview symbol=MNQ
TOOL: analyze_tradingview symbol=ES

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

When using analyze_market_csv, explain the market using Jadin's ICT-based trading model.

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
- If the user asks to analyze MNQ, MES, NQ, ES, or any futures chart and does not provide file names, use analyze_market_csv with the requested symbol.
- When discussing FVGs, always include the timeframe.
- Prioritize higher timeframe zones first:
  1D > 4H > 1H > 15M > 1M.
- 1M is for execution only.

General rules:
- When using web_search, include the source title and URL in your answer.
- Do not invent details beyond tool results.
- If the user asks for current, recent, latest, news, prices, schedules, or anything that may have changed recently, use web_search.
- If no tool is needed, respond normally.
- Do not explain tool usage.
- After receiving a Tool Result, respond normally to the user.
- Do not output TOOL: after a Tool Result.
"""


class ChatRequest(BaseModel):
    message: str
    tool_mode: str = "auto"


def build_prompt():
    messages = get_recent_messages(MAX_HISTORY_MESSAGES)

    history_text = "\n".join(
        [f"{role}: {content}" for role, content in messages]
    )

    return SYSTEM_MESSAGE + "\n\n" + history_text + "\nAssistant:"


@app.get("/")
def health_check():
    return {"status": "backend running"}


@app.post("/chat")
def chat(request: ChatRequest):
    try:
        save_message("User", request.message)

        if request.tool_mode == "market_csv":
            symbol = "MNQ"

            message_upper = request.message.upper()
            for candidate in ["MNQ", "MES", "NQ", "ES"]:
                if candidate in message_upper:
                    symbol = candidate
                    break

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

        prompt = build_prompt()

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "think": False,
            },
            timeout=120,
        )

        response.raise_for_status()
        data = response.json()

        assistant_message = data.get("response", "").strip()

        if "TOOL:" in assistant_message:
            raw = assistant_message.split("TOOL:", 1)[1].strip().splitlines()[0]

            parts = raw.split()
            tool_name = parts[0]

            args = {}

            for part in parts[1:]:
                if "=" in part:
                    key, value = part.split("=", 1)
                    args[key] = value

            if tool_name in TOOLS:
                tool_result = TOOLS[tool_name](**args)
                log_tool(tool_name, str(args), str(tool_result))
                save_message("Tool", f"{tool_name}: {tool_result}")

                tool_message = (
                    tool_result.get("message")
                    if isinstance(tool_result, dict)
                    else None
                )

                followup_prompt = (
                    prompt
                    + f"\nTool Result: {tool_result}\n"
                    + (
                        f"Use this preformatted response as your answer:\n{tool_message}\n"
                        if tool_message
                        else "Use the Tool Result to answer the user normally. "
                    )
                    + "Do not call another tool. Do not output TOOL: again.\n"
                    + "Assistant:"
                )

                response = requests.post(
                    OLLAMA_URL,
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": followup_prompt,
                        "stream": False,
                        "think": False,
                    },
                    timeout=120,
                )

                response.raise_for_status()
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


@app.post("/analyze-image")
async def analyze_image(
    file: UploadFile = File(...),
    prompt: str = Form("Analyze this chart using Jadin's ICT trading model."),
):
    try:
        image_bytes = await file.read()
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        vision_prompt = f"""
        You are Jadin's trading assistant.

        Analyze the uploaded TradingView screenshot using Jadin's ICT-based trading model.

        Jadin's model:
        - Daily / 4H / 1H = higher-timeframe context
        - 15M = setup and refinement
        - 1M = execution trigger
        - Do not use VWAP
        - Do not use 5M unless Jadin explicitly asks
        - Do not claim certainty

        Critical visual rules:
        - User-drawn boxes, rectangles, horizontal lines, arrows, labels, and shaded zones are HIGH PRIORITY.
        - Treat visible white/colored rectangles as marked FVGs, supply/demand, or reaction zones.
        - If the user drew a box, mention it even if the text label is unclear.
        - Do not ignore drawn FVG boxes.
        - Do not invent exact levels unless the price scale makes them readable.
        - If exact box boundaries are not readable, describe the zone approximately using nearby visible price labels.
        - Only use levels visible in the screenshot.
        - If a level or timeframe is not visible, say it is missing.
        - Do not invent PDH/PDL/session highs/lows unless labeled or obvious.
        - Do not call 1M a higher timeframe.
        - MSS means Market Structure Shift.
        - BOS means Break of Structure.

        TradingView UI rules:
        - Ignore bid/ask boxes labeled BUY and SELL. Do not treat them as trade orders or strategy signals.
        - Do not treat the watchlist, right sidebar, news panel, or order buttons as chart analysis.
        - Price labels on the right axis are reference prices only. Use them to estimate levels, not as independent signals.
        - If a label says PDH, PDL, PWH, PWL, New York High/Low, London High/Low, Asia High/Low, 1H FVG, 4H FVG, or 15M FVG, preserve that label exactly.
        - If a labeled level is above current price, treat it as liquidity/resistance above.
        - If a labeled level is below current price, treat it as liquidity/support below.
        - Never call bid/ask boxes “buy order” or “sell order.”

        Classification rules:
        - A horizontal line with a label like PDH, PDL, PWH, PWL, New York High/Low, Asia High/Low, or London High/Low is NOT an FVG.
        - Classify those as liquidity/reference levels.
        - Only classify something as an FVG if it is explicitly labeled FVG or drawn as a box/rectangle around an imbalance area.
        - Do not list every price label as an FVG.

        Structural interpretation rules:
        - If price shows strong displacement followed by consolidation above bullish FVGs, bias is bullish unless those FVGs fail.
        - If multiple bullish FVGs are stacked beneath price, treat them as layered support.
        - If price is consolidating inside the highest bullish FVG after a strong impulse, interpret this as bullish continuation until invalidated.
        - If price accepts below the highest bullish FVG, shift focus to the next lower bullish FVG.
        - If price rejects from a bearish FVG and fails to reclaim it, bias is bearish.

        Zone priority rules:
        1. User-labeled FVGs and marked boxes
        2. PDH, PDL, PWH, PWL
        3. Session highs/lows
        4. Higher-timeframe FVGs
        5. Lower-timeframe execution zones

        Trade plan rules:
        - Always identify the active zone currently interacting with price.
        - Always identify the next backup zone if the active zone fails.
        - Always state what confirms continuation.
        - Always state what invalidates the setup.
        - Use Jadin's terminology: sweep -> reclaim -> MSS/BOS -> BRTC.

        Response format:

        ## Chart Read
        - Visible timeframe:
        - Current price area:
        - Immediate bias:

        ## User-Marked Zones
        - List every visible drawn box/zone.
        - Estimate the zone using visible price scale if needed.
        - State the likely role: FVG, reaction zone, liquidity, support/resistance, or unclear.

        ## Visible Levels To Mark
        - List visible horizontal levels and labeled zones only.

        ## FVG / Imbalance Read
        - Prioritize user-marked FVG boxes first.
        - Then mention any obvious unmarked imbalance.
        - If no clear FVG is visible, say so.

        ## Liquidity
        - Liquidity above:
        - Liquidity below:

        ## Bullish Plan
        - If/then conditions.
        - Require sweep/reclaim/MSS/BOS/BRTC confirmation.

        ## Bearish Plan
        - If/then conditions.
        - Explain failure scenario.

        ## Invalidation
        - What invalidates the long idea.
        - What invalidates the short idea.

        ## Missing Context
        - State what cannot be confirmed from the screenshot alone.

        ## Bottom Line
        - One concise trading takeaway.

        User question:
        {prompt}
        """

        response = requests.post(
            os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate"),
            json={
                "model": os.getenv("VISION_MODEL", "qwen2.5vl:7b"),
                "prompt": vision_prompt,
                "images": [image_base64],
                "stream": False,
                "think": False,
            },
            timeout=180,
        )

        response.raise_for_status()
        data = response.json()

        message = data.get("response", "").strip()

        save_message("User", f"[Image uploaded] {file.filename}: {prompt}")
        save_message("Assistant", message)

        return {
            "success": True,
            "model": os.getenv("VISION_MODEL", "qwen2.5vl:7b"),
            "message": message,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {e}")


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