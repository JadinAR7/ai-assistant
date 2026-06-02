import os
import unittest
from unittest.mock import patch

import tts
from tts import format_text_for_speech


class TTSFormatterTests(unittest.TestCase):
    def test_semicolons_become_sentence_breaks(self):
        self.assertEqual(
            format_text_for_speech("First thing; second thing"),
            "First thing. second thing",
        )

    def test_markdown_bullets_are_removed(self):
        self.assertEqual(
            format_text_for_speech("- First item\n* Second item"),
            "First item Second item",
        )

    def test_arrows_become_to(self):
        self.assertEqual(
            format_text_for_speech("Financial: 0% → 20%"),
            "Financial is 0 percent to 20 percent",
        )

    def test_headings_are_stripped(self):
        self.assertEqual(
            format_text_for_speech("## Morning Briefing\nReadiness: 11% overall"),
            "Morning Briefing Readiness is 11 percent overall",
        )

    def test_top_priority_task_label_is_conversational(self):
        self.assertEqual(
            format_text_for_speech(
                "Top Priority Task: Create first review checklist"
            ),
            "Your top priority is Create first review checklist",
        )

    def test_strategic_gaps_label_is_pause_friendly(self):
        self.assertEqual(
            format_text_for_speech("Strategic Gaps:\n1. Create business launch plan"),
            "Strategic gaps. Create business launch plan",
        )

    def test_empty_text_raises(self):
        with self.assertRaises(ValueError):
            format_text_for_speech("   ")

    def test_parse_say_voices_handles_multiword_voice(self):
        voices = tts.parse_say_voices(
            "Good News            en_US    # Hello from Good News\n"
            "Alex                 en_US    # Most people recognize me\n"
        )

        self.assertEqual(voices[0]["voice"], "Good News")
        self.assertEqual(voices[0]["language"], "en_US")
        self.assertEqual(voices[0]["description"], "Hello from Good News")
        self.assertEqual(voices[1]["voice"], "Alex")

    def test_config_defaults_rate_and_formatter(self):
        with patch.dict(os.environ, {}, clear=True):
            config = tts.get_tts_config()

        self.assertIsNone(config["configured_voice"])
        self.assertIsNone(config["configured_rate"])
        self.assertEqual(config["rate"], 190)
        self.assertTrue(config["formatter_enabled"])

    def test_config_uses_valid_env_voice_and_rate(self):
        with patch.dict(
            os.environ,
            {"HELIX_TTS_VOICE": "Alex", "HELIX_TTS_RATE": "185"},
            clear=True,
        ):
            with patch.object(
                tts,
                "list_macos_voices",
                return_value=[{"voice": "Alex", "language": "en_US"}],
            ):
                config = tts.get_tts_config()

        self.assertEqual(config["configured_voice"], "Alex")
        self.assertEqual(config["voice"], "Alex")
        self.assertEqual(config["configured_rate"], 185)
        self.assertEqual(config["rate"], 185)
        self.assertTrue(config["voice_valid"])

    def test_config_falls_back_for_invalid_voice_and_rate(self):
        with patch.dict(
            os.environ,
            {"HELIX_TTS_VOICE": "NotARealVoice", "HELIX_TTS_RATE": "fast"},
            clear=True,
        ):
            with patch.object(
                tts,
                "list_macos_voices",
                return_value=[{"voice": "Alex", "language": "en_US"}],
            ):
                config = tts.get_tts_config()

        self.assertEqual(config["configured_voice"], "NotARealVoice")
        self.assertIsNone(config["voice"])
        self.assertIsNone(config["configured_rate"])
        self.assertEqual(config["rate"], 190)
        self.assertFalse(config["voice_valid"])
        self.assertFalse(config["rate_valid"])

    def test_speak_text_uses_safe_say_arguments(self):
        with patch.dict(
            os.environ,
            {"HELIX_TTS_VOICE": "Alex", "HELIX_TTS_RATE": "185"},
            clear=True,
        ):
            with patch.object(
                tts,
                "list_macos_voices",
                return_value=[{"voice": "Alex", "language": "en_US"}],
            ):
                with patch.object(tts.subprocess, "Popen") as popen:
                    speech = tts.speak_text_with_metadata("Readiness: 11%")

        self.assertEqual(speech["spoken_text"], "Readiness is 11 percent")
        self.assertEqual(speech["voice"], "Alex")
        self.assertEqual(speech["rate"], 185)
        popen.assert_called_once()
        self.assertEqual(
            popen.call_args.args[0],
            ["say", "-v", "Alex", "-r", "185", "Readiness is 11 percent"],
        )


if __name__ == "__main__":
    unittest.main()
