"""Write KML layers for a Google My Maps copy of the rotation map: zonas.kml (the 7 SIAPA zones with
their days), colonias.kml (the INE outlines matched to SIAPA's colonia list) and municipios.kml.

Usage, from the repo root: python3 pipelines/mymaps_kml.py OUT_DIR

My Maps imports one file per layer (Create a new map › Import, up to 5 MB and 2,000 shapes each).
"""

import json
import pathlib
import sys
from xml.sax.saxutils import escape

root = pathlib.Path(__file__).resolve().parent.parent
rotation = json.loads((root / "api/data/rotation.json").read_text())
DAYS = {"mon": "lunes", "tue": "martes", "wed": "miércoles", "thu": "jueves", "fri": "viernes", "sat": "sábado", "sun": "domingo"}
# The landing map's light palette (pipelines/zonas_preview.py).
COLORS = {1: "#008300", 2: "#2a78d6", 3: "#eda100", 4: "#1baf7a", 5: "#6250d6", 6: "#e87ba4", 7: "#e34948"}
MUNICIPIOS = {"GUADALAJARA": "Guadalajara", "ZAPOPAN": "Zapopan", "SAN PEDRO TLAQUEPAQUE": "Tlaquepaque", "TONALA": "Tonalá", "TONALÁ": "Tonalá"}
FOOT = "Rotación del SIAPA del 15 de octubre de 2026 al 31 de marzo de 2027. Busca tu zona y recibe avisos en https://aguagdl.com/mizona. Agua GDL no es del SIAPA."


def kml_color(hex_rgb, alpha):
    r, g, b = hex_rgb[1:3], hex_rgb[3:5], hex_rgb[5:7]
    return f"{alpha:02x}{b}{g}{r}"


def joined(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " y " + items[-1]


def days(zone):
    return joined([DAYS[d] for d in rotation["zones"][str(zone)]])


def polygons(geom):
    return geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]


def geometry(geom):
    out = []
    for poly in polygons(geom):
        rings = []
        for i, ring in enumerate(poly):
            tag = "outerBoundaryIs" if i == 0 else "innerBoundaryIs"
            coords = " ".join(f"{x:.5f},{y:.5f}" for x, y in ring)
            rings.append(f"<{tag}><LinearRing><coordinates>{coords}</coordinates></LinearRing></{tag}>")
        out.append("<Polygon>" + "".join(rings) + "</Polygon>")
    return "<MultiGeometry>" + "".join(out) + "</MultiGeometry>"


def document(name, styles, placemarks):
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
            f"<name>{escape(name)}</name>{styles}{''.join(placemarks)}</Document></kml>\n")


def placemark(name, style, description, geom):
    return (f"<Placemark><name>{escape(name)}</name><styleUrl>#{style}</styleUrl>"
            f"<description>{escape(description)}</description>{geometry(geom)}</Placemark>")


def main(out):
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)

    zones = {}
    for f in json.loads((root / "api/data/zonas.geojson").read_text())["features"]:
        z = int(f["properties"]["zona"].split()[-1])
        zones.setdefault(z, []).extend(polygons(f["geometry"]))
    styles = "".join(f'<Style id="z{z}"><LineStyle><color>{kml_color(c, 255)}</color><width>2</width></LineStyle>'
                     f'<PolyStyle><color>{kml_color(c, 110)}</color></PolyStyle></Style>' for z, c in COLORS.items())
    marks = [placemark(f"Zona {z}", f"z{z}", f"Días de racionamiento: {days(z)}. {FOOT}",
                       {"type": "MultiPolygon", "coordinates": zones[z]}) for z in sorted(zones)]
    (out / "zonas.kml").write_text(document("Zonas de la rotación", styles, marks))

    listed = {(c["name"], c["municipio"]): c for c in json.loads((root / "api/data/colonias.json").read_text())}
    styles = '<Style id="col"><LineStyle><color>ff2c1e0c</color><width>1.5</width></LineStyle><PolyStyle><color>00ffffff</color></PolyStyle></Style>'
    marks = []
    for f in json.loads((root / "pipelines/colonias.geojson").read_text())["features"]:
        p = f["properties"]
        c = listed[(p["name"], p["municipio"])]
        mun = MUNICIPIOS.get(p["municipio"], p["municipio"].title())
        word = "las zonas" if len(c["zones"]) > 1 else "la zona"
        desc = f"Según la lista del SIAPA está en {word} {joined([str(z) for z in c['zones']])}. " + " ".join(
            f"Zona {z}: {days(z)}." for z in c["zones"])
        if set(p["zones"]) != set(c["zones"]) and p["zones"]:
            desc += f" En el mapa del SIAPA su contorno queda en la zona {joined([str(z) for z in p['zones']])}."
        marks.append(placemark(f"{c['name']} ({mun})", "col", f"{desc} Contorno aproximado del INE (diciembre de 2025). {FOOT}", f["geometry"]))
    (out / "colonias.kml").write_text(document("Colonias de la lista del SIAPA", styles, marks))

    styles = '<Style id="mun"><LineStyle><color>ff555555</color><width>2.5</width></LineStyle><PolyStyle><color>00ffffff</color></PolyStyle></Style>'
    marks = [placemark(MUNICIPIOS[f["properties"]["nombre"]], "mun", "Límite municipal del INE (diciembre de 2025).", f["geometry"])
             for f in json.loads((root / "pipelines/municipios_amg.geojson").read_text())["features"]]
    (out / "municipios.kml").write_text(document("Municipios", styles, marks))

    for name in ("zonas.kml", "colonias.kml", "municipios.kml"):
        print(f"{out / name}: {(out / name).stat().st_size // 1024} KB")


if __name__ == "__main__":
    main(sys.argv[1])
