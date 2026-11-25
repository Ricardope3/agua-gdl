#!/usr/bin/env python3
"""Writes film.html from the ammonia CSV and plantilla.html. Every figure on screen is asserted here."""
import csv, json, pathlib
here = pathlib.Path(__file__).parent
root = here.parents[2]
rows = [r for r in csv.reader(open(root / "web/datos/siapa-dg-135-2026-amoniacal.csv")) if r and r[0][:2] == "20"]
serie = [(m, float(v)) for m, v, _ in rows]
val = dict(serie)
assert len(serie) == 74 and serie[0][0] == "2020-01" and serie[-1][0] == "2026-02"
assert max(serie, key=lambda x: x[1]) == ("2026-01", 3.62)
assert max(v for m, v in serie if m <= "2022-12") == 0.27
assert val["2024-07"] == 2.18
assert 3.62 / 0.5 > 7
html = (here / "plantilla.html").read_text().replace("/*SERIE*/[]", json.dumps(serie))
(here / "film.html").write_text(html)
print("film.html", len(html), "bytes;", len(serie), "meses")
