"""Extract SIAPA's colonia-to-zone list from colonias_siapa.pdf.

Usage: python siapa_colonias.py colonias_siapa.pdf ../api/data/colonias.json

Each page belongs to one zone (the big header digit). The "Zona N" legend on
every page is drawn at 19pt over the table, so those characters are dropped
before reading the table. A trailing "*" means the colonia is served by
several aqueducts and appears under more than one zone.

Use the 12 Oct 2026 PDF (34 pages, 621 colonias). SIAPA's 13 Oct reissue has
truncated columns.
"""

import json
import re
import sys
import unicodedata

import pdfplumber

ZONE_DIGIT_SIZE = 50.5
LEGEND_SIZE = 19.0
ROW_SIZE = 20.0
MUNICIPIOS = {"GUADALAJARA", "ZAPOPAN", "TLAQUEPAQUE", "TONALÁ"}


def clean_spaced(s):
    # "T O N A L Á" -> "TONALÁ"
    parts = s.split()
    if len(parts) > 3 and sum(len(p) <= 2 for p in parts) >= len(parts) - 1:
        return "".join(parts)
    return " ".join(parts)


def main(pdf_path, out_path):
    rows = {}

    def add(zone, name, mun):
        name, mun = clean_spaced(name), clean_spaced(mun)
        multi = name.endswith("*")
        name = name.rstrip("*").strip()
        if not name or not mun or re.fullmatch(r"(?i)zona \d", name):
            return
        if mun not in MUNICIPIOS:
            sys.exit(f"unexpected municipio {mun!r} for {name!r} in zone {zone}")
        r = rows.setdefault((name, mun), {"name": name, "municipio": mun, "zones": [], "multi": False})
        if zone not in r["zones"]:
            r["zones"].append(zone)
        r["multi"] = r["multi"] or multi

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(extra_attrs=["size"])
            digits = [w["text"] for w in words if round(w["size"], 1) == ZONE_DIGIT_SIZE and w["text"].isdigit()]
            if not digits:
                continue
            zone = int(digits[0])
            body = page.filter(lambda o: o.get("object_type") != "char" or round(o.get("size", 0), 1) != LEGEND_SIZE)
            tables = body.find_tables()
            for table in tables:
                for row in table.extract():
                    if row and len(row) >= 2 and row[0]:
                        add(zone, row[0].split("\n")[-1], row[1] or "")
            if tables:
                last = max(tables, key=lambda t: t.bbox[3])
                split = next(r.cells[1][0] for r in last.rows if len(r.cells) > 1 and r.cells[1])
                for name, mun in rows_below(body, last.bbox[3], split):
                    add(zone, name, mun)
    out = sorted(rows.values(), key=lambda r: (strip_accents(r["municipio"]), strip_accents(r["name"])))
    for r in out:
        r["zones"].sort()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{len(out)} colonias, {sum(r['multi'] for r in out)} in several zones")


def rows_below(page, bottom, split):
    # The last row has no bottom border, so the table finder never closes it.
    lines = {}
    for w in page.extract_words(extra_attrs=["size"]):
        if w["top"] > bottom and abs(w["size"] - ROW_SIZE) < 0.5:
            top = next((k for k in lines if abs(k - w["top"]) < 3), w["top"])
            lines.setdefault(top, []).append(w)
    for top in sorted(lines):
        ws = sorted(lines[top], key=lambda w: w["x0"])
        yield " ".join(w["text"] for w in ws if w["x0"] < split), " ".join(w["text"] for w in ws if w["x0"] >= split)


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
