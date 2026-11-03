#!/usr/bin/env python3
"""Write one static page per colonia of SIAPA's map, so an assistant that can only GET answers
«¿cuándo cortan el agua en mi colonia?» with one fetch and cites it:

- web/colonia/<slug>.json: name, municipio, postal code, zones with their share of area, the cut
  weekdays per zone, the rotation's end, checked date and source.
- web/colonia/<slug>.html: the same in plain Spanish, without JavaScript.
- web/colonia/index.html: every colonia A–Z.

Sources: api/data/colonias_mapa.json (keys), web/colonias_siapa.topo.json (area shares, through
mapa_colonias.py) and api/data/rotation.json (days). No next dates: they would go stale.

Slugs: name-municipio, lowercased, accents dropped, other characters as «-» (no prefix stripping), plus -<cp> for every colonia whose name and municipio repeat
with another postal code; the build fails if two colonias still share a slug. A slug changes only
if SIAPA's map adds a colonia with the same name and municipio.

Usage: python3 pipelines/colonia_pages.py [--check]
"""
import argparse
import html
import json
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mapa_colonias  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
COLONIAS = ROOT / "api" / "data" / "colonias_mapa.json"
ROTATION = ROOT / "api" / "data" / "rotation.json"
LIST = ROOT / "api" / "data" / "colonias.json"
OUT = ROOT / "web" / "colonia"
ORIGIN = "https://aguagdl.com"
DAYS = {"sun": "domingo", "mon": "lunes", "tue": "martes", "wed": "miércoles", "thu": "jueves", "fri": "viernes", "sat": "sábado"}
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
BORDER = 15  # as web/mapa.js: below this share a zone is only «al límite»
NOTE = ("No oficial. Los días son días CON corte según el calendario del SIAPA. El SIAPA dice que no son "
        "cortes totales; vecinos reportan que el agua se va antes y tarda en volver.")


def slug(s):
    plain = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", plain).strip("-")


def fecha(iso):
    y, m, d = map(int, iso.split("-"))
    return f"{d} de {MONTHS[m - 1]} de {y}"


def shares():
    """Percent of area per zone for each (name, municipio, cp), as mapa_colonias.py adds them."""
    topo = json.loads(mapa_colonias.SRC.read_bytes())
    arcs = mapa_colonias.decode_arcs(topo)
    by_key = defaultdict(lambda: defaultdict(float))
    for g in topo["objects"]["colonias"]["geometries"]:
        p = g["properties"]
        for z, s in mapa_colonias.zone_shares(g, arcs).items():
            by_key[(p["n"], p["m"], p.get("cp", ""))][z] += s
    return by_key


def slugs(rows):
    groups = defaultdict(list)
    for n, m, cp, _ in rows:
        groups[f"{slug(n)}-{slug(m)}"].append((n, m, cp))
    out = {}
    for base, keys in groups.items():
        for k in keys:
            out[k] = base if len(keys) == 1 else f"{base}-{k[2] or 'sin-cp'}"
    if len(set(out.values())) != len(out):
        sys.exit("colonia_pages: two colonias share a slug; extend the scheme")
    return out


def page(title, desc, canonical, body):
    return (f'<!doctype html>\n<html lang="es-MX"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{title}</title><meta name="description" content="{desc}">\n'
            f'<link rel="canonical" href="{canonical}"><meta name="theme-color" content="#ffffff"><link rel="icon" href="/favicon.ico" sizes="any"><script src="/theme.js"></script>\n'
            '<style>:root{--bg:#fbfaf6;--fg:#14213d;--muted:#4f5b7a;--brand:#1d3f9e}body{margin:0;background:var(--bg);color:var(--fg);font:18px/1.6 system-ui,-apple-system,sans-serif}'
            'main{max-width:800px;margin:auto;padding:16px}a{color:var(--brand)}small{color:var(--muted)}'
            '@media(prefers-color-scheme:dark){:root{--bg:#0c1328;--fg:#eef1fb;--muted:#a6b1d6;--brand:#a9bdfa}}</style></head>\n'
            f'<body><main>{body}</main></body></html>\n')


def build():
    rows = json.loads(COLONIAS.read_bytes())
    rot = json.loads(ROTATION.read_bytes())
    area = shares()
    names = slugs(rows)
    key = lambda n, m: (mapa_colonias.fold(n), mapa_colonias.fold(m).removeprefix("SAN PEDRO "))
    listed = {key(c["name"], c["municipio"]): c["zones"] for c in json.loads(LIST.read_bytes())}
    files, index = {}, []
    source, checked, end = rot["source"], rot["checked"], rot.get("end", "")
    for n, m, cp, zs in rows:
        s = names[(n, m, cp)]
        a = area[(n, m, cp)]
        total = sum(a.values()) or 1
        zones = []
        for z in (int(x) for x in zs.split(",") if x):
            zones.append({"zone": z, "share": round(100 * a.get(z, 0) / total),
                          "days": [DAYS[d] for d in rot["zones"][str(z)]],
                          "calendar": f"{ORIGIN}/calendario/zona-{z}.ics",
                          "telegram": f"https://t.me/AvisoAguaGDLbot?start=z{z}"})
        lz = listed.get(key(n, m))
        differs = lz is not None and sorted(lz) != sorted(z["zone"] for z in zones)
        q = urlencode({"q": n, "m": m, "cp": cp})
        data = {"name": n, "municipio": m, "cp": cp, "zones": zones, **({"list_zones": lz, "list_differs": True} if differs else {}), "rotation_end": end,
                "checked": checked, "source": source, "unofficial": True, "note": NOTE,
                "page": f"{ORIGIN}/colonia/{s}", "map": f"{ORIGIN}/avisos?{q}"}
        files[f"{s}.json"] = json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n"

        e = html.escape
        if not zones:
            items = "<p>El mapa de la rotación del SIAPA no le da zona a esta colonia. Eso no confirma que tenga agua.</p>"
        else:
            items = "<ul>" + "".join(
                f'<li><strong>Zona {z["zone"]}</strong>' + (f' ({z["share"]} % del área)' if len(zones) > 1 else "")
                + (" · al límite" if len(zones) > 1 and z["share"] < BORDER else "")
                + f': días de corte {", ".join(z["days"])}. <a href="/calendario/zona-{z["zone"]}.ics">Calendario</a> · '
                f'<a href="https://t.me/AvisoAguaGDLbot?start=z{z["zone"]}" rel="noopener">Avisos por Telegram</a></li>'
                for z in zones) + "</ul>"
            if len(zones) > 1:
                items += "<p>La colonia está repartida entre zonas: depende de tu calle. Revísalo en el mapa.</p>"
        if differs:
            items += (f"<p>Ojo: la lista de colonias del SIAPA le da {'la zona' if len(lz) == 1 else 'las zonas'} {', '.join(map(str, lz))} a «{e(n)}» de {e(m)}; "
                      "su mapa y su lista no coinciden. Confírmalo en el mapa o con el SIAPA.</p>")
        where = f"{e(n)}, {e(m)}" + (f", C.P. {e(cp)}" if cp else "")
        body = (f'<p><a href="/">Agua GDL</a> · <a href="/colonia/">Colonias</a></p><h1>¿Cuándo cortan el agua en {e(n)}?</h1>'
                f'<p>{where}</p>{items}'
                f'<p><small>{e(NOTE)} Calendario del SIAPA verificado el {fecha(checked)}; la rotación termina el {fecha(end)}. '
                f'Fuente: <a href="https://rotaciondeserviciosiapa.jalisco.gob.mx/" rel="noopener">SIAPA</a>.</small></p>'
                f'<p><a href="/avisos?{e(q)}">Ver en el mapa y próximas fechas</a> · <a href="/reportes?{e(q)}">¿Hay agua? Reporta</a> · '
                f'<a href="/colonia/{s}.json">Datos (JSON)</a></p>')
        zt = ", ".join(f"zona {z['zone']}" for z in zones) or "sin zona"
        files[f"{s}.html"] = page(f"Cortes de agua en {e(n)}, {e(m)} · Agua GDL",
                                  f"Días de corte de agua de la rotación del SIAPA en {where}: {zt}.",
                                  f"{ORIGIN}/colonia/{s}", body)
        index.append((mapa_colonias.fold(n), m, cp, s, n))
    index.sort()
    li = "".join(f'<li><a href="/colonia/{s}">{html.escape(n)}</a> <small>{html.escape(m)}{" " + cp if cp else ""}</small></li>'
                 for _, m, cp, s, n in index)
    files["index.html"] = page("Colonias A–Z · Agua GDL", "Días de corte de agua por colonia según la rotación del SIAPA.",
                               f"{ORIGIN}/colonia/", f'<p><a href="/">Agua GDL</a></p><h1>Colonias A–Z</h1><p><small>{NOTE}</small></p><ul>{li}</ul>')
    return files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    files = build()
    have = {p.name for p in OUT.glob("*")} if OUT.exists() else set()
    if args.check:
        stale = have ^ set(files) or any((OUT / f).read_text(encoding="utf-8") != t for f, t in files.items())
        if stale:
            sys.exit("web/colonia/ is stale: run python3 pipelines/colonia_pages.py")
        print(f"colonia/: up to date ({len(files) - 1} colonias)")
        return
    OUT.mkdir(exist_ok=True)
    for f in have - set(files):
        (OUT / f).unlink()
    for f, t in files.items():
        (OUT / f).write_text(t, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(files)} files, {sum(len(t.encode()) for t in files.values())} bytes")


if __name__ == "__main__":
    main()
