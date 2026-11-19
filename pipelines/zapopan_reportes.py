"""Writes web/datos/zapopan-reportes.json, the counts behind /reportes-zapopan, from web/datos/zapopan-reportes.csv.

--check fails when the JSON is out of date or the CSV no longer adds up to the oficio's total.

The CSV is our transcription of the list the Gobierno de Zapopan delivered on 17 Nov 2026 to PNT
request 140292426004981 (web/datos/zapopan-respuesta-140292426004981.pdf, pp. 9-166, which have a
text layer): 9,828 rows, «con corte al 04 de noviembre» (oficio 11000000/CER.CIU/2026/0878, p. 5).
The PDF wraps long cells onto two or three lines; the text layer puts the first line above the row and
the last below it, and the CSV joins them («Coordinación De Cercanía Ciudadana», «RESIDENCIAL PLAZA
GUADALUPE SEGUNDA SECC»). Two rows have a blank Colonia, kept blank.
Colonias are joined to SIAPA's map (web/colonias_siapa.topo.json, municipios naming Zapopan) by name,
folded as mapa.js folds it; ALIAS holds the spelling errors joined by hand, each to one map name.
"""
import collections
import csv
import json
import pathlib
import re
import sys
import unicodedata

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "web/datos/zapopan-reportes.csv"
DEST = ROOT / "web/datos/zapopan-reportes.json"
TOPO = ROOT / "web/colonias_siapa.topo.json"
LISTA = ROOT / "api/data/colonias.json"  # SIAPA's PDF list of colonias by zone
TOTAL = 9828  # the oficio's own count (PDF p. 5)
DESDE, HASTA = "2026-10-15", "2026-11-04"  # first and last day in the list; the oficio's «corte»
BORDER = 15  # mapa.js: below this share of its area a colonia only borders a zone
PREFIXES = ["COLONIA ", "COL ", "FRACCIONAMIENTO ", "FRACC ", "FRAC "]
CANALES = ["24/7", "SIAPA"]  # the rest go together as «Otros» in the chart by day
SIN_COLONIA = {"No disponible", ""}
# Every value the PDF's Origen and Estatus columns hold; anything else is a transcription error.
ORIGENES = {"24/7", "SIAPA", "Visores Zapopan", "GuaZap", "Delegaciones", "Coordinación De Cercanía Ciudadana",
            "Agentes De Cercanía Ciudadana", "Dirección De Contacto Ciudadano", "Participación Ciudadana"}
ESTATUS = {"En proceso", "Concluido", "Resuelto", "Cancelado"}
FECHA = re.compile(r"2026/(10|11)/\d\d \d\d:\d\d:\d\d")

# Name as written (folded) -> name on SIAPA's map (folded). Only plain misspellings or a missing
# «de»/«el»/plural, and only where the map has one such colonia in Zapopan. An ALIAS never joins a
# section («NORTE», «2DA. SECCIÓN», «CONDOMINIO UNO») to its colonia or «RESIDENCIAL X» to X: either
# may be its own development (18 Nov: joining RESIDENCIAL LA ESTANCIA would put LA ESTANCIA in the
# top five). separa() enforces it for the words in SEPARA and ORDINAL, which are not every such word.
# A name SIAPA's PDF list gives beside the map's name may be another colonia (PUERTA DE ROBLE,
# PUERTA DEL ROBLE): never joined.
SEPARA = [("RESIDENCIAL", r"RES|RE\w*[SD]EN[CS]IAL\w*"), ("SECCION", r"SEC\w*"), ("CONDOMINIO", r"CONDO\w*"),
          ("NORTE", r"NORTE|NTE"), ("SUR", r"SUR"), ("ORIENTE", r"ORIENTE|OTE"), ("PONIENTE", r"PONIENTE|PTE"),
          ("ETAPA", r"ETAPA"), ("MANZANA", r"MANZANA|MZA?"), ("UNIDAD", r"UNIDAD|U"), ("SECTOR", r"SECTOR")]
ORDINAL = {"PRIMERA": 1, "PRIMER": 1, "PRIMERO": 1, "UNO": 1, "I": 1, "SEGUNDA": 2, "SEGUNDO": 2, "DOS": 2, "II": 2,
           "TERCERA": 3, "TERCER": 3, "TERCERO": 3, "TRES": 3, "III": 3, "CUARTA": 4, "CUARTO": 4, "CUATRO": 4, "IV": 4,
           "QUINTA": 5, "QUINTO": 5, "CINCO": 5, "V": 5, "SEXTA": 6, "SEXTO": 6, "SEIS": 6, "VI": 6}
ALIAS = {
    "ARCOS GUADALUPE": "ARCOS DE GUADALUPE",
    "BOSQUES DE LAS LOMAS": "BOSQUE DE LAS LOMAS",
    "BRISAS DE LA PIMAVERA": "BRISAS DE LA PRIMAVERA",
    "CHAPALIOTA DEL OCCIDENTE": "CHAPALITA DE OCCIDENTE",
    "CHAPALITA OCCIDENTE": "CHAPALITA DE OCCIDENTE",
    "CHAPLITA INN": "CHAPALITA INN",
    "COLLI URBANO": "EL COLLI URBANO",
    "GENERAL MARCELINO GARCIA BARRAGAN": "MARCELINO GARCIA BARRAGAN",
    "HACIENDAS DEL TEPEYAC": "HACIENDA DEL TEPEYAC",
    "HACIENDAS DEL VALLE": "HACIENDA DEL VALLE",
    "HACIENDAS TEPEYAC": "HACIENDA DEL TEPEYAC",
    "JARD GUADALUPE": "JARDINES DE GUADALUPE",
    "JARDINES CHAPALITA": "JARDINES DE CHAPALITA",
    "JARDINES GUADALUPE": "JARDINES DE GUADALUPE",
    "JARDINES SANTA ANA": "JARDINES DE SANTA ANA",
    "JARINES DE GUADALUPE": "JARDINES DE GUADALUPE",
    "LINDA VISTA": "LINDAVISTA",
    "OYOMEL": "OYAMEL",
    "PARQUES DEL TEPEYAC": "PARQUES TEPEYAC",
    "PATRIA UNIVERSIDAD": "LA PATRIA UNIVERSIDAD",
    "PRADOS DE GUADALUPE": "PRADOS GUADALUPE",
    "PUERTAS DEL TULE": "PUERTA DEL TULE",
    "RINCONADA DEL BOSQUE": "RINCONADAS DEL BOSQUE",
    "VALLARTA PATRIA": "VALLARTA LA PATRIA",
    "VALLE DE NUEVO MEXICO": "VALLES DE NUEVO MEXICO",
    "VILLA PLUERTA DEL SOL": "VILLA PUERTA DEL SOL",
    "VILLAS DE OTERO DE GUADALUPE": "VILLAS OTERO DE GUADALUPE",
    "VISTAS DEL PINAR": "VISTA DEL PINAR",
}


def norm(s):
    s = re.sub("[̀-ͯ]", "", unicodedata.normalize("NFD", s)).upper()
    return re.sub("[^A-Z0-9]+", " ", s).strip()


def fold(s):
    n = norm(s)
    for p in PREFIXES:
        if n.startswith(p):
            return n[len(p):]
    return n


def separa(name):
    """The words of a folded name that make it a section or a development of its own, in one spelling each
    («RESINDENCIAL» is RESIDENCIAL, «2DA», «SEGUNDA» and «II» are 2), so a join may fix their typos but not add,
    drop or change one."""
    out = []
    for w in name.split():
        n = re.fullmatch(r"(\d+)(?:A|RA|ERA|ER|DA|DO|TA|TO|O|AVA|NA)?", w)
        if n or w in ORDINAL:
            out.append(str(int(n.group(1)) if n else ORDINAL[w]))
            continue
        out += [c for c, rx in SEPARA if re.fullmatch(rx, w)][:1]
    return sorted(out)


def main_zones(props):
    """mapa.js's zonesOf().main: the largest share, and any other at BORDER or more."""
    zs = [z for z in props.get("z", "").split(",") if z]
    if len(zs) < 2 or not props.get("p"):
        return zs
    shares = {z: 0.0 for z in zs} | {z: float(v) for z, v in (part.split(":") for part in props["p"].split(",") if ":" in part)}
    ranked = sorted(zs, key=lambda z: -shares[z])
    return [z for i, z in enumerate(ranked) if i == 0 or shares[z] >= BORDER]


def tanda(rows):
    s = [r["fecha"] for r in rows if r["origen"] == "SIAPA"]
    (dia_hora, n), = collections.Counter(f[:13] for f in s).most_common(1)
    minutos = collections.Counter(f[:16] for f in s if f.startswith(dia_hora))
    return {"dia": dia_hora[:10].replace("/", "-"), "hora": int(dia_hora[11:]), "n": n, "max_minuto": max(minutos.values())}


def build():
    with SRC.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != TOTAL:
        sys.exit(f"{SRC.name}: {len(rows)} rows, the oficio says {TOTAL}")
    if len({r["folio"] for r in rows}) != len(rows):
        sys.exit(f"{SRC.name}: repeated folios")
    for n, r in enumerate(rows, 2):
        bad = ("fecha" if not FECHA.fullmatch(r["fecha"]) else "origen" if r["origen"] not in ORIGENES
               else "estatus" if r["estatus"] not in ESTATUS else "colonia" if r["colonia"] in ORIGENES else None)
        if bad:
            sys.exit(f"{SRC.name}:{n}: {r['folio']} has {bad} {r[bad]!r}")

    topo = json.loads(TOPO.read_text())
    mapa = collections.defaultdict(list)
    for g in topo["objects"]["colonias"]["geometries"]:
        p = g["properties"]
        if "Zapopan" in p.get("m", ""):
            mapa[fold(p["n"])].append(p)
    lista = {fold(c["name"]) for c in json.loads(LISTA.read_text()) if c["municipio"] == "ZAPOPAN"}
    if not lista:
        sys.exit(f"{LISTA.name}: no Zapopan colonias")
    if not ALIAS:
        sys.exit("ALIAS is empty: the spelling-join checks examined nothing")
    for k, v in ALIAS.items():
        if v not in mapa:
            sys.exit(f"ALIAS {k!r} -> {v!r}: not a Zapopan colonia on SIAPA's map")
        if k in mapa:
            sys.exit(f"ALIAS {k!r}: already a Zapopan colonia on SIAPA's map")
        if k in lista and v in lista:
            sys.exit(f"ALIAS {k!r} -> {v!r}: SIAPA's list names both in Zapopan, they may be two colonias")
        if separa(k) != separa(v):
            sys.exit(f"ALIAS {k!r} -> {v!r}: adds, drops or changes a section, number or «residencial» "
                     f"({separa(k)} vs {separa(v)}), it may be another place")

    dias = collections.defaultdict(lambda: collections.Counter())
    estatus, origen = collections.Counter(), collections.Counter()
    canal_dias, canal_horas = collections.defaultdict(set), collections.defaultdict(collections.Counter)
    grupos, usados = {}, set()
    for r in rows:
        dia = r["fecha"][:10].replace("/", "-")
        canal = r["origen"] if r["origen"] in CANALES else "Otros"
        dias[dia][canal] += 1
        canal_dias[canal].add(dia)
        canal_horas[canal][int(r["fecha"][11:13])] += 1
        estatus[r["estatus"]] += 1
        origen[r["origen"]] += 1
        if r["colonia"] in SIN_COLONIA:
            continue
        k = fold(r["colonia"])
        usados.add(k)
        k = ALIAS.get(k, k)
        g = grupos.setdefault(k, {"n": 0, "proceso": 0, "escrito": collections.Counter()})
        g["n"] += 1
        g["proceso"] += r["estatus"] == "En proceso"
        g["escrito"][r["colonia"]] += 1

    if set(ALIAS) - usados:
        sys.exit(f"ALIAS keys no row uses: {sorted(set(ALIAS) - usados)}")
    if (DESDE, HASTA) != (min(dias), max(dias)):
        sys.exit(f"{SRC.name}: runs {min(dias)} to {max(dias)}, not {DESDE} to {HASTA}")

    colonias = []
    for k, g in grupos.items():
        polys = mapa.get(k, [])
        zonas = sorted({z for p in polys for z in main_zones(p)}, key=int)
        # A name the map gives to several colonias in different zones: its reports can't go to one zone.
        por_poligono = sorted({tuple(sorted(main_zones(p), key=int)) for p in polys}, key=lambda zs: [int(z) for z in zs] or [99])
        varias = len(por_poligono) > 1
        escrito = [e for e, _ in sorted(g["escrito"].items(), key=lambda x: (-x[1], x[0]))]
        colonias.append({
            "colonia": polys[0]["n"] if polys else escrito[0],
            "clave": k if polys else None,
            "reportes": g["n"],
            "en_proceso": g["proceso"],
            "zonas": zonas,
            "varias_zonas": varias,
            # Each polygon's own zones, once per distinct set: what the table shows for a repeated name.
            "zonas_poligonos": [list(zs) for zs in por_poligono],
            "poligonos": len(polys),
            "escrito": escrito,
        })
    colonias.sort(key=lambda c: (-c["reportes"], c["colonia"]))

    en_mapa = sum(c["reportes"] for c in colonias if c["clave"])
    zonas = collections.Counter()
    for c in colonias:
        if c["clave"]:
            zonas["varias" if c["varias_zonas"] else " y ".join(c["zonas"]) or "sin zona"] += c["reportes"]
    out = {
        "fuente": {
            "folio": "140292426004981",
            "oficio": "02050000/2026/7942",
            "fecha_oficio": "2026-11-17",
            "oficio_area": "11000000/CER.CIU/2026/0878",
            "area": "Coordinación General de Cercanía Ciudadana",
            "fecha_area": "2026-11-06",
            "pdf": "/datos/zapopan-respuesta-140292426004981.pdf",
            "csv": "/datos/zapopan-reportes.csv",
        },
        "total": len(rows),
        "desde": min(dias),
        "hasta": max(dias),
        "sin_colonia": sum(1 for r in rows if r["colonia"] in SIN_COLONIA),
        "en_mapa": en_mapa,
        "alias": len(ALIAS),
        "estatus": estatus.most_common(),
        "origen": origen.most_common(),
        "por_zona": zonas.most_common(),
        "canales": CANALES + ["Otros"],
        # Days on which each channel has a report, and its busiest hour of the day: [hour, reports].
        "canal_dias": {c: len(canal_dias[c]) for c in CANALES + ["Otros"]},
        "canal_hora": {c: list(canal_horas[c].most_common(1)[0]) for c in CANALES + ["Otros"]},
        # The SIAPA channel's busiest hour of one day: how many, and the most in one minute.
        "tanda": tanda(rows),
        "dias": [{"dia": d, **{c: dias[d][c] for c in CANALES + ["Otros"]}} for d in sorted(dias)],
        "colonias": colonias,
    }
    return out


def main():
    out = build()
    text = json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n"
    n_col = len(out["colonias"])
    on_map = sum(1 for c in out["colonias"] if c["clave"])
    summary = (f"{out['total']} reports, {len(out['dias'])} days, {n_col} colonias ({on_map} on SIAPA's map, {out['en_mapa']} reports), "
               f"{out['alias']} spelling joins checked")
    if n_col == 0 or on_map == 0 or out["en_mapa"] == 0:
        sys.exit("zapopan_reportes: no colonias joined")
    if "--check" in sys.argv:
        if not DEST.exists() or DEST.read_text() != text:
            sys.exit(f"{DEST.relative_to(ROOT)} is out of date: run python3 pipelines/zapopan_reportes.py")
        print(f"{DEST.relative_to(ROOT)} up to date: {summary}")
        return
    DEST.write_text(text)
    print(f"wrote {DEST.relative_to(ROOT)}: {summary}, {DEST.stat().st_size // 1024} KB")


if __name__ == "__main__":
    main()
