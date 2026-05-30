from datetime import datetime
import subprocess
import os
import json
import re
import shutil
import time
import requests
import pandas as pd
import base64
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


load_dotenv()

BASE_DIR = os.path.abspath(".")
MAX_OUTPUT_CHARS = 4000
MIN_FVG_SIZE = 1.0
DISPLACEMENT_MULTIPLIER = 1.5

CSV_DATA_DIR = os.path.join(BASE_DIR, "csv_data")
SCREENSHOTS_DIR = os.path.join(BASE_DIR, "pictures", "tradingview_screenshots")
DOWNLOADS_DIR = os.path.join(BASE_DIR, "downloads", "tradingview_csv")

os.makedirs(CSV_DATA_DIR, exist_ok=True)
os.makedirs(SCREENSHOTS_DIR, exist_ok=True)
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
TEXT_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:9b")
VISION_MODEL = os.getenv("VISION_MODEL", "qwen2.5vl:7b")


SYMBOL_CONFIG = {
    "MNQ": {
        "tv_symbol": "CME_MINI:MNQ1!",
        "csv_root": "CME_MINI_MNQ1!",
        "csv_prefix": "MNQ",
    },
    "NQ": {
        "tv_symbol": "CME_MINI:NQ1!",
        "csv_root": "CME_MINI_NQ1!",
        "csv_prefix": "NQ",
    },
    "MES": {
        "tv_symbol": "CME_MINI:MES1!",
        "csv_root": "CME_MINI_MES1!",
        "csv_prefix": "MES",
    },
    "ES": {
        "tv_symbol": "CME_MINI:ES1!",
        "csv_root": "CME_MINI_ES1!",
        "csv_prefix": "ES",
    },
}


TRADINGVIEW_TIMEFRAMES = {
    "1M": "1",
    "15M": "15",
    "1H": "60",
    "4H": "240",
    "1D": "1D",
}


TIMEFRAME_LABELS = {
    "1M": "1 minute",
    "15M": "15 minutes",
    "1H": "1 hour",
    "4H": "4 hours",
    "1D": "1 day",
}


TIMEFRAME_WEIGHTS = {
    "1D": 50,
    "4H": 40,
    "1H": 30,
    "15M": 20,
    "1M": 10,
}


# ---------------------------------------------------------------------
# General helpers
# ---------------------------------------------------------------------

def ollama_generate(
    model: str,
    prompt: str,
    images: list[str] | None = None,
    timeout: int = 180,
    num_ctx: int = 8192,
):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    if images:
        # Keep vision payload minimal. This matches the direct qwen2.5vl test that worked.
        # Some local vision models can 500 when image input is combined with extra options.
        payload["images"] = images
    else:
        # Text-only calls can keep the extra controls.
        payload["think"] = False
        payload["options"] = {"num_ctx": num_ctx}

    response = requests.post(
        OLLAMA_URL,
        json=payload,
        timeout=timeout,
    )

    response.raise_for_status()
    data = response.json()

    return data.get("response", "").strip()


def parse_json_from_text(text: str):
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)

    if not match:
        raise ValueError("No JSON object found in model response.")

    return json.loads(match.group(0))


def get_symbol_config(symbol: str):
    symbol = symbol.upper()

    if symbol not in SYMBOL_CONFIG:
        raise ValueError(
            f"Unsupported symbol: {symbol}. Supported: {', '.join(SYMBOL_CONFIG.keys())}"
        )

    return SYMBOL_CONFIG[symbol]


def safe_path(path: str):
    os.makedirs(CSV_DATA_DIR, exist_ok=True)

    full_path = os.path.abspath(os.path.join(CSV_DATA_DIR, path))

    if not full_path.startswith(os.path.abspath(CSV_DATA_DIR)):
        raise ValueError("Access denied: outside csv_data directory")

    return full_path


def read_file(path: str = ""):
    try:
        full_path = os.path.abspath(os.path.join(BASE_DIR, path))

        if not full_path.startswith(BASE_DIR):
            raise ValueError("Access denied: outside base directory")

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
        full_path = os.path.abspath(os.path.join(BASE_DIR, path))

        if not full_path.startswith(BASE_DIR):
            raise ValueError("Access denied: outside base directory")

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


# ---------------------------------------------------------------------
# TradingView capture / CSV refresh
# ---------------------------------------------------------------------

def get_tradingview_profile_dir():
    return os.path.join(BASE_DIR, "playwright_tradingview_profile")


def capture_tradingview(symbol: str = "MNQ", timeframe: str | None = None):
    try:
        os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        symbol = symbol.upper()

        suffix = f"_{timeframe.upper()}" if timeframe else ""
        screenshot_path = os.path.join(
            SCREENSHOTS_DIR,
            f"{symbol}{suffix}_{timestamp}.png",
        )

        config = get_symbol_config(symbol)
        tv_symbol = config["tv_symbol"]
        profile_dir = get_tradingview_profile_dir()

        interval = TRADINGVIEW_TIMEFRAMES.get(timeframe.upper()) if timeframe else None
        chart_url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}"

        if interval:
            chart_url += f"&interval={interval}"

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                viewport={"width": 1600, "height": 900},
                accept_downloads=True,
            )

            page = context.pages[0] if context.pages else context.new_page()
            page.goto(chart_url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(15000)
            page.screenshot(path=screenshot_path, full_page=False)

            context.close()

        return {
            "success": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "tv_symbol": tv_symbol,
            "screenshot_path": screenshot_path,
            "message": f"TradingView screenshot captured: {screenshot_path}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"TradingView capture failed: {e}",
        }


def setup_tradingview_profile():
    profile_dir = get_tradingview_profile_dir()
    os.makedirs(profile_dir, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            viewport={"width": 1600, "height": 900},
            accept_downloads=True,
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.tradingview.com/chart/", wait_until="domcontentloaded")

        print("\nTradingView browser is open.")
        print("Log in, load your layout, and make sure CSV export is available.")
        print("You have 5 minutes...")

        page.wait_for_timeout(300000)
        context.close()

    return {
        "success": True,
        "message": "TradingView profile setup complete.",
        "profile_dir": profile_dir,
    }


def set_tradingview_interval(page, timeframe: str):
    interval = TRADINGVIEW_TIMEFRAMES[timeframe]

    # Best-effort URL interval control. TradingView usually respects interval query param
    # after page navigation. If not, the active chart layout may override it.
    return interval


def _try_open_export_menu(page):
    """
    Best-effort TradingView export opener.

    TradingView changes UI often. This tries common paths but returns False
    instead of crashing if selectors fail.
    """
    candidates = [
        "button[aria-label*='More']",
        "button[aria-label*='Menu']",
        "button[data-name='header-toolbar-more']",
    ]

    for selector in candidates:
        try:
            locator = page.locator(selector).first
            if locator.count() > 0:
                locator.click(timeout=3000)
                page.wait_for_timeout(1000)
                return True
        except Exception:
            continue

    try:
        page.keyboard.press("Alt+F")
        page.wait_for_timeout(1000)
        return True
    except Exception:
        return False


def _try_click_export_chart_data(page):
    export_texts = [
        "Export chart data",
        "Export data",
        "Export",
    ]

    for text in export_texts:
        try:
            item = page.get_by_text(text, exact=False).first
            if item.count() > 0:
                item.click(timeout=3000)
                page.wait_for_timeout(1000)
                return True
        except Exception:
            continue

    return False


def _normalize_downloaded_csv(download_path: str, symbol: str, timeframe: str):
    clean_name = f"{symbol.upper()}_{timeframe.upper()}.csv"
    destination = safe_path(clean_name)
    shutil.copyfile(download_path, destination)

    return clean_name


def refresh_market_csvs(symbol: str = "MNQ"):
    """
    Best-effort TradingView CSV export.

    This depends on TradingView UI and account permissions.
    If it fails, export CSVs manually into backend/csv_data using:
        MNQ_1D.csv
        MNQ_4H.csv
        MNQ_1H.csv
        MNQ_15M.csv
        MNQ_1M.csv
    """
    symbol = symbol.upper()

    try:
        config = get_symbol_config(symbol)
        tv_symbol = config["tv_symbol"]
        profile_dir = get_tradingview_profile_dir()

        exported = {}
        failures = {}

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                viewport={"width": 1600, "height": 900},
                accept_downloads=True,
            )

            page = context.pages[0] if context.pages else context.new_page()

            for timeframe, interval in TRADINGVIEW_TIMEFRAMES.items():
                chart_url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}&interval={interval}"

                try:
                    page.goto(chart_url, wait_until="domcontentloaded", timeout=90000)
                    page.wait_for_timeout(12000)

                    opened = _try_open_export_menu(page)
                    clicked = _try_click_export_chart_data(page)

                    if not opened or not clicked:
                        failures[timeframe] = (
                            "Could not find TradingView export menu/button. "
                            "UI may have changed or export may require manual action."
                        )
                        continue

                    try:
                        with page.expect_download(timeout=15000) as download_info:
                            # Some TradingView dialogs require confirming export.
                            for label in ["Export", "Download", "Save"]:
                                try:
                                    confirm = page.get_by_text(label, exact=False).first
                                    if confirm.count() > 0:
                                        confirm.click(timeout=3000)
                                        break
                                except Exception:
                                    pass

                        download = download_info.value
                        temp_path = os.path.join(
                            DOWNLOADS_DIR,
                            f"{symbol}_{timeframe}_{int(time.time())}.csv",
                        )
                        download.save_as(temp_path)

                        clean_name = _normalize_downloaded_csv(
                            temp_path,
                            symbol=symbol,
                            timeframe=timeframe,
                        )

                        exported[timeframe] = clean_name

                    except PlaywrightTimeoutError:
                        failures[timeframe] = (
                            "Export dialog opened, but no CSV download was detected."
                        )

                except Exception as e:
                    failures[timeframe] = str(e)

            context.close()

        success = len(exported) > 0

        return {
            "success": success,
            "symbol": symbol,
            "exported": exported,
            "failures": failures,
            "message": (
                f"CSV refresh completed. Exported: {exported}. Failures: {failures}"
                if success
                else (
                    "CSV refresh failed. TradingView export automation is brittle. "
                    "Manually export CSVs into backend/csv_data as SYMBOL_1D.csv, "
                    "SYMBOL_4H.csv, SYMBOL_1H.csv, SYMBOL_15M.csv, SYMBOL_1M.csv."
                )
            ),
        }

    except Exception as e:
        return {
            "success": False,
            "symbol": symbol,
            "error": str(e),
            "message": f"CSV refresh failed: {e}",
        }


# ---------------------------------------------------------------------
# CSV / market state engine
# ---------------------------------------------------------------------

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
        df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
        df["time"] = df["time"].dt.tz_localize(None)
        df = df.dropna(subset=["time"])
        df = df.sort_values("time")

    return df


def resolve_market_csv(symbol: str, timeframe: str):
    symbol = symbol.upper()
    timeframe = timeframe.upper()

    config = get_symbol_config(symbol)

    clean_name = f"{config['csv_prefix']}_{timeframe}.csv"
    tv_tf = TRADINGVIEW_TIMEFRAMES.get(timeframe)

    possible_names = [clean_name]

    if tv_tf:
        possible_names.append(f"{config['csv_root']}, {tv_tf}.csv")
        possible_names.append(f"{config['csv_root']},{tv_tf}.csv")

    for name in possible_names:
        full_path = safe_path(name)
        if os.path.exists(full_path):
            return name

    raise FileNotFoundError(
        f"No CSV found for {symbol} {timeframe}. Tried: {possible_names}"
    )


def classify_location(current_price: float, low: float, high: float):
    if current_price < low:
        return "above_price"
    if current_price > high:
        return "below_price"
    return "inside_zone"


def zone_relation_to_price(current_price: float, low: float, high: float):
    if current_price < low:
        return "overhead"
    if current_price > high:
        return "below_market"
    return "inside"


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
                midpoint = float((low + high) / 2)

                fvgs.append({
                    "type": "bullish",
                    "low": low,
                    "high": high,
                    "midpoint": midpoint,
                    "size": float(size),
                    "displacement": displacement,
                    "distance_from_price": float(abs(current_price - midpoint)),
                    "index": i,
                    "status": classify_location(current_price, low, high),
                    "relation_to_price": zone_relation_to_price(current_price, low, high),
                    "time": str(candle_3["time"]) if "time" in df.columns else None,
                })

        # Bearish FVG: candle 3 high < candle 1 low
        if candle_3["high"] < candle_1["low"]:
            low = float(candle_3["high"])
            high = float(candle_1["low"])
            size = high - low

            if size >= MIN_FVG_SIZE:
                midpoint = float((low + high) / 2)

                fvgs.append({
                    "type": "bearish",
                    "low": low,
                    "high": high,
                    "midpoint": midpoint,
                    "size": float(size),
                    "displacement": displacement,
                    "distance_from_price": float(abs(current_price - midpoint)),
                    "index": i,
                    "status": classify_location(current_price, low, high),
                    "relation_to_price": zone_relation_to_price(current_price, low, high),
                    "time": str(candle_3["time"]) if "time" in df.columns else None,
                })

    for zone in fvgs:
        zone["score"] = 0

        zone["score"] += min(zone["size"], 40)

        if zone["displacement"]:
            zone["score"] += 15

        if zone["distance_from_price"] <= 25:
            zone["score"] += 30
        elif zone["distance_from_price"] <= 50:
            zone["score"] += 20
        elif zone["distance_from_price"] <= 100:
            zone["score"] += 10
        else:
            zone["score"] -= 50

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


def rank_fvg_zones(current_price: float, zones_by_timeframe: dict):
    all_zones = []

    for timeframe, zones in zones_by_timeframe.items():
        tf_weight = TIMEFRAME_WEIGHTS.get(timeframe, 0)

        for zone in zones:
            midpoint = zone.get("midpoint")
            distance = abs(current_price - midpoint)

            score = 0
            reasons = []

            score += tf_weight
            reasons.append(f"{timeframe} timeframe carries weight.")

            if distance <= 25:
                score += 30
                reasons.append("Zone is very close to current price.")
            elif distance <= 75:
                score += 20
                reasons.append("Zone is near current price.")
            elif distance <= 150:
                score += 10
                reasons.append("Zone is still within reasonable reach.")
            else:
                score -= 20
                reasons.append("Zone is far from current price.")

            if zone.get("displacement"):
                score += 15
                reasons.append("Created with displacement.")

            score += min(zone.get("size", 0), 40)

            if zone.get("status") == "inside_zone":
                score += 25
                reasons.append("Price is currently inside this zone.")
            elif zone.get("status") in ["below_price", "above_price"]:
                score += 5

            ranked_zone = {
                **zone,
                "timeframe": timeframe,
                "score": round(score, 2),
                "ranking_reasons": reasons,
            }

            all_zones.append(ranked_zone)

    ranked = sorted(all_zones, key=lambda z: z["score"], reverse=True)

    active_zone = ranked[0] if ranked else None
    backup_zones = ranked[1:4] if len(ranked) > 1 else []

    return {
        "active_zone": active_zone,
        "backup_zones": backup_zones,
        "all_ranked_zones": ranked[:10],
    }


def get_best_zone(analysis_block: dict, preferred_type: str | None = None):
    if not analysis_block:
        return None

    zones = analysis_block.get("ranked_fvgs", [])

    if not zones:
        return None

    if preferred_type:
        matching = [z for z in zones if z.get("type") == preferred_type]

        if matching:
            return matching[0]

    return zones[0]


def get_directional_targets(current_price: float, analysis: dict):
    daily = analysis.get("daily", {})
    h4 = analysis.get("h4", {})
    htf = analysis.get("htf", {})
    mtf = analysis.get("mtf", {})

    raw_above = [
        htf.get("recent_high_20"),
        htf.get("recent_high_50"),
        h4.get("recent_high_20"),
        daily.get("recent_high_20"),
        mtf.get("recent_high_20"),
    ]

    raw_below = [
        htf.get("recent_low_20"),
        htf.get("recent_low_50"),
        h4.get("recent_low_20"),
        daily.get("recent_low_20"),
        mtf.get("recent_low_20"),
    ]

    above = sorted({
        float(x) for x in raw_above
        if x is not None and float(x) > current_price
    })

    below = sorted({
        float(x) for x in raw_below
        if x is not None and float(x) < current_price
    }, reverse=True)

    return {
        "above": above[:5],
        "below": below[:5],
    }


def format_zone_line(label: str, zone: dict, role: str):
    if not zone:
        return f"- **{label}:** No clean FVG found."

    timeframe = zone.get("timeframe", label)
    zone_type = zone.get("type", "unknown").capitalize()

    return (
        f"- **{timeframe} {zone_type} FVG:** "
        f"{zone['low']} - {zone['high']} "
        f"(midpoint {zone['midpoint']}) — {role}"
    )


def format_market_response(analysis: dict) -> str:
    if not analysis.get("success"):
        return f"I couldn't analyze the market data: {analysis.get('error', 'Unknown error')}"

    symbol = analysis.get("symbol", "the market")
    context = analysis.get("context", {})
    trade_plan = analysis.get("trade_plan", {})

    context_bias = context.get("bias", "neutral")
    context_tf = context.get("bias_timeframe", "1D")
    current_price = context.get("current_price")

    daily = analysis.get("daily")
    h4 = analysis.get("h4")
    htf = analysis.get("htf", {})
    mtf = analysis.get("mtf", {})
    ltf = analysis.get("ltf", {})

    preferred_type = (
        "bullish" if context_bias == "bullish"
        else "bearish" if context_bias == "bearish"
        else None
    )

    daily_zone = get_best_zone(daily, preferred_type)
    h4_zone = get_best_zone(h4, preferred_type)
    h1_zone = get_best_zone(htf, preferred_type)
    m15_zone = get_best_zone(mtf, preferred_type)
    m1_zone = get_best_zone(ltf, preferred_type)

    response = []

    response.append(
        f"**{symbol} Data Read:** Main context is **{context_bias}** from the "
        f"**{context_tf}**. Current price is around **{current_price}**."
    )

    response.append("## Computed Zones")

    if daily:
        response.append(format_zone_line("1D", daily_zone, "strategic HTF context"))

    if h4:
        response.append(format_zone_line("4H", h4_zone, "primary HTF battlefield"))

    response.append(format_zone_line("1H", h1_zone, "HTF confirmation / draw"))
    response.append(format_zone_line("15M", m15_zone, "setup/refinement"))
    response.append(format_zone_line("1M", m1_zone, "execution trigger only"))

    targets = trade_plan.get("targets", {})
    above = targets.get("above", [])
    below = targets.get("below", [])

    response.append("## Liquidity / Targets")
    response.append(f"- **Above:** {above if above else 'No clean upside target from CSV.'}")
    response.append(f"- **Below:** {below if below else 'No clean downside target from CSV.'}")

    response.append("## Trade Logic")
    response.append(
        "- **Bullish:** Needs price to respect/reclaim a meaningful bullish zone, "
        "then confirm with 1M MSS/BOS and BRTC."
    )
    response.append(
        "- **Bearish:** Needs price to reject a meaningful bearish/overhead zone or fail "
        "a bullish zone, then confirm with 1M MSS/BOS and BRTC."
    )

    response.append(
        "**Bottom Line:** CSV controls price, levels, and structure. Screenshot only confirms markings."
    )

    return "\n\n".join(response)


def analyze_market_csv(
    daily: str = "",
    h4: str = "",
    htf: str = "",
    mtf: str = "",
    ltf: str = "",
    symbol: str = "",
):
    try:
        symbol = symbol.upper() if symbol else "MNQ"

        daily = daily or resolve_market_csv(symbol, "1D")
        h4 = h4 or resolve_market_csv(symbol, "4H")
        htf = htf or resolve_market_csv(symbol, "1H")
        mtf = mtf or resolve_market_csv(symbol, "15M")
        ltf = ltf or resolve_market_csv(symbol, "1M")

        daily_df = load_market_csv(daily)
        h4_df = load_market_csv(h4)
        htf_df = load_market_csv(htf)
        mtf_df = load_market_csv(mtf)
        ltf_df = load_market_csv(ltf)

        daily_analysis = analyze_dataframe(daily_df)
        h4_analysis = analyze_dataframe(h4_df)
        htf_analysis = analyze_dataframe(htf_df)
        mtf_analysis = analyze_dataframe(mtf_df)
        ltf_analysis = analyze_dataframe(ltf_df)

        current_price = ltf_analysis["current_price"]

        zones_by_timeframe = {
            "1D": daily_analysis.get("bullish_fvgs", []) + daily_analysis.get("bearish_fvgs", []),
            "4H": h4_analysis.get("bullish_fvgs", []) + h4_analysis.get("bearish_fvgs", []),
            "1H": htf_analysis.get("bullish_fvgs", []) + htf_analysis.get("bearish_fvgs", []),
            "15M": mtf_analysis.get("bullish_fvgs", []) + mtf_analysis.get("bearish_fvgs", []),
            "1M": ltf_analysis.get("bullish_fvgs", []) + ltf_analysis.get("bearish_fvgs", []),
        }

        zone_ranking = rank_fvg_zones(
            current_price=current_price,
            zones_by_timeframe=zones_by_timeframe,
        )

        context_bias = daily_analysis["bias"]
        context_timeframe = "1D"
        execution_bias = ltf_analysis["bias"]

        targets = get_directional_targets(
            current_price=current_price,
            analysis={
                "daily": daily_analysis,
                "h4": h4_analysis,
                "htf": htf_analysis,
                "mtf": mtf_analysis,
            },
        )

        active_zone = zone_ranking.get("active_zone")
        backup_zones = zone_ranking.get("backup_zones", [])

        bullish_zones = [
            zone for zone in zone_ranking.get("all_ranked_zones", [])
            if zone.get("type") == "bullish"
        ]

        bearish_zones = [
            zone for zone in zone_ranking.get("all_ranked_zones", [])
            if zone.get("type") == "bearish"
        ]

        if context_bias == "bullish":
            trade_direction = "long"
            candidate_entries = bullish_zones[:3]
            invalidation = "Below the active bullish FVG or below the sweep low."
        elif context_bias == "bearish":
            trade_direction = "short"
            candidate_entries = bearish_zones[:3]
            invalidation = "Above the active bearish FVG or above the sweep high."
        else:
            trade_direction = "neutral"
            candidate_entries = []
            invalidation = "No high-probability setup until structure resolves."

        analysis = {
            "success": True,
            "symbol": symbol,

            "files_used": {
                "daily": daily,
                "h4": h4,
                "htf": htf,
                "mtf": mtf,
                "ltf": ltf,
            },

            "context": {
                "bias_timeframe": context_timeframe,
                "bias": context_bias,
                "execution_bias": execution_bias,
                "current_price": current_price,
            },

            "daily": {"timeframe": "1D", **daily_analysis},
            "h4": {"timeframe": "4H", **h4_analysis},
            "htf": {"timeframe": "1H", **htf_analysis},
            "mtf": {"timeframe": "15M", **mtf_analysis},
            "ltf": {"timeframe": "1M", **ltf_analysis},

            "zone_ranking": zone_ranking,

            "trade_plan": {
                "direction": trade_direction,
                "active_zone": active_zone,
                "backup_zones": backup_zones,
                "candidate_entry_zones": candidate_entries,
                "targets": targets,
                "invalidation": invalidation,
                "ltf_confirmation": {
                    "bias": execution_bias,
                    "structure": ltf_analysis["structure"],
                    "entry_model": "Liquidity sweep -> MSS/BOS -> BRTC retest.",
                },
                "bullish_plan": {
                    "idea": "Only look for longs after respect/reclaim of a meaningful bullish zone.",
                    "zones": bullish_zones[:3],
                    "confirmation": "Wait for 1M bullish MSS/BOS, then BRTC retest.",
                    "invalidation": "Failure to reclaim or clean acceptance below the FVG low.",
                },
                "bearish_plan": {
                    "idea": "Look for shorts after rejection from an overhead bearish zone or failed bullish zone.",
                    "zones": bearish_zones[:3],
                    "confirmation": "Wait for 1M bearish MSS/BOS, then BRTC retest.",
                    "invalidation": "Reclaim above the rejected zone or break above rejection high.",
                },
            },

            "analysis_rules": {
                "model": "ICT-based",
                "source_of_truth": "CSV data controls price, levels, FVGs, targets, and structure.",
                "screenshot_role": "Screenshot confirms user drawings and visible chart context only.",
                "timeframe_priority": "1D > 4H > 1H > 15M > 1M",
                "entry_model": "Liquidity sweep -> MSS/BOS -> BRTC retest -> continuation",
                "do_not_use": "VWAP",
                "note": "Conditional analysis only. Not financial advice.",
            },
        }

        return {
            "success": True,
            "symbol": symbol,
            "analysis": analysis,
            "zone_ranking": zone_ranking,
            "message": format_market_response(analysis),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"I couldn't analyze the market CSVs: {str(e)}",
        }


# ---------------------------------------------------------------------
# Vision extractor — NOT final analyst
# ---------------------------------------------------------------------

def build_tradingview_visual_extraction_prompt(
    prompt: str = "",
    symbol: str = "",
    source: str = "TradingView screenshot",
):
    return f"""
You are a visual extraction agent.

Your only job is to extract visible chart markings from this {source}.
Do not provide trading advice.
Do not determine bias.
Do not calculate market structure.
Do not invent exact levels.

Return valid JSON only.

Extract:
- visible_timeframe
- current_price_marker if clearly visible, otherwise null
- visible_labels exactly as shown
- horizontal_lines with label/color/approx_price if visible
- drawn_boxes with label/color/location/approx_low/approx_high if visible
- arrows_or_annotations
- notes_about_user_markings
- uncertainty_flags

Hard label discipline rules:
- Preserve labels exactly. Do not reinterpret, rename, or translate them.
- If the chart says "5min FVG", output "5min FVG" only.
- Never call an FVG a Fibonacci retracement unless the exact visible text says "Fibonacci", "Fib", or "retracement".
- Never call a line support/resistance unless the chart label explicitly says that.
- Never convert session levels into FVGs.
- Never convert ranges/averages into trade signals.
- If uncertain, put the uncertainty in uncertainty_flags instead of guessing.

Rules:
- User-drawn boxes, rectangles, horizontal lines, arrows, and labels matter most.
- If a number is unclear, use null.
- If a zone boundary is unclear, use null.
- Do not classify bias as bullish or bearish.
- Do not say price is above/below/inside unless visually obvious.
- CSV data will handle all numeric truth later.

JSON schema:
{{
  "symbol": "{symbol or "Unknown"}",
  "source": "{source}",
  "visible_timeframe": null,
  "current_price_marker": null,
  "visible_labels": [],
  "horizontal_lines": [
    {{
      "label": null,
      "color": null,
      "approx_price": null
    }}
  ],
  "drawn_boxes": [
    {{
      "label": null,
      "color": null,
      "approx_low": null,
      "approx_high": null,
      "location_notes": null
    }}
  ],
  "arrows_or_annotations": [],
  "notes_about_user_markings": [],
  "uncertainty_flags": []
}}

User request:
{prompt or "Extract the visible chart markings."}
"""


def build_simple_visual_fallback_prompt(
    prompt: str = "",
    symbol: str = "",
    source: str = "TradingView screenshot",
):
    return f"""
Extract the visible TradingView chart markings from this {source}.

Return JSON only. Keep it simple.

Rules:
- Preserve labels exactly as visible.
- If text says "5min FVG", write "5min FVG".
- Do not use the word Fibonacci unless that exact word, "Fib", or "retracement" is visibly shown.
- Do not give trade advice.
- Do not determine bias.
- If unsure, use null or add an uncertainty flag.

JSON schema:
{{
  "symbol": "{symbol or "Unknown"}",
  "source": "{source}",
  "visible_timeframe": null,
  "current_price_marker": null,
  "visible_labels": [],
  "horizontal_lines": [],
  "drawn_boxes": [],
  "arrows_or_annotations": [],
  "notes_about_user_markings": [],
  "uncertainty_flags": []
}}

User request:
{prompt or "Extract visible chart markings."}
"""


def normalize_visual_extraction(visuals: dict):
    """
    Clean obvious vision-label drift before the narrator sees it.

    Example: if the chart label says "5min FVG", the vision model should not
    reframe it as Fibonacci unless Fibonacci/Fib/retracement is visibly present.
    """
    if not isinstance(visuals, dict):
        return visuals

    labels = visuals.get("visible_labels", []) or []
    horizontal_lines = visuals.get("horizontal_lines", []) or []
    drawn_boxes = visuals.get("drawn_boxes", []) or []

    visible_text_parts = []
    visible_text_parts.extend([str(label) for label in labels])

    for item in horizontal_lines + drawn_boxes:
        if isinstance(item, dict):
            visible_text_parts.append(str(item.get("label", "")))
            visible_text_parts.append(str(item.get("location_notes", "")))

    visible_text = " ".join(visible_text_parts).lower()
    fibonacci_is_visible = any(
        term in visible_text
        for term in ["fibonacci", "fib", "retracement"]
    )

    if not fibonacci_is_visible:
        cleaned_notes = []
        for note in visuals.get("notes_about_user_markings", []) or []:
            note_text = str(note)
            if any(term in note_text.lower() for term in ["fibonacci", "fib", "retracement"]):
                continue
            cleaned_notes.append(note)

        visuals["notes_about_user_markings"] = cleaned_notes
        if cleaned_notes != (visuals.get("notes_about_user_markings", []) or []):
            visuals.setdefault("uncertainty_flags", []).append(
                "Removed a vision note that reinterpreted a visible label."
            )

    return visuals


def extract_tradingview_visuals_from_image(
    image_base64: str,
    prompt: str = "",
    symbol: str = "",
    source: str = "TradingView screenshot",
):
    raw_response = ""
    used_fallback_prompt = False

    try:
        extraction_prompt = build_tradingview_visual_extraction_prompt(
            prompt=prompt,
            symbol=symbol,
            source=source,
        )

        try:
            raw_response = ollama_generate(
                model=VISION_MODEL,
                prompt=extraction_prompt,
                images=[image_base64],
                timeout=180,
                num_ctx=4096,
            )
        except requests.exceptions.RequestException:
            used_fallback_prompt = True
            fallback_prompt = build_simple_visual_fallback_prompt(
                prompt=prompt,
                symbol=symbol,
                source=source,
            )

            raw_response = ollama_generate(
                model=VISION_MODEL,
                prompt=fallback_prompt,
                images=[image_base64],
                timeout=180,
                num_ctx=2048,
            )

        try:
            extracted = parse_json_from_text(raw_response)
        except Exception:
            extracted = {
                "symbol": symbol,
                "source": source,
                "visible_timeframe": None,
                "current_price_marker": None,
                "visible_labels": [],
                "horizontal_lines": [],
                "drawn_boxes": [],
                "arrows_or_annotations": [],
                "notes_about_user_markings": [],
                "uncertainty_flags": [
                    "Vision model responded, but did not return parseable JSON.",
                    raw_response[:500],
                ],
            }

        extracted = normalize_visual_extraction(extracted)

        if used_fallback_prompt:
            extracted.setdefault("uncertainty_flags", []).append(
                "Strict vision extraction failed once; simple fallback prompt was used."
            )

        return {
            "success": True,
            "model": VISION_MODEL,
            "raw_response": raw_response,
            "used_fallback_prompt": used_fallback_prompt,
            "visuals": extracted,
        }

    except Exception as e:
        return {
            "success": False,
            "model": VISION_MODEL,
            "error": str(e),
            "raw_response": raw_response,
            "visuals": {
                "symbol": symbol,
                "source": source,
                "visible_timeframe": None,
                "current_price_marker": None,
                "visible_labels": [],
                "horizontal_lines": [],
                "drawn_boxes": [],
                "arrows_or_annotations": [],
                "notes_about_user_markings": [],
                "uncertainty_flags": [f"Vision extraction failed: {e}"],
            },
        }


def extract_tradingview_visuals_from_path(
    image_path: str,
    prompt: str = "",
    symbol: str = "",
    source: str = "TradingView screenshot",
):
    with open(image_path, "rb") as image_file:
        image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

    return extract_tradingview_visuals_from_image(
        image_base64=image_base64,
        prompt=prompt,
        symbol=symbol,
        source=source,
    )


# Backward-compatible name for main.py imports.
def build_tradingview_vision_prompt(
    prompt: str = "",
    symbol: str = "",
    source: str = "TradingView screenshot",
):
    return build_tradingview_visual_extraction_prompt(
        prompt=prompt,
        symbol=symbol,
        source=source,
    )


# ---------------------------------------------------------------------
# Merge + narrator
# ---------------------------------------------------------------------

def build_merged_market_state(
    csv_analysis: dict,
    visual_extraction: dict | None = None,
):
    if not csv_analysis.get("success"):
        return {
            "success": False,
            "error": csv_analysis.get("error", "CSV analysis failed."),
            "csv_analysis": csv_analysis,
            "visual_extraction": visual_extraction,
        }

    analysis = csv_analysis["analysis"]
    visuals = {}

    if visual_extraction:
        visuals = visual_extraction.get("visuals", {})

    merged = {
        "success": True,
        "source_priority": [
            "CSV controls numeric price, FVGs, structure, targets, and bias.",
            "Vision controls visible user drawings, labels, and screenshot context.",
            "If CSV and screenshot disagree numerically, trust CSV.",
        ],
        "symbol": analysis.get("symbol"),
        "csv_state": {
            "context": analysis.get("context"),
            "files_used": analysis.get("files_used"),
            "zone_ranking": analysis.get("zone_ranking"),
            "trade_plan": analysis.get("trade_plan"),
            "targets": analysis.get("trade_plan", {}).get("targets"),
            "daily": analysis.get("daily"),
            "h4": analysis.get("h4"),
            "htf": analysis.get("htf"),
            "mtf": analysis.get("mtf"),
            "ltf": analysis.get("ltf"),
        },
        "visual_state": visuals,
    }

    return merged


def _compact_zone(zone: dict | None):
    if not zone:
        return None

    return {
        "timeframe": zone.get("timeframe"),
        "type": zone.get("type"),
        "low": zone.get("low"),
        "high": zone.get("high"),
        "midpoint": zone.get("midpoint"),
        "status": zone.get("status"),
        "relation_to_price": zone.get("relation_to_price"),
        "distance_from_price": zone.get("distance_from_price"),
        "displacement": zone.get("displacement"),
    }


def _compact_zones(zones: list[dict] | None, limit: int = 3):
    if not zones:
        return []

    return [_compact_zone(zone) for zone in zones[:limit]]


def build_compact_market_state(merged_state: dict):
    """
    Reduce the merged state before sending it to the narrator model.

    The narrator does not need raw candles, full FVG history, scores, ages,
    ranking reasons, file paths, or every nested analysis object.
    It only needs the confirmed market state and a few relevant zones.
    """
    csv_state = merged_state.get("csv_state", {})
    visual_state = merged_state.get("visual_state", {})

    context = csv_state.get("context", {})
    trade_plan = csv_state.get("trade_plan", {})
    targets = csv_state.get("targets") or trade_plan.get("targets", {})
    zone_ranking = csv_state.get("zone_ranking", {})

    current_price = context.get("current_price")

    all_ranked_zones = zone_ranking.get("all_ranked_zones", [])

    overhead_zones = [
        zone for zone in all_ranked_zones
        if zone.get("relation_to_price") == "overhead"
    ]

    below_market_zones = [
        zone for zone in all_ranked_zones
        if zone.get("relation_to_price") == "below_market"
    ]

    inside_zones = [
        zone for zone in all_ranked_zones
        if zone.get("relation_to_price") == "inside"
    ]

    visual_labels = visual_state.get("visible_labels", [])
    horizontal_lines = visual_state.get("horizontal_lines", [])
    drawn_boxes = visual_state.get("drawn_boxes", [])
    uncertainty_flags = visual_state.get("uncertainty_flags", [])

    # Keep the visual payload small. The narrator only needs enough to judge
    # whether Jadin's drawings line up with CSV structure.
    compact_visual_state = {
        "visible_timeframe": visual_state.get("visible_timeframe"),
        "current_price_marker": visual_state.get("current_price_marker"),
        "visible_labels": visual_labels[:20],
        "horizontal_lines": horizontal_lines[:12],
        "drawn_boxes": drawn_boxes[:8],
        "uncertainty_flags": uncertainty_flags[:5],
    }

    return {
        "symbol": merged_state.get("symbol"),
        "source_priority": merged_state.get("source_priority", []),
        "context": {
            "current_price": current_price,
            "htf_bias_timeframe": context.get("bias_timeframe"),
            "htf_bias": context.get("bias"),
            "execution_bias": context.get("execution_bias"),
        },
        "structure": {
            "daily": {
                "bias": csv_state.get("daily", {}).get("bias"),
                "structure": csv_state.get("daily", {}).get("structure"),
                "recent_high_20": csv_state.get("daily", {}).get("recent_high_20"),
                "recent_low_20": csv_state.get("daily", {}).get("recent_low_20"),
            },
            "h4": {
                "bias": csv_state.get("h4", {}).get("bias"),
                "structure": csv_state.get("h4", {}).get("structure"),
                "recent_high_20": csv_state.get("h4", {}).get("recent_high_20"),
                "recent_low_20": csv_state.get("h4", {}).get("recent_low_20"),
            },
            "h1": {
                "bias": csv_state.get("htf", {}).get("bias"),
                "structure": csv_state.get("htf", {}).get("structure"),
                "recent_high_20": csv_state.get("htf", {}).get("recent_high_20"),
                "recent_low_20": csv_state.get("htf", {}).get("recent_low_20"),
            },
            "m15": {
                "bias": csv_state.get("mtf", {}).get("bias"),
                "structure": csv_state.get("mtf", {}).get("structure"),
                "recent_high_20": csv_state.get("mtf", {}).get("recent_high_20"),
                "recent_low_20": csv_state.get("mtf", {}).get("recent_low_20"),
            },
            "m1": {
                "bias": csv_state.get("ltf", {}).get("bias"),
                "structure": csv_state.get("ltf", {}).get("structure"),
                "recent_high_20": csv_state.get("ltf", {}).get("recent_high_20"),
                "recent_low_20": csv_state.get("ltf", {}).get("recent_low_20"),
            },
        },
        "zones": {
            "active_zone": _compact_zone(zone_ranking.get("active_zone")),
            "inside_zones": _compact_zones(inside_zones, limit=3),
            "overhead_zones": _compact_zones(overhead_zones, limit=3),
            "below_market_zones": _compact_zones(below_market_zones, limit=3),
            "candidate_bullish_zones": _compact_zones(
                trade_plan.get("bullish_plan", {}).get("zones", []),
                limit=3,
            ),
            "candidate_bearish_zones": _compact_zones(
                trade_plan.get("bearish_plan", {}).get("zones", []),
                limit=3,
            ),
        },
        "targets": {
            "above": targets.get("above", [])[:5],
            "below": targets.get("below", [])[:5],
        },
        "execution_model": trade_plan.get("ltf_confirmation", {}),
        "visual_state": compact_visual_state,
    }



BANNED_NARRATOR_TERMS = [
    "recommended strategy",
    "recommendation",
    "strategy:",
    "action:",
    "entry:",
    "entry ",
    "stop loss",
    "take profit",
    "risk/reward",
    "target:",
    "targets:",
    "score",
    "age of",
    "json",
    "buy side",
    "sell side",
    "buy now",
    "sell now",
    "do not buy",
    "do not sell",
    "do not chase",
    "look for longs",
    "look for shorts",
    "consider long",
    "consider short",
    "short scalp",
    "long scalp",
    "selling opportunity",
    "buying opportunity",
    "institutional involvement",
    "algorithms",
    "volume spike",
]

BANNED_NARRATOR_PATTERNS = [
    r"\bscore\s*(of|is|=|:)\s*\d",
    r"\bage\s*(of|is|=|:)\s*\d",
    r"\bwait for .* to enter\b",
    r"\benter a\b",
    r"\benter an\b",
    r"\bto enter\b",
    r"\btarget(?:ing)?\s+\d",
    r"\bstop\s*(?:below|above)\b",
]


def validate_market_narration(message: str):
    """
    Keep the narrator in-bounds.

    If Qwen outputs advisory language, raw scoring internals, or a bloated
    response, the caller should retry or use deterministic fallback text.
    """
    lowered = (message or "").lower()
    violations = []

    for term in BANNED_NARRATOR_TERMS:
        if term in lowered:
            violations.append(term)

    for pattern in BANNED_NARRATOR_PATTERNS:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            violations.append(f"pattern:{pattern}")

    word_count = len((message or "").split())

    if word_count > 240:
        violations.append(f"too_long:{word_count}_words")

    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "word_count": word_count,
    }


def _fmt_price(value):
    if value is None:
        return "unknown"

    try:
        return f"{float(value):.2f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def _fmt_zone(zone: dict | None):
    if not zone:
        return "None identified"

    timeframe = zone.get("timeframe") or "?"
    zone_type = zone.get("type") or "unknown"
    low = _fmt_price(zone.get("low"))
    high = _fmt_price(zone.get("high"))
    relation = zone.get("relation_to_price") or zone.get("status") or "unknown relation"

    return f"{timeframe} {zone_type} FVG {low}–{high} ({relation})"


def _fmt_zone_list(zones: list[dict] | None, limit: int = 2):
    if not zones:
        return "None nearby"

    return "; ".join(_fmt_zone(zone) for zone in zones[:limit])


def _fmt_targets(values: list | None, limit: int = 3):
    if not values:
        return "None identified"

    return ", ".join(_fmt_price(value) for value in values[:limit])


def _visual_marking_summary(
    visual: dict,
    current_price=None,
    active_zone=None,
    overhead_zones=None,
    below_zones=None,
) -> str:
    if not isinstance(visual, dict):
        return "No usable screenshot markings were detected, so this read is CSV-only."

    overhead_zones = overhead_zones or []
    below_zones = below_zones or []

    visible_labels = visual.get("visible_labels") or []
    horizontal_lines = visual.get("horizontal_lines") or []
    drawn_boxes = visual.get("drawn_boxes") or []
    uncertainty_flags = visual.get("uncertainty_flags") or []

    has_visual_context = bool(visible_labels or horizontal_lines or drawn_boxes)

    if not has_visual_context:
        if uncertainty_flags:
            return "No usable screenshot markings were detected, so this read is CSV-only."
        return "No visible chart markings were detected."

    # -------------------------
    # Local helpers
    # -------------------------
    def _dedupe_keep_order(items):
        seen = set()
        cleaned = []

        for item in items:
            text = str(item).strip()
            key = text.lower()

            if not key or key in seen:
                continue

            seen.add(key)
            cleaned.append(text)

        return cleaned

    def _normalize_session_label(text: str) -> list[str]:
        text_lower = str(text).lower()
        sessions = []

        if "tokyo" in text_lower:
            sessions.append("Tokyo")

        if "london" in text_lower:
            sessions.append("London")

        if "new york" in text_lower:
            sessions.append("New York")

        return sessions

    def _is_noise_label(text: str) -> bool:
        text_lower = str(text).lower()

        return any(
            skip in text_lower
            for skip in [
                "buy",
                "sell",
                "range:",
                "avg:",
                "%",
                "vol",
                "500",
                "tradingview",
            ]
        )

    def _is_relevant_label(text: str) -> bool:
        text_lower = str(text).lower()

        return any(
            keep in text_lower
            for keep in [
                "fvg",
                "pdh",
                "pdnyh",
                "pwh",
                "previous week",
                "asia",
                "london",
                "tokyo",
                "new york",
                "high",
                "low",
            ]
        )

    def _is_ltf_fvg_label(text: str) -> bool:
        text_lower = str(text).lower()

        return any(
            token in text_lower
            for token in [
                "1min fvg",
                "1m fvg",
                "3min fvg",
                "3m fvg",
                "5min fvg",
                "5m fvg",
                "15min fvg",
                "15m fvg",
                "15 min fvg",
            ]
        )

    def _has_htf_or_compressed_context(text: str) -> bool:
        text_lower = str(text).lower()

        return any(
            token in text_lower
            for token in [
                "4hr fvg",
                "4h fvg",
                "pdh",
                "pdnyh",
                "previous week high",
                "pwh",
            ]
        )

    def _normalize_uncertain_ltf_fvg_label(label: str, context_text: str) -> str:
        text = str(label or "").strip()

        if not text:
            return text

        if _is_ltf_fvg_label(text) and _has_htf_or_compressed_context(context_text):
            return "LTF FVG label visible, exact timeframe unclear from this view"

        return text

    def _zone_contains_price(zone: dict, price) -> bool:
        if not zone or price is None:
            return False

        low = zone.get("low")
        high = zone.get("high")

        if low is None or high is None:
            return False

        zone_low = min(low, high)
        zone_high = max(low, high)

        return zone_low <= price <= zone_high

    def _zone_distance(zone: dict, price):
        if not zone or price is None:
            return None

        low = zone.get("low")
        high = zone.get("high")

        if low is None or high is None:
            return None

        zone_low = min(low, high)
        zone_high = max(low, high)

        if zone_low <= price <= zone_high:
            return 0

        if price < zone_low:
            return zone_low - price

        return price - zone_high

    parts = []

    # -------------------------
    # Clean visible labels
    # -------------------------
    important_labels = []

    for label in visible_labels:
        if not isinstance(label, str):
            continue

        label = label.strip()

        if not label:
            continue

        if _is_noise_label(label):
            continue

        session_labels = _normalize_session_label(label)

        if session_labels:
            important_labels.extend(session_labels)
        elif _is_relevant_label(label):
            important_labels.append(label)

    important_labels = _dedupe_keep_order(important_labels)

    if important_labels:
        parts.append(
            "Detected labels: "
            + ", ".join(important_labels[:8])
            + "."
        )

    # -------------------------
    # Clean horizontal levels
    # -------------------------
    clean_lines = []

    for line in horizontal_lines:
        if not isinstance(line, dict):
            continue

        label = str(line.get("label") or "horizontal level").strip()
        price = line.get("approx_price")
        label_lower = label.lower()

        if not label or _is_noise_label(label):
            continue

        if not _is_relevant_label(label):
            continue

        # FVGs are zones, not horizontal levels.
        # They should be reported under "Marked zones" instead.
        if "fvg" in label_lower:
            continue

        # If vision extracts a suspicious price for a major reference level,
        # keep the label but downgrade confidence in the numeric value.
        if price is not None and current_price is not None:
            try:
                distance_from_current = abs(float(price) - float(current_price))

                is_major_reference = any(
                    token in label_lower
                    for token in [
                        "previous week high",
                        "pwh",
                        "pdh",
                        "pdnyh",
                        "asia high",
                        "asia low",
                        "london high",
                        "london low",
                    ]
                )

                if is_major_reference and distance_from_current > 75:
                    clean_lines.append(f"{label}; extracted price may be unreliable")
                    continue

            except (TypeError, ValueError):
                clean_lines.append(f"{label}; extracted price may be unreliable")
                continue

        if price is not None:
            clean_lines.append(f"{label} near {_fmt_price(price)}")
        else:
            clean_lines.append(label)

    clean_lines = _dedupe_keep_order(clean_lines)

    if clean_lines:
        parts.append(
            "Visible levels: "
            + "; ".join(clean_lines[:5])
            + "."
        )

    # -------------------------
    # Build pre-box visual context
    # -------------------------
    pre_box_visual_text = " ".join(
        str(item).lower()
        for item in important_labels + clean_lines
    )

    # -------------------------
    # Clean drawn boxes / zones
    # -------------------------
    clean_boxes = []

    for box in drawn_boxes:
        if not isinstance(box, dict):
            continue

        raw_label = str(box.get("label") or "marked box").strip()
        low = box.get("approx_low")
        high = box.get("approx_high")

        label = _normalize_uncertain_ltf_fvg_label(
            raw_label,
            pre_box_visual_text,
        )

        if not label or _is_noise_label(label):
            continue

        if low is not None and high is not None and low != high:
            clean_boxes.append(f"{label} around {_fmt_price(low)}–{_fmt_price(high)}")
        elif low is not None:
            clean_boxes.append(f"{label} near {_fmt_price(low)}")
        elif high is not None:
            clean_boxes.append(f"{label} near {_fmt_price(high)}")
        else:
            clean_boxes.append(label)

    clean_boxes = _dedupe_keep_order(clean_boxes)

    if clean_boxes:
        parts.append(
            "Marked zones: "
            + "; ".join(clean_boxes[:3])
            + "."
        )

    # -------------------------
    # Build full visual context
    # -------------------------
    visual_text = " ".join(
        str(item).lower()
        for item in important_labels + clean_lines + clean_boxes
    )

    active_zone_text = _fmt_zone(active_zone) if active_zone else None

    # -------------------------
    # Compare visual FVG markings to CSV zones
    # -------------------------
    if "4hr fvg" in visual_text or "4h fvg" in visual_text:
        if active_zone and active_zone_text and "4H" in active_zone_text:
            parts.append(
                f"Visual 4H FVG appears aligned with the active computed zone: {active_zone_text}."
            )
        elif below_zones:
            parts.append(
                f"Visual 4H FVG was detected; nearest below-market CSV zone is {_fmt_zone(below_zones[0])}."
            )
        else:
            parts.append(
                "Visual 4H FVG was detected, but no matching below-market CSV zone was found."
            )

    if "15min fvg" in visual_text or "15m fvg" in visual_text:
        parts.append(
            "Visual 15M FVG was detected and should be treated as execution/context confirmation, not HTF source of truth."
        )

    if "ltf fvg label visible" in visual_text:
        parts.append(
            "LTF FVG label appears compressed on this screenshot, so exact timeframe should be confirmed on the lower timeframe."
        )

    # -------------------------
    # Compare current price to active zone
    # -------------------------
    if active_zone and current_price is not None:
        if _zone_contains_price(active_zone, current_price):
            parts.append(
                "Current price is inside the active computed zone."
            )
        else:
            distance = _zone_distance(active_zone, current_price)
            relation = active_zone.get("relation_to_price", "away from price")

            if distance is not None:
                parts.append(
                    f"Current price is {_fmt_price(distance)} points from the active computed zone ({relation})."
                )

    # -------------------------
    # Compare current price to nearest CSV zones
    # -------------------------
    if overhead_zones and current_price is not None:
        nearest_overhead = overhead_zones[0]
        distance = _zone_distance(nearest_overhead, current_price)

        if distance is not None:
            parts.append(
                f"Nearest overhead CSV zone is {_fmt_price(distance)} points away: {_fmt_zone(nearest_overhead)}."
            )

    if below_zones and current_price is not None:
        nearest_below = below_zones[0]
        distance = _zone_distance(nearest_below, current_price)

        if distance is not None:
            parts.append(
                f"Nearest below-market CSV zone is {_fmt_price(distance)} points away: {_fmt_zone(nearest_below)}."
            )

    # -------------------------
    # Add session context
    # -------------------------
    if "tokyo" in visual_text or "london" in visual_text or "new york" in visual_text:
        parts.append(
            "Session labels are visible and can be used as context around the active levels."
        )

    # -------------------------
    # Return final visual summary
    # -------------------------
    if not parts:
        return "Screenshot markings were detected, but no clean trading-relevant markings were extracted."

    return " ".join(parts)


def format_deterministic_market_summary(merged_state: dict) -> str:
    """
    Stable final market summary.

    This intentionally does not call the text model. CSV controls the numeric
    state; vision only adds visible drawing/label confirmation.
    """
    state = build_compact_market_state(merged_state)

    symbol = state.get("symbol") or "Market"
    context = state.get("context", {})
    structure = state.get("structure", {})
    zones = state.get("zones", {})
    targets = state.get("targets", {})
    visual = state.get("visual_state", {})

    current_price = context.get("current_price")
    htf_bias = context.get("htf_bias") or "neutral"
    htf_tf = context.get("htf_bias_timeframe") or "HTF"
    execution_bias = context.get("execution_bias") or "neutral"

    active_zone = zones.get("active_zone")
    overhead_zones = zones.get("overhead_zones", [])
    below_zones = zones.get("below_market_zones", [])

    m15 = structure.get("m15", {})
    m1 = structure.get("m1", {})
    h4 = structure.get("h4", {})
    h1 = structure.get("h1", {})

    if execution_bias != htf_bias:
        bias_line = (
            f"HTF remains {htf_bias}, but execution is {execution_bias}; "
            f"short-term read should respect the {execution_bias} structure until reclaimed."
        )
    else:
        bias_line = f"HTF and execution are aligned {htf_bias}."

    scenario_up = (
        f"Upside continuation requires reclaim/acceptance through {_fmt_zone(overhead_zones[0])}."
        if overhead_zones
        else "Upside continuation requires acceptance above the nearest overhead level."
    )

    first_below_target = _fmt_targets(targets.get("below", []), 1)
    scenario_down = (
        f"Downside continuation requires rejection from overhead or loss of {first_below_target}."
        if targets.get("below")
        else "Downside continuation requires rejection from overhead and fresh downside structure."
    )

    lines = [
        "## HTF Context",
        f"{symbol} is around {_fmt_price(current_price)}. {htf_tf} bias is {htf_bias}. H4 is {h4.get('bias', 'unknown')} and H1 is {h1.get('bias', 'unknown')}.",
        "",
        "## Current Structure",
        f"Execution bias is {execution_bias}. M15 structure is {m15.get('structure', 'unknown')}; M1 structure is {m1.get('structure', 'unknown')}.",
        f"Active computed zone: {_fmt_zone(active_zone)}.",
        "",
        "## Liquidity / Levels",
        f"Overhead: {_fmt_zone_list(overhead_zones, 2)}.",
        f"Below market: {_fmt_zone_list(below_zones, 2)}.",
        f"Upside references: {_fmt_targets(targets.get('above', []))}. Downside references: {_fmt_targets(targets.get('below', []))}.",
        "",
        "## Visual Markings Check",
        _visual_marking_summary(
            visual,
            current_price=current_price,
            active_zone=active_zone,
            overhead_zones=overhead_zones,
            below_zones=below_zones,
        ),
        "",
        "## Bias",
        bias_line,
        "",
        "## Scenarios",
        f"- Bullish scenario: {scenario_up}",
        f"- Bearish scenario: {scenario_down}",
        "",
        "## Bottom Line",
        "CSV controls price, levels, FVGs, and structure. Screenshot markings are confirmation only.",
    ]

    return "\n".join(lines)


# Backward-compatible fallback name used by older narration guardrails.
def build_deterministic_market_summary(merged_state: dict):
    return format_deterministic_market_summary(merged_state)

def build_narration_repair_prompt(
    original_message: str,
    validation: dict,
    merged_state: dict,
    user_prompt: str = "",
):
    compact_state = build_compact_market_state(merged_state)
    compact_state_json = json.dumps(compact_state, indent=2, default=str)

    return f"""
Rewrite the market narration because it violated output rules.

Violations:
{validation.get("violations", [])}

Original message:
{original_message}

Hard rules for rewrite:
- Under 220 words.
- Do not mention JSON.
- Do not mention scores.
- Do not say buy, sell, short, long as instructions.
- Do not use "entry", "stop loss", "take profit", "recommended", or "recommendation".
- Do not give financial advice.
- Do not invent labels or indicators.
- Use conditional market narration only.
- If HTF and execution bias differ, explain both briefly.

Required sections only:
## HTF Context
## Current Structure
## Liquidity / Levels
## Visual Markings Check
## Bias
## Scenarios
## Bottom Line

Compact market state:
{compact_state_json}

User request:
{user_prompt or "Analyze the current market state."}
"""


def build_market_narrator_prompt(
    merged_state: dict,
    user_prompt: str = "",
):
    compact_state = build_compact_market_state(merged_state)
    compact_state_json = json.dumps(compact_state, indent=2, default=str)

    return f"""
You are Helix, Jadin's professional futures market narrator.

Your job is to describe:
- market structure
- liquidity
- HTF/LTF alignment
- imbalance reactions
- key levels
- execution context

Use this source priority:
1. CSV market structure data controls current price, numeric levels, FVGs, targets, and bias.
2. Chart vision data only confirms visible drawings, labels, boxes, and markings.
3. If CSV and vision disagree numerically, trust CSV.

DO NOT:
- invent indicators
- invent volume analysis
- mention Fibonacci unless the visual_state explicitly labels Fibonacci
- mention smart money concepts unless explicitly visible
- give financial advice
- tell the user to buy or sell
- use buy/sell/short/long as direct instructions
- say "enter here"
- say "entry"
- say "take profit"
- say "stop loss"
- say "recommended strategy"
- say "recommendation"
- mention FVG scores
- mention JSON
- hallucinate chart labels

Bias handling:
- If HTF bias and execution bias differ, explain both.
- Identify which bias is dominant short term.
- Identify which bias remains intact long term.
- Do not force bullish and bearish scenarios to have equal weight if structure is clearly favoring one side.

Language rules:
- Use conditional language.
- If information is uncertain, say "appears", "likely", "potential", or "currently reacting".
- Do not claim certainty.
- Do not tell Jadin to enter immediately.

Response style:
- concise
- structured
- trader-focused
- no fluff
- no motivational language
- total response under 220 words

Required sections:
## HTF Context
## Current Structure
## Liquidity / Levels
## Visual Markings Check
## Bias
## Scenarios
## Bottom Line

Compact market state:
{compact_state_json}

User request:
{user_prompt or "Analyze the current market state."}
"""
def narrate_market_state(
    merged_state: dict,
    prompt: str = "",
):
    try:
        narrator_prompt = build_market_narrator_prompt(
            merged_state=merged_state,
            user_prompt=prompt,
        )

        message = ollama_generate(
            model=TEXT_MODEL,
            prompt=narrator_prompt,
            images=None,
            timeout=180,
            num_ctx=8192,
        )

        validation = validate_market_narration(message)

        if not validation["valid"]:
            repair_prompt = build_narration_repair_prompt(
                original_message=message,
                validation=validation,
                merged_state=merged_state,
                user_prompt=prompt,
            )

            repaired_message = ollama_generate(
                model=TEXT_MODEL,
                prompt=repair_prompt,
                images=None,
                timeout=180,
                num_ctx=4096,
            )

            repaired_validation = validate_market_narration(repaired_message)

            if not repaired_validation["valid"]:
                fallback_message = build_deterministic_market_summary(merged_state)
                fallback_validation = validate_market_narration(fallback_message)

                return {
                    "success": True,
                    "model": "deterministic_fallback",
                    "message": fallback_message,
                    "validation": fallback_validation,
                    "repaired": True,
                    "fallback_used": True,
                    "original_validation": validation,
                    "repaired_validation": repaired_validation,
                }

            return {
                "success": True,
                "model": TEXT_MODEL,
                "message": repaired_message,
                "validation": repaired_validation,
                "repaired": True,
                "fallback_used": False,
                "original_validation": validation,
            }

        return {
            "success": True,
            "model": TEXT_MODEL,
            "message": message,
            "validation": validation,
            "repaired": False,
        }

    except Exception as e:
        return {
            "success": False,
            "model": TEXT_MODEL,
            "error": str(e),
            "message": f"Market narration failed: {e}",
        }


# ---------------------------------------------------------------------
# Full trading analysis pipeline
# ---------------------------------------------------------------------

def analyze_tradingview(symbol: str = "MNQ", prompt: str = ""):
    """
    Full pipeline:
    1. Capture TradingView screenshot.
    2. Extract visual markings with vision model.
    3. Analyze CSV data with deterministic Python.
    4. Merge states.
    5. Narrate with text model.
    """
    symbol = symbol.upper()

    try:
        capture_result = capture_tradingview(symbol=symbol)

        if not capture_result.get("success"):
            return capture_result

        screenshot_path = capture_result["screenshot_path"]

        visual_result = extract_tradingview_visuals_from_path(
            image_path=screenshot_path,
            prompt=prompt,
            symbol=symbol,
            source="live TradingView capture",
        )

        csv_result = analyze_market_csv(symbol=symbol)

        if not csv_result.get("success"):
            return {
                "success": False,
                "symbol": symbol,
                "screenshot_path": screenshot_path,
                "visual_extraction": visual_result,
                "csv_analysis": csv_result,
                "message": (
                    "Screenshot was captured and visual markings were extracted, "
                    "but CSV analysis failed.\n\n"
                    f"CSV error: {csv_result.get('error')}\n\n"
                    "Refresh or manually export CSV files for 1D, 4H, 1H, 15M, and 1M."
                ),
            }

        merged_state = build_merged_market_state(
            csv_analysis=csv_result,
            visual_extraction=visual_result,
        )

        message = format_deterministic_market_summary(merged_state)

        return {
            "success": True,
            "symbol": symbol,
            "models": {
                "vision": VISION_MODEL,
                "narrator": "deterministic_formatter",
            },
            "screenshot_path": screenshot_path,
            "visual_extraction": visual_result,
            "csv_analysis": csv_result,
            "merged_state": merged_state,
            "message": message + f"\n\nScreenshot saved: `{screenshot_path}`",
        }

    except Exception as e:
        return {
            "success": False,
            "symbol": symbol,
            "error": str(e),
            "message": f"TradingView pipeline failed: {e}",
        }


def analyze_uploaded_chart_image(
    image_base64: str,
    prompt: str = "",
    symbol: str = "",
):
    """
    Uploaded-image pipeline:
    - Vision extracts markings.
    - CSV analyzes real data.
    - Text model narrates.
    """
    try:
        symbol = symbol.upper() if symbol else "MNQ"

        visual_result = extract_tradingview_visuals_from_image(
            image_base64=image_base64,
            prompt=prompt,
            symbol=symbol,
            source="uploaded chart image",
        )

        csv_result = analyze_market_csv(symbol=symbol)

        if not csv_result.get("success"):
            return {
                "success": False,
                "symbol": symbol,
                "visual_extraction": visual_result,
                "csv_analysis": csv_result,
                "message": (
                    "Image visual extraction ran, but CSV analysis failed. "
                    f"CSV error: {csv_result.get('error')}"
                ),
            }

        merged_state = build_merged_market_state(
            csv_analysis=csv_result,
            visual_extraction=visual_result,
        )

        message = format_deterministic_market_summary(merged_state)

        return {
            "success": True,
            "symbol": symbol,
            "models": {
                "vision": VISION_MODEL,
                "narrator": "deterministic_formatter",
            },
            "visual_extraction": visual_result,
            "csv_analysis": csv_result,
            "merged_state": merged_state,
            "message": message,
        }

    except Exception as e:
        return {
            "success": False,
            "symbol": symbol if symbol else None,
            "error": str(e),
            "message": f"Uploaded chart pipeline failed: {e}",
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

    # Trading / market tools
    "refresh_market_csvs": refresh_market_csvs,
    "analyze_market_csv": analyze_market_csv,
    "capture_tradingview": capture_tradingview,
    "setup_tradingview_profile": setup_tradingview_profile,
    "extract_tradingview_visuals_from_path": extract_tradingview_visuals_from_path,
    "analyze_tradingview": analyze_tradingview,
    "analyze_uploaded_chart_image": analyze_uploaded_chart_image,
}