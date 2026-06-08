from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import scanner_settings
import scheduled_scan
from main import ScannerSettingsRequest, force_scan, update_scanner_settings


class ScannerEnabledSettingTests(unittest.TestCase):
    def setUp(self):
        self._tempdir = tempfile.TemporaryDirectory()
        self.settings_path = Path(self._tempdir.name) / "scanner_settings.json"
        self.runtime_path = Path(self._tempdir.name) / "scan_runtime_status.json"
        self._settings_patch = patch.object(
            scanner_settings,
            "SCANNER_SETTINGS_PATH",
            self.settings_path,
        )
        self._scheduled_settings_patch = patch.object(
            scheduled_scan,
            "SCAN_RUNTIME_STATUS_PATH",
            self.runtime_path,
        )
        self._settings_patch.start()
        self._scheduled_settings_patch.start()

    def tearDown(self):
        self._scheduled_settings_patch.stop()
        self._settings_patch.stop()
        self._tempdir.cleanup()

    def test_scanner_settings_default_includes_enabled_true(self):
        settings = scanner_settings.get_scanner_settings()

        self.assertEqual(settings["default_symbol"], "MES")
        self.assertTrue(settings["scanner_enabled"])

    def test_post_scanner_enabled_false_persists(self):
        response = update_scanner_settings(
            ScannerSettingsRequest(scanner_enabled=False)
        )

        self.assertTrue(response["success"])
        self.assertFalse(response["scanner_enabled"])
        self.assertFalse(scanner_settings.get_scanner_settings()["scanner_enabled"])

    def test_scheduled_iteration_skips_automatic_scan_when_disabled(self):
        scanner_settings.set_scanner_settings(scanner_enabled=False)

        with patch.object(scheduled_scan, "run_scan") as run_scan:
            record = scheduled_scan.run_scheduled_scan_iteration()

        self.assertIsNone(record)
        run_scan.assert_not_called()

    def test_force_scan_still_runs_when_scanner_disabled(self):
        scanner_settings.set_scanner_settings(scanner_enabled=False)
        fake_record = {
            "success": True,
            "symbol": "MES",
            "message": "Manual scan completed.",
        }

        with patch.object(scheduled_scan, "run_scan", return_value=fake_record) as run_scan:
            response = force_scan()

        self.assertEqual(response["message"], "Manual scan completed.")
        run_scan.assert_called_once()
        self.assertTrue(run_scan.call_args.kwargs["force"])

    def test_status_reflects_disabled_state(self):
        scanner_settings.set_scanner_settings(scanner_enabled=False)

        status = scheduled_scan.get_scanner_runtime_status()

        self.assertFalse(status["scanner_enabled"])
        self.assertTrue(status["automatic_scans_paused"])
        self.assertFalse(status["scheduled_scan_allowed"])


if __name__ == "__main__":
    unittest.main()
