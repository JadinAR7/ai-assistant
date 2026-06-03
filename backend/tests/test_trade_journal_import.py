from pathlib import Path
import unittest

from backend.orbit.trade_journal_import import (
    _enrich_trade_drafts,
    _parse_daily_summary,
    _parse_orders,
    _parse_performance_trades,
)


FIXTURE_DIR = Path(__file__).parent / "fixtures"


class TradeJournalImportParserTests(unittest.TestCase):
    def setUp(self):
        self.performance_text = (FIXTURE_DIR / "performance_20260603.txt").read_text()
        self.orders_text = (FIXTURE_DIR / "orders_20260603.txt").read_text()

    def test_performance_summary_and_trades_parse_from_real_extracted_text(self):
        warnings: list[str] = []
        summary = _parse_daily_summary(self.performance_text, warnings)
        drafts = _parse_performance_trades(self.performance_text, warnings)

        self.assertEqual(summary.trade_count, 3)
        self.assertEqual(summary.contract_count, 24)
        self.assertEqual(summary.expectancy, 132.00)
        self.assertEqual(summary.longest_trade_time, "8min 31sec")

        self.assertEqual(len(drafts), 3)
        self.assertEqual(drafts[0].direction, "Long")
        self.assertEqual(drafts[1].direction, "Long")
        self.assertEqual(drafts[2].direction, "Short")
        self.assertEqual(drafts[0].pnl, 130.00)
        self.assertEqual(drafts[1].pnl, 134.00)
        self.assertEqual(drafts[2].pnl, 132.00)

    def test_orders_enrich_real_performance_trade_drafts(self):
        warnings: list[str] = []
        drafts = _parse_performance_trades(self.performance_text, warnings)
        orders = _parse_orders(self.orders_text, warnings)
        enriched, matched_order_ids = _enrich_trade_drafts(drafts, orders, warnings)

        self.assertEqual(len(orders), 8)
        self.assertEqual(len(matched_order_ids), 8)

        self.assertTrue(enriched[0].limit_entry)
        self.assertTrue(enriched[0].limit_exit)
        self.assertFalse(enriched[0].stop_detected)

        self.assertTrue(enriched[1].limit_entry)
        self.assertTrue(enriched[1].limit_exit)
        self.assertTrue(enriched[1].stop_detected)
        self.assertTrue(enriched[1].stop_canceled)

        self.assertEqual(enriched[2].direction, "Short")
        self.assertTrue(enriched[2].market_entry)
        self.assertTrue(enriched[2].limit_exit)
        self.assertTrue(enriched[2].stop_detected)
        self.assertTrue(enriched[2].stop_canceled)


if __name__ == "__main__":
    unittest.main()
