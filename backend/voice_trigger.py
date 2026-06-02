#!/usr/bin/env python3
"""Manual push-to-talk voice trigger prototype for Helix morning check-in."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
MORNING_ENDPOINT = "/agents/morning/check-in"
TRIGGER_PHRASES = (
    "good morning helix",
    "morning helix",
    "start my morning",
)


@dataclass
class TranscriptResult:
    text: str
    source: str


def normalize_text(text: str) -> str:
    lowered = text.strip().lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def is_morning_trigger(text: str) -> bool:
    normalized = normalize_text(text)
    return any(phrase in normalized for phrase in TRIGGER_PHRASES)


def print_audio_setup_instructions(reason: str) -> None:
    print(f"Audio/STT unavailable: {reason}")
    print()
    print("Typed fallback is available now:")
    print('  python3 backend/voice_trigger.py --text "good morning helix"')
    print()
    print("Optional local microphone/STT setup:")
    print("  python3 -m pip install SpeechRecognition PyAudio pocketsphinx")
    print()
    print("Notes:")
    print("- SpeechRecognition handles microphone capture.")
    print("- PyAudio provides microphone access on many systems.")
    print("- pocketsphinx enables local/offline transcription.")


def transcribe_from_microphone(duration: int) -> TranscriptResult | None:
    try:
        import speech_recognition as sr  # type: ignore[import-not-found]
    except ImportError as exc:
        print_audio_setup_instructions("missing SpeechRecognition")
        return prompt_for_typed_fallback()

    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as microphone:
            print(f"Listening for up to {duration} seconds. Say a trigger phrase now.")
            recognizer.adjust_for_ambient_noise(microphone, duration=0.5)
            audio = recognizer.listen(
                microphone,
                timeout=duration,
                phrase_time_limit=duration,
            )
    except Exception as exc:
        print_audio_setup_instructions(f"microphone capture failed ({type(exc).__name__}: {exc})")
        return prompt_for_typed_fallback()

    try:
        text = recognizer.recognize_sphinx(audio)
    except AttributeError:
        print_audio_setup_instructions("SpeechRecognition does not expose local Sphinx STT")
        return prompt_for_typed_fallback()
    except sr.UnknownValueError:
        print("Could not understand the recorded audio.")
        return prompt_for_typed_fallback()
    except sr.RequestError as exc:
        print_audio_setup_instructions(f"local Sphinx STT unavailable ({exc})")
        return prompt_for_typed_fallback()

    return TranscriptResult(text=text, source="microphone")


def prompt_for_typed_fallback() -> TranscriptResult | None:
    if not sys.stdin.isatty():
        return None

    try:
        text = input("Type trigger text instead, or press Enter to cancel: ").strip()
    except EOFError:
        return None

    if not text:
        return None
    return TranscriptResult(text=text, source="typed fallback")


def call_morning_checkin(backend_url: str) -> dict[str, Any]:
    base_url = backend_url.rstrip("/")
    url = f"{base_url}{MORNING_ENDPOINT}"
    payload = json.dumps({"source": "voice", "speak": True}).encode("utf-8")
    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Morning check-in failed with HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(
            f"Could not reach Helix backend at {url}. Start the backend first."
        ) from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Morning check-in returned invalid JSON: {body}") from exc


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual push-to-talk prototype for Helix morning voice check-in."
    )
    parser.add_argument(
        "--text",
        help="Typed test input. Example: --text 'good morning helix'",
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=5,
        help="Maximum microphone recording duration in seconds. Default: 5.",
    )
    parser.add_argument(
        "--backend-url",
        default=DEFAULT_BACKEND_URL,
        help=f"Helix backend base URL. Default: {DEFAULT_BACKEND_URL}.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    duration = max(1, args.duration)

    if args.text:
        transcript = TranscriptResult(text=args.text, source="typed --text")
    else:
        transcript = transcribe_from_microphone(duration)

    if transcript is None:
        print("No trigger text captured. Morning check-in was not called.")
        return 1

    print(f"Captured ({transcript.source}): {transcript.text}")

    if not is_morning_trigger(transcript.text):
        print("No morning trigger phrase detected. Morning check-in was not called.")
        print("Supported phrases:")
        for phrase in TRIGGER_PHRASES:
            print(f"- {phrase}")
        return 1

    try:
        result = call_morning_checkin(args.backend_url)
    except RuntimeError as exc:
        print(str(exc))
        return 1

    status = "success" if result.get("success") else "unknown"
    print(f"Morning check-in called with source=voice, speak=true ({status}).")
    summary = result.get("summary")
    if summary:
        print()
        print(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
