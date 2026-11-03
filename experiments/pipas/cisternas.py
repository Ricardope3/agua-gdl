"""Writes web/cisternas.json, the community water points the /pipas variants map, from cisternas_fuente.json.

Exact points only where an official map gives coordinates; where a source names only a colonia,
the colonia's outline from web/colonias_siapa.topo.json.
"""
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]


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
            pts.append((round(y * sy + ty, 6), round(x * sx + tx, 6)))
        arcs.append(pts)
    return arcs


def ring(arcs, idxs):
    out = []
    for i in idxs:
        pts = arcs[i] if i >= 0 else arcs[~i][::-1]
        out.extend(pts if not out else pts[1:])
    return out


def outline(arcs, geom):
    polys = geom["arcs"] if geom["type"] == "MultiPolygon" else [geom["arcs"]]
    return [[ring(arcs, r) for r in poly] for poly in polys]


def main():
    src = json.loads((HERE / "cisternas_fuente.json").read_text())
    topo = json.loads((ROOT / "web/colonias_siapa.topo.json").read_text())
    arcs = decode_arcs(topo)
    geoms = topo["objects"]["colonias"]["geometries"]
    colonias = []
    for c in src["colonias"]:
        hits = [g for g in geoms if g["properties"]["m"] == c["municipio"] and g["properties"]["n"] == c["colonia"]]
        if len(hits) != 1:
            raise SystemExit(f"{c['municipio']} {c['colonia']}: {len(hits)} matches in the SIAPA layer")
        colonias.append({**c, "forma": outline(arcs, hits[0])})
    out = {
        "revisado": "2026-11-03",
        "fuentes": src["fuentes"],
        "puntos": src["puntos"],
        "colonias": colonias,
        "sin_coordenadas": src["sin_coordenadas"],
        "sin_ubicar": src["sin_ubicar"],
    }
    dest = ROOT / "web/cisternas.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")))
    print(f"wrote {dest}: {len(out['puntos'])} points, {len(colonias)} colonias, {dest.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
