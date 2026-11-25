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

  // Runs fn once when el is at least `umbral` on screen (at once without IntersectionObserver).
  NC.alVer = (el, fn, umbral = 0.35) => {
    if (!el) return;
    if (!("IntersectionObserver" in window)) return fn(el);
    const io = new IntersectionObserver((es) => es.forEach((e) => { if (e.isIntersecting) { io.disconnect(); fn(el); } }), { threshold: umbral });
    io.observe(el);
  };

  // Counts el's text up to `fin` when it comes into view; with reduced motion it just shows the number.
  NC.cuenta = (el, fin, dec = 0, ms = 1100) => {
    const fmt = (v) => v.toLocaleString("es-MX", { minimumFractionDigits: dec, maximumFractionDigits: dec });
    if (NC.quieto()) { el.textContent = fmt(fin); return; }
    el.textContent = fmt(0);
    NC.alVer(el, () => {
      const t0 = performance.now();
      const paso = (t) => {
        const k = Math.min(1, (t - t0) / ms), e = 1 - Math.pow(1 - k, 3);
        el.textContent = fmt(fin * e);
        if (k < 1) requestAnimationFrame(paso);
      };
      requestAnimationFrame(paso);
    }, 0.6);
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
  NC.foto = (p, mini = true) => `<a class="foto" href="/img/documentos/${p.foto}.webp"><span class="punto" aria-hidden="true">${p.n}</span><img src="/img/documentos/${p.foto}${mini ? "-mini" : ""}.webp" width="${p.w}" height="${p.h}" alt="${NC.esc(p.alt)}" decoding="async"></a>`;
  NC.pie = (p) => `Descarga ${NC.esc(p.nombre)}<span class="sub">${NC.esc(p.latT)} ${NC.esc(p.lonT)} · <a href="/datos/siapa-dg-135-2026.pdf#page=${p.pag}">p. ${p.pag}</a></span>`;
})();
