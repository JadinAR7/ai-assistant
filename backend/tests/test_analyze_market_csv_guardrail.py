import unittest

from backend.tools import format_deterministic_market_summary, format_market_response


def _zone(timeframe="1H", zone_type="bullish", relation="overhead"):
    return {
        "timeframe": timeframe,
        "type": zone_type,
        "low": 30280.0,
        "high": 30310.0,
        "midpoint": 30295.0,
        "relation_to_price": relation,
    }


def _analysis(*, stale=True, execution_bias="bearish"):
    csv_freshness = {
        "1M": {
            "is_stale": stale,
            "latest_csv_time": "2026-06-04T17:00:00Z",
            "age_minutes": 203.4,
            "threshold_minutes": 10,
        },
        "15M": {
            "is_stale": stale,
            "latest_csv_time": "2026-06-04T17:00:00Z",
            "age_minutes": 203.4,
            "threshold_minutes": 30,
        },
        "1H": {
            "is_stale": stale,
            "latest_csv_time": "2026-06-04T17:00:00Z",
            "age_minutes": 203.4,
            "threshold_minutes": 120,
        },
    }
    bullish_zone = _zone("1H", "bullish", "overhead")

    return {
        "success": True,
        "symbol": "MNQ",
        "context": {
            "bias": "bullish",
            "bias_timeframe": "1D",
            "execution_bias": execution_bias,
            "current_price": 30294.75,
        },
        "daily": {"timeframe": "1D", "ranked_fvgs": [bullish_zone]},
        "h4": {"timeframe": "4H", "ranked_fvgs": [bullish_zone], "bias": "bullish"},
        "htf": {"timeframe": "1H", "ranked_fvgs": [bullish_zone], "bias": "bullish"},
        "mtf": {"timeframe": "15M", "ranked_fvgs": [bullish_zone], "structure": "bearish_internal_structure"},
        "ltf": {"timeframe": "1M", "ranked_fvgs": [bullish_zone], "structure": "bearish_breakdown"},
        "csv_freshness": csv_freshness,
        "trade_plan": {
            "targets": {
                "above": [30350.0],
                "below": [30213.75],
            }
        },
    }


class AnalyzeMarketCsvGuardrailTests(unittest.TestCase):
    def test_stale_csv_close_is_not_described_as_live_current_price(self):
        message = format_market_response(_analysis(stale=True))

        self.assertIn("Stale CSV reference close is **30294.75**", message)
        self.assertIn("Live chart/vision is primary for current price", message)
        self.assertNotIn("CSV 1M close is around **30294.75**", message)

    def test_stale_csv_bearish_execution_does_not_produce_bullish_leading_summary(self):
        message = format_market_response(_analysis(stale=True, execution_bias="bearish"))
        first_line = message.splitlines()[0]

        self.assertNotIn("Main context is **bullish**", first_line)
        self.assertIn(
            "1D structure remains bullish, but 4H/1H/15M/1M execution context is bearish or reclaim-needed.",
            message,
        )

    def test_stale_csv_warning_appears_in_analyze_market_csv_message(self):
        message = format_market_response(_analysis(stale=True))

        self.assertIn("Warning: 1M CSV is stale", message)
        self.assertIn("CSV is stale; using CSV only for structural context.", message)
        self.assertIn("Live chart/vision is primary for current price and zone interaction.", message)

    def test_stale_bullish_fvg_above_price_is_overhead_reclaim_zone(self):
        message = format_market_response(_analysis(stale=True))

        self.assertIn("overhead reclaim zone by stale CSV reference", message)
        self.assertNotIn("primary HTF battlefield", message)

    def test_fresh_csv_behavior_remains_unchanged(self):
        message = format_market_response(_analysis(stale=False, execution_bias="bullish"))

        self.assertIn("Main context is **bullish**", message)
        self.assertIn("CSV 1M close is around **30294.75**", message)
        self.assertNotIn("Stale CSV reference close", message)

    def test_chart_summary_prefers_vision_price_when_csv_is_stale(self):
        analysis = _analysis(stale=True)
        zone = _zone("1H", "bullish", "overhead")
        merged_state = {
            "success": True,
            "symbol": "MNQ",
            "csv_state": {
                "context": analysis["context"],
                "csv_freshness": analysis["csv_freshness"],
                "trade_plan": analysis["trade_plan"],
                "targets": analysis["trade_plan"]["targets"],
                "zone_ranking": {
                    "active_zone": zone,
                    "all_ranked_zones": [zone],
                },
                "daily": {"bias": "bullish", "structure": "bullish_internal_structure"},
                "h4": {"bias": "bullish", "structure": "bullish_internal_structure"},
                "htf": {"bias": "bullish", "structure": "bullish_internal_structure"},
                "mtf": {"bias": "bearish", "structure": "bearish_internal_structure"},
                "ltf": {"bias": "bearish", "structure": "bearish_breakdown"},
            },
            "visual_state": {
                "current_price_marker": 30213.75,
                "visible_labels": ["MNQ", "1H bullish FVG"],
                "drawn_boxes": [
                    {
                        "label": "1H bullish FVG",
                        "approx_low": 30280.0,
                        "approx_high": 30310.0,
                    }
                ],
            },
        }

        message = format_deterministic_market_summary(merged_state)

        self.assertIn("stale CSV reference close is 30294.75", message)
        self.assertIn("Vision price estimate is 30213.75", message)
        self.assertIn("Live vision is primary for current price", message)
        self.assertNotIn("MNQ CSV 1M close is around 30294.75", message)


if __name__ == "__main__":
    unittest.main()
