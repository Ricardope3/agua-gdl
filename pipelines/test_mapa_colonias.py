import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import mapa_colonias


class PlainPropertiesTest(unittest.TestCase):
    def test_unsafe_names_the_keys(self):
        self.assertEqual(mapa_colonias.unsafe({"n": "LOMAS INDEPENDENCIA", "m": "Guadalajara", "cp": "44370", "z": "3"}), [])
        self.assertEqual(mapa_colonias.unsafe({"n": "LOMAS", "m": "Guadalajara", "cp": "", "z": ""}), [])
        self.assertEqual(mapa_colonias.unsafe({"n": "LOMAS <b>", "m": "Guadalajara", "cp": "44370"}), ["n"])
        self.assertEqual(mapa_colonias.unsafe({"n": "LOMAS", "m": "Guadalajara\x07", "cp": "4437"}), ["m"])
        for cp in ('45000"><img src=x>', "443701", "abcde", "44 70", 44370.0):
            self.assertEqual(mapa_colonias.unsafe({"n": "LOMAS", "m": "Guadalajara", "cp": cp}), ["cp"], cp)

    def test_check_counts_the_real_map_and_stops_at_a_planted_row(self):
        topo = json.loads(mapa_colonias.SRC.read_bytes())
        total = len(topo["objects"]["colonias"]["geometries"])
        self.assertEqual(mapa_colonias.check_plain(topo), total)
        topo["objects"]["colonias"]["geometries"][99]["properties"]["n"] += " <img src=x onerror=alert(1)>"
        with tempfile.TemporaryDirectory() as d:
            src = Path(d) / "colonias_siapa.topo.json"
            src.write_text(json.dumps(topo), encoding="utf-8")
            with patch.object(mapa_colonias, "SRC", src), self.assertRaises(SystemExit) as cm:
                mapa_colonias.check_plain(json.loads(src.read_bytes()))
        self.assertIn("['n']", str(cm.exception))
        self.assertIn("100 properties examined", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
