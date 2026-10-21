#!/usr/bin/env python3
"""Variants of the landing page, to compare one idea at a time against it: writes web/v6.html …
web/v10.html (noindex, with a bar to switch between them and the current landing) from the blocks
of web/index.html, so each carries the landing's copy, quotes, sources, style and scripts and only
moves, widens, folds or wires them differently. The landing is the 21 Oct 2026 round's v1; that
round's generator and pages are in git history (web/v1.html … v5.html, now redirected to /).
Change a variant here and run it again; a block index.html no longer has stops it.

Usage, from the repo root: python3 -I experiments/landing/variantes.py
"""
import re
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
WEB = ROOT / "web"
SRC = (WEB / "index.html").read_text(encoding="utf-8")
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}


class Blocks(HTMLParser):
    """The direct children of <main>, as written, keyed by their class (else aria-labelledby)."""

    def __init__(self, src):
        super().__init__(convert_charrefs=False)
        self.src, self.depth, self.found = src, None, {}
        self.starts = [0]
        for line in src.splitlines(keepends=True):
            self.starts.append(self.starts[-1] + len(line))
        self.feed(src)

    def here(self):
        line, col = self.getpos()
        return self.starts[line - 1] + col

    def handle_starttag(self, tag, attrs):
        if tag == "main" and self.depth is None:
            self.depth = 0
        elif self.depth is not None and tag not in VOID:
            if self.depth == 0:
                a = dict(attrs)
                self.key, self.start = a.get("class") or a.get("aria-labelledby"), self.here()
            self.depth += 1

    def handle_endtag(self, tag):
        if self.depth is None or tag in VOID:
            return
        if self.depth == 0:  # </main>
            self.depth = None
            return
        self.depth -= 1
        if self.depth == 0:
            self.found[self.key] = "    " + self.src[self.start:self.here() + len(f"</{tag}>")] + "\n"


def grab(pattern, text=SRC):
    m = re.search(pattern, text, re.S)
    if not m:
        raise SystemExit(f"web/index.html has no {pattern[:70]!r}: update variantes.py")
    return m.group(0)


def text(markup):
    return " ".join(re.sub(r"<[^>]+>", "", markup).split())


def split(section):
    """A section's heading text and what follows the heading."""
    m = re.match(r"\s*<section[^>]*>\s*<h2[^>]*>(.*?)</h2>(.*)</section>\s*$", section, re.S)
    return text(m.group(1)), m.group(2)


B = Blocks(SRC).found
try:
    HEADLINE, MAP, CONTRAST, YOURS, WALL, BOXES = (B[k] for k in ("headline", "maphero", "vs-grid contrast", "yours", "wall", "boxes"))
    CONGRESO, MAS, WHY, CONTACT = (B[k] for k in ("congreso", "mas", "why", "contact"))
except KeyError as e:
    raise SystemExit(f"web/index.html's <main> has no block {e}: update variantes.py")
HEAD, AFTER_STYLE = SRC.split("</style>", 1)
HEAD_END = AFTER_STYLE.split("</head>", 1)[0]
HEADER = grab(r'  <header class="top">.*?</header>\n')
FOOTER = grab(r"  <footer>.*?</footer>\n")
SCRIPTS = re.search(r"</footer>\n</div>\n(<script>.*)</body>", SRC, re.S).group(1)
V = re.search(r"/icons\.svg\?v=(\d+)", SRC).group(1)


NAMES = {6: "Mapa a lo ancho", 7: "Portada", 8: "Mapa con lista", 9: "Tu colonia primero", 10: "Breve"}

BAR_CSS = """
.variant-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 6px; margin: 0 -16px; padding: 6px 16px; background: #1c1400; color: #fde68a; font-size: .78rem }
.variant-bar strong { margin-right: 4px }
.variant-bar a { color: #fde68a; text-decoration: none; padding: 2px 8px; border-radius: 999px; border: 1px solid #fde68a55 }
.variant-bar a[aria-current="page"] { background: #fde68a; color: #1c1400; font-weight: 700 }
"""

FOLDS_CSS = """
.fold { border-top: 1px solid var(--line) }
.fold:first-of-type { border-top: 3px solid var(--fg) }
.fold:last-of-type { border-bottom: 1px solid var(--fg); margin-bottom: 8px }
.fold > summary { display: flex; justify-content: space-between; align-items: center; gap: 14px; padding: 18px 0; cursor: pointer; list-style: none; font-family: var(--serif); font-size: 1.35rem; font-weight: 700; line-height: 1.25 }
.fold > summary::-webkit-details-marker { display: none }
.fold > summary::after { content: "+"; flex-shrink: 0; font-family: var(--serif); font-size: 1.8rem; font-weight: 400; line-height: 1; color: var(--alarm) }
.fold[open] > summary::after { content: "−" }
.fold > div { padding: 0 0 26px }
"""


def bar(n):
    current = ' aria-current="page"'
    links = ['<a href="/">Actual</a>'] + [
        f'<a href="/v{i}" title="{name}"{current if i == n else ""}>v{i}</a>' for i, name in NAMES.items()]
    return f'  <div class="variant-bar"><strong>Prueba · v{n}: {NAMES[n]}</strong>{"".join(links)}</div>\n'


def page(n, css, main, script=""):
    head = re.sub(r"<title>.*?</title>", f'<title>Agua GDL · Variante {n}: {NAMES[n]}</title>\n<meta name="robots" content="noindex">', HEAD, count=1, flags=re.S)
    out = (head + BAR_CSS + css + "</style>" + HEAD_END + "</head>\n<body>\n<div class=\"wrap\">\n" + bar(n) + HEADER
           + "\n  <main>\n" + main + "  </main>\n\n" + FOOTER + "</div>\n" + SCRIPTS + script + "</body>\n</html>\n")
    (WEB / f"v{n}.html").write_text(out, encoding="utf-8")


# v6: the map edge to edge and taller; the rest as on the landing.
page(6, """
html, body { overflow-x: clip }
.maphero .mapframe-box { width: 100vw; margin-left: calc(50% - 50vw); margin-right: 0; height: min(88vh, 920px); border-inline: 0; border-radius: 0 }
@media (max-width: 760px) { .maphero .mapframe-box { height: 80vh } }
""", HEADLINE + MAP + CONTRAST + YOURS + WALL + BOXES + CONGRESO + MAS + WHY + CONTACT)

# v7: a front page on wide screens: the headline and the promise against the figures on the left,
# the map on the right; phones keep the landing's order.
page(7, """
@media (min-width: 1100px) {
  .wrap { max-width: 1320px }
  main > :not(.frontpage) { max-width: 928px; margin-left: auto; margin-right: auto }
  .frontpage { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1.55fr); grid-template-areas: "head map" "contrast map"; column-gap: 32px; align-items: start; margin: 0 0 30px }
  .frontpage > .headline { grid-area: head }
  .frontpage > .maphero { grid-area: map; margin: 14px 0 0 }
  .frontpage > .contrast { grid-area: contrast; grid-template-columns: 1fr; margin: 0 }
  .frontpage .contrast > :first-child { padding-right: 0 }
  .frontpage .contrast > :last-child { border-left: 0; padding-left: 0; border-top: 1px solid var(--line) }
  .frontpage .mapframe-box { height: min(calc(100vh - 120px), 900px); min-height: 600px }
  .frontpage .headline h1 { font-size: clamp(2.2rem, 3.4vw, 3rem) }
}
""", '    <div class="frontpage">\n' + HEADLINE + MAP + CONTRAST + "    </div>\n" + YOURS + WALL + BOXES + CONGRESO + MAS + WHY + CONTACT)

# v8: under the map, the colonias with the most publications; a tap shows one in the map.
page(8, """
.hot { padding: 0 0 30px; border-top: 0 }
.hot h2 { font-size: 1.4rem; margin: 0 0 4px }
.hot > p { margin: 0 0 12px; color: var(--muted); font-size: .9rem }
.hot-list { list-style: none; margin: 0; padding: 0; columns: 2 280px; column-gap: 28px; border-top: 3px solid var(--fg) }
.hot-list li { break-inside: avoid; border-bottom: 1px solid var(--line) }
.hot-list button { display: grid; grid-template-columns: 1fr auto; column-gap: 12px; align-items: center; width: 100%; padding: 10px 0 10px 10px; border: 0; border-left: 3px solid transparent; background: none; color: var(--fg); font: inherit; text-align: left; cursor: pointer }
.hot-list button:hover strong { text-decoration: underline; text-underline-offset: 3px }
.hot-list button[aria-pressed="true"] { border-left-color: var(--alarm); background: color-mix(in srgb, var(--alarm) 7%, transparent) }
.hot-list strong { grid-column: 1; font-family: var(--serif); font-size: 1.12rem; line-height: 1.25 }
.hot-list small { grid-column: 1; color: var(--muted); font-size: .8rem }
.hot-list span { grid-column: 2; grid-row: 1 / span 2; color: var(--alarm); font-family: var(--serif); font-weight: 700; font-size: 1.05rem; white-space: nowrap }
""", HEADLINE + MAP + """    <section class="hot" aria-labelledby="hot-h" hidden>
      <h2 id="hot-h">Las colonias con más publicaciones</h2>
      <p>Según lo que publican medios y vecinos. Toca una para verla en el mapa.</p>
      <ol class="hot-list" id="hot"></ol>
    </section>
""" + CONTRAST + YOURS + WALL + BOXES + CONGRESO + MAS + WHY + CONTACT, script=r"""<script>
(() => {
  const f = document.querySelector(".mapframe"), note = document.querySelector(".mapnote"), list = document.getElementById("hot");
  const api = new URLSearchParams(location.search).get("api");
  const SMALL = new Set(["de", "del", "la", "las", "los", "el", "y", "e"]);
  const nice = (name) => name.toLowerCase().split(" ").map((w, i) => /^(i{1,3}|iv|vi{0,3}|ix|x)$/.test(w) ? w.toUpperCase() : i && SMALL.has(w) ? w : w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
  fetch("/publicaciones.json").then((r) => (r.ok ? r.json() : null)).then((doc) => {
    if (!doc) return;
    const count = new Map(), days = new Map();
    for (const p of doc.publicaciones) for (const k of p.colonias) {
      count.set(k, (count.get(k) || 0) + 1);
      if (p.dias != null) days.set(k, Math.max(days.get(k) || 0, p.dias));
    }
    const top = [...count].sort((a, b) => b[1] - a[1] || (days.get(b[0]) || 0) - (days.get(a[0]) || 0)).slice(0, 8);
    const buttons = top.map(([k, n]) => {
      const [name, m, cp] = k.split("|"), d = days.get(k);
      const b = document.createElement("button"), strong = document.createElement("strong"), small = document.createElement("small"), span = document.createElement("span");
      b.type = "button";
      b.setAttribute("aria-pressed", String(k === note.dataset.colonia));
      strong.textContent = nice(name);
      small.textContent = m + (d ? ` · hasta ${d} ${d === 1 ? "día" : "días"} sin agua` : "");
      span.textContent = `${n} ${n === 1 ? "publicación" : "publicaciones"}`;
      b.append(strong, small, span);
      b.addEventListener("click", () => {
        for (const x of buttons) x.setAttribute("aria-pressed", String(x === b));
        const q = new URLSearchParams({ q: name, m, cp });
        note.lastElementChild.href = "/reportes?" + q;
        note.dataset.colonia = k;
        note.dataset.nombre = `${nice(name)}, ${m}`;
        note.firstElementChild.textContent = `${n} ${n === 1 ? "publicación" : "publicaciones"} de medios y vecinos sobre la falta de agua en ${nice(name)}, ${m}.`;
        if (api) q.set("api", api);
        f.classList.remove("ready");
        f.src = "/reportes?" + q;
      });
      return b;
    });
    list.replaceChildren(...buttons.map((b) => { const li = document.createElement("li"); li.append(b); return li; }));
    document.querySelector(".hot").hidden = !buttons.length;
  }).catch(() => {});
})();
</script>
""")

# v9: the colonia search right under the headline; it opens the visitor's colonia in the map
# below, with its report form, instead of leaving the page.
page(9, """
.yours { padding: 6px 0 22px }
.yours h2 { font-size: clamp(1.4rem, 3.6vw, 1.8rem) }
.maphero { scroll-margin-top: 90px }
""", HEADLINE + YOURS + MAP + CONTRAST + WALL + BOXES + CONGRESO + MAS + WHY + CONTACT, script=r"""<script>
(() => {
  const form = document.querySelector(".yours form"), f = document.querySelector(".mapframe"), note = document.querySelector(".mapnote");
  const api = new URLSearchParams(location.search).get("api");
  form.addEventListener("submit", (e) => {
    const q = form.elements.q.value.trim();
    if (!q) return;
    e.preventDefault();
    const params = new URLSearchParams({ q, reportar: "1" });
    note.lastElementChild.href = "/reportes?" + params;
    note.firstElementChild.textContent = "Tu colonia en el mapa de lo que publican medios y vecinos: repórtala ahí mismo.";
    delete note.dataset.colonia;
    if (api) params.set("api", api);
    f.classList.remove("ready");
    f.src = "/reportes?" + params;
    document.querySelector(".maphero").scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  });
})();
</script>
""")

# v10: the headline, the map, the promise against the figures and the search; the rest folded.
folded = "".join(f'    <details class="fold"><summary>{title}</summary><div>{body}</div></details>\n'
                 for title, body in (split(WALL), split(CONGRESO), split(MAS), split(WHY)))
page(10, FOLDS_CSS + """
.fold .wall, .fold section { border-top: 0; padding: 0 }
.fold .cols { columns: 2 300px; column-gap: 28px }
.fold h4 { break-after: avoid; margin: 0 0 10px; font-size: .78rem; letter-spacing: .12em; text-transform: uppercase; color: var(--alarm) }
.fold .posts { margin: 0 0 18px }
.fold .posts li { break-inside: avoid }
.fold .note { color: var(--muted); font-size: .82rem; margin: 6px 0 0 }
.contact { border-top: 0 }
""", HEADLINE + MAP + CONTRAST + YOURS + BOXES + folded + CONTACT)

print(f"wrote {', '.join(f'web/v{n}.html' for n in NAMES)} from web/index.html")
