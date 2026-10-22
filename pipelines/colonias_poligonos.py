"""Write pipelines/colonias.geojson, the outline of each SIAPA colonia with the zones of
api/data/zonas.geojson it overlaps (SIAPA's list can name others; only mymaps_kml.py reads
it, since /mizona draws SIAPA's own map), and api/data/otras_colonias.json, the colonias INE
knows that aren't on SIAPA's rotation list, with the zones they overlap (none = not affected
by the rotation). pipelines/mapa_colonias.py then gives those the zones SIAPA's map draws.

Source: INE's Base Geográfica Digital for Jalisco (cut of 15 Dec 2025), layer COLONIA,
from cartografia.ine.mx (BGD_15_diciembre_2025, "14 JALISCO.7z", shapefile without
exterior numbers). Convert it first; the shapefile is in UTM 13N and its text is CP1252:

    ogr2ogr -f GeoJSON -t_srs EPSG:4326 --config SHAPE_ENCODING CP1252 ine_colonias.geojson COLONIA.shp

then run, from the repo root:

    python3 pipelines/colonias_poligonos.py ine_colonias.geojson
    python3 pipelines/mapa_colonias.py

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
OUT = ROOT / "pipelines" / "colonias.geojson"
OTHERS = ROOT / "api" / "data" / "otras_colonias.json"
ZONAS = ROOT / "api" / "data" / "zonas.geojson"

# INE's own municipio codes, not INEGI's, with SIAPA's spelling.
INE_MUNICIPIOS = {41: "GUADALAJARA", 120: "ZAPOPAN", 99: "TLAQUEPAQUE", 102: "TONALÁ"}
PREFIXES = ("COLONIA ", "COL ", "FRACCIONAMIENTO ", "FRACC ", "FRAC ")

# SIAPA name -> INE name, same municipio. Each checked by hand on 16 Oct 2026.
ALIASES = {
    ("CENTRO GUADALAJARA", "GUADALAJARA"): "GUADALAJARA CENTRO",
    ("ARROYO DE LAS FLORES", "TLAQUEPAQUE"): "ARROYO LAS FLORES",
    ("ARBOLEDAS DEL SUR", "GUADALAJARA"): "ARBOLEDAS SUR",
    ("BARRAGAN Y HERNANDEZ", "GUADALAJARA"): "BARRAGAN HERNANDEZ",
    ("EL FRESNO", "GUADALAJARA"): "DEL FRESNO",
    ("EL HORMIGUERO", "GUADALAJARA"): "HORMIGUERO",
    ("EL MIRADOR", "GUADALAJARA"): "MIRADOR",
    ("EL REAL", "GUADALAJARA"): "REAL",
    ("JARDINES DE PLAZA DEL SOL", "GUADALAJARA"): "JARDINES PLAZA DEL SOL",
    ("PARQUES SAN PEDRO", "GUADALAJARA"): "PARQUES DE SAN PEDRO",
    ("RESIDENCIAL SAN RAFAEL", "GUADALAJARA"): "SAN RAFAEL RESIDENCIAL",
    ("UNIDAD MODELO", "GUADALAJARA"): "MODELO",
    ("JARDIN DE LOS POETAS", "GUADALAJARA"): "JARDINES DE LOS POETAS",
    ("BARRIO DE SANTA MARIA", "TLAQUEPAQUE"): "SANTA MARIA",
    ("BARRIO DE SANTIAGO", "TLAQUEPAQUE"): "DE SANTIAGO",
    ("COTO EL CARMEN", "TLAQUEPAQUE"): "COTO DEL CARMEN",
    ("FRACCIONAMIENTO LAS TERRAZAS", "TLAQUEPAQUE"): "LAS TERRAZAS",
    ("FRACCIONAMIENTO MERIDIANO HOGARES DEL ALAMO", "TLAQUEPAQUE"): "MERIDIANO HOGARES DEL ALAMO",
    ("FRACCIONAMIENTO RESIDENCIAL ARRAYANES", "TLAQUEPAQUE"): "ARRAYANES",
    ("HACIENDAS DE SAN MARTIN", "TLAQUEPAQUE"): "HACIENDA DE SAN MARTIN",
    ("HACIENDAS SAN PEDRO", "TLAQUEPAQUE"): "HACIENDA SAN PEDRO",
    ("PARQUES SANTA CRUZ DEL VALLE", "TLAQUEPAQUE"): "PARQUES DE SANTA CRUZ DEL VALLE",
    ("PORTALES DE TLAQUEPAQUE", "TLAQUEPAQUE"): "LOS PORTALES TLAQUEPAQUE",
    ("TLAQUEPAQUE PUEBLITO CONDOMINIO", "TLAQUEPAQUE"): "TLAQUEPAQUE PUEBLITO",
    ("VALLE BALCONES SANTA MARIA", "TLAQUEPAQUE"): "VALLE BALCONES DE SANTA MARIA",
    ("VILLA DEL PRADO", "TLAQUEPAQUE"): "VILLAS DEL PRADO",
    ("VILLAS EL TAPATIO", "TLAQUEPAQUE"): "VILLAS DEL TAPATIO",
    ("FRACCIONAMIENTO REVOLUCION", "TLAQUEPAQUE"): "REVOLUCION",
    ("FRACCIONAMIENTO CANADA REAL", "TONALA"): "CANADA REAL",
    ("NUEVA AURORA RESIDENCIAL", "TONALA"): "NUEVA AURORA",
    ("PASEO DE LA CANADA", "TONALA"): "PASEOS DE LA CANADA",
    ("PUERTAS DEL ROSARIO", "TONALA"): "PUERTA DEL ROSARIO",
    ("QUINTA CATALINA", "TONALA"): "LA QUINTA CATALINA",
    ("LA PUERTA", "TONALA"): "LAS PUERTAS",
    ("AGUA BLANCA", "ZAPOPAN"): "AGUA BLANCA POBLADO",
    ("BOSQUES DE LAS LOMAS", "ZAPOPAN"): "BOSQUE DE LAS LOMAS",
    ("CHAPALITA OCCIDENTE", "ZAPOPAN"): "CHAPALITA DE OCCIDENTE",
    ("COLLI URBANO", "ZAPOPAN"): "EL COLLI URBANO",
    ("CONDOMINIO CRISTAL", "ZAPOPAN"): "CRISTAL",
    ("EL ALCAZAR ORIENTE", "ZAPOPAN"): "ALCAZAR ORIENTE",
    ("EL BOSQUE RESIDENCIAL", "ZAPOPAN"): "EL BOSQUE",
    ("EL COLLI CTM", "ZAPOPAN"): "COLLI CTM",
    ("FORET RESIDENCIAL", "ZAPOPAN"): "FORET",
    ("HACIENDAS TEPEYAC", "ZAPOPAN"): "HACIENDA DEL TEPEYAC",
    ("PARQUES DEL TEPEYAC", "ZAPOPAN"): "PARQUES TEPEYAC",
    ("RESIDENCIAL LA CASTILLA", "ZAPOPAN"): "LA CASTILLA",
    ("RESIDENCIAL LA ESTANCIA", "ZAPOPAN"): "LA ESTANCIA",
    ("RESIDENCIAL LA PENA", "ZAPOPAN"): "LA PENA",
    ("RESIDENCIAL MOCTEZUMA", "ZAPOPAN"): "MOCTEZUMA",
    ("RESIDENCIAL NUEVA GALICIA", "ZAPOPAN"): "NUEVA GALICIA",
    ("RESIDENCIAL TEPEYAC DEL SOL", "ZAPOPAN"): "TEPEYAC DEL SOL",
    ("VALLARTA PATRIA", "ZAPOPAN"): "VALLARTA LA PATRIA",
    ("VIRREYES RESIDENCIAL", "ZAPOPAN"): "VIRREYES",
}


def norm(s):
    s = unicodedata.normalize("NFD", s.upper())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9 ]", " ", s)).strip()


def search_norm(s):
    """Like colonias.Normalize in Go: also drops a Col./Fracc. prefix."""
    s = norm(s)
    for p in PREFIXES:
        if s.startswith(p):
            return s[len(p):]
    return s


def inside(pt, rings):
    """Even-odd test over every ring, so holes count."""
    x, y, hit = pt[0], pt[1], False
    for ring in rings:
        for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
            if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
                hit = not hit
    return hit


def probe_points(polys):
    """Each piece's vertex centroid, and its vertices pulled 20% toward it, so a colonia
    that only touches a zone's edge doesn't count as inside it."""
    pts = []
    for poly in polys:
        ring = poly[0]
        cx, cy = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
        pts.append((cx, cy))
        pts += [(cx + 0.8 * (p[0] - cx), cy + 0.8 * (p[1] - cy)) for p in ring]
    return pts


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
    pieces, names = {}, {}
    for f in json.loads(Path(src).read_text())["features"]:
        mun = INE_MUNICIPIOS.get(f["properties"]["MUNICIPIO"])
        if mun and f["geometry"]:
            key = (norm(f["properties"]["NOMBRE"]), norm(mun))
            pieces.setdefault(key, []).extend(polygons(f["geometry"]))
            names.setdefault(key, (f["properties"]["NOMBRE"].strip(), mun))

    zones = []
    for f in json.loads(ZONAS.read_text())["features"]:
        z = int(re.sub(r"\D", "", f["properties"]["zona"]))
        zones.append((z, [ring for poly in polygons(f["geometry"]) for ring in poly]))

    def overlapped(polys):
        pts = probe_points(polys)
        return sorted({z for z, rings in zones if any(inside(p, rings) for p in pts)})

    features, missing, listed = [], [], set()
    for c in json.loads(COLONIAS.read_text()):
        name, mun = norm(c["name"]), norm(c["municipio"])
        listed.add((search_norm(ALIASES.get((name, mun), name)), mun))
        found = pieces.get((ALIASES.get((name, mun), name), mun))
        # INE can give one name to separate colonias in a municipio (LOS PINOS, Zapopan,
        # has three); keep only the pieces in a zone SIAPA lists for it.
        if found and len(found) > 1:
            found = [p for p in found if set(overlapped([p])) & set(c["zones"])]
        if not found:
            missing.append(f'{c["name"]} ({c["municipio"]})')
            continue
        features.append({"type": "Feature", "properties": {"name": c["name"], "municipio": c["municipio"], "zones": overlapped(found)},
                         "geometry": {"type": "MultiPolygon", "coordinates": rounded(found)}})

    OUT.write_text(json.dumps({"type": "FeatureCollection", "features": features}, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(f"{len(features)} colonias written to {OUT.relative_to(ROOT)}, {len(missing)} without an outline")

    others = []
    for (name, mun), polys in sorted(pieces.items()):
        if (search_norm(name), mun) in listed:
            continue
        others.append({"name": names[(name, mun)][0], "municipio": names[(name, mun)][1], "zones": overlapped(polys)})
    OTHERS.write_text(json.dumps(others, ensure_ascii=False, indent=1) + "\n")
    print(f"{len(others)} other colonias written to {OTHERS.relative_to(ROOT)}, {sum(1 for o in others if not o['zones'])} outside every zone")


if __name__ == "__main__":
    main(sys.argv[1])
