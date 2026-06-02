import json
import unittest
from unittest.mock import MagicMock, patch

import wake_listener


class WakeListenerTests(unittest.TestCase):
    def test_detects_supported_wake_phrases_after_normalization(self):
        self.assertTrue(wake_listener.contains_wake_phrase("Good morning, Helix."))
        self.assertTrue(wake_listener.contains_wake_phrase("okay morning helix"))
        self.assertTrue(wake_listener.contains_wake_phrase("start my morning please"))
        self.assertFalse(wake_listener.contains_wake_phrase("hello helix"))

    def test_cooldown_prevents_duplicate_backend_calls(self):
        state = wake_listener.ListenerState()
        transcript = wake_listener.TranscriptResult(
            text="good morning helix",
            source="test",
        )

        with patch.object(wake_listener, "call_morning_checkin", return_value={"success": True}) as call:
            first = wake_listener.handle_transcript(
                transcript,
                backend_url="http://127.0.0.1:8000",
                cooldown_seconds=30,
                state=state,
                now=100.0,
            )
            second = wake_listener.handle_transcript(
                transcript,
                backend_url="http://127.0.0.1:8000",
                cooldown_seconds=30,
                state=state,
                now=110.0,
            )

        self.assertTrue(first)
        self.assertFalse(second)
        call.assert_called_once_with("http://127.0.0.1:8000")

    def test_morning_checkin_post_uses_voice_and_speak_true(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(
            {"success": True}
        ).encode("utf-8")

        with patch.object(wake_listener, "urlopen", return_value=response) as urlopen:
            result = wake_listener.call_morning_checkin("http://example.test")

        self.assertEqual(result, {"success": True})
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://example.test/agents/morning/check-in")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(
            json.loads(request.data.decode("utf-8")),
            {"source": "voice", "speak": True},
        )


if __name__ == "__main__":
    unittest.main()
