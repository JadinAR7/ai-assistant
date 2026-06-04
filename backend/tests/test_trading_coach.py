import unittest
from unittest.mock import patch

from backend import chat_intents, trading_coach


def full_entry(entry_id: int = 1, **overrides):
    entry = {
        "id": entry_id,
        "trade_date": "2026-06-03",
        "symbol": "MNQ",
        "direction": "Long",
        "result_dollars": 150.0,
        "session": "London",
        "htf_bias": "Bullish",
        "strategy_mode": "Scalp",
        "draw_on_liquidity": ["Asia High"],
        "reaction_zone": "1H FVG",
        "behavior_tags": ["Reclaim", "Displacement"],
        "execution_tags": ["BRTC"],
        "why_taken": "Price reclaimed the reaction zone and continued toward Asia High.",
        "price_intent": "Continue into buy-side liquidity.",
        "liquidity_target": "Asia High",
        "went_well": "Waited for reclaim before execution.",
        "went_wrong": "",
        "lesson_learned": "Wait for reclaim before execution.",
    }
    entry.update(overrides)
    return entry


class TradingCoachReviewTests(unittest.TestCase):
    def test_no_entries_returns_empty_state(self):
        review = trading_coach.generate_trading_coach_review(entries=[])

        self.assertEqual(review["summary"]["total_trades_reviewed"], 0)
        self.assertEqual(
            review["readable_summary"],
            "No journal entries available yet. Import or create trades first.",
        )
        self.assertIn("Import or create trades first", review["missing_data"][0])

    def test_full_strategy_context_produces_stronger_alignment(self):
        full_review = trading_coach.generate_trading_coach_review(
            entries=[full_entry()]
        )
        weak_review = trading_coach.generate_trading_coach_review(
            entries=[
                full_entry(
                    htf_bias=None,
                    draw_on_liquidity=[],
                    reaction_zone=None,
                    behavior_tags=[],
                    execution_tags=[],
                    why_taken=None,
                    liquidity_target=None,
                    lesson_learned=None,
                )
            ]
        )

        self.assertEqual(full_review["model_alignment"]["label"], "Strong alignment")
        self.assertGreater(
            full_review["model_alignment"]["score"],
            weak_review["model_alignment"]["score"],
        )
        self.assertEqual(weak_review["model_alignment"]["label"], "Weak alignment")

    def test_missing_narrative_fields_produce_missing_data_warnings(self):
        review = trading_coach.generate_trading_coach_review(
            entries=[
                full_entry(
                    why_taken=None,
                    liquidity_target=None,
                    lesson_learned=None,
                )
            ]
        )

        missing = " ".join(review["missing_data"])
        self.assertIn("narrative explanation missing", missing)
        self.assertIn("target liquidity missing", missing)
        self.assertIn("review/lesson missing", missing)
        self.assertTrue(review["warnings"])

    def test_scalp_and_day_trade_modes_are_counted_separately(self):
        review = trading_coach.generate_trading_coach_review(
            entries=[
                full_entry(entry_id=1, strategy_mode="Scalp"),
                full_entry(entry_id=2, strategy_mode="Day Trade"),
                full_entry(entry_id=3, strategy_mode="Scalp"),
            ]
        )

        distribution = review["summary"]["strategy_mode_distribution"]
        self.assertEqual(distribution["Scalp"], 2)
        self.assertEqual(distribution["Day Trade"], 1)
        self.assertEqual(distribution["Hybrid / Review"], 0)

    def test_command_router_routes_trading_coach_phrases(self):
        fake_review = {
            "readable_summary": "Trading Coach Review\n\nReviewed 1 trade.",
        }
        phrases = [
            "review my trades",
            "how did I trade today",
            "what did I do well trading",
            "what should I improve in my trading",
            "review my trade journal",
            "trading coach review",
        ]
        with patch.object(
            chat_intents.trading_coach,
            "generate_trading_coach_review",
            return_value=fake_review,
        ) as generate_review:
            responses = [chat_intents.route_chat_intent(phrase) for phrase in phrases]

        for response in responses:
            self.assertIsNotNone(response)
            self.assertEqual(response["model"], "intent:trading_coach_review")
            self.assertIn("Reviewed 1 trade", response["message"])
        self.assertEqual(generate_review.call_count, len(phrases))


if __name__ == "__main__":
    unittest.main()
