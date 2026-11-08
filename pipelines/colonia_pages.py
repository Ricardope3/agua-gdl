#!/usr/bin/env python3
"""Write one static page per colonia of SIAPA's map, so an assistant that can only GET answers
«¿cuándo cortan el agua en mi colonia?» with one fetch and cites it:

- web/colonia/<slug>.json: name, municipio, postal code, zones with their share of area, the cut
  weekdays per zone, the rotation's end, checked date and source.
- web/colonia/<slug>.html: the same in plain Spanish, without JavaScript.
- web/colonia/index.html: every colonia A–Z.
- web/colonia/municipio-<slug>.html: each municipio's colonias grouped by zone, then those
  without one (a colonia in two municipios is listed under both).

A colonia that SIAPA's map gives no zone, and whose list doesn't either, carries noindex: its
page says only that, and the municipio page carries the fact for all of them.

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
NOTE = ("No oficial. Los días son días CON corte según el calendario del SIAPA. El Gobierno de Jalisco dice "
        "que no son cortes totales; vecinos reportan que el agua se va antes y tarda en volver.")


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


FOOTER = ('<footer><p>Agua GDL es una iniciativa ciudadana, no oficial y sin partido. No tiene relación con el SIAPA ni con el Gobierno de Jalisco.</p>'
          '<p class="enlaces"><a href="/">Inicio</a> · <a href="/colonia/">Colonias A–Z</a> · <a href="/avisos">¿Qué zona me toca?</a> · '
          '<a href="/pipas">Pedir una pipa</a> · <a href="/transparencia">Quién hace Agua GDL</a> · <a href="/correcciones">Corregir un dato</a></p></footer>')


def crumbs(trail):
    """BreadcrumbList JSON-LD for [(name, url), …]."""
    items = [{"@type": "ListItem", "position": i, "name": n, "item": u} for i, (n, u) in enumerate(trail, 1)]
    ld = json.dumps({"@context": "https://schema.org", "@type": "BreadcrumbList", "itemListElement": items}, ensure_ascii=False, separators=(",", ":"))
    return '<script type="application/ld+json">' + ld.replace("</", "<\\/") + "</script>"


def y(xs):
    """[5, 7] → «5 y 7»; [lunes, jueves, viernes] → «lunes, jueves y viernes»."""
    xs = [str(x) for x in xs]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " y " + xs[-1]


def municipios(m):
    """«San Pedro Tlaquepaque y Tonalá» → both; a colonia on a border is listed under each."""
    return [x for x in m.split(" y ") if x]


def page(title, desc, canonical, body, noindex=False, trail=None):
    return (f'<!doctype html>\n<html lang="es-MX"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">\n'
            f'<title>{title}</title><meta name="description" content="{desc}">\n'
            + ('<meta name="robots" content="noindex,follow">' if noindex else "")
            + f'<link rel="canonical" href="{canonical}"><meta name="theme-color" content="#ffffff"><link rel="icon" href="/favicon.ico" sizes="any"><script src="/theme.js"></script>\n'
            + (crumbs(trail) + "\n" if trail else "")
            + '<style>:root{--bg:#fbfaf6;--fg:#14213d;--muted:#4f5b7a;--brand:#1d3f9e}body{margin:0;background:var(--bg);color:var(--fg);font:18px/1.6 system-ui,-apple-system,sans-serif}'
            'main{max-width:800px;margin:auto;padding:16px}a{color:var(--brand)}small{color:var(--muted)}'
            '.acciones a,.enlaces a{display:inline-block;padding:10px 0}footer{border-top:3px double var(--brand);margin-top:32px;font-size:16px}'
            '@media(prefers-color-scheme:dark){:root{--bg:#0c1328;--fg:#eef1fb;--muted:#a6b1d6;--brand:#a9bdfa}}</style></head>\n'
            f'<body><main>{body}{FOOTER}</main></body></html>\n')


def build():
    rows = json.loads(COLONIAS.read_bytes())
    rot = json.loads(ROTATION.read_bytes())
    area = shares()
    names = slugs(rows)
    key = lambda n, m: (mapa_colonias.fold(n), mapa_colonias.fold(m).removeprefix("SAN PEDRO "))
    listed = {key(c["name"], c["municipio"]): c["zones"] for c in json.loads(LIST.read_bytes())}
    files, index, by_mun = {}, [], defaultdict(list)
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
            items += (f"<p>Ojo: la lista de colonias del SIAPA le da {'la zona' if len(lz) == 1 else 'las zonas'} {y(lz)} a «{e(n)}» de {e(m)}; "
                      "su mapa y su lista no coinciden. Confírmalo en el mapa o con el SIAPA.</p>")
        where = f"{e(n)}, {e(m)}" + (f", C.P. {e(cp)}" if cp else "")
        ms = municipios(m)
        mlinks = " · ".join(f'<a href="/colonia/municipio-{slug(x)}">{e(x)}</a>' for x in ms)
        body = (f'<p><a href="/">Agua GDL</a> · <a href="/colonia/">Colonias</a>' + (f" · {mlinks}" if ms else "") + f'</p><h1>¿Cuándo cortan el agua en {e(n)}?</h1>'
                f'<p>{where}</p>{items}'
                f'<p><small>{e(NOTE)} Calendario del SIAPA verificado el {fecha(checked)}; la rotación sigue hasta {fecha(end).split(" de ", 1)[1]}. '
                f'Fuente: <a href="https://rotaciondeserviciosiapa.jalisco.gob.mx/" rel="noopener">SIAPA</a>.</small></p>'
                f'<p class="acciones"><a href="/avisos?{e(q)}">Ver en el mapa y próximas fechas</a> · <a href="/reportes?{e(q)}">¿Hay agua? Reporta</a> · '
                f'<a href="/pipas">¿Sin agua? Pide una pipa</a> · <a href="/colonia/{s}.json">Datos (JSON)</a></p>')
        if zones:
            zt = "; ".join(f"zona {z['zone']}" + (" (al límite)" if len(zones) > 1 and z["share"] < BORDER else "")
                           + f", corte {y(z['days'])}" for z in zones)
        elif differs:
            zt = f"sin zona en su mapa; su lista le da {'la zona' if len(lz) == 1 else 'las zonas'} {y(lz)}"
        else:
            zt = "sin zona en su mapa"
        dup = s != f"{slug(n)}-{slug(m)}"  # name and municipio repeat: the postal code tells them apart
        title = f"Cortes de agua en {e(n)}, {e(m)}" + (f", C.P. {e(cp)}" if dup and cp else "") + " · Agua GDL"
        trail = [("Agua GDL", f"{ORIGIN}/"), ("Colonias", f"{ORIGIN}/colonia/")]
        if ms:
            trail.append((ms[0], f"{ORIGIN}/colonia/municipio-{slug(ms[0])}"))
        trail.append((n, f"{ORIGIN}/colonia/{s}"))
        files[f"{s}.html"] = page(title, f"Días de corte de agua (tandeo) de la rotación del SIAPA en {where}: {zt}.",
                                  f"{ORIGIN}/colonia/{s}", body, noindex=not zones and not differs, trail=trail)
        index.append((mapa_colonias.fold(n), m, cp, s, n))
        for x in ms:
            by_mun[x].append((mapa_colonias.fold(n), n, cp, s, [z["zone"] for z in zones]))
    index.sort()
    e = html.escape
    li = "".join(f'<li><a href="/colonia/{s}">{e(n)}</a> <small>{e(m)}{" " + cp if cp else ""}</small></li>'
                 for _, m, cp, s, n in index)
    mun_nav = " · ".join(f'<a href="/colonia/municipio-{slug(x)}">{e(x)}</a>' for x in sorted(by_mun))
    files["index.html"] = page("Colonias A–Z · Agua GDL", "Días de corte de agua (tandeo) por colonia según la rotación del SIAPA.",
                               f"{ORIGIN}/colonia/", f'<p><a href="/">Agua GDL</a></p><h1>Colonias A–Z</h1><p><small>{NOTE}</small></p>'
                               f'<p class="enlaces">Por municipio: {mun_nav}</p><ul>{li}</ul>',
                               trail=[("Agua GDL", f"{ORIGIN}/"), ("Colonias", f"{ORIGIN}/colonia/")])
    for x, cols in by_mun.items():
        ms_slug = f"municipio-{slug(x)}"
        if f"{ms_slug}.html" in files:
            sys.exit(f"colonia_pages: {ms_slug} collides with a colonia's slug")
        cols.sort()
        con = [c for c in cols if c[4]]
        sin = [c for c in cols if not c[4]]
        sections = []
        for z in sorted(rot["zones"], key=int):
            here = [c for c in con if int(z) in c[4]]
            if not here:
                continue
            days = ", ".join(DAYS[d] for d in rot["zones"][z])
            sections.append(f'<h2 id="zona-{z}">Zona {z}: días de corte {days}</h2><p class="enlaces"><a href="/calendario/zona-{z}.ics">Calendario</a> · '
                            f'<a href="https://t.me/AvisoAguaGDLbot?start=z{z}" rel="noopener">Avisos por Telegram</a></p><ul>'
                            + "".join(f'<li><a href="/colonia/{s}">{e(n)}</a>' + (f" <small>{cp}</small>" if cp else "") + "</li>" for _, n, cp, s, _ in here)
                            + "</ul>")
        if sin:
            sections.append('<h2 id="sin-zona">Sin zona en el mapa del SIAPA</h2><p>El mapa de la rotación no les da zona a estas colonias. '
                            'Eso no confirma que tengan agua.</p><ul>'
                            + "".join(f'<li><a href="/colonia/{s}">{e(n)}</a>' + (f" <small>{cp}</small>" if cp else "") + "</li>" for _, n, cp, s, _ in sin)
                            + "</ul>")
        summary = (f"De las {len(cols)} colonias de {e(x)} en el mapa de la rotación del SIAPA, "
                   + (f"{len(con)} tienen zona" if con else "ninguna tiene zona")
                   + (f" y {len(sin)} no." if con and sin else "."))
        desc = (f"Días de corte de agua (tandeo) por colonia en {e(x)} según la rotación del SIAPA: " + summary[0].lower() + summary[1:])
        files[f"{ms_slug}.html"] = page(f"Cortes de agua por colonia en {e(x)} · Agua GDL", desc, f"{ORIGIN}/colonia/{ms_slug}",
                                        f'<p><a href="/">Agua GDL</a> · <a href="/colonia/">Colonias</a></p><h1>Cortes de agua por colonia en {e(x)}</h1>'
                                        f'<p>{summary}</p>{"".join(sections)}'
                                        f'<p><small>{e(NOTE)} Calendario del SIAPA verificado el {fecha(checked)}. Fuente: '
                                        '<a href="https://rotaciondeserviciosiapa.jalisco.gob.mx/" rel="noopener">SIAPA</a>.</small></p>',
                                        trail=[("Agua GDL", f"{ORIGIN}/"), ("Colonias", f"{ORIGIN}/colonia/"), (x, f"{ORIGIN}/colonia/{ms_slug}")])
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
        n = sum(f.endswith(".json") for f in files)
        print(f"colonia/: up to date ({n} colonias, {sum(f.startswith('municipio-') for f in files)} municipios)")
        return
    OUT.mkdir(exist_ok=True)
    for f in have - set(files):
        (OUT / f).unlink()
    for f, t in files.items():
        (OUT / f).write_text(t, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {len(files)} files, {sum(len(t.encode()) for t in files.values())} bytes")


if __name__ == "__main__":
    main()
