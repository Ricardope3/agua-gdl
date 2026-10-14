"""Convert SIAPA's My Maps KML of rotation zones to GeoJSON.

Usage: python siapa_zonas.py zonas.kml ../api/data/zonas.geojson

KML: https://www.google.com/maps/d/kml?mid=1AJ1jEcf4YzgRPw5r9yBXkZOoFMfoB6Y&forcekml=1

Every placemark must be named "ZONA N" (1 to 7, trailing spaces allowed) and
each zone becomes one MultiPolygon feature, sorted by zone. Altitudes are
dropped; coordinates keep the KML's digits.
"""

import json
import re
import sys
import xml.etree.ElementTree as ET

NS = {"k": "http://www.opengis.net/kml/2.2"}
ZONES = 7


def convert(kml):
    root = ET.fromstring(kml)
    zones = {}
    for pm in root.iter(f"{{{NS['k']}}}Placemark"):
        name = pm.findtext("k:name", "", NS).strip()
        m = re.fullmatch(r"ZONA ([1-9])", name)
        if not m or int(m.group(1)) > ZONES:
            raise ValueError(f"unexpected placemark {name!r}")
        zone = int(m.group(1))
        if zone in zones:
            raise ValueError(f"zone {zone} appears twice")
        polys = [polygon(p) for p in pm.iterfind(".//k:Polygon", NS)]
        if not polys:
            raise ValueError(f"zone {zone} has no polygons")
        zones[zone] = polys
    if len(zones) != ZONES:
        raise ValueError(f"expected {ZONES} zones, found {sorted(zones)}")
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"zona": f"ZONA {z}"},
                "geometry": {"type": "MultiPolygon", "coordinates": zones[z]},
            }
            for z in sorted(zones)
        ],
    }


def polygon(p):
    rings = p.findall("k:outerBoundaryIs/k:LinearRing/k:coordinates", NS)
    if len(rings) != 1:
        raise ValueError(f"polygon with {len(rings)} outer rings")
    rings += p.findall("k:innerBoundaryIs/k:LinearRing/k:coordinates", NS)
    return [[[float(v) for v in pt.split(",")[:2]] for pt in (r.text or "").split()] for r in rings]


def main(kml_path, out_path):
    with open(kml_path, "rb") as f:
        fc = convert(f.read())
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(fc, f)
    polys = sum(len(f["geometry"]["coordinates"]) for f in fc["features"])
    print(f"{len(fc['features'])} zones, {polys} polygons")


if __name__ == "__main__":
    try:
        main(sys.argv[1], sys.argv[2])
    except ValueError as e:
        sys.exit(f"siapa_zonas: {e}")
