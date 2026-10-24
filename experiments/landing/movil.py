"""Writes the phone variants of the landing, web/m1.html … web/m5.html, from web/index.html.

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
  .m4-vs div { border-top: 3px solid var(--line); padding-top: 6px }
  .m4-vs .m-num { font-size: 2.6rem }
  .m4-vs div:first-child .m-num { color: var(--brand) }
  .mapframe-box { height: 70svh; min-height: 400px }
  .maphero .mapnote { font-size: .85rem }
}""",
    before_map="""<section class="m-only m4" aria-label="La crisis en seis tarjetas" data-ancla>
  <div class="m4-track" id="m4-track">
    <article class="m4-card"><p class="m-k">¿Hay agua en tu colonia?</p><div class="m-num" id="m4-num">—</div><p>colonias llevan <strong>una semana o más sin agua</strong>, según medios y vecinos.</p><p class="who">Desliza para ver más →</p></article>
    <article class="m4-card"><p class="m-k">Lo que prometió el SIAPA</p><div class="m4-vs"><div><div class="m-num">1</div>día «por máximo», dijo el SIAPA</div><div><div class="m-num" id="m4-max">—</div>días sin agua, lo más largo que publica un medio</div></div><p class="who">Fuente: <a href="https://rotaciondeserviciosiapa.jalisco.gob.mx/" rel="noopener">página de la rotación del SIAPA</a></p></article>
    <article class="m4-card"><h3>Las que llevan más días</h3><ol class="m-rank" id="m4-rank"></ol></article>
    <article class="m4-card" id="m4-voz"><p class="m-k">Lo que publican los vecinos</p></article>
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
  document.getElementById("m4-rank").innerHTML = aguaM.rank(d.peores, 4, d.peores[0].dias);
  document.getElementById("m4-munis").innerHTML = d.munis.slice(0, 5).map(([m, n]) => `<li><a href="/reportes"><b>${m}</b><span class="d">${n}</span><small>colonias con publicaciones</small></a></li>`).join("");
  const v = d.pubs.filter((e) => e.fuente === "vecinos" && e.cita && e.cita.length < 180 && e.dias >= 7).sort((a, b) => b.fecha.localeCompare(a.fecha))[0];
  if (v) {
    const card = document.getElementById("m4-voz"), dia = new Date(v.fecha + "T12:00").toLocaleDateString("es-MX", { day: "numeric", month: "long" });
    const q = document.createElement("q"); q.textContent = v.cita;
    const who = document.createElement("p"); who.className = "who";
    who.append(`${v.lugar} · ${dia} · `);
    const a = document.createElement("a"); a.href = v.url; a.rel = "noopener"; a.textContent = "ver la publicación"; who.append(a);
    card.append(q, who);
  }
});
const track = document.getElementById("m4-track"), dots = document.getElementById("m4-dots");
dots.innerHTML = [...track.children].map(() => "<i></i>").join("");
const mark = () => { const i = Math.round(track.scrollLeft / (track.children[1].offsetLeft - track.children[0].offsetLeft)); [...dots.children].forEach((d, j) => d.classList.toggle("on", i === j)); };
track.addEventListener("scroll", mark, { passive: true }); mark();""",
)

V["m5"] = dict(
    head='<script src="/mapa.js"></script>',
    css="""
:root { --s1: #f59d8b; --s2: #ea6d56; --s3: #cc361e; --s4: #90200e }
@media (prefers-color-scheme: dark) { :root { --s1: #993b2b; --s2: #cb4832; --s3: #ea6d56; --s4: #fca391 } }
@media (max-width: 760px) {
  .m5 { margin: 0 -16px 18px }
  .m5-track { display: flex; gap: 10px; overflow-x: auto; scroll-snap-type: x mandatory; padding: 4px 16px; scrollbar-width: none }
  .m5-card { flex: 0 0 86%; scroll-snap-align: center; display: flex; flex-direction: column; border: 3px double var(--zc, var(--brand)); border-radius: 6px; background: var(--surface); overflow: hidden }
  .m5-map { display: block; width: 100%; aspect-ratio: 4 / 3; background: var(--subtle); border-bottom: 1px solid var(--line) }
  .m5-map path { vector-effect: non-scaling-stroke }
  .m5-body { padding: 12px 14px 14px; display: flex; flex-direction: column; flex: 1 }
  .m5-body h3 { font-size: 1.3rem; margin: 0; font-style: italic; font-weight: 400 }
  .m5-body h3 small { font-style: normal; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); margin-left: 6px }
  .m5-body p { margin: 6px 0 0; font-size: .95rem }
  .m5-hoy { display: inline-block; font-size: .7rem; font-weight: 700; letter-spacing: .06em; text-transform: uppercase; background: var(--fg); color: var(--bg); padding: 2px 6px; border-radius: 4px; margin-left: 6px; vertical-align: 2px }
  .m5-big { font: 800 2.2rem/1 var(--serif, Georgia, serif); color: var(--s3); font-variant-numeric: tabular-nums }
  .m5-body .m-rank a { padding: 6px 0 }
  .m5-body .more { margin-top: auto; padding-top: 10px; font-size: .9rem }
  .m5-key { display: flex; gap: 10px; flex-wrap: wrap; font-size: .75rem; color: var(--muted); margin: 8px 0 0; padding: 0; list-style: none }
  .m5-key i { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: 4px; vertical-align: -1px }
  .m5-dots { display: flex; justify-content: center; gap: 6px; margin-top: 10px }
  .m5-dots i { width: 7px; height: 7px; border-radius: 50%; background: var(--line) }
  .m5-dots i.on { background: var(--brand) }
  .mapframe-box { height: 70svh; min-height: 400px }
  .maphero .mapnote { font-size: .85rem }
}""",
    before_map="""<section class="m-only m5" aria-label="La crisis zona por zona" data-ancla>
  <div class="m5-track" id="m5-track"><article class="m5-card"><div class="m5-map"></div><div class="m5-body"><p>Cargando las zonas…</p></div></article></div>
  <div class="m5-dots" id="m5-dots" aria-hidden="true"></div>
</section>""",
    after_map="",
    frame_css=MAP_ONLY,
    map_only=True,
    js=r"""
if (aguaM.phone) Promise.all([
  fetch(aguaMapa.DATA).then((r) => r.json()), aguaM.datos,
  fetch("https://api.aguagdl.com/v1/zones").then((r) => r.json()).catch(() => []),
]).then(([topo, d, api]) => {
  const g = aguaMapa.decode(topo), pubs = new Map(d.cols.map((c) => [c.k, c]));
  const K = Math.cos(20.65 * Math.PI / 180), px = ([x, y]) => [x * K, -y];
  const SEV = (n) => n >= 14 ? 4 : n >= 7 ? 3 : n >= 3 ? 2 : n >= 1 ? 1 : 0;
  const dark = () => window.aguaDark && aguaDark();
  const zc = (z) => aguaMapa.COLORS[dark() ? "dark" : "light"][z];
  // Each shape is projected once into a path; every card's map only changes its viewBox.
  const shape = (f) => {
    const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, dpath = "";
    for (const poly of polys) for (const ring of poly) {
      dpath += ring.map((p, i) => { const [x, y] = px(p); x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); return (i ? "L" : "M") + x.toFixed(5) + " " + y.toFixed(5); }).join("") + "Z";
    }
    return { f, d: dpath, box: [x0, y0, x1, y1] };
  };
  const cols = g.colonias.map(shape), zonas = g.zonas.map(shape);
  for (const c of cols) { const p = c.f.properties; c.pub = pubs.get(`${p.n}|${p.m}|${p.cp}`); c.zs = aguaMapa.zones(p).main; }
  const fit = (box) => {
    let [x0, y0, x1, y1] = box, w = x1 - x0, h = y1 - y0;
    const pad = 0.08; x0 -= w * pad; x1 += w * pad; y0 -= h * pad; y1 += h * pad; w = x1 - x0; h = y1 - y0;
    if (w / h > 4 / 3) { const nh = w * 3 / 4; y0 -= (nh - h) / 2; h = nh; } else { const nw = h * 4 / 3; x0 -= (nw - w) / 2; w = nw; }
    return [x0, y0, w, h];
  };
  const meets = (b, [x, y, w, h]) => b[2] >= x && b[0] <= x + w && b[3] >= y && b[1] <= y + h;
  const fill = (c) => c.pub ? (c.pub.dias ? `var(--s${SEV(c.pub.dias)})` : "var(--s1)") : "var(--surface)";
  const map = (vb, zs, href, label) => {
    const inView = cols.filter((c) => meets(c.box, vb));
    return `<a href="${href}" aria-label="${label}"><svg class="m5-map" viewBox="${vb.join(" ")}" preserveAspectRatio="xMidYMid slice" role="img">`
      + `<g stroke="var(--line)" stroke-width=".5">${inView.map((c) => `<path d="${c.d}" fill="${fill(c)}"${c.pub ? "" : ' fill-opacity=".6"'}/>`).join("")}</g>`
      + zonas.filter((z) => zs.includes(z.f.properties.z)).map((z) => `<path d="${z.d}" fill="${zc(z.f.properties.z)}" fill-opacity=".08" stroke="${zc(z.f.properties.z)}" stroke-width="2.5"/>`).join("")
      + `</svg></a>`;
  };
  const hoy = new Date().toLocaleDateString("en-CA", { timeZone: "America/Mexico_City" });
  const days = new Map(api.map((z) => [z.zone, z]));
  const all = [1, 2, 3, 4, 5, 6, 7];
  const box = zonas.reduce((b, z) => [Math.min(b[0], z.box[0]), Math.min(b[1], z.box[1]), Math.max(b[2], z.box[2]), Math.max(b[3], z.box[3])], [Infinity, Infinity, -Infinity, -Infinity]);
  const key = `<ul class="m5-key"><li><i style="background:var(--s1)"></i>1–2 días</li><li><i style="background:var(--s2)"></i>3–6</li><li><i style="background:var(--s3)"></i>7–13</li><li><i style="background:var(--s4)"></i>14 o más</li></ul>`;
  const cards = [`<article class="m5-card">${map(fit(box), all, "/mizona", "Las siete zonas en el mapa")}<div class="m5-body"><p class="m-k">¿Hay agua en tu colonia?</p><div class="m5-big">${aguaM.fmt(d.semana)}</div><p>colonias llevan <strong>una semana o más sin agua</strong>, según medios y vecinos. El SIAPA prometió «por máximo un día».</p>${key}<p class="more">Desliza para ver cada zona →</p></div></article>`];
  const zcards = zonas.map((z) => {
    const n = z.f.properties.z, mine = cols.filter((c) => c.zs.includes(n)), withPub = mine.filter((c) => c.pub);
    const week = withPub.filter((c) => c.pub.dias >= 7).length;
    const top = withPub.map((c) => c.pub).sort((a, b) => b.dias - a.dias || b.n - a.n);
    const info = days.get(n), cut = info && info.next[0] === hoy;
    const html = `<article class="m5-card" style="--zc:${zc(n)}">${map(fit(z.box), [n], `/mizona?zona=${n}`, `La zona ${n} en el mapa`)}<div class="m5-body">`
      + `<h3>Zona ${n}<small>${z.f.properties.nombre}</small>${cut ? '<span class="m5-hoy">Hoy hay corte</span>' : ""}</h3>`
      + (info ? `<p>Cortes: ${aguaMapa.joinES(info.days)}</p>` : "")
      + `<p><span class="m5-big">${week}</span> de sus ${mine.length} colonias llevan una semana o más sin agua · ${withPub.length} con publicaciones</p>`
      + (top.length ? `<ol class="m-rank">${aguaM.rank(top, 3, 0)}</ol>` : "<p>Nadie ha publicado todavía que falte el agua aquí.</p>")
      + `<a class="more" href="/mizona?zona=${n}">Ver la zona ${n} →</a></div></article>`;
    return { week, html };
  }).sort((a, b) => b.week - a.week).map((c) => c.html);
  const end = `<article class="m5-card"><div class="m5-body"><h3>¿Y en tu colonia?</h3><p>Cada reporte es una prueba de dónde falla el gobierno. Sin cuenta y anónimo.</p><a class="button" href="/reportes?reportar=1" style="justify-content:center;margin-top:12px">Reportar mi colonia</a><p><a href="/exige">Exígele a quien le toca →</a></p><p><a href="/avisos">Recibe avisos de los cortes de tu zona →</a></p></div></article>`;
  const track = document.getElementById("m5-track"), dots = document.getElementById("m5-dots");
  track.innerHTML = [...cards, ...zcards, end].join("");
  dots.innerHTML = [...track.children].map(() => "<i></i>").join("");
  const mark = () => { const i = Math.round(track.scrollLeft / (track.children[1].offsetLeft - track.children[0].offsetLeft)); [...dots.children].forEach((x, j) => x.classList.toggle("on", i === j)); };
  track.addEventListener("scroll", mark, { passive: true }); mark();
});""",
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
    src = (WEB / "index.html").read_text()
    for key, v in V.items():
        (WEB / f"{key}.html").write_text(build(key, v, src))
        print("wrote", key)


if __name__ == "__main__":
    main()
