import os
import json
import requests
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
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

You have access to tools.

If a tool is needed, respond EXACTLY like this:
TOOL: tool_name

Available tools:
- get_time: returns the current system time
- echo: repeats provided text

Tool format:
TOOL: tool_name key=value

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
- write_file: writes content to a file

Examples:
TOOL: read_file path=main.py
TOOL: write_file path=test.txt content=hello_world

- open_url: opens a webpage and returns title/body text

Example:
TOOL: open_url url=https://example.com

- extract_links: extracts links from a webpage

Example:
TOOL: extract_links url=https://example.com

- create_reminder: creates a real macOS Reminder

Reminder rules:
If the user asks to remind them, schedule something, or create a reminder, you MUST use create_reminder.
Never claim a reminder was created unless Tool Result success is True.

Example:
TOOL: create_reminder title=Test_Reminder reminder_time=Friday_May_9_2026_8:00_PM

- web_search: searches the web using Brave Search

Example:
TOOL: web_search query=latest_cybersecurity_news

When using analyze_market_csv, explain the market using Jadin's ICT-based trading model.

Analyze:
- Higher-timeframe bias
- Fair Value Gaps (FVGs)
- Break of Structure (BOS) and Market Structure Shift (MSS)
- Break-Retest-Continue (BRTC)
- Liquidity draws:
  - Previous Day High (PDH)
  - Previous Day Low (PDL)
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

Use if/then language.
Do not claim certainty.
Do not tell Jadin to enter immediately without confirmation.
Never use read_file for CSV market analysis. Always use analyze_market_csv.

Example:
Example:
TOOL: analyze_market_csv htf=MNQ_1H.csv mtf=MNQ_15M.csv ltf=MNQ_1M.csv symbol=MNQ

When market analysis requires multiple timeframes, always provide htf, mtf, and ltf arguments.
When using web_search, include the source title and URL in your answer.
Do not invent details beyond the search results.
If the user asks for current, recent, latest, news, prices, schedules, or anything that may have changed recently, use web_search.
If no tool is needed, respond normally.
Do not explain tool usage.

Important:
Use underscores instead of spaces in tool argument values.
After receiving a Tool Result, respond normally to the user.
Do not output TOOL: after a Tool Result.
"""


class ChatRequest(BaseModel):
    message: str


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

                followup_prompt = (
                    prompt
                    + f"\nTool Result: {tool_result}\n"
                    + "Use the Tool Result to answer the user normally. "
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
        raise HTTPException(status_code=500, detail=f"Ollama request failed: {e}")


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
                timeout=120,
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