from datetime import datetime
import subprocess
import os
import requests
import pandas as pd
import tempfile
import base64
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright


load_dotenv()

BASE_DIR = os.path.abspath(".")
MAX_OUTPUT_CHARS = 4000
MIN_FVG_SIZE = 1.0
DISPLACEMENT_MULTIPLIER = 1.5
CSV_DATA_DIR = os.path.join(BASE_DIR, "csv_data")
os.makedirs(CSV_DATA_DIR, exist_ok=True)

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


def get_symbol_config(symbol: str):
    symbol = symbol.upper()

    if symbol not in SYMBOL_CONFIG:
        raise ValueError(
            f"Unsupported symbol: {symbol}. Supported: {', '.join(SYMBOL_CONFIG.keys())}"
        )

    return SYMBOL_CONFIG[symbol]


def safe_path(path: str):
    """
    Resolve a CSV filename safely inside backend/csv_data.

    Example:
        safe_path("MNQ_15M.csv")
        -> /Users/jadinrobinson/ai-assistant/backend/csv_data/MNQ_15M.csv
    """
    # Ensure the CSV data directory exists
    os.makedirs(CSV_DATA_DIR, exist_ok=True)

    # Build absolute path inside csv_data/
    full_path = os.path.abspath(os.path.join(CSV_DATA_DIR, path))

    # Prevent directory traversal attacks
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

TIMEFRAME_WEIGHTS = {
    "1D": 50,
    "4H": 40,
    "1H": 30,
    "15M": 20,
    "1M": 10,
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

            # 1. Timeframe strength
            score += tf_weight
            reasons.append(f"{timeframe} timeframe carries weight.")

            # 2. Proximity
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

            # 3. Displacement
            if zone.get("displacement"):
                score += 15
                reasons.append("Created with displacement.")

            # 4. Size cap
            score += min(zone.get("size", 0), 40)

            # 5. Status
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

    # Fallback to strongest zone regardless of type
    return zones[0]


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

    daily = analysis.get("daily")
    h4 = analysis.get("h4")
    htf = analysis.get("htf", {})
    mtf = analysis.get("mtf", {})
    ltf = analysis.get("ltf", {})
    context = analysis.get("context", {})
    trade_plan = analysis.get("trade_plan", {})

    context_bias = context.get("bias", htf.get("bias", "neutral"))
    context_tf = context.get("bias_timeframe", "1H")
    current_price = context.get("current_price", htf.get("current_price"))

    # Prefer zones aligned with context bias, but still show key zones per timeframe.
    preferred_type = "bullish" if context_bias == "bullish" else "bearish" if context_bias == "bearish" else None

    daily_zone = get_best_zone(daily, preferred_type)
    h4_zone = get_best_zone(h4, preferred_type)
    h1_zone = get_best_zone(htf, preferred_type)
    m15_zone = get_best_zone(mtf, preferred_type)
    m1_zone = get_best_zone(ltf, preferred_type)

    targets = trade_plan.get("targets", [])

    response = []

    response.append(
        f"**{symbol} Read:** Main context is **{context_bias}** from the **{context_tf}**. "
        f"Current price is around **{current_price}**."
    )

    response.append("## Chart Levels To Mark")

    if daily:
        response.append(
            format_zone_line(
                "1D",
                daily_zone,
                "strategic HTF zone"
            )
        )

    if h4:
        response.append(
            format_zone_line(
                "4H",
                h4_zone,
                "primary battlefield / active HTF zone"
            )
        )

    response.append(
        format_zone_line(
            "1H",
            h1_zone,
            "backup HTF support/resistance if the 4H fails"
        )
    )

    response.append(
        format_zone_line(
            "15M",
            m15_zone,
            "setup/refinement zone"
        )
    )

    response.append(
        format_zone_line(
            "1M",
            m1_zone,
            "execution trigger only, not the main bias"
        )
    )

    response.append(
        "**Ranking Framework:** Higher timeframe zones control the narrative. "
        "The nearest valid HTF FVG is the active zone. Lower timeframes are used for confirmation and entry."
    )

    # For planning, prefer 4H as the active battlefield when present.
    # 1D is strategic context, not the immediate execution zone.
    if h4_zone:
        active_zone = h4_zone
        active_tf = "4H"
    elif h1_zone:
        active_zone = h1_zone
        active_tf = "1H"
    elif m15_zone:
        active_zone = m15_zone
        active_tf = "15M"
    elif daily_zone:
        active_zone = daily_zone
        active_tf = "1D"
    else:
        active_zone = None
        active_tf = None

    if active_zone:
        if active_zone["type"] == "bullish":
            response.append(
                f"**Bullish Plan:** If price respects or reclaims the "
                f"**{active_tf} Bullish FVG** at "
                f"**{active_zone['low']} - {active_zone['high']}**, "
                f"then drop to the 15M and 1M charts and wait for a "
                f"bullish MSS/BOS followed by a BRTC retest."
            )

            response.append(
                f"**Bearish Failure Plan:** If price accepts below the "
                f"**{active_tf} Bullish FVG** and fails to reclaim it, "
                f"the immediate long setup is invalid. In that case, "
                f"shift focus to the next lower higher-timeframe zone "
                f"or the nearest downside liquidity."
            )

        elif active_zone["type"] == "bearish":
            response.append(
                f"**Bearish Plan:** If price respects or rejects the "
                f"**{active_tf} Bearish FVG** at "
                f"**{active_zone['low']} - {active_zone['high']}**, "
                f"then drop to the 15M and 1M charts and wait for a "
                f"bearish MSS/BOS followed by a BRTC retest."
            )

            response.append(
                f"**Bullish Failure Plan:** If price reclaims the "
                f"**{active_tf} Bearish FVG** and holds above it, "
                f"the immediate short setup is invalid. In that case, "
                f"shift focus to the next higher liquidity pool."
            )

    if targets:
        if len(targets) > 1:
            response.append(f"Targets: **{targets[0]}** first, then **{targets[1]}**.")
        else:
            response.append(f"Target: **{targets[0]}**.")

    response.append(
        "**Bottom Line:** HTF FVG decides the battlefield. 15M refines the setup. "
        "1M pulls the trigger. No confirmation = no trade."
    )

    return "\n\n".join(response)

def analyze_market_csv(
    daily: str = "",
    h4: str = "",
    htf: str = "",
    mtf: str = "",
    ltf: str = "",
    symbol: str = ""
):
    try:
        symbol = symbol.upper() if symbol else "MNQ"

        # Auto-resolve CSV names if paths were not provided.
        # Supports both:
        # MNQ_15M.csv
        # CME_MINI_MNQ1!, 15.csv
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
            "1D": (
                daily_analysis.get("bullish_fvgs", [])
                + daily_analysis.get("bearish_fvgs", [])
            ),
            "4H": (
                h4_analysis.get("bullish_fvgs", [])
                + h4_analysis.get("bearish_fvgs", [])
            ),
            "1H": (
                htf_analysis.get("bullish_fvgs", [])
                + htf_analysis.get("bearish_fvgs", [])
            ),
            "15M": (
                mtf_analysis.get("bullish_fvgs", [])
                + mtf_analysis.get("bearish_fvgs", [])
            ),
            "1M": (
                ltf_analysis.get("bullish_fvgs", [])
                + ltf_analysis.get("bearish_fvgs", [])
            ),
        }

        zone_ranking = rank_fvg_zones(
            current_price=current_price,
            zones_by_timeframe=zones_by_timeframe,
        )

        # Bias hierarchy: Daily > 4H > 1H.
        context_bias = daily_analysis["bias"]
        context_timeframe = "1D"
        execution_bias = ltf_analysis["bias"]

        if context_bias == "bullish":
            trade_direction = "long"

            candidate_entries = [
                zone for zone in zone_ranking.get("all_ranked_zones", [])
                if zone.get("type") == "bullish"
            ]

            targets = [
                htf_analysis["recent_high_20"],
                htf_analysis["recent_high_50"],
                h4_analysis["recent_high_20"],
                daily_analysis["recent_high_20"],
            ]

            targets = sorted(set([target for target in targets if target is not None]))

            invalidation = (
                "Below the active bullish FVG or below the liquidity sweep low."
            )

        elif context_bias == "bearish":
            trade_direction = "short"

            candidate_entries = [
                zone for zone in zone_ranking.get("all_ranked_zones", [])
                if zone.get("type") == "bearish"
            ]

            targets = [
                htf_analysis["recent_low_20"],
                htf_analysis["recent_low_50"],
                h4_analysis["recent_low_20"],
                daily_analysis["recent_low_20"],
            ]

            targets = sorted(
                set([target for target in targets if target is not None]),
                reverse=True,
            )

            invalidation = (
                "Above the active bearish FVG or above the liquidity sweep high."
            )

        else:
            trade_direction = "neutral"
            candidate_entries = []
            targets = []
            invalidation = "No high-probability setup."

        ltf_confirmation = {
            "bias": execution_bias,
            "structure": ltf_analysis["structure"],
            "entry_model": "Wait for liquidity sweep, MSS/BOS, then BRTC retest.",
        }

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

            "daily": {
                "timeframe": "1D",
                **daily_analysis,
            },

            "h4": {
                "timeframe": "4H",
                **h4_analysis,
            },

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

            "zone_ranking": zone_ranking,

            "trade_plan": {
                "direction": trade_direction,
                "active_zone": active_zone,
                "backup_zones": backup_zones,
                "candidate_entry_zones": candidate_entries[:3],
                "ltf_confirmation": ltf_confirmation,
                "targets": targets,
                "invalidation": invalidation,

                "bullish_plan": {
                    "idea": (
                        "Only look for longs if price respects or reclaims "
                        "a meaningful bullish FVG."
                    ),
                    "zones": bullish_zones[:3],
                    "confirmation": "Wait for 1M MSS/BOS bullish, then BRTC retest.",
                    "invalidation": (
                        "Failure to reclaim the active FVG or clean acceptance "
                        "below the FVG low."
                    ),
                },

                "bearish_plan": {
                    "idea": (
                        "If price fails to respect the active bullish FVG or rejects "
                        "a bearish FVG, look for bearish continuation."
                    ),
                    "zones": bearish_zones[:3],
                    "confirmation": "Wait for 1M bearish MSS/BOS, then BRTC retest.",
                    "invalidation": (
                        "Reclaim back above the rejected FVG or break above rejection high."
                    ),
                },
            },

            "analysis_rules": {
                "model": "ICT-based",
                "fvg_ranking": (
                    "Rank FVGs by timeframe, proximity to price, displacement, "
                    "and reaction/acceptance."
                ),
                "entry_model": (
                    "Liquidity sweep -> MSS/BOS -> BRTC retest -> continuation"
                ),
                "timeframe_priority": "1D > 4H > 1H > 15M > 1M",
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
    
def capture_tradingview(symbol: str = "MNQ"):
    try:
        screenshots_dir = os.path.join(
            BASE_DIR,
            "pictures",
            "tradingview_screenshots",
        )
        os.makedirs(screenshots_dir, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")

        screenshot_path = os.path.join(
            screenshots_dir,
            f"{symbol.upper()}_{timestamp}.png",
        )

        symbol = symbol.upper()
        config = get_symbol_config(symbol)
        tv_symbol = config["tv_symbol"]

        chart_url = f"https://www.tradingview.com/chart/?symbol={tv_symbol}"
        profile_dir = os.path.join(BASE_DIR, "playwright_tradingview_profile")

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_dir,
                headless=False,
                viewport={"width": 1600, "height": 900},
            )

            page = context.pages[0] if context.pages else context.new_page()

            # page.goto(chart_url, wait_until="domcontentloaded", timeout=90000)
            # page.wait_for_timeout(10000)

            page.goto("https://www.tradingview.com/chart/", wait_until="domcontentloaded")
            page.wait_for_timeout(15000)
            page.screenshot(path=screenshot_path)

            # page.screenshot(path=screenshot_path, full_page=False)

            context.close()

        return {
            "success": True,
            "symbol": symbol,
            "tv_symbol": tv_symbol,
            "screenshot_path": screenshot_path,
            "message": f"TradingView screenshot captured for {tv_symbol}: {screenshot_path}",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"TradingView capture failed: {e}",
        }
    
def setup_tradingview_profile():
    profile_dir = os.path.join(BASE_DIR, "playwright_tradingview_profile")
    os.makedirs(profile_dir, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            viewport={"width": 1600, "height": 900},
        )

        page = context.pages[0] if context.pages else context.new_page()
        page.goto("https://www.tradingview.com/chart/", wait_until="domcontentloaded")

        print("\nTradingView browser is open.")
        print("You have 5 minutes to log in and load your MNQ layout...")

        page.wait_for_timeout(300000)  # 5 minutes

        context.close()

    return {
        "success": True,
        "message": "TradingView profile setup complete.",
        "profile_dir": profile_dir,
    }

def analyze_tradingview(symbol: str = "MNQ", prompt: str = ""):
    try:
        symbol = symbol.upper()

        capture_result = capture_tradingview(symbol)

        if not capture_result.get("success"):
            return capture_result

        screenshot_path = capture_result["screenshot_path"]

        with open(screenshot_path, "rb") as image_file:
            image_base64 = base64.b64encode(image_file.read()).decode("utf-8")

        vision_prompt = f"""
        You are Jadin's trading assistant.

        Analyze this TradingView screenshot using Jadin's ICT-based trading model.

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
        - If the user drew a box, mention it even if the label is unclear.
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
        - If a label says PDH, PDL, New York High/Low, London High/Low, Asia High/Low, 1H FVG, 4H FVG, or 15M FVG, preserve that label exactly.
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

        FVG priority:
        - Labeled FVGs override your own guesses.
        - If the chart has labels such as "1H FVG", "4H FVG", or "15min FVG", list those first.
        - Do not relabel a marked bullish FVG as supply unless price is clearly rejecting from it.

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
        {prompt or "Analyze the current TradingView chart setup."}
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

        return {
            "success": True,
            "symbol": symbol,
            "model": os.getenv("VISION_MODEL", "qwen2.5vl:7b"),
            "screenshot_path": screenshot_path,
            "message": message + f"\n\nScreenshot saved: `{screenshot_path}`",
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": f"TradingView analysis failed: {e}",
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
    "capture_tradingview": capture_tradingview,
    "setup_tradingview_profile": setup_tradingview_profile,
    "analyze_tradingview": analyze_tradingview,
}