#!/usr/bin/env python3
"""Build web/colonias_siapa.topo.json, and its copy api/data/colonias_siapa.topo.json that the API
looks zones up in, from the data behind SIAPA's rotation map.

Usage: python3 pipelines/siapa_mapa.py [--input rotacion-siapa.topo.json] [--ajustes ajustes.json]
                                       [--out web/colonias_siapa.topo.json] [--fetched YYYY-MM-DD]

Since 16 Oct 2026 SIAPA's page (https://rotaciondeserviciosiapa.jalisco.gob.mx/) draws its
own map from /geo/rotacion-siapa.topo.json (2,303 colonias of the metropolitan area with
name, municipio, postal code and the zones their outline crosses, the 7 zone polygons and
the municipios) and /api/ajustes.php (days per zone and colonia zones edited by SIAPA's
admins, which the page applies over the file). Without --input/--ajustes both are downloaded.

The output keeps the TopoJSON arcs and the colonias and zonas objects. Each colonia keeps
n (name), m (municipio), cp and z (the map's zones, "1,5" when several), gets l when SIAPA's
PDF list (api/data/colonias.json) gives that name and municipio other zones, and, when z has
several zones, p: the share of the colonia's area inside each zone, in percent ("5:93,6:7",
estimated on a grid of sample points), so the pages can tell a colonia split between zones
from one that merely touches a border. /mapa and /mizona decode the file in the browser.
Days per zone are not copied: the pages read them from the API, i.e. api/data/rotation.json.
When ajustes gives other days this prints a warning, since someone must check SIAPA's
calendar before changing rotation.json; colonia overrides in ajustes are reported, not
applied (none existed when this was written).
"""

import argparse
import datetime
import json
import math
import re
import sys
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOPO_URL = "https://rotaciondeserviciosiapa.jalisco.gob.mx/geo/rotacion-siapa.topo.json"
AJUSTES_URL = "https://rotaciondeserviciosiapa.jalisco.gob.mx/api/ajustes.php"
UA = "Mozilla/5.0 (compatible; AguaGDL/1.0; +https://aguagdl.com)"
PREFIXES = ("COLONIA ", "COL ", "FRACCIONAMIENTO ", "FRACC ", "FRAC ")
MUNICIPIO_ALIAS = {"SAN PEDRO TLAQUEPAQUE": "TLAQUEPAQUE", "GDL": "GUADALAJARA"}
DAY_KEYS = {"lunes": "mon", "martes": "tue", "miercoles": "wed", "jueves": "thu", "viernes": "fri", "sabado": "sat", "domingo": "sun"}
SAMPLES = 900  # grid points per colonia when estimating the share of its area in each zone
BORDER = 15  # under this share in a zone, a colonia only touches it (web/mapa.js BORDER)


def fold(s):
    """Normalize like internal/colonias.Normalize: upper case, no accents, letters and digits only."""
    s = unicodedata.normalize("NFD", s.upper())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = " ".join(re.sub(r"[^A-Z0-9]+", " ", s).split())
    for p in PREFIXES:
        if s.startswith(p):
            return s[len(p):]
    return s


def municipio(m):
    m = fold(m)
    return MUNICIPIO_ALIAS.get(m, m)


def load(path, url):
    if path:
        return json.loads(Path(path).read_bytes())
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def zones_of(z):
    return sorted(int(x) for x in str(z).split(",") if x.strip())


def decode_arcs(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    return arcs


def polygons(g, arcs):
    """The geometry's polygons, each a list of rings (outer first) of (lon, lat) points."""
    def ring(idx):
        pts = []
        for i in idx:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            if pts:
                pts.pop()
            pts.extend(a)
        return pts
    polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
    return [[ring(r) for r in poly] for poly in polys]


def in_ring(pt, ring):
    x, y = pt
    hit = False
    j = len(ring) - 1
    for i in range(len(ring)):
        x1, y1 = ring[i]
        x2, y2 = ring[j]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            hit = not hit
        j = i
    return hit


def bbox(polys):
    xs = [x for poly in polys for x, _ in poly[0]]
    ys = [y for poly in polys for _, y in poly[0]]
    return min(xs), min(ys), max(xs), max(ys)


def inside(pt, polys, boxes=None):
    for k, poly in enumerate(polys):
        if boxes is not None:
            x0, y0, x1, y1 = boxes[k]
            if not (x0 <= pt[0] <= x1 and y0 <= pt[1] <= y1):
                continue
        if in_ring(pt, poly[0]) and not any(in_ring(pt, hole) for hole in poly[1:]):
            return True
    return False


def zone_shares(colonia_polys, zone_polys, zone_boxes):
    """Percent of the colonia's area in each zone, from a grid of sample points inside it."""
    x0, y0, x1, y1 = bbox(colonia_polys)
    step = math.sqrt((x1 - x0) * (y1 - y0) / SAMPLES) or 1e-6
    counts = {}
    total = 0
    y = y0 + step / 2
    while y < y1:
        x = x0 + step / 2
        while x < x1:
            pt = (x, y)
            if inside(pt, colonia_polys):
                for z, polys in zone_polys.items():
                    if inside(pt, polys, zone_boxes[z]):
                        counts[z] = counts.get(z, 0) + 1
                        total += 1
                        break
            x += step
        y += step
    if not total:
        return {}
    return {z: 100 * n / total for z, n in counts.items()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", help="local copy of SIAPA's TopoJSON (default: download)")
    ap.add_argument("--ajustes", help="local copy of /api/ajustes.php (default: download)")
    ap.add_argument("--out", default=str(ROOT / "web" / "colonias_siapa.topo.json"))
    ap.add_argument("--fetched", default=datetime.date.today().isoformat(), help="date shown as «consultado» on /mapa")
    args = ap.parse_args()

    topo = load(args.input, TOPO_URL)
    ajustes = load(args.ajustes, AJUSTES_URL)
    with open(ROOT / "api" / "data" / "colonias.json", encoding="utf-8") as f:
        listed = {}
        for c in json.load(f):
            listed.setdefault((fold(c["name"]), municipio(c["municipio"])), set()).update(c["zones"])

    arcs = decode_arcs(topo)
    zonas = sorted(topo["objects"]["zonas"]["geometries"], key=lambda g: int(g["properties"]["z"]))
    if len(zonas) != 7:
        sys.exit(f"expected 7 zones, got {len(zonas)}")
    zone_polys = {int(g["properties"]["z"]): polygons(g, arcs) for g in zonas}
    zone_boxes = {z: [bbox([poly]) for poly in polys] for z, polys in zone_polys.items()}

    colonias, matched, differs, with_zone, split, border = [], 0, 0, 0, 0, 0
    for g in topo["objects"]["colonias"]["geometries"]:
        p = g["properties"]
        z = zones_of(p.get("z", ""))
        props = {"n": p["n"].strip(), "m": p["m"].strip(), "cp": str(p.get("cp", "")).strip(), "z": ",".join(map(str, z))}
        with_zone += bool(z)
        hits = [listed[(fold(p["n"]), m)] for m in map(municipio, re.split(r"\s+Y\s+", fold(p["m"]))) if (fold(p["n"]), m) in listed]
        if hits:
            matched += 1
            lz = sorted(set().union(*hits))
            if lz != z:
                differs += 1
                props["l"] = ",".join(map(str, lz))
        if len(z) > 1:
            shares = zone_shares(polygons(g, arcs), {k: zone_polys[k] for k in z}, zone_boxes)
            if shares:
                rounded = {k: max(1, round(v)) if v > 0 else 0 for k, v in shares.items()}
                props["p"] = ",".join(f"{k}:{rounded[k]}" for k in sorted(rounded, key=lambda k: -shares[k]))
                if min(shares.values()) < BORDER and len(shares) == len(z):
                    border += 1
                elif len(shares) == len(z):
                    split += 1
        colonias.append({"type": g["type"], "arcs": g["arcs"], "properties": props})
    zonas_out = [{"type": g["type"], "arcs": g["arcs"], "properties": {"z": int(g["properties"]["z"]), "nombre": g["properties"].get("nombre", "")}} for g in zonas]

    result = {"type": "Topology", "transform": topo["transform"], "arcs": topo["arcs"],
              "objects": {"colonias": {"type": "GeometryCollection", "geometries": colonias},
                          "zonas": {"type": "GeometryCollection", "geometries": zonas_out}},
              "meta": {"source": TOPO_URL, "fetched": args.fetched}}
    text = json.dumps(result, ensure_ascii=False, separators=(",", ":")) + "\n"
    outs = [args.out]
    if Path(args.out).resolve() == (ROOT / "web" / "colonias_siapa.topo.json").resolve():
        outs.append(ROOT / "api" / "data" / "colonias_siapa.topo.json")  # go:embed can't reach web/
    for out in outs:
        with open(out, "w", encoding="utf-8") as f:
            f.write(text)
    print(f"{args.out}: {len(colonias)} colonias ({with_zone} in a zone), {matched} on SIAPA's list, {differs} with other zones there; "
          f"{split + border} in several zones ({border} only touch a border, under {BORDER} % in the other zone, as web/mapa.js counts them); {len(topo['arcs'])} arcs")

    with open(ROOT / "api" / "data" / "rotation.json", encoding="utf-8") as f:
        rotation = json.load(f)["zones"]
    for z, v in sorted(ajustes.get("zonas", {}).items(), key=lambda kv: int(kv[0])):
        theirs = sorted(DAY_KEYS.get(d, d) for d in v.get("dias", []))
        if theirs != sorted(rotation.get(z, [])):
            print(f"WARNING: zone {z}: SIAPA's ajustes ({ajustes.get('actualizado')}) say {theirs}, rotation.json says {sorted(rotation.get(z, []))}", file=sys.stderr)
    if ajustes.get("colonias"):
        print(f"WARNING: ajustes move {len(ajustes['colonias'])} colonias (not applied): {json.dumps(ajustes['colonias'], ensure_ascii=False)[:400]}", file=sys.stderr)


if __name__ == "__main__":
    main()
