"""/fotos: the crisis in photos and videos, a collage built from reviewed previews.

    python3 pipelines/fotos.py                  write web/fotos.html
    python3 pipelines/fotos.py --check          fail if web/fotos.html is stale or a reviewed photo is missing; for CI
    python3 pipelines/fotos.py --pendientes     list previews nobody has reviewed yet
    python3 pipelines/fotos.py --variantes DIR  write the design variants (v1..v6) into DIR (web/ serves them noindex
                                                at /fotos-v1../fotos-v6 until one is chosen; --check keeps them fresh)

Photos come from web/publicaciones.json's vistas (web/fuentes/), /noticias' photos (web/img/noticias/)
and its video thumbnails (web/img/videos/). Only the ones in pipelines/fotos_temas.json's "temas" make
the page: that list was reviewed by eye, so text-only cards, official notices, maps, interviews and
anything showing a private person's name stay out, and a new preview stays out until someone tags it.
"""
import html
import json
import pathlib
import re
import struct
import sys

root = pathlib.Path(__file__).resolve().parent.parent
WEB = root / "web"
PUB = WEB / "publicaciones.json"
NOTICIAS = WEB / "noticias.html"
TEMAS = root / "pipelines/fotos_temas.json"
OUT = WEB / "fotos.html"

TEMA = {"protesta": "Protesta", "sin-agua": "Sin agua", "calidad": "Agua sucia"}
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_LARGOS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
CHICAS = {"de", "del", "la", "las", "los", "el", "y", "en"}
VIDEO_URL = re.compile(r"facebook\.com/(reel|watch|share/[rv])|fb\.watch|youtube\.com|youtu\.be|tiktok\.com")


def dims(path):
    b = path.read_bytes()
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        c = b[12:16]
        if c == b"VP8 ":
            w, h = struct.unpack("<HH", b[26:30])
            return w & 0x3FFF, h & 0x3FFF
        if c == b"VP8L":
            v = int.from_bytes(b[21:25], "little")
            return (v & 0x3FFF) + 1, ((v >> 14) & 0x3FFF) + 1
        if c == b"VP8X":
            return int.from_bytes(b[24:27], "little") + 1, int.from_bytes(b[27:30], "little") + 1
    i = 2
    while i + 9 < len(b):
        if b[i] != 0xFF:
            i += 1
            continue
        m = b[i + 1]
        if m in (0xD8, 0x01, 0xFF) or 0xD0 <= m <= 0xD7:
            i += 2 if m != 0xFF else 1
            continue
        if m in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", b[i + 5:i + 9])
            return w, h
        i += 2 + struct.unpack(">H", b[i + 2:i + 4])[0]
    raise ValueError(f"{path}: can't read its size")


def nombre(key):
    n, m, _ = key.split("|")
    words = [w.capitalize() if i == 0 or w.lower() not in CHICAS else w.lower() for i, w in enumerate(n.split())]
    return " ".join(words), m


def fecha_larga(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} de {MESES_LARGOS[int(m) - 1]}"


def fecha_corta(iso):
    y, m, d = iso.split("-")
    return f"{int(d)} {MESES[int(m) - 1]}"


def from_publicaciones(temas):
    by = {}
    for p in json.loads(PUB.read_text())["publicaciones"]:
        v = p.get("vista")
        if v in temas:
            by.setdefault(v, []).append(p)
    out = []
    for v, ps in by.items():
        posts = [p for p in ps if p.get("tipo") != "comentario"]
        rep = min(posts or ps, key=lambda p: (p["fecha"], p["fuente"] != "medio"))
        url, quien = (rep["url"], rep["quien"]) if rep.get("tipo") != "comentario" else (rep["en"]["url"], rep["en"]["quien"])
        cols = sorted({c for p in ps for c in p["colonias"]})
        video = any(p.get("video") for p in ps) or bool(VIDEO_URL.search(url))
        out.append({"img": v, "tema": temas[v], "fecha": rep["fecha"], "url": url, "quien": quien or "Vecinos",
                    "lugar": rep["lugar"], "colonias": cols, "video": video, "alt": ""})
    return out


def from_noticias(temas):
    text = NOTICIAS.read_text()
    out = []
    day = None
    for m in re.finditer(r"<h3>(\d{1,2}) de (\w+)</h3>|<article\b.*?</article>|<figure class=\"video\".*?</figure>", text, re.S):
        if m.group(1):
            day = f"2026-{MESES_LARGOS.index(m.group(2)) + 1:02d}-{int(m.group(1)):02d}"
            continue
        block = m.group(0)
        for fig in re.findall(r'<figure class="video".*?</figure>', block, re.S):
            img = re.search(r'src="/(img/videos/[^"]+)"', fig).group(1)
            if img not in temas:
                continue
            src = re.search(r'<span class="src">([^<]+) · (\d{1,2}) (\w{3})[^<]*</span>', fig)
            href = re.search(r'<figcaption><a href="([^"]+)"', fig).group(1)
            vt = re.search(r'<span class="vt">([^<]+)</span>', fig)
            iso = f"2026-{MESES.index(src.group(3)) + 1:02d}-{int(src.group(2)):02d}"
            out.append({"img": img, "tema": temas[img], "fecha": iso, "url": html.unescape(href), "quien": html.unescape(src.group(1)),
                        "lugar": "", "colonias": [], "video": True, "alt": html.unescape(vt.group(1)) if vt else ""})
        if block.startswith("<figure"):
            continue
        via = re.search(r'<span class="via"><a href="([^"]+)"[^>]*>([^<]+)</a>', block)
        for im in re.finditer(r'<img src="/(img/noticias/[^"]+)"[^>]*alt="([^"]*)"', block):
            img = im.group(1)
            if img not in temas or not via or not day:
                continue
            quien = re.sub(r"\s*\((grupo|Facebook[^)]*)\)$", "", html.unescape(via.group(2)))
            out.append({"img": img, "tema": temas[img], "fecha": day, "url": html.unescape(via.group(1)), "quien": quien,
                        "lugar": "", "colonias": [], "video": False, "alt": html.unescape(im.group(2))})
    return out


def tiles():
    doc = json.loads(TEMAS.read_text())
    temas = doc["temas"]
    ts = from_publicaciones(temas) + from_noticias(temas)
    found = {t["img"] for t in ts}
    missing = [k for k in temas if k not in found or not (WEB / k).is_file()]
    for t in ts:
        t["w"], t["h"] = dims(WEB / t["img"])
        names = [nombre(c) for c in t["colonias"]]
        t["cols"] = [n for n, _ in names]
        if not t["alt"]:
            donde = t["lugar"] or ", ".join(f"{n}, {m}" for n, m in names[:2])
            t["alt"] = f"{TEMA[t['tema']]}{' (video)' if t['video'] else ''}" + (f" en {donde}" if donde else "")
    ts.sort(key=lambda t: (t["fecha"], t["img"]), reverse=True)
    return ts, missing, doc


E = html.escape


def tile(t, prefix="/", extra=""):
    cap = f'{E(fecha_corta(t["fecha"]))} · {E(t["cols"][0] if t["cols"] else t["quien"])}'
    small = f'<small>{E(t["quien"])}</small>' if t["cols"] else ""
    return (f'<a class="t {t["tema"]}{" v" if t["video"] else ""}" href="{E(t["url"])}" target="_blank" rel="noopener"'
            f' data-tema="{t["tema"]}" data-fecha="{t["fecha"]}" data-col="{E("|".join(t["cols"]))}"'
            f' style="--r:{t["w"] / t["h"]:.3f}"{extra}>'
            f'<img src="{prefix}{t["img"]}" width="{t["w"]}" height="{t["h"]}" alt="{E(t["alt"])}" loading="lazy" decoding="async">'
            f'{"<span class=play aria-hidden=true></span>" if t["video"] else ""}'
            f'<span class="cap"><b>{cap}</b>{small}</span></a>')


def filtros(ts, fecha=True):
    cols = {}
    for t in ts:
        for c in t["cols"]:
            cols[c] = cols.get(c, 0) + 1
    opts = "".join(f'<option value="{E(c)}">{E(c)} ({n})</option>' for c, n in sorted(cols.items(), key=lambda kv: (-kv[1], kv[0])))
    n = {k: sum(1 for t in ts if t["tema"] == k) for k in TEMA}
    nv = sum(1 for t in ts if t["video"])
    chips = (f'<button type="button" class="chip" data-f="" aria-pressed="true">Todo <span>{len(ts)}</span></button>'
             + "".join(f'<button type="button" class="chip" data-f="{k}" aria-pressed="false">{v} <span>{n[k]}</span></button>' for k, v in TEMA.items())
             + f'<button type="button" class="chip" data-f="video" aria-pressed="false">Videos <span>{nv}</span></button>')
    dias = sorted({t["fecha"] for t in ts})
    fsel = ""
    if fecha:
        o = "".join(f'<option value="{d}">{E(fecha_larga(d))}</option>' for d in dias)
        fsel = (f'<label>Desde <select id="desde"><option value="">el inicio</option>{o}</select></label>'
                f'<label>Hasta <select id="hasta"><option value="">hoy</option>{o}</select></label>')
    return (f'<div class="filtros" role="group" aria-label="Filtrar fotos"><div class="chips">{chips}</div>'
            f'<div class="sel"><label>Colonia <select id="colonia"><option value="">Todas</option>{opts}</select></label>{fsel}</div>'
            f'<p class="cuenta" id="cuenta" aria-live="polite"></p></div>')


SCRIPT = """<script>
(() => {
  const tiles = [...document.querySelectorAll('.t')];
  const chips = [...document.querySelectorAll('.chip')];
  const $ = (id) => document.getElementById(id);
  let tema = '';
  const apply = () => {
    const col = $('colonia')?.value || '', d = $('desde')?.value || '', h = $('hasta')?.value || '';
    let n = 0;
    for (const t of tiles) {
      const ok = (!tema || (tema === 'video' ? t.classList.contains('v') : t.dataset.tema === tema))
        && (!col || t.dataset.col.split('|').includes(col))
        && (!d || t.dataset.fecha >= d) && (!h || t.dataset.fecha <= h);
      t.hidden = !ok;
      if (ok) n++;
    }
    for (const g of document.querySelectorAll('[data-grupo]')) g.hidden = !g.querySelector('.t:not([hidden])');
    $('cuenta').textContent = n === 1 ? '1 foto' : n + ' fotos';
  };
  for (const c of chips) c.addEventListener('click', () => {
    tema = c.dataset.f;
    for (const o of chips) o.setAttribute('aria-pressed', o === c);
    apply();
  });
  for (const id of ['colonia', 'desde', 'hasta']) $(id)?.addEventListener('change', apply);
  apply();
})();
</script>"""

BASE_CSS = """
.filtros { position: sticky; top: 0; z-index: 5; background: color-mix(in srgb, var(--bg) 92%, transparent); backdrop-filter: blur(8px); padding: 10px 0; margin: 0 0 14px; border-bottom: 1px solid var(--line) }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 0 0 8px }
.chip { font: inherit; font-size: .88rem; padding: 5px 12px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); color: var(--fg); cursor: pointer }
.chip span { color: var(--muted); font-variant-numeric: tabular-nums }
.chip[aria-pressed="true"] { background: var(--primary); border-color: var(--primary); color: var(--on-primary) }
.chip[aria-pressed="true"] span { color: inherit; opacity: .8 }
.sel { display: flex; flex-wrap: wrap; gap: 8px 14px; font-size: .88rem; color: var(--muted) }
.sel select { font: inherit; color: var(--fg); background: var(--surface); border: 1px solid var(--line); border-radius: 6px; padding: 4px 6px; margin-left: 4px; max-width: 14rem }
.cuenta { margin: 6px 0 0; font-size: .82rem; color: var(--muted) }
.t { position: relative; display: block; overflow: hidden; background: var(--subtle); color: #fff; text-decoration: none }
.t img { display: block; width: 100%; height: 100%; object-fit: cover; transition: transform .3s }
.t:hover img, .t:focus-visible img { transform: scale(1.03) }
.cap { position: absolute; inset: auto 0 0 0; padding: 18px 8px 6px; background: linear-gradient(transparent, rgb(0 0 0 / .72)); font-size: .74rem; line-height: 1.3; display: flex; flex-direction: column }
.cap b { font-weight: 600 } .cap small { opacity: .85; white-space: nowrap; overflow: hidden; text-overflow: ellipsis }
.play { position: absolute; top: 8px; right: 8px; width: 28px; height: 28px; border-radius: 50%; background: rgb(0 0 0 / .6) }
.play::after { content: ""; position: absolute; left: 11px; top: 8px; border: 6px solid transparent; border-left: 9px solid #fff; border-right: 0 }
.t::before { content: ""; position: absolute; left: 0; top: 0; width: 4px; height: 100%; z-index: 1 }
.t.protesta::before { background: var(--rep, #dc2626) } .t.sin-agua::before { background: var(--agua, #0284c7) } .t.calidad::before { background: #a16207 }
section.dia, section.colonia, section.frente { padding: 0 }
.aviso { font-size: .85rem; color: var(--muted); max-width: 70ch }
@media (prefers-reduced-motion: reduce) { .t img { transition: none } }
"""

VARIANTES = {
    "v1": ("Mosaico", "Columnas con cada foto en su proporción, la más reciente primero.", """
.collage { columns: 4 220px; column-gap: 6px }
.collage .t { break-inside: avoid; margin: 0 0 6px; border-radius: 4px; aspect-ratio: var(--r) }
@media (max-width: 560px) { .collage { columns: 2; column-gap: 4px } .collage .t { margin-bottom: 4px } }
"""),
    "v2": ("Muro", "Cuadrícula pareja de borde a borde: un muro de cuadros iguales.", """
.collage { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 2px; margin: 0 calc(50% - 50vw); padding: 0 2px }
.collage .t { aspect-ratio: 1 }
.collage .cap { opacity: 0; transition: opacity .2s } .collage .t:hover .cap, .collage .t:focus-visible .cap { opacity: 1 }
@media (max-width: 560px) { .collage { grid-template-columns: repeat(3, 1fr) } .collage .cap { display: none } }
"""),
    "v3": ("Día por día", "Una fila por día, con las fotos a la misma altura.", """
.dia h3 { font-size: 1rem; margin: 18px 0 6px; font-style: italic; font-weight: 400; color: var(--muted) }
.fila { display: flex; flex-wrap: wrap; gap: 4px }
.fila .t { height: 150px; flex: calc(var(--r) * 150) 1 calc(var(--r) * 150px); max-width: 100%; border-radius: 3px }
.fila::after { content: ""; flex: 999 1 0 }
@media (max-width: 560px) { .fila .t { height: 110px; flex-basis: calc(var(--r) * 110px) } }
"""),
    "v4": ("Por colonia", "Una tira por colonia, de la que tiene más fotos a la que menos; se desliza de lado.", """
.colonia h3 { font-size: 1rem; margin: 18px 0 6px; display: flex; gap: 8px; align-items: baseline } .colonia h3 span { font-size: .8rem; color: var(--muted); font-weight: 400 }
.tira { display: flex; gap: 4px; overflow-x: auto; scroll-snap-type: x mandatory; padding-bottom: 6px }
.tira .t { flex: 0 0 auto; height: 180px; aspect-ratio: var(--r); scroll-snap-align: start; border-radius: 4px; max-width: 80vw }
@media (max-width: 560px) { .tira .t { height: 140px } }
"""),
    "v5": ("Portada", "Collage de periódico: protestas y videos ocupan cuadros grandes, el resto llena los huecos.", """
.collage { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); grid-auto-rows: 140px; grid-auto-flow: dense; gap: 4px }
.collage .t.g { grid-column: span 2; grid-row: span 2 }
.collage .t.a { grid-column: span 2 }
.collage .t.l { grid-row: span 2 }
@media (max-width: 560px) { .collage { grid-template-columns: repeat(3, 1fr); grid-auto-rows: 31vw; gap: 3px } .collage .cap small { display: none } }
"""),
    "v6": ("Tres frentes", "Tres bloques: protestas, gente sin agua y agua sucia, cada uno con su color.", """
.frente { margin: 0 0 22px; border-top: 4px solid var(--c); padding-top: 8px }
.frente h3 { font-size: 1.15rem; margin: 0 0 8px; color: var(--c); display: flex; gap: 8px; align-items: baseline } .frente h3 span { font-size: .8rem; color: var(--muted); font-style: normal }
.frente.protesta { --c: var(--rep, #dc2626) } .frente.sin-agua { --c: var(--agua, #0284c7) } .frente.calidad { --c: #a16207 }
.frente .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 3px }
.frente .t { aspect-ratio: 4/5 } .frente .t::before { display: none }
@media (max-width: 560px) { .frente .grid { grid-auto-flow: column; grid-template-columns: none; grid-auto-columns: 42vw; grid-template-rows: repeat(2, auto); overflow-x: auto; scroll-snap-type: x mandatory } .frente .t { scroll-snap-align: start } }
"""),
}


def cuerpo(v, ts, prefix):
    if v in ("v1", "v2"):
        return f'<div class="collage">{"".join(tile(t, prefix) for t in ts)}</div>'
    if v == "v3":
        dias = {}
        for t in ts:
            dias.setdefault(t["fecha"], []).append(t)
        return "".join(f'<section class="dia" data-grupo><h3>{E(fecha_larga(d))}</h3><div class="fila">{"".join(tile(t, prefix) for t in g)}</div></section>' for d, g in dias.items())
    if v == "v4":
        grupos = {}
        for t in ts:
            for c in t["cols"] or ["Sin colonia en la publicación"]:
                grupos.setdefault(c, []).append(t)
        orden = sorted(grupos.items(), key=lambda kv: (kv[0].startswith("Sin colonia"), -len(kv[1]), kv[0]))
        return "".join(f'<section class="colonia" data-grupo><h3>{E(c)} <span>{len(g)}</span></h3><div class="tira">{"".join(tile(t, prefix) for t in g)}</div></section>' for c, g in orden)
    if v == "v5":
        out = []
        for i, t in enumerate(ts):
            r = t["w"] / t["h"]
            k = "g" if (t["video"] or (t["tema"] == "protesta" and i % 3 == 0)) and r > .8 else "a" if r > 1.6 else "l" if r < .7 else ""
            out.append(tile(t, prefix).replace('class="t ', f'class="t {k} ', 1) if k else tile(t, prefix))
        return f'<div class="collage">{"".join(out)}</div>'
    return "".join(f'<section class="frente {k}" data-grupo><h3>{E(n)} <span>{sum(1 for t in ts if t["tema"] == k)}</span></h3><div class="grid">{"".join(tile(t, prefix) for t in ts if t["tema"] == k)}</div></section>' for k, n in [("protesta", "Protestas"), ("sin-agua", "Sin agua"), ("calidad", "Agua sucia")])


def page(v, ts, prefix="/", variante=False):
    shell = NOTICIAS.read_text()
    head_css = "".join(re.findall(r"<style>.*?</style>", shell, re.S)[:1])
    talavera = re.search(r"<style>/\* Talavera \*/.*?</style>", shell, re.S).group(0)
    base = re.sub(r"\.hero\b.*", "", head_css, flags=re.S).rstrip() + "\n</style>"
    nav = re.search(r"<header class=\"top\">.*?</header>", shell, re.S).group(0).replace(' aria-current="page"', "")
    foot = re.search(r"<footer>.*?</footer>", shell, re.S).group(0)
    if prefix != "/":
        for a in ("logo.svg", "icons.svg", "theme.js"):
            nav = nav.replace(f'"/{a}', f'"{prefix}{a}')
    titulo, desc, css = VARIANTES[v]
    desde = min(t["fecha"] for t in ts)
    n_med = len({t["quien"] for t in ts})
    tag = f'<p class="aviso"><b>Variante {v[1]}: {E(titulo)}.</b> {E(desc)}</p>' if variante else ""
    return f"""<!doctype html>
<html lang="es-MX">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="facebook-domain-verification" content="li0vsm7edv0afccxodm5t0jvyiw0za">
<title>La crisis del agua, en fotos · Agua GDL</title>
<meta name="description" content="Fotos y videos de la crisis del agua en Guadalajara: protestas, filas en las pipas, cubetas vacías y agua sucia, cada una con su publicación original.">
{'<meta name="robots" content="noindex">' if variante else '<link rel="canonical" href="https://aguagdl.com/fotos">'}
<meta name="theme-color" content="#ffffff">
<link rel="icon" href="{prefix}favicon.ico" sizes="any">
<link rel="icon" href="{prefix}logo.svg" type="image/svg+xml">
{base}
{talavera}
<style>{BASE_CSS}{css}</style>
<script src="{prefix}theme.js"></script>
</head>
<body>
<div class="wrap">
  {nav}
  <main>
  {tag}
  <h1>La crisis del agua, en fotos</h1>
  <p class="lede">{len(ts)} fotos y videos que publicaron {n_med} medios, grupos y cuentas de vecinos desde el {E(fecha_larga(desde))}: protestas, filas en las pipas, cubetas vacías y agua sucia. Toca una para abrir la publicación original.</p>
  {filtros(ts, fecha=v != "v3")}
  {cuerpo(v, ts, prefix)}
  <p class="aviso">Guardamos una copia pequeña de cada imagen, así tu navegador no se conecta a Facebook, a X ni a los medios para verlas. No incluimos publicaciones de solo texto, avisos oficiales ni imágenes con el nombre de una persona. Si apareces en una foto y quieres que la quitemos, escríbenos a <a href="mailto:soporte@aguagdl.com">soporte@aguagdl.com</a>.</p>
  </main>
  {foot}
</div>
{SCRIPT}
</body>
</html>
"""


def main():
    args = sys.argv[1:]
    ts, missing, doc = tiles()
    if missing:
        sys.exit(f"fotos: reviewed photos not found in the sources or on disk: {', '.join(missing)}")
    if "--pendientes" in args:
        seen = set(doc["temas"]) | set(doc["fuera"])
        vistas = {p["vista"] for p in json.loads(PUB.read_text())["publicaciones"] if p.get("vista")}
        imgs = {f"img/{d}/{f.name}" for d in ("noticias", "videos") for f in (WEB / "img" / d).iterdir()}
        pend = sorted((vistas | imgs) - seen)
        print("\n".join(pend) or "fotos: nothing to review")
        return
    if "--variantes" in args:
        out = pathlib.Path(args[args.index("--variantes") + 1])
        out.mkdir(parents=True, exist_ok=True)
        prefix = "/" if (out.resolve() / "x").is_relative_to(WEB.resolve()) else ""
        for v in VARIANTES:
            (out / f"fotos-{v}.html").write_text(page(v, ts, prefix or "/", variante=True))
        print(f"fotos: wrote {len(VARIANTES)} variants with {len(ts)} photos to {out}")
        return
    want = page(CHOSEN, ts)
    if "--check" in args:
        if not OUT.is_file() or OUT.read_text() != want:
            sys.exit("fotos: web/fotos.html is stale; run python3 pipelines/fotos.py")
        for v in VARIANTES:
            f = WEB / f"fotos-{v}.html"
            if f.is_file() and f.read_text() != page(v, ts, variante=True):
                sys.exit(f"fotos: web/{f.name} is stale; run python3 pipelines/fotos.py --variantes web")
        print(f"fotos: ok, {len(ts)} photos")
        return
    OUT.write_text(want)
    print(f"fotos: wrote web/fotos.html with {len(ts)} photos")


CHOSEN = "v1"

if __name__ == "__main__":
    main()
