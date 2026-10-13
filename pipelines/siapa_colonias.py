"""Extract SIAPA's colonia-to-zone list from colonias_siapa.pdf.

Usage: python siapa_colonias.py colonias_siapa.pdf ../api/data/colonias.json

Each page belongs to one zone (the big header digit). The "Zona N" legend on
every page is drawn at 19pt over the table, so those characters are dropped
before reading the table. A trailing "*" means the colonia is served by
several aqueducts and appears under more than one zone.
"""

import json
import re
import sys
import unicodedata

import pdfplumber

ZONE_DIGIT_SIZE = 50.5
LEGEND_SIZE = 19.0


def clean_spaced(s):
    # "T O N A L Á" -> "TONALÁ"
    parts = s.split()
    if len(parts) > 3 and sum(len(p) <= 2 for p in parts) >= len(parts) - 1:
        return "".join(parts)
    return " ".join(parts)


def main(pdf_path, out_path):
    rows = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words(extra_attrs=["size"])
            digits = [w["text"] for w in words if round(w["size"], 1) == ZONE_DIGIT_SIZE and w["text"].isdigit()]
            if not digits:
                continue
            zone = int(digits[0])
            body = page.filter(lambda o: o.get("object_type") != "char" or round(o.get("size", 0), 1) != LEGEND_SIZE)
            for table in body.extract_tables():
                for row in table:
                    if not row or len(row) < 2 or not row[0]:
                        continue
                    name = clean_spaced(row[0].split("\n")[-1])
                    mun = clean_spaced(row[1] or "")
                    multi = name.endswith("*")
                    name = name.rstrip("*").strip()
                    if not name or not mun or re.fullmatch(r"(?i)zona \d", name):
                        continue
                    key = (name, mun)
                    r = rows.setdefault(key, {"name": name, "municipio": mun, "zones": [], "multi": False})
                    if zone not in r["zones"]:
                        r["zones"].append(zone)
                    r["multi"] = r["multi"] or multi
    out = sorted(rows.values(), key=lambda r: (strip_accents(r["municipio"]), strip_accents(r["name"])))
    for r in out:
        r["zones"].sort()
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{len(out)} colonias, {sum(r['multi'] for r in out)} in several zones")


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
