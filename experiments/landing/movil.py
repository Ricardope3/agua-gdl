"""Writes the phone variants of the landing, web/m1.html … web/m5.html, from the landing as it was before m5 became it
(experiments/landing/index-before-m5.html); web/index.html is m5 without its noindex and variant bar.

Each one changes only what shows at 760 px or less; on a wider screen it is the landing as is.
Run from the repo root: python3 experiments/landing/movil.py
"""
import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[2] / "web"
MUESTRA = "?muestra=CIUDAD+GRANJA%7CZapopan%7C45010"

NAMES = {"m1": "Mapa limpio", "m2": "Cifras primero", "m3": "Pantalla completa", "m4": "Historias", "m5": "Zonas"}

# Shared by every variant: a smaller illustration beside the headline, the variant bar, the data.
BASE_CSS = """
@media (max-width: 760px) {
  .cartel { grid-template-columns: minmax(0, 1fr) 92px; gap: 4px 12px; padding: 4px 0 12px }
  .cartel h1 { font-size: 1.55rem; margin: 0 }
  .cartel .kicker { font-size: .72rem; margin-bottom: 4px }
  .cartel .ilus { width: 92px; justify-self: end }
}
.vbar { position: fixed; left: 8px; bottom: 8px; z-index: 50; background: var(--fg); color: var(--bg); font: 12px/1.4 system-ui, sans-serif; padding: 6px 10px; border-radius: 6px; max-width: calc(100% - 16px) }
.vbar a { color: inherit; opacity: .7 } .vbar a[aria-current] { opacity: 1; font-weight: 700 }
.m-only { display: none }
@media (max-width: 760px) { .m-only { display: block } }
.m-num { font: 800 3.4rem/1 var(--serif, Georgia, serif); color: var(--alarm); font-variant-numeric: tabular-nums }
.m-k { font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 700; margin: 0 0 6px }
.m-rank { list-style: none; margin: 0; padding: 0 }
.m-rank li { border-bottom: 1px solid var(--line) }
.m-rank a { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 2px 10px; padding: 10px 0; color: inherit; text-decoration: none }
.m-rank b { font-weight: 600 } .m-rank small { color: var(--muted); grid-column: 1 }
.m-rank .d { grid-row: 1 / 3; grid-column: 2; align-self: center; font-weight: 800; color: var(--alarm); font-variant-numeric: tabular-nums }
.m-bar { height: 6px; border-radius: 3px; background: var(--subtle); overflow: hidden }
.m-rank .m-bar { grid-column: 1 / -1 }
.m-bar i { display: block; height: 100%; background: var(--alarm) }
"""

BASE_JS = r"""
const aguaM = (() => {
  const SMALL = ["de", "del", "la", "las", "los", "el", "y"];
  const name = (k) => k.split("|")[0].toLowerCase().replace(/(^|[\s(])([^\s(]+)/g, (m, p, w) => p + (SMALL.includes(w) && p ? w : w[0].toUpperCase() + w.slice(1)));
  const link = (k) => { const [q, m, cp] = k.split("|"); return "/reportes?" + new URLSearchParams({ q, m, cp }); };
  const fmt = (n) => n.toLocaleString("es-MX");
  const datos = fetch("/publicaciones.json").then((r) => r.json()).then((d) => {
    const m = new Map();
    for (const e of d.publicaciones) for (const k of e.colonias) {
      const r = m.get(k) || { k, dias: 0, n: 0, muni: k.split("|")[1] };
      r.dias = Math.max(r.dias, e.dias || 0); r.n++; m.set(k, r);
    }
    const cols = [...m.values()], medios = d.publicaciones.filter((e) => e.fuente === "medio");
    const munis = new Map();
    for (const c of cols) if (!c.muni.includes(" y ")) munis.set(c.muni, (munis.get(c.muni) || 0) + 1);
    return {
      pubs: d.publicaciones, cols, semana: cols.filter((c) => c.dias >= 7).length, medios: medios.length,
      max: Math.max(...medios.map((e) => e.dias || 0)),
      top: [...cols].sort((a, b) => b.n - a.n || b.dias - a.dias),
      peores: [...cols].sort((a, b) => b.dias - a.dias || b.n - a.n),
      munis: [...munis].sort((a, b) => b[1] - a[1]),
    };
  });
  // The frame is same-origin: a style element in it rearranges /reportes for this variant.
  const frame = (css) => {
    const f = document.querySelector(".mapframe");
    if (!f) return;
    const go = () => {
      try {
        const d = f.contentDocument;
        if (!d || !d.head || d.location.href === "about:blank" || d.getElementById("movil")) return;
        const s = d.createElement("style"); s.id = "movil"; s.textContent = css; d.head.append(s);
      } catch {}
    };
    const t = setInterval(() => { go(); try { if (f.contentDocument.getElementById("movil")) clearInterval(t); } catch {} }, 50);
    f.addEventListener("load", go);
  };
  const rank = (list, n, max) => list.slice(0, n).map((c) =>
    `<li><a href="${link(c.k)}"><b>${name(c.k)}</b><span class="d">${c.dias ? c.dias + " días" : c.n + " rep."}</span><small>${c.muni} · ${c.n} ${c.n === 1 ? "publicación" : "publicaciones"}</small>${max ? `<span class="m-bar"><i style="width:${Math.max(4, 100 * c.dias / max)}%"></i></span>` : ""}</a></li>`).join("");
  return { datos, frame, name, link, fmt, rank, phone: matchMedia("(max-width: 760px)").matches };
})();
"""

# Hides /reportes' summary and timeline inside the frame, so the phone sees the map alone.
MAP_ONLY = "@media (max-width: 760px) { #resumen-mapa, #linea { display: none !important } }"

V = {}

V["m1"] = dict(
    css="""
@media (max-width: 760px) {
  .m1-cifra { margin: 4px 0 10px }
  .m1-cifra p { margin: 4px 0 0; font-size: 1.05rem; line-height: 1.35 }
  .m1-cifra .s { color: var(--muted); font-size: .88rem }
  .mapframe-box { height: 64svh; min-height: 380px }
  .maphero { margin-bottom: 8px }
  .maphero .mapnote { display: none }
  .m1-chips { display: flex; gap: 8px; overflow-x: auto; scroll-snap-type: x mandatory; padding: 4px 16px 10px; margin: 0 -16px 22px; scrollbar-width: none }
  .m1-chips a { flex: 0 0 auto; scroll-snap-align: start; display: grid; gap: 1px; padding: 8px 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); color: inherit; text-decoration: none; font-size: .9rem }
  .m1-chips a b { font-weight: 700 } .m1-chips a small { color: var(--muted) }
  .m1-chips-h { margin: 0 0 4px }
}""",
    before_map="""<div class="m-only m1-cifra" aria-live="polite" data-ancla><div class="m-num" id="m1-num">—</div><p>colonias llevan <strong>una semana o más sin agua</strong>, según medios y vecinos.</p><p class="s" id="m1-sub"></p></div>""",
    after_map="""<div class="m-only"><p class="m-k m1-chips-h">Las que más reportes tienen · toca una</p><div class="m1-chips" id="m1-chips"></div></div>""",
    frame_css=MAP_ONLY,
    map_only=True,
    js="""
aguaM.datos.then((d) => {
  document.getElementById("m1-num").textContent = aguaM.fmt(d.semana);
  document.getElementById("m1-sub").textContent = `De ${aguaM.fmt(d.cols.length)} colonias con publicaciones · ${aguaM.fmt(d.medios)} notas de medios · hasta ${d.max} días según un medio`;
  document.getElementById("m1-chips").innerHTML = d.top.slice(0, 10).map((c) => `<a href="${aguaM.link(c.k)}"><b>${aguaM.name(c.k)}</b><small>${c.n} reportes${c.dias ? " · " + c.dias + " días" : ""}</small></a>`).join("");
});""",
)

V["m2"] = dict(
    css="""
@media (max-width: 760px) {
  .maphero { display: none }
  .m2 { margin: 0 0 28px }
  .m2-card { border: 1px solid var(--line); border-radius: 12px; background: var(--surface); padding: 14px 16px; margin: 0 0 14px }
  .m2-card p { margin: 6px 0 0 }
  .m2 form { display: flex; gap: 8px; margin: 0 0 14px }
  .m2 input { flex: 1; min-width: 0; font: inherit; font-size: 1rem; padding: 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); color: var(--fg) }
  .m2-munis { display: grid; gap: 6px; margin: 0; padding: 0; list-style: none }
  .m2-munis li { display: grid; grid-template-columns: 9em minmax(0, 1fr) 2.2em; gap: 8px; align-items: center; font-size: .9rem }
  .m2-munis b { text-align: right; font-variant-numeric: tabular-nums }
  .m2 .button.full { width: 100%; justify-content: center; margin-top: 12px }
}""",
    before_map="""<section class="m-only m2" aria-label="Resumen">
  <div class="m2-card"><p class="m-k">¿Hay agua en tu colonia?</p><div class="m-num" id="m2-num">—</div><p>colonias llevan <strong>una semana o más sin agua</strong>, según medios y vecinos. El SIAPA prometió «por máximo un día».</p><p class="note" id="m2-sub"></p></div>
  <form action="/reportes" method="get" role="search"><input name="q" type="search" placeholder="Busca tu colonia" aria-label="Tu colonia" required maxlength="80"><button class="button" type="submit">Buscar</button></form>
  <div class="m2-card"><p class="m-k">Las que llevan más días sin agua</p><ol class="m-rank" id="m2-rank"></ol><a class="button full" href="/reportes">Abrir el mapa completo</a></div>
  <div class="m2-card"><p class="m-k">Colonias con publicaciones, por municipio</p><ul class="m2-munis" id="m2-munis"></ul></div>
</section>""",
    after_map="",
    frame_css="",
    lazy_frame=True,
    js="""
aguaM.datos.then((d) => {
  document.getElementById("m2-num").textContent = aguaM.fmt(d.semana);
  document.getElementById("m2-sub").textContent = `${aguaM.fmt(d.cols.length)} colonias con publicaciones · ${aguaM.fmt(d.medios)} notas de medios`;
  document.getElementById("m2-rank").innerHTML = aguaM.rank(d.peores, 8, d.peores[0].dias);
  const top = d.munis[0][1];
  document.getElementById("m2-munis").innerHTML = d.munis.map(([m, n]) => `<li><span>${m}</span><span class="m-bar"><i style="width:${100 * n / top}%"></i></span><b>${n}</b></li>`).join("");
});""",
)

V["m3"] = dict(
    css="""
@media (max-width: 760px) {
  .mapframe-box { height: calc(100svh - 96px); min-height: 460px }
  .maphero .mapnote { font-size: .85rem }
}""",
    before_map="",
    after_map="",
    frame_css="",
    js="",
)

V["m4"] = dict(
    css="""
@media (max-width: 760px) {
  .m4 { margin: 0 -16px 18px }
  .m4-track { display: flex; gap: 10px; overflow-x: auto; scroll-snap-type: x mandatory; padding: 4px 16px; scrollbar-width: none }
  .m4-card { flex: 0 0 84%; scroll-snap-align: center; min-height: 260px; display: flex; flex-direction: column; border: 3px double var(--brand); border-radius: 6px; background: var(--surface); padding: 16px }
  .m4-card h3 { font-size: 1.25rem; margin: 0 0 8px; font-style: italic; font-weight: 400 }
  .m4-card p { margin: 6px 0 0 }
  .m4-card q { display: block; font-size: 1.15rem; line-height: 1.4; font-style: italic }
  .m4-card .who { margin-top: auto; color: var(--muted); font-size: .85rem }
  .m4-card .button { margin-top: auto; justify-content: center }
  .m4-card .m-rank a { padding: 7px 0 }
  .m4-dots { display: flex; justify-content: center; gap: 6px; margin-top: 10px }
  .m4-dots i { width: 7px; height: 7px; border-radius: 50%; background: var(--line) }
  .m4-dots i.on { background: var(--brand) }
  .m4-vs { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-top: 6px }
  .m4-vs > div { border-top: 3px solid var(--line); padding-top: 8px }
  .m4-vs .m-k { min-height: 2.6em }
  .m4-vs .m-num { font-size: 2.6rem }
  .m4-vs > div:first-child .m-num { color: var(--brand) }
  .mapframe-box { height: 70svh; min-height: 400px }
  .maphero .mapnote { font-size: .85rem }
}""",
    before_map="""<section class="m-only m4" aria-label="La crisis en cuatro tarjetas" data-ancla>
  <div class="m4-track" id="m4-track">
    <article class="m4-card"><p class="m-k">¿Hay agua en tu colonia?</p><div class="m-num" id="m4-num">—</div><p>colonias llevan <strong>una semana o más sin agua</strong>, según medios y vecinos.</p><p class="who">Desliza para ver más →</p></article>
    <article class="m4-card"><div class="m4-vs"><div><p class="m-k">Lo que prometió el SIAPA</p><div class="m-num">1</div>día de corte «por máximo»</div><div><p class="m-k">La realidad</p><div class="m-num" id="m4-max">—</div>días sin agua, lo más largo que publica un medio</div></div><p class="who">Fuente: <a href="https://rotaciondeserviciosiapa.jalisco.gob.mx/" rel="noopener">página de la rotación del SIAPA</a></p></article>
    <article class="m4-card"><h3>Por municipio</h3><ol class="m-rank" id="m4-munis"></ol></article>
    <article class="m4-card"><h3>¿Y en tu colonia?</h3><p>Cada reporte es una prueba de dónde falla el gobierno. Sin cuenta y anónimo.</p><a class="button" href="/reportes?reportar=1">Reportar mi colonia</a><p><a href="/exige">Exígele a quien le toca →</a></p></article>
  </div>
  <div class="m4-dots" id="m4-dots" aria-hidden="true"></div>
</section>""",
    after_map="",
    frame_css=MAP_ONLY,
    map_only=True,
    js="""
aguaM.datos.then((d) => {
  document.getElementById("m4-num").textContent = aguaM.fmt(d.semana);
  document.getElementById("m4-max").textContent = d.max;
  document.getElementById("m4-munis").innerHTML = d.munis.slice(0, 5).map(([m, n]) => `<li><a href="/reportes"><b>${m}</b><span class="d">${n}</span><small>colonias con publicaciones</small></a></li>`).join("");
});
const track = document.getElementById("m4-track"), dots = document.getElementById("m4-dots");
dots.innerHTML = [...track.children].map(() => "<i></i>").join("");
const mark = () => { const i = Math.round(track.scrollLeft / (track.children[1].offsetLeft - track.children[0].offsetLeft)); [...dots.children].forEach((d, j) => d.classList.toggle("on", i === j)); };
track.addEventListener("scroll", mark, { passive: true }); mark();""",
)

V["m5"] = dict(
    head='<link rel="stylesheet" href="/vendor/leaflet-1.9.4/leaflet.css">\n<script src="/vendor/leaflet-1.9.4/leaflet.js"></script>\n<script src="/mapa.js"></script>',
    css="""
:root { --s1: #f59d8b; --s2: #ea6d56; --s3: #cc361e; --s4: #90200e }
@media (prefers-color-scheme: dark) { :root { --s1: #993b2b; --s2: #cb4832; --s3: #ea6d56; --s4: #fca391 } .m5-map .leaflet-tile-pane { filter: invert(1) hue-rotate(180deg) brightness(.9) contrast(.9) } .m5-map.leaflet-container { background: #0c1e2c } }
@media (max-width: 760px) {
  .m5 { margin: 0 -16px 14px }
  .m5-track { display: flex; gap: 10px; overflow-x: auto; scroll-snap-type: x mandatory; padding: 4px 16px; scrollbar-width: none }
  .m5-card { position: relative; flex: 0 0 84%; scroll-snap-align: center; border: 3px double var(--zc, var(--brand)); border-radius: 6px; background: var(--subtle); overflow: hidden }
  .m5-card a { display: block }
  .m5-map { display: block; width: 100%; aspect-ratio: 4 / 5; pointer-events: none; background: var(--subtle) }
  .m5-map .leaflet-control-attribution { font-size: 9px }
  .m5-b { display: grid; place-items: center; border-radius: 50%; border: 1px solid #fff; font: 700 9px/1 system-ui, sans-serif; color: #fff; box-shadow: 0 1px 3px rgb(0 0 0 / .35) }
  .m5-b.l { color: #3b0d05 }
  .m5-tag { position: absolute; z-index: 1000; left: 10px; top: 10px; font-size: .78rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; background: var(--zc, var(--fg)); color: #fff; padding: 3px 8px; border-radius: 4px; pointer-events: none }
  .m5-dots, .m4-dots { display: flex; justify-content: center; gap: 6px; margin-top: 10px }
  .m5-dots i, .m4-dots i { width: 7px; height: 7px; border-radius: 50%; background: var(--line) }
  .m5-dots i.on, .m4-dots i.on { background: var(--brand) }
}
@media (max-width: 760px) { .maphero { display: none } }
""" + V["m4"]["css"].replace("  .mapframe-box { height: 70svh; min-height: 400px }\n", "  .mapframe-box { height: 70svh; min-height: 400px }\n"),
    before_map="""<section class="m-only m5" aria-label="Las zonas del SIAPA en el mapa">
  <div class="m5-track" id="m5-track"><article class="m5-card"><div class="m5-map"></div></article></div>
  <div class="m5-dots" id="m5-dots" aria-hidden="true"></div>
</section>
    """ + V["m4"]["before_map"].replace(" data-ancla>", ">"),
    after_map="",
    frame_css="",
    lazy_frame=True,
    js=r"""
// On a phone m5 stays where the visitor lands: no scroll down to the map.
if (aguaM.phone) document.documentElement.dataset.quieto = "";
if (aguaM.phone) Promise.all([fetch(aguaMapa.DATA).then((r) => r.json()), aguaM.datos]).then(([topo, d]) => {
  const g = aguaMapa.decode(topo), pubs = new Map(d.cols.map((c) => [c.k, c]));
  // Colour and size both follow the colonia's reports: the more, the bigger and the deeper red, in either theme.
  const STEP = (n) => n >= 15 ? 4 : n >= 5 ? 3 : n >= 2 ? 2 : 1, RED = [, "#f59d8b", "#ea6d56", "#cc361e", "#90200e"];
  const zc = (z) => aguaMapa.COLORS[window.aguaDark && aguaDark() ? "dark" : "light"][z];
  // The badge sits at the middle of the colonia's biggest ring.
  const mid = (f) => {
    const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
    const r = polys.map((p) => p[0]).sort((a, b) => b.length - a.length)[0];
    return [r.reduce((t, p) => t + p[1], 0) / r.length, r.reduce((t, p) => t + p[0], 0) / r.length];
  };
  const mine = (n) => g.colonias.filter((f) => aguaMapa.zones(f.properties).main.includes(n))
    .map((f) => ({ f, pub: pubs.get(`${f.properties.n}|${f.properties.m}|${f.properties.cp}`) })).filter((c) => c.pub);
  // Each card's map is a still picture: no dragging or zooming, so the cards swipe; a tap opens /mizona.
  const draw = (el, z) => {
    const n = z.properties.z, map = L.map(el, { zoomControl: false, dragging: false, touchZoom: false, scrollWheelZoom: false, doubleClickZoom: false, boxZoom: false, keyboard: false, zoomSnap: 0.25 });
    aguaMapa.tiles(L, map);
    const zone = L.geoJSON(z, { interactive: false, style: { color: zc(n), weight: 3, fillColor: zc(n), fillOpacity: 0.06 } }).addTo(map);
    const cs = mine(n);
    L.geoJSON({ type: "FeatureCollection", features: cs.map((c) => c.f) }, { interactive: false, style: (f) => {
      const c = RED[STEP(pubs.get(`${f.properties.n}|${f.properties.m}|${f.properties.cp}`).n)];
      return { color: c, weight: 1, fillColor: c, fillOpacity: 0.45 };
    } }).addTo(map);
    for (const c of cs) {
      const s = STEP(c.pub.n), px = Math.round(11 + 3.5 * Math.log2(c.pub.n));
      L.marker(mid(c.f), { interactive: false, keyboard: false, zIndexOffset: -c.pub.n, icon: L.divIcon({
        className: "", iconSize: [px, px],
        html: `<span class="m5-b${s < 3 ? " l" : ""}" style="width:${px}px;height:${px}px;background:${RED[s]}">${c.pub.n}</span>`,
      }) }).addTo(map);
    }
    map.fitBounds(zone.getBounds(), { padding: [10, 10] });
  };
  const track = document.getElementById("m5-track"), dots = document.getElementById("m5-dots");
  track.innerHTML = g.zonas.map((z) => { const n = z.properties.z; return `<article class="m5-card" style="--zc:${zc(n)}"><a href="/mizona?zona=${n}" aria-label="La zona ${n} en el mapa"><div class="m5-map" data-z="${n}"></div></a><span class="m5-tag">Zona ${n}</span></article>`; }).join("");
  // A card's streets load only once it, or the card beside it, is in view.
  const maps = [...track.querySelectorAll(".m5-map")], done = new Set();
  const near = (i) => { for (const j of [i - 1, i, i + 1]) if (maps[j] && !done.has(j)) { done.add(j); draw(maps[j], g.zonas[j]); } };
  dots.innerHTML = [...track.children].map(() => "<i></i>").join("");
  const mark = () => { const i = Math.round(track.scrollLeft / (track.children[1].offsetLeft - track.children[0].offsetLeft)); [...dots.children].forEach((x, j) => x.classList.toggle("on", i === j)); near(i); };
  track.addEventListener("scroll", mark, { passive: true }); mark();
  // The cards open on zone 3, the one with the most colonias a week or more without water.
  const tres = track.querySelector('[data-z="3"]');
  if (tres) { track.scrollLeft = tres.closest(".m5-card").offsetLeft - track.children[0].offsetLeft; mark(); }
});
""" + V["m4"]["js"],
)

def build(key, v, src):
    s = src
    s = s.replace("<title>", '<meta name="robots" content="noindex">\n<title>', 1)
    s = s.replace("</style>", BASE_CSS + v["css"] + "\n</style>", 1)
    if v.get("head"):
        s = s.replace('<script src="/theme.js"></script>', '<script src="/theme.js"></script>\n' + v["head"], 1)
    if v.get("map_only"):
        assert MUESTRA in s
        s = s.replace(MUESTRA, "", 1)
    if v.get("lazy_frame"):
        s = s.replace('<iframe class="mapframe" src="', '<iframe class="mapframe" data-src="', 1)
    hero = '    <div class="maphero">'
    assert hero in s
    s = s.replace(hero, "    " + v["before_map"] + "\n" + hero, 1) if v["before_map"] else s
    end = re.search(r'(    <div class="maphero">.*?</p>\n    </div>\n)', s, re.S)
    assert end
    if v["after_map"]:
        s = s[: end.end()] + "    " + v["after_map"] + "\n" + s[end.end():]
    js = BASE_JS
    if v.get("lazy_frame"):
        js += '{ const f = document.querySelector(".mapframe"); if (!aguaM.phone) f.src = f.dataset.src; }\n'
    if v["frame_css"]:
        js += "aguaM.frame(" + repr(v["frame_css"]).replace("\\n", "\\n") + ");\n"
    js += v["js"]
    bar = " · ".join(f'<a href="/{k}"{" aria-current=page" if k == key else ""}>{k} {n}</a>' for k, n in NAMES.items())
    tail = f'<script>\n{js}\n</script>\n<nav class="vbar"><a href="/">actual</a> · {bar}</nav>\n'
    # The variant's data script goes before the landing's own scripts, so a lazy frame has its src
    # before the landing's frame script reads it.
    first = s.index("<script>", s.index("</main>"))
    return s[:first] + tail + s[first:]


def main():
    # The landing became m5 on phones; the variants build from the landing as it was before.
    src = (Path(__file__).parent / "index-before-m5.html").read_text()
    for key, v in V.items():
        (WEB / f"{key}.html").write_text(build(key, v, src))
        print("wrote", key)


if __name__ == "__main__":
    main()
