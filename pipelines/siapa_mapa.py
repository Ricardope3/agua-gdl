#!/usr/bin/env python3
"""Build web/colonias_siapa.topo.json from the data behind SIAPA's rotation map.

Usage: python3 pipelines/siapa_mapa.py [--input rotacion-siapa.topo.json] [--ajustes ajustes.json]
                                       [--out web/colonias_siapa.topo.json] [--fetched YYYY-MM-DD]

Since 16 Oct 2026 SIAPA's page (https://rotaciondeserviciosiapa.jalisco.gob.mx/) draws its
own map from /geo/rotacion-siapa.topo.json (2,303 colonias of the metropolitan area with
name, municipio, postal code and the zones their outline crosses, the 7 zone polygons and
the municipios) and /api/ajustes.php (days per zone and colonia zones edited by SIAPA's
admins, which the page applies over the file). Without --input/--ajustes both are downloaded.

The output keeps the TopoJSON arcs and the colonias and zonas objects. Each colonia keeps
n (name), m (municipio), cp and z (the map's zones, "1,5" when several) and gets l when
SIAPA's PDF list (api/data/colonias.json) gives that name and municipio other zones.
/mapa decodes the file in the browser. Days per zone are not copied: /mapa reads them from
the API, i.e. api/data/rotation.json. When ajustes gives other days this prints a warning,
since someone must check SIAPA's calendar before changing rotation.json; colonia overrides
in ajustes are reported, not applied (none existed when this was written).
"""

import argparse
import datetime
import json
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

    colonias, matched, differs, with_zone = [], 0, 0, 0
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
        colonias.append({"type": g["type"], "arcs": g["arcs"], "properties": props})
    zonas = [{"type": g["type"], "arcs": g["arcs"], "properties": {"z": int(g["properties"]["z"]), "nombre": g["properties"].get("nombre", "")}}
             for g in sorted(topo["objects"]["zonas"]["geometries"], key=lambda g: int(g["properties"]["z"]))]
    if len(zonas) != 7:
        sys.exit(f"expected 7 zones, got {len(zonas)}")

    result = {"type": "Topology", "transform": topo["transform"], "arcs": topo["arcs"],
              "objects": {"colonias": {"type": "GeometryCollection", "geometries": colonias},
                          "zonas": {"type": "GeometryCollection", "geometries": zonas}},
              "meta": {"source": TOPO_URL, "fetched": args.fetched}}
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, separators=(",", ":"))
        f.write("\n")
    print(f"{args.out}: {len(colonias)} colonias ({with_zone} in a zone), {matched} on SIAPA's list, {differs} with other zones there; {len(topo['arcs'])} arcs")

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
