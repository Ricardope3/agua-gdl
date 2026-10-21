#!/usr/bin/env python3
"""Variants of the landing page, to compare ordering and placement in one style: writes
web/v1.html … web/v5.html (noindex, with a bar to switch between them and the current landing)
from the pieces of web/index.html, so each carries its copy, quotes and sources as they are.
All five share STYLE, v1's newspaper look (serif headlines, quotes and figures, rules in ink);
each adds its own layout. Change a variant here and run it again; a piece index.html no longer
has stops it.

Usage, from the repo root: python3 -I experiments/landing/variantes.py
"""
import html
import re
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent.parent
WEB = ROOT / "web"
SRC = (WEB / "index.html").read_text(encoding="utf-8")


def grab(pattern, text=SRC):
    m = re.search(pattern, text, re.S)
    if not m:
        raise SystemExit(f"web/index.html has no {pattern[:70]!r}: update variantes.py")
    return m.group(0)


def text(html):
    return " ".join(re.sub(r"<[^>]+>", "", html).split())


def split(section):
    """A section's heading text and what follows the heading."""
    m = re.match(r"\s*<section[^>]*>\s*<h2[^>]*>(.*?)</h2>(.*)</section>\s*$", section, re.S)
    return text(m.group(1)), m.group(2)


V = re.search(r"/icons\.svg\?v=(\d+)", SRC).group(1)


def icon(name):
    return f'<svg class="i" aria-hidden="true"><use href="/icons.svg?v={V}#{name}"/></svg>'


HEAD, AFTER_STYLE = SRC.split("</style>", 1)
HEAD_END = AFTER_STYLE.split("</head>", 1)[0]
HEADER = grab(r'  <header class="top">.*?</header>\n')
FOOTER = grab(r"  <footer>.*?</footer>\n")
SCRIPT = grab(r"<script>\n\(\(\) => \{.*?</script>\n")
H1 = grab(r"<h1>.*?</h1>")
LEDE = grab(r'<p class="lede">.*?</p>')
PULSE = grab(r'<p class="pulse".*?</p>')
FORM = grab(r'<form class="quick".*?</form>')
CONGRESO_BOX = grab(r'<a class="aviso" href="/escribe">.*?</a>')
EXIGE_BOX = grab(r'<a class="aviso" href="/exige">.*?</a>')
ALERTA = grab(r'<div class="alerta">.*?</div>')
VS = grab(r'    <section class="vs".*?</section>\n')
VS_TITLE = text(grab(r'<h2 id="vs">.*?</h2>', VS))
PROMESA = grab(r'<div class="vs-col promesa">.*?</div>', VS)
REALIDAD_H3 = grab(r"<h3>Lo que está pasando</h3>", VS)
FACTS = grab(r'<ul class="vs-facts">.*?</ul>', VS)
NEWS = grab(r'<h4>En las noticias</h4>\s*<ul class="posts">.*?</ul>', VS)
NEIGHBOURS = grab(r'<h4>Lo que publican los vecinos</h4>\s*<ul class="posts">.*?</ul>', VS)
POSTS_NOTE = grab(r'<p class="note">.*?</p>', VS)
VS_BUTTONS = grab(r'<div class="buttons">.*?</div>', VS)
CONGRESO = grab(r'    <section class="congreso".*?</section>\n')
MAS = grab(r'    <section aria-labelledby="mas">.*?</section>\n')
WHY = grab(r'    <section class="why".*?</section>\n')
CONTACT = grab(r'    <section class="contact".*?</section>\n')
POSTS = [(text(q), text(who).removesuffix(" · en X"))
         for q, who in re.findall(r'<li><q>(.*?)</q><span class="who">(.*?)</span></li>', NEWS + NEIGHBOURS, re.S)]


def realidad(facts=True):
    return f'<div class="vs-col realidad">\n{REALIDAD_H3}\n{FACTS if facts else ""}\n{NEWS}\n{NEIGHBOURS}\n{POSTS_NOTE}\n</div>'


def vs(facts=True):
    return (f'    <section class="vs" aria-labelledby="vs">\n<h2 id="vs">{VS_TITLE}</h2>\n'
            f'<div class="vs-grid">\n{PROMESA}\n{realidad(facts)}\n</div>\n{VS_BUTTONS}\n    </section>\n')


# The colonia with the most publications on /reportes (24 on 21 Oct 2026): some variants open on it.
GRANJA = {"q": "CIUDAD GRANJA", "m": "Zapopan", "cp": "45010"}


def map_hero(colonia=None):
    """/reportes' own map, front and center, on a colonia or on the whole city."""
    src = html.escape("/reportes" + ("?" + urlencode(colonia) if colonia else ""))
    if colonia:
        note = (f'<p class="mapnote" data-colonia="{html.escape("|".join(colonia.values()))}"><span>Ciudad Granja, en Zapopan, '
                f'en el mapa de lo que publican medios y vecinos.</span> <a href="{src}">Abrir el mapa completo</a></p>')
    else:
        note = ('<p class="mapnote"><span>Cada colonia toma el color de los días sin agua que dicen sus publicaciones. '
                f'Toca la tuya para ver qué se ha publicado y reportarla.</span> <a href="{src}">Abrir el mapa completo</a></p>')
    return (f'    <div class="maphero">\n      <div class="mapframe-box"><iframe class="mapframe" src="{src}" '
            f'title="Mapa de lo que publican medios y vecinos, colonia por colonia"></iframe></div>\n      {note}\n    </div>\n')


# /reportes is a whole page: in the frame only its map shows, its links leave the frame, it follows
# this page's theme, and the note under it says how many publications the colonia has.
EMBED = r"""<script>
(() => {
  const f = document.querySelector(".mapframe");
  if (!f) return;
  const api = new URLSearchParams(location.search).get("api");
  if (api) { const u = new URL(f.src); u.searchParams.set("api", api); f.src = u; }
  f.addEventListener("load", () => {
    const d = f.contentDocument;
    if (!d || !d.head) return;
    const s = d.createElement("style");
    s.textContent = "header.top, footer, main > :not(.stage) { display: none !important } :root { --hh: 0px !important } .stage { height: 100dvh !important; min-height: 0 !important }";
    d.head.append(s);
    d.addEventListener("click", (e) => {
      const a = e.target.closest("a[href]");
      if (a && !a.target && !a.getAttribute("href").startsWith("#")) a.target = "_top";
    }, true);
    f.contentWindow.dispatchEvent(new Event("resize"));
    f.classList.add("ready");
  });
  document.addEventListener("tema", () => {
    const w = f.contentWindow, b = f.contentDocument && f.contentDocument.querySelector(".theme-btn");
    if (w && w.aguaDark && b && w.aguaDark() !== aguaDark()) b.click();
  });
  const note = document.querySelector(".mapnote[data-colonia]");
  if (note) fetch("/publicaciones.json").then((r) => (r.ok ? r.json() : null)).then((doc) => {
    if (!doc) return;
    const count = new Map();
    for (const p of doc.publicaciones) for (const k of p.colonias) count.set(k, (count.get(k) || 0) + 1);
    const n = count.get(note.dataset.colonia) || 0, most = Math.max(...count.values());
    const alone = [...count.values()].filter((v) => v === most).length === 1;
    if (n) note.firstChild.textContent = `${n} ${n === 1 ? "publicación" : "publicaciones"} de medios y vecinos sobre la falta de agua en Ciudad Granja, Zapopan${n === most && alone ? ": más que en ninguna otra colonia" : ""}.`;
  }).catch(() => {});
})();
</script>
"""


NAMES = {1: "Promesa contra realidad", 2: "Acciones primero", 3: "Alerta y cifras", 4: "Datos en vivo", 5: "Lo esencial"}

BAR_CSS = """
.variant-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 6px; margin: 0 -16px; padding: 6px 16px; background: #1c1400; color: #fde68a; font-size: .78rem }
.variant-bar strong { margin-right: 4px }
.variant-bar a { color: #fde68a; text-decoration: none; padding: 2px 8px; border-radius: 999px; border: 1px solid #fde68a55 }
.variant-bar a[aria-current="page"] { background: #fde68a; color: #1c1400; font-weight: 700 }
"""

# v1's newspaper look, shared: serif headlines, quotes and figures; the promise against what is
# happening set flat between rules in ink; neighbours' words marked by a red rule.
STYLE = """
:root { --serif: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif }
main h1, main h2, .v5-more > summary { font-family: var(--serif); font-weight: 700; letter-spacing: -.015em }
main h1 { line-height: 1.03 }
main .lede { color: var(--fg) }
.kicker { margin: 0 0 12px; font-family: var(--font); color: var(--alarm); font-size: .78rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase }
.vs-grid { gap: 0; border-top: 3px solid var(--fg); border-bottom: 1px solid var(--fg) }
.vs-col { background: none; border: 0; border-radius: 0; box-shadow: none; padding: 20px 0 }
.vs-col h3 { margin: 0 0 14px; color: var(--alarm); letter-spacing: .12em }
.promesa h3 { color: var(--muted) }
@media (min-width: 760px) { .vs-grid > :first-child { padding-right: 28px } .vs-grid > :last-child { border-left: 1px solid var(--line); padding-left: 28px } }
.promesa blockquote { font-family: var(--serif); font-style: italic; font-size: 1.22rem; line-height: 1.38; border: 0; padding: 0; margin: 0 0 16px }
.promesa blockquote mark { font-style: normal }
.vs-facts { grid-template-columns: 1fr; gap: 0; margin: 0 0 4px }
.vs-facts li { display: block; padding: 0 0 18px; margin: 0 0 18px; border-bottom: 1px solid var(--line) }
.vs-facts li:last-child { border: 0; margin: 0; padding: 0 }
.vs-facts strong { display: block; font-family: var(--serif); font-size: clamp(2.6rem, 9vw, 3.6rem); line-height: 1; letter-spacing: -.02em; margin: 0 0 6px }
.vs-facts span { font-size: .95rem; margin: 0 }
.realidad h4 { margin: 22px 0 10px; font-size: .78rem; letter-spacing: .12em; text-transform: uppercase; color: var(--alarm) }
.posts { display: block }
.posts li { margin: 0 0 12px; background: none; border: 0; border-left: 2px solid var(--alarm); border-radius: 0; padding: 2px 0 2px 14px }
.posts q { font-family: var(--serif); font-size: 1.08rem }
.maphero { margin: 4px 0 30px }
.mapframe-box { position: relative; height: min(78vh, 780px); min-height: 460px; border: 1px solid var(--fg); border-radius: 4px; overflow: hidden; background: var(--subtle) }
.mapframe-box::before { content: "Cargando el mapa…"; position: absolute; inset: 0; display: grid; place-items: center; color: var(--muted); font-size: .9rem }
.mapframe { position: relative; display: block; width: 100%; height: 100%; border: 0; opacity: 0; transition: opacity .3s }
.mapframe.ready { opacity: 1 }
.mapnote { margin: 8px 0 0; color: var(--muted); font-size: .88rem; line-height: 1.45 }
.mapnote a { white-space: nowrap; font-weight: 600 }
@media (max-width: 760px) { .mapframe-box { height: 72vh; min-height: 430px; margin: 0 -16px; border-radius: 0; border-inline: 0 } }
"""


def bar(n):
    current = ' aria-current="page"'
    links = ['<a href="/">Actual</a>'] + [
        f'<a href="/v{i}" title="{name}"{current if i == n else ""}>v{i}</a>' for i, name in NAMES.items()]
    return f'  <div class="variant-bar"><strong>Prueba · v{n}: {NAMES[n]}</strong>{"".join(links)}</div>\n'


def page(n, css, main, script=SCRIPT, after=""):
    head = re.sub(r"<title>.*?</title>", f'<title>Agua GDL · Variante {n}: {NAMES[n]}</title>\n<meta name="robots" content="noindex">', HEAD, count=1, flags=re.S)
    html = (head + BAR_CSS + STYLE + css + "</style>" + HEAD_END + "</head>\n<body>\n<div class=\"wrap\">\n" + bar(n) + HEADER
            + "\n  <main>\n" + main + "  </main>\n\n" + FOOTER + "</div>\n" + after + script + EMBED + "</body>\n</html>\n")
    (WEB / f"v{n}.html").write_text(html, encoding="utf-8")


# v1: what SIAPA promised against what is happening is the hero, set like a newspaper page.
page(1, """
.v1-hero { padding: 10px 0 16px }
.v1-hero h1 { font-size: clamp(1.9rem, 4.4vw, 2.9rem); max-width: 34ch; margin: 0 }
.v1-cols { margin: 0 0 8px }
.v1-cols .promesa { position: static }
@media (min-width: 760px) { .v1-cols { grid-template-columns: 1fr 1fr } }
.v1-act { margin: 0 0 8px; padding: 26px 0; border-top: 0 }
.v1-act h2 { font-size: clamp(1.6rem, 4.4vw, 2.2rem); margin: 0 0 10px }
.v1-wall { padding: 30px 0 36px; border-top: 3px solid var(--fg) }
.v1-wall h2 { font-size: 1.6rem; margin: 0 0 18px }
.v1-wall .cols { columns: 2 300px; column-gap: 28px }
.v1-wall h4 { break-after: avoid; margin: 0 0 10px; font-size: .78rem; letter-spacing: .12em; text-transform: uppercase; color: var(--alarm) }
.v1-wall .posts { margin: 0 0 18px }
.v1-wall .posts li { break-inside: avoid }
.v1-wall .note { color: var(--muted); font-size: .82rem; margin: 6px 0 0 }
.v1-boxes { display: grid; gap: 12px; margin: 0 0 40px }
@media (min-width: 860px) { .v1-boxes { grid-template-columns: repeat(3, 1fr) } }
""", f"""    <div class="v1-hero">
      <p class="kicker">{text(H1)}</p>
      <h1>{VS_TITLE}</h1>
    </div>
{map_hero(GRANJA)}    <div class="vs-grid v1-cols">
{PROMESA}
<div class="vs-col realidad">{REALIDAD_H3}{FACTS}</div>
    </div>
    <section class="v1-act" aria-labelledby="tuya">
      <h2 id="tuya">¿Y en tu colonia?</h2>
      {LEDE}
      {PULSE}
      {FORM}
    </section>
    <section class="v1-wall" aria-labelledby="dicen">
      <h2 id="dicen">Lo que se publica</h2>
      <div class="cols">{NEWS}{NEIGHBOURS}</div>
      {POSTS_NOTE}
      {VS_BUTTONS}
    </section>
    <div class="v1-boxes">{ALERTA}{EXIGE_BOX}{CONGRESO_BOX}</div>
{CONGRESO}{MAS}{WHY}{CONTACT}""")

# v2: the three things to do up top; on phones they stay in a bar at the bottom.
page(2, """
.v2-hero { padding: 10px 0 16px }
.v2-hero h1 { font-size: clamp(2rem, 5.4vw, 3.3rem); margin: 0 }
.v2-intro { max-width: 780px }
.v2-intro .pulse { margin-top: 12px }
.v2-actions { display: grid; gap: 12px; margin: 22px 0 22px }
@media (min-width: 900px) { .v2-actions { grid-template-columns: 1.35fr 1fr 1fr; align-items: stretch } }
.v2-report { background: var(--surface); border: 1px solid var(--line); border-top: 3px solid #e11d48; border-radius: 12px; box-shadow: var(--shadow); padding: 14px 16px }
.v2-report h2 { font-size: 1.3rem; margin: 0 0 10px }
.v2-report .ih .i-badge { width: 28px; height: 28px; background: #e11d48 }
.v2-report .quick { background: none; border: 0; box-shadow: none; padding: 0; margin: 0 }
.v2-report .quick label { font-weight: 500; color: var(--muted); font-size: .9rem }
.v2 .aviso { height: 100%; align-content: start; grid-template-columns: 1fr; gap: 8px }
.v2 .aviso .aviso-time, .v2 .aviso .aviso-text, .v2 .aviso .button { grid-column: 1; grid-row: auto }
.v2 .aviso[href="/exige"] { border-top-color: #d97706 }
.v2 .aviso[href="/escribe"] { border-top-color: #7c3aed }
.v2 .alerta { margin: 0 0 36px; padding: 14px 18px; font-size: 1rem }
.v2 .alerta .alerta-head { font-size: 1.1rem }
.v2-dock { position: fixed; left: 0; right: 0; bottom: 0; z-index: 20; display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; padding: 8px 12px calc(8px + env(safe-area-inset-bottom)); background: color-mix(in srgb, var(--bg) 90%, transparent); backdrop-filter: blur(10px); border-top: 1px solid var(--line) }
.v2-dock a { display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 7px 4px; border-radius: 10px; background: var(--surface); border: 1px solid var(--line); color: var(--fg); font-size: .8rem; font-weight: 600; text-decoration: none }
.v2-dock a:first-child { background: var(--primary); border-color: var(--primary); color: var(--on-primary) }
.v2-dock .i { width: 1.25em; height: 1.25em; color: inherit }
.v2-dock a:not(:first-child) .i { color: var(--ic) }
@media (min-width: 900px) { .v2-dock { display: none } }
@media (max-width: 899px) { body { padding-bottom: 72px } }
""", f"""    <div class="v2-hero">{H1}</div>
{map_hero()}    <div class="v2-intro">
      {LEDE}
      {PULSE}
    </div>
    <div class="v2 v2-actions">
      <div class="v2-report" id="reporta">
        <h2 class="ih"><span class="i-badge">{icon("map-pin")}</span>Reporta tu colonia</h2>
        {FORM}
      </div>
      {EXIGE_BOX}
      {CONGRESO_BOX}
    </div>
    <div class="v2">{ALERTA}</div>
{VS}{CONGRESO}{MAS}{WHY}{CONTACT}""", after=f"""<nav class="v2-dock" aria-label="Acciones">
  <a href="#reporta">{icon("map-pin")}Reportar</a>
  <a href="/exige">{icon("megaphone")}Exigir</a>
  <a href="/pipas">{icon("phone")}Pedir pipa</a>
</nav>
""")

# v3: the alarm first, the motto as a headline, neighbours' words rolling by, then the figures.
ticker = "".join(f"<li><b>«{q}»</b> {who}</li>" for q, who in POSTS)
page(3, """
.v3-alarm { padding: 16px 0 0 }
.v3-alarm .alerta { font-size: .95rem }
.v3-alarm .alerta .alerta-head { font-size: 1.05rem }
.v3-hero { padding: 18px 0 16px }
.v3-hero h1 { font-size: clamp(2.2rem, 6vw, 3.6rem); margin: 0 }
.v3-hero h1 .red { color: var(--alarm) }
.v3-intro { padding: 0 0 30px }
.v3-intro .quick { max-width: 640px }
.v3-ticker { overflow: hidden; border-top: 3px solid var(--fg); border-bottom: 1px solid var(--fg) }
.v3-ticker ul { display: flex; gap: 40px; width: max-content; margin: 0; padding: 12px 0; list-style: none; animation: v3-roll 120s linear infinite }
.v3-ticker li { white-space: nowrap; color: var(--muted); font-size: .88rem }
.v3-ticker li b { font-family: var(--serif); font-style: italic; font-weight: 400; font-size: 1.08rem; color: var(--fg) }
.v3-ticker:hover ul { animation-play-state: paused }
@keyframes v3-roll { to { transform: translateX(-50%) } }
@media (prefers-reduced-motion: reduce) { .v3-ticker { overflow-x: auto } .v3-ticker ul { animation: none } }
.v3-numbers { padding: 30px 0 36px; border-top: 0 }
.v3-numbers .vs-facts strong { font-size: clamp(3rem, 11vw, 4.8rem) }
@media (min-width: 760px) {
  .v3-numbers .vs-facts { grid-template-columns: repeat(3, 1fr) }
  .v3-numbers .vs-facts li { border: 0; margin: 0; padding: 0 22px; border-left: 1px solid var(--line) }
  .v3-numbers .vs-facts li:first-child { border-left: 0; padding-left: 0 }
}
.v3-calls { display: grid; gap: 12px; margin: 0 0 40px }
@media (min-width: 760px) { .v3-calls { grid-template-columns: 1fr 1fr } }
""", f"""    <div class="v3-alarm">{ALERTA}</div>
    <div class="v3-hero">{H1.replace("Exígelo.", '<span class="red">Exígelo.</span>')}</div>
{map_hero(GRANJA)}    <div class="v3-intro">
      {LEDE}
      {FORM}
      {PULSE}
    </div>
    <div class="v3-ticker" aria-hidden="true"><ul>{ticker}{ticker}</ul></div>
    <section class="v3-numbers" aria-labelledby="cifras">
      <h2 class="kicker" id="cifras">En números</h2>
      {FACTS}
    </section>
{vs(facts=False)}    <div class="v3-calls">{EXIGE_BOX}{CONGRESO_BOX}</div>
{CONGRESO}{MAS}{WHY}{CONTACT}""")

# v4: the numbers lead, live: this map's last day and what outlets and neighbours publish.
V4_SCRIPT = SCRIPT.split("  // What neighbours reported", 1)[0] + r"""  const fmt = (n) => n.toLocaleString("es-MX");
  const show = (id, value, label) => {
    const t = document.getElementById(id);
    t.querySelector("b").textContent = value;
    t.querySelector("span").textContent = label;
    t.hidden = false;
  };
  fetch(API + "/v1/reportes").then((r) => (r.ok ? r.json() : null)).then((s) => {
    if (!s || !s.total) return;
    show("t-total", fmt(s.total), `${s.total === 1 ? "reporte llegó" : "reportes llegaron"} a este mapa en las últimas 24 horas, de ${fmt(s.colonias_con_reportes)} ${s.colonias_con_reportes === 1 ? "colonia" : "colonias"}`);
    show("t-sin", `${Math.round(100 * s.sin_agua / s.total)} %`, "de esos reportes dicen que no hay agua");
  }).catch(() => {});
  // The same counts as /reportes: each colonia's most days, from what outlets and neighbours publish.
  const SMALL = new Set(["de", "del", "la", "las", "los", "el", "y", "e"]);
  const nice = (name) => name.toLowerCase().split(" ").map((w, i) => /^(i{1,3}|iv|vi{0,3}|ix|x)$/.test(w) ? w.toUpperCase() : i && SMALL.has(w) ? w : w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  fetch("/publicaciones.json").then((r) => (r.ok ? r.json() : null)).then((doc) => {
    if (!doc) throw new Error("no publications");
    const days = new Map(), latest = new Map(), count = new Map();
    for (const p of doc.publicaciones) for (const k of p.colonias) {
      if (p.dias != null) days.set(k, Math.max(days.get(k) || 0, p.dias));
      if (!latest.has(k) || p.fecha > latest.get(k)) latest.set(k, p.fecha);
      count.set(k, (count.get(k) || 0) + 1);
    }
    const week = [...days.values()].filter((d) => d >= 7).length;
    show("t-semana", fmt(week), `${week === 1 ? "colonia lleva" : "colonias llevan"} una semana o más sin agua, según medios y vecinos`);
    const news = Math.max(0, ...doc.publicaciones.filter((p) => p.fuente === "medio" && p.dias).map((p) => p.dias));
    if (news) show("t-medio", `${news} ${news === 1 ? "día" : "días"}`, "es lo más largo sin agua que reporta un medio");
    const top = [...days].sort((a, b) => b[1] - a[1] || count.get(b[0]) - count.get(a[0]) || latest.get(b[0]).localeCompare(latest.get(a[0]))).slice(0, 6);
    const list = document.getElementById("top");
    list.replaceChildren(...top.map(([k, d]) => {
      const [n, m, cp] = k.split("|");
      const a = document.createElement("a");
      a.href = "/reportes?" + new URLSearchParams({ q: n, m, cp });
      const name = document.createElement("strong"), where = document.createElement("small"), badge = document.createElement("span");
      name.textContent = nice(n);
      where.textContent = m;
      badge.textContent = `${d} ${d === 1 ? "día" : "días"}`;
      a.append(badge, name, where);
      const li = document.createElement("li");
      li.append(a);
      return li;
    }));
    document.getElementById("top-sec").hidden = !top.length;
  }).catch(() => { document.getElementById("t-semana").hidden = true; });
})();
</script>
"""
page(4, """
.v4-title { padding: 10px 0 16px }
.v4-title h1 { font-size: clamp(2rem, 5.4vw, 3.3rem); margin: 0 }
.v4-hero { display: grid; gap: 22px; padding: 0 0 30px }
@media (min-width: 860px) { .v4-hero { grid-template-columns: 1fr 1.05fr; align-items: center; gap: 36px } }
.v4-board { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); margin: 0; border-top: 3px solid var(--fg); border-bottom: 1px solid var(--fg) }
.v4-tile { margin: 0; padding: 14px 10px 14px 0 }
.v4-tile b { display: block; font-family: var(--serif); font-size: clamp(1.7rem, 5.6vw, 2.4rem); font-weight: 700; letter-spacing: -.02em; line-height: 1.05; font-variant-numeric: tabular-nums }
.v4-tile span { display: block; margin-top: 6px; color: var(--muted); font-size: .82rem; line-height: 1.35 }
.v4-tile:not(.wide) + .v4-tile { border-left: 1px solid var(--line); padding-left: 14px }
.v4-tile.wide { grid-column: 1 / -1; padding: 16px 0 18px; border-bottom: 1px solid var(--line) }
.v4-tile.wide b { color: var(--alarm); font-size: clamp(3.2rem, 12vw, 4.8rem); line-height: 1 }
.v4-tile.wide span { color: var(--fg); font-size: 1rem }
.v4-top { padding: 30px 0 34px }
.v4-top h2 { margin: 0 0 6px }
.v4-top > p { margin: 0 0 16px; color: var(--muted); font-size: .9rem }
.v4-list { list-style: none; margin: 0 0 14px; padding: 0; columns: 2 300px; column-gap: 32px; border-top: 3px solid var(--fg) }
.v4-list li { break-inside: avoid; border-bottom: 1px solid var(--line) }
.v4-list a { display: grid; grid-template-columns: 1fr auto; column-gap: 12px; align-items: baseline; padding: 10px 0; color: var(--fg); text-decoration: none }
.v4-list a:hover strong { text-decoration: underline; text-underline-offset: 3px }
.v4-list strong { grid-column: 1; grid-row: 1; font-family: var(--serif); font-size: 1.15rem; line-height: 1.25 }
.v4-list small { grid-column: 1; grid-row: 2; color: var(--muted); font-size: .8rem }
.v4-list span { grid-column: 2; grid-row: 1 / span 2; align-self: center; font-family: var(--serif); font-size: 1.3rem; font-weight: 700; color: var(--alarm); white-space: nowrap }
.v4-report { padding: 30px 0 }
.v4-report h2 { margin: 0 }
.v4-report .quick { margin-top: 14px }
.v4-row { display: grid; gap: 12px; margin: 0 0 40px }
@media (min-width: 860px) { .v4-row { grid-template-columns: repeat(3, 1fr) } }
""", f"""    <div class="v4-title">{H1}</div>
{map_hero()}    <div class="v4-hero">
      <div>
        {LEDE}
      </div>
      <div class="v4-board" aria-live="polite">
        <p class="v4-tile wide" id="t-semana"><b>…</b><span>colonias llevan una semana o más sin agua, según medios y vecinos</span></p>
        <p class="v4-tile" id="t-medio" hidden><b></b><span></span></p>
        <p class="v4-tile" id="t-total" hidden><b></b><span></span></p>
        <p class="v4-tile" id="t-sin" hidden><b></b><span></span></p>
      </div>
    </div>
    <section class="v4-top" id="top-sec" aria-labelledby="top-h" hidden>
      <h2 id="top-h">Donde más días llevan sin agua</h2>
      <p>Según lo que publican medios y vecinos. Cada colonia tiene sus fuentes en <a href="/reportes">el mapa</a>.</p>
      <ol class="v4-list" id="top"></ol>
    </section>
    <section class="v4-report" aria-labelledby="tuya">
      <h2 id="tuya">¿Y en tu colonia?</h2>
      {FORM}
    </section>
    <div class="v4-row">{ALERTA}{EXIGE_BOX}{CONGRESO_BOX}</div>
{VS}{CONGRESO}{MAS}{WHY}{CONTACT}""", script=V4_SCRIPT)

# v5: one narrow column: the search, two boxes, and the rest folded until it's wanted.
folded = "".join(f'    <details class="v5-more"><summary>{title}</summary><div>{body}</div></details>\n'
                 for title, body in [(VS_TITLE, f'<div class="vs-grid">{PROMESA}{realidad()}</div>{VS_BUTTONS}'), split(CONGRESO), split(MAS), split(WHY)])
page(5, """
.v5 { max-width: 680px; margin: 0 auto }
.v5-hero { padding: 10px 0 16px }
.v5-hero h1 { font-size: clamp(2rem, 5.4vw, 3.3rem); margin: 0 }
.v5-intro { padding: 0 0 4px }
.v5 .quick input { font-size: 1.05rem; padding: 12px 14px }
.v5 .pulse { font-weight: 500 }
.v5-boxes { display: grid; gap: 10px; margin: 8px 0 14px }
.v5 .alerta { margin: 0 0 26px }
.v5-more { border-top: 1px solid var(--line) }
.v5-more:first-of-type { border-top: 3px solid var(--fg) }
.v5-more:last-of-type { border-bottom: 1px solid var(--fg); margin-bottom: 8px }
.v5-more > summary { display: flex; justify-content: space-between; align-items: center; gap: 14px; padding: 18px 0; cursor: pointer; list-style: none; font-size: 1.35rem; line-height: 1.25 }
.v5-more > summary::-webkit-details-marker { display: none }
.v5-more > summary::after { content: "+"; flex-shrink: 0; font-family: var(--serif); font-size: 1.8rem; font-weight: 400; line-height: 1; color: var(--alarm) }
.v5-more[open] > summary::after { content: "−" }
.v5-more > div { padding: 0 0 26px }
.v5-more .vs-grid { grid-template-columns: 1fr }
.v5-more .vs-grid > :last-child { border-left: 0; padding-left: 0; border-top: 1px solid var(--line) }
.v5-more .vs-grid > :first-child { padding-right: 0 }
.v5-more .promesa { position: static }
.v5 .contact { border-top: 0 }
""", f"""    <div class="v5 v5-hero">{H1}</div>
{map_hero(GRANJA)}    <div class="v5">
    <div class="v5-intro">
      {LEDE}
      {FORM}
      {PULSE}
    </div>
    <div class="v5-boxes">{EXIGE_BOX}{CONGRESO_BOX}</div>
    {ALERTA}
{folded}{CONTACT}    </div>
""")

print(f"wrote {', '.join(f'web/v{n}.html' for n in NAMES)} from web/index.html")
