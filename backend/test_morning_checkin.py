import unittest
from unittest.mock import patch

import morning_checkin


FULL_MORNING_SUMMARY = """Morning Briefing

Corporate Escape is 18% complete with 214 days remaining.
Readiness: 42% overall.

Top Priority Task:
Create first review checklist for Build trading review cadence (P91) - Trading Review

Secondary Tasks:
1. Update dashboard copy (P80)

Strategic Gaps:
1. Build business launch plan (P95)
   - Missing launch offer
   - Missing distribution system
2. Improve trade review cadence (P88)
   - No weekly review rhythm

Blockers:
- Low readiness categories: Financial, Trading.
- No recent Orbit review within the last 2 days.

Recommended Actions:
1. Complete or advance: Create first review checklist for Build trading review cadence.
2. Clear blocker: Low readiness categories.

Next action: Complete or advance: Create first review checklist for Build trading review cadence."""


class MorningBriefingCondenserTests(unittest.TestCase):
    def test_condenser_keeps_spoken_briefing_short_and_selective(self):
        spoken = morning_checkin.condense_morning_summary_for_speech(
            FULL_MORNING_SUMMARY
        )

        self.assertIn("Good morning.", spoken)
        self.assertIn(
            "Corporate Escape is 18 percent complete, with 214 days remaining.",
            spoken,
        )
        self.assertIn("Overall readiness is 42 percent overall.", spoken)
        self.assertIn("Your top priority is to create the first review checklist", spoken)
        self.assertIn("The biggest blocker is low readiness categories", spoken)
        self.assertIn("For focus, complete or advance", spoken)
        self.assertNotIn("Missing launch offer", spoken)
        self.assertLessEqual(spoken.count("."), 7)

    def test_condenser_uses_strategic_gap_when_no_blocker_exists(self):
        summary = FULL_MORNING_SUMMARY.replace(
            "Blockers:\n- Low readiness categories: Financial, Trading.\n- No recent Orbit review within the last 2 days.",
            "Blockers:\n- No active blockers",
        )

        spoken = morning_checkin.condense_morning_summary_for_speech(summary)

        self.assertIn(
            "The biggest strategic gap is build business launch plan.",
            spoken,
        )
        self.assertNotIn("Improve trade review cadence", spoken)

    def test_check_in_preserves_full_summary_and_returns_condensed_spoken_text(self):
        agent_run = {
            "id": 7,
            "summary": FULL_MORNING_SUMMARY,
            "output_json": {},
        }

        with patch.object(
            morning_checkin,
            "ensure_morning_review_output",
            return_value=agent_run,
        ):
            with patch.object(morning_checkin, "_get_day_state") as get_day_state:
                get_day_state.return_value = {
                    "date": "2026-06-02",
                    "morning_acknowledged": False,
                    "morning_acknowledged_at": None,
                    "morning_fallback_sent": False,
                    "morning_fallback_sent_at": None,
                    "morning_agent_run_id": None,
                    "delivery_channel": None,
                }
                with patch.object(morning_checkin, "_save_day_state"):
                    with patch.object(morning_checkin, "get_status", return_value={}):
                        with patch.object(
                            morning_checkin,
                            "speak_text",
                            side_effect=lambda text: text,
                        ) as speak:
                            result = morning_checkin.check_in(
                                source="voice",
                                speak=True,
                            )

        self.assertEqual(result["summary"], FULL_MORNING_SUMMARY)
        self.assertNotEqual(result["spoken_text"], FULL_MORNING_SUMMARY)
        self.assertEqual(result["original_text"], FULL_MORNING_SUMMARY)
        self.assertTrue(result["full_spoken_text_available"])
        self.assertTrue(result["tts_success"])
        speak.assert_called_once_with(result["spoken_text"])


if __name__ == "__main__":
    unittest.main()
