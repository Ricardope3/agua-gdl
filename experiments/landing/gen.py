import re, sys, pathlib
web = pathlib.Path(sys.argv[1])
src = (web / "index.html").read_text()
head, rest = src.split("<body>", 1)
header = re.search(r'  <header class="top">.*?</header>\n', rest, re.S).group(0)
footer = re.search(r'  <footer>.*?</footer>\n', rest, re.S).group(0)
base_main = re.search(r'  <main>\n(.*?)  </main>\n', rest, re.S).group(1)
congreso = re.search(r'    <section class="congreso".*?</section>\n', base_main, re.S).group(0)
que = re.search(r'    <section aria-labelledby="que">.*?</section>\n', base_main, re.S).group(0)
why = re.search(r'    <section class="why".*?</section>\n', base_main, re.S).group(0)
contact = re.search(r'    <section class="contact".*?</section>\n', base_main, re.S).group(0)
mapfig = re.search(r'        <figure class="hero-fig">.*?</figure>\n', base_main, re.S).group(0)
aviso = re.search(r'        <a class="aviso" href="/avisos">.*?</a>\n', base_main, re.S).group(0)

I = lambda n: f'<svg class="i" aria-hidden="true"><use href="/icons.svg?v=3#{n}"/></svg>'
TG = '<span class="nw"><svg class="tg" aria-hidden="true"><use href="/icons.svg?v=3#telegram"/></svg> Telegram</span>'

NAMES = {1: "Buscador primero", 2: "Calendario en vivo", 3: "Buscador + semana", 4: "Semana + buscador", 5: "Lado a lado"}

SWITCH_CSS = """
.variant-bar { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 6px; margin: 0 -16px; padding: 6px 16px; background: #1c1400; color: #fde68a; font-size: .78rem }
.variant-bar strong { margin-right: 4px }
.variant-bar a { color: #fde68a; text-decoration: none; padding: 2px 8px; border-radius: 999px; border: 1px solid #fde68a55 }
.variant-bar a[aria-current="page"] { background: #fde68a; color: #1c1400; font-weight: 700 }
"""

def switcher(n):
    cur = ' aria-current="page"'
    links = ['<a href="/">Actual</a>'] + [f'<a href="/v{i}"{cur if i == n else ""} title="{NAMES[i]}">v{i}</a>' for i in NAMES]
    return f'  <div class="variant-bar"><strong>Prueba · v{n}: {NAMES[n]}</strong>{"".join(links)}</div>\n'

# Shared client code: today's date in Guadalajara and the zone schedule from the API.
ZONES_JS = r"""
  const API = "https://api.aguagdl.com";
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "America/Mexico_City" }).format(new Date());
  const addDays = (iso, n) => { const d = new Date(iso + "T12:00:00Z"); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
  const tomorrow = addDays(today, 1);
  const dayES = (iso) => new Intl.DateTimeFormat("es-MX", { timeZone: "UTC", weekday: "long", day: "numeric", month: "short" }).format(new Date(iso + "T12:00:00Z")).replace(".", "");
  const whenES = (iso) => iso === today ? "hoy" : iso === tomorrow ? "mañana" : dayES(iso);
  const nextCut = (z) => z.next.find((d) => d >= today);
  const joinES = (a) => a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " y " + a[a.length - 1];
  const zonesP = fetch(API + "/v1/zones").then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); });
"""

def page(n, css, main, script=""):
    h = head.replace("<title>Agua GDL · La crisis del agua en Guadalajara</title>",
                     f'<title>Agua GDL · Variante {n}</title>\n<meta name="robots" content="noindex">')
    h = h.replace("</style>", SWITCH_CSS + css + "</style>")
    body = "<body>\n<div class=\"wrap\">\n" + switcher(n) + header + "\n  <main>\n" + main + "  </main>\n\n" + footer + "</div>\n"
    if script:
        body += "<script>\n(() => {" + ZONES_JS + script + "})();\n</script>\n"
    (web / f"v{n}.html").write_text(h + body + "</body>\n</html>\n")

# v1: the colonia search right in the hero.
page(1, """
.hero1 { display: grid; gap: 28px; padding: 20px 0 36px }
.hero1 h1 { margin-bottom: 10px }
.quick { background: var(--surface); border: 1px solid var(--line); border-top: 3px solid var(--brand); border-radius: 12px; box-shadow: var(--shadow); padding: 18px; margin: 22px 0 0 }
.quick label { display: block; font-weight: 600; margin: 0 0 8px }
.quick .row { display: flex; flex-wrap: wrap; gap: 8px }
.quick input { flex: 1 1 220px; min-width: 0; font: inherit; color: var(--fg); background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; box-shadow: var(--shadow) }
.quick input:focus-visible { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px var(--ring) }
.quick button.button { font: inherit; font-weight: 500; font-size: .95rem; cursor: pointer }
.quick .or { margin: 10px 0 0; color: var(--muted); font-size: .9rem }
.band { display: grid; gap: 14px; margin: 0 0 40px }
@media (min-width: 720px) { .hero1 { grid-template-columns: 1.05fr 1fr; align-items: center } .band { grid-template-columns: 1fr 1fr } }
""", f"""    <div class="hero1">
      <div>
        <h1>¿Te toca corte mañana?</h1>
        <p class="lede">El SIAPA <mark>raciona el agua</mark> en más de 600 colonias hasta marzo de 2027. Escribe tu colonia y te decimos tu zona y tus días.</p>
        <form class="quick" action="/mizona" method="get" role="search">
          <label for="q">Tu colonia</label>
          <div class="row">
            <input id="q" name="q" type="search" autocomplete="off" placeholder="Por ejemplo: Las Juntas" required maxlength="80">
            <button class="button glow" type="submit">{I("search")}Ver mi zona</button>
          </div>
          <p class="or">o <a href="/mizona">usa tu ubicación</a>: es lo más exacto.</p>
        </form>
      </div>
      <div class="hero-side">
{mapfig}      </div>
    </div>
    <div class="band">
{aviso}        <a class="aviso" href="/escribe">
          <span class="aviso-head"><span class="i-badge" style="background:#7c3aed">{I("landmark")}</span>El Congreso decide el contrato del acueducto</span>
          <span class="aviso-time">$48,296 M</span>
          <span class="aviso-text">pagaría el Estado en 25 años. Pide a las 38 diputaciones que no lo aprueben a ciegas.</span>
          <span class="button">Escribir al Congreso</span>
        </a>
    </div>
{congreso}{que}{why}{contact}""")

# v2: live schedule of the seven zones up front.
page(2, """
.hero2 { padding: 20px 0 8px }
.hero2 .lede { margin: 0 0 18px }
.today { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 0 0 14px; font-weight: 600 }
.pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: .85rem }
.pill.hot { background: #fee2e2; color: #991b1b } .pill.warm { background: #fef3c7; color: #92400e }
.ztiles { list-style: none; margin: 0 0 18px; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 150px), 1fr)); gap: 10px }
.ztile { display: block; height: 100%; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; color: var(--fg); text-decoration: none; box-shadow: var(--shadow); border-left: 5px solid var(--zc, var(--brand)) }
.ztile:hover { border-color: var(--zc, var(--brand)) }
.ztile b { display: block; font-size: 1.05rem }
.ztile .when { display: block; font-size: 1.35rem; font-weight: 700; letter-spacing: -.02em; line-height: 1.2; margin: 4px 0 2px }
.ztile .when::first-letter { text-transform: uppercase }
.ztile small { color: var(--muted); font-size: .8rem }
.ztile.hot { background: color-mix(in srgb, #ef4444 10%, var(--surface)) } .ztile.warm { background: color-mix(in srgb, #f59e0b 12%, var(--surface)) }
.ztiles .skeleton { height: 92px; border-radius: 12px; background: var(--subtle) }
.hero2 .buttons { margin: 0 0 32px }
.split { display: grid; gap: 14px; margin: 0 0 40px }
@media (min-width: 720px) { .split { grid-template-columns: 1.2fr 1fr; align-items: start } }
@media (prefers-color-scheme: dark) { .pill.hot { background: #450a0a; color: #fecaca } .pill.warm { background: #422006; color: #fde68a } }
""", f"""    <div class="hero2">
      <h1>La crisis del agua en Guadalajara</h1>
      <p class="lede">El SIAPA <mark>raciona el agua</mark> por zonas, de 2 a 3 días por semana, hasta marzo de 2027. Así va la semana:</p>
      <p class="today" id="today" aria-live="polite"></p>
      <ul class="ztiles" id="ztiles">{'<li class="skeleton"></li>' * 7}</ul>
      <div class="buttons">
        <a class="button glow" href="/mizona">{I("map-pin")}¿No sabes tu zona? Búscala</a>
        <a class="button alt" href="/avisos">{I("bell")}Avísenme a las 8 p. m.</a>
      </div>
    </div>
    <div class="split">
      <div class="hero-side">
{mapfig}      </div>
{aviso}    </div>
{congreso}{que}{why}{contact}""", """
  const COLORS = ["", "#e11d48", "#f59e0b", "#10b981", "#0ea5e9", "#8b5cf6", "#ec4899", "#14b8a6"];
  const list = document.getElementById("ztiles");
  const head = document.getElementById("today");
  zonesP.then((zones) => {
    list.replaceChildren(...zones.map((z) => {
      const d = nextCut(z);
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = "/mizona";
      a.className = "ztile" + (d === today ? " hot" : d === tomorrow ? " warm" : "");
      a.style.setProperty("--zc", COLORS[z.zone] || "");
      const b = document.createElement("b"); b.textContent = `Zona ${z.zone}`;
      const w = document.createElement("span"); w.className = "when"; w.textContent = d ? whenES(d) : "sin fecha";
      const s = document.createElement("small"); s.textContent = joinES(z.days);
      a.append(b, w, s); li.append(a); return li;
    }));
    const hot = zones.filter((z) => nextCut(z) === today).map((z) => z.zone);
    const warm = zones.filter((z) => nextCut(z) === tomorrow).map((z) => z.zone);
    const pill = (cls, text) => { const p = document.createElement("span"); p.className = "pill " + cls; p.textContent = text; return p; };
    head.replaceChildren(...[hot.length ? pill("hot", `Hoy: zona${hot.length > 1 ? "s" : ""} ${joinES(hot)}`) : null, warm.length ? pill("warm", `Mañana: zona${warm.length > 1 ? "s" : ""} ${joinES(warm)}`) : null].filter(Boolean));
  }).catch(() => { list.hidden = true; head.textContent = "No pudimos cargar el calendario. Búscalo en «Mi zona»."; });
""")

CSS1 = """
.hero1 { display: grid; gap: 28px; padding: 20px 0 36px }
.hero1 h1 { margin-bottom: 10px }
.quick { background: var(--surface); border: 1px solid var(--line); border-top: 3px solid var(--brand); border-radius: 12px; box-shadow: var(--shadow); padding: 18px; margin: 22px 0 0 }
.quick label { display: block; font-weight: 600; margin: 0 0 8px }
.quick .row { display: flex; flex-wrap: wrap; gap: 8px }
.quick input { flex: 1 1 220px; min-width: 0; font: inherit; color: var(--fg); background: var(--surface); border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; box-shadow: var(--shadow) }
.quick input:focus-visible { outline: none; border-color: var(--brand); box-shadow: 0 0 0 3px var(--ring) }
.quick button.button { font: inherit; font-weight: 500; font-size: .95rem; cursor: pointer }
.quick .or { margin: 10px 0 0; color: var(--muted); font-size: .9rem }
.band { display: grid; gap: 14px; margin: 0 0 40px }
@media (min-width: 720px) { .hero1 { grid-template-columns: 1.05fr 1fr; align-items: center } .band { grid-template-columns: 1fr 1fr } }
"""
CSS2 = """
.hero2 { padding: 20px 0 8px }
.hero2 .lede { margin: 0 0 18px }
.today { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin: 0 0 14px; font-weight: 600 }
.pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: .85rem }
.pill.hot { background: #fee2e2; color: #991b1b } .pill.warm { background: #fef3c7; color: #92400e }
.ztiles { list-style: none; margin: 0 0 18px; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, 150px), 1fr)); gap: 10px }
.ztile { display: block; height: 100%; background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 12px 14px; color: var(--fg); text-decoration: none; box-shadow: var(--shadow); border-left: 5px solid var(--zc, var(--brand)) }
.ztile:hover { border-color: var(--zc, var(--brand)) }
.ztile b { display: block; font-size: 1.05rem }
.ztile .when { display: block; font-size: 1.35rem; font-weight: 700; letter-spacing: -.02em; line-height: 1.2; margin: 4px 0 2px }
.ztile .when::first-letter { text-transform: uppercase }
.ztile small { color: var(--muted); font-size: .8rem }
.ztile.hot { background: color-mix(in srgb, #ef4444 10%, var(--surface)) } .ztile.warm { background: color-mix(in srgb, #f59e0b 12%, var(--surface)) }
.ztiles .skeleton { height: 92px; border-radius: 12px; background: var(--subtle) }
.hero2 .buttons { margin: 0 0 32px }
.split { display: grid; gap: 14px; margin: 0 0 40px }
@media (min-width: 720px) { .split { grid-template-columns: 1.2fr 1fr; align-items: start } }
@media (prefers-color-scheme: dark) { .pill.hot { background: #450a0a; color: #fecaca } .pill.warm { background: #422006; color: #fde68a } }
"""
TILES_JS = """
  const COLORS = ["", "#e11d48", "#f59e0b", "#10b981", "#0ea5e9", "#8b5cf6", "#ec4899", "#14b8a6"];
  const list = document.getElementById("ztiles");
  const head = document.getElementById("today");
  zonesP.then((zones) => {
    list.replaceChildren(...zones.map((z) => {
      const d = nextCut(z);
      const li = document.createElement("li");
      const a = document.createElement("a");
      a.href = "/mizona";
      a.className = "ztile" + (d === today ? " hot" : d === tomorrow ? " warm" : "");
      a.style.setProperty("--zc", COLORS[z.zone] || "");
      const b = document.createElement("b"); b.textContent = `Zona ${z.zone}`;
      const w = document.createElement("span"); w.className = "when"; w.textContent = d ? whenES(d) : "sin fecha";
      const s = document.createElement("small"); s.textContent = joinES(z.days);
      a.append(b, w, s); li.append(a); return li;
    }));
    const hot = zones.filter((z) => nextCut(z) === today).map((z) => z.zone);
    const warm = zones.filter((z) => nextCut(z) === tomorrow).map((z) => z.zone);
    const pill = (cls, text) => { const p = document.createElement("span"); p.className = "pill " + cls; p.textContent = text; return p; };
    head.replaceChildren(...[hot.length ? pill("hot", `Hoy: zona${hot.length > 1 ? "s" : ""} ${joinES(hot)}`) : null, warm.length ? pill("warm", `Mañana: zona${warm.length > 1 ? "s" : ""} ${joinES(warm)}`) : null].filter(Boolean));
  }).catch(() => { list.hidden = true; head.textContent = "No pudimos cargar el calendario. Búscalo en «Mi zona»."; });
"""
TILES = '<p class="today" id="today" aria-live="polite"></p>\n' + '      <ul class="ztiles" id="ztiles">' + '<li class="skeleton"></li>' * 7 + '</ul>\n'
def form(label="Tu colonia", glow=True):
    return f"""<form class="quick" action="/mizona" method="get" role="search">
          <label for="q">{label}</label>
          <div class="row">
            <input id="q" name="q" type="search" autocomplete="off" placeholder="Por ejemplo: Las Juntas" required maxlength="80">
            <button class="button{' glow' if glow else ''}" type="submit">{I("search")}Ver mi zona</button>
          </div>
          <p class="or">o <a href="/mizona">usa tu ubicación</a>: es lo más exacto.</p>
        </form>
"""
BAND = f"""    <div class="band">
{aviso}        <a class="aviso" href="/escribe">
          <span class="aviso-head"><span class="i-badge" style="background:#7c3aed">{I("landmark")}</span>El Congreso decide el contrato del acueducto</span>
          <span class="aviso-time">$48,296 M</span>
          <span class="aviso-text">pagaría el Estado en 25 años. Pide a las 38 diputaciones que no lo aprueben a ciegas.</span>
          <span class="button">Escribir al Congreso</span>
        </a>
    </div>
"""

# v3: v1's search hero, then v2's week of zones, then the two cards.
page(3, CSS1 + CSS2 + """
.week { margin: 0 0 32px }
.week h2 { font-size: 1.3rem; margin: 0 0 10px }
""", f"""    <div class="hero1">
      <div>
        <h1>¿Te toca corte mañana?</h1>
        <p class="lede">El SIAPA <mark>raciona el agua</mark> en más de 600 colonias hasta marzo de 2027. Escribe tu colonia y te decimos tu zona y tus días.</p>
        {form()}      </div>
      <div class="hero-side">
{mapfig}      </div>
    </div>
    <section class="week" aria-labelledby="semana" style="border-top:0;padding:0">
      <h2 id="semana">Así va la semana</h2>
      {TILES}    </section>
{BAND}{congreso}{que}{why}{contact}""", TILES_JS)

# v4: v2's week up front, v1's search box right under it instead of the buttons.
page(4, CSS1 + CSS2 + """
.hero2 .quick { margin: 0 0 32px; max-width: 640px }
""", f"""    <div class="hero2">
      <h1>¿Te toca corte mañana?</h1>
      <p class="lede">El SIAPA <mark>raciona el agua</mark> por zonas, de 2 a 3 días por semana, hasta marzo de 2027. Así va la semana:</p>
      {TILES}      {form("¿No sabes tu zona? Escribe tu colonia")}    </div>
    <div class="split">
      <div class="hero-side">
{mapfig}      </div>
{aviso}    </div>
{congreso}{que}{why}{contact}""", TILES_JS)

# v5: search on the left, a compact week on the right; the map moves below.
page(5, CSS1 + CSS2 + """
.hero5 { display: grid; gap: 24px; padding: 20px 0 32px }
.hero5 .side h2 { font-size: 1.1rem; margin: 0 0 8px }
.hero5 .ztiles { grid-template-columns: repeat(2, 1fr); gap: 8px }
.hero5 .ztile { padding: 8px 12px; display: grid; grid-template-columns: auto 1fr; column-gap: 10px; align-items: baseline }
.hero5 .ztile .when { font-size: 1.05rem; margin: 0 }
.hero5 .ztile small { grid-column: 1 / -1 }
.hero5 .ztiles .skeleton { height: 56px }
.mapband { display: grid; gap: 14px; margin: 0 0 40px }
@media (min-width: 720px) { .hero5 { grid-template-columns: 1.1fr 1fr; align-items: start } .mapband { grid-template-columns: 1.2fr 1fr; align-items: start } }
""", f"""    <div class="hero5">
      <div>
        <h1>¿Te toca corte mañana?</h1>
        <p class="lede">El SIAPA <mark>raciona el agua</mark> en más de 600 colonias hasta marzo de 2027. Escribe tu colonia y te decimos tu zona y tus días.</p>
        {form()}      </div>
      <div class="side">
        <h2>Así va la semana</h2>
        {TILES}      </div>
    </div>
    <div class="mapband">
      <div class="hero-side">
{mapfig}      </div>
      <div class="hero-side">
{aviso}        <a class="aviso" href="/escribe">
          <span class="aviso-head"><span class="i-badge" style="background:#7c3aed">{I("landmark")}</span>El Congreso decide el contrato del acueducto</span>
          <span class="aviso-time">$48,296 M</span>
          <span class="aviso-text">pagaría el Estado en 25 años. Pide a las 38 diputaciones que no lo aprueben a ciegas.</span>
          <span class="button">Escribir al Congreso</span>
        </a>
      </div>
    </div>
{congreso}{que}{why}{contact}""", TILES_JS)
