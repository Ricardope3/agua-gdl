"""Writes web/cisternas.json, the community water points on /avisos, /reportes and the /pipas variants, from cisternas_fuente.json.

--check fails when web/cisternas.json is out of date.

Exact points only where an official map gives coordinates; where a source names only a colonia,
the colonia's outline from web/colonias_siapa.topo.json.
"""
import json
import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent


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


def centre(ring):
    a = cx = cy = 0.0
    for (y1, x1), (y2, x2) in zip(ring, ring[1:] + ring[:1]):
        k = x1 * y2 - x2 * y1
        a += k
        cx += (x1 + x2) * k
        cy += (y1 + y2) * k
    return [round(cy / (3 * a), 6), round(cx / (3 * a), 6)]


FIELDS = {
    "fuentes": {"mapa", "titulo", "url"},
    "puntos": {"capa", "fuente", "lat", "lon", "lugar", "municipio"},
    "colonias": {"colonia", "fuente", "lugar", "municipio", "nombre"},
    "sin_coordenadas": {"fuente", "lugar", "municipio"},
    "sin_ubicar": {"fuente", "lugar", "municipio"},
}


def allowed(src):
    """Publish only listed fields: a source field such as a responsible person's name must never reach the site."""
    for key, fields in FIELDS.items():
        rows = src[key].values() if isinstance(src[key], dict) else src[key]
        for row in rows:
            if extra := set(row) - fields:
                raise SystemExit(f"cisternas_fuente.json {key}: field(s) not allowed on the site: {sorted(extra)}")


def main():
    src = json.loads((HERE / "cisternas_fuente.json").read_text(encoding="utf-8"))
    allowed(src)
    topo = json.loads((ROOT / "web/colonias_siapa.topo.json").read_text(encoding="utf-8"))
    arcs = decode_arcs(topo)
    geoms = topo["objects"]["colonias"]["geometries"]
    colonias = []
    for c in src["colonias"]:
        hits = [g for g in geoms if g["properties"]["m"] == c["municipio"] and g["properties"]["n"] == c["colonia"]]
        if len(hits) != 1:
            raise SystemExit(f"{c['municipio']} {c['colonia']}: {len(hits)} matches in the SIAPA layer")
        forma = outline(arcs, hits[0])
        colonias.append({**c, "centro": centre(max((poly[0] for poly in forma), key=len)), "forma": forma})
    # The day the sources were last checked lives beside them, so editing one means moving it.
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(src.get("revisado"))):
        raise SystemExit("cisternas_fuente.json: revisado must be the ISO date the sources were last checked")
    out = {
        "revisado": src["revisado"],
        "fuentes": src["fuentes"],
        "puntos": src["puntos"],
        "colonias": colonias,
        "sin_coordenadas": src["sin_coordenadas"],
        "sin_ubicar": src["sin_ubicar"],
    }
    dest = ROOT / "web/cisternas.json"
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    if "--check" in sys.argv:
        if not dest.exists() or dest.read_text(encoding="utf-8") != text:
            raise SystemExit("web/cisternas.json is stale: run python3 pipelines/cisternas.py")
        print(f"web/cisternas.json up to date: {len(out['puntos'])} points, {len(colonias)} colonias")
        return
    dest.write_text(text, encoding="utf-8")
    print(f"wrote {dest}: {len(out['puntos'])} points, {len(colonias)} colonias, {dest.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
