from datetime import date
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.orbit import database as orbit_database
from backend.orbit import service as orbit_service
from backend.orbit import trade_journal_import
from backend.orbit.models import (
    TradeJournalCreate,
    TradeJournalImportDraft,
    TradeJournalImportSaveRequest,
    TradeJournalUpdate,
)


class IsolatedOrbitDbTestCase(unittest.TestCase):
    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tempdir.name) / "assistant.db"
        self._db_patch = patch.object(orbit_database, "DB_PATH", self.db_path)
        self._db_patch.start()
        orbit_database.init_orbit_db()

    def tearDown(self):
        self._db_patch.stop()
        self._tempdir.cleanup()


class TradeJournalCrudTests(IsolatedOrbitDbTestCase):
    def test_create_list_get_update_delete_trade_journal_entry(self):
        created = orbit_service.create_trade_journal_entry(
            TradeJournalCreate(
                trade_date=date(2026, 6, 4),
                symbol="mnq",
                direction="Long",
                entry_price=30700.25,
                stop_loss=30688.0,
                take_profit=30742.0,
                exit_price=30736.75,
                result_dollars=146.0,
                result_r=1.8,
                contracts=2,
                session="London",
                htf_bias="Bullish",
                strategy_profile="Liquidity Narrative Continuation",
                strategy_mode="Scalp",
                draw_on_liquidity=["Asia High", "PDH"],
                reaction_zone="1H FVG",
                behavior_tags=["Reclaim", "Displacement"],
                execution_tags=["BRTC", "1M FVG retest"],
                why_taken="Price reclaimed the reaction zone after drawing into Asia High.",
                price_intent="Continue toward buy-side liquidity.",
                liquidity_target="PDH",
                went_well="Waited for reclaim before execution.",
                went_wrong="Entry was slightly late.",
                lesson_learned="Wait for reclaim, then execute without chasing.",
                screenshot_path="/tmp/chart.png",
                csv_path="/tmp/mnq.csv",
            )
        )

        self.assertEqual(created["symbol"], "MNQ")
        self.assertEqual(created["direction"], "Long")
        self.assertEqual(created["entry_price"], 30700.25)
        self.assertEqual(created["exit_price"], 30736.75)
        self.assertEqual(created["result_dollars"], 146.0)
        self.assertEqual(created["strategy_profile"], "Liquidity Narrative Continuation")
        self.assertEqual(created["strategy_mode"], "Scalp")
        self.assertEqual(created["session"], "London")
        self.assertEqual(created["why_taken"], "Price reclaimed the reaction zone after drawing into Asia High.")
        self.assertEqual(created["price_intent"], "Continue toward buy-side liquidity.")
        self.assertEqual(created["liquidity_target"], "PDH")
        self.assertEqual(created["went_well"], "Waited for reclaim before execution.")
        self.assertEqual(created["went_wrong"], "Entry was slightly late.")
        self.assertEqual(created["lesson_learned"], "Wait for reclaim, then execute without chasing.")
        self.assertEqual(created["draw_on_liquidity"], ["Asia High", "PDH"])
        self.assertEqual(created["behavior_tags"], ["Reclaim", "Displacement"])
        self.assertEqual(created["execution_tags"], ["BRTC", "1M FVG retest"])

        listed = orbit_service.list_trade_journal_entries()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], created["id"])

        detail = orbit_service.get_trade_journal_entry(created["id"])
        self.assertIsNotNone(detail)
        self.assertEqual(detail["symbol"], "MNQ")
        self.assertEqual(detail["session"], "London")

        updated = orbit_service.update_trade_journal_entry(
            created["id"],
            TradeJournalUpdate(
                direction="Short",
                entry_price=30710.0,
                exit_price=30690.5,
                result_dollars=-78.0,
                strategy_mode="Day Trade",
                session="New York",
                why_taken="Reversal attempt after failure to hold above liquidity.",
                went_wrong="Took it before structure confirmed.",
                lesson_learned="Do not short without confirmation after a bullish draw.",
            ),
        )

        self.assertIsNotNone(updated)
        self.assertEqual(updated["symbol"], "MNQ")
        self.assertEqual(updated["direction"], "Short")
        self.assertEqual(updated["entry_price"], 30710.0)
        self.assertEqual(updated["exit_price"], 30690.5)
        self.assertEqual(updated["result_dollars"], -78.0)
        self.assertEqual(updated["strategy_profile"], "Liquidity Narrative Continuation")
        self.assertEqual(updated["strategy_mode"], "Day Trade")
        self.assertEqual(updated["session"], "New York")
        self.assertEqual(updated["why_taken"], "Reversal attempt after failure to hold above liquidity.")
        self.assertEqual(updated["went_wrong"], "Took it before structure confirmed.")
        self.assertEqual(updated["lesson_learned"], "Do not short without confirmation after a bullish draw.")

        self.assertTrue(orbit_service.delete_trade_journal_entry(created["id"]))
        self.assertIsNone(orbit_service.get_trade_journal_entry(created["id"]))
        self.assertEqual(orbit_service.list_trade_journal_entries(), [])


class TradeJournalImportSaveTests(IsolatedOrbitDbTestCase):
    def test_selected_import_draft_is_saved_and_unselected_draft_is_skipped(self):
        selected_draft = TradeJournalImportDraft(
            draft_id="draft-1",
            selected=True,
            trade_date=date(2026, 6, 4),
            symbol="MNQ",
            direction="Long",
            quantity=4,
            contracts=2,
            entry_price=30685.0,
            exit_price=30732.5,
            pnl=380.0,
            session="London",
            htf_bias="Bullish",
            draw_on_liquidity=["Asia High"],
            reaction_zone="1H FVG",
            behavior_tags=["Reclaim"],
            execution_tags=["BRTC"],
            why_taken="Imported trade had continuation context after reclaim.",
            price_intent="Move into buy-side liquidity.",
            liquidity_target="PDH",
            went_well="Stayed patient through the pullback.",
            went_wrong="Entry could have been tighter.",
            lesson_learned="Keep requiring reclaim before execution.",
            screenshot_path="/tmp/import-chart.png",
            csv_path="/tmp/import.csv",
        )
        skipped_draft = TradeJournalImportDraft(
            draft_id="draft-2",
            selected=False,
            trade_date=date(2026, 6, 4),
            symbol="MNQ",
            direction="Short",
            quantity=1,
            contracts=1,
            entry_price=30750.0,
            exit_price=30760.0,
            pnl=-40.0,
            session="New York",
            htf_bias="Bearish",
            draw_on_liquidity=["PDL"],
            reaction_zone="15M FVG",
            behavior_tags=["Rejection"],
            execution_tags=["MSS after displacement"],
            why_taken="This skipped draft should not be saved.",
            price_intent="Move lower.",
            liquidity_target="PDL",
            went_well="Nothing.",
            went_wrong="Skipped.",
            lesson_learned="Skipped draft should stay out of journal.",
        )

        result = trade_journal_import.save_trade_journal_import(
            TradeJournalImportSaveRequest(
                trade_drafts=[selected_draft, skipped_draft],
            )
        )

        self.assertEqual(len(result["created_entries"]), 1)
        self.assertEqual(result["warnings"], [])

        saved = result["created_entries"][0]
        self.assertEqual(saved["symbol"], "MNQ")
        self.assertEqual(saved["direction"], "Long")
        self.assertEqual(saved["entry_price"], 30685.0)
        self.assertEqual(saved["exit_price"], 30732.5)
        self.assertEqual(saved["result_dollars"], 380.0)
        self.assertEqual(saved["contracts"], 2)
        self.assertEqual(saved["session"], "London")
        self.assertEqual(saved["strategy_profile"], "Liquidity Narrative Continuation")
        self.assertEqual(saved["strategy_mode"], "Hybrid / Review")
        self.assertEqual(saved["htf_bias"], "Bullish")
        self.assertEqual(saved["draw_on_liquidity"], ["Asia High"])
        self.assertEqual(saved["reaction_zone"], "1H FVG")
        self.assertEqual(saved["behavior_tags"], ["Reclaim"])
        self.assertEqual(saved["execution_tags"], ["BRTC"])
        self.assertEqual(saved["why_taken"], "Imported trade had continuation context after reclaim.")
        self.assertEqual(saved["price_intent"], "Move into buy-side liquidity.")
        self.assertEqual(saved["liquidity_target"], "PDH")
        self.assertEqual(saved["went_well"], "Stayed patient through the pullback.")
        self.assertEqual(saved["went_wrong"], "Entry could have been tighter.")
        self.assertEqual(saved["lesson_learned"], "Keep requiring reclaim before execution.")
        self.assertEqual(saved["screenshot_path"], "/tmp/import-chart.png")
        self.assertEqual(saved["csv_path"], "/tmp/import.csv")

        listed = orbit_service.list_trade_journal_entries()
        self.assertEqual(len(listed), 1)
        self.assertEqual(listed[0]["id"], saved["id"])
        self.assertNotEqual(listed[0]["direction"], "Short")
        self.assertNotEqual(listed[0]["why_taken"], "This skipped draft should not be saved.")


if __name__ == "__main__":
    unittest.main()
