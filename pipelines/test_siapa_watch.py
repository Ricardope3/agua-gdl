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

    def test_hostile_zone_key_is_rendered_as_inline_code(self):
        key = "1\n::warning::hola\n@octocat [x](https://example.invalid) <img src=x>"
        with tempfile.TemporaryDirectory() as directory:
            rotation = Path(directory) / "rotation.json"
            rotation.write_text(json.dumps({"zones": {"1": ["fri"]}}))
            body = json.dumps({"zonas": {key: {"dias": ["lunes"]}}, "colonias": {}}).encode()
            with patch.object(siapa_watch, "ROTATION", rotation):
                text, differs = siapa_watch.days_report(body)
        self.assertTrue(differs)
        self.assertEqual(len(text.splitlines()), 1)
        self.assertIn(siapa_watch.code(key, 60), text)
        outside_code = "".join(text.split("`")[::2])
        for hostile in ("::warning::", "@octocat", "[x](", "<img"):
            self.assertNotIn(hostile, outside_code)


if __name__ == "__main__":
    unittest.main()
