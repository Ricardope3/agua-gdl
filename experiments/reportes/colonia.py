"""Writes web/c1.html … web/c5.html: /reportes with a colonia open (Americana unless the link names
another), each laying out the colonia's view differently on phones. Wider screens see /reportes as is.
Run from the repo root: python3 experiments/reportes/colonia.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "web"

NAMES = {"c1": "Hoja", "c2": "Mitad y mitad", "c3": "Carrusel", "c4": "Ficha", "c5": "Muro"}

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
  const calla = (map) => map.eachLayer((l) => l.closeTooltip && l.closeTooltip());
"""

V = {
    # A bottom sheet that peeks with the essentials and opens to the posts.
    "c1": ("""
@media (max-width: 760px) {
  .stage .card { bottom: 0; left: 0; width: 100%; max-height: 220px; overflow: hidden; border-radius: 18px 18px 0 0; padding-top: 22px; transition: max-height .25s }
  .stage .card::before { content: ""; position: absolute; top: 8px; left: 50%; width: 40px; height: 5px; margin-left: -20px; border-radius: 3px; background: var(--line) }
  .stage .card.abierta { max-height: 86%; overflow: auto }
  .stage .card:not(.abierta) .mosaic, .stage .card:not(.abierta) .posts, .stage .card:not(.abierta) .ev ~ *, .stage .card:not(.abierta) .ev > .linkbtn { display: none }
  .stage .card .where { margin-bottom: 6px }
}""", r"""
  window.__antes = (map) => { calla(map); document.getElementById("ficha").classList.remove("abierta"); };
  window.__ficha = (card, e, form) => { if (form) card.classList.add("abierta"); acciones(card, e, true); };
  window.__pad = (s) => ({ paddingTopLeft: [70, 90], paddingBottomRight: [70, 240] });
"""),
    # The map on top, the card below it, each with its own half of the screen.
    "c2": ("""
@media (max-width: 760px) {
  .stage.has-card .bigmap { height: 44% }
  .stage .card { top: 44%; bottom: 0; left: 0; width: 100%; max-height: none; border-radius: 0; border-width: 2px 0 0; border-top-color: #e4572e; box-shadow: none }
  .stage.has-card .float-search { display: none }
}""", r"""
  window.__antes = (map, stage) => { calla(map); stage.classList.add("has-card"); map.invalidateSize(); };
  window.__cierra = (map) => map.invalidateSize();
  window.__ficha = (card, e) => acciones(card, e, false);
  window.__pad = (s) => ({ paddingTopLeft: [24, 24], paddingBottomRight: [24, 24] });
  window.__tile = [92, 70];
"""),
    # A short card over the map whose posts slide sideways, one at a time.
    "c3": ("""
@media (max-width: 760px) {
  .stage .card { bottom: 0; left: 0; width: 100%; max-height: 62%; border-radius: 18px 18px 0 0; padding: 14px 0 12px }
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
  window.__ficha = (card, e) => acciones(card, e, false);
  window.__pad = (s) => ({ paddingTopLeft: [70, 90], paddingBottomRight: [70, Math.round(s.y * 0.6)] });
"""),
    # The colonia as a page: a strip of map, the days in large type, the report button always at hand.
    "c4": ("""
@media (max-width: 760px) {
  .stage.has-card .bigmap { height: 30% }
  .stage .card { top: calc(30% - 16px); bottom: 0; left: 0; width: 100%; max-height: none; border-radius: 18px 18px 0 0; padding-bottom: 0 }
  .stage.has-card .float-search { display: none }
  .stage .card .ev-head { flex-direction: column; align-items: flex-start; gap: 4px; font-size: 1.15rem }
  .stage .card .ev-head .sevb { font: 800 2.6rem/1 var(--font); padding: 6px 14px; border-radius: 14px }
  .stage .card .mosaic { margin-left: -18px; margin-right: -18px; border-radius: 0 }
  .stage .card .c-acc { position: sticky; bottom: 0; z-index: 2; margin: 14px -18px 0; padding: 10px 18px calc(10px + env(safe-area-inset-bottom)); background: var(--surface); border-top: 1px solid var(--line) }
  .stage .card > .button { display: none }
}""", r"""
  window.__antes = (map, stage) => { calla(map); stage.classList.add("has-card"); map.invalidateSize(); };
  window.__cierra = (map) => map.invalidateSize();
  window.__ficha = (card, e) => card.append(acciones(card, e, false));
  window.__pad = (s) => ({ paddingTopLeft: [16, 16], paddingBottomRight: [16, 16] });
  window.__tile = [0, 0];
"""),
    # The map and its wall of posts are the view; the card is a slim bar until asked.
    "c5": ("""
@media (max-width: 760px) {
  .stage .card { bottom: 8px; max-height: 160px; overflow: hidden; padding: 12px 14px; border: 2px solid #e4572e }
  .stage .card h2 { font-size: 1.1rem }
  .stage .card .where { margin: 0; font-size: .85rem }
  .stage .card:not(.abierta) > :not(h2):not(.where):not(.close):not(.c-acc) { display: none }
  .stage .card:not(.abierta) .where ~ .where { display: none }
  .stage .card .c-acc { margin-top: 8px }
  .stage .card.abierta { max-height: 82%; overflow: auto }
  .stage .float-search { opacity: .96 }
}""", r"""
  window.__antes = (map) => { calla(map); document.getElementById("ficha").classList.remove("abierta"); };
  window.__ficha = (card, e, form) => {
    if (form) card.classList.add("abierta");
    const h = card.querySelector("h2");
    if (e && !h.querySelector(".sevb")) { const b = card.querySelector(".ev-head .sevb"); if (b) h.append(" ", b.cloneNode(true)); }
    card.querySelector(".where").after(acciones(card, e, true));
  };
  window.__pad = (s) => ({ paddingTopLeft: [120, 130], paddingBottomRight: [120, 200] });
  window.__tile = [140, 105];
"""),
}


def sub(html, old, new):
    assert html.count(old) == 1, old
    return html.replace(old, new)


CUR = ' aria-current="page"'


def build(src, v, bar=True):
    name = NAMES[v]
    css, js = V[v]
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
            '      stage.classList.add("has-card");\n      setOverview(false);\n      if (window.__ficha && phone()) window.__ficha(card, e, openForm);\n')
    return h


def main():
    src = (Path(__file__).parent / "reportes-before-c3.html").read_text()
    for v in NAMES:
        (WEB / f"{v}.html").write_text(build(src, v))
        print(f"web/{v}.html")
    # /reportes itself takes c3's layout on phones.
    (WEB / "reportes.html").write_text(build(src, "c3", bar=False))
    print("web/reportes.html")


if __name__ == "__main__":
    main()
