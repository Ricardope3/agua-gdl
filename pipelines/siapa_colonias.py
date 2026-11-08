"""Extract SIAPA's colonia-to-zone list from colonias_siapa.pdf.

Usage: python siapa_colonias.py colonias_siapa.pdf ../api/data/colonias.json

Each page is one zone and municipio, named in its header («Zona 3 -
Tlaquepaque») over that zone's «Días de baja presión». Names are in Garet-Bold
below 30pt; the «Zona N» legend drawn over the table is Garet-ExtraBold, and
text Illustrator left outside the page is dropped. A trailing "*" means the
colonia is served by several aqueducts and appears under more than one zone.
SIAPA marks every row whose name appears in more than one zone, even when the
rows are in different municipios; SAME_COLONIA lists the ones that are one
colonia, whose zones are merged.

Written for the 5 Nov 2026 PDF (23 pages, each for one zone and municipio; 621
colonias, the same list as the 12 Oct PDF). A reissue can drop names, as the
13 Oct one did: compare the count it prints with the old file's, and each
zone's days with api/data/rotation.json.
"""

import json
import re
import sys
import unicodedata

import pdfplumber

HEADER_SIZE = 50.5
MUNICIPIOS = {"GUADALAJARA", "ZAPOPAN", "TLAQUEPAQUE", "TONALÁ"}

# Colonias SIAPA lists under two municipios with a different zone in each, both marked
# "*", that are one colonia: SIAPA's zone map puts its INE outline in both zones. Each row
# gets both zones. Checked by hand on 16 Oct 2026. Same-name rows that are different
# places stay apart: EL ROSARIO (Guadalajara 3, Tonalá 4) and AGUA BLANCA (Tonalá 4,
# Zapopan 6) are 6 and 26 km apart; ALAMO INDUSTRIAL's Tlaquepaque part is in zone 3 on
# the list and the map; ARBOLEDAS (Guadalajara 7, Tlaquepaque 6) has no outline, and Google
# Maps lists separate Arboledas places (checked 17 Oct), so it stays two colonias.
SAME_COLONIA = [
    # Guadalajara's outline overlaps zones 5 and 6; INE has no CHAPALITA in Zapopan.
    [("CHAPALITA", "GUADALAJARA"), ("CHAPALITA", "ZAPOPAN")],
    # Zapopan's outline overlaps zones 5 and 6; neither INE nor OpenStreetMap has one in Tlaquepaque.
    [("CIUDAD DEL SOL", "TLAQUEPAQUE"), ("CIUDAD DEL SOL", "ZAPOPAN")],
]


def main(pdf_path, out_path):
    rows = {}

    def add(zone, name, mun):
        multi = name.endswith("*")
        name = name.rstrip("*").strip()
        if not name:
            return
        if mun not in MUNICIPIOS:
            sys.exit(f"unexpected municipio {mun!r} for {name!r} in zone {zone}")
        r = rows.setdefault((name, mun), {"name": name, "municipio": mun, "zones": [], "multi": False})
        if zone not in r["zones"]:
            r["zones"].append(zone)
        r["multi"] = r["multi"] or multi

    days = {}
    with pdfplumber.open(pdf_path) as pdf:
        for n, page in enumerate(pdf.pages, 1):
            header = "".join(c["text"] for c in page.chars if round(c["size"], 1) == HEADER_SIZE)
            m = re.fullmatch(r"\s*Zona (\d) - (.+?)\s*", header)
            if not m:
                sys.exit(f"page {n}: no «Zona N - Municipio» header ({header!r})")
            zone, mun = int(m.group(1)), m.group(2).upper()
            line = " ".join(" ".join(t) for t in lines(c for c in page.chars if 30 <= c["size"] < 40))
            if days.setdefault(zone, line) != line:
                sys.exit(f"page {n}: zone {zone} days {line!r} differ from {days[zone]!r}")
            names = [c for c in page.chars
                     if c["fontname"].endswith("Garet-Bold") and c["size"] < 30 and 0 <= c["x0"] < page.width]
            found = [name for row in lines(names) for name in row]
            if not found:
                sys.exit(f"page {n}: no colonia names under «{header.strip()}»")
            for name in found:
                add(zone, name, mun)
    for zone in sorted(days):
        print(f"zona {zone}: {days[zone]}")
    for group in SAME_COLONIA:
        parts = [rows.get(key) for key in group]
        if not all(p and p["multi"] for p in parts):
            sys.exit(f"{group} is no longer on the list with * in each municipio")
        zones = sorted({z for p in parts for z in p["zones"]})
        for p in parts:
            p["zones"] = list(zones)
    out = sorted(rows.values(), key=lambda r: (strip_accents(r["municipio"]), strip_accents(r["name"])))
    for r in out:
        r["zones"].sort()
    try:
        with open(out_path, encoding="utf-8") as f:
            before = f" (the file had {len(json.load(f))})"
    except FileNotFoundError:
        before = ""
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{len(out)} colonias, {sum(r['multi'] for r in out)} in several zones{before}")


def lines(chars):
    # Read the characters in drawing order, which keeps SIAPA's own spaces; a jump of
    # more than two font sizes, or three or more spaces, separates two names.
    runs, prev = [], None
    for c in chars:
        if not prev or abs(c["top"] - prev["top"]) >= 3 or abs(c["x0"] - prev["x1"]) > 2 * c["size"]:
            runs.append({"top": c["top"], "x0": c["x0"], "text": ""})
        runs[-1]["text"] += c["text"]
        prev = c
    rows = []
    for r in sorted(runs, key=lambda r: r["top"]):
        if rows and abs(rows[-1][0]["top"] - r["top"]) < 3:
            rows[-1].append(r)
        else:
            rows.append([r])
    for row in rows:
        names = []
        for r in sorted(row, key=lambda r: r["x0"]):
            names += [" ".join(t.split()) for t in re.split(r" {3,}", r["text"])]
        yield [t for t in names if t]


def strip_accents(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
