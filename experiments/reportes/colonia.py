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
}
.ql { position: fixed; inset: 0; z-index: 5000; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 10px; padding: 16px; background: rgb(3 8 20 / 0); -webkit-backdrop-filter: blur(0); backdrop-filter: blur(0); transition: background .25s, backdrop-filter .25s, -webkit-backdrop-filter .25s }
.ql.on { background: rgb(3 8 20 / .45); -webkit-backdrop-filter: blur(14px); backdrop-filter: blur(14px) }
.ql-card { width: min(100%, 440px); max-height: 62vh; overflow: auto; border-radius: 16px; background: var(--surface); color: var(--fg); box-shadow: 0 18px 50px rgb(0 0 0 / .45); transition: transform .38s cubic-bezier(.2, 1.25, .4, 1), opacity .2s }
.ql-card img { display: block; width: 100%; max-height: 34vh; object-fit: cover; background: var(--subtle) }
.ql-body { padding: 14px 16px 16px }
.ql-tit { margin: 0 0 8px; font-weight: 700; font-size: 1.05rem; line-height: 1.3 }
.ql-body q { display: block; font-size: 1.05rem; line-height: 1.45; quotes: "«" "»" }
.ql-body .who, .ql-body .eco { margin: 8px 0 0; font-size: .85rem; color: var(--muted) }
.ql-menu { width: min(100%, 440px); display: flex; gap: 8px; opacity: 0; transform: translateY(-8px) scale(.96); transition: opacity .2s .1s, transform .3s .1s cubic-bezier(.2, 1.25, .4, 1) }
.ql.on .ql-menu { opacity: 1; transform: none }
.ql-menu .button { flex: 1; justify-content: center; padding: 11px 10px }
.ql-menu .ql-go { flex: 1.6; background: #e4572e; color: #fff; font-weight: 700; text-decoration: none }
@media (prefers-reduced-motion: reduce) { .ql, .ql-card, .ql-menu { transition: none } }"""

# Hooks the variants fill: __antes(map, stage) before the map frames the colonia, __ficha(card, e, form)
# once its card is drawn, __cierra(map) when it closes, __pad(size) the phone's framing, __tile the tiles' size.
COMMON = r"""
  const isPhone = () => matchMedia("(max-width: 760px)").matches;
  // The report button and, when wanted, a toggle for the rest of the card, right under its title.
  function acciones(card, e, more) {
    quicklook(card, e);
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
  // A tap on a slide (not on its link) opens it in a quick look, as iOS previews a photo: the slide
  // grows from where it is into a large card over a blurred map, with its actions underneath.
  function quicklook(card, e) {
    if (!e) return;
    const items = [...card.querySelectorAll(".posts li")];
    items.forEach((li, i) => {
      const p = e.posts[i];
      if (!p || li.dataset.ql) return;
      li.dataset.ql = "1";
      li.style.cursor = "pointer";
      li.addEventListener("click", (ev) => { if (!ev.target.closest("a, button")) abre(li, p); });
    });
  }
  const reduce = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  function abre(li, p) {
    const mk = (tag, cls, txt) => { const n = document.createElement(tag); if (cls) n.className = cls; if (txt != null) n.textContent = txt; return n; };
    const link = p.tipo === "comentario" ? (p.red === "x" ? "Ver la respuesta" : "Ver el comentario") : p.red === "web" ? "Leer la nota" : "Ver la publicación";
    const img = p.captura || p.vista || (p.en && p.en.vista);
    const back = mk("div", "ql");
    const box = mk("div", "ql-card");
    box.setAttribute("role", "dialog"); box.setAttribute("aria-modal", "true"); box.setAttribute("aria-label", "Vista previa de la publicación");
    if (img) { const im = mk("img"); im.src = `/${img}`; im.alt = ""; box.append(im); }
    const body = mk("div", "ql-body");
    // The headline, unless the quote already is it.
    if (p.titular && !p.cita.startsWith(p.titular.slice(0, 30))) body.append(mk("p", "ql-tit", p.titular));
    const q = mk("q", null, p.cita);
    body.append(q);
    const who = li.querySelector(".who");
    if (who) { const w = who.cloneNode(true); w.querySelectorAll("a").forEach((a) => a.remove()); w.lastChild && (w.lastChild.textContent = w.lastChild.textContent.replace(/ · $/, "")); body.append(w); }
    li.querySelectorAll(".eco").forEach((x) => body.append(x.cloneNode(true)));
    box.append(body);
    const menu = mk("div", "ql-menu");
    const go = mk("a", "button ql-go", link);
    go.href = p.url; go.target = "_blank"; go.rel = "noopener nofollow";
    const share = mk("button", "button alt", "Compartir");
    share.type = "button";
    share.onclick = () => {
      if (navigator.share) navigator.share({ url: p.url, text: `«${p.cita}»` }).catch(() => {});
      else navigator.clipboard?.writeText(p.url).then(() => { share.textContent = "Enlace copiado"; }).catch(() => {});
    };
    const shut = mk("button", "button alt", "Cerrar");
    shut.type = "button";
    menu.append(go, share, shut);
    back.append(box, menu);
    document.body.append(back);
    // From the slide's own rectangle to the card's, with a spring; the menu follows a beat later.
    const from = li.getBoundingClientRect(), to = box.getBoundingClientRect();
    const anim = !reduce();
    if (anim) {
      box.style.transformOrigin = "0 0";
      box.style.transform = `translate(${from.left - to.left}px, ${from.top - to.top}px) scale(${from.width / to.width}, ${from.height / to.height})`;
    }
    requestAnimationFrame(() => requestAnimationFrame(() => { back.classList.add("on"); box.style.transform = ""; }));
    const prev = document.activeElement;
    go.focus({ preventScroll: true });
    function close() {
      document.removeEventListener("keydown", key);
      back.classList.remove("on");
      if (anim) {
        const now = li.getBoundingClientRect(), r = box.getBoundingClientRect();
        box.style.transform = `translate(${now.left - r.left}px, ${now.top - r.top}px) scale(${now.width / r.width}, ${now.height / r.height})`;
        box.style.opacity = "0";
        setTimeout(() => back.remove(), 280);
      } else back.remove();
      prev?.focus?.({ preventScroll: true });
    }
    const key = (ev) => { if (ev.key === "Escape") close(); };
    document.addEventListener("keydown", key);
    shut.onclick = close;
    back.addEventListener("click", (ev) => { if (ev.target === back) close(); });
  }
  // The card's head on one line: «NAME · Municipio», then only the zone SIAPA puts it in.
  function compacta(card, p) {
    const M = window.aguaMapa, h = card.querySelector("h2"), w = card.querySelector(".where");
    if (!p || !h || !w || h.querySelector("small")) return;
    const ls = M.zonesOf(p.l || ""), zs = ls.length ? ls : M.zones(p).main;
    h.append(" ", Object.assign(document.createElement("small"), { textContent: `· ${p.m}` }));
    w.textContent = zs.length ? `${zs.length > 1 ? "Zonas" : "Zona"} ${M.joinES(zs.map(String))}` : "Sin zona en el mapa del SIAPA";
    // With publications, the zone opens their line: «Zona 5 · 3 fuentes distintas · …».
    const src = card.querySelector(".ev-src");
    if (src) { src.prepend(`${w.textContent} · `); w.hidden = true; }
  }
  const calla = (map) => map.eachLayer((l) => l.closeTooltip && l.closeTooltip());
"""

# /reportes' carousel on phones: a short card over the map whose posts slide sideways.
BASE = ("""
@media (max-width: 760px) {
  .stage .card { bottom: 0; left: 0; width: 100%; max-height: none; overflow: hidden; border-radius: 18px 18px 0 0; padding: 14px 0 12px }
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
  // Framed again once the card is drawn, in the map left above it: the card's height varies with
  // the colonia and with the browser's toolbars.
  // The zoom fits the colonia in that space, but never further out than 14: a small strip of map
  // above a tall card would otherwise zoom out to the whole city.
  window.__refit = (map, b, card) => {
    const size = map.getSize(), top = 76, bottom = card.offsetHeight + 12;
    // The free strip is at least 120 px tall, so a short screen doesn't zoom in without limit.
    const room = Math.max(120, size.y - top - bottom);
    const z = Math.min(16, Math.max(14, map.getBoundsZoom(b, false, L.point(60, size.y - room + 20))));
    // The colonia's centre goes to the middle of the free strip, not of the whole map.
    const free = Math.min(top + room / 2, size.y - bottom - 60);
    const at = map.project(b.getCenter(), z).add([0, size.y / 2 - free]);
    map.flyTo(map.unproject(at, z), z, { duration: 0.5, animate: !matchMedia("(prefers-reduced-motion: reduce)").matches });
  };
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


# Desktop takes on an open colonia (/d1 … /d5). Phones get /reportes' carousel on these pages.
DESK = r"""
  const isDesk = () => !isPhone();
  const mk = (tag, cls, txt) => { const n = document.createElement(tag); if (cls) n.className = cls; if (txt != null) n.textContent = txt; return n; };
  const fecha = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString("es-MX", { day: "numeric", month: "short" }).replace(".", "");
  const hoy = () => new Date().toLocaleDateString("en-CA", { timeZone: "America/Mexico_City" });
  const quien = (q) => q.tipo === "comentario" ? (q.red === "x" ? "Respuesta en X" : "Comentario en Facebook") : q.fuente === "medio" || q.quien ? q.quien : "Vecina o vecino";
  // Each post with its picture above its words (the slide's own, the article's, or the post it's under).
  function imagenes(card, e) {
    if (!e) return;
    [...card.querySelectorAll(".posts li")].forEach((li, i) => {
      const p = e.posts[i], src = p && (p.vista || p.captura || (p.en && p.en.vista));
      if (!src || li.querySelector(".c-img")) return;
      const img = document.createElement("img");
      img.className = "c-img"; img.src = `/${src}`; img.alt = ""; img.loading = "lazy"; img.decoding = "async";
      li.prepend(img);
    });
  }
  // The colonia flown into the part of the map the card leaves free (left, right, above or below it).
  window.__refitD = (map, b, card) => {
    const s = map.getContainer().getBoundingClientRect(), r = card.getBoundingClientRect();
    const room = { left: r.left - s.left, right: s.right - r.right, top: r.top - s.top, bottom: s.bottom - r.bottom };
    const side = Object.keys(room).sort((a, c) => room[c] - room[a])[0], G = 50;
    const pad = side === "left" ? { paddingTopLeft: [G, 90], paddingBottomRight: [s.width - room.left + G, G] }
      : side === "right" ? { paddingTopLeft: [s.width - room.right + G, 90], paddingBottomRight: [G, G] }
      : side === "top" ? { paddingTopLeft: [G, 90], paddingBottomRight: [G, s.height - room.top + G] }
      : { paddingTopLeft: [G, s.height - room.bottom + G], paddingBottomRight: [G, G] };
    map.flyToBounds(b, { ...pad, maxZoom: 16, duration: 0.6, animate: !reduce() });
  };
"""

# What a visitor can do with a colonia, on desktop (/d1 … /d5). Phones get /reportes' carousel.
UTIL = r"""
  // SIAPA's calendar per zone, fetched once.
  let zonasP = null;
  const zonas = () => zonasP || (zonasP = fetch("https://api.aguagdl.com/v1/zones").then((r) => r.json()).then((l) => new Map(l.map((z) => [z.zone, z]))).catch(() => new Map()));
  const zonaDe = (p) => { const M = window.aguaMapa, ls = M.zonesOf(p.l || ""); return ls.length ? ls : M.zones(p).main; };
  const WD = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];
  const wd = (iso) => WD[new Date(`${iso}T12:00:00`).getDay()];
  const largo = (iso) => `${wd(iso)} ${fecha(iso)}`;
  const edad = (e) => Math.round((Date.parse(hoy()) - Date.parse(e.ultima)) / 864e5);
  const ahora = (e) => !e ? ["calma", "Nadie ha publicado que falte el agua aquí."]
    : edad(e) <= 3 ? ["activa", `Hay quejas de los últimos 3 días: la más reciente del ${fecha(e.ultima)}.`]
    : edad(e) <= 7 ? ["reciente", `La última queja es del ${fecha(e.ultima)}, hace ${edad(e)} días.`]
    : ["vieja", `Sin quejas nuevas desde el ${fecha(e.ultima)}. Puede que ya tenga agua: si no, repórtalo.`];
  const nombre = (p) => p.n.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase());
  const link = (href, txt, cls) => { const a = mk("a", cls || "", txt); a.href = href; if (/^https?:/.test(href)) { a.target = "_blank"; a.rel = "noopener"; } return a; };
  function cortes(p, box) {
    const zs = zonaDe(p);
    if (!zs.length) { box.textContent = "El mapa del SIAPA no le da zona de cortes."; return; }
    zonas().then((m) => {
      box.replaceChildren(...zs.map((z) => {
        const i = m.get(z), next = i && i.next.find((d) => d >= hoy());
        return mk("p", "u-z", i ? `Zona ${z}: corta ${window.aguaMapa.joinES(i.days)}. ${next ? (next === hoy() ? "Hoy hay corte." : `Próximo corte: ${largo(next)}.`) : ""}` : `Zona ${z}.`);
      }));
    });
  }
  // The steps, each a row with what it's for.
  function pasos(p, e) {
    const zs = zonaDe(p), z = zs[0], q = new URLSearchParams({ q: p.n, m: p.m, cp: p.cp });
    const rows = [
      ["Reporta cómo está el agua", "Cuatro toques, sin cuenta. Si no se reporta, no queda registro.", () => { const b = mk("button", "button u-rep", "Reportar"); b.type = "button"; b.onclick = () => document.getElementById("reporta-btn").click(); return b; }],
      ["¿Sin agua? Pide una pipa", `Los teléfonos del SIAPA y de ${p.m}, con su fuente.`, () => link("/pipas#municipios", "Ver teléfonos", "button alt")],
      z ? ["Que te avisen antes del corte", `Telegram te avisa dos días antes y la noche anterior (zona ${z}).`, () => link(`https://t.me/AvisoAguaGDLbot?start=z${z}`, "Telegram", "button alt")] : null,
      ["Exígelo", "Arma tu mensaje al SIAPA, la CEA y tu municipio.", () => link(`/exige?${q}`, "Escribir", "button alt")],
    ].filter(Boolean);
    const ol = mk("ol", "u-pasos");
    for (const [t, s, btn] of rows) { const li = mk("li"); const tx = mk("div"); tx.append(mk("b", null, t), mk("span", null, s)); li.append(tx, btn()); ol.append(li); }
    return ol;
  }
  // The colonia's posts as a short list that opens the quick look.
  function pruebas(e, n) {
    const ul = mk("ul", "u-pr");
    for (const q of [...e.posts].sort((a, b) => b.fecha.localeCompare(a.fecha)).slice(0, n)) {
      const li = mk("li"); li.append(mk("small", null, `${fecha(q.fecha)} · ${quien(q)}`), mk("span", null, q.titular || q.cita));
      li.onclick = () => abre(li, q); ul.append(li);
    }
    return ul;
  }
  // Colonias with complaints within 1.5 km, from the page's own data.
  let centros = null;
  function cercanas(f) {
    const d = window.__datos; if (!d) return [];
    if (!centros) { centros = new Map(); for (const [k] of d.ev) { const fs = d.features.get(k); if (fs) centros.set(k, L.geoJSON(fs[0]).getBounds().getCenter()); } }
    const c = L.geoJSON(f).getBounds().getCenter(), me = window.__key;
    return [...centros].filter(([k]) => k !== me).map(([k, ll]) => [k, c.distanceTo(ll)]).filter(([, m]) => m <= 1500).sort((a, b) => a[1] - b[1]).map(([k, m]) => ({ k, m, e: d.ev.get(k) }));
  }
  // A square picture to post: the days, the colonia and the site, drawn on a canvas.
  function imagen(p, e) {
    const c = document.createElement("canvas"); c.width = c.height = 1080;
    const g = c.getContext("2d");
    g.fillStyle = "#0c1328"; g.fillRect(0, 0, 1080, 1080);
    g.fillStyle = "#e4572e"; g.fillRect(0, 0, 1080, 18);
    g.fillStyle = "#a6b1d6"; g.font = "600 40px Georgia, serif"; g.fillText(`${p.m.toUpperCase()} · ${hoy().split("-").reverse().slice(0, 2).join("/")}`, 80, 150);
    g.fillStyle = "#ea6d56"; g.font = "800 230px Georgia, serif"; g.fillText(e && e.dias ? `${e.dias} días` : "Sin agua", 70, 420);
    g.fillStyle = "#eef1fb"; g.font = "italic 700 76px Georgia, serif";
    const words = `${e && e.dias ? "sin agua en " : "en "}${nombre(p)}`.split(" "); let line = "", y = 540;
    for (const w of words) { if (g.measureText(line + w).width > 920) { g.fillText(line, 80, y); line = ""; y += 90; } line += w + " "; }
    g.fillText(line, 80, y);
    g.fillStyle = "#a6b1d6"; g.font = "40px Georgia, serif";
    if (e) g.fillText(`Según ${e.medios} medios y ${e.posts.filter((q) => q.fuente !== "medio").length} publicaciones de vecinos`, 80, y + 90);
    g.fillText("El SIAPA prometió cortes «por máximo un día».", 80, y + 150);
    g.fillStyle = "#7f9cf5"; g.font = "700 46px Georgia, serif"; g.fillText("aguagdl.com/reportes", 80, 1000);
    return c;
  }
  function compartir(p, e) {
    const box = mk("div", "u-share"), c = imagen(p, e), img = mk("img"); img.src = c.toDataURL("image/png"); img.alt = "Imagen para compartir";
    const name = `sin-agua-${p.n.toLowerCase().replace(/[^a-z0-9]+/g, "-")}.png`;
    const dl = link(img.src, "Descargar imagen", "button"); dl.download = name; dl.removeAttribute("target");
    const url = `https://aguagdl.com/reportes?${new URLSearchParams({ q: p.n, m: p.m, cp: p.cp })}`;
    const text = e && e.dias ? `${e.dias} días sin agua en ${nombre(p)}, según medios y vecinos. Míralo y reporta tu colonia:` : `¿Hay agua en ${nombre(p)}? Míralo y reporta tu colonia:`;
    const wa = link(`https://wa.me/?text=${encodeURIComponent(`${text} ${url}`)}`, "WhatsApp", "button alt");
    const x = link(`https://x.com/intent/post?text=${encodeURIComponent(`${text} ${url}`)}`, "X", "button alt");
    const row = mk("div", "u-row"); row.append(dl, wa, x);
    if (navigator.canShare) c.toBlob((b) => { const file = new File([b], name, { type: "image/png" }); if (navigator.canShare({ files: [file] })) { const s = mk("button", "button alt", "Compartir…"); s.type = "button"; s.onclick = () => navigator.share({ files: [file], text, url }).catch(() => {}); row.append(s); } });
    box.append(img, row);
    return box;
  }
  const UCSS = true;
"""

U_CSS = """
@media (min-width: 761px) {
  .stage .card { width: 440px }
  #reporta { display: none !important }
  .stage .card .ev, .stage .card > .button, .stage .card .sub-head, .stage .card .conteo, .stage .card > .c-acc { display: none }
  .u-now { margin: 10px 0 0; padding: 10px 12px; border-radius: 10px; border-left: 5px solid var(--line); background: var(--bg); font-size: .95rem; line-height: 1.4 }
  .u-now.activa { border-color: #cc361e } .u-now.reciente { border-color: #f08c5a } .u-now.vieja, .u-now.calma { border-color: var(--muted) }
  .u-now b { display: block; font-size: .72rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted) }
  .u-h { margin: 16px 0 6px; font-size: .74rem; letter-spacing: .08em; text-transform: uppercase; color: var(--muted); font-weight: 800 }
  .u-z { margin: 0 0 4px; font-size: .95rem }
  .u-pasos { list-style: none; margin: 0; padding: 0; counter-reset: p }
  .u-pasos li { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--line); counter-increment: p }
  .u-pasos li::before { content: counter(p); flex: 0 0 26px; height: 26px; display: grid; place-items: center; border-radius: 50%; background: var(--subtle); font-weight: 800; font-size: .85rem }
  .u-pasos div { flex: 1; min-width: 0 } .u-pasos b { display: block; font-size: .95rem } .u-pasos span { display: block; font-size: .8rem; color: var(--muted); line-height: 1.35 }
  .u-pasos .button { flex: 0 0 auto; padding: 7px 12px; font-size: .85rem; text-decoration: none }
  .u-pasos .u-rep { background: #e4572e; color: #fff; font-weight: 700 }
  .u-pr { list-style: none; margin: 0; padding: 0 }
  .u-pr li { padding: 7px 0; border-bottom: 1px solid var(--line); cursor: pointer }
  .u-pr small { display: block; font-size: .72rem; color: var(--muted) }
  .u-pr span { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; font-size: .9rem; line-height: 1.35 }
  .u-pr li:hover span { color: var(--link) }
  .u-row { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 10px } .u-row .button { text-decoration: none; padding: 8px 12px }
  .u-share img { display: block; width: 100%; border-radius: 10px; margin-top: 6px }
  .u-cal { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px }
  .u-cal div { position: relative; min-height: 46px; padding: 3px 4px; border-radius: 6px; border: 1px solid var(--line); font-size: .72rem; color: var(--muted) }
  .u-cal div.corte { background: color-mix(in srgb, var(--brand) 18%, var(--surface)); border-color: var(--brand) }
  .u-cal div.hoy { outline: 2px solid var(--fg) }
  .u-cal div.futuro { border-style: dashed }
  .u-cal i { position: absolute; right: 4px; bottom: 4px; min-width: 18px; height: 18px; padding: 0 4px; border-radius: 9px; background: #e4572e; color: #fff; font: 700 .7rem/18px var(--font); text-align: center; font-style: normal }
  .u-cal .wd { min-height: 0; border: 0; text-align: center; font-weight: 700; text-transform: uppercase }
  .u-key { margin: 6px 0 0; font-size: .78rem; color: var(--muted) }
  .u-near { list-style: none; margin: 0; padding: 0 }
  .u-near li { display: flex; gap: 8px; align-items: baseline; padding: 6px 0; border-bottom: 1px solid var(--line); font-size: .9rem }
  .u-near a { flex: 1; color: var(--fg); text-decoration: none } .u-near a:hover { color: var(--link) }
  .u-near small { color: var(--muted); font-variant-numeric: tabular-nums }
  .u-dot { width: 10px; height: 10px; border-radius: 50%; flex: 0 0 10px; background: var(--muted) } .u-dot.activa { background: #cc361e } .u-dot.reciente { background: #f08c5a }
  .u-big { margin: 4px 0 0; font-size: 1.05rem; line-height: 1.4 } .u-big b { font-size: 1.5rem; color: #cc361e }
  .u-tabs { display: flex; gap: 4px; margin: 12px 0 0; border-bottom: 1px solid var(--line) }
  .u-tabs button { flex: 1; padding: 8px 4px; border: 0; border-bottom: 3px solid transparent; background: none; color: var(--muted); font: 600 .9rem var(--font); cursor: pointer }
  .u-tabs button[aria-selected="true"] { color: var(--fg); border-color: #e4572e }
}"""

def u(name, js):
    return (name, U_CSS, "\n  window.__tileD = [0, 0];\n" + js)

VD = {
    # What to do now: the state, the zone's next cut, and four steps with their buttons.
    "d1": u("Qué hacer", r"""
  window.__fichaD = (card, e, form, p, f) => {
    compacta(card, p);
    const [k, t] = ahora(e), now = mk("div", `u-now ${k}`); now.append(mk("b", null, "Ahora"), t);
    const cal = mk("div"); cortes(p, cal);
    const kids = [now, mk("p", "u-h", "Cortes del SIAPA"), cal, mk("p", "u-h", "Qué puedes hacer"), pasos(p, e)];
    if (e) kids.push(mk("p", "u-h", `Lo que se publica · ${e.posts.length}`), pruebas(e, 4));
    card.querySelector(".where").after(...kids);
  };
"""),
    # Is it only my colonia? The colonias around it within 1.5 km and how they're doing.
    "d2": u("Alrededor", r"""
  window.__fichaD = (card, e, form, p, f) => {
    compacta(card, p);
    const [k, t] = ahora(e), now = mk("div", `u-now ${k}`); now.append(mk("b", null, "Aquí"), t);
    const near = cercanas(f), act = near.filter((x) => ahora(x.e)[0] === "activa").length;
    const big = mk("p", "u-big"); big.innerHTML = near.length ? `<b>${near.length}</b> colonias a 1.5 km o menos tienen publicaciones de que no hay agua; <b>${act}</b> con quejas de los últimos 3 días.` : "Ninguna colonia a 1.5 km tiene publicaciones de que no hay agua.";
    const ul = mk("ul", "u-near");
    for (const x of near.slice(0, 9)) {
      const [kk] = ahora(x.e), [n, m, cp] = x.k.split("|"), li = mk("li");
      li.append(mk("span", `u-dot ${kk}`), link(`?${new URLSearchParams({ q: n, m, cp })}`, `${nombre({ n })} · ${m}`), mk("small", null, `${x.e.dias ? `${x.e.dias} días · ` : ""}${(x.m / 1000).toFixed(1)} km`));
      ul.append(li);
    }
    const kids = [now, mk("p", "u-h", "Alrededor"), big, ul, mk("p", "u-h", "Qué puedes hacer"), pasos(p, e)];
    card.querySelector(".where").after(...kids);
  };
"""),
    # SIAPA's cut days against the days complaints were published, three weeks at a glance.
    "d3": u("Calendario", r"""
  window.__fichaD = (card, e, form, p, f) => {
    compacta(card, p);
    const grid = mk("div", "u-cal"), note = mk("p", "u-key"), summary = mk("p", "u-big");
    for (const w of ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]) grid.append(mk("div", "wd", w));
    const t = new Date(`${hoy()}T12:00:00`), start = new Date(t); start.setDate(t.getDate() - ((t.getDay() + 6) % 7) - 14);
    const per = new Map(); if (e) for (const q of e.posts) per.set(q.fecha, (per.get(q.fecha) || 0) + 1);
    zonas().then((m) => {
      const zs = zonaDe(p), days = new Set(zs.flatMap((z) => (m.get(z) || { days: [] }).days));
      let fuera = 0, con = 0;
      for (let i = 0; i < 28; i++) {
        const d = new Date(start); d.setDate(start.getDate() + i);
        const iso = d.toLocaleDateString("en-CA"), corte = days.has(WD[d.getDay()]);
        const cell = mk("div", [corte ? "corte" : "", iso === hoy() ? "hoy" : "", iso > hoy() ? "futuro" : ""].join(" "), String(d.getDate()));
        if (per.get(iso)) { const b = mk("i", null, String(per.get(iso))); cell.append(b); con++; if (!corte) fuera++; }
        cell.title = `${largo(iso)}${corte ? " · día de corte según el SIAPA" : ""}${per.get(iso) ? ` · ${per.get(iso)} publicaciones` : ""}`;
        grid.append(cell);
      }
      summary.innerHTML = con ? `Hubo publicaciones de que no hay agua en <b>${con}</b> días; <b>${fuera}</b> de ellos no eran día de corte de su zona.` : "No hay publicaciones de esta colonia en estas semanas.";
      note.textContent = `Azul: día de corte de la zona ${zs.join(" y ")} según el SIAPA. Número: publicaciones de ese día. Punteado: lo que viene.`;
    });
    const kids = [mk("p", "u-h", "Cortes y quejas, día por día"), summary, grid, note, mk("p", "u-h", "Qué puedes hacer"), pasos(p, e)];
    card.querySelector(".where").after(...kids);
  };
"""),
    # Ready to pass on: a square picture with the days, to download or send, and the colonia's link.
    "d4": u("Para compartir", r"""
  window.__fichaD = (card, e, form, p, f) => {
    compacta(card, p);
    const [k, t] = ahora(e), now = mk("div", `u-now ${k}`); now.append(mk("b", null, "Ahora"), t);
    const kids = [now, mk("p", "u-h", "Pásalo a tus vecinos"), compartir(p, e), mk("p", "u-h", "Qué más puedes hacer"), pasos(p, e)];
    card.querySelector(".where").after(...kids);
  };
"""),
    # All of it in tabs: now, what to do, the evidence, around, share.
    "d5": u("Todo en pestañas", r"""
  window.__fichaD = (card, e, form, p, f) => {
    compacta(card, p);
    const near = cercanas(f);
    const panes = {
      "Ahora": () => { const [k, t] = ahora(e), now = mk("div", `u-now ${k}`); now.append(mk("b", null, "Ahora"), t); const cal = mk("div"); cortes(p, cal); return [now, mk("p", "u-h", "Cortes del SIAPA"), cal]; },
      "Qué hacer": () => [pasos(p, e)],
      "Pruebas": () => e ? [mk("p", "u-big", `${e.dias ? `Hasta ${e.dias} días sin agua · ` : ""}${e.fuentes} fuentes, ${e.medios} medios`), pruebas(e, 12)] : [mk("p", null, "Nadie ha publicado que falte el agua aquí.")],
      "Alrededor": () => { const ul = mk("ul", "u-near"); for (const x of near.slice(0, 10)) { const [kk] = ahora(x.e), [n, m, cp] = x.k.split("|"), li = mk("li"); li.append(mk("span", `u-dot ${kk}`), link(`?${new URLSearchParams({ q: n, m, cp })}`, `${nombre({ n })} · ${m}`), mk("small", null, `${(x.m / 1000).toFixed(1)} km`)); ul.append(li); } return [mk("p", "u-big", `${near.length} colonias con publicaciones a 1.5 km o menos.`), ul]; },
      "Compartir": () => [compartir(p, e)],
    };
    const tabs = mk("div", "u-tabs"), body = mk("div");
    tabs.setAttribute("role", "tablist");
    const show = (name) => { for (const b of tabs.children) b.setAttribute("aria-selected", String(b.textContent === name)); body.replaceChildren(...panes[name]()); };
    for (const name of Object.keys(panes)) { const b = mk("button", null, name); b.type = "button"; b.setAttribute("role", "tab"); b.onclick = () => show(name); tabs.append(b); }
    card.querySelector(".where").after(tabs, body);
    show("Ahora");
  };
"""),
}

DNAMES = {k: v[0] for k, v in VD.items()}

DEFAULT = "c1"


AMERICANA = "q=AMERICANA&m=Guadalajara&cp=44100"
GRANJA = "q=CIUDAD+GRANJA&m=Zapopan&cp=45010"


def sub(html, old, new):
    assert html.count(old) == 1, old
    return html.replace(old, new)


CUR = ' aria-current="page"'


def build(src, v, bar=True):
    fam = DNAMES if v in VD else NAMES
    name = fam.get(v)
    if v in VD:
        # The desktop takes ride on /reportes' own phone carousel.
        dv = V[DEFAULT]
        css, js = BASE[0] + dv[1] + VD[v][1], BASE[1] + SLIDES + dv[2] + DESK + UTIL + VD[v][2]
    else:
        css, js = (BASE[0] + V[v][1], BASE[1] + SLIDES + V[v][2]) if v in V else BASE
    links = f'<a href="/reportes?{(GRANJA if v in VD else AMERICANA).replace("&", "&amp;")}">Actual</a>' + "".join(
        f'<a href="/{k}"{CUR if k == v else ""}>{k} {n}</a>' for k, n in fam.items())
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
    return hooks(h, js, americana=GRANJA if v in VD else AMERICANA)


def hooks(h, js, americana=False):
    if not americana:
        h = sub(h, "<body>\n<div class=\"wrap\">", f'<body>\n<script>{COMMON}{js}</script>\n<div class="wrap">')
    # Americana unless the link names a colonia.
    if americana: h = sub(h, "const params = new URLSearchParams(location.search);",
            'if (!new URLSearchParams(location.search).get("q")) history.replaceState(null, "", `${location.pathname}?' + americana + '${location.search.replace(/^\\?/, "&")}`);\n'
            "    const params = new URLSearchParams(location.search);")
    h = sub(h, "    const atEnd = () => at >= DAYS.length - 1;\n", "    const atEnd = () => at >= DAYS.length - 1;\n    window.__datos = { features, ev };\n")
    h = sub(h, "      selected = f;\n", "      selected = f;\n      window.__key = keyOf(f.properties);\n")
    h = sub(h, '      stage.classList.remove("has-card");\n',
            '      stage.classList.remove("has-card");\n      if (window.__cierra) window.__cierra(map);\n')
    h = sub(h, "      if (fit) {\n        // Room around",
            "      if (window.__antes && phone()) window.__antes(map, stage);\n      if (!phone()) for (const g of document.querySelectorAll('.leaflet-tooltip')) g.remove();\n      if (fit) {\n        // Room around")
    h = sub(h, "      renderCard(f, form);\n", "      renderCard(f, form);\n      if (fit && window.__refit && phone()) window.__refit(map, marks[1].getBounds(), card);\n"
               "      else if (fit && window.__refitD && window.__fichaD && !phone()) window.__refitD(map, marks[1].getBounds(), card);\n")
    h = sub(h, "const pad = phone() ? {", "const pad = phone() && window.__pad ? window.__pad(map.getSize()) : !phone() && window.__padD ? window.__padD(map.getSize()) : phone() ? {")
    h = sub(h, "const W = phone() ? 120 : 210, H = phone() ? 90 : 158, G = 8;",
            "const W = phone() ? (window.__tile || [120])[0] : (window.__tileD || [210])[0], H = phone() ? (window.__tile || [0, 90])[1] : (window.__tileD || [0, 158])[1], G = 8;\n"
            "        if (!W) return;")
    h = sub(h, '      stage.classList.add("has-card");\n      setOverview(false);\n',
            '      stage.classList.add("has-card");\n      setOverview(false);\n      if (window.__ficha && phone()) window.__ficha(card, e, openForm, f.properties);\n'
            '      else if (window.__fichaD && !phone()) window.__fichaD(card, e, openForm, f.properties, f);\n')
    return h


def main():
    src = (Path(__file__).parent / "reportes-before-c3.html").read_text()
    for v in [*NAMES, *DNAMES]:
        (WEB / f"{v}.html").write_text(build(src, v))
        print(f"web/{v}.html")
    # /reportes itself takes this variant's carousel on phones.
    (WEB / "reportes.html").write_text(build(src, DEFAULT, bar=False))
    print("web/reportes.html")


if __name__ == "__main__":
    main()
