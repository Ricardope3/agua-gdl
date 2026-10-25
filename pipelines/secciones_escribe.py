"""Rebuild the SECCIONES string in web/exige.html from secciones_ine.csv (INE section → Jalisco local district)."""
import csv
import pathlib
import re

root = pathlib.Path(__file__).resolve().parent.parent
with open(root / "pipelines/secciones_ine.csv", encoding="utf-8-sig") as f:
    districts = {int(r["SECCION"]): int(r["DISTRITO_LOCAL"].split()[-1]) for r in csv.DictReader(f)}
assert set(districts.values()) == set(range(1, 21)), "expected districts 1–20"
encoded = "".join("0123456789abcdefghijk"[districts.get(n, 0)] for n in range(1, max(districts) + 1))
page = root / "web/exige.html"
html, count = re.subn(r'const SECCIONES = "[0-9a-k]*";', f'const SECCIONES = "{encoded}";', page.read_text())
assert count == 1, "SECCIONES not found in exige.html"
page.write_text(html)
print(f"{len(districts)} sections, districts 1–20")
