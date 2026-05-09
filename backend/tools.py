from datetime import datetime
import subprocess
import os
from playwright.sync_api import sync_playwright
import requests
from dotenv import load_dotenv
import pandas as pd

load_dotenv()

BASE_DIR = os.path.abspath(".")



# Tool functions

# safe_path ensures that the provided path is within the BASE_DIR to prevent directory traversal attacks. It raises an error if the path is outside the allowed directory.
def safe_path(path: str):
    full_path = os.path.abspath(os.path.join(BASE_DIR, path))
    
    if not full_path.startswith(BASE_DIR):
        raise ValueError("Access denied: outside base directory")
    
    return full_path

# read_file reads the content of a file at the given path, ensuring that the path is safe. It returns a dictionary with the success status, the path, and the content (truncated to 4000 characters). If an error occurs, it returns a dictionary with the success status and the error message.
def read_file(path: str = ""):
    try:
        full_path = safe_path(path)

        with open(full_path, "r") as f:
            content = f.read()

        return {
            "success": True,
            "path": path,
            "content": content[:4000],
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

# write_file writes the provided content to a file at the given path, ensuring that the path is safe. It returns a dictionary with the success status and the path if successful, or an error message if an exception occurs. 
def write_file(path: str = "", content: str = "", mode: str = "w"):
    try:
        full_path = safe_path(path)

        with open(full_path, mode) as f:
            f.write(content)

        return {
            "success": True,
            "path": path,
            "mode": mode,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }

# get time returns the current date and time as a string in the format "YYYY-MM-DD HH:MM:SS". It returns a dictionary with the success status and the time string.
def get_time():
    return {
        "success": True,
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }


def echo(text: str = ""):
    return {
        "success": True,
        "echo": text,
    }

# allows running a predefined set of safe commands on the server. It checks if the command is in the allowed list, executes it, and returns the output, error, and return code. If the command is not allowed or if it times out, it returns an appropriate error message.
ALLOWED_COMMANDS = {
    "pwd": ["pwd"],
    "list_files": ["ls", "-la"],
    "disk_usage": ["df", "-h"],
}

MAX_OUTPUT_CHARS = 4000

def run_command(command: str = ""):
    if command not in ALLOWED_COMMANDS:
        return {
            "success": False,
            "error": f"Command not allowed: {command}",
        }

    try:
        result = subprocess.run(
            ALLOWED_COMMANDS[command],
            capture_output=True,
            text=True,
            timeout=10,
        )

        stdout = result.stdout[:MAX_OUTPUT_CHARS]
        stderr = result.stderr[:MAX_OUTPUT_CHARS]

        return {
            "success": True,
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "returncode": result.returncode,
            "truncated": (
                len(result.stdout) > MAX_OUTPUT_CHARS
                or len(result.stderr) > MAX_OUTPUT_CHARS
            ),
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": "Command timed out.",
        }


def open_url(url: str = ""):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded")

            title = page.title()
            text = page.locator("body").inner_text()[:4000]

            browser.close()

            return {
                "success": True,
                "url": url,
                "title": title,
                "text": text,
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
    

def extract_links(url: str = ""):
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded")

            links = page.locator("a").evaluate_all("""
                elements => elements.map(a => ({
                    text: a.innerText,
                    href: a.href
                }))
            """)

            browser.close()

            return {
                "success": True,
                "url": url,
                "links": links[:50],
            }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
    
def create_reminder(title: str = "", reminder_time: str = ""):
    try:

        title = title.replace("_", " ")
        reminder_time = reminder_time.replace("_", " ")

        if reminder_time:
            script = f'''
        tell application "Reminders"
            tell default list
                make new reminder with properties {{name:"{title}", remind me date:date "{reminder_time}"}}
            end tell
        end tell
        '''
        else:
            script = f'''
        tell application "Reminders"
            tell default list
                make new reminder with properties {{name:"{title}"}}
            end tell
        end tell
        '''

        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
            timeout=10,
        )

        return {
            "success": result.returncode == 0,
            "title": title,
            "time": reminder_time,
            "stderr": result.stderr,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
    
def web_search(query: str = ""):
    api_key = os.getenv("BRAVE_API_KEY")

    if not api_key:
        return {
            "success": False,
            "error": "BRAVE_API_KEY is missing.",
        }

    try:
        response = requests.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={
                "Accept": "application/json",
                "X-Subscription-Token": api_key,
            },
            params={
                "q": query.replace("_", " "),
                "count": 5,
            },
            timeout=10,
        )

        response.raise_for_status()
        data = response.json()

        results = []

        for item in data.get("web", {}).get("results", []):
            results.append({
                "title": item.get("title"),
                "url": item.get("url"),
                "description": item.get("description"),
            })

        return {
            "success": True,
            "query": query,
            "results": results,
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
    
def load_market_csv(path: str):
    full_path = safe_path(path)
    df = pd.read_csv(full_path)

    df.columns = [col.lower().strip() for col in df.columns]

    required = ["open", "high", "low", "close"]
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    df = df.dropna(subset=required)

    for col in required:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=required)

    if "time" in df.columns:
        df["time"] = pd.to_datetime(df["time"], errors="coerce")
        df = df.dropna(subset=["time"])
        df = df.sort_values("time")

    return df
    
def analyze_market_csv(
    htf: str = "",
    mtf: str = "",
    ltf: str = "",
    symbol: str = ""
):
    try:
        # Load all three CSVs
        htf_df = load_market_csv(htf)
        mtf_df = load_market_csv(mtf)
        ltf_df = load_market_csv(ltf)

        # --------------------------
        # Helper analysis function
        # --------------------------
        def analyze_df(df):
            current_price = float(df.iloc[-1]["close"])

            # Recent ranges
            recent_20 = df.tail(20)
            recent_50 = df.tail(50)

            recent_high_20 = float(recent_20["high"].max())
            recent_low_20 = float(recent_20["low"].min())
            recent_high_50 = float(recent_50["high"].max())
            recent_low_50 = float(recent_50["low"].min())

            # Basic bias
            if current_price > recent_high_20:
                bias = "bullish"
                structure = "bullish_breakout"
            elif current_price < recent_low_20:
                bias = "bearish"
                structure = "bearish_breakdown"
            elif recent_20["close"].iloc[-1] > recent_20["close"].iloc[0]:
                bias = "bullish"
                structure = "bullish_internal_structure"
            elif recent_20["close"].iloc[-1] < recent_20["close"].iloc[0]:
                bias = "bearish"
                structure = "bearish_internal_structure"
            else:
                bias = "neutral"
                structure = "balanced_or_choppy"

            # FVG detection
            fvgs = []

            for i in range(2, len(df)):
                candle_1 = df.iloc[i - 2]
                candle_3 = df.iloc[i]

                # Bullish FVG
                if candle_3["low"] > candle_1["high"]:
                    fvgs.append({
                        "type": "bullish",
                        "low": float(candle_1["high"]),
                        "high": float(candle_3["low"]),
                        "midpoint": float(
                            (candle_1["high"] + candle_3["low"]) / 2
                        ),
                    })

                # Bearish FVG
                if candle_3["high"] < candle_1["low"]:
                    fvgs.append({
                        "type": "bearish",
                        "low": float(candle_3["high"]),
                        "high": float(candle_1["low"]),
                        "midpoint": float(
                            (candle_3["high"] + candle_1["low"]) / 2
                        ),
                    })

            recent_fvgs = fvgs[-5:]

            return {
                "current_price": current_price,
                "bias": bias,
                "structure": structure,
                "recent_high_20": recent_high_20,
                "recent_low_20": recent_low_20,
                "recent_high_50": recent_high_50,
                "recent_low_50": recent_low_50,
                "recent_fvgs": recent_fvgs,
            }

        # Analyze each timeframe
        htf_analysis = analyze_df(htf_df)
        mtf_analysis = analyze_df(mtf_df)
        ltf_analysis = analyze_df(ltf_df)

        # Determine overall trade plan
        overall_bias = htf_analysis["bias"]

        if overall_bias == "bullish":
            trade_direction = "long"

            candidate_entries = [
                zone
                for zone in mtf_analysis["recent_fvgs"]
                if zone["type"] == "bullish"
            ]

            targets = [
                htf_analysis["recent_high_20"],
                htf_analysis["recent_high_50"],
            ]

            invalidation = (
                "Below the reacting bullish FVG or below the liquidity sweep low."
            )

        elif overall_bias == "bearish":
            trade_direction = "short"

            candidate_entries = [
                zone
                for zone in mtf_analysis["recent_fvgs"]
                if zone["type"] == "bearish"
            ]

            targets = [
                htf_analysis["recent_low_20"],
                htf_analysis["recent_low_50"],
            ]

            invalidation = (
                "Above the reacting bearish FVG or above the liquidity sweep high."
            )

        else:
            trade_direction = "neutral"
            candidate_entries = []
            targets = []
            invalidation = "No high-probability setup."

        # Entry trigger confirmation from 1M
        ltf_confirmation = {
            "bias": ltf_analysis["bias"],
            "structure": ltf_analysis["structure"],
            "entry_model": (
                "Wait for liquidity sweep, MSS/BOS, then BRTC retest."
            ),
        }

        # Final response
        return {
            "success": True,
            "symbol": symbol,

            "htf": {
                "timeframe": "1H",
                **htf_analysis,
            },

            "mtf": {
                "timeframe": "15M",
                **mtf_analysis,
            },

            "ltf": {
                "timeframe": "1M",
                **ltf_analysis,
            },

            "trade_plan": {
                "direction": trade_direction,
                "candidate_entry_zones": candidate_entries[-3:],
                "ltf_confirmation": ltf_confirmation,
                "targets": targets,
                "invalidation": invalidation,
            },

            "analysis_rules": {
                "model": "ICT-based",
                "entry_model": (
                    "Liquidity sweep -> MSS/BOS -> BRTC retest -> continuation"
                ),
                "do_not_use": "VWAP",
                "note": "Conditional analysis only. Not financial advice.",
            },
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }   


TOOLS = {
    "get_time": get_time,
    "echo": echo,
    "run_command": run_command,
    "read_file": read_file,
    "write_file": write_file,
    "open_url": open_url,
    "extract_links": extract_links,
    "create_reminder": create_reminder,
    "web_search": web_search,
    "analyze_market_csv": analyze_market_csv,
}
