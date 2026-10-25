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

VD = {
    # A dossier: the colonia's numbers as four figures, then every publication on a dated line, newest first.
    "d1": ("Expediente", """
@media (min-width: 761px) {
  .stage .card { width: 440px }
  #reporta { display: none !important }
  .stage .card .ev, .stage .card > .button, .stage .card .sub-head { display: none }
  .x-stats { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin: 10px 0 0 }
  .x-stats div { padding: 10px 12px; border: 1px solid var(--line); border-radius: 10px; background: var(--bg) }
  .x-stats b { display: block; font: 800 1.7rem/1.05 var(--font); color: var(--s3); font-variant-numeric: tabular-nums }
  .x-stats span { font-size: .8rem; color: var(--muted) }
  .x-crono { list-style: none; margin: 14px 0 0; padding: 0 0 0 14px; border-left: 2px solid var(--line) }
  .x-crono li { position: relative; padding: 0 0 12px 10px; cursor: pointer }
  .x-crono li::before { content: ""; position: absolute; left: -21px; top: 5px; width: 10px; height: 10px; border-radius: 50%; background: #e4572e; box-shadow: 0 0 0 3px var(--surface) }
  .x-crono li.medio::before { background: var(--brand) }
  .x-crono small { display: block; font-size: .74rem; color: var(--muted); text-transform: uppercase; letter-spacing: .04em }
  .x-crono span { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; font-size: .92rem; line-height: 1.35 }
  .x-crono li:hover span { color: var(--link) }
}""", r"""
  window.__tileD = [0, 0];
  window.__fichaD = (card, e, form, p) => {
    compacta(card, p);
    const row = acciones(card, e, false);
    if (!e) return;
    const stats = mk("div", "x-stats");
    stats.innerHTML = `<div><b>${e.dias ?? "—"}</b><span>días sin agua, lo más largo que se publica</span></div><div><b>${e.fuentes}</b><span>fuentes distintas</span></div><div><b>${e.medios}</b><span>${e.medios === 1 ? "medio lo reporta" : "medios lo reportan"}</span></div><div><b>${fecha(e.ultima)}</b><span>la publicación más reciente</span></div>`;
    const list = mk("ol", "x-crono");
    for (const q of [...e.posts].sort((a, b) => b.fecha.localeCompare(a.fecha))) {
      const li = mk("li", q.fuente === "medio" ? "medio" : "");
      li.append(mk("small", null, `${fecha(q.fecha)} · ${quien(q)}`), mk("span", null, q.titular || q.cita));
      li.onclick = () => abre(li, q);
      list.append(li);
    }
    card.querySelector(".where").after(stats);
    stats.after(row, list);
  };
"""),
    # The crisis day by day: a strip with one column per day since the first post, a dot per publication.
    "d2": ("Día por día", """
@media (min-width: 761px) {
  .stage .card { top: auto; left: 12px; right: 12px; bottom: 12px; width: auto; max-height: none; overflow: visible; display: grid; grid-template-columns: 320px minmax(0, 1fr); gap: 0 26px; padding: 16px 20px }
  #reporta { display: none !important }
  .stage .card > .d-head { grid-column: 1 }
  .stage .card .ev .mosaic, .stage .card .ev .posts, .stage .card .ev > .linkbtn, .stage .card .sub-head, .stage .card .conteo, .stage .card .d-head > .button { display: none }
  .x-dias { grid-column: 2; grid-row: 1; display: flex; flex-direction: column; min-width: 0 }
  .x-dias h3 { margin: 0 0 6px; font-size: .75rem; letter-spacing: .06em; text-transform: uppercase; color: var(--muted) }
  .x-cols { display: flex; align-items: flex-end; gap: 4px; height: 150px; border-bottom: 1px solid var(--line) }
  .x-cols div { flex: 1; display: flex; flex-direction: column-reverse; align-items: center; gap: 3px; min-width: 0 }
  .x-cols button { width: 14px; height: 14px; border-radius: 50%; border: 0; padding: 0; background: #e4572e; cursor: pointer }
  .x-cols button.medio { background: var(--brand) }
  .x-cols button:hover { transform: scale(1.4) }
  .x-lbl { display: flex; gap: 4px; margin-top: 4px }
  .x-lbl span { flex: 1; text-align: center; font-size: .7rem; color: var(--muted); font-variant-numeric: tabular-nums }
  .x-key { margin: 6px 0 0; font-size: .78rem; color: var(--muted) }
  .x-key i { display: inline-block; width: 9px; height: 9px; border-radius: 50%; margin: 0 4px 0 10px; background: #e4572e } .x-key i.m { background: var(--brand) }
}""", r"""
  window.__tileD = [0, 0];
  window.__fichaD = (card, e, form, p) => {
    compacta(card, p);
    acciones(card, e, false);
    const close = card.querySelector(".close");
    const head = mk("div", "d-head");
    head.append(...[...card.childNodes].filter((n) => n !== close));
    card.append(head);
    if (!e) return;
    const first = e.posts.reduce((m, q) => q.fecha < m ? q.fecha : m, "9999");
    const days = [];
    for (let d = new Date(`${first}T12:00:00Z`); d.toISOString().slice(0, 10) <= hoy(); d.setUTCDate(d.getUTCDate() + 1)) days.push(d.toISOString().slice(0, 10));
    const box = mk("div", "x-dias"), cols = mk("div", "x-cols"), lbl = mk("div", "x-lbl");
    box.append(mk("h3", null, `Cada publicación el día que salió · ${e.posts.length} en ${days.length} días`));
    for (const d of days) {
      const col = mk("div");
      for (const q of e.posts.filter((x) => x.fecha === d).sort((a, b) => (a.fuente === "medio") - (b.fuente === "medio"))) {
        const b = mk("button", q.fuente === "medio" ? "medio" : "");
        b.type = "button"; b.title = `${quien(q)} · ${fecha(q.fecha)}: «${q.cita}»`; b.setAttribute("aria-label", b.title);
        b.onclick = () => abre(b, q);
        col.append(b);
      }
      cols.append(col);
      lbl.append(mk("span", null, String(Number(d.slice(8)))));
    }
    const key = mk("p", "x-key");
    key.innerHTML = `Toca un punto para leerlo:<i class="m"></i>medio<i></i>vecina o vecino`;
    box.append(cols, lbl, key);
    card.append(box);
  };
"""),
    # A newspaper column: kicker, the days as the headline, the outlets' own headlines, then a few voices.
    "d3": ("Primera plana", """
@media (min-width: 761px) {
  .stage .card { width: 470px; padding: 22px 26px; border-top: 6px solid var(--fg) }
  #reporta { display: none !important }
  .stage .card > h2, .stage .card > .where, .stage .card .ev, .stage .card > .button, .stage .card .sub-head { display: none }
  .x-kick { margin: 0; font-size: .74rem; letter-spacing: .12em; text-transform: uppercase; color: var(--muted); font-weight: 700 }
  .x-tit { margin: 6px 34px 6px 0; font: italic 700 2.3rem/1.05 var(--serif, Georgia, serif); letter-spacing: -.02em }
  .x-tit em { font-style: normal; color: #cc361e }
  .x-deck { margin: 0 0 4px; font-size: 1rem; color: var(--muted) }
  .x-sec { margin: 16px 0 6px; padding-top: 8px; border-top: 1px solid var(--fg); font-size: .72rem; letter-spacing: .1em; text-transform: uppercase; font-weight: 800 }
  .x-heads { list-style: none; margin: 0; padding: 0 }
  .x-heads li { padding: 8px 0; border-bottom: 1px solid var(--line); cursor: pointer }
  .x-heads b { display: block; font: 700 1.02rem/1.3 var(--serif, Georgia, serif) }
  .x-heads li:hover b { color: var(--link) }
  .x-heads small { font-size: .78rem; color: var(--muted) }
  .x-voces q { display: block; margin: 0 0 10px; padding-left: 10px; border-left: 3px solid #e4572e; font: italic 1rem/1.4 var(--serif, Georgia, serif); cursor: pointer }
}""", r"""
  window.__tileD = [0, 0];
  window.__fichaD = (card, e, form, p) => {
    const row = acciones(card, e, false);
    const close = card.querySelector(".close");
    const M = window.aguaMapa, ls = M.zonesOf(p.l || ""), zs = ls.length ? ls : M.zones(p).main;
    const kick = mk("p", "x-kick", [p.m, zs.length ? `Zona ${M.joinES(zs.map(String))}` : null, e ? `Actualizado ${fecha(e.ultima)}` : null].filter(Boolean).join(" · "));
    const name = p.n.toLowerCase().replace(/(^|\s)\S/g, (c) => c.toUpperCase());
    const tit = mk("h3", "x-tit");
    if (e && e.dias) tit.append(mk("em", null, `${e.dias} días`), ` sin agua en ${name}`); else tit.textContent = e ? `Sin agua en ${name}` : name;
    close.after(kick, tit);
    if (!e) { tit.after(row); return; }
    const vec = e.posts.filter((q) => q.fuente !== "medio").length;
    const deck = mk("p", "x-deck", `Lo reportan ${e.medios} ${e.medios === 1 ? "medio" : "medios"} y ${vec} ${vec === 1 ? "publicación de vecinos" : "publicaciones de vecinos"}.`);
    tit.after(deck, row);
    const news = e.posts.filter((q) => q.fuente === "medio").sort((a, b) => b.fecha.localeCompare(a.fecha));
    let at = row;
    if (news.length) {
      const ul = mk("ul", "x-heads");
      for (const q of news.slice(0, 6)) {
        const li = mk("li");
        li.append(mk("b", null, q.titular || q.cita), mk("small", null, `${quien(q)} · ${fecha(q.fecha)}`));
        li.onclick = () => abre(li, q);
        ul.append(li);
      }
      const sec = mk("p", "x-sec", "Lo que publican los medios");
      at.after(sec, ul); at = ul;
    }
    const voces = e.posts.filter((q) => q.fuente !== "medio").slice(0, 3);
    if (voces.length) {
      const box = mk("div", "x-voces");
      for (const q of voces) { const el = mk("q", null, q.cita.length > 160 ? `${q.cita.slice(0, 158)}…` : q.cita); el.onclick = () => abre(el, q); box.append(el); }
      const sec = mk("p", "x-sec", "Lo que dicen los vecinos");
      at.after(sec, box);
    }
  };
"""),
    # The promise against the reports: SIAPA's one day beside the days published, one square per day.
    "d4": ("La promesa", """
@media (min-width: 761px) {
  .stage .card { width: 430px }
  #reporta { display: none !important }
  .stage .card .ev .mosaic, .stage .card .ev .posts, .stage .card .ev > .linkbtn, .stage .card > .button, .stage .card .ev-head { display: none }
  .x-vs { margin: 12px 0 4px; display: grid; gap: 10px }
  .x-vs p { margin: 0 0 4px; font-size: .85rem; color: var(--muted) }
  .x-vs p b { color: var(--fg) }
  .x-sq { display: flex; flex-wrap: wrap; gap: 3px }
  .x-sq i { width: 16px; height: 16px; border-radius: 3px; background: #e4572e }
  .x-sq.siapa i { background: var(--brand) }
  .x-big { font: 800 2.6rem/1 var(--font); color: #cc361e; font-variant-numeric: tabular-nums }
  .x-q { margin: 12px 0 0; padding: 10px 12px; border-radius: 10px; background: var(--bg); cursor: pointer }
  .x-q q { display: block; font-size: .95rem; line-height: 1.4 }
  .x-q small { display: block; margin-top: 4px; font-size: .78rem; color: var(--muted) }
  .x-exige { margin: 12px 0 0; font-size: .92rem }
}""", r"""
  window.__tileD = [0, 0];
  window.__fichaD = (card, e, form, p) => {
    compacta(card, p);
    const row = acciones(card, e, false);
    if (!e) return;
    const vs = mk("div", "x-vs");
    const n = e.dias || 0;
    vs.innerHTML = `<div><p><b>Lo que prometió el SIAPA:</b> cortes «por máximo un día»</p><div class="x-sq siapa"><i></i></div></div>`
      + (n ? `<div><p><b>Lo que se publica de esta colonia:</b></p><div class="x-big">${n} días</div><div class="x-sq">${"<i></i>".repeat(Math.min(n, 60))}</div></div>`
           : `<div><p><b>Lo que se publica de esta colonia:</b> que no hay agua, sin días contados</p></div>`);
    card.querySelector(".ev").before(vs);
    const best = [...e.posts].sort((a, b) => (b.fuente === "medio") - (a.fuente === "medio") || (b.dias || 0) - (a.dias || 0)).slice(0, 2);
    let at = card.querySelector(".ev");
    for (const q of best) {
      const box = mk("div", "x-q");
      box.append(mk("q", null, q.cita.length > 180 ? `${q.cita.slice(0, 178)}…` : q.cita), mk("small", null, `${quien(q)} · ${fecha(q.fecha)} · toca para verla`));
      box.onclick = () => abre(box, q);
      at.after(box); at = box;
    }
    at.after(row);
    const ex = mk("p", "x-exige");
    ex.innerHTML = `<a href="/exige?${new URLSearchParams({ q: p.n, m: p.m, cp: p.cp })}">Exígele al SIAPA, a la CEA y a tu municipio →</a>`;
    row.after(ex);
  };
"""),
    # The colonia alone in the light: the rest of the city dimmed, its voices pinned around it as bubbles.
    "d5": ("Foco", """
@media (min-width: 761px) {
  .stage .card { width: 330px }
  #reporta { display: none !important }
  .stage .card .ev .mosaic, .stage .card .ev .posts, .stage .card .ev > .linkbtn, .stage .card > .button, .stage .card .sub-head, .stage .card .conteo { display: none }
  .x-bub { background: none; border: 0 }
  .x-bub div { width: 230px; padding: 10px 12px; border-radius: 14px; background: var(--surface); color: var(--fg); box-shadow: 0 8px 24px rgb(0 0 0 / .35); font-size: .86rem; line-height: 1.35; cursor: pointer }
  .x-bub div:hover { outline: 2px solid #e4572e }
  .x-bub small { display: block; margin-top: 4px; font-size: .72rem; color: var(--muted) }
}""", r"""
  window.__tileD = [0, 0];
  let foco = [];
  window.__fichaD = (card, e, form, p, f) => { compacta(card, p); acciones(card, e, false); window.__sel = { e, f }; };
  window.__cierra = () => { for (const l of foco) l.remove(); foco = []; };
  window.__refitD = (map, b, card) => {
    window.__cierra();
    const { e, f } = window.__sel || {};
    // A world-sized veil with the colonia cut out of it.
    const rings = (g) => g.type === "Polygon" ? [g.coordinates[0]] : g.coordinates.map((x) => x[0]);
    const holes = f ? rings(f.geometry).map((r) => r.map(([x, y]) => [y, x])) : [];
    foco.push(L.polygon([[[-89, -179], [-89, 179], [89, 179], [89, -179]], ...holes], { interactive: false, stroke: false, fillColor: "#030814", fillOpacity: 0.55 }).addTo(map));
    if (e) {
      // Stacked down the colonia's right edge, in their own pane above the badges.
      if (!map.getPane("burbujas")) map.createPane("burbujas").style.zIndex = 690;
      const at = L.latLng(b.getCenter().lat, b.getEast());
      const pick = [...e.posts].sort((a, c) => (c.fuente === "medio") - (a.fuente === "medio")).slice(0, 4);
      pick.forEach((q, i) => {
        const div = `<div>«${(q.cita.length > 80 ? q.cita.slice(0, 78) + "…" : q.cita).replace(/</g, "&lt;")}»<small>${quien(q).replace(/</g, "&lt;")} · ${fecha(q.fecha)}</small></div>`;
        const m = L.marker(at, { pane: "burbujas", icon: L.divIcon({ className: "x-bub", html: div, iconSize: [230, 0], iconAnchor: [-40, 190 - i * 95] }), keyboard: false }).addTo(map);
        m.on("click", () => abre(m.getElement().firstChild, q));
        foco.push(m);
      });
    }
    map.flyToBounds(b, { paddingTopLeft: [330 + 60, 80], paddingBottomRight: [320, 60], maxZoom: 15, duration: 0.6, animate: !reduce() });
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
        css, js = BASE[0] + dv[1] + VD[v][1], BASE[1] + SLIDES + dv[2] + DESK + VD[v][2]
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
