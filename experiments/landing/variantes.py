#!/usr/bin/env python3
"""Variants of the landing page, to compare ordering, placement and style: writes web/v1.html …
web/v5.html (noindex, with a bar to switch between them and the current landing) from the
pieces of web/index.html, so each carries its copy, quotes and sources as they are. Change a
variant here and run it again; a piece index.html no longer has stops it.

Usage, from the repo root: python3 -I experiments/landing/variantes.py
"""
import re
from pathlib import Path

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


NAMES = {1: "Promesa contra realidad", 2: "Acciones primero", 3: "Cartel", 4: "Datos en vivo", 5: "Lo esencial"}

BAR_CSS = """
.variant-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 6px; margin: 0 -16px; padding: 6px 16px; background: #1c1400; color: #fde68a; font-size: .78rem }
.variant-bar strong { margin-right: 4px }
.variant-bar a { color: #fde68a; text-decoration: none; padding: 2px 8px; border-radius: 999px; border: 1px solid #fde68a55 }
.variant-bar a[aria-current="page"] { background: #fde68a; color: #1c1400; font-weight: 700 }
"""


def bar(n):
    current = ' aria-current="page"'
    links = ['<a href="/">Actual</a>'] + [
        f'<a href="/v{i}" title="{name}"{current if i == n else ""}>v{i}</a>' for i, name in NAMES.items()]
    return f'  <div class="variant-bar"><strong>Prueba · v{n}: {NAMES[n]}</strong>{"".join(links)}</div>\n'


def page(n, css, main, script=SCRIPT, after=""):
    head = re.sub(r"<title>.*?</title>", f'<title>Agua GDL · Variante {n}: {NAMES[n]}</title>\n<meta name="robots" content="noindex">', HEAD, count=1, flags=re.S)
    html = (head + BAR_CSS + css + "</style>" + HEAD_END + "</head>\n<body>\n<div class=\"wrap\">\n" + bar(n) + HEADER
            + "\n  <main>\n" + main + "  </main>\n\n" + FOOTER + "</div>\n" + after + script + "</body>\n</html>\n")
    (WEB / f"v{n}.html").write_text(html, encoding="utf-8")


# v1: what SIAPA promised against what is happening is the hero, set like a newspaper page.
page(1, """
.v1 { --serif: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif }
.v1-hero { padding: 14px 0 34px }
.kicker { margin: 0 0 12px; color: var(--alarm); font-size: .78rem; font-weight: 700; letter-spacing: .14em; text-transform: uppercase }
.v1 h1 { font-family: var(--serif); font-size: clamp(2.2rem, 6.6vw, 4rem); line-height: 1.03; letter-spacing: -.015em; max-width: 21ch; margin: 0 0 26px }
.v1-cols { display: grid; border-top: 3px solid var(--fg); border-bottom: 1px solid var(--fg) }
.v1 .vs-col { background: none; border: 0; border-radius: 0; box-shadow: none; padding: 20px 0; position: static }
.v1 .vs-col h3 { margin: 0 0 14px; color: var(--alarm); letter-spacing: .12em }
.v1 .promesa h3 { color: var(--muted) }
.v1 .promesa blockquote { font-family: var(--serif); font-style: italic; font-size: 1.22rem; line-height: 1.38; border: 0; padding: 0; margin: 0 0 16px }
.v1 .promesa blockquote mark { font-style: normal }
.v1 .vs-facts { grid-template-columns: 1fr; gap: 0; margin: 0 }
.v1 .vs-facts li { display: block; padding: 0 0 18px; margin: 0 0 18px; border-bottom: 1px solid var(--line) }
.v1 .vs-facts li:last-child { border: 0; margin: 0; padding: 0 }
.v1 .vs-facts strong { display: block; font-family: var(--serif); font-size: clamp(2.6rem, 9vw, 3.6rem); line-height: 1; letter-spacing: -.02em; margin: 0 0 6px }
.v1 .vs-facts span { font-size: .95rem }
@media (min-width: 760px) { .v1-cols { grid-template-columns: 1fr 1fr } .v1-cols > :first-child { padding-right: 28px } .v1-cols > :last-child { border-left: 1px solid var(--line); padding-left: 28px } }
.v1-act { margin: 0 0 8px; padding: 26px 0; border-top: 0 }
.v1-act h2 { font-family: var(--serif); font-size: clamp(1.6rem, 4.4vw, 2.2rem); margin: 0 0 10px }
.v1-act .lede { color: var(--fg) }
.v1-wall { padding: 30px 0 36px; border-top: 3px solid var(--fg) }
.v1-wall h2 { font-family: var(--serif); font-size: 1.6rem; margin: 0 0 18px }
.v1-wall .cols { columns: 2 300px; column-gap: 28px }
.v1-wall h4 { break-after: avoid; margin: 0 0 10px; font-size: .78rem; letter-spacing: .12em; text-transform: uppercase; color: var(--alarm) }
.v1-wall .posts { display: block; margin: 0 0 18px }
.v1-wall .posts li { break-inside: avoid; margin: 0 0 12px; background: none; border: 0; border-left: 2px solid var(--alarm); border-radius: 0; padding: 2px 0 2px 14px }
.v1-wall .posts q { font-family: var(--serif); font-size: 1.08rem }
.v1-wall .note { color: var(--muted); font-size: .82rem; margin: 6px 0 0 }
.v1-boxes { display: grid; gap: 12px; margin: 0 0 40px }
@media (min-width: 860px) { .v1-boxes { grid-template-columns: repeat(3, 1fr) } }
.v1 .congreso h2, .v1 section > h2 { font-family: var(--serif) }
""", f"""    <div class="v1 v1-hero">
      <p class="kicker">{text(H1)}</p>
      <h1>{VS_TITLE}</h1>
      <div class="v1-cols">
{PROMESA}
<div class="vs-col realidad">{REALIDAD_H3}{FACTS}</div>
      </div>
    </div>
    <section class="v1 v1-act" aria-labelledby="tuya">
      <h2 id="tuya">¿Y en tu colonia?</h2>
      {LEDE}
      {PULSE}
      {FORM}
    </section>
    <section class="v1 v1-wall" aria-labelledby="dicen">
      <h2 id="dicen">Lo que se publica</h2>
      <div class="cols">{NEWS}{NEIGHBOURS}</div>
      {POSTS_NOTE}
      {VS_BUTTONS}
    </section>
    <div class="v1 v1-boxes">{ALERTA}{EXIGE_BOX}{CONGRESO_BOX}</div>
    <div class="v1">
{CONGRESO}{MAS}{WHY}{CONTACT}    </div>
""")

# v2: the three things to do up top; on phones they stay in a bar at the bottom.
page(2, """
.v2-hero { padding: 16px 0 6px; max-width: 780px }
.v2-hero .pulse { margin-top: 12px }
.v2-actions { display: grid; gap: 12px; margin: 22px 0 22px }
@media (min-width: 900px) { .v2-actions { grid-template-columns: 1.35fr 1fr 1fr; align-items: stretch } }
.v2-report { background: var(--surface); border: 1px solid var(--line); border-top: 3px solid #e11d48; border-radius: 12px; box-shadow: var(--shadow); padding: 14px 16px }
.v2-report h2 { font-size: 1.1rem; margin: 0 0 10px }
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
""", f"""    <div class="v2 v2-hero">
      {H1}
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

# v3: a protest poster: the alarm on top, a dark hero with the motto, neighbours' words rolling by.
ticker = "".join(f"<li><b>«{q}»</b> {who}</li>" for q, who in POSTS)
page(3, """
.v3-alarm { margin: 0 0 0; }
.v3-alarm .alerta { margin: 0 -16px; border: 0; border-radius: 0; padding: 12px 16px; background: #b91c1c; color: #fff; box-shadow: 0 0 0 100vmax #b91c1c; clip-path: inset(0 -100vmax); font-size: .95rem }
.v3-alarm .alerta .alerta-head { color: #fff; font-size: 1.05rem }
.v3-alarm .alerta-i { background: #fff; color: #b91c1c }
.v3-alarm .alerta a { color: #fff }
.v3-poster { background: #0b1220; color: #f8fafc; box-shadow: 0 0 0 100vmax #0b1220; clip-path: inset(0 -100vmax); padding: 40px 0 38px }
.v3-poster h1 { font-size: clamp(2.7rem, 11.5vw, 6.2rem); line-height: .93; font-weight: 900; text-transform: uppercase; letter-spacing: -.04em; max-width: 11ch; margin: 0 0 24px }
.v3-poster h1 mark { background: #fcd34d; color: #1c1400; font-weight: 900; padding: 0 .1em; border-radius: 6px }
.v3-poster .lede { color: #cbd5e1; font-size: 1.12rem; max-width: 58ch }
.v3-poster .lede a { color: #7dd3fc }
.v3-poster .pulse { color: #e2e8f0 }
.v3-poster .quick { background: #111a2e; border-color: #22314d; border-top-color: #fcd34d; box-shadow: none; max-width: 640px }
.v3-poster .quick label { color: #f8fafc }
.v3-poster .quick .or { color: #94a3b8 }
.v3-poster .quick .or a { color: #7dd3fc }
.v3-ticker { overflow: hidden; margin: 0 -16px; border-bottom: 2px solid var(--fg); background: var(--surface) }
.v3-ticker ul { display: flex; gap: 40px; width: max-content; margin: 0; padding: 13px 16px; list-style: none; animation: v3-roll 120s linear infinite }
.v3-ticker li { white-space: nowrap; color: var(--muted); font-size: .92rem }
.v3-ticker li b { color: var(--fg); font-weight: 600 }
.v3-ticker:hover ul { animation-play-state: paused }
@keyframes v3-roll { to { transform: translateX(-50%) } }
@media (prefers-reduced-motion: reduce) { .v3-ticker { overflow-x: auto } .v3-ticker ul { animation: none } }
.v3-numbers { padding: 36px 0 40px; border-top: 0 }
.v3-numbers h2 { font-size: 1rem; text-transform: uppercase; letter-spacing: .12em; color: var(--muted); margin: 0 0 18px }
.v3-numbers .vs-facts { grid-template-columns: 1fr; gap: 26px; margin: 0 }
.v3-numbers .vs-facts li { display: block }
.v3-numbers .vs-facts strong { display: block; font-size: clamp(3.2rem, 13vw, 5.6rem); font-weight: 900; letter-spacing: -.05em; line-height: .9; margin: 0 0 8px }
.v3-numbers .vs-facts span { font-size: 1rem; color: var(--fg) }
@media (min-width: 760px) { .v3-numbers .vs-facts { grid-template-columns: repeat(3, 1fr); gap: 32px } }
.v3 .vs h2 { font-size: clamp(1.8rem, 5vw, 2.8rem); font-weight: 900; text-transform: uppercase; letter-spacing: -.03em; line-height: 1 }
.v3 .promesa blockquote { font-size: 1.15rem; font-weight: 600 }
.v3-calls { display: grid; gap: 12px; margin: 0 0 40px }
@media (min-width: 760px) { .v3-calls { grid-template-columns: 1fr 1fr } }
""", f"""    <div class="v3-alarm">{ALERTA}</div>
    <div class="v3-poster">
      {H1.replace("Exígelo.", "<mark>Exígelo.</mark>")}
      {LEDE}
      {FORM}
      {PULSE}
    </div>
    <div class="v3-ticker" aria-hidden="true"><ul>{ticker}{ticker}</ul></div>
    <section class="v3-numbers" aria-labelledby="cifras">
      <h2 id="cifras">En números</h2>
      {FACTS}
    </section>
    <div class="v3">
{vs(facts=False)}    </div>
    <div class="v3-calls">{EXIGE_BOX}{CONGRESO_BOX}</div>
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
.v4-hero { display: grid; gap: 22px; padding: 16px 0 30px }
@media (min-width: 860px) { .v4-hero { grid-template-columns: 1fr 1.05fr; align-items: center; gap: 36px } }
.v4-board { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; margin: 0 }
.v4-tile { margin: 0; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 14px 16px; box-shadow: var(--shadow) }
.v4-tile b { display: block; font-size: clamp(1.8rem, 6.2vw, 2.5rem); font-weight: 700; letter-spacing: -.035em; line-height: 1.05; font-variant-numeric: tabular-nums }
.v4-tile span { display: block; margin-top: 4px; color: var(--muted); font-size: .85rem; line-height: 1.35 }
.v4-tile.wide { grid-column: 1 / -1; background: color-mix(in srgb, var(--alarm) 8%, var(--surface)); border-color: color-mix(in srgb, var(--alarm) 30%, var(--line)); border-top: 3px solid var(--alarm) }
.v4-tile.wide b { color: var(--alarm); font-size: clamp(2.6rem, 9vw, 3.6rem) }
.v4-tile.wide span { color: var(--fg); font-size: .98rem }
.v4-board > :last-child:nth-child(even) { grid-column: 1 / -1 }
.v4-top { padding: 30px 0 34px }
.v4-top h2 { margin: 0 0 6px }
.v4-top > p { margin: 0 0 16px; color: var(--muted); font-size: .9rem }
.v4-list { list-style: none; margin: 0 0 14px; padding: 0; display: grid; gap: 8px; grid-template-columns: repeat(auto-fill, minmax(min(100%, 260px), 1fr)) }
.v4-list a { display: grid; grid-template-columns: auto 1fr; grid-template-rows: auto auto; column-gap: 12px; align-items: center; padding: 10px 12px; background: var(--surface); border: 1px solid var(--line); border-radius: 10px; color: var(--fg); text-decoration: none; box-shadow: var(--shadow) }
.v4-list a:hover { border-color: var(--alarm) }
.v4-list span { grid-row: 1 / span 2; min-width: 4.4em; padding: 6px 8px; border-radius: 999px; background: var(--alarm); color: #fff; font-weight: 700; font-size: .85rem; text-align: center; white-space: nowrap }
@media (prefers-color-scheme: dark) { .v4-list span { color: #2d0b10 } }
.v4-list strong { font-size: .98rem; line-height: 1.25 }
.v4-list small { color: var(--muted); font-size: .8rem }
.v4-report { padding: 30px 0 }
.v4-report h2 { margin: 0 }
.v4-report .quick { margin-top: 14px }
.v4-row { display: grid; gap: 12px; margin: 0 0 40px }
@media (min-width: 860px) { .v4-row { grid-template-columns: repeat(3, 1fr) } }
""", f"""    <div class="v4-hero">
      <div>
        {H1}
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
.v5-hero { padding: 30px 0 18px }
.v5-hero h1 { font-size: clamp(2.4rem, 8.5vw, 3.6rem); margin: 0 0 14px }
.v5 .quick { background: none; border: 0; box-shadow: none; padding: 0; margin: 22px 0 0 }
.v5 .quick label { font-size: 1.05rem }
.v5 .quick input { font-size: 1.1rem; padding: 13px 14px }
.v5 .quick .button { padding: 13px 20px; font-size: 1rem }
.v5 .pulse { font-weight: 500; color: var(--muted) }
.v5 .pulse b { color: var(--fg) }
.v5-boxes { display: grid; gap: 10px; margin: 8px 0 14px }
.v5 .alerta { margin: 0 0 26px }
.v5-more { border-top: 1px solid var(--line) }
.v5-more:last-of-type { border-bottom: 1px solid var(--line); margin-bottom: 8px }
.v5-more > summary { display: flex; justify-content: space-between; align-items: center; gap: 14px; padding: 18px 0; cursor: pointer; list-style: none; font-size: 1.15rem; font-weight: 600; line-height: 1.3 }
.v5-more > summary::-webkit-details-marker { display: none }
.v5-more > summary::after { content: "+"; flex-shrink: 0; display: grid; place-items: center; width: 30px; height: 30px; border-radius: 50%; background: var(--subtle); color: var(--link); font-size: 1.2rem; font-weight: 600 }
.v5-more[open] > summary::after { content: "−" }
.v5-more > div { padding: 0 0 26px }
.v5-more .vs-grid { grid-template-columns: 1fr }
.v5-more .promesa { position: static }
.v5 .contact { border-top: 0 }
""", f"""    <div class="v5">
    <div class="v5-hero">
      {H1}
      {LEDE}
      {FORM}
      {PULSE}
    </div>
    <div class="v5-boxes">{EXIGE_BOX}{CONGRESO_BOX}</div>
    {ALERTA}
{folded}{CONTACT}    </div>
""")

print(f"wrote {', '.join(f'web/v{n}.html' for n in NAMES)} from web/index.html")
