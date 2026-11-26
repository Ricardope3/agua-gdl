"""What Nestlé's Jalisco plants reported releasing to water in SEMARNAT's RETC, 2004–2024, for /contamina-nestle.

Usage: python3 experiments/contamina-nestle/retc.py [retc-nestle-jalisco-2004-2024.csv]
The CSV (87 rows) was cut from SEMARNAT's «RETC_Verificado_2004-2024.zip» by the private research repo's
scripts/retc_nestle.py on 25 Nov 2026; it stays there with the zip. This script writes retc.json beside it.
The figures are the companies' own reports, converted to kg (ton and ton/año x 1000, kg and kg/año x 1, g / 1000).
Metals are the substances whose name starts Arsénico, Cadmio, Cromo, Mercurio, Níquel or Plomo (our grouping).
DUDOSAS lists the plant-years the research notes flag as possible reporting errors (README, finding 6), plus a repeated value: the page
leaves their figures out until SEMARNAT confirms them.
"""
import csv, json, pathlib, sys
from collections import defaultdict

SRC = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else pathlib.Path.home() / "agua-gdl/research/nestle-jalisco-2026-11-25/captures/retc-nestle-jalisco-2004-2024.csv")
MET = ("Arsénico", "Cadmio", "Cromo", "Mercurio", "Níquel", "Plomo")
# 2023 NME1406300025: its cadmium, 15.886 kg, repeats 2022's to the gram (found 25 Nov 2026, writing the page).
DUDOSAS = {("2021", "NME1406300025", "cianuro"), ("2022", "NME1406300025", "metales"), ("2022", "NMEML1406311", "metales"), ("2023", "NME1406300025", "metales")}


def kg(unidad):
    u = unidad.strip().lower()
    return 1000.0 if u.startswith("ton") else 1.0 if u.startswith("kg") else 0.001 if u == "g" else None


rows = list(csv.DictReader(SRC.open(encoding="utf-8")))
assert len(rows) == 87, len(rows)
tot = defaultdict(float)
sust = defaultdict(lambda: defaultdict(float))
info = {}
for r in rows:
    m = kg(r["unidad"])
    assert m is not None, r["unidad"]
    v = float(r["agua"]) * m if r["agua"].strip() not in ("", "-") else 0.0
    grupo = "metales" if r["sustancia"].startswith(MET) else "cianuro" if r["sustancia"].startswith("Cianuro") else None
    if not grupo or not v:
        continue
    k = (r["year"], r["NRA"], grupo)
    tot[k] += v
    sust[k][r["sustancia"]] += v
    info[r["NRA"]] = r["municipio"].replace("Ocotlan", "Ocotlán")
out = []
for (y, nra, g), v in sorted(tot.items()):
    out.append({"año": y, "nra": nra, "municipio": info[nra], "grupo": g, "kg": round(v, 2),
                "dudosa": (y, nra, g) in DUDOSAS,
                "sustancias": {s: round(x, 3) for s, x in sorted(sust[(y, nra, g)].items())}})
assert all(any(o["año"] == y and o["nra"] == n and o["grupo"] == g for o in out) for y, n, g in DUDOSAS)
res = {"fuente": "SEMARNAT, RETC verificado 2004–2024 (zip descargado el 25 nov 2026), filas de Nestlé en Jalisco",
       "filas_csv": len(rows), "agua": out,
       "suma_sin_dudosas_kg": {g: round(sum(sum(o["sustancias"].values()) for o in out if o["grupo"] == g and not o["dudosa"]), 2) for g in ("metales", "cianuro")}}
(pathlib.Path(__file__).parent / "retc.json").write_text(json.dumps(res, ensure_ascii=False, indent=1) + "\n")
for o in out:
    print(o["año"], o["nra"], o["municipio"], o["grupo"], o["kg"], "DUDOSA" if o["dudosa"] else "", o["sustancias"])
print(res["suma_sin_dudosas_kg"])
