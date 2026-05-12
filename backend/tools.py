from datetime import datetime
import subprocess
import os
import requests
import pandas as pd
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

BASE_DIR = os.path.abspath(".")
MAX_OUTPUT_CHARS = 4000
MIN_FVG_SIZE = 5.0
DISPLACEMENT_MULTIPLIER = 1.5


def safe_path(path: str):
    full_path = os.path.abspath(os.path.join(BASE_DIR, path))

    if not full_path.startswith(BASE_DIR):
        raise ValueError("Access denied: outside base directory")

    return full_path


def read_file(path: str = ""):
    try:
        full_path = safe_path(path)

        with open(full_path, "r") as f:
            content = f.read()

        return {
            "success": True,
            "path": path,
            "content": content[:MAX_OUTPUT_CHARS],
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


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
        return {"success": False, "error": str(e)}


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


ALLOWED_COMMANDS = {
    "pwd": ["pwd"],
    "list_files": ["ls", "-la"],
    "disk_usage": ["df", "-h"],
}


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
            text = page.locator("body").inner_text()[:MAX_OUTPUT_CHARS]

            browser.close()

            return {
                "success": True,
                "url": url,
                "title": title,
                "text": text,
            }

    except Exception as e:
        return {"success": False, "error": str(e)}


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
        return {"success": False, "error": str(e)}


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
        return {"success": False, "error": str(e)}


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
        return {"success": False, "error": str(e)}


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


def analyze_dataframe(df):
    current_price = float(df.iloc[-1]["close"])

    recent_20 = df.tail(20)
    recent_50 = df.tail(50)

    recent_high_20 = float(recent_20["high"].max())
    recent_low_20 = float(recent_20["low"].min())
    recent_high_50 = float(recent_50["high"].max())
    recent_low_50 = float(recent_50["low"].min())

    avg_range = float((df["high"] - df["low"]).tail(20).mean())

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

    fvgs = []

    for i in range(2, len(df)):
        candle_1 = df.iloc[i - 2]
        candle_2 = df.iloc[i - 1]
        candle_3 = df.iloc[i]

        middle_range = float(candle_2["high"] - candle_2["low"])
        displacement = middle_range >= avg_range * DISPLACEMENT_MULTIPLIER

        # Bullish FVG: candle 3 low > candle 1 high
        if candle_3["low"] > candle_1["high"]:
            low = float(candle_1["high"])
            high = float(candle_3["low"])
            size = high - low

            if size >= MIN_FVG_SIZE:
                fvgs.append({
                    "type": "bullish",
                    "low": low,
                    "high": high,
                    "midpoint": float((low + high) / 2),
                    "size": float(size),
                    "displacement": displacement,
                    "distance_from_price": float(abs(current_price - ((low + high) / 2))),
                    "index": i,
                    "status": (
                        "above_price" if low > current_price
                        else "below_price" if high < current_price
                        else "inside_zone"
                    ),
                    "time": str(candle_3["time"]) if "time" in df.columns else None,
                })

        # Bearish FVG: candle 3 high < candle 1 low
        if candle_3["high"] < candle_1["low"]:
            low = float(candle_3["high"])
            high = float(candle_1["low"])
            size = high - low

            if size >= MIN_FVG_SIZE:
                fvgs.append({
                    "type": "bearish",
                    "low": low,
                    "high": high,
                    "midpoint": float((low + high) / 2),
                    "size": float(size),
                    "displacement": displacement,
                    "distance_from_price": float(abs(current_price - ((low + high) / 2))),
                    "index": i,
                    "status": (
                        "above_price" if low > current_price
                        else "below_price" if high < current_price
                        else "inside_zone"
                    ),
                    "time": str(candle_3["time"]) if "time" in df.columns else None,
                })

    # Rank FVGs: larger, displaced, and closer to current price matter more
    for zone in fvgs:
        zone["score"] = 0

        # Size matters, but cap it so old monster gaps don't dominate
        zone["score"] += min(zone["size"], 40)

        # Prefer displacement FVGs
        if zone["displacement"]:
            zone["score"] += 15

        # Prefer zones near current price
        if zone["distance_from_price"] <= 25:
            zone["score"] += 30
        elif zone["distance_from_price"] <= 50:
            zone["score"] += 20
        elif zone["distance_from_price"] <= 100:
            zone["score"] += 10
        else:
            zone["score"] -= 50

        # Prefer recent FVGs
        zone["age"] = len(df) - zone["index"]
        if zone["age"] <= 20:
            zone["score"] += 25
        elif zone["age"] <= 50:
            zone["score"] += 15
        elif zone["age"] <= 100:
            zone["score"] += 5
        else:
            zone["score"] -= 25

    relevant_fvgs = [
        zone for zone in fvgs
        if zone["distance_from_price"] <= 150 and zone["age"] <= 150
    ]

    ranked_fvgs = sorted(
        relevant_fvgs,
        key=lambda z: z["score"],
        reverse=True,
)

    return {
        "current_price": current_price,
        "bias": bias,
        "structure": structure,
        "recent_high_20": recent_high_20,
        "recent_low_20": recent_low_20,
        "recent_high_50": recent_high_50,
        "recent_low_50": recent_low_50,
        "recent_fvgs": fvgs[-10:],
        "ranked_fvgs": ranked_fvgs[:10],
        "bullish_fvgs": [z for z in ranked_fvgs if z["type"] == "bullish"][:5],
        "bearish_fvgs": [z for z in ranked_fvgs if z["type"] == "bearish"][:5],
    }


def format_market_response(analysis: dict) -> str:
    if not analysis.get("success"):
        return f"I couldn't analyze the market data: {analysis.get('error', 'Unknown error')}"

    symbol = analysis.get("symbol", "the market")

    htf = analysis.get("htf", {})
    mtf = analysis.get("mtf", {})
    ltf = analysis.get("ltf", {})
    trade_plan = analysis.get("trade_plan", {})

    htf_bias = htf.get("bias", "neutral")
    mtf_bias = mtf.get("bias", "neutral")
    ltf_bias = ltf.get("bias", "neutral")
    current_price = htf.get("current_price")

    bullish_plan = trade_plan.get("bullish_plan", {})
    bearish_plan = trade_plan.get("bearish_plan", {})

    bullish_zones = bullish_plan.get("zones", [])
    bearish_zones = bearish_plan.get("zones", [])
    targets = trade_plan.get("targets", [])
    invalidation = trade_plan.get("invalidation", "No clear invalidation yet.")

    response = []

    response.append(
        f"**{symbol} Read:** 1H is **{htf_bias}**, 15M is **{mtf_bias}**, and 1M is **{ltf_bias}**."
    )

    if current_price:
        response.append(f"Current price is around **{current_price}**.")

    if bullish_zones:
        zone = bullish_zones[0]
        response.append(
            f"The main 15M bullish FVG I care about is **{zone['low']} - {zone['high']}** "
            f"(midpoint **{zone['midpoint']}**)."
        )
    else:
        response.append("I do not see a clean meaningful 15M bullish FVG right now.")

    response.append(
        "**Bullish plan:** If price sweeps liquidity below the FVG, reclaims the zone, "
        "and prints a 1M bullish MSS/BOS, then I’d look for a BRTC long."
    )

    if targets:
        if len(targets) > 1:
            response.append(
                f"Upside targets: **{targets[0]}** first, then **{targets[1]}**."
            )
        else:
            response.append(f"Upside target: **{targets[0]}**.")

    response.append(
        "**Bearish plan:** If price accepts below the FVG and fails to reclaim it, "
        "the long idea is weak. Then I’d look for a 1M bearish MSS/BOS and a BRTC short toward lower liquidity."
    )

    if bearish_zones:
        zone = bearish_zones[0]
        response.append(
            f"Nearest bearish FVG to watch: **{zone['low']} - {zone['high']}** "
            f"(midpoint **{zone['midpoint']}**)."
        )

    response.append(f"Invalidation: **{invalidation}**")

    response.append("No confirmation = no trade. Don’t marry the bias.")

    return "\n\n".join(response)


def analyze_market_csv(
    htf: str = "",
    mtf: str = "",
    ltf: str = "",
    symbol: str = ""
):
    try:
        htf_df = load_market_csv(htf)
        mtf_df = load_market_csv(mtf)
        ltf_df = load_market_csv(ltf)

        htf_analysis = analyze_dataframe(htf_df)
        mtf_analysis = analyze_dataframe(mtf_df)
        ltf_analysis = analyze_dataframe(ltf_df)

        overall_bias = htf_analysis["bias"]

        if overall_bias == "bullish":
            trade_direction = "long"

            candidate_entries = mtf_analysis["bullish_fvgs"]

            targets = list(dict.fromkeys([
                htf_analysis["recent_high_20"],
                htf_analysis["recent_high_50"],
            ]))

            invalidation = (
                "Below the reacting bullish FVG or below the liquidity sweep low."
            )

        elif overall_bias == "bearish":
            trade_direction = "short"

            candidate_entries = mtf_analysis["bearish_fvgs"]

            targets = list(dict.fromkeys([
                htf_analysis["recent_low_20"],
                htf_analysis["recent_low_50"],
            ]))

            invalidation = (
                "Above the reacting bearish FVG or above the liquidity sweep high."
            )

        else:
            trade_direction = "neutral"
            candidate_entries = []
            targets = []
            invalidation = "No high-probability setup."

        ltf_confirmation = {
            "bias": ltf_analysis["bias"],
            "structure": ltf_analysis["structure"],
            "entry_model": "Wait for liquidity sweep, MSS/BOS, then BRTC retest.",
        }

        analysis = {
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

                "bullish_plan": {
                    "idea": "Only look for longs if price reclaims or respects a meaningful bullish FVG.",
                    "zones": mtf_analysis.get("bullish_fvgs", [])[:3],
                    "confirmation": "Wait for 1M MSS/BOS bullish, then BRTC retest.",
                    "invalidation": "Failure to reclaim the FVG or clean acceptance below the FVG low.",
                },

                "bearish_plan": {
                    "idea": "If price fails to respect the bullish FVG, look for bearish continuation.",
                    "zones": mtf_analysis.get("bearish_fvgs", [])[:3],
                    "confirmation": "Wait for rejection, 1M bearish MSS/BOS, then BRTC retest.",
                    "invalidation": "Reclaim back above the rejected FVG or break above rejection high.",
                },
            },

            "analysis_rules": {
                "model": "ICT-based",
                "entry_model": "Liquidity sweep -> MSS/BOS -> BRTC retest -> continuation",
                "do_not_use": "VWAP",
                "note": "Conditional analysis only. Not financial advice.",
            },
        }

        return {
            "success": True,
            "symbol": symbol,
            "analysis": analysis,
            "message": format_market_response(analysis),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"I couldn't analyze the market CSVs: {str(e)}",
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