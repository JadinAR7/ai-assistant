#!/usr/bin/env python3
"""Manual wake phrase listener for Helix Morning Check-In."""

from __future__ import annotations

import argparse
import json
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_BACKEND_URL = "http://127.0.0.1:8000"
MORNING_ENDPOINT = "/agents/morning/check-in"
WAKE_PHRASES = (
    "good morning helix",
    "morning helix",
    "start my morning",
)


class DependencyUnavailable(RuntimeError):
    """Raised when local microphone or speech-to-text dependencies are missing."""


@dataclass
class TranscriptResult:
    text: str
    source: str


@dataclass
class ListenerState:
    last_triggered_at: float | None = None


def normalize_text(text: str) -> str:
    lowered = text.strip().lower()
    cleaned = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return re.sub(r"\s+", " ", cleaned).strip()


def contains_wake_phrase(text: str) -> bool:
    normalized = normalize_text(text)
    return any(phrase in normalized for phrase in WAKE_PHRASES)


def print_setup_instructions(reason: str) -> None:
    print(f"Wake listener unavailable: {reason}")
    print()
    print("Install optional local microphone/STT dependencies:")
    print("  python3 -m pip install SpeechRecognition PyAudio pocketsphinx")
    print()
    print("Notes:")
    print("- SpeechRecognition handles microphone capture.")
    print("- PyAudio provides microphone access on many systems.")
    print("- pocketsphinx enables local/offline transcription.")
    print()
    print("Typed simulation is available without microphone dependencies:")
    print('  python3 backend/wake_listener.py --once --text "good morning helix"')


def transcribe_from_microphone(listen_seconds: int) -> TranscriptResult | None:
    try:
        import speech_recognition as sr  # type: ignore[import-not-found]
    except ImportError as exc:
        raise DependencyUnavailable("missing SpeechRecognition") from exc

    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as microphone:
            print("Listening for wake phrase...")
            recognizer.adjust_for_ambient_noise(microphone, duration=0.5)
            try:
                audio = recognizer.listen(
                    microphone,
                    timeout=listen_seconds,
                    phrase_time_limit=listen_seconds,
                )
            except sr.WaitTimeoutError:
                print("No speech detected.")
                return None
    except Exception as exc:
        raise DependencyUnavailable(
            f"microphone capture failed ({type(exc).__name__}: {exc})"
        ) from exc

    try:
        text = recognizer.recognize_sphinx(audio)
    except AttributeError as exc:
        raise DependencyUnavailable("SpeechRecognition does not expose local Sphinx STT") from exc
    except sr.UnknownValueError:
        print("Could not understand the recorded audio.")
        return None
    except sr.RequestError as exc:
        raise DependencyUnavailable(f"local Sphinx STT unavailable ({exc})") from exc

    return TranscriptResult(text=text, source="microphone")


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
            f"Could not reach Helix backend at {url}: {exc.reason}. Start the backend first."
        ) from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Morning check-in returned invalid JSON: {body}") from exc


def should_trigger(state: ListenerState, now: float, cooldown_seconds: int) -> bool:
    if state.last_triggered_at is None:
        return True
    return now - state.last_triggered_at >= cooldown_seconds


def handle_transcript(
    transcript: TranscriptResult,
    *,
    backend_url: str,
    cooldown_seconds: int,
    state: ListenerState,
    now: float | None = None,
) -> bool:
    print(f"Captured ({transcript.source}): {transcript.text}")

    if not contains_wake_phrase(transcript.text):
        print("No wake phrase detected.")
        return False

    current_time = time.monotonic() if now is None else now
    if not should_trigger(state, current_time, cooldown_seconds):
        remaining = int(cooldown_seconds - (current_time - (state.last_triggered_at or current_time)))
        print(f"Wake phrase ignored during cooldown ({max(1, remaining)} seconds remaining).")
        return False

    result = call_morning_checkin(backend_url)
    state.last_triggered_at = current_time

    status = "success" if result.get("success") else "unknown"
    print(f"Morning check-in called with source=voice, speak=true ({status}).")
    summary = result.get("summary")
    if summary:
        print()
        print(summary)
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual wake phrase listener for Helix Morning Check-In."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--once",
        action="store_true",
        help="Listen once, trigger at most once, then exit. Default when --loop is not set.",
    )
    mode.add_argument(
        "--loop",
        action="store_true",
        help="Keep listening until interrupted.",
    )
    parser.add_argument(
        "--cooldown-seconds",
        type=int,
        default=30,
        help="Minimum seconds between backend triggers. Default: 30.",
    )
    parser.add_argument(
        "--backend-url",
        default=DEFAULT_BACKEND_URL,
        help=f"Helix backend base URL. Default: {DEFAULT_BACKEND_URL}.",
    )
    parser.add_argument(
        "--text",
        help="Typed simulation input. Example: --text 'good morning helix'",
    )
    parser.add_argument(
        "--listen-seconds",
        type=int,
        default=5,
        help="Maximum seconds per microphone listen attempt. Default: 5.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cooldown_seconds = max(0, args.cooldown_seconds)
    listen_seconds = max(1, args.listen_seconds)
    state = ListenerState()

    if args.text:
        transcript = TranscriptResult(text=args.text, source="typed --text")
        try:
            return 0 if handle_transcript(
                transcript,
                backend_url=args.backend_url,
                cooldown_seconds=cooldown_seconds,
                state=state,
            ) else 1
        except RuntimeError as exc:
            print(str(exc))
            return 1

    keep_listening = args.loop
    while True:
        try:
            transcript = transcribe_from_microphone(listen_seconds)
        except DependencyUnavailable as exc:
            print_setup_instructions(str(exc))
            return 0

        if transcript is not None:
            try:
                triggered = handle_transcript(
                    transcript,
                    backend_url=args.backend_url,
                    cooldown_seconds=cooldown_seconds,
                    state=state,
                )
            except RuntimeError as exc:
                print(str(exc))
                return 1
            if triggered and not keep_listening:
                return 0

        if not keep_listening:
            return 1


if __name__ == "__main__":
    raise SystemExit(main())
