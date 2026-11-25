#!/usr/bin/env python3
"""Builds web/nocuadra-p1..p10.html (noindex prototypes) from fragments pN.html in this folder.

Each fragment holds a <style>, a <main> and an optional <script>, and may use {{name}} placeholders for blocks lifted
verbatim from the live pages (the hub, /zapopan, /tlajomulco), so the copy stays the checked copy. A first line
`<!-- titulo: ... | mapa -->` gives the title and whether Leaflet is needed."""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WEB = HERE.parents[1] / "web"
hub = (WEB / "nocuadra.html").read_text(encoding="utf8")
zap = (WEB / "zapopan.html").read_text(encoding="utf8")
tla = (WEB / "tlajomulco.html").read_text(encoding="utf8")


def grab(s, i, tag):
    """The element of type `tag` that starts at index i, through its matching close tag."""
    assert s.startswith(f"<{tag}", i), (tag, s[i:i + 60])
    depth, j = 0, i
    pat = re.compile(rf"<{tag}[\s>]|</{tag}>")
    while True:
        m = pat.search(s, j)
        depth += -1 if m.group().startswith("</") else 1
        j = m.end()
        if depth == 0:
            return s[i:j]


def after(s, marker, tag, n=1):
    i = -1
    for _ in range(n):
        i = s.index(marker, i + 1)
    return grab(s, s.index(f"<{tag}", i), tag)


def clean_doc(fig):
    fig = re.sub(r"\n?<!-- /?documento:[\w-]+ -->", "", fig)
    return re.sub(r' data-documento="[\w-]+"', "", fig)


B = {}
zsec = hub[hub.index('<section class="caso" aria-labelledby="zapopan">'):]
tsec = hub[hub.index('<section class="caso" aria-labelledby="tlajomulco">'):]
B["zap_duo"] = grab(zsec, zsec.index('<div class="duo">'), "div")
B["tlaj_duo"] = grab(tsec, tsec.index('<div class="duo">'), "div")
B["tlaj_contador"] = grab(tsec, tsec.index('<ul class="contador"'), "ul")
B["tlaj_contador_fuentes"] = grab(tsec, tsec.index('<p class="note">'), "p")
B["zap_hosp_doc"] = grab(zsec, zsec.index('<figure class="documento">'), "figure")
B["tlaj_rec_doc"] = grab(tsec, tsec.index('<figure class="documento">'), "figure")
B["pipas_cap"] = re.search(r"<figcaption>Del 15 de octubre.*?</figcaption>", zsec, re.S).group()
B["cis_cap"] = re.search(r"<figcaption>Cada punto es una cisterna.*?</figcaption>", zsec, re.S).group()
B["pts_note"] = re.search(r'<p class="note">Siete de los diez puntos.*?</p>', tsec, re.S).group()
B["ir_zap"] = re.search(r'<a class="button" href="/zapopan">.*?</a>', zsec, re.S).group()
B["ir_tlaj"] = re.search(r'<a class="button" href="/tlajomulco">.*?</a>', tsec, re.S).group()
B["pendiente"] = grab(hub, hub.index('<ul class="municipios">'), "ul")
B["como"] = grab(hub, hub.index('<section aria-labelledby="como">'), "section")
B["amon_cap"] = re.search(r"<figcaption>Nitrógeno amoniacal, promedio mensual.*?</figcaption>", tla, re.S).group()
for page in (zap, tla):
    for m in re.finditer(r"<!-- documento:([\w-]+) -->", page):
        B["doc:" + m.group(1)] = clean_doc(grab(page, page.rindex("<figure", 0, m.start()), "figure"))
B["crono_zap"] = after(zap, '<ol class="cronologia">', "ol", 2)
B["crono_tlaj"] = after(tla, '<ol class="cronologia">', "ol", 1)
B["crono_zap_items"] = re.findall(r"<li>.*?</li>", B["crono_zap"], re.S)
B["crono_tlaj_items"] = re.findall(r"<li>.*?</li>", B["crono_tlaj"], re.S)
# The duo's three parts, for formats that lay them out differently.
for k in ("zap", "tlaj"):
    d = B[f"{k}_duo"]
    B[f"{k}_prometido"] = grab(d, d.index('<div class="prometido">'), "div")
    B[f"{k}_entregado"] = grab(d, d.index('<div class="entregado">'), "div")
    B[f"{k}_diferencia"] = grab(d, d.index('<div class="diferencia">'), "div")
    B[f"{k}_diferencia_txt"] = re.search(r"<span>(.*)</span></div>$", B[f"{k}_diferencia"], re.S).group(1)

# Both chronologies in one list, by date, each item tagged with its municipio and kind: what a government announced,
# what a document shows, or what we asked. Items without a <time> keep their place after the item before them.
ANUNCIO = {"zap:2026-10-17", "zap:2026-10-19", "zap:2026-10-27", "tlaj:2026-03-09"}
PEDIDO = {"tlaj:2026-11-10"}
todo = []
for k, items in (("zap", B["crono_zap_items"]), ("tlaj", B["crono_tlaj_items"])):
    prev = "2025-12-00"
    for j, li in enumerate(items):
        m = re.search(r'<time datetime="([\d-]+)">', li)
        key = m.group(1) if m else prev + "~"
        prev = key
        tipo = "anuncio" if f"{k}:{key}" in ANUNCIO else "pedido" if f"{k}:{key}" in PEDIDO else "documento"
        todo.append((key, k, j, li.replace("<li>", f'<li class="{k} {tipo}" data-m="{k}" data-tipo="{tipo}">', 1)))
todo.sort()
B["crono_todo"] = "\n".join(t[3] for t in todo)

head_end = hub.index("<script src=\"/theme.js\"></script>")
head = hub[:head_end]
head = re.sub(r'<link rel="canonical"[^>]*>\n', "", head)
head = re.sub(r'<meta property="og:url"[^>]*>\n', "", head)
head = head.replace('<meta name="viewport"', '<meta name="robots" content="noindex, nofollow">\n<meta name="viewport"', 1)
body_top = hub[head_end:hub.index("  <main>")]
foot = hub[hub.index("  </main>") + len("  </main>"):hub.index("</div>\n<script src=\"/vendor/leaflet")] + "</div>\n"


def fill(t):
    def rep(m):
        k = m.group(1)
        if k.startswith("doc:") and k not in B:
            sys.exit(f"unknown block {k}")
        v = B[k]
        return "\n".join(v) if isinstance(v, list) else v
    return re.sub(r"\{\{([\w:-]+)\}\}", rep, t)


FRAGS = sorted(HERE.glob("p*.html"), key=lambda p: int(re.sub(r"\D", "", p.stem)))
TITULOS = {int(re.sub(r"\D", "", f.stem)): re.match(r"<!-- titulo: (.*?)( \| mapa)? -->", f.read_text(encoding="utf8")).group(1) for f in FRAGS}


def barra(actual):
    """The row of version links under the site header; the page itself is marked as the site menu marks it."""
    def a(k):
        href = f"/nocuadra-p{k}" if k else "/nocuadra-propuestas"
        cur = ' aria-current="page"' if k == actual else ""
        txt = "Todas" if not k else f'<b>{k}</b><span>{TITULOS[k]}</span>'
        return f'<a href="{href}"{cur}>{txt}</a>'
    links = "".join(a(k) for k in sorted(TITULOS))
    return f'  <nav class="versiones" aria-label="Versiones de No cuadra"><span class="et">Versiones</span>{links}</nav>\n'


# On a narrow screen the row scrolls sideways: bring the current version into it.
BARRA_JS = '<script>(() => { const b = document.querySelector(".versiones"), a = b && b.querySelector("[aria-current]"); if (a) b.scrollLeft = a.offsetLeft - (b.clientWidth - a.offsetWidth) / 2; })();</script>\n'


n_written = 0
for frag in FRAGS:
    n = int(re.sub(r"\D", "", frag.stem))
    src = frag.read_text(encoding="utf8")
    meta = re.match(r"<!-- titulo: (.*?)( \| mapa)? -->\n", src)
    assert meta, frag
    titulo, mapa = meta.group(1), bool(meta.group(2))
    src = fill(src[meta.end():])
    style = re.search(r"<style>.*?</style>\n", src, re.S)
    main = re.search(r"  <main.*?</main>\n", src, re.S)
    script = re.search(r"<script>.*?</script>\n", src, re.S)
    assert style and main, frag
    nombre = f"nocuadra-p{n}.html" if n else "nocuadra-propuestas.html"
    t = f"No cuadra · propuesta {n}: {titulo} · Agua GDL" if n else f"No cuadra · {titulo} · Agua GDL"
    assert "<title>No cuadra · Agua GDL</title>" in head, "the hub's <title> changed: update gen.py"
    h = head.replace("<title>No cuadra · Agua GDL</title>", f"<title>{t}</title>")
    if not mapa:
        h = h.replace('<link rel="stylesheet" href="/vendor/leaflet-1.9.4/leaflet.css">\n', "")
    css = '<link rel="stylesheet" href="/nocuadra.css">\n'
    assert css in h
    h = h.replace(css, css + '<link rel="stylesheet" href="/nocuadra-lab.css">\n', 1)
    out = h + style.group() + body_top + barra(n) + main.group() + foot
    if mapa:
        out += '<script src="/vendor/leaflet-1.9.4/leaflet.js"></script>\n<script src="/mapa.js"></script>\n'
    out += '<script src="/nocuadra-lab.js"></script>\n'
    if script:
        out += script.group()
    out += BARRA_JS + "</body>\n</html>\n"
    if not n:
        out = out.replace('<script src="/nocuadra-lab.js"></script>\n', "")
    (WEB / nombre).write_text(out, encoding="utf8")
    n_written += 1
print(f"{n_written} pages; blocks: {len(B)}")
if len(sys.argv) > 1 and sys.argv[1] == "--blocks":
    for k, v in B.items():
        print(k, len(v))
