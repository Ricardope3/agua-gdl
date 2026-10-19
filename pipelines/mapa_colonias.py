#!/usr/bin/env python3
"""Write the API's colonia data from SIAPA's map (web/colonias_siapa.topo.json, built by
pipelines/siapa_mapa.py):

- api/data/colonias_mapa.json, the colonias people can report on /reportes: each colonia once
  as [name, municipio, postal code, zones], the key the page sends and the API checks. Name,
  municipio and postal code repeat on 56 keys (121 outlines) that are pieces of one colonia,
  so their reports count together, and their zones are joined, the one with most of the
  colonia's area first (the count on /reportes puts a report in that zone).
- the zones of api/data/otras_colonias.json, the colonias INE knows that aren't on SIAPA's
  list (pipelines/colonias_poligonos.py writes the names): when SIAPA's map draws a colonia
  with the same name in the same municipio, its zones are the ones SIAPA's map gives it
  (none when the map leaves it out of the rotation), so the bot and /mizona answer what
  SIAPA's map shows. The others keep the zones their INE outline overlaps.

Usage: python3 pipelines/mapa_colonias.py [--check]

Run it after siapa_mapa.py; --check fails when either file is stale (CI runs it).
"""
import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "web" / "colonias_siapa.topo.json"
OUT = ROOT / "api" / "data" / "colonias_mapa.json"
OTHERS = ROOT / "api" / "data" / "otras_colonias.json"
PREFIXES = ("COLONIA ", "COL ", "FRACCIONAMIENTO ", "FRACC ", "FRAC ")


def fold(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().upper()
    s = " ".join(re.sub(r"[^A-Z0-9 ]", " ", s).split())
    for p in PREFIXES:
        if s.startswith(p):
            return s[len(p):]
    return s


def municipios(m):
    """SIAPA's map writes «San Pedro Tlaquepaque» and joins two municipios with « y »."""
    return [fold(x).removeprefix("SAN PEDRO ") for x in re.split(r" y (?=[A-ZÁÉÍÓÚ])", m)]


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


def area(g, arcs):
    """The geometry's area in squared degrees: enough to compare pieces of one colonia."""
    def ring(idx):
        pts = []
        for i in idx:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            if pts:
                pts.pop()
            pts.extend(a)
        return abs(sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))) / 2
    polys = [g["arcs"]] if g["type"] == "Polygon" else g["arcs"]
    return sum(ring(p[0]) - sum(ring(h) for h in p[1:]) for p in polys if p)


def zone_shares(g, arcs):
    """Each zone's share of the outline, weighted by its area."""
    p = g["properties"]
    zs = [int(z) for z in p.get("z", "").split(",") if z]
    parts = dict(x.split(":") for x in p["p"].split(",")) if p.get("p") else {}
    a = area(g, arcs)
    return {z: a * int(parts.get(str(z), 100 if len(zs) == 1 else 0)) for z in zs}


def ordered(shares):
    return [z for z in sorted(shares, key=lambda z: (-shares[z], z))]


def build():
    topo = json.loads(SRC.read_bytes())
    arcs = decode_arcs(topo)
    by_key, by_name = {}, {}
    for g in topo["objects"]["colonias"]["geometries"]:
        p = g["properties"]
        shares = zone_shares(g, arcs)
        for target in [by_key.setdefault((p["n"], p["m"], p.get("cp", "")), {})] + [
                by_name.setdefault((fold(p["n"]), m), {}) for m in municipios(p["m"])]:
            for z, s in shares.items():
                target[z] = target.get(z, 0) + s
    rows = [[n, m, cp, ",".join(map(str, ordered(s)))] for (n, m, cp), s in sorted(by_key.items())]
    mapa = "[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n]\n"

    others = json.loads(OTHERS.read_bytes())
    changed = []
    for o in others:
        # «SIN NOMBRE» names many unrelated places.
        shares = None if fold(o["name"]) == "SIN NOMBRE" else by_name.get((fold(o["name"]), fold(o["municipio"])))
        if shares is None:
            continue
        zones = ordered(shares)
        if zones != o["zones"]:
            changed.append((o["name"], o["municipio"], o["zones"], zones))
            o["zones"] = zones
    return mapa, len(rows), json.dumps(others, ensure_ascii=False, indent=1) + "\n", changed


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if a file is out of date")
    args = ap.parse_args()
    mapa, n, others, changed = build()
    if args.check:
        for path, text in ((OUT, mapa), (OTHERS, others)):
            if not path.exists() or path.read_text(encoding="utf-8") != text:
                sys.exit(f"{path} is out of date: run python3 pipelines/mapa_colonias.py")
        print(f"{OUT.name} and {OTHERS.name}: up to date ({n} colonias)")
        return
    OUT.write_text(mapa, encoding="utf-8")
    OTHERS.write_text(others, encoding="utf-8")
    print(f"{OUT}: {n} colonias; {OTHERS}: {len(changed)} zones taken from SIAPA's map")
    for name, mun, old, new in changed:
        print(f"  {name} ({mun}): {old} -> {new}")


if __name__ == "__main__":
    main()
