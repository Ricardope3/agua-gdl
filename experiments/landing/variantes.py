#!/usr/bin/env python3
"""Variants of the landing page, to compare one idea at a time against it: writes web/v11.html …
web/v15.html (noindex, with a bar to switch between them and the current landing) from the blocks
of web/index.html, so each carries the landing's copy, quotes, sources, style and scripts and only
moves, retargets or wires them differently. The landing is the 21 Oct 2026 rounds' v1 and then v6;
those rounds' pages are in git history (web/v1.html … v10.html, now redirected to /).
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


def map_on(src, href, note):
    """The landing's map block opening src, its link going to href, with its own note (and no
    colonia for the landing's script to count)."""
    m = re.sub(r' data-(colonia|nombre)="[^"]*"', "", MAP)
    m = re.sub(r'src="/reportes[^"]*"', f'src="{src}"', m)
    m = re.sub(r'href="/reportes[^"]*"', f'href="{href}"', m)
    return re.sub(r"<span>.*?</span>", f"<span>{note}</span>", m, count=1)


NAMES = {11: "Mapa primero", 12: "Toda la ciudad", 13: "La más publicada", 14: "Mapa con lista", 15: "Tu colonia primero"}

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


def page(n, css, main, script=""):
    head = re.sub(r"<title>.*?</title>", f'<title>Agua GDL · Variante {n}: {NAMES[n]}</title>\n<meta name="robots" content="noindex">', HEAD, count=1, flags=re.S)
    out = (head + BAR_CSS + css + "</style>" + HEAD_END + "</head>\n<body>\n<div class=\"wrap\">\n" + bar(n) + HEADER
           + "\n  <main>\n" + main + "  </main>\n\n" + FOOTER + "</div>\n" + SCRIPTS + script + "</body>\n</html>\n")
    (WEB / f"v{n}.html").write_text(out, encoding="utf-8")


REST = CONTRAST + YOURS + WALL + BOXES + CONGRESO + MAS + WHY + CONTACT
NICE = r"""  const SMALL = new Set(["de", "del", "la", "las", "los", "el", "y", "e"]);
  const nice = (name) => name.toLowerCase().split(" ").map((w, i) => /^(i{1,3}|iv|vi{0,3}|ix|x)$/.test(w) ? w.toUpperCase() : i && SMALL.has(w) ? w : w.charAt(0).toUpperCase() + w.slice(1)).join(" ");
"""

# v11: the map first, filling the screen under the menu; the headline after it.
page(11, """
header.top { margin-bottom: 0 }
.maphero { margin: 0 0 22px }
.maphero .mapframe-box { height: calc(100dvh - 110px); border-top: 0 }
@media (min-width: 1100px) { .maphero .mapframe-box { height: calc(100dvh - 62px) } }
.headline { padding-top: 6px }
""", MAP + HEADLINE + REST)

# v12: the map on the whole city instead of one colonia.
page(12, "", HEADLINE + map_on("/reportes", "/reportes", "Cada colonia toma el color de los días sin agua que dicen sus publicaciones. Toca la tuya para ver qué se ha publicado y reportarla.") + REST)

# v13: the map opens on whichever colonia has the most publications when the page loads.
page(13, "", HEADLINE + map_on("about:blank", "/reportes", "Buscando la colonia con más publicaciones…") + REST, script=r"""<script>
(() => {
  const f = document.querySelector(".mapframe"), note = document.querySelector(".mapnote");
  const api = new URLSearchParams(location.search).get("api");
""" + NICE + r"""  const open = (params) => {
    if (api) params.set("api", api);
    f.classList.remove("ready");
    f.src = "/reportes?" + params;
  };
  fetch("/publicaciones.json").then((r) => (r.ok ? r.json() : null)).then((doc) => {
    const count = new Map();
    for (const p of doc.publicaciones) for (const k of p.colonias) count.set(k, (count.get(k) || 0) + 1);
    const ranked = [...count].sort((a, b) => b[1] - a[1]);
    const [k, n] = ranked[0], tied = ranked.filter(([, c]) => c === n).length > 1;
    const [name, m, cp] = k.split("|"), q = new URLSearchParams({ q: name, m, cp });
    note.lastElementChild.href = "/reportes?" + q;
    note.firstElementChild.textContent = `${nice(name)}, ${m}, es ${tied ? "una de las colonias" : "la colonia"} con más publicaciones de medios y vecinos sobre la falta de agua: ${n}.`;
    open(q);
  }).catch(() => {
    note.firstElementChild.textContent = "Cada colonia toma el color de los días sin agua que dicen sus publicaciones.";
    open(new URLSearchParams());
  });
})();
</script>
""")

# v14: under the map, the colonias with the most publications; a tap shows one in the map.
page(14, """
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
""" + REST, script=r"""<script>
(() => {
  const f = document.querySelector(".mapframe"), note = document.querySelector(".mapnote"), list = document.getElementById("hot");
  const api = new URLSearchParams(location.search).get("api");
""" + NICE + r"""  fetch("/publicaciones.json").then((r) => (r.ok ? r.json() : null)).then((doc) => {
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

# v15: the colonia search right under the headline; it opens the visitor's colonia in the map
# below, with its report form, instead of leaving the page.
page(15, """
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

print(f"wrote {', '.join(f'web/v{n}.html' for n in NAMES)} from web/index.html")
