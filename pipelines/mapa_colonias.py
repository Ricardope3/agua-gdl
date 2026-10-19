#!/usr/bin/env python3
"""Write api/data/colonias_mapa.json, the colonias people can report on /reportes.

Usage: python3 pipelines/mapa_colonias.py [--check]

Reads web/colonias_siapa.topo.json (built by pipelines/siapa_mapa.py) and lists each colonia
once as [name, municipio, postal code, zones]: the key the page sends and the API checks.
Name, municipio and postal code repeat on 56 outlines that are pieces of one colonia, so
their reports count together, and their zones are joined, the one with most of the colonia's
area first (the count on /reportes puts a report in that zone). Run it after siapa_mapa.py;
--check fails when the file is stale (internal/webreports's test checks it too).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "web" / "colonias_siapa.topo.json"
OUT = ROOT / "api" / "data" / "colonias_mapa.json"


def build():
    topo = json.loads(SRC.read_bytes())
    shares = {}
    for g in topo["objects"]["colonias"]["geometries"]:
        p = g["properties"]
        share = shares.setdefault((p["n"], p["m"], p.get("cp", "")), {})
        zs = [int(z) for z in p.get("z", "").split(",") if z]
        parts = dict(x.split(":") for x in p["p"].split(",")) if p.get("p") else {}
        for z in zs:
            share[z] = share.get(z, 0) + int(parts.get(str(z), 100 if len(zs) == 1 else 0))
    order = lambda s: ",".join(str(z) for z in sorted(s, key=lambda z: (-s[z], z)))  # noqa: E731
    rows = [[n, m, cp, order(s)] for (n, m, cp), s in sorted(shares.items())]
    return "[\n" + ",\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n]\n", len(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="fail if the file is out of date")
    args = ap.parse_args()
    text, n = build()
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != text:
            sys.exit(f"{OUT} is out of date: run python3 pipelines/mapa_colonias.py")
        print(f"{OUT}: up to date ({n} colonias)")
        return
    OUT.write_text(text, encoding="utf-8")
    print(f"{OUT}: {n} colonias")


if __name__ == "__main__":
    main()
