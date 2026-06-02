from __future__ import annotations

import os
import re
import subprocess
from typing import Any


MAX_SPOKEN_TEXT_LENGTH = 500
DEFAULT_TTS_RATE = 190
URL_PATTERN = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
SHORT_LABEL_PATTERN = re.compile(r"\b([A-Z][A-Za-z ]{1,32}):\s*")
VOICE_LINE_PATTERN = re.compile(
    r"^(?P<voice>.+?)\s+(?P<locale>[a-z]{2}_[A-Z]{2})\s+#\s*(?P<description>.*)$"
)


def _replace_short_label(match: re.Match[str]) -> str:
    label = " ".join(match.group(1).split())
    lower_label = label.lower()

    if lower_label == "top priority task":
        return "Your top priority is "
    if lower_label == "strategic gaps":
        return "Strategic gaps. "
    if lower_label in {"blockers", "recommended actions", "secondary tasks"}:
        return f"{label}. "
    if lower_label.startswith(("http", "www")):
        return ""

    return f"{label} is "


def format_text_for_speech(text: str) -> str:
    spoken_text = text.strip()
    if not spoken_text:
        raise ValueError("No text provided.")

    spoken_text = URL_PATTERN.sub("", spoken_text)
    spoken_text = re.sub(r"```[\s\S]*?```", " ", spoken_text)
    spoken_text = spoken_text.replace("`", "")
    spoken_text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", spoken_text)
    spoken_text = re.sub(r"(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+)", "", spoken_text)
    spoken_text = re.sub(r"\s*(?:→|->|=>)\s*", " to ", spoken_text)
    spoken_text = spoken_text.replace("&", " and ")
    spoken_text = re.sub(r"(\d+(?:\.\d+)?)\s*%", r"\1 percent", spoken_text)
    spoken_text = SHORT_LABEL_PATTERN.sub(_replace_short_label, spoken_text)
    spoken_text = spoken_text.replace(";", ".")
    spoken_text = re.sub(r"[{}\[\]]", " ", spoken_text)
    spoken_text = re.sub(r'["“”]', "", spoken_text)
    spoken_text = re.sub(r"\s*,\s*,+", ", ", spoken_text)
    spoken_text = re.sub(r"\s+", " ", spoken_text).strip()

    if not spoken_text:
        raise ValueError("No speakable text provided.")

    if len(spoken_text) > MAX_SPOKEN_TEXT_LENGTH:
        return spoken_text[:MAX_SPOKEN_TEXT_LENGTH].rstrip() + "..."
    return spoken_text


def prepare_spoken_text(text: str) -> str:
    return format_text_for_speech(text)


def parse_say_voices(output: str) -> list[dict[str, str | None]]:
    voices = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = VOICE_LINE_PATTERN.match(line)
        if match:
            voices.append(
                {
                    "voice": match.group("voice"),
                    "language": match.group("locale"),
                    "description": match.group("description").strip(),
                    "raw_line": line,
                }
            )
            continue

        parts = line.split(None, 1)
        voices.append(
            {
                "voice": parts[0],
                "language": None,
                "description": parts[1].strip() if len(parts) > 1 else "",
                "raw_line": line,
            }
        )
    return voices


def list_macos_voices() -> list[dict[str, str | None]]:
    result = subprocess.run(
        ["say", "-v", "?"],
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_say_voices(result.stdout)


def _configured_voice() -> str | None:
    voice = os.getenv("HELIX_TTS_VOICE", "").strip()
    return voice or None


def _configured_rate() -> int | None:
    rate = os.getenv("HELIX_TTS_RATE", "").strip()
    if not rate:
        return None
    try:
        parsed = int(rate)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _voice_is_available(voice: str) -> bool:
    try:
        voices = list_macos_voices()
    except Exception:
        return False
    return any(item.get("voice") == voice for item in voices)


def get_tts_config() -> dict[str, Any]:
    configured_voice = _configured_voice()
    configured_rate = _configured_rate()
    voice = (
        configured_voice
        if configured_voice and _voice_is_available(configured_voice)
        else None
    )
    rate = configured_rate or DEFAULT_TTS_RATE

    return {
        "configured_voice": configured_voice,
        "configured_rate": configured_rate,
        "voice": voice,
        "rate": rate,
        "default_voice": None,
        "default_rate": DEFAULT_TTS_RATE,
        "formatter_enabled": True,
        "voice_valid": configured_voice is None or voice is not None,
        "rate_valid": os.getenv("HELIX_TTS_RATE", "").strip() == ""
        or configured_rate is not None,
    }


def _say_command(spoken_text: str, config: dict[str, Any]) -> list[str]:
    command = ["say"]
    voice = config.get("voice")
    if voice:
        command.extend(["-v", str(voice)])
    command.extend(["-r", str(config["rate"])])
    command.append(spoken_text)
    return command


def speak_text_with_metadata(text: str) -> dict[str, Any]:
    formatted_text = prepare_spoken_text(text)
    config = get_tts_config()
    subprocess.Popen(
        _say_command(formatted_text, config),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    return {
        "original_text": text,
        "formatted_text": formatted_text,
        "spoken_text": formatted_text,
        "voice": config["voice"],
        "rate": config["rate"],
        "configured_voice": config["configured_voice"],
        "configured_rate": config["configured_rate"],
    }


def speak_text(text: str) -> str:
    return str(speak_text_with_metadata(text)["spoken_text"])
