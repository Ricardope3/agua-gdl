// The rotation map shared by /mapa and /mizona: SIAPA's colonias and zones from
// /colonias_siapa.topo.json (built by pipelines/siapa_mapa.py), decoded here without a library.
window.aguaMapa = (() => {
  "use strict";
  const DATA = "/colonias_siapa.topo.json";
  const COLORS = {
    light: { 1: "#008300", 2: "#2a78d6", 3: "#eda100", 4: "#1baf7a", 5: "#6250d6", 6: "#e87ba4", 7: "#e34948" },
    dark: { 1: "#008300", 2: "#3987e5", 3: "#c98500", 4: "#199e70", 5: "#9085e9", 6: "#d55181", 7: "#d94141" },
  };
  // Below this share of its area in a zone, a colonia only touches that zone's border.
  const BORDER = 15;
  const PREFIXES = ["COLONIA ", "COL ", "FRACCIONAMIENTO ", "FRACC ", "FRAC "];
  const MUNICIPIOS = { "SAN PEDRO TLAQUEPAQUE": "TLAQUEPAQUE", GDL: "GUADALAJARA" };

  const norm = (s) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toUpperCase().replace(/[^A-Z0-9]+/g, " ").trim();
  // fold normalizes like the API's colonia index: norm plus the usual prefixes dropped.
  const fold = (s) => {
    const n = norm(s);
    const p = PREFIXES.find((x) => n.startsWith(x));
    return p ? n.slice(p.length) : n;
  };
  const municipioKey = (m) => {
    const k = norm(m);
    return MUNICIPIOS[k] || k;
  };
  const joinES = (items) => items.length < 2 ? items.join("") : items.slice(0, -1).join(", ") + " y " + items[items.length - 1];
  const zonesOf = (s) => s ? s.split(",").map(Number) : [];

  // zones(props) reads z and p: all the colonia's zones by share of its area, the ones it is
  // really in (main), the ones it only borders, and whether it is split between zones.
  function zones(props) {
    const zs = zonesOf(props.z);
    const shares = new Map();
    if (props.p) {
      for (const z of zs) shares.set(z, 0);
      for (const part of props.p.split(",")) {
        const [z, pct] = part.split(":");
        if (z) shares.set(Number(z), Number(pct));
      }
    }
    if (zs.length < 2 || !shares.size) return { all: zs, main: zs, border: [], split: zs.length > 1, shares };
    const all = [...zs].sort((a, b) => shares.get(b) - shares.get(a));
    const main = all.filter((z, i) => i === 0 || shares.get(z) >= BORDER);
    const border = all.filter((z) => !main.includes(z));
    return { all, main, border, split: main.length > 1, shares };
  }
  const zoneWord = (zs) => (zs.length > 1 ? "zonas " : "zona ") + joinES(zs.map(String));
  // theZones: "la zona 6" · "las zonas 5 y 6".
  const theZones = (zs) => (zs.length > 1 ? "las " : "la ") + zoneWord(zs);
  const borderWord = (zs) => `al límite con ${theZones(zs)}`;
  // label: "Zona 6" · "Zonas 5 y 6" · "Zona 6, al límite con la zona 5" · "Fuera de la rotación".
  function label(props) {
    const z = zones(props);
    if (!z.all.length) return "Fuera de la rotación";
    const main = zoneWord(z.main);
    return main.charAt(0).toUpperCase() + main.slice(1) + (z.border.length ? `, ${borderWord(z.border)}` : "");
  }
  // describe: the sentence a card shows above the zones, or null for a plain single-zone colonia.
  function describe(props) {
    const z = zones(props);
    if (z.all.length < 2) return null;
    if (z.split) {
      const pct = z.shares.size ? ` (más o menos ${joinES(z.main.map((zone) => `${Math.round(z.shares.get(zone))} %`))} de su superficie)` : "";
      return `Esta colonia queda repartida entre las ${zoneWord(z.main)}${pct}. Mira en el mapa de qué lado del límite entre zonas queda tu casa, o usa tu ubicación.`
        + (z.border.length ? ` También toca el límite de ${theZones(z.border)}.` : "");
    }
    return `Esta colonia está en ${theZones(z.main)}, ${borderWord(z.border)}. Si vives junto a ese límite, revisa también los días de ${z.border.length > 1 ? "esas zonas" : `la zona ${z.border[0]}`}.`;
  }

  // TopoJSON → GeoJSON. Arcs are delta-encoded and quantized; a negative index is the arc
  // reversed, and consecutive arcs share their junction point, which is pushed only once.
  function decode(topo) {
    const [sx, sy] = topo.transform.scale;
    const [tx, ty] = topo.transform.translate;
    const arcs = topo.arcs.map((arc) => {
      let x = 0, y = 0;
      return arc.map(([dx, dy]) => { x += dx; y += dy; return [x * sx + tx, y * sy + ty]; });
    });
    const ring = (idx) => {
      const pts = [];
      for (const i of idx) {
        const a = i < 0 ? arcs[~i].slice().reverse() : arcs[i];
        if (pts.length) pts.pop();
        for (const p of a) pts.push(p);
      }
      return pts;
    };
    const geometry = (g) => g.type === "Polygon"
      ? { type: "Polygon", coordinates: g.arcs.map(ring) }
      : { type: "MultiPolygon", coordinates: g.arcs.map((poly) => poly.map(ring)) };
    const features = (name) => topo.objects[name].geometries.map((g, i) => ({ type: "Feature", id: i, properties: g.properties, geometry: geometry(g) }));
    return { colonias: features("colonias"), zonas: features("zonas"), meta: topo.meta || {} };
  }
  const inRing = ([x, y], ring) => {
    let hit = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [x1, y1] = ring[i], [x2, y2] = ring[j];
      if ((y1 > y) !== (y2 > y) && x < (x2 - x1) * (y - y1) / (y2 - y1) + x1) hit = !hit;
    }
    return hit;
  };
  // contains(f, [lng, lat]).
  const contains = (f, pt) => (f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates)
    .some((rings) => inRing(pt, rings[0]) && !rings.slice(1).some((r) => inRing(pt, r)));

  let loading = null;
  function load() {
    if (!loading) {
      loading = fetch(DATA).then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); }).then(decode);
      loading.catch(() => { loading = null; });
    }
    return loading;
  }
  // find: the colonias drawn under a name from SIAPA's list, in that municipio when given.
  function find(colonias, name, municipio) {
    const n = fold(name);
    const m = municipio ? municipioKey(municipio) : null;
    return colonias.filter((f) => fold(f.properties.n) === n && (!m || f.properties.m.split(/\s+y\s+/i).some((x) => municipioKey(x) === m)));
  }

  function tiles(L, map) {
    map.attributionControl.setPrefix('<a href="https://leafletjs.com">Leaflet</a>');
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    }).addTo(map);
  }
  const node = (tag, className, text) => {
    const n = document.createElement(tag);
    if (className) n.className = className;
    if (text != null) n.textContent = text;
    return n;
  };

  // draw puts the zones and every colonia on map. opts: dark, days(zone) → text or null,
  // onClick(feature, event). Returns the layers, the home bounds and highlight helpers.
  function draw(L, map, { colonias, zonas }, opts = {}) {
    const colors = COLORS[opts.dark ? "dark" : "light"];
    const color = (z) => colors[z] || "#888888";
    const edge = opts.dark ? "#0b1a24" : "#1f2d3a";
    const faint = opts.dark ? "#9bb8ca" : "#6b7f8c";
    const ink = opts.dark ? "#f0f9ff" : "#0c1e2c";
    const halo = opts.dark ? "#06141d" : "#ffffff";
    let focus = null;
    const zoneStyle = (f) => {
      const z = f.properties.z;
      const dim = focus && focus !== z;
      return { color: color(z), weight: dim ? 1 : 2, fillColor: color(z), fillOpacity: dim ? 0.04 : 0.16 };
    };
    const zoneLayer = L.geoJSON({ type: "FeatureCollection", features: zonas }, { interactive: false, style: zoneStyle }).addTo(map);
    const home = zoneLayer.getBounds().pad(0.04);
    const coloniaStyle = (f) => {
      const z = zones(f.properties);
      if (!z.all.length) return { color: faint, weight: 0.8, fillColor: "#000000", fillOpacity: focus ? 0 : 0.02, dashArray: null };
      const dim = focus && !z.all.includes(focus);
      return { color: dim ? faint : edge, weight: dim ? 0.6 : 1, fillColor: color(z.main[0]), fillOpacity: dim ? 0.04 : 0.3, dashArray: z.split ? "4 3" : null };
    };
    const tip = (f) => {
      const p = f.properties;
      const z = zones(p);
      const el = node("span", "", `${p.n} · ${p.m}`);
      if (!z.all.length) {
        el.append(node("span", "sub", "Fuera de la rotación"));
        return el;
      }
      for (const zone of z.main) {
        const line = node("span", "sub");
        const dot = node("span", "dot");
        dot.style.setProperty("--zc", color(zone));
        const days = opts.days && opts.days(zone);
        line.append(dot, `Zona ${zone}` + (days ? `: ${days}` : ""));
        el.append(line);
      }
      if (z.border.length) el.append(node("span", "sub", borderWord(z.border).replace(/^al/, "Al")));
      return el;
    };
    const coloniaLayer = L.geoJSON({ type: "FeatureCollection", features: colonias }, {
      renderer: L.canvas({ padding: 0.5 }),
      style: coloniaStyle,
      onEachFeature: (f, layer) => {
        layer.bindTooltip(() => tip(f), { sticky: true, className: "map-label" });
        layer.on("click", (e) => { if (opts.onClick) opts.onClick(f, e); });
        layer.on("mouseover", () => layer.setStyle({ weight: 2, fillOpacity: 0.5 }));
        layer.on("mouseout", () => coloniaLayer.resetStyle(layer));
      },
    }).addTo(map);
    let marks = [];
    // highlight outlines f over everything; label (text) floats above it.
    function highlight(f, label) {
      const gj = { type: "Feature", geometry: f.geometry, properties: {} };
      const group = L.featureGroup([
        L.geoJSON(gj, { interactive: false, style: { color: halo, weight: 9, fill: false } }),
        L.geoJSON(gj, { interactive: false, style: { color: ink, weight: 4, fill: false } }),
      ]).addTo(map);
      if (label) {
        const b = group.getBounds();
        const t = L.tooltip({ permanent: true, direction: "top", className: "map-label" }).setLatLng([b.getNorth(), b.getCenter().lng]).setContent(node("span", "", label)).addTo(map);
        group.on("remove", () => t.remove());
      }
      marks.push(group);
      return group;
    }
    function clearHighlights() {
      for (const g of marks) g.remove();
      marks = [];
    }
    function setFocus(z) {
      focus = z;
      zoneLayer.setStyle(zoneStyle);
      coloniaLayer.setStyle(coloniaStyle);
    }
    return { zoneLayer, coloniaLayer, home, color, ink, halo, highlight, clearHighlights, setFocus };
  }

  const icon = (name) => {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "i");
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `/icons.svg?v=5#${name}`);
    svg.append(use);
    return svg;
  };
  // cross is a plain × for closing: the sprite's "x" is the X (Twitter) logo used on /escribe.
  const cross = () => {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "i");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("aria-hidden", "true");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M6 6l12 12M18 6L6 18");
    svg.append(path);
    return svg;
  };
  // card builds the colonia card the pages float over the map (an <aside class="card">).
  // o: title, subtitle, sentence (a warning above the zones, or null), main (zones the
  // colonia is in), side (zones it only borders), extra (zones the other source gives) with
  // extraNote, days(z) → text or null, next(z) → ISO date or null, dateES(iso), color(z),
  // links(z) → nodes for the buttons, note (text or node), onClose().
  function card(o) {
    const c = node("aside", "card");
    const close = node("button", "close");
    close.type = "button";
    close.setAttribute("aria-label", "Cerrar");
    close.append(cross());
    close.addEventListener("click", () => { if (o.onClose) o.onClose(); });
    c.append(close, node("h2", "", o.title), node("p", "where", o.subtitle));
    const zbox = (z, side) => {
      const box = node("div", side ? "zbox side" : "zbox");
      box.style.setProperty("--zc", o.color(z));
      const days = o.days(z);
      box.append(node("p", "zn", side ? `Zona ${z} · al otro lado del límite` : `Zona ${z}`), node("p", "zd", days || "No pudimos cargar los días"));
      const next = o.next(z);
      if (next) {
        const line = node("p", "next");
        line.append(icon("calendar"), " Próximo racionamiento: ", node("strong", "", o.dateES(next)));
        box.append(line);
      }
      return box;
    };
    const main = o.main || [], side = o.side || [], extra = o.extra || [];
    if (!main.length) {
      const out = node("div", "zbox");
      out.append(node("p", "zn", "Fuera de la rotación"), node("p", "zd", "Según el mapa del SIAPA, aquí no toca racionamiento."));
      c.append(out);
    }
    if (o.sentence) c.append(node("p", "warn", o.sentence));
    for (const z of main) c.append(zbox(z, false));
    for (const z of side) c.append(zbox(z, true));
    if (o.extraNote) c.append(node("p", "warn", o.extraNote));
    for (const z of extra) c.append(zbox(z, false));
    const all = [...main, ...side, ...extra];
    if (all.length && o.links) {
      const sub = node("div", "subscribe");
      for (const z of all) sub.append(...o.links(z));
      c.append(sub);
    }
    if (o.note) c.append(typeof o.note === "string" ? node("p", "note", o.note) : o.note);
    return c;
  }

  return { DATA, BORDER, COLORS, norm, fold, joinES, zonesOf, zones, label, describe, borderWord, zoneWord, theZones, decode, contains, load, find, tiles, draw, card, icon, cross };
})();
