import json
import tempfile
import unittest
from pathlib import Path

import colonia_pages


class CpEscaping(unittest.TestCase):
    def test_crafted_cp_is_escaped_and_slugged(self):
        rows = json.loads(colonia_pages.COLONIAS.read_bytes())
        rows += [["PRUEBA", "Zapopan", '45000<img src=x onerror=alert(1)>', "1"],
                 ["PRUEBA DOS", "Zapopan", "45000", "1"],
                 ["PRUEBA DOS", "Zapopan", '45000"><img src=x onerror=alert(1)>', "1"]]
        with tempfile.TemporaryDirectory() as d:
            fixture = Path(d) / "colonias_mapa.json"
            fixture.write_text(json.dumps(rows, ensure_ascii=False), encoding="utf-8")
            old = colonia_pages.COLONIAS
            colonia_pages.COLONIAS = fixture
            try:
                files = colonia_pages.build()
            finally:
                colonia_pages.COLONIAS = old
        html_out = "".join(t for f, t in files.items() if f.endswith(".html"))
        self.assertNotIn("<img", html_out)
        self.assertIn("&lt;img", files["index.html"])
        self.assertIn("&lt;img", files["municipio-zapopan.html"])
        self.assertFalse([f for f in files if any(c in f for c in '<>"/')], "slug characters leaked into a file name")
        self.assertIn("prueba-dos-zapopan-45000-img-src-x-onerror-alert-1.html", files)


if __name__ == "__main__":
    unittest.main()
