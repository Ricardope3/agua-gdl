#!/usr/bin/env python3
"""Instagram carousels for Agua GDL: one JSON per carousel in carruseles/, rendered to 1080x1350 PNGs.

    python3 experiments/carrusel/build.py               check every carousel, render all, write FUENTES.md and contact sheets
    python3 experiments/carrusel/build.py 01-maximo     only carousels whose id starts with this
    python3 experiments/carrusel/build.py --check       validate only (no Chrome)
    python3 experiments/carrusel/build.py --capturas    retake the aguagdl.com phone screenshots in capturas/

Checks before rendering: every number written on a slide appears in the "cita" of a source the slide cites
(or in the slide's "calculo", which says how it was computed); every source has url, medio, fecha, cita and
"revisado"; every background is in fotos.json (reviewed: no close face, no name, no watermark) and in
pipelines/fotos_temas.json's "temas". A pass checks shape, not truth: the citas were copied from the sources
on the "revisado" date. Output goes to experiments/carrusel/out/ (gitignored). Drafts only: Ricardo posts.
"""
import html
import json
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "out"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
W, H = 1080, 1350
CHROME_BAR = 87  # headless Chrome's viewport is the window minus this; screenshots are cropped back
TYPES = {"foto", "dividido", "perfil", "altura", "desnivel", "sitio", "portada", "texto", "cita", "barras", "iconos", "calendario", "versus", "lista", "linea", "pregunta", "cierre"}
DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
DIAS_CORTO = ["L", "M", "M", "J", "V", "S", "D"]


def fail(msg):
    sys.exit(f"carrusel: {msg}")


def foto_path(rel):
    """The private 800 px original when the main checkout has it, else the public 480 px copy."""
    name = pathlib.Path(rel).name
    for base in (ROOT / "research/fotos", pathlib.Path.home() / "agua-gdl/research/fotos"):
        p = base / name
        if p.is_file():
            return p
    p = ROOT / "web" / rel
    if not p.is_file():
        fail(f"no photo {rel}")
    return p


def slide_texts(s):
    out = []
    for k, v in s.items():
        if k in ("tipo", "foto", "fuentes", "calculo", "nota", "posicion", "propio", "captura", "bins", "alturas", "color", "x", "y"):
            continue
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, str):
                    out.append(x)
                elif isinstance(x, dict):
                    out += [str(y) for kk, y in x.items() if kk not in ("color", "icono", "foto", "x", "y")]
        elif isinstance(v, dict):
            out += [str(y) for kk, y in v.items() if kk not in ("color", "icono", "foto", "x", "y")]
        elif isinstance(v, (int, float)) and k not in ("total", "n", "columnas", "respuesta"):
            out.append(str(v))
    return out


def numbers(text):
    return [n.replace(",", "") for n in re.findall(r"\d[\d,]*(?:\.\d+)?", text)]


def check(c, fotos_ok, temas):
    cid = c.get("id", "?")
    for k in ("id", "titulo", "caption", "fuentes", "slides"):
        if k not in c:
            fail(f"{cid}: missing {k}")
    for key, f in c["fuentes"].items():
        for k in ("url", "medio", "fecha", "cita", "revisado"):
            if not f.get(k):
                fail(f"{cid}: fuente {key} missing {k}")
        if not f["url"].startswith("https://"):
            fail(f"{cid}: fuente {key} url must be https")
    if not 3 <= len(c["slides"]) <= 10:
        fail(f"{cid}: 3 to 10 slides")
    if "¿" not in c["caption"]:
        fail(f"{cid}: the caption asks the reader something («¿…?») people can answer in the comments")
    if c["slides"][-1]["tipo"] != "cierre":
        fail(f"{cid}: the last slide is a cierre")
    for i, s in enumerate(c["slides"], 1):
        where = f"{cid} slide {i}"
        if s.get("tipo") not in TYPES:
            fail(f"{where}: tipo {s.get('tipo')!r}")
        if s.get("foto") and s["foto"] not in fotos_ok:
            fail(f"{where}: {s['foto']} is not in fotos.json (review it for faces, names and watermarks first)")
        if s.get("foto") and s["foto"] not in temas:
            fail(f"{where}: {s['foto']} is not in pipelines/fotos_temas.json temas")
        for key in s.get("fuentes", []):
            if key not in c["fuentes"]:
                fail(f"{where}: unknown fuente {key}")
        pool = " ".join(c["fuentes"][k]["cita"] for k in s.get("fuentes", [])) + " " + s.get("calculo", "")
        for k in s.get("fuentes", []):
            y, m, d = c["fuentes"][k]["fecha"].split("-")
            pool += f" {int(d)} {y} "  # the source's own date may be written on the slide
        pool = pool.replace(",", "")
        texts = slide_texts(s)
        nums = [n for t in texts for n in numbers(t)]
        if nums and not s.get("fuentes") and not s.get("calculo"):
            fail(f"{where}: numbers {nums} without fuentes")
        for n in nums:
            if not re.search(r"(?<![\d.])" + re.escape(n) + r"(?![\d])", pool):
                fail(f"{where}: {n} is not in the cited citas or the calculo")
        if s["tipo"] != "cierre" and not s.get("fuentes") and not s.get("propio"):
            fail(f"{where}: no fuentes; a slide without a source says why in \"propio\" (our question, proposal, method or service)")
        if s["tipo"] == "cita" and not s.get("fuentes"):
            fail(f"{where}: a quote needs its fuente")
        if s["tipo"] == "cita":
            q = s["cita"].strip("«»\"“” ")
            q = q.replace("…", "")
            if not all(part.strip() in " ".join(c["fuentes"][k]["cita"] for k in s["fuentes"]) for part in q.split("[...]")):
                fail(f"{where}: the quote is not word for word in its fuente's cita")


def md(text):
    t = html.escape(text)
    t = re.sub(r"\*\*(.+?)\*\*", r'<span class="alarm">\1</span>', t)
    t = re.sub(r"\*(.+?)\*", r'<span class="acc">\1</span>', t)
    return t.replace("\n", "<br>")


ICONS = {
    "gota": '<path d="M50 6C50 6 18 46 18 66a32 32 0 0 0 64 0C82 46 50 6 50 6z"/>',
    "persona": '<circle cx="50" cy="26" r="16"/><path d="M20 94c0-22 13-38 30-38s30 16 30 38z"/>',
    "casa": '<path d="M50 10 8 46h12v44h24V66h12v24h24V46h12z"/>',
    "pipa": '<path d="M6 36h52a14 14 0 0 1 14 14v24H6z"/><path d="M74 46h10l10 14v14H74z"/><circle cx="24" cy="80" r="9"/><circle cx="78" cy="80" r="9"/>',
    "cubeta": '<path d="M16 26h68l-8 66H24z"/><path d="M12 18h76v10H12z"/>',
    "peso": '<circle cx="50" cy="50" r="42"/>',
}


def icon(name, cls=""):
    return f'<svg class="ic {cls}" viewBox="0 0 100 100">{ICONS[name]}</svg>'


LOGO = None


def logo():
    global LOGO
    if LOGO is None:
        LOGO = (ROOT / "web/logo.svg").read_text().replace("<svg ", '<svg class="logo" ', 1)
    return LOGO


def render_body(s):
    t = s["tipo"]
    if t in ("portada", "texto"):
        parts = []
        if s.get("kicker"):
            parts.append(f'<div class="kicker">{md(s["kicker"])}</div>')
        if s.get("cifra"):
            parts.append(f'<div class="cifra">{md(s["cifra"])}</div>')
        if s.get("titular"):
            parts.append(f'<div class="titular">{md(s["titular"])}</div>')
        if s.get("texto"):
            parts.append(f'<div class="texto">{md(s["texto"])}</div>')
        if s.get("pie"):
            parts.append(f'<div class="pie">{md(s["pie"])}</div>')
        return f'<div class="stack {s.get("posicion", "")}">{"".join(parts)}</div>'
    if t == "cita":
        return (f'<div class="stack"><div class="kicker">{md(s.get("kicker", ""))}</div><div class="comillas">“</div>'
                f'<blockquote>{md(s["cita"])}</blockquote><div class="quien">{md(s["quien"])}</div>'
                + (f'<div class="texto small">{md(s["texto"])}</div>' if s.get("texto") else "") + "</div>")
    if t == "barras":
        mx = max(b["valor"] for b in s["barras"])
        rows = "".join(
            f'<div class="barra"><div class="bl"><span>{md(b["etiqueta"])}</span><b class="{b.get("color", "")}">{md(b["texto"])}</b></div>'
            f'<div class="track"><div class="fill {b.get("color", "")}" style="width:{max(2, 100 * b["valor"] / mx):.1f}%"></div></div></div>'
            for b in s["barras"])
        return (f'<div class="stack"><div class="kicker">{md(s.get("kicker", ""))}</div><div class="titular">{md(s["titular"])}</div>'
                f'<div class="barras{" compact" if len(s["barras"]) > 4 else ""}{" tiny" if len(s["barras"]) > 6 else ""}">{rows}</div>' + (f'<div class="texto small">{md(s["texto"])}</div>' if s.get("texto") else "") + "</div>")
    if t == "iconos":
        n, total = s["n"], s["total"]
        cols = s.get("columnas", 10 if total > 12 else total)
        cells = "".join(icon(s["icono"], "on" if i < n else "off") for i in range(total))
        return (f'<div class="stack"><div class="kicker">{md(s.get("kicker", ""))}</div>'
                f'<div class="cifra{" long" if len(s["cifra"]) > 6 else ""}">{md(s["cifra"])}</div><div class="titular">{md(s["titular"])}</div>'
                f'<div class="iconos{" many" if total > 30 else ""}" style="grid-template-columns:repeat({cols},1fr)">{cells}</div>'
                + (f'<div class="texto small">{md(s["texto"])}</div>' if s.get("texto") else "") + "</div>")
    if t == "calendario":
        head = '<div></div>' + "".join(f'<div class="dh">{d}</div>' for d in DIAS_CORTO)
        rows = ""
        for z in s["zonas"]:
            rows += f'<div class="zl">{md(z["zona"])}</div>' + "".join(
                f'<div class="dc {"cut" if d in z["dias"] else ""}"></div>' for d in DIAS)
        return (f'<div class="stack"><div class="kicker">{md(s.get("kicker", ""))}</div><div class="titular">{md(s["titular"])}</div>'
                f'<div class="cal">{head}{rows}</div><div class="leyenda"><i class="dc cut"></i> {md(s.get("leyenda", "día de racionamiento"))}</div>'
                + (f'<div class="texto small">{md(s["texto"])}</div>' if s.get("texto") else "") + "</div>")
    if t == "versus":
        a, b = s["izq"], s["der"]
        col = lambda x, cls: (f'<div class="vs {cls}"><div class="vk">{md(x["kicker"])}</div><div class="vc">{md(x["cifra"])}</div>'
                              f'<div class="vt">{md(x["texto"])}</div></div>')
        return (f'<div class="stack"><div class="kicker">{md(s.get("kicker", ""))}</div><div class="titular">{md(s["titular"])}</div>'
                f'<div class="versus">{col(a, "a")}<div class="vsx">vs</div>{col(b, "b")}</div>'
                + (f'<div class="texto small">{md(s["texto"])}</div>' if s.get("texto") else "") + "</div>")
    if t == "lista":
        mark = s.get("marca", "num")
        items = "".join(
            f'<li><span class="m {mark}">{i if mark == "num" else ""}</span><div>{md(it)}</div></li>'
            for i, it in enumerate(s["items"], 1))
        return (f'<div class="stack"><div class="kicker">{md(s.get("kicker", ""))}</div><div class="titular">{md(s["titular"])}</div>'
                f'<ul class="lista">{items}</ul>' + (f'<div class="texto small">{md(s["texto"])}</div>' if s.get("texto") else "") + "</div>")
    if t == "linea":
        items = "".join(
            f'<div class="hito {h.get("color", "")}"><div class="hf">{md(h["fecha"])}</div><div class="ht">{md(h["texto"])}</div></div>'
            for h in s["hitos"])
        return (f'<div class="stack"><div class="kicker">{md(s.get("kicker", ""))}</div><div class="titular">{md(s["titular"])}</div>'
                f'<div class="linea">{items}</div>' + (f'<div class="texto small">{md(s["texto"])}</div>' if s.get("texto") else "") + "</div>")
    if t == "pregunta":
        ops = "".join(
            f'<div class="op {"ok" if s.get("respuesta") == i else ""}"><b>{"ABCD"[i]}</b>{md(o)}</div>'
            for i, o in enumerate(s["opciones"]))
        return (f'<div class="stack"><div class="kicker">{md(s.get("kicker", ""))}</div><div class="titular">{md(s["titular"])}</div>'
                f'<div class="ops">{ops}</div>' + (f'<div class="texto small">{md(s["texto"])}</div>' if s.get("texto") else "") + "</div>")
    if t == "foto":
        return (f'<div class="stack abajo">' + (f'<div class="kicker">{md(s["kicker"])}</div>' if s.get("kicker") else "")
                + f'<div class="titular">{md(s["titular"])}</div>' + (f'<div class="texto">{md(s["texto"])}</div>' if s.get("texto") else "") + "</div>")
    if t == "dividido":
        return (f'<div class="stack abajo"><div class="titular">{md(s["titular"])}</div>'
                + (f'<div class="texto">{md(s["texto"])}</div>' if s.get("texto") else "") + "</div>")
    if t == "perfil":
        alt = sorted(s["alturas"])
        lo, hi = s["eje"]["desde"], s["eje"]["hasta"]
        L, w, h, top = 96, 832, 400, 60
        y = lambda m: top + h - h * (m - lo) / (hi - lo)
        bw = w / len(alt)
        i = alt.index(s["marca"]["m"])
        bars = "".join(f'<rect x="{L + k * bw:.2f}" y="{y(m):.1f}" width="{bw + .3:.2f}" height="{top + h - y(m):.1f}" fill="#3ea6ff"/>' for k, m in enumerate(alt))
        mx, my, med = L + (i + .5) * bw, y(s["marca"]["m"]), y(s["mediana"]["m"])
        ticks = "".join(f'<line x1="{L}" x2="{L + w}" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="rgba(255,255,255,.12)"/>'
                        f'<text x="{L - 12}" y="{y(v) + 8:.1f}" text-anchor="end">{v:,}</text>' for v in s["eje"]["marcas"])
        svg = (f'<svg class="alt" viewBox="0 0 {L + w} {top + h + 56}">{ticks}{bars}'
               f'<line x1="{L}" x2="{L + w}" y1="{med:.1f}" y2="{med:.1f}" stroke="#fff" stroke-width="3" stroke-dasharray="10 8"/>'
               f'<text x="{L + 14}" y="{med - 12:.1f}" class="lab">{html.escape(s["mediana"]["etiqueta"])}</text>'
               f'<rect x="{mx - 5:.1f}" y="{my:.1f}" width="10" height="{top + h - my:.1f}" fill="#ff7a66"/>'
               f'<circle cx="{mx:.1f}" cy="{my:.1f}" r="13" fill="#ff7a66" stroke="#06141d" stroke-width="4"/>'
               f'<text x="{mx - 24:.1f}" y="{my - 22:.1f}" text-anchor="end" class="pin">{html.escape(s["marca"]["etiqueta"])}</text>'
               f'<text x="{L}" y="{top + h + 42}">{html.escape(s["eje"]["izq"])}</text>'
               f'<text x="{L + w}" y="{top + h + 42}" text-anchor="end">{html.escape(s["eje"]["der"])}</text>'
               f'<text x="0" y="{top - 30}">{html.escape(s["eje"]["titulo"])}</text></svg>')
        return (f'<div class="stack"><div class="kicker">{md(s.get("kicker", ""))}</div><div class="titular">{md(s["titular"])}</div>{svg}'
                + (f'<div class="texto small">{md(s["texto"])}</div>' if s.get("texto") else "") + "</div>")
    if t == "altura":
        bins = s["bins"]
        w, h, top = 928, 430, 60
        bw = w / len(bins)
        mx = max(b["n"] for b in bins)
        lo, step = bins[0]["desde"], bins[1]["desde"] - bins[0]["desde"]
        x = lambda m: (m - lo) / step * bw
        bars = "".join(
            f'<rect x="{i * bw + 2:.1f}" y="{top + h - h * b["n"] / mx:.1f}" width="{bw - 4:.1f}" height="{h * b["n"] / mx:.1f}" rx="4" '
            f'fill="{"#ff7a66" if b["desde"] <= s["marca"]["m"] < b["desde"] + step else "#3ea6ff"}" opacity="{1 if b["desde"] <= s["marca"]["m"] < b["desde"] + step else 0.85}"/>'
            for i, b in enumerate(bins))
        mm, mk = x(s["mediana"]["m"]), x(s["marca"]["m"])
        eje = "".join(f'<text x="{x(int(v.replace(",", ""))):.1f}" y="{top + h + 44}" text-anchor="middle">{html.escape(v)} m</text>' for v in s["eje"])
        svg = (f'<svg class="alt" viewBox="0 -10 {w} {top + h + 60}">{bars}'
               f'<line x1="{mm:.1f}" x2="{mm:.1f}" y1="{top - 10}" y2="{top + h}" stroke="#fff" stroke-width="3" stroke-dasharray="10 8"/>'
                              f'<line x1="{mk:.1f}" x2="{mk:.1f}" y1="{top - 50}" y2="{top + h}" stroke="#ff7a66" stroke-width="5"/>'
               f'<circle cx="{mk:.1f}" cy="{top - 50}" r="12" fill="#ff7a66"/>'
               f'<text x="{mk - 22:.1f}" y="{top - 40}" text-anchor="end" class="pin">{html.escape(s["marca"]["etiqueta"])}</text>'
               f'<text x="{mm + 14:.1f}" y="{top + 150}" text-anchor="start" class="lab"><tspan class="bgl">{html.escape(s["mediana"]["etiqueta"])}</tspan></text>'
               f'<line x1="0" x2="{w}" y1="{top + h}" y2="{top + h}" stroke="rgba(255,255,255,.4)" stroke-width="2"/>{eje}</svg>')
        return (f'<div class="stack"><div class="kicker">{md(s.get("kicker", ""))}</div><div class="titular">{md(s["titular"])}</div>{svg}'
                + (f'<div class="texto small">{md(s["texto"])}</div>' if s.get("texto") else "") + "</div>")
    if t == "desnivel":
        mx = max(abs(f["valor"]) for f in s["filas"])
        rows = "".join(
            f'<div class="dn"><div class="dl">{md(f["etiqueta"])}</div><div class="dt">'
            + (f'<div class="db pos {f.get("color", "")}" style="width:{50 * f["valor"] / mx:.1f}%"></div>' if f["valor"] > 0
               else f'<div class="db neg" style="width:{50 * -f["valor"] / mx:.1f}%"></div>')
            + f'</div><div class="dv {"pos" if f["valor"] > 0 else "neg"} {f.get("color", "")}">{md(f["texto"])}</div></div>'
            for f in s["filas"])
        return (f'<div class="stack"><div class="kicker">{md(s.get("kicker", ""))}</div><div class="titular">{md(s["titular"])}</div>'
                f'<div class="eje0"><span>{md(s["izq"])}</span><span>{md(s["centro"])}</span><span>{md(s["der"])}</span></div>'
                f'<div class="desnivel">{rows}</div>' + (f'<div class="texto small">{md(s["texto"])}</div>' if s.get("texto") else "") + "</div>")
    if t == "sitio":
        items = "".join(f'<li>{md(it)}</li>' for it in s.get("items", []))
        shot = (HERE / "capturas" / f'{s["captura"]}.jpg').as_uri()
        return (f'<div class="sitio"><div class="scol"><div class="kicker">{md(s.get("kicker", ""))}</div>'
                + (f'<div class="cifra">{md(s["cifra"])}</div>' if s.get("cifra") else "")
                + f'<div class="titular">{md(s["titular"])}</div><ul class="acts">{items}</ul>'
                f'<div class="bio">Link en la bio<b>{md(s["url"])}</b></div></div>'
                f'<div class="phone"><div class="screen" style="background-image:url(\'{shot}\')"></div></div></div>')
    if t == "cierre":
        acts = "".join(f'<li>{md(a)}</li>' for a in s.get("acciones", []))
        return (f'<div class="stack cierre">{logo()}<div class="titular">{md(s["titular"])}</div>'
                f'<ul class="acts">{acts}</ul><div class="url">{md(s.get("url", "aguagdl.com"))}</div>'
                f'<div class="pie">Agua GDL es un proyecto ciudadano, sin partido ni afiliación oficial. Cada dato lleva su fuente; si ves un error, escríbenos a soporte@aguagdl.com.</div></div>')
    fail(f"tipo {t}")


CSS = """
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1350px;overflow:hidden;background:#06141d}
body{font-family:"Avenir Next",Avenir,"Helvetica Neue",sans-serif;color:#fff;position:relative}
.bg{position:absolute;inset:0;background-size:cover;background-position:center;filter:saturate(.9) brightness(.78) contrast(1.05)}
.tint{position:absolute;inset:0;background:linear-gradient(180deg,rgba(2,14,28,.7) 0%,rgba(2,14,28,.15) 22%,rgba(2,14,28,.2) 45%,rgba(2,14,28,.82) 72%,rgba(1,10,22,.95) 100%)}
.heavy .tint{background:linear-gradient(180deg,rgba(2,14,28,.78) 0%,rgba(2,14,28,.72) 100%)}
.plain .bg{display:none}.plain .tint{background:radial-gradient(120% 90% at 20% 0%,#0b3a66 0%,#06141d 60%)}
.frame{position:absolute;inset:0;padding:72px 76px 64px;display:flex;flex-direction:column}
.top{display:flex;align-items:center;gap:16px;font-weight:700;font-size:30px;letter-spacing:.01em}
.top .logo{width:40px;height:58px}
.top .n{margin-left:auto;font-size:26px;font-weight:600;opacity:.7}
.main{flex:1;display:flex;align-items:center}
.conf .main{align-items:flex-end;padding-bottom:10px}
.stack{width:100%;display:flex;flex-direction:column;gap:26px}
.stack.abajo{align-self:flex-end;padding-bottom:20px}
.kicker{font-family:"Avenir Next Condensed";font-weight:700;font-size:32px;color:#7cc4ff;text-transform:none;letter-spacing:.01em}
.kicker:empty{display:none}
.cifra{font-family:"Avenir Next Condensed";font-weight:800;font-size:200px;line-height:.9;color:#3ea6ff;letter-spacing:-.02em}
.titular{font-family:"Avenir Next Condensed";font-weight:800;font-size:86px;line-height:1;letter-spacing:-.005em;text-wrap:balance;text-shadow:0 2px 18px rgba(0,0,0,.55)}
.texto{font-size:34px;line-height:1.3;font-weight:500;opacity:.9;text-wrap:pretty;text-shadow:0 2px 12px rgba(0,0,0,.5)}
.texto.small{font-size:31px;font-weight:500;opacity:.92}
.pie{font-size:24px;opacity:.75;line-height:1.35}
.acc{color:#3ea6ff}.alarm{color:#ff7a66}
.comillas{font-family:Georgia,serif;font-size:260px;line-height:1;height:110px;color:#3ea6ff;margin-bottom:-10px}
blockquote{font-family:"Avenir Next Condensed";font-weight:800;font-size:82px;line-height:1.08;text-wrap:balance}
.quien{font-size:30px;font-weight:600;opacity:.85}
.barras{display:flex;flex-direction:column;gap:34px;margin-top:10px}
.bl{display:flex;justify-content:space-between;align-items:baseline;gap:20px;font-size:32px;font-weight:600;margin-bottom:12px}
.bl b{font-family:"Avenir Next Condensed";font-weight:800;font-size:54px;white-space:nowrap;color:#3ea6ff}
.barras.compact{gap:14px}.barras.compact .bl{font-size:28px;margin-bottom:6px}.barras.compact .bl b{font-size:42px}.barras.compact .track{height:30px}
.barras.tiny{gap:8px}.barras.tiny .bl{font-size:26px;margin-bottom:4px}.barras.tiny .bl b{font-size:36px}.barras.tiny .track{height:22px}
.track{height:44px;background:rgba(255,255,255,.12);border-radius:8px;overflow:hidden}
.fill{height:100%;background:#3ea6ff;border-radius:8px}
.fill.alarm{background:#ff7a66}.bl b.alarm{color:#ff7a66}
.fill.gris{background:#c9d4de}.bl b.gris{color:#c9d4de}
.iconos{display:grid;gap:14px;margin-top:6px}.iconos.many{gap:6px;width:72%}
.cifra.long{font-size:140px}
.ic{width:100%;aspect-ratio:1}
.ic.on{fill:#3ea6ff}.ic.off{fill:rgba(255,255,255,.18)}
.cal{display:grid;grid-template-columns:150px repeat(7,1fr);gap:10px;margin-top:6px}
.dh{text-align:center;font-weight:700;font-size:30px;opacity:.8}
.zl{font-family:"Avenir Next Condensed";font-weight:700;font-size:34px;display:flex;align-items:center}
.dc{height:62px;border-radius:10px;background:rgba(255,255,255,.12)}
.dc.cut{background:#ff7a66}
.leyenda{display:flex;align-items:center;gap:14px;font-size:26px;opacity:.85}
.leyenda .dc{display:inline-block;width:34px;height:34px}
.versus{display:flex;align-items:stretch;gap:22px}
.vs{flex:1;border-radius:22px;padding:34px 30px;background:rgba(255,255,255,.08);border:2px solid rgba(255,255,255,.18);display:flex;flex-direction:column;gap:14px}
.vs.a{border-color:#3ea6ff}.vs.b{border-color:#ff7a66}
.vk{font-size:28px;font-weight:700;opacity:.85}
.vc{font-family:"Avenir Next Condensed";font-weight:800;font-size:120px;line-height:.95}
.vs.a .vc{color:#3ea6ff}.vs.b .vc{color:#ff7a66}
.vt{font-size:29px;line-height:1.3;font-weight:500}
.vsx{align-self:center;font-family:"Avenir Next Condensed";font-weight:800;font-size:44px;opacity:.6}
.lista{list-style:none;display:flex;flex-direction:column;gap:24px}
.lista li{display:flex;gap:24px;align-items:flex-start;font-size:34px;line-height:1.28;font-weight:600}
.m{flex:none;width:58px;height:58px;border-radius:50%;background:#3ea6ff;color:#06141d;font-weight:800;font-size:32px;display:flex;align-items:center;justify-content:center}
.m.check{background:transparent;border:4px solid #3ea6ff;border-radius:10px;width:50px;height:50px;margin-top:4px}
.linea{display:flex;flex-direction:column;gap:0;border-left:5px solid rgba(255,255,255,.3);margin-left:14px}
.hito{position:relative;padding:0 0 30px 44px}
.hito:before{content:"";position:absolute;left:-17px;top:6px;width:28px;height:28px;border-radius:50%;background:#3ea6ff}
.hito.alarm:before{background:#ff7a66}.hito.gris:before{background:#c9d4de}
.hf{font-family:"Avenir Next Condensed";font-weight:800;font-size:44px;color:#7cc4ff}
.hito.alarm .hf{color:#ff7a66}
.ht{font-size:30px;line-height:1.3;font-weight:500}
.ops{display:flex;flex-direction:column;gap:20px}
.op{display:flex;gap:24px;align-items:center;font-size:40px;font-weight:700;padding:26px 30px;border-radius:18px;background:rgba(255,255,255,.1);border:3px solid rgba(255,255,255,.2)}
.op b{font-family:"Avenir Next Condensed";font-size:46px;color:#7cc4ff}
.op.ok{border-color:#3ea6ff;background:rgba(62,166,255,.22)}
.cierre{align-items:flex-start}
.cierre .logo{width:110px;height:160px}
.acts{list-style:none;display:flex;flex-direction:column;gap:16px;font-size:36px;font-weight:600}
.acts li:before{content:"→ ";color:#3ea6ff}
.url{font-family:"Avenir Next Condensed";font-weight:800;font-size:84px;color:#3ea6ff}
.sitio{position:relative;width:100%;height:100%;display:flex;align-items:center}
.scol{width:560px;display:flex;flex-direction:column;gap:22px;position:relative;z-index:2}
.sitio .cifra{font-size:150px}.sitio .titular{font-size:60px}.sitio .acts{font-size:30px}
.bio{display:inline-flex;flex-direction:column;align-self:flex-start;gap:4px;margin-top:8px;padding:18px 26px;border-radius:18px;background:#3ea6ff;color:#04121c;font-weight:700;font-size:24px;text-transform:uppercase;letter-spacing:.06em}
.bio b{font-family:"Avenir Next Condensed";font-size:44px;text-transform:none;letter-spacing:0}
.phone{position:absolute;right:-30px;top:50%;transform:translateY(-50%) rotate(4deg);width:400px;height:860px;border-radius:56px;background:#0b0f14;padding:14px;box-shadow:0 30px 80px rgba(0,0,0,.6),0 0 0 2px rgba(255,255,255,.12)}
.screen{width:100%;height:100%;border-radius:44px;background-size:100% auto;background-position:top center;background-repeat:no-repeat;background-color:#fbfaf6}
.alt{width:100%;margin-top:4px;overflow:visible}
.alt text{fill:#fff;font-family:"Avenir Next";font-size:24px;font-weight:600;opacity:.85}
.alt text.lab{font-size:26px;opacity:1;paint-order:stroke;stroke:#06141d;stroke-width:8px}.alt text.pin{font-family:"Avenir Next Condensed";font-weight:800;font-size:40px;fill:#ff7a66;opacity:1}
.eje0{display:flex;justify-content:space-between;font-size:24px;font-weight:600;opacity:.8;margin-bottom:-8px}
.desnivel{display:flex;flex-direction:column;gap:16px;position:relative}
.dn{display:grid;grid-template-columns:250px 1fr 150px;align-items:center;gap:18px}
.dl{font-family:"Avenir Next Condensed";font-weight:700;font-size:32px;line-height:1.05}
.dt{position:relative;height:46px;background:rgba(255,255,255,.08);border-radius:8px}
.dt:after{content:"";position:absolute;left:50%;top:-12px;bottom:-12px;width:3px;background:#fff;opacity:.7}
.db{position:absolute;top:0;height:100%;border-radius:8px}
.db.pos{left:50%;background:#3ea6ff}.db.pos.alarm{background:#ff7a66}.db.neg{right:50%;background:#c9d4de}
.dv{font-family:"Avenir Next Condensed";font-weight:800;font-size:40px;text-align:right;white-space:nowrap}.dv.pos{color:#3ea6ff}.dv.pos.alarm{color:#ff7a66}.dv.neg{color:#c9d4de}
.tag{position:absolute;transform:translate(-50%,-50%);background:#0b0f14;color:#fff;font-family:"Avenir Next Condensed";font-weight:800;font-size:58px;padding:8px 20px;border-radius:10px;white-space:nowrap;box-shadow:0 6px 24px rgba(0,0,0,.45)}
.tag.alarm{background:#ff7a66;color:#0b0f14}.tag.acc{background:#3ea6ff;color:#04121c}
.tags{position:absolute;inset:0;z-index:1;pointer-events:none}
.tag.lab{background:transparent;box-shadow:none;font-size:56px;text-shadow:0 2px 16px rgba(0,0,0,.7)}
.split{position:absolute;inset:0;display:grid;grid-template-columns:1fr 1fr;gap:6px;background:#06141d}
.split .half{position:relative;background-size:cover;background-position:center;filter:saturate(.9) brightness(.8)}
.foot{display:flex;justify-content:space-between;align-items:flex-end;gap:30px;font-size:18px;line-height:1.35;opacity:.62;padding-top:14px}
.foot .src{max-width:760px}
.foot .site{font-weight:700;font-size:24px;white-space:nowrap}
"""


def footer(c, s):
    keys = s.get("fuentes", [])
    if not keys:
        return "" if s["tipo"] == "cierre" else "Agua GDL"
    seen, names = set(), []
    for k in keys:
        f = c["fuentes"][k]
        label = f'{f["medio"]}, {"consultada el " if f.get("consultada") else ""}{fecha_corta(f["fecha"])}'
        if label not in seen:
            seen.add(label)
            names.append(label)
    out = "Fuente: " + "; ".join(names) + (f'. {s["nota"]}' if s.get("nota") else "")
    return out


_VISTAS = None


def nombre(c):
    w = c.title().split()
    return " ".join(x.lower() if i and x.lower() in ("de", "del", "la", "las", "los", "el", "y") else x for i, x in enumerate(w))


def credito(s):
    """«Foto: outlet, colonia» for a background from publicaciones.json, so a photo never stands for another place."""
    global _VISTAS
    fotos = [s["foto"]] if s.get("foto") else [h["foto"] for h in (s.get("izq"), s.get("der")) if isinstance(h, dict) and h.get("foto")]
    if not fotos:
        return ""
    if _VISTAS is None:
        _VISTAS = {}
        for x in json.loads((ROOT / "web/publicaciones.json").read_text())["publicaciones"]:
            if x.get("vista") and x["vista"] not in _VISTAS:
                _VISTAS[x["vista"]] = (x["quien"] or "vecinos", nombre(x["colonias"][0].split("|")[0]) if x["colonias"] else "")
    out = []
    for f in fotos:
        q, col = _VISTAS.get(f, ("", ""))
        if q:
            out.append(f"Foto: {q}{', ' + col if col else ''}")
    return "; ".join(dict.fromkeys(out))


MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def fecha_corta(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} {MESES[int(m) - 1]} {y}"


def slide_html(c, i, s):
    total = len(c["slides"])
    bg = ""
    plain = " plain"
    if s.get("foto"):
        bg = f'<div class="bg" style="background-image:url(\'{foto_path(s["foto"]).as_uri()}\')"></div>'
        plain = " conf" if s["tipo"] in ("foto", "portada", "texto", "cita") else " heavy"
    if s["tipo"] == "dividido":
        halves = "".join(f'<div class="half" style="background-image:url(\'{foto_path(h["foto"]).as_uri()}\')"></div>' for h in (s["izq"], s["der"]))
        bg = f'<div class="split">{halves}</div>'
        s = dict(s, etiquetas=[
            *({"x": x, "y": 13, "texto": h["etiqueta"], "color": "lab"} for x, h in ((25, s["izq"]), (75, s["der"]))),
            *({"x": x, "y": 46, "texto": h["cifra"], "color": h.get("color", "")} for x, h in ((25, s["izq"]), (75, s["der"])))])
        plain = " conf"
    if s.get("etiquetas"):
        bg += '<div class="tags">' + "".join(
            f'<div class="tag {e.get("color", "")}" style="left:{e["x"]}%;top:{e["y"]}%">{md(e["texto"])}</div>' for e in s["etiquetas"]) + "</div>"
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><style>{CSS}</style></head>
<body class="{plain}">{bg}<div class="tint"></div><div class="frame">
<div class="top">{logo()}<span>Agua GDL</span><span class="n">{i}/{total}</span></div>
<div class="main">{render_body(s)}</div>
<div class="foot"><div class="src">{html.escape(" · ".join(x for x in (credito(s), footer(c, s)) if x))}</div><div class="site">aguagdl.com</div></div>
</div></body></html>"""


def crop(png, w, h):
    # sips treats offset 0 0 as "centre"; 1 1 starts one pixel in, which the extra window pixel covers
    subprocess.run(["sips", "-c", str(h), str(w), "--cropOffset", "1", "1", str(png)], check=True, capture_output=True)


def shoot(src, png):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                    "--force-device-scale-factor=1", f"--window-size={W},{H + CHROME_BAR + 1}", "--virtual-time-budget=1500",
                    f"--screenshot={png}", src.as_uri()], check=True, capture_output=True)
    crop(png, W, H)


def caption(c):
    lines = [c["caption"].rstrip(), "", "📚 Fuentes:"]
    for f in c["fuentes"].values():
        lines.append(f'- {f["medio"]}, {"consultada el " if f.get("consultada") else ""}{fecha_corta(f["fecha"])}: {f["url"]}')
    return "\n".join(lines) + "\n"


def fuentes_md(c):
    lines = [f"# {c['titulo']}", "", "Borrador para Instagram. No publicado. Ricardo publica.", "", "## Texto del post", "", c["caption"], "",
             "## Fuentes (citas copiadas de cada fuente el día de «revisado»)", ""]
    for k, f in c["fuentes"].items():
        lines += [f"- **{k}** · {f['medio']}, {f['fecha']} · revisado {f['revisado']}", f"  {f['url']}", f"  > {f['cita']}", ""]
    lines += ["## Diapositivas", ""]
    for i, s in enumerate(c["slides"], 1):
        nums = sorted({n for t in slide_texts(s) for n in numbers(t)})
        lines.append(f"{i}. {s['tipo']} · fuentes: {', '.join(s.get('fuentes', [])) or '—'}"
                     + (f" · cifras: {', '.join(nums)}" if nums else "")
                     + (f" · cálculo: {s['calculo']}" if s.get("calculo") else "")
                     + (f" · sin fuente: {s['propio']}" if s.get("propio") else "")
                     + (f" · foto: {s['foto']}" if s.get("foto") else ""))
    return "\n".join(lines) + "\n"


PAGINAS = {"reportes": "reportes", "promesas": "promesas", "pipas": "pipas", "exige": "exige", "avisos": "avisos",
           "ciudad-granja": "reportes?q=CIUDAD%20GRANJA&m=Zapopan&cp=45010"}
DESDE = {"promesas": 520, "ciudad-granja": 75}  # CSS px to skip at the top (/promesas starts at its meter, not its opening stance)


def capturas():
    """Retake the phone screenshots of aguagdl.com used by the sitio slides (500 CSS px wide, 2x)."""
    (HERE / "capturas").mkdir(exist_ok=True)
    for p, path in PAGINAS.items():
        png = HERE / "capturas" / f"{p}.png"
        top = DESDE.get(p, 0)
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=2",
                        "--virtual-time-budget=10000", f"--window-size=500,{1080 + top + CHROME_BAR}", f"--screenshot={png}",
                        f"https://aguagdl.com/{path}"], check=True, capture_output=True)
        subprocess.run(["sips", "-c", "2160", "1000", "--cropOffset", str(2 * top + 1), "1", str(png)], check=True, capture_output=True)
        jpg = png.with_suffix(".jpg")
        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "80", "-Z", "1512", str(png), "--out", str(jpg)],
                       check=True, capture_output=True)
        png.unlink()
        print(f"  capturas/{jpg.name}")


def main():
    if "--capturas" in sys.argv:
        return capturas()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    only_check = "--check" in sys.argv
    fotos_ok = set(json.loads((HERE / "fotos.json").read_text())["fotos"])
    temas = set(json.loads((ROOT / "pipelines/fotos_temas.json").read_text())["temas"])
    files = sorted((HERE / "carruseles").glob("*.json"))
    carr = [json.loads(f.read_text()) for f in files]
    ids = [c["id"] for c in carr]
    if len(ids) != len(set(ids)):
        fail("duplicate ids")
    for f, c in zip(files, carr):
        if f.stem != c["id"]:
            fail(f"{f.name}: id must match the file name")
        check(c, fotos_ok, temas)
    carr = [c for c in carr if not args or any(c["id"].startswith(a) for a in args)]
    print(f"carrusel: {len(carr)} carousels, {sum(len(c['slides']) for c in carr)} slides pass the checks")
    if only_check:
        return
    OUT.mkdir(exist_ok=True)
    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        for c in carr:
            d = OUT / c["id"]
            if d.exists():
                shutil.rmtree(d)
            d.mkdir()
            pngs = []
            for i, s in enumerate(c["slides"], 1):
                src = tmp / f"{c['id']}-{i}.html"
                src.write_text(slide_html(c, i, s))
                png = d / f"{i:02d}.png"
                shoot(src, png)
                pngs.append(png)
            (d / "FUENTES.md").write_text(fuentes_md(c))
            (d / "caption.txt").write_text(caption(c))
            cells = "".join(f'<img src="{p.as_uri()}">' for p in pngs)
            sheet = tmp / f"{c['id']}-sheet.html"
            sheet.write_text(f'<!doctype html><style>body{{margin:0;background:#111;display:flex;gap:12px;padding:12px}}img{{width:360px;height:450px}}</style>{cells}')
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                            f"--window-size={12 + 372 * len(pngs)},{474 + CHROME_BAR + 1}", f"--screenshot={d / 'hoja.png'}", sheet.as_uri()],
                           check=True, capture_output=True)
            crop(d / "hoja.png", 12 + 372 * len(pngs), 474)
            print(f"  {c['id']}: {len(pngs)} slides")
    finally:
        shutil.rmtree(tmp)


if __name__ == "__main__":
    main()
