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
    carteles = set(doc.get("carteles", []))
    missing = [k for k in carteles if k not in temas]
    ts = from_publicaciones(temas) + from_noticias(temas)
    found = {t["img"] for t in ts}
    missing += [k for k in temas if k not in found or not (WEB / k).is_file()]
    for t in ts:
        t["cartel"] = t["img"] in carteles
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
    return (f'<a class="t {t["tema"]}{" v" if t["video"] else ""}{" c" if t["cartel"] else ""}" href="{E(t["url"])}" target="_blank" rel="noopener"'
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
    document.dispatchEvent(new Event('fotos-filtro'));
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

MASONRY_CSS = """
.collage { columns: 4 220px; column-gap: 6px }
.collage .t { break-inside: avoid; margin: 0 0 6px; border-radius: 4px; aspect-ratio: var(--r) }
.collage.js { columns: auto; position: relative }
.collage.js .t { position: absolute; margin: 0 }
@media (max-width: 560px) { .collage { columns: 2; column-gap: 4px } .collage .t { margin-bottom: 4px } }
.t.c .cap { font-size: .82rem }
"""

MASONRY_JS = """<script>
(() => {
  for (const box of document.querySelectorAll('.collage[data-cfg]')) {
  const cfg = JSON.parse(box.dataset.cfg);
  const lay = () => {
    if (box.hidden || !box.clientWidth) return;
    const W = box.clientWidth, phone = W < 560, g = phone ? 4 : cfg.gap;
    const n = Math.max(phone ? cfg.phoneCols : 2, Math.floor((W + g) / (cfg.col + g)));
    const cw = (W - g * (n - 1)) / n, h = new Array(n).fill(0), cols = h.map(() => []);
    box.classList.add('js');
    const span = (t) => Math.min(n, t.classList.contains('c') ? (n >= 5 ? cfg.bigWide : cfg.big) : t.classList.contains('v') ? cfg.video : 1);
    const queue = [...box.children].filter((t) => !t.hidden);
    const put = (t, col, s) => {
      const top = Math.max(...h.slice(col, col + s));
      const w = cw * s + g * (s - 1), ht = w / parseFloat(t.style.getPropertyValue('--r'));
      Object.assign(t.style, { left: col * (cw + g) + 'px', top: top + 'px', width: w + 'px', height: ht + 'px' });
      for (let i = col; i < col + s; i++) h[i] = top + ht + g;
      if (s === 1) cols[col].push([t, ht]);
    };
    while (queue.length) {
      const m = Math.min(...h), low = h.indexOf(m);
      let done = false;
      // Fill the lowest column with the first of the next few tiles that fits there without leaving a hole.
      for (let k = 0; k < Math.min(6, queue.length) && !done; k++) {
        const s = span(queue[k]);
        for (let c = Math.max(0, low - s + 1); c <= Math.min(low, n - s); c++) {
          if (h.slice(c, c + s).every((x) => x <= m + 24)) { put(queue[k], c, s); queue.splice(k, 1); done = true; break; }
        }
      }
      if (!done) {
        const t = queue.shift(), s = span(t);
        let col = 0, top = Infinity;
        for (let i = 0; i <= n - s; i++) { const x = Math.max(...h.slice(i, i + s)); if (x < top - 1) { top = x; col = i; } }
        put(t, col, s);
      }
    }
    // A block that a band follows ends flush: a short column's photos grow a little (cropped by cover).
    if (cfg.flush && cols.every((c) => c.length)) {
      const end = Math.max(...h);
      cols.forEach((c, i) => {
        const sum = c.reduce((a, [, x]) => a + x, 0), f = (sum + end - h[i]) / sum;
        let top = 0;
        for (const [t, x] of c) { t.style.top = top + 'px'; t.style.height = x * f + 'px'; top += x * f + g; }
        h[i] = end;
      });
    }
    box.style.height = Math.max(0, ...h) - g + 'px';
  };
  let w = 0;
  new ResizeObserver(() => { if (box.clientWidth !== w) { w = box.clientWidth; lay(); } }).observe(box);
  document.addEventListener('fotos-filtro', lay);
  }
})();
</script>"""

VARIANTES = {
    "v1": ("Mosaico", "Columnas con cada foto en su proporción, la más reciente primero.", MASONRY_CSS),
    "v7": ("Carteles al doble", "El mosaico de la variante 1; las fotos donde se lee un cartel ocupan dos columnas.", MASONRY_CSS),
    "v8": ("Carteles primero", "Abre con el muro de carteles, a doble columna; después, todo lo demás por fecha.", MASONRY_CSS),
    "v9": ("Mosaico fino", "Seis columnas angostas; los carteles ocupan tres (dos en el teléfono).", MASONRY_CSS),
    "v10": ("Bandas de carteles", "El mosaico de la variante 1, cortado cada tanto por una franja con dos carteles grandes.", MASONRY_CSS + """
.banda { display: flex; gap: 6px; margin: 0 0 6px }
.banda .t { flex: var(--r) 1 0; aspect-ratio: var(--r); border-radius: 4px }
@media (max-width: 560px) { .banda { gap: 4px; margin-bottom: 4px } }
"""),
}

CFG = {
    "v7": {"col": 220, "gap": 6, "phoneCols": 2, "big": 2, "bigWide": 2, "video": 1},
    "v8": {"col": 220, "gap": 6, "phoneCols": 2, "big": 2, "bigWide": 2, "video": 1},
    "v10": {"col": 220, "gap": 6, "phoneCols": 2, "big": 1, "bigWide": 1, "video": 1, "flush": True},
    "v9": {"col": 140, "gap": 4, "phoneCols": 3, "big": 2, "bigWide": 3, "video": 1},
}


def cuerpo(v, ts, prefix):
    if v == "v8":
        ts = [t for t in ts if t["cartel"]] + [t for t in ts if not t["cartel"]]
    if v == "v10":
        attr = f" data-cfg='{json.dumps(CFG[v])}'"
        out, block, pend = [], [], []

        def flush(xs, cls):
            if xs:
                out.append(f'<div class="{cls}" data-grupo{attr if cls == "collage" else ""}>{"".join(tile(t, prefix) for t in xs)}</div>')

        rest = sum(1 for t in ts if not t["cartel"])
        for t in ts:
            if t["cartel"]:
                pend.append(t)
            else:
                block.append(t)
                rest -= 1
            if len(block) >= 8 and len(pend) >= 2 and rest >= 8:
                flush(block, "collage")
                flush(pend[:2], "banda")
                block, pend = [], pend[2:]
        flush(block, "collage")
        flush(pend, "banda")
        return "".join(out) + MASONRY_JS
    if v in CFG:
        return f'<div class="collage" data-cfg=\'{json.dumps(CFG[v])}\'>{"".join(tile(t, prefix) for t in ts)}</div>{MASONRY_JS}'
    return f'<div class="collage">{"".join(tile(t, prefix) for t in ts)}</div>'


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
    tag = ""
    if variante:
        cur = ' aria-current="page"'
        links = "".join(f'<a href="/fotos-{k}"{cur if k == v else ""} title="{E(VARIANTES[k][1])}">{k[1:]} · {E(VARIANTES[k][0])}</a>' for k in VARIANTES)
        tag = (f'<p class="aviso"><b>Variante {v[1:]}: {E(titulo)}.</b> {E(desc)}</p>'
               f'<nav class="vbar" aria-label="Variantes">{links}</nav>'
               '<style>.vbar { position: fixed; left: 50%; bottom: 12px; transform: translateX(-50%); z-index: 20; display: flex; gap: 4px; max-width: calc(100vw - 16px); overflow-x: auto; scrollbar-width: none; padding: 5px; border-radius: 999px; background: var(--surface); border: 1px solid var(--line); box-shadow: 0 4px 18px rgb(0 0 0 / .18) }'
               ' .vbar a { white-space: nowrap; padding: 6px 12px; border-radius: 999px; font-size: .85rem; color: var(--fg); text-decoration: none }'
               ' .vbar a:hover { background: var(--subtle) } .vbar a[aria-current] { background: var(--primary); color: var(--on-primary) }'
               ' body { padding-bottom: 64px }</style>'
               "<script>addEventListener('load', () => { const b = document.querySelector('.vbar'), a = b.querySelector('[aria-current]'); b.scrollLeft = a.offsetLeft - (b.clientWidth - a.offsetWidth) / 2; });</script>")
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
  {filtros(ts, fecha=True)}
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
