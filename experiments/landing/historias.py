"""Writes web/h1.html … web/h5.html: the phone landing (m5) with different information over each
zone's map card. Wider screens see the landing as is.
Run from the repo root: python3 experiments/landing/historias.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import movil  # noqa: E402

NAMES = {"h1": "Próximo corte", "h2": "La cifra", "h3": "La más reportada", "h4": "La semana", "h5": "Todo junto"}

# Shared over every variant: the zone's days from the API, and a panel at the foot of each map card.
CSS = """
@media (max-width: 760px) {
  .m5-map { aspect-ratio: 2 / 3 }
  .m5-over { position: absolute; z-index: 1000; left: 0; right: 0; bottom: 0; padding: 34px 12px 12px; pointer-events: none;
    background: linear-gradient(transparent, color-mix(in srgb, var(--surface) 92%, transparent) 38%); color: var(--fg); font-size: .9rem; line-height: 1.3 }
  .m5-over:empty { display: none }
  .m5-card .leaflet-control-attribution { display: none }
  .h-k { font-size: .68rem; letter-spacing: .07em; text-transform: uppercase; color: var(--muted); font-weight: 700 }
  .h-big { font: 800 2.4rem/1 var(--serif, Georgia, serif); color: #cc361e; font-variant-numeric: tabular-nums }
  @media (prefers-color-scheme: dark) { .h-big { color: #ea6d56 } }
  .h-hoy { display: inline-block; background: var(--zc); color: #fff; font-size: .72rem; font-weight: 700; letter-spacing: .05em; text-transform: uppercase; padding: 2px 7px; border-radius: 4px }
  .h-week { display: grid; grid-template-columns: repeat(7, 1fr); gap: 3px; margin-top: 6px }
  .h-week span { display: grid; place-items: center; height: 26px; border-radius: 4px; font-size: .72rem; font-weight: 700; border: 1px solid var(--line); background: var(--surface); color: var(--muted) }
  .h-week span.c { background: var(--zc); border-color: var(--zc); color: #fff }
  .h-week span.t { outline: 2px solid var(--fg); outline-offset: 1px }
  .h-row { display: flex; align-items: baseline; gap: 8px; flex-wrap: wrap }
  .h-name { font-weight: 700; font-size: 1.05rem }
}"""

# Each variant fills over(n, i) with i: { days, next, hoy, total, cs } for zone n.
COMMON = r"""
  const DAYS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"];
  const hoyISO = new Date().toLocaleDateString("en-CA", { timeZone: "America/Mexico_City" });
  const dayName = (iso) => new Date(iso + "T12:00").toLocaleDateString("es-MX", { weekday: "long", day: "numeric", month: "long" });
  const info = (n) => {
    const z = api.find((x) => x.zone === n) || { days: [], next: [] };
    const cs = mine(n), total = g.colonias.filter((f) => aguaMapa.zones(f.properties).main.includes(n)).length;
    const next = z.next.find((x) => x >= hoyISO);
    return { days: z.days, hoy: next === hoyISO, next: z.next.find((x) => x > hoyISO), total, cs,
      week: cs.filter((c) => c.pub.dias >= 7).length, top: [...cs].sort((a, b) => b.pub.n - a.pub.n)[0] };
  };
  const week = (i) => `<div class="h-week">${DAYS.map((d, j) => {
    const today = (new Date(hoyISO + "T12:00").getDay() + 6) % 7 === j;
    return `<span class="${i.days.includes(d) ? "c" : ""}${today ? " t" : ""}">${d[0].toUpperCase()}</span>`;
  }).join("")}</div>`;
  const cut = (i) => i.hoy ? '<span class="h-hoy">Hoy hay corte</span>' : i.next ? `Próximo corte: <b>${dayName(i.next)}</b>` : "";
  const nm = (c) => aguaM.name(`${c.f.properties.n}|`);
"""

OVER = {
    "h1": r"""(n) => { const i = info(n); return `<div class="h-k">Cortes: ${aguaMapa.joinES(i.days)}</div><div style="margin-top:4px">${cut(i)}</div>`; }""",
    "h2": r"""(n) => { const i = info(n); return `<div class="h-row"><span class="h-big">${i.week}</span><span>de sus ${i.total} colonias llevan <b>una semana o más sin agua</b></span></div>`; }""",
    "h3": r"""(n) => { const i = info(n); return i.top ? `<div class="h-k">La más reportada</div><div class="h-name">${nm(i.top)}</div><div>${i.top.pub.n} reportes${i.top.pub.dias ? ` · hasta ${i.top.pub.dias} días sin agua` : ""}</div>` : '<div class="h-k">Nadie ha publicado aún que falte el agua aquí</div>'; }""",
    "h4": r"""(n) => { const i = info(n); return `<div class="h-k">Su semana · ${aguaMapa.joinES(i.days)}</div>${week(i)}<div style="margin-top:6px">${cut(i)}</div>`; }""",
    "h5": r"""(n) => { const i = info(n); return `<div class="h-row"><span class="h-big" style="font-size:1.9rem">${i.week}</span><span>colonias con una semana o más sin agua</span></div>${week(i)}<div style="margin-top:6px;font-size:.85rem">${cut(i)}${i.top ? ` · más reportes: <b>${nm(i.top)}</b> (${i.top.pub.n})` : ""}</div>`; }""",
}


def variant(key):
    v = dict(movil.V["m5"])
    js = v["js"]
    a = "if (aguaM.phone) Promise.all([fetch(aguaMapa.DATA).then((r) => r.json()), aguaM.datos]).then(([topo, d]) => {"
    b = ("if (aguaM.phone) Promise.all([fetch(aguaMapa.DATA).then((r) => r.json()), aguaM.datos, "
         "fetch(\"https://api.aguagdl.com/v1/zones\").then((r) => r.json()).catch(() => [])]).then(([topo, d, api]) => {")
    c = '<span class="m5-tag">Zona ${n}</span></article>`; }).join("");'
    assert a in js and c in js
    js = js.replace(a, b, 1)
    js = js.replace("  const track = document.getElementById(\"m5-track\")", COMMON + "  const over = " + OVER[key] + ";\n  const track = document.getElementById(\"m5-track\")", 1)
    js = js.replace(c, '<span class="m5-tag">Zona ${n}</span><div class="m5-over">${over(n)}</div></article>`; }).join("");', 1)
    # The map leaves room for the zone's tag above and the panel below.
    f = "    map.fitBounds(zone.getBounds(), { padding: [10, 10] });"
    assert f in js
    js = js.replace(f, "    const foot = el.closest(\".m5-card\").querySelector(\".m5-over\");\n"
                    "    // Zoomed onto where the zone's reports are (the whole zone when it has none), a step closer than a plain fit.\n"
                    "    const where = cs.length ? L.latLngBounds(cs.map((c) => mid(c.f))) : zone.getBounds();\n"
                    "    map.fitBounds(where, { paddingTopLeft: [24, 56], paddingBottomRight: [24, 24 + (foot ? foot.offsetHeight - 24 : 0)], maxZoom: 15 });\n"
                    "    map.setZoom(map.getZoom() + (n === 2 ? 0 : 0.25), { animate: false }); // zone 2's two pieces need the whole width", 1)
    v["js"] = js
    v["css"] = v["css"] + CSS
    return v


def main():
    src = (Path(__file__).parent / "index-before-m5.html").read_text()
    movil.NAMES = NAMES
    for key in NAMES:
        (movil.WEB / f"{key}.html").write_text(movil.build(key, variant(key), src))
        print("wrote", key)


if __name__ == "__main__":
    main()
