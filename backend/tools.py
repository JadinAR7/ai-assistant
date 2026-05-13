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
MIN_FVG_SIZE = 1.0
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
        df["time"] = pd.to_datetime(df["time"], errors="coerce", utc=True)
        df["time"] = df["time"].dt.tz_localize(None)
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
        daily_df = load_market_csv(daily) if daily else None
        h4_df = load_market_csv(h4) if h4 else None
        htf_df = load_market_csv(htf)
        mtf_df = load_market_csv(mtf)
        ltf_df = load_market_csv(ltf)

        daily_analysis = analyze_dataframe(daily_df) if daily_df is not None else None
        h4_analysis = analyze_dataframe(h4_df) if h4_df is not None else None
        htf_analysis = analyze_dataframe(htf_df)
        mtf_analysis = analyze_dataframe(mtf_df)
        ltf_analysis = analyze_dataframe(ltf_df)

        current_price = ltf_analysis["current_price"]

        zones_by_timeframe = {}

        if daily_analysis:
            zones_by_timeframe["1D"] = (
                daily_analysis.get("bullish_fvgs", [])
                + daily_analysis.get("bearish_fvgs", [])
            )

        if h4_analysis:
            zones_by_timeframe["4H"] = (
                h4_analysis.get("bullish_fvgs", [])
                + h4_analysis.get("bearish_fvgs", [])
            )

        zones_by_timeframe["1H"] = (
            htf_analysis.get("bullish_fvgs", [])
            + htf_analysis.get("bearish_fvgs", [])
        )

        zones_by_timeframe["15M"] = (
            mtf_analysis.get("bullish_fvgs", [])
            + mtf_analysis.get("bearish_fvgs", [])
        )

        zones_by_timeframe["1M"] = (
            ltf_analysis.get("bullish_fvgs", [])
            + ltf_analysis.get("bearish_fvgs", [])
        )

        zone_ranking = rank_fvg_zones(
            current_price=current_price,
            zones_by_timeframe=zones_by_timeframe,
        )

        # Bias hierarchy:
        # Daily > 4H > 1H. If higher TF exists, use it for context.
        if daily_analysis:
            context_bias = daily_analysis["bias"]
            context_timeframe = "1D"
        elif h4_analysis:
            context_bias = h4_analysis["bias"]
            context_timeframe = "4H"
        else:
            context_bias = htf_analysis["bias"]
            context_timeframe = "1H"

        execution_bias = ltf_analysis["bias"]

        if context_bias == "bullish":
            trade_direction = "long"

            candidate_entries = (
                zone_ranking.get("all_ranked_zones", [])
                if zone_ranking
                else mtf_analysis.get("bullish_fvgs", [])
            )

            candidate_entries = [
                zone for zone in candidate_entries
                if zone.get("type") == "bullish"
            ]

            targets = list(dict.fromkeys([
                htf_analysis["recent_high_20"],
                htf_analysis["recent_high_50"],
                h4_analysis["recent_high_20"] if h4_analysis else None,
                daily_analysis["recent_high_20"] if daily_analysis else None,
            ]))

            targets = sorted(set([target for target in targets if target is not None]))

            invalidation = (
                "Below the active bullish FVG or below the liquidity sweep low."
            )

        elif context_bias == "bearish":
            trade_direction = "short"

            candidate_entries = (
                zone_ranking.get("all_ranked_zones", [])
                if zone_ranking
                else mtf_analysis.get("bearish_fvgs", [])
            )

            candidate_entries = [
                zone for zone in candidate_entries
                if zone.get("type") == "bearish"
            ]

            targets = list(dict.fromkeys([
                htf_analysis["recent_low_20"],
                htf_analysis["recent_low_50"],
                h4_analysis["recent_low_20"] if h4_analysis else None,
                daily_analysis["recent_low_20"] if daily_analysis else None,
            ]))

            targets = sorted(set([target for target in targets if target is not None]))

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

            "context": {
                "bias_timeframe": context_timeframe,
                "bias": context_bias,
                "execution_bias": execution_bias,
                "current_price": current_price,
            },

            "daily": {
                "timeframe": "1D",
                **daily_analysis,
            } if daily_analysis else None,

            "h4": {
                "timeframe": "4H",
                **h4_analysis,
            } if h4_analysis else None,

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