"""Writes web/c1.html … web/c5.html: /reportes with a colonia open (Americana unless the link names
another), each a take on the carousel /reportes shows a colonia in on phones. Wider screens see /reportes as is.
Run from the repo root: python3 experiments/reportes/colonia.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"


BAR_CSS = """
.variant-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 6px; padding: 6px 16px; background: #1c1400; color: #fde68a; font-size: .78rem } .variant-bar strong { margin-right: 4px } .variant-bar a { color: #fde68a; text-decoration: none; padding: 2px 8px; border-radius: 999px; border: 1px solid #fde68a55 } .variant-bar a[aria-current="page"] { background: #fde68a; color: #1c1400; font-weight: 700 }
.en-portada .variant-bar { display: none }
@media (max-width: 760px) {
  #reporta { display: none !important }
  .c-acc { display: flex; gap: 8px; margin: 10px 0 0 }
  .c-acc .button { flex: 1; justify-content: center; padding: 10px 12px; font-size: .95rem }
  .c-acc .rep { background: #e4572e; color: #fff; font-weight: 700 }
  .c-acc .rep:hover { background: #c4421c }
  .c-acc .alt2 { flex: 0 0 auto; background: var(--subtle); color: var(--fg) }
  .stage .card > .button { display: none }
  .stage.has-card .leaflet-control-zoom, .stage.has-card .leaflet-control-centrar { display: none }
}"""

# Hooks the variants fill: __antes(map, stage) before the map frames the colonia, __ficha(card, e, form)
# once its card is drawn, __cierra(map) when it closes, __pad(size) the phone's framing, __tile the tiles' size.
COMMON = r"""
  const isPhone = () => matchMedia("(max-width: 760px)").matches;
  // The report button and, when wanted, a toggle for the rest of the card, right under its title.
  function acciones(card, e, more) {
    const row = document.createElement("div");
    row.className = "c-acc";
    if (!card.querySelector(".thanks") && !card.querySelector("form.report")) {
      const r = document.createElement("button");
      r.type = "button"; r.className = "button rep"; r.textContent = "Reportar esta colonia";
      r.addEventListener("click", () => { card.classList.add("abierta"); document.getElementById("reporta-btn").click(); });
      row.append(r);
    }
    if (more) {
      const t = document.createElement("button");
      t.type = "button"; t.className = "button alt2";
      const set = () => { t.textContent = card.classList.contains("abierta") ? "Menos" : e ? `Ver ${e.posts.length} publicaciones` : "Ver más"; };
      t.addEventListener("click", () => { card.classList.toggle("abierta"); card.scrollTop = 0; set(); });
      set();
      row.append(t);
    }
    const at = card.querySelector(".ev-src") || [...card.querySelectorAll(".where")].pop();
    if (row.children.length && at) at.after(row);
    return row;
  }
  // The card's head on one line: «NAME · Municipio», then only the zone SIAPA puts it in.
  function compacta(card, p) {
    const M = window.aguaMapa, h = card.querySelector("h2"), w = card.querySelector(".where");
    if (!p || !h || !w || h.querySelector("small")) return;
    const ls = M.zonesOf(p.l || ""), zs = ls.length ? ls : M.zones(p).main;
    h.append(" ", Object.assign(document.createElement("small"), { textContent: `· ${p.m}` }));
    w.textContent = zs.length ? `${zs.length > 1 ? "Zonas" : "Zona"} ${M.joinES(zs.map(String))}` : "Sin zona en el mapa del SIAPA";
  }
  const calla = (map) => map.eachLayer((l) => l.closeTooltip && l.closeTooltip());
"""

# /reportes' carousel on phones: a short card over the map whose posts slide sideways.
BASE = ("""
@media (max-width: 760px) {
  .stage .card { bottom: 0; left: 0; width: 100%; max-height: 74%; overflow: hidden; border-radius: 18px 18px 0 0; padding: 14px 0 12px }
  .stage .card h2 { font-size: 1.2rem }
  .stage .card h2 small { font: 400 1rem var(--font); color: var(--muted); text-transform: none; letter-spacing: 0 }
  .stage .card .where { margin-bottom: 8px }
  .stage .card .where ~ .where { display: none }
  .stage .card .ev-src { margin-top: 3px }
  .stage .card > :not(.ev):not(.close), .stage .card .ev > :not(.posts) { margin-left: 16px; margin-right: 16px }
  .stage .card .mosaic, .stage .card .ev > .linkbtn, .stage .card .sub-head, .stage .card .conteo { display: none }
  .stage .card .posts { display: flex; overflow-x: auto; scroll-snap-type: x mandatory; gap: 10px; padding: 0 16px 6px; scrollbar-width: none }
  .stage .card .posts li, .stage .card .posts li[hidden] { display: block; flex: 0 0 82%; scroll-snap-align: center }
  .stage .card .posts .eco { display: none }
  .stage .card .posts q { display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden }
  .stage .card .ev-src { font-size: .82rem }
  .stage .card .c-acc { margin-left: 16px; margin-right: 16px }
}""", r"""
  window.__antes = (map) => calla(map);
  window.__ficha = (card, e, form, p) => { compacta(card, p); acciones(card, e, false); };
  window.__pad = (s) => ({ paddingTopLeft: [40, 90], paddingBottomRight: [40, Math.round(s.y * 0.6)] });
  // The carousel holds the posts, so the map shows no tiles of them around the colonia.
  window.__tile = [0, 0];
""")

# Helpers the variants share: each slide with its post, and a dot per slide that follows the scroll.
SLIDES = r"""
  const slides = (card, e) => [...card.querySelectorAll(".posts li")].map((li, i) => [li, e.posts[i]]);
  function dots(card, n, label) {
    const list = card.querySelector(".posts");
    if (!list || n < 2) return;
    const row = document.createElement("div");
    row.className = "c-dots";
    const count = document.createElement("span");
    const prev = document.createElement("button"), next = document.createElement("button");
    prev.type = next.type = "button"; prev.textContent = "‹"; next.textContent = "›";
    prev.setAttribute("aria-label", "Anterior"); next.setAttribute("aria-label", "Siguiente");
    const step = () => list.children[0].getBoundingClientRect().width + 10;
    prev.onclick = () => list.scrollBy({ left: -step(), behavior: "smooth" });
    next.onclick = () => list.scrollBy({ left: step(), behavior: "smooth" });
    const marks = label ? null : Array.from({ length: Math.min(n, 12) }, () => document.createElement("i"));
    const at = () => {
      const i = Math.min(n - 1, Math.round(list.scrollLeft / step()));
      if (marks) marks.forEach((m, j) => m.classList.toggle("on", j === Math.min(i, marks.length - 1)));
      else count.textContent = `${i + 1} de ${n}`;
      prev.disabled = i === 0; next.disabled = i === n - 1;
    };
    list.addEventListener("scroll", at, { passive: true });
    if (marks) row.append(prev, ...marks, next); else row.append(prev, count, next);
    list.after(row);
    at();
  }
"""

DOTS_CSS = """
  .c-dots { display: flex; align-items: center; justify-content: center; gap: 6px; margin: 4px 16px 0; font-size: .85rem; color: var(--muted); font-variant-numeric: tabular-nums }
  .c-dots button { width: 34px; height: 30px; border: 1px solid var(--line); border-radius: 8px; background: var(--surface); color: var(--fg); font: 700 1.1rem/1 var(--font); cursor: pointer }
  .c-dots button:disabled { opacity: .35 }
  .c-dots i { width: 7px; height: 7px; border-radius: 50%; background: var(--line); transition: width .2s }
  .c-dots i.on { width: 18px; border-radius: 4px; background: #e4572e }"""

V = {
    # Each slide shows the post's own picture above its words.
    "c1": ("Con imagen", """
@media (max-width: 760px) {
  .stage .card .posts li { padding: 0 0 10px; overflow: hidden }
  .stage .card .posts li > :not(.c-img) { margin-left: 12px; margin-right: 12px }
  .c-img { display: block; width: 100%; height: 96px; object-fit: cover; margin-bottom: 8px; background: var(--subtle) }
  .stage .card .posts li.sin-img { padding-top: 10px }
  .stage .card .posts q { -webkit-line-clamp: 2 }
}""", r"""
  window.__ficha = (card, e, form, p) => {
    compacta(card, p);
    acciones(card, e, false);
    if (!e) return;
    for (const [li, p] of slides(card, e)) {
      const src = p.vista || p.captura || (p.en && p.en.vista);
      if (!src) { li.classList.add("sin-img"); continue; }
      const img = document.createElement("img");
      img.className = "c-img"; img.src = `/${src}`; img.alt = ""; img.loading = "lazy"; img.decoding = "async";
      li.prepend(img);
    }
  };
"""),
    # Arrows and «2 de 5», and a tap on a quote reads it whole.
    "c2": ("Contador", """
@media (max-width: 760px) {""" + DOTS_CSS + """
  .stage .card .posts q { cursor: pointer }
  .stage .card .posts li.full q { -webkit-line-clamp: unset; display: block }
  .stage .card .posts li:not(.full) q::after { content: " Leer todo"; color: var(--link); font-weight: 600; font-size: .85rem }
}""", r"""
  window.__ficha = (card, e, form, p) => {
    compacta(card, p);
    acciones(card, e, false);
    if (!e) return;
    for (const [li] of slides(card, e)) li.querySelector("q").addEventListener("click", () => li.classList.toggle("full"));
    dots(card, e.posts.length, true);
  };
"""),
    # The least card that still says it: name and days on one line, narrower slides, more map.
    "c3": ("Compacto", """
@media (max-width: 760px) {
  .stage .card { max-height: 46%; padding-top: 12px }
  .stage .card h2 { font-size: 1.1rem; display: flex; align-items: center; gap: 8px; flex-wrap: wrap }
  .stage .card .where { margin: 2px 0 0; font-size: .82rem }
  .stage .card .where ~ .where, .stage .card .ev-head, .stage .card .ev-src { display: none }
  .stage .card .c-acc { margin-top: 8px }
  .stage .card .c-acc .button { padding: 8px 10px }
  .stage .card .posts li, .stage .card .posts li[hidden] { flex-basis: 72%; padding: 8px 10px }
  .stage .card .posts q { font-size: .88rem; -webkit-line-clamp: 2 }
  .stage .card .posts .who { font-size: .75rem }
}""", r"""
  window.__ficha = (card, e, form, p) => {
    compacta(card, p);
    const h = card.querySelector("h2"), b = card.querySelector(".ev-head .sevb");
    if (b) h.append(b.cloneNode(true));
    const row = acciones(card, e, false);
    card.querySelector(".where").after(row);
  };
  window.__pad = (s) => ({ paddingTopLeft: [50, 90], paddingBottomRight: [50, Math.round(s.y * 0.46) + 20] });
"""),
    # Outlets first, each slide marked as a news outlet or a neighbour, with the days it gives.
    "c4": ("Quién lo dice", """
@media (max-width: 760px) {
  .stage .card .posts li { position: relative; padding-top: 34px }
  .c-who { position: absolute; top: 9px; left: 12px; right: 12px; display: flex; gap: 6px; align-items: center }
  .c-who span { font-size: .68rem; font-weight: 800; letter-spacing: .05em; text-transform: uppercase; padding: 2px 7px; border-radius: 4px; background: var(--subtle); color: var(--muted) }
  .c-who .m { background: var(--brand); color: #fff }
  .c-who .d { margin-left: auto; background: #e4572e; color: #fff }
  .stage .card .posts li.medio { background: color-mix(in srgb, var(--brand) 10%, var(--bg)) }
  .stage .card .posts .who .tag { display: none }
}""", r"""
  window.__ficha = (card, e, form, p) => {
    compacta(card, p);
    acciones(card, e, false);
    if (!e) return;
    const all = slides(card, e), list = card.querySelector(".posts");
    all.sort(([, a], [, b]) => (b.fuente === "medio") - (a.fuente === "medio"));
    for (const [li, p] of all) {
      const w = document.createElement("span");
      w.className = "c-who";
      w.innerHTML = p.fuente === "medio" ? '<span class="m">Medio</span>' : `<span>${p.tipo === "comentario" ? "Comentario de vecino" : "Vecino"}</span>`;
      if (p.dias) w.insertAdjacentHTML("beforeend", `<span class="d">${p.dias} ${p.dias === 1 ? "día" : "días"}</span>`);
      li.prepend(w);
      list.append(li);
    }
  };
"""),
    # Dots under the slides, and a last slide that asks the visitor to act: report, demand, share.
    "c5": ("Remata con acción", """
@media (max-width: 760px) {""" + DOTS_CSS + """
  .stage .card .posts li.c-fin { display: flex; flex-direction: column; justify-content: center; gap: 8px; border: 2px dashed #e4572e; background: color-mix(in srgb, #e4572e 8%, var(--bg)) }
  .c-fin p { margin: 0; font-weight: 700; line-height: 1.3 }
  .c-fin .button { justify-content: center; padding: 8px 10px; font-size: .9rem }
  .c-fin .rep { background: #e4572e; color: #fff }
}""", r"""
  window.__ficha = (card, e, form, p) => {
    compacta(card, p);
    acciones(card, e, false);
    if (!e) return;
    const list = card.querySelector(".posts"), name = card.querySelector("h2").textContent;
    const q = new URLSearchParams(location.search);
    const fin = document.createElement("li");
    fin.className = "post c-fin";
    fin.innerHTML = `<p>¿Y en tu casa hay agua?</p><button type="button" class="button rep">Reportar esta colonia</button><a class="button alt" href="/exige?${new URLSearchParams({ q: q.get("q") || name, m: q.get("m") || "", cp: q.get("cp") || "" })}">Exígelo al gobierno</a>`;
    fin.querySelector(".rep").onclick = () => document.getElementById("reporta-btn").click();
    list.append(fin);
    dots(card, e.posts.length + 1, false);
  };
"""),
}
NAMES = {k: v[0] for k, v in V.items()}


DEFAULT = "c1"


def sub(html, old, new):
    assert html.count(old) == 1, old
    return html.replace(old, new)


CUR = ' aria-current="page"'


def build(src, v, bar=True):
    name = NAMES.get(v)
    css, js = (BASE[0] + V[v][1], BASE[1] + SLIDES + V[v][2]) if v in V else BASE
    links = '<a href="/reportes?q=AMERICANA&amp;m=Guadalajara&amp;cp=44100">Actual</a>' + "".join(
        f'<a href="/{k}"{CUR if k == v else ""}>{k} {n}</a>' for k, n in NAMES.items())
    h = src
    if not bar:
        return hooks(h.replace("</style>", BAR_CSS.split(".en-portada .variant-bar { display: none }")[1] + css + "\n</style>", 1), js)
    h = sub(h, "<title>¿Hay agua en tu colonia? · Agua GDL</title>",
            f'<title>Agua GDL · Prueba {v}: {name}</title>\n<meta name="robots" content="noindex">')
    h = h.replace("</style>", BAR_CSS + css + "\n</style>", 1)
    h = sub(h, "<body>\n<div class=\"wrap\">",
            f'<body>\n<div class="variant-bar"><strong>Prueba · {v}: {name}</strong>{links}</div>\n'
            f'<script>{COMMON}{js}</script>\n<div class="wrap">')
    h = sub(h, 'const stage = $("escenario"), top = document.querySelector("header.top");\n'
               '  const fitStage = () => { document.documentElement.style.setProperty("--hh", `${top.offsetHeight}px`); map.invalidateSize(); };\n'
               '  if (window.ResizeObserver) new ResizeObserver(fitStage).observe(top);',
            'const stage = $("escenario"), top = document.querySelector("header.top"), vbar = document.querySelector(".variant-bar");\n'
            '  const fitStage = () => { document.documentElement.style.setProperty("--hh", `${top.offsetHeight + (vbar && vbar.offsetParent ? vbar.offsetHeight : 0)}px`); map.invalidateSize(); };\n'
            '  if (window.ResizeObserver) { const ro = new ResizeObserver(fitStage); ro.observe(top); if (vbar) ro.observe(vbar); }')
    return hooks(h, js, americana=True)


def hooks(h, js, americana=False):
    if not americana:
        h = sub(h, "<body>\n<div class=\"wrap\">", f'<body>\n<script>{COMMON}{js}</script>\n<div class="wrap">')
    # Americana unless the link names a colonia.
    if americana: h = sub(h, "const params = new URLSearchParams(location.search);",
            'if (!new URLSearchParams(location.search).get("q")) history.replaceState(null, "", `${location.pathname}?q=AMERICANA&m=Guadalajara&cp=44100${location.search.replace(/^\\?/, "&")}`);\n'
            "    const params = new URLSearchParams(location.search);")
    h = sub(h, '      stage.classList.remove("has-card");\n',
            '      stage.classList.remove("has-card");\n      if (window.__cierra) window.__cierra(map);\n')
    h = sub(h, "      if (fit) {\n        // Room around",
            "      if (window.__antes && phone()) window.__antes(map, stage);\n      if (fit) {\n        // Room around")
    h = sub(h, "const pad = phone() ? {", "const pad = phone() && window.__pad ? window.__pad(map.getSize()) : phone() ? {")
    h = sub(h, "const W = phone() ? 120 : 210, H = phone() ? 90 : 158, G = 8;",
            "const W = phone() ? (window.__tile || [120])[0] : 210, H = phone() ? (window.__tile || [0, 90])[1] : 158, G = 8;\n"
            "        if (!W) return;")
    h = sub(h, '      stage.classList.add("has-card");\n      setOverview(false);\n',
            '      stage.classList.add("has-card");\n      setOverview(false);\n      if (window.__ficha && phone()) window.__ficha(card, e, openForm, f.properties);\n')
    return h


def main():
    src = (Path(__file__).parent / "reportes-before-c3.html").read_text()
    for v in NAMES:
        (WEB / f"{v}.html").write_text(build(src, v))
        print(f"web/{v}.html")
    # /reportes itself takes this variant's carousel on phones.
    (WEB / "reportes.html").write_text(build(src, DEFAULT, bar=False))
    print("web/reportes.html")


if __name__ == "__main__":
    main()
