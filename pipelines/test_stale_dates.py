import datetime as dt
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))
import stale_dates  # noqa: E402

TODAY = dt.date(2026, 11, 3)


def found(name, html):
    return [msg for _, msg in stale_dates.scan_html(name, html, TODAY, 10)]


class ScanHtmlTest(unittest.TestCase):
    def test_old_as_of_dates_are_listed(self):
        got = found("pipas.html", "<p>al 19 de octubre llevaban 40 colonias.</p>\n<p>revisado el 20 de octubre</p>")
        self.assertEqual(got, ["web/pipas.html:1: «al 19 de octubre»", "web/pipas.html:2: «revisado el 20 de octubre»"])

    def test_recent_dates_and_ranges_are_not(self):
        self.assertEqual(found("x.html", "<p>al 29 de octubre; del 15 al 19 de octubre; 5 al 9 de octubre</p>"), [])

    def test_noticias_cards_are_history(self):
        html = "<p>Actualizado el 1 de octubre</p><article>al 1 de octubre</article>"
        self.assertEqual(found("noticias.html", html), ["web/noticias.html:1: «Actualizado el 1 de octubre»"])

    def test_year_without_one_is_the_latest_past(self):
        self.assertEqual(stale_dates.as_of("20", "diciembre", None, TODAY), dt.date(2025, 12, 20))
        self.assertEqual(stale_dates.as_of("26", "octubre", "2026", TODAY), dt.date(2026, 10, 26))


if __name__ == "__main__":
    unittest.main()
