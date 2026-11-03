#!/usr/bin/env python3
"""List dated "as of" claims in the site's copy and data that are older than a few days.

    python3 scripts/stale_dates.py [--days N] [--count]

Copy: «al 19 de octubre», «revisado el…», «Actualizado el…» in web/*.html (date ranges like
«del 15 al 26» and /noticias' dated cards don't count). Data: `checked` in rotation.json and
zones.json, `actualizado` and each `veredicto_fecha` in promesas.json. Warn-only: always exits 0,
since a date ages without any change and CI must not go red for it. Recheck the fact, then update
its date (promesas.html is generated from promesas.json).
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "scripts"))
from lint_copy import blank, visible_html  # noqa: E402

MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
          "octubre", "noviembre", "diciembre"]
M = "|".join(MONTHS)
AS_OF = re.compile(
    rf"(?:\b[Aa]l|\b(?:[Aa]ctualizad|[Rr]evisad)[oa]s? el) (\d{{1,2}}) de ({M})(?: de (\d{{4}}))?")
RANGE = re.compile(rf"\d(?: de (?:{M}))?\s*$")
ARTICLE = re.compile(r"<article\b.*?</article\s*>", re.S | re.I)
DATA = [("api/data/rotation.json", "checked"), ("web/zones.json", "checked"),
        ("web/promesas.json", "actualizado")]


def as_of(day, month, year, today):
    d = dt.date(int(year or today.year), MONTHS.index(month) + 1, int(day))
    return d.replace(year=d.year - 1) if not year and d > today else d


def scan_html(name, text, today, days):
    if name == "noticias.html":
        text = ARTICLE.sub(blank, text)
    text = visible_html(text)
    out = []
    for n, line in enumerate(text.splitlines(), 1):
        for m in AS_OF.finditer(line):
            if m.group(0)[:2].lower() == "al" and RANGE.search(line[:m.start()]):
                continue
            d = as_of(*m.groups(), today)
            if (today - d).days > days:
                out.append((d, f"web/{name}:{n}: «{m.group(0)}»"))
    return out


def scan_data(today, days):
    out = []
    for path, key in DATA:
        doc = json.loads((root / path).read_text(encoding="utf-8"))
        if doc.get(key):
            out.append((path, key, doc[key]))
        if path.endswith("promesas.json"):
            out += [(path, f"{p['codigo']}.veredicto_fecha", p["veredicto_fecha"])
                    for p in doc.get("promesas", []) if p.get("veredicto_fecha")]
    return [(d, f"{path}: {key} {d}") for path, key, v in out
            if (today - (d := dt.date.fromisoformat(v[:10]))).days > days]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=10)
    ap.add_argument("--count", action="store_true", help="print only the number found")
    args = ap.parse_args()
    today = dt.date.today()
    found = scan_data(today, args.days)
    for f in sorted((root / "web").glob("*.html")):
        found += scan_html(f.name, f.read_text(encoding="utf-8"), today, args.days)
    if args.count:
        print(len(found))
        return
    for d, msg in sorted(found):
        print(f"{msg}  ({(today - d).days} days)")


if __name__ == "__main__":
    main()
