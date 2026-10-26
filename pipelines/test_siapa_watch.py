import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import siapa_watch


class DaysReportTest(unittest.TestCase):
    def test_manual_colonia_override_stays_an_alert_without_day_changes(self):
        with tempfile.TemporaryDirectory() as directory:
            rotation = Path(directory) / "rotation.json"
            rotation.write_text(json.dumps({"zones": {"1": ["fri", "sun"]}}))
            body = json.dumps({"zonas": {"1": {"dias": ["viernes", "domingo"]}}, "colonias": {"COLONIA": "2"}}).encode()
            with patch.object(siapa_watch, "ROTATION", rotation):
                _, differs = siapa_watch.days_report(body)
            self.assertTrue(differs)

    def test_matching_days_without_overrides_are_clear(self):
        with tempfile.TemporaryDirectory() as directory:
            rotation = Path(directory) / "rotation.json"
            rotation.write_text(json.dumps({"zones": {"1": ["fri", "sun"]}}))
            body = json.dumps({"zonas": {"1": {"dias": ["viernes", "domingo"]}}, "colonias": {}}).encode()
            with patch.object(siapa_watch, "ROTATION", rotation):
                _, differs = siapa_watch.days_report(body)
            self.assertFalse(differs)


if __name__ == "__main__":
    unittest.main()
