// Shared data and helpers for the /nocuadra-p1 to p10 prototypes (noindex). The numbers are copies of /zapopan's and
// /tlajomulco's; change them there first.
(() => {
  const NC = (window.NC = {});

  // Pipas per jornada, 15 October to 3 November 2026: our reading of the chart annexed to oficio 011300/2026/0150
  // (UT-091/2026, PDF p. 4), as /datos/zapopan-pipas-por-dia.csv.
  NC.PIPAS = [5, 12, 7, 7, 11, 11, 13, 13, 15, 21, 25, 33, 34, 32, 31, 32, 30, 30, 27, 31];
  NC.DUDA = { 1: "la etiqueta 12 puede ser del 17 de octubre", 2: "la etiqueta 7 puede ser del 16 de octubre" };
  NC.ANUNCIADAS = 45;
  const DIA0 = Date.UTC(2026, 9, 15);
  NC.fecha = (i) => new Date(DIA0 + i * 864e5);
  NC.largo = (i) => NC.fecha(i).toLocaleDateString("es-MX", { timeZone: "UTC", weekday: "long", day: "numeric", month: "long" });
  NC.corto = (i) => `${NC.fecha(i).getUTCDate()} ${NC.fecha(i).getUTCMonth() === 9 ? "oct." : "nov."}`;

  // Our reading of the SIAPA's Gráfico 1 (oficio DG-135/2026, PDF p. 5), mg/L, January 2020 to February 2026, as
  // /datos/siapa-dg-135-2026-amoniacal.csv. A month counts as above the limit only beyond our ±0.05 reading margin.
  NC.AMONIACO = [
    0.11, 0.10, 0.10, 0.10, 0.10, 0.10, 0.10, 0.11, 0.10, 0.11, 0.10, 0.10,
    0.10, 0.11, 0.10, 0.10, 0.10, 0.10, 0.11, 0.10, 0.11, 0.11, 0.11, 0.11,
    0.12, 0.12, 0.12, 0.11, 0.12, 0.13, 0.23, 0.13, 0.27, 0.22, 0.12, 0.13,
    0.12, 0.13, 0.14, 0.18, 0.11, 0.18, 1.37, 1.11, 0.29, 1.28, 1.31, 0.86,
    0.60, 0.34, 0.13, 0.49, 0.44, 1.07, 2.18, 1.57, 0.56, 0.92, 0.60, 0.74,
    0.27, 0.27, 0.26, 0.52, 0.58, 0.90, 2.14, 1.35, 0.66, 1.42, 1.19, 2.28,
    3.62, 3.01];
  NC.LIMITE = 0.5;
  NC.MARGEN = 0.05;
  NC.sobre = (v) => v > NC.LIMITE + NC.MARGEN;
  const MESES = ["ene.", "feb.", "mar.", "abr.", "may.", "jun.", "jul.", "ago.", "sep.", "oct.", "nov.", "dic."];
  const MESES_L = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"];
  NC.mes = (i) => `${MESES[i % 12]} ${2020 + Math.floor(i / 12)}`;
  NC.mesLargo = (i) => `${MESES_L[i % 12]} de ${2020 + Math.floor(i / 12)}`;

  // The seven of DG-135/2026's ten points with a page of photographs and coordinates, as /tlajomulco lists them.
  const grados = (s) => {
    const [, g, mi, se, h] = s.match(/(\d+)°(\d+)'([\d.]+)"([NSEW])/);
    const v = +g + mi / 60 + se / 3600;
    return h === "S" || h === "W" ? -v : v;
  };
  NC.PUNTOS = [
    ["1", "Capulín 1", `20°28'40.4"N`, `103°15'56.5"W`, "dg135-capulin-1", 612, 530, 8, "Dos fotografías: agua gris que sale con fuerza de un tubo roto entre el pasto, bajo un puente de barandal amarillo, y un tubo blanco que termina en un charco de agua gris, junto a un canal cubierto de plantas."],
    ["2", "El Guayabo", `20°28'40.9"N`, `103°16'29.1"W`, "dg135-guayabo", 562, 739, 9, "Agua oscura y quieta bajo árboles y matorrales, junto a un muro de concreto, con una casa al fondo."],
    ["6", "La Carreta", `20°31'25.4"N`, `103°21'28.9"W`, "dg135-carreta", 618, 454, 10, "Un puente de tres arcos sobre agua oscura, con basura en la ladera de atrás."],
    ["7", "El Edén", `20°31'59.9"N`, `103°21'50.1"W`, "dg135-eden", 543, 770, 11, "Dos fotografías: una capa de espuma blanca que cubre el canal al pie de una caída de agua, y un sillón atorado en el borde de una caída, con espuma abajo."],
    ["8", "La Teja", `20°32'10.6"N`, `103°21'46.3"W`, "dg135-teja", 516, 671, 12, "Un flujo de agua que entra a un cuerpo de agua turbia, bajo un cielo nublado."],
    ["9", "Vaso Regulador Adolf Horn", `20°32'40.4"N`, `103°21'14.5"W`, "dg135-adolf-horn", 574, 647, 13, "Agua verdosa que sale de un tubo azul y baja por un muro de piedra, bajo una cerca de lámina azul, hacia agua cubierta de espuma blanca, entre la maleza."],
    ["10", "1º de Mayo", `20°32'49.1"N`, `103°21'05.2"W`, "dg135-1-mayo", 606, 522, 15, "Dos fotografías: el canal con agua oscura bajo una barda blanca, y la boca de un tubo de concreto en la orilla, entre plantas."],
  ].map(([n, nombre, latT, lonT, foto, w, h, pag, alt]) => ({ n, nombre, latT, lonT, lat: grados(latT), lon: grados(lonT), foto, w, h, pag, alt }));

  NC.esc = (s) => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/"/g, "&quot;");
  NC.quieto = () => matchMedia("(prefers-reduced-motion: reduce)").matches;
  NC.color = (v, f) => getComputedStyle(document.documentElement).getPropertyValue(v).trim() || f;

  // Runs fn once when el is at least `umbral` on screen (at once without IntersectionObserver). If the reader jumps past
  // el first, runs pasado instead (when given), so a figure never sits empty above the screen.
  NC.alVer = (el, fn, umbral = 0.35, pasado = null) => {
    if (!el) return;
    if (!("IntersectionObserver" in window)) return fn(el);
    // An element taller than the screen can never be `umbral` visible: lower the bar to what fits.
    umbral = Math.min(umbral, 0.99, 0.9 * innerHeight / Math.max(1, el.offsetHeight));
    const io = new IntersectionObserver((es) => es.forEach((e) => {
      if (e.isIntersecting && e.intersectionRatio >= umbral) { io.disconnect(); fn(el); }
      else if (pasado && !e.isIntersecting && e.boundingClientRect.bottom < 0) { io.disconnect(); pasado(el); }
    }), { threshold: [0, umbral] });
    io.observe(el);
  };

  // Counts el's text up to `fin` when it comes into view, or at once with ahora (for something just revealed on screen);
  // with reduced motion it just shows the number.
  NC.cuenta = (el, fin, dec = 0, ms = 1100, ahora = false) => {
    const fmt = (v) => v.toLocaleString("es-MX", { minimumFractionDigits: dec, maximumFractionDigits: dec });
    if (NC.quieto()) { el.textContent = fmt(fin); return; }
    el.textContent = fmt(0);
    const corre = () => {
      const t0 = performance.now();
      const paso = (t) => {
        const k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3);
        el.textContent = fmt(fin * e);
        if (k < 1) requestAnimationFrame(paso);
      };
      requestAnimationFrame(paso);
    };
    if (ahora || !("IntersectionObserver" in window)) return corre();
    // A figure the reader jumped past (a link, a fast scroll) shows its number instead of waiting at zero.
    const io = new IntersectionObserver(([e]) => {
      if (e.intersectionRatio >= 0.6) { io.disconnect(); corre(); }
      else if (e.boundingClientRect.bottom < 0) { io.disconnect(); el.textContent = fmt(fin); }
    }, { threshold: [0, 0.6] });
    io.observe(el);
  };

  // A grid of `total` squares, the first `n` marked .si.
  NC.waffle = (el, n, total = 100) => {
    el.replaceChildren(...Array.from({ length: total }, (_, i) => { const s = document.createElement("span"); if (i < n) s.className = "si"; return s; }));
  };

  // Bar chart in the style of /zapopan's: hover or arrow keys show a value. o: { V, tope, cada, limite, limiteT(angosto),
  // ticks(angosto) -> indices, eje(i), tip(i), notas: [{ i, en, t(angosto) }], clase(v, i), aria, unidad, alto }.
  const NS = "http://www.w3.org/2000/svg";
  const el = (name, attrs = {}, text) => {
    const e = document.createElementNS(NS, name);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (text != null) e.textContent = text;
    return e;
  };
  NC.serie = (caja, o) => {
    if (!caja) return;
    const V = o.V;
    const tip = document.createElement("div");
    tip.className = "tip";
    tip.hidden = true;
    let actual = o.inicio ?? V.length - 1, geo = null;
    const muestra = (i) => {
      if (!geo) return;
      actual = i;
      for (const g of geo.cols) g.classList.toggle("on", +g.dataset.i === i);
      tip.innerHTML = o.tip(i);
      tip.hidden = false;
      const cx = geo.x(i) + geo.ancho / 2, cy = geo.y(V[i]);
      const w = tip.offsetWidth, izq = cx + 14 + w > geo.W ? cx - 14 - w : cx + 14;
      tip.style.left = `${Math.max(0, izq)}px`;
      tip.style.top = `${Math.max(0, Math.min(cy - 30, geo.H - tip.offsetHeight - geo.m.b))}px`;
    };
    const oculta = () => { tip.hidden = true; if (geo) for (const g of geo.cols) g.classList.remove("on"); };
    const dibuja = () => {
      const W = Math.max(260, Math.round(caja.clientWidth)), angosto = W < 520;
      const H = o.alto ? o.alto(angosto) : angosto ? 220 : 260, m = { l: o.izquierda ?? 30, r: 6, t: 24, b: 24 };
      const pw = W - m.l - m.r, ph = H - m.t - m.b, paso = pw / V.length;
      const hueco = paso >= 6 ? Math.min(6, Math.round(paso * 0.2)) : paso >= 3 ? 1 : 0, ancho = Math.max(1, paso - hueco);
      const y = (v) => m.t + ph - (Math.min(v, o.tope) / o.tope) * ph;
      const x = (i) => m.l + i * paso + hueco / 2;
      const centro = (i) => x(i) + ancho / 2;
      const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, width: W, height: H, role: "img", tabindex: 0, "aria-label": o.aria });
      if (o.unidad) svg.append(el("text", { x: 0, y: 12 }, o.unidad));
      for (let t = 0; t <= o.tope + 1e-9; t += o.cada) {
        svg.append(el("line", { class: t ? "gl" : "base", x1: m.l, x2: W - m.r, y1: y(t), y2: y(t) }));
        svg.append(el("text", { x: m.l - 6, y: y(t) + 4, "text-anchor": "end" }, o.fmtEje ? o.fmtEje(t) : String(t)));
      }
      for (const i of o.ticks(angosto)) {
        const ancla = i === 0 ? "start" : i === V.length - 1 ? "end" : "middle";
        svg.append(el("text", { x: ancla === "start" ? x(i) : ancla === "end" ? x(i) + ancho : centro(i), y: H - 6, "text-anchor": ancla }, o.eje(i)));
      }
      const cols = [];
      V.forEach((v, i) => {
        const g = el("g", { class: "col", "data-i": i });
        g.append(el("rect", { class: "hit", x: m.l + i * paso, y: m.t, width: paso, height: ph, fill: "transparent" }));
        const top = y(v), h = m.t + ph - top, r = Math.min(3, ancho / 2, h), x0 = x(i);
        g.append(el("path", { class: o.clase ? o.clase(v, i) : "uno",
          d: `M${x0},${top + h}V${top + r}Q${x0},${top} ${x0 + r},${top}H${x0 + ancho - r}Q${x0 + ancho},${top} ${x0 + ancho},${top + r}V${top + h}Z` }));
        svg.append(g);
        cols.push(g);
      });
      if (o.limite != null) {
        svg.append(el("line", { class: "limite", x1: m.l, x2: W - m.r, y1: y(o.limite), y2: y(o.limite) }));
        svg.append(el("text", { class: "limite-t", x: m.l + 4, y: y(o.limite) - 6 }, o.limiteT(angosto)));
      }
      for (const n of o.notas || []) {
        const cx = centro(n.i);
        svg.append(el("line", { class: "nota-l", x1: cx, x2: cx, y1: y(V[n.i]) - 3, y2: y(n.en) + 4 }));
        svg.append(el("text", { class: "nota", x: cx, y: y(n.en), "text-anchor": n.ancla || "middle" }, n.t(angosto)));
      }
      const indice = (ev) => {
        const r = svg.getBoundingClientRect();
        const i = Math.floor(((ev.clientX - r.left) * (W / r.width) - m.l) / paso);
        return i >= 0 && i < V.length ? i : -1;
      };
      svg.addEventListener("pointermove", (ev) => { const i = indice(ev); if (i < 0) oculta(); else muestra(i); });
      svg.addEventListener("pointerleave", oculta);
      svg.addEventListener("focus", () => muestra(actual));
      svg.addEventListener("blur", oculta);
      svg.addEventListener("keydown", (ev) => {
        const salto = { ArrowLeft: -1, ArrowRight: 1, Home: -V.length, End: V.length }[ev.key];
        if (ev.key === "Escape") return oculta();
        if (salto == null) return;
        ev.preventDefault();
        muestra(Math.max(0, Math.min(V.length - 1, actual + salto)));
      });
      svg.addEventListener("pointerdown", (ev) => { const i = indice(ev); if (i >= 0) muestra(i); });
      caja.replaceChildren(svg, tip);
      if (o.fila) caja.append(tabla);
      geo = { W, H, m, x, y, ancho, cols };
    };
    // The values as text for screen readers: the chart's tooltip is the only other place they appear.
    const tabla = document.createElement("div");
    if (o.fila) {
      Object.assign(tabla.style, { position: "absolute", width: "1px", height: "1px", margin: "-1px", padding: "0", overflow: "hidden", clipPath: "inset(50%)", border: "0" });
      const [a, b] = o.columnas;
      tabla.innerHTML = `<table><caption>${NC.esc(o.aria.split(":")[0])}</caption><thead><tr><th scope="col">${a}</th><th scope="col">${b}</th></tr></thead><tbody>${V.map((_, i) => { const [k, v] = o.fila(i); return `<tr><th scope="row">${k}</th><td>${v}</td></tr>`; }).join("")}</tbody></table>`;
    }
    dibuja();
    let w = caja.clientWidth;
    new ResizeObserver(() => { if (Math.abs(caja.clientWidth - w) > 1) { w = caja.clientWidth; dibuja(); } }).observe(caja);
  };

  // The two charts every prototype can draw.
  NC.seriePipas = (caja, extra = {}) => NC.serie(caja, Object.assign({
    V: NC.PIPAS, tope: 50, cada: 10, limite: NC.ANUNCIADAS, unidad: "pipas", inicio: 12, izquierda: 26,
    ticks: (a) => (a ? [0, 9, 19] : [0, 5, 9, 14, 19]), eje: NC.corto,
    tip: (i) => `<b>${NC.largo(i)}</b>${NC.PIPAS[i]} pipas<br>${NC.ANUNCIADAS - NC.PIPAS[i]} menos que las 45 anunciadas${NC.DUDA[i] ? `<br><small>Lectura dudosa: ${NC.DUDA[i]}</small>` : ""}`,
    limiteT: (a) => (a ? "Anunciadas: 45" : "Anunciadas el 19 de octubre: 45"),
    notas: [{ i: 4, en: 24, t: () => "19 oct.: 11" }, { i: 12, en: 40, t: () => "27 oct.: 34" }],
    columnas: ["Día", "Pipas"], fila: (i) => [NC.largo(i), `${NC.PIPAS[i]}${NC.DUDA[i] ? " (lectura dudosa)" : ""}`],
    aria: "Gráfica de barras de las pipas por jornada en Zapopan, del 15 de octubre al 3 de noviembre de 2026, según Protección Civil: de 5 a 34, nunca las 45 anunciadas; 11 el 19 de octubre y 34 el 27. Con las flechas se recorren los días.",
  }, extra));
  NC.serieAmoniaco = (caja, extra = {}) => NC.serie(caja, Object.assign({
    V: NC.AMONIACO, tope: 4, cada: 1, limite: NC.LIMITE, unidad: "mg/L", inicio: 72, izquierda: 22,
    ticks: (a) => (a ? [0, 36, 73] : [0, 12, 24, 36, 48, 60, 73]), eje: (i) => (i === 73 ? "feb. 2026" : String(2020 + Math.floor(i / 12))),
    clase: (v) => (NC.sobre(v) ? "sobre" : "bajo"),
    tip: (i) => `<b>${NC.mesLargo(i)}</b>${NC.AMONIACO[i].toFixed(2)} mg/L${NC.sobre(NC.AMONIACO[i]) ? `<br>${(NC.AMONIACO[i] / NC.LIMITE).toFixed(1)} veces el límite` : ""}`,
    limiteT: () => "Límite que cita el SIAPA: 0.5",
    notas: [{ i: 72, en: 3.85, ancla: "end", t: (a) => (a ? "Ene. 2026: 3.62" : "Enero de 2026: 3.62") }],
    columnas: ["Mes", "mg/L"], fila: (i) => [NC.mesLargo(i), NC.AMONIACO[i].toFixed(2)],
    aria: "Gráfica de barras del nitrógeno amoniacal, promedio mensual en el agua que entra a la Planta 1, de enero de 2020 a febrero de 2026: de 0.10 a 0.27 mg/L de 2020 a 2022, por encima del límite la mayoría de los meses desde julio de 2023 y 3.62 mg/L en enero de 2026. Con las flechas se recorren los meses.",
  }, extra));

  // Leaflet: a base map with the site's tiles and pinch, or null when Leaflet didn't load.
  NC.mapa = (caja, opts = {}) => {
    if (!caja || !window.L) { if (caja) caja.hidden = true; return null; }
    const M = window.aguaMapa;
    const map = L.map(caja, Object.assign({ scrollWheelZoom: false, zoomSnap: 0.25 }, opts));
    if (M && M.tiles) M.tiles(L, map);
    else L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "© OpenStreetMap" }).addTo(map);
    if (M && M.pinch) M.pinch(map);
    return map;
  };
  NC.marcaPunto = (p, onPick) => {
    const m = L.marker([p.lat, p.lon], {
      icon: L.divIcon({ className: "marca-punto", html: `<span class="punto">${p.n}</span>`, iconSize: [24, 24], iconAnchor: [12, 12] }),
      keyboard: true,
    }).bindTooltip(`${NC.esc(p.nombre)}<span class="sub">${NC.esc(p.latT)} ${NC.esc(p.lonT)}</span>`, { className: "map-label", direction: "top", offset: [0, -12] });
    m.on("add", () => m.getElement().setAttribute("aria-label", `Punto ${p.n}, ${p.nombre}`));
    if (onPick) m.on("click", () => onPick(p));
    return m;
  };
  let cis = null;
  // Zapopan's 49 cisternas from /cisternas.json (the list delivered for folio 140292426004978).
  NC.cisternas = () => (cis ||= fetch("/cisternas.json")
    .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then((d) => d.puntos.filter((p) => p.municipio === "Zapopan" && isFinite(p.lat) && isFinite(p.lon)))
    .catch((e) => { cis = null; throw e; }));
  NC.marcaCisterna = (p) => {
    const touch = matchMedia("(hover: none)").matches;
    const m = L.circleMarker([p.lat, p.lon], { radius: 7, weight: 2, color: "#ffffff", fillColor: NC.color("--s1", "#2a78d6"), fillOpacity: 0.95 });
    const html = `${NC.esc(p.lugar || "Sin domicilio en la lista")}<span class="sub">Cisterna de la lista de Cercanía Ciudadana</span>`;
    if (touch) m.bindPopup(html); else m.bindTooltip(html, { className: "map-label", direction: "top", offset: [0, -6] });
    document.addEventListener("tema", () => m.setStyle({ fillColor: NC.color("--s1", "#2a78d6") }));
    return m;
  };
  // The scrolling story (nocuadra-lab.css): a sticky .escena of .capa[data-c] layers beside ol.pasos of .paso[data-c].
  // The step whose top crosses a line (the middle of the screen, lower on phones) shows its layer. o.capas[c](capa, first)
  // runs each time a layer shows (first is true the first time, for maps and charts that need their box); o.progreso(paso,
  // t) gets how far, 0 to 1, the active step has scrolled past the line, for pages that scrub.
  NC.relato = (root, o = {}) => {
    if (!root) return;
    const capas = [...root.querySelectorAll(".capa")], pasos = [...root.querySelectorAll(".paso")];
    if (!pasos.length) return;
    root.classList.add("vivo");
    const vistas = new Set();
    let actual = null, activo = null;
    const muestra = (paso) => {
      if (paso !== activo) {
        if (activo) activo.classList.remove("activo");
        paso.classList.add("activo");
        activo = paso;
        if (o.alPaso) o.alPaso(paso);
      }
      const c = paso.dataset.c;
      if (c === actual) return;
      actual = c;
      let capa = null;
      for (const k of capas) { const on = k.dataset.c === c; k.classList.toggle("on", on); if (on) capa = k; }
      if (o.capas && o.capas[c]) { const first = !vistas.has(c); vistas.add(c); try { o.capas[c](capa, first); } catch (e) { console.error(e); } }
    };
    const elige = () => {
      // Nothing plays while the story is still below the screen, so its first layer's animation isn't spent unseen.
      if (actual === null && root.getBoundingClientRect().top > innerHeight) return;
      const linea = innerHeight * (innerWidth <= 860 ? 0.72 : 0.5);
      let p = pasos[0];
      // The card's top, not the step's: on phones a step is taller than the screen and its card sits in its middle.
      for (const q of pasos) if ((q.querySelector(".tarjeta") || q).getBoundingClientRect().top < linea) p = q;
      muestra(p);
      if (o.progreso) {
        const r = p.getBoundingClientRect();
        o.progreso(p, Math.max(0, Math.min(1, (linea - r.top) / Math.max(1, r.height))));
      }
    };
    let pend = false;
    addEventListener("scroll", () => { if (!pend) { pend = true; requestAnimationFrame(() => { pend = false; elige(); }); } }, { passive: true });
    addEventListener("resize", elige);
    elige();
    return { actual: () => actual };
  };

  // Zapopan's list of «Falta de agua» reports (oficio 11000000/CER.CIU/2026/0878, folio 140292426004981), as /zapopan
  // draws it from /datos/zapopan-reportes.json.
  let rep = null;
  NC.reportes = () => (rep ||= fetch("/datos/zapopan-reportes.json")
    .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .catch((e) => { rep = null; throw e; }));
  const CORTES = [1, 5, 25, 100, 250];
  const RAMPA = { light: ["#b7d3f6", "#6da7ec", "#2a78d6", "#1c5cab", "#0d366b"], dark: ["#184f95", "#256abf", "#3987e5", "#6da7ec", "#b7d3f6"] };
  const oscuro = () => (window.aguaDark ? window.aguaDark() : false);
  const clase = (n) => CORTES.reduce((c, x, i) => (n >= x ? i : c), 0);
  const rampa = () => RAMPA[oscuro() ? "dark" : "light"];
  const rango = (i) => (i === CORTES.length - 1 ? `${CORTES[i]} o más` : `${CORTES[i]} a ${CORTES[i + 1] - 1}`);
  const fmt = (n) => n.toLocaleString("es-MX");
  // The same choropleth as /zapopan's: Zapopan's colonias on the SIAPA's map, coloured by how many reports name them;
  // a colonia no report names is only outlined. leyenda is a ul.keys to fill. Returns the map, or null without Leaflet.
  NC.mapaReportes = (caja, leyenda, aviso) => {
    const M = window.aguaMapa;
    if (!M || !M.load) { if (caja) caja.hidden = true; return null; }
    const map = NC.mapa(caja, { preferCanvas: true });
    if (!map) return null;
    map.setView([20.70, -103.42], 11);
    if (leyenda) {
      leyenda.innerHTML = CORTES.map((_, i) => `<li><span class="sw" data-clase="${i}"></span>${rango(i)}</li>`).join("") + `<li><span class="sw none"></span>Ningún reporte la nombra así</li>`;
    }
    const pinta = () => { if (leyenda) for (const s of leyenda.querySelectorAll("[data-clase]")) s.style.setProperty("--sw", rampa()[s.dataset.clase]); };
    pinta();
    // The error gets its own line: aviso holds the caveats («un reporte no es una casa»), which must stay.
    const falla = () => { if (!aviso) return; const p = document.createElement("p"); p.className = "note"; p.setAttribute("role", "status"); p.textContent = "No pudimos cargar el mapa de reportes. Intenta de nuevo en unos minutos."; aviso.before(p); };
    Promise.all([NC.reportes(), M.load()]).then(([d, { colonias }]) => {
      const porClave = new Map(d.colonias.filter((c) => c.clave).map((c) => [c.clave, c]));
      const de = (f) => porClave.get(M.fold(f.properties.n));
      const estilo = (f) => {
        const c = de(f);
        if (!c) return { color: oscuro() ? "#6b7aa6" : "#8a94ad", weight: 0.6, opacity: 0.7, fill: false };
        return { color: oscuro() ? "#0c1328" : "#ffffff", weight: 0.8, opacity: 0.9, fillColor: rampa()[clase(c.reportes)], fillOpacity: 0.82 };
      };
      const texto = (f) => {
        const c = de(f);
        const zs = [...M.zones(f.properties).main].sort((a, b) => a - b);
        const lineas = c
          ? [`${fmt(c.reportes)} ${c.reportes === 1 ? "reporte" : "reportes"} · ${fmt(c.en_proceso)} «En proceso»`, zs.length ? (zs.length > 1 ? "Zonas " : "Zona ") + zs.join(" y ") : "Sin zona en el mapa"]
          : ["Ningún reporte la nombra así", "(no quiere decir que haya tenido agua)"];
        if (c && c.poligonos > 1) lineas.push(`El mapa tiene ${c.poligonos} colonias con este nombre en Zapopan y la lista no dice cuál, así que se pintan todas.`);
        return NC.esc(f.properties.n) + lineas.map((l) => `<span class="sub">${NC.esc(l)}</span>`).join("");
      };
      const touch = matchMedia("(hover: none)").matches;
      const zap = colonias.filter((f) => (f.properties.m || "").includes("Zapopan"));
      const capa = L.geoJSON(zap, {
        style: estilo,
        onEachFeature: (f, l) => (touch ? l.bindPopup(() => texto(f)) : l.bindTooltip(() => texto(f), { sticky: true, className: "map-label", direction: "top" })),
      }).addTo(map);
      const con = L.featureGroup(capa.getLayers().filter((l) => de(l.feature)));
      map._ncLimites = con.getBounds();
      map.fitBounds(map._ncLimites, { padding: [12, 12] });
      document.addEventListener("tema", () => { capa.setStyle(estilo); pinta(); });
    }).catch((e) => { console.error(e); falla(); });
    return map;
  };
  // Pictograms that fill in, one unit at a time (propuesta 9). Each returns { anima, vacia }: anima() plays the fill
  // (at once with reduced motion), vacia() empties it so a scrolling story can play it again. With { alVer: true } the
  // fill plays once when the pictogram comes into view.
  const llena = (items, n, cuenta, ms) => {
    let t = null;
    const vacia = () => { clearInterval(t); items.forEach((x) => x.classList.remove("si")); if (cuenta) cuenta.textContent = "0"; };
    const lleno = () => { clearInterval(t); items.forEach((x, i) => x.classList.toggle("si", i < n)); if (cuenta) cuenta.textContent = String(n); };
    const anima = () => {
      if (NC.quieto()) return lleno();
      vacia();
      let i = 0;
      t = setInterval(() => { if (i >= n) return clearInterval(t); items[i++].classList.add("si"); if (cuenta) cuenta.textContent = String(i); }, ms);
    };
    return { anima, vacia, lleno };
  };
  const auto = (el, ctl, o, umbral) => {
    if (o.alVer) { if (NC.quieto()) (ctl.lleno || ctl.anima)(); else NC.alVer(el, ctl.anima, umbral, ctl.lleno || ctl.anima); }
    return ctl;
  };
  // 100 drops, the first n blue: one per announced cisterna.
  const GOTA = '<svg viewBox="0 0 20 26" aria-hidden="true"><path d="M10 1C10 1 2 11 2 17a8 8 0 0 0 16 0C18 11 10 1 10 1z" fill="currentColor"/></svg>';
  NC.gotas = (el, n = 49, cuenta = null, o = {}) => {
    el.innerHTML = GOTA.repeat(o.total || 100);
    return auto(el, llena([...el.children], n, cuenta, o.ms || 28), o, 0.5);
  };
  // A grid of `total` squares that fills up to n (the waffle, animated).
  NC.cuadros = (el, n = 49, cuenta = null, o = {}) => {
    NC.waffle(el, 0, o.total || 100);
    return auto(el, llena([...el.children], n, cuenta, o.ms || 20), o, 0.5);
  };
  // One row per jornada, 45 circles a row: the announced pipas, blue where the chart has one.
  NC.matriz = (el, o = {}) => {
    const max = Math.max(...NC.PIPAS), cols = NC.ANUNCIADAS;
    el.innerHTML = NC.PIPAS.map((v, i) => `<div class="fila${v === max ? " max" : ""}" title="${NC.esc(NC.largo(i))}: ${v} pipas"><span>${NC.corto(i)}</span><span class="puntos">${Array.from({ length: cols }, (_, j) => `<i class="${j < v ? "si" : ""}" style="transition-delay:${NC.quieto() ? 0 : i * 40 + j * 4}ms"></i>`).join("")}</span><span class="n">${v}</span></div>`).join("")
      + `<div class="fila eje" aria-hidden="true"><span></span><span><span>1</span><span>${cols} anunciadas</span></span><span></span></div>`;
    const ctl = { anima: () => el.classList.add("ve"), vacia: () => el.classList.remove("ve") };
    if (NC.quieto()) { ctl.anima(); return ctl; }
    return auto(el, ctl, o, 0.15);
  };
  // Glasses of the limit's worth (0.5 mg/L) of ammonia for the months in `meses`, poured one after another.
  NC.vasos = (el, meses = [0, 54, 71, 72], o = {}) => {
    const fila = (i) => {
      const v = NC.AMONIACO[i], k = v / NC.LIMITE, enteros = Math.floor(k), resto = k - enteros;
      const vs = Array.from({ length: Math.ceil(k) || 1 }, (_, j) => `<span class="v"><i data-h="${j < enteros ? 100 : Math.round((j === enteros ? resto : k) * 100)}"></i></span>`).join("");
      return `<div class="renglon-v"><div class="q">${NC.mesLargo(i)}<b class="${NC.sobre(v) ? "sobre" : ""}">${v.toFixed(2)} mg/L</b>${k >= 1 ? `${k.toFixed(1)} vasos` : `${k.toFixed(1)} de un vaso`}</div><div class="vasos ${NC.sobre(v) ? "" : "bajo"}">${vs}</div></div>`;
    };
    el.innerHTML = meses.map(fila).join("");
    const is = [...el.querySelectorAll(".v i")];
    let ts = [];
    const vacia = () => { ts.forEach(clearTimeout); ts = []; is.forEach((x) => { x.style.height = "0"; }); };
    // The reflow lets the emptied glasses render before they pour again.
    const anima = () => { vacia(); void el.offsetWidth; is.forEach((x, j) => ts.push(setTimeout(() => { x.style.height = x.dataset.h + "%"; }, NC.quieto() ? 0 : 40 + j * 90))); };
    return auto(el, { anima, vacia }, o, 0.3);
  };
  NC.foto = (p, mini = true) => `<a class="foto" href="/img/documentos/${p.foto}.webp"><span class="punto" aria-hidden="true">${p.n}</span><img src="/img/documentos/${p.foto}${mini ? "-mini" : ""}.webp" width="${p.w}" height="${p.h}" alt="${NC.esc(p.alt)}" decoding="async"></a>`;
  NC.pie = (p) => `Descarga ${NC.esc(p.nombre)}<span class="sub">${NC.esc(p.latT)} ${NC.esc(p.lonT)} · <a href="/datos/siapa-dg-135-2026.pdf#page=${p.pag}">p. ${p.pag}</a></span>`;
})();
