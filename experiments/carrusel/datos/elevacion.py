#!/usr/bin/env python3
"""Elevation of each SIAPA colonia and how it lines up with the publications about missing water.

    python3 experiments/carrusel/datos/elevacion.py            fetch missing elevations, write elevacion.json and stats.json
    python3 experiments/carrusel/datos/elevacion.py --stats    recompute stats.json from elevacion.json only

Each colonia's point is the area centroid of its largest polygon in web/colonias_siapa.topo.json (SIAPA's map).
Elevation comes from the Copernicus DEM GLO-90 (90 m) through Open-Meteo's elevation API; only coordinates are
sent. Publications come from the live https://aguagdl.com/publicaciones.json. A colonia is "in the rotation" when
SIAPA's map gives it a zone. The point elevation is approximate: a colonia spans a range of heights.
"""
import collections
import json
import pathlib
import statistics as st
import sys
import time
import urllib.error
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ELEV = HERE / "elevacion.json"
STATS = HERE / "stats.json"
API = "https://api.open-meteo.com/v1/elevation"
PUB = "https://aguagdl.com/publicaciones.json"
FOCO = "CIUDAD GRANJA|Zapopan|45010"


def centroides():
    t = json.loads((ROOT / "web/colonias_siapa.topo.json").read_text())
    (sx, sy), (tx, ty) = t["transform"]["scale"], t["transform"]["translate"]
    arcs = []
    for a in t["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in a:
            x, y = x + dx, y + dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(r):
        out = []
        for i in r:
            out += arcs[i] if i >= 0 else arcs[~i][::-1]
        return out

    def centroid(pts):
        a = cx = cy = 0
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
            c = x0 * y1 - x1 * y0
            a, cx, cy = a + c, cx + (x0 + x1) * c, cy + (y0 + y1) * c
        a /= 2
        return (cx / (6 * a), cy / (6 * a), abs(a)) if a else (pts[0][0], pts[0][1], 0)

    out = {}
    for g in t["objects"]["colonias"]["geometries"]:
        p = g["properties"]
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]] if g["type"] == "Polygon" else []
        best = max((centroid(ring(poly[0])) for poly in polys), key=lambda c: c[2], default=None)
        if best:
            out[f"{p['n']}|{p['m']}|{p['cp']}"] = {"lon": round(best[0], 5), "lat": round(best[1], 5), "zona": p["z"]}
    return out


def fetch(cols, have):
    keys = sorted(k for k in cols if have.get(k, {}).get("m") is None)
    for i in range(0, len(keys), 100):
        ks = keys[i:i + 100]
        url = f"{API}?latitude={','.join(str(cols[k]['lat']) for k in ks)}&longitude={','.join(str(cols[k]['lon']) for k in ks)}"
        for attempt in range(6):
            try:
                r = json.load(urllib.request.urlopen(url, timeout=30))
                break
            except urllib.error.HTTPError:
                time.sleep(20 * (attempt + 1))
        else:
            sys.exit("elevacion: Open-Meteo kept refusing; rerun later")
        for k, m in zip(ks, r["elevation"]):
            have[k] = {**cols[k], "m": m}
        time.sleep(4)
    return have


def rank(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    r, i = [0.0] * len(v), 0
    while i < len(v):
        j = i
        while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = rank(a), rank(b)
    ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    return num / (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5


def stats(elev):
    data = json.load(urllib.request.urlopen(urllib.request.Request(PUB, headers={"User-Agent": "Mozilla/5.0 (agua-gdl carrusel)"}), timeout=30))
    pubs = data["publicaciones"]
    cnt = collections.Counter(k for x in pubs for k in x["colonias"])
    dias = collections.defaultdict(int)
    for x in pubs:
        for k in x["colonias"]:
            dias[k] = max(dias[k], x.get("dias") or 0)
    rot = [k for k, v in elev.items() if v["zona"] and v["zona"] != "0"]
    alt = sorted(elev[k]["m"] for k in rot)
    foco = elev[FOCO]["m"]
    med = st.median(alt)
    lo = 20 * int(alt[0] // 20)
    bins = collections.Counter(20 * int(m // 20) for m in alt)
    top = cnt.most_common(5)
    con = [k for k in rot if cnt[k]]
    condias = [k for k in rot if dias[k]]
    hi, lw = [k for k in rot if elev[k]["m"] > med], [k for k in rot if elev[k]["m"] <= med]
    return {
        "publicaciones_actualizado": data["actualizado"],
        "colonias_en_rotacion": len(rot),
        "foco": FOCO, "foco_m": foco,
        "mediana_m": med, "min_m": alt[0], "max_m": alt[-1],
        "pct_rotacion_mas_bajas_que_foco": round(100 * sum(m < foco for m in alt) / len(alt), 1),
        "bins_20m": [{"desde": b, "n": bins.get(b, 0)} for b in range(lo, int(alt[-1]) + 20, 20)],
        "top5_publicaciones": [{"colonia": k, "publicaciones": n, "m": elev[k]["m"], "vs_mediana_m": round(elev[k]["m"] - med)} for k, n in top],
        "mitad_alta_con_publicaciones": [sum(1 for k in hi if cnt[k]), len(hi)],
        "mitad_baja_con_publicaciones": [sum(1 for k in lw if cnt[k]), len(lw)],
        "spearman_altura_publicaciones": {"rho": round(spearman([elev[k]["m"] for k in con], [cnt[k] for k in con]), 2), "n": len(con)},
        "spearman_altura_dias": {"rho": round(spearman([elev[k]["m"] for k in condias], [dias[k] for k in condias]), 2), "n": len(condias)},
    }


def main():
    elev = json.loads(ELEV.read_text()) if ELEV.exists() else {}
    if "--stats" not in sys.argv:
        elev = fetch(centroides(), elev)
        ELEV.write_text(json.dumps(dict(sorted(elev.items())), ensure_ascii=False, indent=0) + "\n")
    s = stats(elev)
    STATS.write_text(json.dumps(s, ensure_ascii=False, indent=1) + "\n")
    print(json.dumps({k: v for k, v in s.items() if k != "bins_20m"}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
