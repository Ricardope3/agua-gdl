"""Rebuild the SECCIONES string in web/exige.html from secciones_ine.csv (INE section → Jalisco local district).

    python3 pipelines/secciones_escribe.py            rewrite the string
    python3 pipelines/secciones_escribe.py --check    fail if web/exige.html is stale; write nothing
"""
import csv
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent.parent
PAGE = root / "web/exige.html"
PATTERN = r'const SECCIONES = "[0-9a-k]*";'


def main(argv):
    with open(root / "pipelines/secciones_ine.csv", encoding="utf-8-sig") as f:
        districts = {int(r["SECCION"]): int(r["DISTRITO_LOCAL"].split()[-1]) for r in csv.DictReader(f)}
    assert set(districts.values()) == set(range(1, 21)), "expected districts 1–20"
    encoded = "".join("0123456789abcdefghijk"[districts.get(n, 0)] for n in range(1, max(districts) + 1))
    old = PAGE.read_text()
    html, count = re.subn(PATTERN, f'const SECCIONES = "{encoded}";', old)
    assert count == 1, "SECCIONES not found in exige.html"
    if "--check" in argv:
        if html != old:
            sys.exit("secciones: web/exige.html is stale; run python3 pipelines/secciones_escribe.py")
        print(f"web/exige.html up to date: {len(districts)} sections, districts 1–20")
        return
    PAGE.write_text(html)
    print(f"{len(districts)} sections, districts 1–20")


if __name__ == "__main__":
    main(sys.argv[1:])
