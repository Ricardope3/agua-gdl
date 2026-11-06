"""Writes ten noindex «historias» variants: /fotos' photos as stories, by colonia, in the map or on the landing.

    python3 experiments/historias/build.py --force

/historias-1 … /historias-10 are web/index.html plus one idea and a bar to switch between them. Variants 1–5 live in
the map: their landing frame loads /historias-mapa-N, a copy of web/reportes.html with two hooks (window.__mapa and
window.__select) and the idea added. Photos come from pipelines/fotos.py's reviewed list. Writes straight into web/
(public on push), hence --force. Retire them like the other variants once one is ported.
"""
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
sys.path.insert(0, str(ROOT / "pipelines"))
import fotos  # noqa: E402

E = html.escape
TS, _, _ = fotos.tiles()
N = len(TS)


def ph(t):
    return {"i": "/" + t["img"], "r": round(t["w"] / t["h"], 3), "f": t["fecha"], "d": fotos.fecha_corta(t["fecha"]),
            "ks": t["colonias"], "cs": t["cols"], "q": t["quien"], "u": t["url"], "t": t["tema"], "v": t["video"], "a": t["alt"]}


DATA = "<script>window.FOTOS = " + json.dumps([ph(t) for t in TS], ensure_ascii=False, separators=(",", ":")) + ";</script>"

# Shared: story rings, the story viewer (autoplay, progress bars, hold to pause, swipe, groups) and grouping helpers.
CORE_CSS = """
.hring { --s: 68px; background: none; border: 0; padding: 0; cursor: pointer; display: grid; justify-items: center; gap: 4px; width: calc(var(--s) + 14px); color: inherit; font: inherit; position: relative; flex: 0 0 auto }
.hring .o { width: var(--s); height: var(--s); border-radius: 50%; padding: 3px; background: conic-gradient(#dc2626, #f59e0b, #0284c7, #dc2626) }
.hring.visto .o { background: #9ca3af }
.hring .o img { width: 100%; height: 100%; object-fit: cover; border-radius: 50%; border: 3px solid var(--bg, #fff); display: block }
.hring .n { font-size: .74rem; line-height: 1.2; text-align: center; max-width: calc(var(--s) + 14px); overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical }
.hring .k { position: absolute; top: 0; right: 2px; background: #dc2626; color: #fff; font-size: .66rem; font-weight: 700; border-radius: 999px; padding: 1px 6px }
.hrow { display: flex; gap: 12px; overflow-x: auto; scrollbar-width: none; padding: 4px 2px 6px; scroll-snap-type: x proximity }
.hrow > * { scroll-snap-align: start }
.hvisor { position: fixed; inset: 0; z-index: 3000; background: rgb(6 10 20 / .97); color: #fff; display: grid; grid-template-rows: auto auto 1fr auto; font-family: var(--font, system-ui); user-select: none }
.hvisor[hidden] { display: none }
.hvisor .bars { display: flex; gap: 3px; padding: 10px 12px 0 } .hvisor .bars i { flex: 1; height: 3px; background: rgb(255 255 255 / .28); border-radius: 2px; overflow: hidden } .hvisor .bars i b { display: block; height: 100%; width: 0; background: #fff }
.hvisor .top { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; gap: 8px }
.hvisor .top b { font-size: 1rem } .hvisor .top small { opacity: .75; margin-left: 6px } .hvisor .x { background: none; border: 0; color: #fff; font-size: 1.9rem; line-height: 1; cursor: pointer; padding: 0 6px }
.hvisor .stage { position: relative; display: grid; place-items: center; min-height: 0; padding: 0 8px }
.hvisor .stage img { max-width: min(100%, 720px); max-height: 100%; object-fit: contain; border-radius: 8px }
.hvisor .play { position: absolute; width: 56px; height: 56px; border-radius: 50%; background: rgb(0 0 0 / .55); pointer-events: none } .hvisor .play::after { content: ""; position: absolute; left: 21px; top: 16px; border: 12px solid transparent; border-left: 18px solid #fff; border-right: 0 }
.hvisor .prev, .hvisor .next { position: absolute; top: 0; bottom: 0; width: 38%; background: none; border: 0; cursor: pointer }
.hvisor .prev { left: 0 } .hvisor .next { right: 0 }
.hvisor .foot { padding: 10px 14px 18px; display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px 14px; font-size: .88rem }
.hvisor .foot a, .hvisor .foot button.mapa { color: #fff; font-weight: 600; white-space: nowrap; background: none; border: 0; font: inherit; text-decoration: underline; cursor: pointer; padding: 0 }
.hvar { font-size: .85rem; color: var(--muted); margin: 0 0 6px }
.vbar { position: fixed; left: 50%; bottom: 12px; transform: translateX(-50%); z-index: 2000; display: flex; gap: 4px; max-width: calc(100vw - 16px); overflow-x: auto; scrollbar-width: none; padding: 5px; border-radius: 999px; background: var(--surface); border: 1px solid var(--line); box-shadow: 0 4px 18px rgb(0 0 0 / .18); font-family: var(--font) }
.vbar a { white-space: nowrap; padding: 6px 11px; border-radius: 999px; font-size: .82rem; color: var(--fg); text-decoration: none }
.vbar a:hover { background: var(--subtle) } .vbar a[aria-current] { background: var(--primary); color: var(--on-primary) }
body { padding-bottom: 64px }
"""

CORE_JS = r"""<script>
(() => {
  const F = window.FOTOS;
  const nombre = (k) => { const [n, m] = k.split('|'); return n.split(' ').map((w, i) => i && /^(de|del|la|las|los|el|y|en)$/i.test(w) ? w.toLowerCase() : w[0] + w.slice(1).toLowerCase()).join(' '); };
  // Groups of photos by colonia key, newest first; a group's cover is a sign photo if it has one.
  const porColonia = () => {
    const g = new Map();
    for (const p of F) for (const k of p.ks) { if (!g.has(k)) g.set(k, []); g.get(k).push(p); }
    return [...g].map(([k, ps]) => ({ k, nombre: nombre(k), muni: k.split('|')[1], ps, cover: ps.find((p) => p.t === 'protesta') || ps[0] }))
      .sort((a, b) => b.ps.length - a.ps.length || a.nombre.localeCompare(b.nombre));
  };
  const visto = new Set();
  const ring = (g, size) => {
    const b = document.createElement('button');
    b.type = 'button'; b.className = 'hring' + (visto.has(g.k) ? ' visto' : ''); if (size) b.style.setProperty('--s', size + 'px');
    b.innerHTML = '<span class="o"><img alt="" loading="lazy"></span><span class="n"></span><span class="k"></span>';
    b.querySelector('img').src = g.cover.i; b.querySelector('.n').textContent = g.nombre; b.querySelector('.k').textContent = g.ps.length;
    b.setAttribute('aria-label', 'Ver ' + g.ps.length + (g.ps.length === 1 ? ' foto de ' : ' fotos de ') + g.nombre);
    b.dataset.k = g.k;
    return b;
  };
  let v, timer, raf, t0, paused = false, left = 0;
  const DUR = 5000;
  // groups: [{k, nombre, ps}], gi: group index, i: photo index; opts.onMapa(group) adds «Ver en el mapa».
  const abrir = (groups, gi = 0, i = 0, opts = {}) => {
    if (!v) {
      v = document.createElement('div'); v.className = 'hvisor'; v.setAttribute('role', 'dialog'); v.setAttribute('aria-modal', 'true');
      v.innerHTML = '<div class="bars"></div><div class="top"><b></b><button class="x" aria-label="Cerrar">×</button></div><div class="stage"><img alt=""><span class="play" hidden></span><button class="prev" aria-label="Anterior"></button><button class="next" aria-label="Siguiente"></button></div><div class="foot"><span class="c"></span><span><button class="mapa" type="button" hidden>Ver en el mapa</button> &nbsp; <a target="_blank" rel="noopener">Ver la publicación</a></span></div>';
      document.body.append(v);
    }
    const last = document.activeElement;
    const g = () => groups[gi];
    const tick = () => {
      const p = Math.min(1, (performance.now() - t0) / DUR);
      const bar = v.querySelectorAll('.bars b')[i]; if (bar) bar.style.width = p * 100 + '%';
      if (p >= 1) return go(1);
      raf = requestAnimationFrame(tick);
    };
    const start = (rest = DUR) => { cancelAnimationFrame(raf); t0 = performance.now() - (DUR - rest); if (!matchMedia('(prefers-reduced-motion: reduce)').matches) raf = requestAnimationFrame(tick); };
    const show = () => {
      const G = g(), p = G.ps[i];
      visto.add(G.k);
      document.querySelectorAll('.hring[data-k="' + CSS.escape(G.k) + '"]').forEach((r) => r.classList.add('visto'));
      v.querySelector('.bars').innerHTML = G.ps.map((_, k) => '<i><b style="width:' + (k < i ? 100 : 0) + '%"></b></i>').join('');
      v.querySelector('.top b').innerHTML = ''; v.querySelector('.top b').append(G.nombre, Object.assign(document.createElement('small'), { textContent: (i + 1) + ' de ' + G.ps.length }));
      const img = v.querySelector('.stage img'); img.src = p.i; img.alt = p.a;
      v.querySelector('.play').hidden = !p.v;
      v.querySelector('.c').textContent = p.d + ' · ' + p.q + (p.v ? ' · video' : '');
      v.querySelector('.foot a').href = p.u;
      const m = v.querySelector('.mapa'); m.hidden = !opts.onMapa || !G.k.includes('|');
      m.onclick = () => { cerrar(); opts.onMapa(G); };
      start();
    };
    const go = (d) => {
      i += d;
      if (i >= g().ps.length) { gi++; i = 0; if (gi >= groups.length) return cerrar(); }
      if (i < 0) { gi--; if (gi < 0) { gi = 0; i = 0; } else i = g().ps.length - 1; }
      opts.onGroup?.(g());
      show();
    };
    const cerrar = () => { cancelAnimationFrame(raf); v.hidden = true; document.removeEventListener('keydown', key); opts.onClose?.(); last?.focus?.(); };
    const key = (e) => { if (e.key === 'Escape') cerrar(); if (e.key === 'ArrowRight') go(1); if (e.key === 'ArrowLeft') go(-1); };
    v.querySelector('.prev').onclick = () => go(-1); v.querySelector('.next').onclick = () => go(1); v.querySelector('.x').onclick = cerrar;
    const st = v.querySelector('.stage');
    st.onpointerdown = () => { paused = true; left = DUR - (performance.now() - t0); cancelAnimationFrame(raf); };
    st.onpointerup = st.onpointerleave = () => { if (paused) { paused = false; start(left); } };
    let x0 = null;
    v.ontouchstart = (e) => { x0 = e.touches[0].clientX; };
    v.ontouchend = (e) => { if (x0 === null) return; const dx = e.changedTouches[0].clientX - x0; if (Math.abs(dx) > 50) { gi = Math.max(0, Math.min(groups.length - 1, gi + (dx < 0 ? 1 : -1))); i = 0; show(); } x0 = null; };
    document.addEventListener('keydown', key);
    v.hidden = false; opts.onGroup?.(g()); show(); v.querySelector('.x').focus();
  };
  window.HIST = { F, porColonia, ring, abrir, nombre };
})();
</script>"""

# Inside the /reportes copy: wait for the map and its data, then run the idea.
MAPA_BOOT = r"""<script>
(() => {
  const wait = (fn) => { const t = setInterval(() => { if (window.__mapa && window.__datos && window.__select && window.HIST) { clearInterval(t); fn(window.__mapa, window.__datos); } }, 150); };
  window.HISTMAPA = { wait,
    feat: (k) => (window.__datos.features.get(k) || [])[0],
    centro: (f) => L.geoJSON(f.geometry).getBounds().getCenter(),
    ir: (k) => { const f = (window.__datos.features.get(k) || [])[0]; if (f) window.__select(f); },
    pane: (map) => { if (!map.getPane('historias')) { map.createPane('historias').style.zIndex = 650; } return 'historias'; },
    // The busiest colonias show at city zoom; zooming in reveals the rest.
    escalonar: (map, markers, top) => { const z = () => { const all = map.getZoom() >= 13; markers.forEach((m, i) => { const el = m.getElement(); if (el) el.style.display = all || i < top ? '' : 'none'; }); }; map.on('zoomend', z); z(); } };
})();
</script>"""


def map_v1():
    css = """
.hmark { background: none; border: 0 } .hmark .hring { --s: 46px; width: 46px } .hmark .hring .n { display: none }
.hmark .hring .o { box-shadow: 0 3px 10px rgb(0 0 0 / .35) } .hmark .hring .k { top: -4px; right: -6px }
"""
    js = r"""<script>
HISTMAPA.wait((map) => {
  const groups = HIST.porColonia().filter((g) => HISTMAPA.feat(g.k));
  const layer = L.layerGroup().addTo(map), pane = HISTMAPA.pane(map), ms = [];
  groups.forEach((g, gi) => {
    const icon = L.divIcon({ className: 'hmark', html: '', iconSize: [46, 46], iconAnchor: [23, 23] });
    const m = L.marker(HISTMAPA.centro(HISTMAPA.feat(g.k)), { icon, pane, zIndexOffset: 1000 - gi, keyboard: false }).addTo(layer); ms.push(m);
    m.on('add', () => { const r = HIST.ring(g); m.getElement().append(r); r.onclick = (e) => { e.stopPropagation(); HIST.abrir(groups, gi, 0, { onMapa: (G) => HISTMAPA.ir(G.k) }); }; });
    if (m.getElement()) m.fire('add');
  });
  HISTMAPA.escalonar(map, ms, 20);
});
</script>"""
    return css, js


def map_v2():
    css = """
.hficha { margin: 0 0 10px } .hficha h4 { margin: 0 0 6px; font-size: .78rem; letter-spacing: .1em; text-transform: uppercase; color: var(--alarm, #dc2626) }
.hficha .hrow { gap: 6px } .hficha .th { flex: 0 0 auto; width: 74px; height: 96px; border-radius: 8px; overflow: hidden; border: 0; padding: 0; cursor: pointer; position: relative; background: #000 }
.hficha .th img { width: 100%; height: 100%; object-fit: cover; display: block } .hficha .th::after { content: ""; position: absolute; inset: 0; border-radius: 8px; box-shadow: inset 0 0 0 2px #f59e0b }
"""
    js = r"""<script>
HISTMAPA.wait(() => {
  const groups = HIST.porColonia(), by = new Map(groups.map((g, i) => [g.k, i]));
  const card = document.getElementById('ficha');
  const put = () => {
    if (card.hidden || card.querySelector('.hficha')) return;
    const gi = by.get(window.__key); if (gi === undefined) return;
    const g = groups[gi];
    const box = document.createElement('div'); box.className = 'hficha';
    box.innerHTML = '<h4></h4><div class="hrow"></div>';
    box.querySelector('h4').textContent = g.ps.length === 1 ? '1 foto de esta colonia' : g.ps.length + ' fotos de esta colonia';
    g.ps.forEach((p, i) => { const b = document.createElement('button'); b.type = 'button'; b.className = 'th'; b.setAttribute('aria-label', 'Ver foto ' + (i + 1)); b.innerHTML = '<img alt="">'; b.querySelector('img').src = p.i; b.onclick = () => HIST.abrir([g], 0, i); box.querySelector('.hrow').append(b); });
    const anchor = card.querySelector('h2, h3') || card.firstElementChild;
    anchor ? anchor.after(box) : card.prepend(box);
  };
  new MutationObserver(put).observe(card, { childList: true, subtree: true, attributes: true, attributeFilter: ['hidden'] });
  put();
});
</script>"""
    return css, js


def map_v3():
    css = """
.hrec-btn { position: absolute; z-index: 1300; left: 50%; top: 14px; transform: translateX(-50%); display: flex; align-items: center; gap: 10px; padding: 8px 16px 8px 8px; border-radius: 999px; border: 0; background: #dc2626; color: #fff; font: 600 .95rem/1.2 var(--font); cursor: pointer; box-shadow: 0 6px 18px rgb(0 0 0 / .3) }
.hrec-btn .pila { display: flex } .hrec-btn img { width: 30px; height: 30px; border-radius: 50%; object-fit: cover; border: 2px solid #fff; margin-left: -10px } .hrec-btn img:first-child { margin-left: 0 }
.hrec { position: absolute; z-index: 1300; right: 14px; top: 14px; bottom: 14px; width: min(340px, 44vw); background: #0b1020; color: #fff; border-radius: 12px; display: grid; grid-template-rows: auto auto 1fr auto; overflow: hidden; box-shadow: 0 10px 30px rgb(0 0 0 / .45) }
.hrec[hidden] { display: none }
.hrec .bars { display: flex; gap: 3px; padding: 10px 10px 0 } .hrec .bars i { flex: 1; height: 3px; background: rgb(255 255 255 / .28); border-radius: 2px; overflow: hidden } .hrec .bars b { display: block; height: 100%; width: 0; background: #fff }
.hrec .top { padding: 8px 12px; display: flex; justify-content: space-between; align-items: baseline } .hrec .top b { font-size: 1.05rem } .hrec .top small { opacity: .7 } .hrec .x { background: none; border: 0; color: #fff; font-size: 1.6rem; cursor: pointer }
.hrec .ph { min-height: 0; display: grid; place-items: center; padding: 0 10px } .hrec .ph img { max-width: 100%; max-height: 100%; border-radius: 8px; object-fit: contain }
.hrec .foot { padding: 10px 12px 14px; font-size: .84rem; display: flex; justify-content: space-between; gap: 10px } .hrec .foot a { color: #fff; font-weight: 600 }
.en-recorrido #resumen-mapa, .en-recorrido .map-key, .en-recorrido #linea, .en-recorrido #reporta, .en-recorrido .float-search, .en-recorrido .leaflet-marker-pane { visibility: hidden }
@media (max-width: 760px) { .hrec { left: 10px; right: 10px; top: auto; bottom: 10px; width: auto; height: 46vh } .hrec-btn { top: auto; bottom: 90px } }
"""
    js = r"""<script>
HISTMAPA.wait((map) => {
  const groups = HIST.porColonia().filter((g) => HISTMAPA.feat(g.k)).sort((a, b) => (a.ps.at(-1).f).localeCompare(b.ps.at(-1).f));
  const stage = document.getElementById('escenario');
  const btn = document.createElement('button'); btn.type = 'button'; btn.className = 'hrec-btn';
  btn.innerHTML = '<span class="pila"></span><span>Recorre la crisis, colonia por colonia</span>';
  groups.slice(0, 4).forEach((g) => { const im = document.createElement('img'); im.src = g.cover.i; im.alt = ''; btn.querySelector('.pila').append(im); });
  const box = document.createElement('div'); box.className = 'hrec'; box.hidden = true;
  box.innerHTML = '<div class="bars"></div><div class="top"><span><b></b> <small></small></span><button class="x" aria-label="Detener el recorrido">×</button></div><div class="ph"><img alt=""></div><div class="foot"><span class="c"></span><a target="_blank" rel="noopener">Ver la publicación</a></div>';
  stage.append(btn, box);
  let gi = 0, i = 0, t = null, hl = null;
  const DUR = 3500;
  const show = () => {
    const g = groups[gi], p = g.ps[i];
    if (i === 0) { const f = HISTMAPA.feat(g.k); hl?.remove(); hl = L.geoJSON(f.geometry, { style: { color: '#dc2626', weight: 4, fillColor: '#dc2626', fillOpacity: .25 }, interactive: false }).addTo(map); map.flyToBounds(hl.getBounds(), { maxZoom: 13.5, duration: 1.2, paddingBottomRight: [innerWidth > 760 ? 380 : 0, innerWidth > 760 ? 0 : innerHeight * 0.48] }); }
    box.querySelector('.bars').innerHTML = g.ps.map((_, k) => '<i><b style="width:' + (k < i ? 100 : 0) + '%"></b></i>').join('');
    box.querySelector('.top b').textContent = g.nombre; box.querySelector('.top small').textContent = g.muni + ' · ' + (gi + 1) + ' de ' + groups.length;
    const img = box.querySelector('.ph img'); img.src = p.i; img.alt = p.a;
    box.querySelector('.c').textContent = p.d + ' · ' + p.q; box.querySelector('.foot a').href = p.u;
    const bar = box.querySelectorAll('.bars b')[i]; bar.style.transition = 'none'; bar.style.width = '0'; requestAnimationFrame(() => { bar.style.transition = 'width ' + DUR + 'ms linear'; bar.style.width = '100%'; });
    t = setTimeout(next, i === 0 ? DUR + 900 : DUR);
  };
  const next = () => { i++; if (i >= groups[gi].ps.length) { i = 0; gi++; } if (gi >= groups.length) return stop(); show(); };
  const stop = () => { clearTimeout(t); hl?.remove(); hl = null; box.hidden = true; btn.hidden = false; stage.classList.remove('en-recorrido'); };
  btn.onclick = () => { gi = 0; i = 0; btn.hidden = true; box.hidden = false; stage.classList.add('en-recorrido'); show(); };
  box.querySelector('.x').onclick = stop;
  box.querySelector('.ph').onclick = () => { clearTimeout(t); next(); };
});
</script>"""
    return css, js


def map_v4():
    css = """
.htira { position: absolute; z-index: 900; left: 50%; transform: translateX(-50%); top: 10px; max-width: min(560px, calc(100% - 820px)); min-width: 260px; background: color-mix(in srgb, var(--surface) 88%, transparent); backdrop-filter: blur(6px); border: 1px solid var(--line); border-radius: 16px; padding: 6px 10px 2px; box-shadow: 0 4px 16px rgb(0 0 0 / .15) }
.htira .hring { --s: 52px } .htira .n { font-size: .68rem }
@media (max-width: 1100px) { .htira { top: auto; bottom: 150px; max-width: calc(100% - 24px) } }
.hvisor { background: rgb(6 10 20 / .6); backdrop-filter: blur(1px) } .hvisor .stage img { max-height: 72%; box-shadow: 0 10px 40px rgb(0 0 0 / .6) }
@media (max-width: 760px) { .htira { top: 66px; bottom: auto } }
"""
    js = r"""<script>
HISTMAPA.wait(() => {
  const groups = HIST.porColonia().filter((g) => HISTMAPA.feat(g.k));
  const box = document.createElement('div'); box.className = 'htira hrow'; box.setAttribute('aria-label', 'Historias por colonia');
  groups.forEach((g, gi) => { const r = HIST.ring(g); r.onclick = () => { HISTMAPA.ir(g.k); setTimeout(() => HIST.abrir(groups, gi, 0, { onGroup: (G) => HISTMAPA.ir(G.k) }), 700); }; box.append(r); });
  document.getElementById('escenario').append(box);
});
</script>"""
    return css, js


def map_v5():
    css = """
.hpol { background: none; border: 0 }
.hpol button { all: unset; cursor: pointer; display: block; background: #fffdf7; padding: 4px 4px 14px; box-shadow: 0 4px 12px rgb(0 0 0 / .35); transform: rotate(var(--rot)); transition: transform .2s; position: relative; width: 64px }
.hpol button:hover, .hpol button:focus-visible { transform: rotate(0) scale(1.6); z-index: 10 }
.hpol img { display: block; width: 64px; height: 56px; object-fit: cover } .hpol span { position: absolute; left: 0; right: 0; bottom: 1px; text-align: center; font: 600 8px/1 var(--font); color: #222; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; padding: 0 3px }
.hpol button::before { content: ""; position: absolute; top: -6px; left: calc(50% - 4px); width: 8px; height: 8px; border-radius: 50%; background: #dc2626; box-shadow: 0 1px 2px rgb(0 0 0 / .5) }
"""
    js = r"""<script>
HISTMAPA.wait((map) => {
  const groups = HIST.porColonia().filter((g) => HISTMAPA.feat(g.k));
  const pane = HISTMAPA.pane(map), ms = [];
  groups.forEach((g, gi) => {
    const rot = ((gi * 37) % 13) - 6;
    const icon = L.divIcon({ className: 'hpol', html: '<button type="button" style="--rot:' + rot + 'deg" aria-label="Fotos de ' + g.nombre.replace(/"/g, '') + '"><img alt="" src="' + g.cover.i + '"><span></span></button>', iconSize: [72, 76], iconAnchor: [36, 6] });
    const m = L.marker(HISTMAPA.centro(HISTMAPA.feat(g.k)), { icon, pane, zIndexOffset: 900 - gi }).addTo(map); ms.push(m);
    m.on('click', () => HIST.abrir(groups, gi, 0, { onMapa: (G) => HISTMAPA.ir(G.k) }));
    const set = () => { const el = m.getElement(); if (el) el.querySelector('span').textContent = g.nombre; };
    m.on('add', set); set();
  });
  HISTMAPA.escalonar(map, ms, 14);
});
</script>"""
    return css, js


# Landing-only ideas: (css, html, anchor, js)
A_HEAD_END = '        <p class="buttons">'
A_AFTER_HEAD = '    <section class="m-only m5"'
A_FORM_END = '      </form>\n    </section>\n    <section class="wall"'


def land_v6():
    css = """
.cartel > div { min-width: 0 } .htitular { margin: 14px 0 0; min-width: 0 }
@media (max-width: 760px) { .htitular { width: calc(100% + 104px) } } .htitular .hring { --s: 58px; color: #fff } .htitular .hring .o img { border-color: #0a1022 }
.htitular p { margin: 0 0 4px; font-size: .8rem; letter-spacing: .1em; text-transform: uppercase; color: #fca5a5 }
"""
    html_ = '<div class="htitular"><p>Lo que se ve en cada colonia</p><div class="hrow" id="hrow"></div></div>\n'
    js = r"""<script>
(() => { const groups = HIST.porColonia(), row = document.getElementById('hrow');
  groups.slice(0, 16).forEach((g, gi) => { const r = HIST.ring(g); r.onclick = () => HIST.abrir(groups, gi); row.append(r); }); })();
</script>"""
    return css, html_, "buttons_after", js


def land_v7():
    css = """
.hpegada { position: fixed; z-index: 1500; left: 0; right: 0; top: 0; background: color-mix(in srgb, var(--bg) 94%, transparent); backdrop-filter: blur(8px); border-bottom: 1px solid var(--line); padding: 6px 12px 0; transform: translateY(-110%); transition: transform .25s }
.hpegada.on { transform: none } .hpegada .hring { --s: 44px } .hpegada .n { font-size: .66rem }
.hpegada .hrow { max-width: 1100px; margin: 0 auto }
@media (prefers-reduced-motion: reduce) { .hpegada { transition: none } }
"""
    html_ = '<div class="hpegada" aria-label="Historias por colonia"><div class="hrow" id="hrow"></div></div>\n'
    js = r"""<script>
(() => { const groups = HIST.porColonia(), row = document.getElementById('hrow'), bar = document.querySelector('.hpegada');
  groups.forEach((g, gi) => { const r = HIST.ring(g); r.onclick = () => HIST.abrir(groups, gi); row.append(r); });
  new IntersectionObserver(([e]) => bar.classList.toggle('on', !e.isIntersecting && e.boundingClientRect.top < 0)).observe(document.querySelector('.headline'));
})();
</script>"""
    return css, html_, "body_start", js


def land_v8():
    css = """
.hmunis { margin: 0 0 26px } .hmunis h2 { font-size: 1.35rem; margin: 0 0 4px } .hmunis .sub { color: var(--muted); margin: 0 0 12px; font-size: .92rem }
.hmunis .hrow { gap: 22px; justify-content: center } .hmunis .hring { --s: 104px } .hmunis .n { font-size: .95rem; font-weight: 700 } .hmunis .k { font-size: .78rem; padding: 2px 8px }
@media (max-width: 560px) { .hmunis .hring { --s: 74px } .hmunis .hrow { justify-content: flex-start; gap: 12px } }
"""
    html_ = (f'<section class="hmunis" aria-labelledby="hm"><h2 id="hm">La crisis, municipio por municipio</h2>'
             f'<p class="sub">Toca un municipio para ver sus fotos colonia por colonia. <a href="/fotos">Ver las {N}</a></p><div class="hrow" id="hrow"></div></section>\n')
    js = r"""<script>
(() => { const row = document.getElementById('hrow'), cols = HIST.porColonia(), m = new Map();
  // One colonia key spans two municipios («San Pedro Tlaquepaque y Guadalajara»): it goes under the first.
  for (const g of cols) { const mu = g.muni.split(' y ')[0]; if (!m.has(mu)) m.set(mu, []); m.get(mu).push(g); }
  const munis = [...m].map(([mu, gs]) => ({ mu, gs, n: gs.reduce((a, g) => a + g.ps.length, 0) })).sort((a, b) => b.n - a.n);
  munis.forEach((M) => {
    const fake = { k: 'mun:' + M.mu, nombre: M.mu, ps: M.gs.flatMap((g) => g.ps), cover: M.gs[0].cover };
    const r = HIST.ring(fake); r.querySelector('.k').textContent = M.n; r.onclick = () => HIST.abrir(M.gs, 0); row.append(r);
  });
})();
</script>"""
    return css, html_, "after_head", js


def land_v9():
    css = """
.hdias { margin: 0 0 26px } .hdias h2 { font-size: 1.35rem; margin: 0 0 4px } .hdias .sub { color: var(--muted); margin: 0 0 12px; font-size: .92rem }
.hdias .hring .n { font-family: var(--serif); font-weight: 700; font-size: .85rem }
"""
    html_ = ('<section class="hdias" aria-labelledby="hd"><h2 id="hd">Día por día</h2>'
             '<p class="sub">Las fotos de cada día, como historias: del más reciente al primero.</p><div class="hrow" id="hrow"></div></section>\n')
    js = r"""<script>
(() => { const row = document.getElementById('hrow'), m = new Map();
  for (const p of HIST.F) { if (!m.has(p.f)) m.set(p.f, []); m.get(p.f).push(p); }
  const groups = [...m].sort((a, b) => b[0].localeCompare(a[0])).map(([f, ps]) => ({ k: 'dia:' + f, nombre: ps[0].d, ps, cover: ps.find((p) => p.t === 'protesta') || ps[0] }));
  groups.forEach((g, gi) => { const r = HIST.ring(g); r.onclick = () => HIST.abrir(groups, gi); row.append(r); });
})();
</script>"""
    return css, html_, "after_head", js


def land_v10():
    css = """
.htuya { margin: 14px 0 0 } .htuya p { margin: 0 0 6px; font-weight: 700 } .htuya p span { font-weight: 400; color: var(--muted); font-size: .88rem }
"""
    html_ = '<div class="htuya"><p>Historias de tu colonia <span id="hn"></span></p><div class="hrow" id="hrow"></div></div>\n'
    js = r"""<script>
(() => { const fold = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();
  const all = HIST.porColonia(), row = document.getElementById('hrow'), n = document.getElementById('hn'), q = document.getElementById('q');
  const draw = () => { const s = fold(q.value);
    const list = s.length < 3 ? all.slice(0, 10) : all.filter((g) => fold(g.nombre).includes(s));
    n.textContent = s.length < 3 ? '· las que tienen más fotos; escribe la tuya' : list.length ? '· ' + list.length + (list.length === 1 ? ' colonia' : ' colonias') : '· ninguna foto publicada todavía. Eso no quiere decir que tenga agua.';
    row.innerHTML = ''; list.forEach((g, gi) => { const r = HIST.ring(g); r.onclick = () => HIST.abrir(list, gi); row.append(r); }); };
  q.addEventListener('input', draw); draw(); })();
</script>"""
    return css, html_, "after_form", js


VARIANTS = [
    ("Burbujas en el mapa", "Las colonias con más fotos tienen en el mapa su círculo de historia (al acercarte aparecen todas); al tocarlo, sus fotos se ven una por una.", "map", map_v1),
    ("Fotos en la ficha", "Al abrir una colonia en el mapa, su ficha empieza con sus fotos; cada una abre la historia.", "map", map_v2),
    ("Recorrido", "Un botón en el mapa recorre la crisis colonia por colonia: el mapa vuela a cada una mientras sus fotos pasan al lado.", "map", map_v3),
    ("Tira sobre el mapa", "Una tira de historias flota sobre el mapa; al tocar una, el mapa va a esa colonia y pasan sus fotos.", "map", map_v4),
    ("Polaroids clavadas", "Fotos tipo polaroid clavadas en cada colonia del mapa; crecen al pasar el cursor y abren su historia.", "map", map_v5),
    ("En el titular", "Los círculos de historias van dentro del titular, sobre el muro de fotos.", "land", land_v6),
    ("Barra pegada", "Al bajar por la página, una barra de historias se queda pegada arriba.", "land", land_v7),
    ("Por municipio", "Un círculo grande por municipio; sus fotos pasan colonia por colonia.", "land", land_v8),
    ("Día por día", "Historias por fecha, de la más reciente a la primera, como un diario.", "land", land_v9),
    ("Tu colonia", "En «¿Y en tu colonia?», al escribir aparecen las historias de esa colonia.", "land", land_v10),
]


def bar(k):
    cur = ' aria-current="page"'
    return ('<nav class="vbar" aria-label="Variantes de historias">' + "".join(
        f'<a href="/historias-{i}"{cur if i == k else ""} title="{E(d)}" target="_top">{i} · {E(n)}</a>' for i, (n, d, _, _) in enumerate(VARIANTS, 1)) + "</nav>")


def noindex(s):
    s = re.sub(r'<link rel="canonical"[^>]*>\n', "", s)
    return s.replace("<title>", '<meta name="robots" content="noindex">\n<title>', 1)


def put(s, anchor, text, before=True):
    assert s.count(anchor) == 1, anchor[:50]
    return s.replace(anchor, text + anchor if before else anchor + text)


def build(k, name, desc, kind, fn):
    land = noindex((WEB / "index.html").read_text())
    land = put(land, '    <div class="headline cartel">', f'    <p class="hvar"><b>Variante {k}: {E(name)}.</b> {E(desc)}</p>\n')
    css = CORE_CSS
    if kind == "map":
        mcss, mjs = fn()
        rep = noindex((WEB / "reportes.html").read_text())
        rep = put(rep, '  L.control.zoom({ position: "bottomright" }).addTo(map);', "  window.__mapa = map;\n")
        rep = put(rep, "    window.__datos = { features, ev };\n", "    window.__select = select;\n", before=False)
        rep = put(rep, "</head>", f"<style>{CORE_CSS}{mcss}</style>\n")
        rep = put(rep, "</body>", DATA + CORE_JS + MAPA_BOOT + mjs + "\n")
        (WEB / f"historias-mapa-{k}.html").write_text(rep)
        land = land.replace('data-src="/reportes-portada"', f'data-src="/historias-mapa-{k}"')
        assert f'/historias-mapa-{k}"' in land
        land = put(land, '<p class="mapnote">', f'<p class="hvar" style="text-align:center">La idea está en el mapa de abajo (en el teléfono, ábrelo aquí: <a href="/historias-mapa-{k}">/historias-mapa-{k}</a>).</p>')
        land_js = ""
    else:
        lcss, html_, where, land_js = fn()
        css += lcss
        if where == "buttons_after":
            i = land.index(A_HEAD_END); j = land.index("</p>", i) + 4
            land = land[:j] + "\n        " + html_ + land[j:]
        elif where == "after_head":
            land = put(land, A_AFTER_HEAD, "    " + html_)
        elif where == "after_form":
            assert land.count(A_FORM_END) == 1
            land = land.replace(A_FORM_END, "      </form>\n      " + html_ + "    </section>\n    <section class=\"wall\"")
        elif where == "body_start":
            land = put(land, '<div class="wrap">', html_, before=True)
    land = put(land, "</head>", f"<style>{css}</style>\n")
    land = put(land, "</body>", bar(k) + DATA + CORE_JS + land_js
               + "<script>addEventListener('load', () => { const b = document.querySelector('.vbar'), a = b.querySelector('[aria-current]'); b.scrollLeft = a.offsetLeft - (b.clientWidth - a.offsetWidth) / 2; });</script>\n")
    (WEB / f"historias-{k}.html").write_text(land)


def main():
    if "--force" not in sys.argv:
        sys.exit("historias: writes public pages into web/; rerun with --force")
    for f in WEB.glob("historias-*.html"):
        f.unlink()
    for k, (name, desc, kind, fn) in enumerate(VARIANTS, 1):
        build(k, name, desc, kind, fn)
    print(f"historias: wrote web/historias-1.html … historias-{len(VARIANTS)}.html and their map pages")


if __name__ == "__main__":
    main()
