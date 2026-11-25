"""Groundwater permits in Ocotlán by use, Nestlé apart, from CONAGUA's REPDA export (carousel 24).

Usage: python3 experiments/carrusel/datos/nestle_repda.py [export.csv]
The export («Búsqueda avanzada», aguas subterráneas, Jalisco, Ocotlán, cut-off 16 Nov 2026, saved 25 Nov 2026)
names natural persons, so it stays in the private research repo; only these sums are committed.
Volumes are permits (m³ a year CONAGUA allows), not water drawn.
"""
import csv, json, pathlib, sys
from collections import defaultdict

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path.home() / "agua-gdl/research/nestle-jalisco-2026-11-25/captures/export-ocotlan-subterraneas/repda-ocotlan-subterraneas-2026-11-25.csv")
rows = list(csv.reader(SRC.read_text(encoding="utf-8-sig").splitlines()))[1:]
num = lambda s: float(s.replace(",", "").replace(" ", "") or 0)
vol, n = defaultdict(float), defaultdict(int)
nestle = []
for r in rows:
    k = r[2].strip() + (" (NESTLE)" if "NESTL" in r[0].upper() else "")
    vol[k] += num(r[9]); n[k] += 1
    if "NESTL" in r[0].upper():
        nestle.append({"titulo": r[1].strip(), "m3_anio": num(r[9])})
total = sum(vol.values())
assert len(nestle) == 5 and round(vol["INDUSTRIAL (NESTLE)"]) == 2330753, (len(nestle), vol["INDUSTRIAL (NESTLE)"])
out = {
    "fuente": "CONAGUA, REPDA, exportación de aguas subterráneas de Ocotlán, Jalisco; corte 16 nov 2026; descargada 25 nov 2026",
    "filas": len(rows),
    "total_m3_anio": round(total, 2),
    "por_uso": {k: {"titulos": n[k], "m3_anio": round(vol[k], 2)} for k in sorted(vol, key=lambda k: -vol[k])},
    "nestle": sorted(nestle, key=lambda x: -x["m3_anio"]),
    "nestle_entre_publico_urbano": round(vol["INDUSTRIAL (NESTLE)"] / vol["PUBLICO URBANO"], 2),
    "mayor_titulo_del_municipio_es_de_nestle": max(num(r[9]) for r in rows) == max(x["m3_anio"] for x in nestle),
}
dst = pathlib.Path(__file__).with_name("nestle_repda.json")
dst.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps(out, ensure_ascii=False))
