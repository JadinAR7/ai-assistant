import unittest
from unittest.mock import patch

import imessage_bridge


class IMessageRoutingTests(unittest.TestCase):
    def test_wake_prefixed_say_routes_to_tts(self):
        with patch.object(imessage_bridge, "speak_text", return_value="Speaking now.") as speak:
            reply = imessage_bridge.route_message("Helix say hello Whitney")

        self.assertEqual(reply, "Speaking now.")
        speak.assert_called_once_with("hello Whitney")

    def test_wake_prefixed_speak_routes_to_tts(self):
        with patch.object(imessage_bridge, "speak_text", return_value="Speaking now.") as speak:
            reply = imessage_bridge.route_message("Hey Helix speak market scan complete")

        self.assertEqual(reply, "Speaking now.")
        speak.assert_called_once_with("market scan complete")

    def test_ok_helix_prefix_preserves_latest_scan_intent(self):
        with patch.object(
            imessage_bridge,
            "get_latest_scan_summary",
            return_value="Latest MES scan.",
        ) as latest_scan:
            reply = imessage_bridge.route_message("Ok Helix latest scan")

        self.assertEqual(reply, "Latest MES scan.")
        latest_scan.assert_called_once_with()

    def test_wake_prefixed_chat_falls_back_without_prefix(self):
        with patch.object(imessage_bridge, "ask_helix", return_value="Chat reply.") as chat:
            reply = imessage_bridge.route_message("Helix how should I plan today?")

        self.assertEqual(reply, "Chat reply.")
        chat.assert_called_once_with("how should I plan today?")


if __name__ == "__main__":
    unittest.main()
