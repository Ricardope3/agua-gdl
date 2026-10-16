"""Draw web/zonas.svg, the static zone map on the landing page, from api/data/zonas.geojson, with the
municipio borders from pipelines/municipios_amg.geojson (INE BGD Jalisco, Dec 2025, layer MUNICIPIO,
simplified to 50 m: ogr2ogr -f GeoJSON -t_srs EPSG:4326 -where "MUNICIPIO IN (41,120,99,102)"
-simplify 50 -select nombre -lco COORDINATE_PRECISION=5 municipios_amg.geojson MUNICIPIO.shp)."""
import json
import math
import pathlib

root = pathlib.Path(__file__).resolve().parent.parent
features = json.loads((root / "api/data/zonas.geojson").read_text())["features"]

# One color per zone, ordered so neighbouring zones stay apart (checked with a palette validator, light and dark); the labels carry identity.
LIGHT = {1: "#008300", 2: "#2a78d6", 3: "#eda100", 4: "#1baf7a", 5: "#6250d6", 6: "#e87ba4", 7: "#e34948"}
DARK = {1: "#008300", 2: "#3987e5", 3: "#c98500", 4: "#199e70", 5: "#9085e9", 6: "#d55181", 7: "#d94141"}
WIDTH, PAD = 800, 16
# Zones 1 and 2 are small neighbours; move their labels apart so they don't overlap.
NUDGE = {1: (-34, -22), 2: (18, 14)}

zones = {}
for f in features:
    zone = int(f["properties"]["zona"].split()[-1])
    geom = f["geometry"]
    zones[zone] = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]

points = [p for polys in zones.values() for poly in polys for ring in poly for p in ring]
lon0, lon1 = min(p[0] for p in points), max(p[0] for p in points)
lat0, lat1 = min(p[1] for p in points), max(p[1] for p in points)
kx = math.cos(math.radians((lat0 + lat1) / 2))
scale = (WIDTH - 2 * PAD) / ((lon1 - lon0) * kx)
height = round((lat1 - lat0) * scale + 2 * PAD)


def xy(p):
    return (PAD + (p[0] - lon0) * kx * scale, PAD + (lat1 - p[1]) * scale)


def area(ring):
    return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]))) / 2


def inside(x, y, ring):
    hit = False
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            hit = not hit
    return hit


def edge_distance(x, y, ring):
    best = math.inf
    for (x0, y0), (x1, y1) in zip(ring, ring[1:] + ring[:1]):
        dx, dy = x1 - x0, y1 - y0
        t = max(0, min(1, ((x - x0) * dx + (y - y0) * dy) / (dx * dx + dy * dy or 1)))
        best = min(best, math.hypot(x - x0 - t * dx, y - y0 - t * dy))
    return best


def label_point(ring):
    """The point inside the ring farthest from its edges, on a 4px grid."""
    xs, ys = [p[0] for p in ring], [p[1] for p in ring]
    candidates = ((x, y) for x in range(int(min(xs)), int(max(xs)) + 1, 4) for y in range(int(min(ys)), int(max(ys)) + 1, 4))
    return max((p for p in candidates if inside(*p, ring)), key=lambda p: edge_distance(*p, ring))


municipios = json.loads((root / "pipelines/municipios_amg.geojson").read_text())["features"]
MUN_NAMES = {"GUADALAJARA": "Guadalajara", "ZAPOPAN": "Zapopan", "SAN PEDRO TLAQUEPAQUE": "Tlaquepaque", "TONALA": "Tonalá"}
# Where each municipio's label sits, as a fraction of the map, chosen by eye to stay clear of the zone labels.
MUN_LABEL = {"Guadalajara": (0.43, 0.05), "Zapopan": (0.13, 0.12), "Tlaquepaque": (0.43, 0.83), "Tonalá": (0.80, 0.30)}

paths, labels = [], []
for zone in sorted(zones):
    d, biggest = [], []
    for poly in zones[zone]:
        for i, ring in enumerate(poly):
            pts = [xy(p) for p in ring]
            d.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
            if i == 0 and area(pts) > area(biggest or [(0, 0)] * 3):
                biggest = pts
    paths.append(f'<path class="z{zone}" d="{"".join(d)}"/>')
    x, y = label_point(biggest)
    dx, dy = NUDGE.get(zone, (0, 0))
    x, y = x + dx, y + dy
    labels.append(f'<text x="{x}" y="{y}">Zona {zone}</text>')

borders = []
for f in municipios:
    geom = f["geometry"]
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    d = "".join("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in map(xy, poly[0])) + "Z" for poly in polys)
    borders.append(f'<path class="mun" d="{d}"/>')
    name = MUN_NAMES[f["properties"]["nombre"]]
    fx, fy = MUN_LABEL[name]
    labels.append(f'<text class="munl" x="{fx * WIDTH:.0f}" y="{fy * height:.0f}">{name}</text>')

fills = "\n".join(f".z{z}{{fill:{c}}}" for z, c in LIGHT.items())
dark = "\n".join(f".z{z}{{fill:{c}}}" for z, c in DARK.items())
svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" role="img" aria-label="Mapa de las 7 zonas de la rotación del SIAPA">
<style>
path{{stroke:#e0f2fe;stroke-width:2;stroke-linejoin:round;fill-rule:evenodd}}
{fills}
.mun{{fill:none;stroke:#0c1e2c;stroke-width:1.6;stroke-dasharray:6 4;opacity:.7}}
.munl{{font:600 15px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;letter-spacing:.06em;text-transform:uppercase;fill:#557083}}
text{{font:600 22px -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Arial,sans-serif;fill:#0c1e2c;stroke:#ffffff;stroke-width:5px;paint-order:stroke;stroke-linejoin:round;text-anchor:middle;dominant-baseline:middle}}
@media (prefers-color-scheme: dark){{
path{{stroke:#0c3149}}
{dark}
text{{fill:#f0f9ff;stroke:#06141d}}
.mun{{stroke:#f0f9ff;opacity:.8}}
.munl{{fill:#c4dbe9}}
}}
</style>
{"".join(paths)}
{"".join(borders)}
{"".join(labels)}
</svg>
"""
(root / "web/zonas.svg").write_text(svg)
print(f"web/zonas.svg {WIDTH}x{height}, {len(svg) // 1024} KB")
