"""Write web/colonias.geojson: the outline of each SIAPA colonia, for the map on /llego.

Source: INE's Base Geográfica Digital for Jalisco (cut of 15 Dec 2025), layer COLONIA,
from cartografia.ine.mx (BGD_15_diciembre_2025, "14 JALISCO.7z", shapefile without
exterior numbers). Convert it first; the shapefile is in UTM 13N and its text is CP1252:

    ogr2ogr -f GeoJSON -t_srs EPSG:4326 --config SHAPE_ENCODING CP1252 ine_colonias.geojson COLONIA.shp

then run, from the repo root:

    python3 pipelines/colonias_poligonos.py ine_colonias.geojson

Only exact name + municipio matches and the checked aliases below are used: SIAPA lists
look-alike names as different colonias, so fuzzy matching would draw the wrong one.
Same-name pieces within a municipio are merged into one MultiPolygon.
"""

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COLONIAS = ROOT / "api" / "data" / "colonias.json"
OUT = ROOT / "web" / "colonias.geojson"

# INE's own municipio codes, not INEGI's.
INE_MUNICIPIOS = {41: "GUADALAJARA", 120: "ZAPOPAN", 99: "TLAQUEPAQUE", 102: "TONALA"}

# SIAPA name -> INE name, same municipio. Each checked by hand on 16 Oct 2026.
ALIASES = {
    ("CENTRO GUADALAJARA", "GUADALAJARA"): "GUADALAJARA CENTRO",
    ("ARROYO DE LAS FLORES", "TLAQUEPAQUE"): "ARROYO LAS FLORES",
}


def norm(s):
    s = unicodedata.normalize("NFD", s.upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", s)).strip()


def rounded(coords):
    if isinstance(coords[0], (int, float)):
        return [round(coords[0], 5), round(coords[1], 5)]
    return [rounded(c) for c in coords]


def polygons(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return geom["coordinates"]
    raise ValueError("unexpected geometry " + geom["type"])


def main(src):
    pieces = {}
    for f in json.loads(Path(src).read_text())["features"]:
        mun = INE_MUNICIPIOS.get(f["properties"]["MUNICIPIO"])
        if mun and f["geometry"]:
            pieces.setdefault((norm(f["properties"]["NOMBRE"]), mun), []).extend(polygons(f["geometry"]))

    features, missing = [], []
    for c in json.loads(COLONIAS.read_text()):
        name, mun = norm(c["name"]), norm(c["municipio"])
        found = pieces.get((ALIASES.get((name, mun), name), mun))
        if not found:
            missing.append(f'{c["name"]} ({c["municipio"]})')
            continue
        features.append({"type": "Feature", "properties": {"name": c["name"], "municipio": c["municipio"]},
                         "geometry": {"type": "MultiPolygon", "coordinates": rounded(found)}})

    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"{len(features)} colonias written to {OUT.relative_to(ROOT)}, {len(missing)} without an outline")


if __name__ == "__main__":
    main(sys.argv[1])
