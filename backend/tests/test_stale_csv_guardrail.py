from pathlib import Path
import sys
import unittest
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import scheduled_scan


def _capture_visuals(*, labels=None, notes=None, boxes=None):
    return {
        "visual_extraction": {
            "visuals": {
                "visible_labels": labels or [],
                "drawn_boxes": boxes or [],
                "notes_about_user_markings": notes or [],
            }
        }
    }


def _base_record(*, stale=True, price_relation="below_active_zone", visual_bearish=True):
    visual_notes = [
        "Price has displaced lower below the 1H bullish FVG.",
        "Lost support and bearish displacement lower from the zone.",
    ] if visual_bearish else [
        "Price is holding above the 1H bullish FVG with acceptance.",
    ]

    return {
        "symbol": "MNQ",
        "message": "HTF remains bullish. Execution is bearish.",
        "vision_success": True,
        "csv_success": True,
        "state": {
            "htf_bias": "bullish",
            "execution_bias": "bearish" if visual_bearish else "bullish",
            "price_relation": price_relation,
            "vision_success": True,
            "csv_success": True,
        },
        "csv_freshness": {
            "1M": {
                "is_stale": stale,
                "age_minutes": 151,
                "threshold_minutes": 10,
            },
            "15M": {
                "is_stale": stale,
                "age_minutes": 151,
                "threshold_minutes": 30,
            },
        },
        "csv_analysis": {
            "success": True,
            "analysis": {
                "context": {
                    "bias": "bullish",
                    "execution_bias": "bearish" if visual_bearish else "bullish",
                    "current_price": 30294.75,
                },
                "zone_ranking": {
                    "active_zone": {
                        "timeframe": "1H",
                        "type": "bullish",
                        "low": 30280.0,
                        "high": 30310.0,
                        "relation_to_price": price_relation,
                    },
                    "all_ranked_zones": [
                        {
                            "timeframe": "1H",
                            "type": "bullish",
                            "low": 30280.0,
                            "high": 30310.0,
                        }
                    ],
                },
            },
        },
        "liquidity_draw": {
            "primary_draw": {
                "key": "pdh",
                "label": "PDH",
                "side": "above",
                "price": 30380.0,
                "untouched": True,
            },
            "confidence": "medium",
            "candidates": [],
        },
        "timeframe_captures": {
            "15M": _capture_visuals(
                labels=["1H bullish FVG"],
                notes=visual_notes,
                boxes=[
                    {
                        "label": "1H bullish FVG",
                        "location_notes": "Price is below this FVG support zone.",
                        "low": 30280.0,
                        "high": 30310.0,
                    }
                ],
            ),
            "5M": _capture_visuals(
                notes=["5M displacement lower and market structure shift below support."]
                if visual_bearish
                else ["5M reclaimed and holding above the FVG."],
            ),
        },
        "news_risk": {"risk": "Low"},
    }


class StaleCsvGuardrailTests(unittest.TestCase):
    def _attach_behavior(self, record):
        with patch.object(scheduled_scan, "_get_csv_refresh_limitation", return_value=None):
            scheduled_scan.attach_behavior_classification(record)
        return record["behavior_classification"]

    def test_stale_csv_live_price_below_bullish_zone_marks_not_active_support(self):
        record = _base_record()
        behavior = self._attach_behavior(record)

        self.assertTrue(behavior["stale_csv_guardrail"]["applies"])
        self.assertEqual(behavior["stale_csv_guardrail"]["zone_status"], "failed_support")
        self.assertEqual(scheduled_scan._reaction_zone_status(record), "failed_support")

    def test_stale_csv_live_price_below_bullish_zone_requires_reclaim(self):
        record = _base_record()
        behavior = self._attach_behavior(record)
        scheduled_scan.attach_narrative_scanner_state(record)

        self.assertEqual(
            behavior["stale_csv_guardrail"]["execution_readiness"],
            "no_long_until_reclaim",
        )
        self.assertEqual(record["narrative"]["execution_readiness"], "no_long_until_reclaim")
        self.assertIn("reclaim", record["narrative"]["invalidation_context"].lower())

    def test_stale_csv_bearish_visual_behavior_blocks_bullish_execution_watch(self):
        record = _base_record()
        self._attach_behavior(record)
        scheduled_scan.attach_opportunity_watch(record)
        scheduled_scan.attach_narrative_scanner_state(record)

        self.assertNotEqual(record["opportunity_watch"]["opportunity_type"], "bullish_continuation_watch")
        self.assertNotEqual(record["narrative"]["narrative_phase"], "execution_watch")
        self.assertIn(
            record["behavior_classification"]["classification"],
            {"rejection", "displacement"},
        )

    def test_stale_csv_warning_appears_in_summary(self):
        record = _base_record()
        record["message"] = "\n".join([
            record["message"],
            "MNQ bullish setup: price reacting near 4H/1H bullish FVG.",
            "Plan: to buy reclaim and respect 4H/1H FVG.",
        ])
        self._attach_behavior(record)

        self.assertIn("CSV is stale; using CSV only for structural context.", record["message"])
        self.assertIn("Live vision is primary for current price and zone interaction.", record["message"])
        self.assertIn("Stale CSV Guardrail", record["message"])
        self.assertNotIn("bullish setup", record["message"].lower())
        self.assertNotIn("price reacting near", record["message"].lower())
        self.assertNotIn("to buy reclaim", record["message"].lower())

    def test_fresh_csv_behavior_remains_unchanged(self):
        record = _base_record(stale=False, price_relation="inside_active_zone", visual_bearish=False)
        behavior = self._attach_behavior(record)

        self.assertFalse(behavior["stale_csv_guardrail"]["applies"])
        self.assertEqual(behavior["stale_csv_guardrail"]["zone_status"], "unclear")
        self.assertNotIn("Stale CSV Guardrail", record["message"])


if __name__ == "__main__":
    unittest.main()
