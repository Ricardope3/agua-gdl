"""Writes ten noindex landing variants that bring /fotos' photos onto the landing: web/portada-1.html … portada-10.html.

    python3 experiments/portada-fotos/build.py --force

Each is web/index.html as it stands plus one idea (markup, CSS and JS spliced in at fixed anchors), and a bar
to switch between them. Photos come from pipelines/fotos.py (the reviewed list), so nothing outside /fotos
appears. Writes straight into web/ (public on push), hence --force. Retire them like the other variants
once one is ported to web/index.html.
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
CARTELES = [t for t in TS if t["cartel"]]
N = len(TS)


def ph(t):
    return {"i": "/" + t["img"], "r": round(t["w"] / t["h"], 3), "f": t["fecha"], "d": fotos.fecha_corta(t["fecha"]),
            "c": t["cols"][0] if t["cols"] else "", "cs": t["cols"], "q": t["quien"], "u": t["url"], "t": t["tema"],
            "k": t["cartel"], "v": t["video"], "a": t["alt"]}


DATA = "<script>window.FOTOS = " + json.dumps([ph(t) for t in TS], ensure_ascii=False, separators=(",", ":")) + ";</script>"


def cap(t):
    return f'{E(fotos.fecha_corta(t["fecha"]))} · {E(t["cols"][0] if t["cols"] else t["quien"])}'


def a_img(t, cls="", extra=""):
    return (f'<a class="{cls}" href="{E(t["url"])}" target="_blank" rel="noopener"{extra}>'
            f'<img src="/{t["img"]}" width="{t["w"]}" height="{t["h"]}" alt="{E(t["alt"])}" loading="lazy" decoding="async">')


MAS = f'<a class="ver-todas" href="/fotos">Ver las {N} fotos</a>'

COMMON_CSS = """
.ver-todas { font-weight: 600 }
.ph-sec { margin: 8px 0 28px }
.ph-sec h2 { font-size: 1.35rem; margin: 0 0 4px } .ph-sec .sub { color: var(--muted); margin: 0 0 12px; font-size: .92rem }
.vbar { position: fixed; left: 50%; bottom: 12px; transform: translateX(-50%); z-index: 1000; display: flex; gap: 4px; max-width: calc(100vw - 16px); overflow-x: auto; scrollbar-width: none; padding: 5px; border-radius: 999px; background: var(--surface); border: 1px solid var(--line); box-shadow: 0 4px 18px rgb(0 0 0 / .18); font-family: var(--font) }
.vbar a { white-space: nowrap; padding: 6px 11px; border-radius: 999px; font-size: .82rem; color: var(--fg); text-decoration: none }
.vbar a:hover { background: var(--subtle) } .vbar a[aria-current] { background: var(--primary); color: var(--on-primary) }
body { padding-bottom: 64px }
.vnote { font-size: .85rem; color: var(--muted); margin: 0 0 6px }
/* full-screen viewer shared by the story and deck variants */
.visor { position: fixed; inset: 0; z-index: 1100; background: rgb(6 10 20 / .96); color: #fff; display: grid; grid-template-rows: auto 1fr auto; font-family: var(--font) }
.visor[hidden] { display: none }
.visor .bars { display: flex; gap: 3px; padding: 10px 12px 0 } .visor .bars i { flex: 1; height: 3px; background: rgb(255 255 255 / .3); border-radius: 2px } .visor .bars i.on { background: #fff }
.visor .top { display: flex; justify-content: space-between; align-items: center; padding: 8px 12px; gap: 8px }
.visor .top b { font-size: .95rem } .visor .x { background: none; border: 0; color: #fff; font-size: 1.8rem; line-height: 1; cursor: pointer; padding: 0 6px }
.visor .stage { position: relative; display: grid; place-items: center; min-height: 0; padding: 0 8px }
.visor .stage img { max-width: 100%; max-height: 100%; object-fit: contain; border-radius: 6px }
.visor .prev, .visor .next { position: absolute; top: 0; bottom: 0; width: 40%; background: none; border: 0; cursor: pointer }
.visor .prev { left: 0 } .visor .next { right: 0 }
.visor .foot { padding: 10px 14px 18px; display: flex; justify-content: space-between; align-items: center; gap: 12px; font-size: .88rem }
.visor .foot a { color: #fff; font-weight: 600; white-space: nowrap }
"""

VISOR_JS = """<script>
window.abrirVisor = (list, start, title) => {
  let v = document.querySelector('.visor');
  if (!v) {
    v = document.createElement('div');
    v.className = 'visor'; v.setAttribute('role', 'dialog'); v.setAttribute('aria-modal', 'true');
    v.innerHTML = '<div class="bars"></div><div class="top"><b></b><button class="x" aria-label="Cerrar">×</button></div><div class="stage"><img alt=""><button class="prev" aria-label="Anterior"></button><button class="next" aria-label="Siguiente"></button></div><div class="foot"><span class="c"></span><a target="_blank" rel="noopener">Ver la publicación</a></div>';
    document.body.append(v);
  }
  let i = start, last = document.activeElement;
  const show = () => {
    const p = list[i];
    v.querySelector('.stage img').src = p.i; v.querySelector('.stage img').alt = p.a;
    v.querySelector('.top b').textContent = title || (i + 1) + ' de ' + list.length;
    v.querySelector('.c').textContent = p.d + (p.c && !title ? ' · ' + p.c : '') + ' · ' + p.q + (p.v ? ' · video' : '');
    v.querySelector('.foot a').href = p.u;
    v.querySelector('.bars').innerHTML = list.length <= 30 ? list.map((_, k) => '<i' + (k <= i ? ' class="on"' : '') + '></i>').join('') : '';
  };
  const go = (d) => { i = (i + d + list.length) % list.length; show(); };
  const close = () => { v.hidden = true; document.removeEventListener('keydown', key); last?.focus(); };
  const key = (e) => { if (e.key === 'Escape') close(); if (e.key === 'ArrowRight') go(1); if (e.key === 'ArrowLeft') go(-1); };
  v.querySelector('.prev').onclick = () => go(-1); v.querySelector('.next').onclick = () => go(1); v.querySelector('.x').onclick = close;
  let x0 = null;
  v.ontouchstart = (e) => { x0 = e.touches[0].clientX; };
  v.ontouchend = (e) => { if (x0 === null) return; const dx = e.changedTouches[0].clientX - x0; if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1); x0 = null; };
  document.addEventListener('keydown', key);
  v.hidden = false; show(); v.querySelector('.x').focus();
};
</script>"""


# Anchors in web/index.html
A_HEAD = '    <section class="m-only m5"'
A_ILUS = '<img class="ilus" src="/img/ilustracion.png"'
A_MAP = '    <div class="maphero">'
A_WALL = '    <section class="wall" aria-labelledby="dicen">'
A_FORM_END = '      </form>\n    </section>\n    <section class="wall"'


def v1():
    picks = CARTELES[:9]
    items = "".join(f'<li style="--rot:{(-3, 2, -1, 3, -2, 1, -3, 2, -1)[k]}deg">{a_img(t)}<span>{cap(t)}</span></a></li>' for k, t in enumerate(picks))
    html_ = (f'<section class="ph-sec tendedero" aria-labelledby="tend"><h2 id="tend">El tendedero</h2>'
             f'<p class="sub">Carteles de las protestas por el agua, como los publicaron medios y vecinos. Toca uno para ver la publicación. {MAS}</p>'
             f'<ul class="cuerda">{items}</ul></section>')
    css = """
.tendedero .cuerda { list-style: none; margin: 0; padding: 26px 8px 18px; display: flex; gap: 18px; overflow-x: auto; scroll-snap-type: x proximity; position: relative;
  background: radial-gradient(120% 40px at 50% -14px, transparent 98%, #8a6d4a 99%, #8a6d4a 100%, transparent 101%) top/100% 30px no-repeat }
.tendedero li { flex: 0 0 auto; width: 190px; margin: 0; background: #fffdf7; padding: 8px 8px 10px; box-shadow: 0 6px 14px rgb(0 0 0 / .18); transform: rotate(var(--rot)); transform-origin: 50% -12px; scroll-snap-align: center; position: relative; transition: transform .25s }
.tendedero li:hover { transform: rotate(0deg) scale(1.03) }
.tendedero li::before { content: ""; position: absolute; top: -18px; left: calc(50% - 5px); width: 10px; height: 26px; background: #c8a46a; border-radius: 2px; box-shadow: inset 0 0 0 1px rgb(0 0 0 / .15) }
.tendedero img { display: block; width: 100%; height: 150px; object-fit: cover }
.tendedero a { color: #333; text-decoration: none } .tendedero span { display: block; margin-top: 6px; font-family: var(--serif); font-size: .82rem }
@media (max-width: 760px) { .tendedero li { width: 150px } .tendedero img { height: 120px } }
@media (prefers-reduced-motion: reduce) { .tendedero li { transition: none } }
"""
    return {"after_head": html_, "css": css}


def v2():
    pool = [t for t in TS if not t["video"]][:40]
    rows = [pool[0::2], pool[1::2]]
    strips = "".join(f'<div class="fila{" rev" if k else ""}"><div class="pista">' + "".join(a_img(t, "f") + "</a>" for t in r + r) + "</div></div>" for k, r in enumerate(rows))
    html_ = f'<section class="ph-sec cinta" aria-label="Fotos de la crisis">{strips}<p class="sub">Fotos que publicaron medios y vecinos desde el 11 de octubre. {MAS}</p></section>'
    css = """
main > .cinta { max-width: none; margin: 0 calc(50% - 50vw) 24px; overflow: hidden }
.cinta .fila { overflow: hidden; margin: 0 0 6px }
.cinta .pista { display: flex; gap: 6px; width: max-content; animation: cinta 140s linear infinite }
.cinta .rev .pista { animation-direction: reverse; animation-duration: 170s }
.cinta:hover .pista { animation-play-state: paused }
.cinta a.f { flex: 0 0 auto; display: block; height: 130px } .cinta img { height: 100%; width: auto; display: block; border-radius: 3px }
.cinta .sub { max-width: 928px; margin: 8px auto 0; padding: 0 16px }
@keyframes cinta { to { transform: translateX(-50%) } }
@media (max-width: 760px) { .cinta a.f { height: 96px } }
@media (prefers-reduced-motion: reduce) { .cinta .pista { animation: none } .cinta .fila { overflow-x: auto } }
"""
    return {"after_head": html_, "css": css}


def v3():
    pool = (CARTELES + [t for t in TS if not t["cartel"]])[:24]
    grid = "".join(f'<img src="/{t["img"]}" alt="" loading="eager" decoding="async">' for t in pool)
    css = """
main > .headline.cartel { position: relative; isolation: isolate; color: #fff; padding: 28px 22px 30px; margin: 0 auto 18px; border-radius: 6px; overflow: hidden }
.headline .fondo { position: absolute; inset: 0; z-index: -1; display: grid; grid-template-columns: repeat(6, 1fr); grid-auto-rows: 1fr; gap: 2px }
.headline .fondo img { width: 100%; height: 100%; object-fit: cover; filter: grayscale(.35) }
.headline .fondo::after { content: ""; position: absolute; inset: 0; background: linear-gradient(90deg, rgb(10 16 34 / .9) 0%, rgb(10 16 34 / .78) 55%, rgb(10 16 34 / .45) 100%) }
.headline.cartel h1, .headline.cartel p { color: #fff } .headline.cartel .kicker { color: #fca5a5 }
.headline.cartel .ilus { filter: drop-shadow(0 4px 14px rgb(0 0 0 / .5)); background: rgb(255 255 255 / .9); border-radius: 6px }
.headline .pie { position: absolute; left: 22px; bottom: 6px; margin: 0; font-size: .72rem; color: rgb(255 255 255 / .8) } .headline .pie a { color: #fff }
@media (max-width: 760px) { .headline .fondo { grid-template-columns: repeat(4, 1fr) } main > .headline.cartel { padding: 18px 14px 28px; margin: 0 -8px 14px } .headline .pie { left: 14px } }
"""
    return {"in_head": f'<div class="fondo" aria-hidden="true">{grid}</div><p class="pie">Fotos de medios y vecinos · <a href="/fotos">ver las {N}</a></p>', "css": css}


def v4():
    pool = (CARTELES[:6] + [t for t in TS if not t["cartel"]][:14])
    cells = "".join(f'<img src="/{t["img"]}" alt="" loading="eager" decoding="async">' for t in pool)
    drop = "data:image/svg+xml," + "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 140'%3E%3Cpath d='M50 0C50 0 0 62 0 92a50 48 0 0 0 100 0C100 62 50 0 50 0z'/%3E%3C/svg%3E"
    html_ = f'<a class="gota" href="/fotos" aria-label="Ver las {N} fotos de la crisis"><span class="m">{cells}</span><span class="t">{N} fotos de la crisis</span></a>'
    css = f"""
.cartel {{ grid-template-columns: 1fr auto auto }}
.gota {{ display: grid; justify-items: center; gap: 6px; text-decoration: none; color: var(--fg) }}
.gota .m {{ width: 200px; aspect-ratio: 100/140; display: grid; grid-template-columns: repeat(4, 1fr); grid-auto-rows: 1fr; gap: 2px; -webkit-mask: url("{drop}") center/contain no-repeat; mask: url("{drop}") center/contain no-repeat; background: #017CDC }}
.gota img {{ width: 100%; height: 100%; object-fit: cover }}
.gota .t {{ font-family: var(--serif); font-style: italic; font-size: .9rem }} .gota:hover .t {{ text-decoration: underline }}
@media (max-width: 760px) {{ .cartel {{ grid-template-columns: minmax(0, 1fr) 92px }} .gota {{ grid-column: 1 / -1; display: flex; align-items: center; gap: 10px; justify-self: start }} .gota .m {{ width: 46px }} .gota .t {{ font-size: .95rem }} }}
"""
    return {"after_ilus": html_, "css": css}


def colonias_top(k):
    by = {}
    for t in TS:
        for c in t["cols"][:1]:
            by.setdefault(c, []).append(t)
    return sorted(by.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:k]


def v5():
    tops = colonias_top(14)
    circles = "".join(
        f'<li><button type="button" data-c="{E(c)}"><span class="ring"><img src="/{g[0]["img"]}" alt=""></span><span class="n">{E(c)}</span><span class="k">{len(g)}</span></button></li>'
        for c, g in tops)
    html_ = (f'<section class="ph-sec historias" aria-labelledby="hist"><h2 id="hist">Lo que se ve en cada colonia</h2>'
             f'<p class="sub">Toca una colonia para ver sus fotos una por una; cada una lleva a su publicación. {MAS}</p><ul>{circles}</ul></section>')
    js = """<script>
document.querySelectorAll('.historias button').forEach((b) => b.addEventListener('click', () => {
  const list = window.FOTOS.filter((p) => p.cs.includes(b.dataset.c));
  window.abrirVisor(list, 0, b.dataset.c);
}));
</script>"""
    css = """
.historias ul { list-style: none; margin: 0; padding: 4px 2px 8px; display: flex; gap: 14px; overflow-x: auto; scroll-snap-type: x proximity }
.historias li { margin: 0; flex: 0 0 auto; scroll-snap-align: start }
.historias button { background: none; border: 0; padding: 0; cursor: pointer; display: grid; justify-items: center; gap: 4px; width: 84px; color: var(--fg); font: inherit; position: relative }
.historias .ring { width: 74px; height: 74px; border-radius: 50%; padding: 3px; background: conic-gradient(var(--alarm), #f59e0b, var(--brand), var(--alarm)) }
.historias .ring img { width: 100%; height: 100%; object-fit: cover; border-radius: 50%; border: 3px solid var(--bg); display: block }
.historias .n { font-size: .75rem; line-height: 1.2; text-align: center; max-width: 84px; overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical }
.historias .k { position: absolute; top: 0; right: 4px; background: var(--alarm); color: #fff; font-size: .68rem; font-weight: 700; border-radius: 999px; padding: 1px 6px }
"""
    return {"after_head": html_, "css": css, "js": VISOR_JS + js}


def v6():
    pool = [t for t in CARTELES if t["w"] >= t["h"]]
    t0 = pool[0]
    html_ = (f'<figure class="ph-sec fotodia"><span class="sello">Foto del día</span>'
             f'{a_img(t0, "fd")}</a>'
             f'<figcaption><span class="c">{cap(t0)}</span> — foto publicada por <span class="q">{E(t0["quien"])}</span>. '
             f'<a class="u" href="{E(t0["url"])}" target="_blank" rel="noopener">Ver la publicación</a> · {MAS}</figcaption></figure>')
    js = """<script>
(() => {
  const pool = window.FOTOS.filter((p) => p.k && p.r >= 1);
  const day = Math.floor((Date.now() - 6 * 3600e3) / 864e5);
  const p = pool[day % pool.length], f = document.querySelector('.fotodia');
  f.querySelector('a.fd').href = p.u; f.querySelector('a.u').href = p.u;
  const img = f.querySelector('img'); img.src = p.i; img.alt = p.a; img.removeAttribute('width'); img.removeAttribute('height');
  f.querySelector('.c').textContent = p.d + ' · ' + (p.c || p.q); f.querySelector('.q').textContent = p.q;
})();
</script>"""
    css = """
.fotodia { margin: 0 0 26px; position: relative; border-top: 3px solid var(--fg); border-bottom: 1px solid var(--fg); padding: 12px 0 10px; display: grid; grid-template-columns: minmax(0, 600px) 1fr; gap: 6px 22px; align-items: end }
@media (max-width: 760px) { .fotodia { grid-template-columns: 1fr } }
.fotodia a.fd { display: block } .fotodia img { display: block; width: 100%; max-height: 520px; object-fit: cover; height: auto }
.fotodia .sello { position: absolute; top: 22px; left: 10px; z-index: 1; background: var(--alarm); color: #fff; font: 700 .72rem/1 var(--font); letter-spacing: .12em; text-transform: uppercase; padding: 6px 9px }
.fotodia figcaption { font-family: var(--serif); font-size: 1.02rem; line-height: 1.5; color: var(--muted); margin-top: 8px } .fotodia figcaption .c { color: var(--fg); font-weight: 700 }
"""
    return {"after_head": html_, "css": css, "js": js}


def v7():
    by = {}
    for t in TS:
        by.setdefault(t["fecha"], []).append(t)
    days = sorted(by)
    cells = []
    for d in days:
        g = sorted(by[d], key=lambda t: (not t["cartel"], t["tema"] != "protesta", t["img"]))
        t = g[0]
        cells.append(f'<li>{a_img(t)}<span class="d">{E(fotos.fecha_corta(d))}</span><span class="n">{len(g)} {"foto" if len(g) == 1 else "fotos"}</span></a></li>')
    html_ = (f'<section class="ph-sec diapordia" aria-labelledby="dpd"><h2 id="dpd">Día por día, en fotos</h2>'
             f'<p class="sub">Una foto por cada día con publicaciones, del {E(fotos.fecha_larga(days[0]))} al {E(fotos.fecha_larga(days[-1]))}. Desliza. {MAS}</p>'
             f'<ol>{"".join(cells)}</ol></section>')
    js = "<script>(() => { const o = document.querySelector('.diapordia ol'); o.scrollLeft = o.scrollWidth; })();</script>"
    css = """
.diapordia ol { list-style: none; margin: 0; padding: 0 0 8px; display: flex; gap: 6px; overflow-x: auto; scroll-snap-type: x mandatory; position: relative }
.diapordia ol::before { content: ""; position: absolute; left: 0; right: 0; top: 186px; height: 2px; background: var(--line) }
.diapordia li { margin: 0; flex: 0 0 150px; scroll-snap-align: end }
.diapordia a { display: block; text-decoration: none; color: var(--fg) }
.diapordia img { display: block; width: 150px; height: 180px; object-fit: cover; border-radius: 4px }
.diapordia .d { display: block; margin-top: 12px; font-family: var(--serif); font-weight: 700; font-size: 1rem } .diapordia .d::before { content: ""; display: inline-block; width: 9px; height: 9px; border-radius: 50%; background: var(--alarm); margin-right: 6px; vertical-align: .05em }
.diapordia .n { display: block; color: var(--muted); font-size: .78rem }
@media (max-width: 760px) { .diapordia li { flex-basis: 120px } .diapordia img { width: 120px; height: 150px } .diapordia ol::before { top: 156px } }
"""
    return {"before_map": html_, "css": css, "js": js}


def v8():
    pubs = json.loads(fotos.PUB.read_text())["publicaciones"]
    temas = json.loads(fotos.TEMAS.read_text())["temas"]
    seen, picks = set(), []
    for p in sorted(pubs, key=lambda p: p["fecha"], reverse=True):
        v = p.get("vista")
        if v in temas and v not in seen and p.get("tipo") != "comentario" and len(p.get("cita", "")) >= 40:
            seen.add(v)
            picks.append(p)
        if len(picks) == 8:
            break
    items = []
    for p in picks:
        w, h = fotos.dims(WEB / p["vista"])
        who = p["quien"] or "Vecinos"
        lugar = ", ".join(fotos.nombre(c)[0] for c in p["colonias"][:1])
        items.append(f'<li><a class="im" href="{E(p["url"])}" target="_blank" rel="noopener"><img src="/{p["vista"]}" width="{w}" height="{h}" alt="" loading="lazy" decoding="async"></a>'
                     f'<div><q>{E(p["cita"])}</q><span class="who">{E(who)} · {E(lugar + " · ") if lugar else ""}{E(fotos.fecha_larga(p["fecha"]))} · '
                     f'<a href="{E(p["url"])}" target="_blank" rel="noopener">ver la publicación</a></span></div></li>')
    html_ = (f'<section class="ph-sec citas" aria-labelledby="citas-h"><h2 id="citas-h">Lo que se publica, con su foto</h2>'
             f'<p class="sub">Cada cita va con la foto de la misma publicación, tal como la publicaron. {MAS}</p><ul>{"".join(items)}</ul></section>')
    css = """
.citas ul { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(380px, 100%), 1fr)); gap: 18px }
.citas li { margin: 0; display: grid; grid-template-columns: 112px 1fr; gap: 12px; align-items: start; border-top: 2px solid var(--fg); padding-top: 10px }
.citas .im img { width: 112px; height: 112px; object-fit: cover; display: block; border-radius: 3px }
.citas q { display: block; quotes: "«" "»"; font-family: var(--serif); font-size: 1rem; line-height: 1.4 }
.citas .who { display: block; color: var(--muted); font-size: .8rem; margin-top: 6px }
"""
    return {"before_wall": html_, "css": css}


def v9():
    html_ = (f'<div class="tusfotos" aria-live="polite"><p class="tf-h">Fotos de tu colonia <span id="tf-n"></span></p><div class="tf-grid" id="tf-grid"></div>'
             f'<p class="tf-more"><a href="/fotos">Ver las {N} fotos</a></p></div>')
    js = """<script>
(() => {
  const fold = (s) => s.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase().trim();
  const q = document.getElementById('q'), grid = document.getElementById('tf-grid'), n = document.getElementById('tf-n');
  const draw = () => {
    const s = fold(q.value);
    let list = s.length < 3 ? window.FOTOS.slice(0, 8) : window.FOTOS.filter((p) => p.cs.some((c) => fold(c).includes(s)));
    n.textContent = s.length < 3 ? '· las más recientes; escribe tu colonia' : list.length ? '· ' + list.length + (list.length === 1 ? ' foto' : ' fotos') : '· ninguna publicada todavía. Eso no quiere decir que tenga agua.';
    grid.innerHTML = list.slice(0, 8).map((p) => '<a href="' + p.u + '" target="_blank" rel="noopener"><img src="' + p.i + '" alt="' + p.a.replace(/"/g, '&quot;') + '" loading="lazy"><span>' + p.d + ' · ' + (p.c || p.q) + '</span></a>').join('');
  };
  q.addEventListener('input', draw); draw();
})();
</script>"""
    css = """
.tusfotos { margin: 14px 0 0 } .tf-h { font-weight: 700; margin: 0 0 8px } .tf-h span { font-weight: 400; color: var(--muted); font-size: .88rem }
.tf-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 4px } .tf-grid a { position: relative; display: block; aspect-ratio: 1; overflow: hidden; border-radius: 4px; color: #fff }
.tf-grid img { width: 100%; height: 100%; object-fit: cover; display: block }
.tf-grid span { position: absolute; inset: auto 0 0 0; padding: 14px 6px 4px; font-size: .7rem; background: linear-gradient(transparent, rgb(0 0 0 / .7)) }
.tf-more { margin: 6px 0 0; font-size: .9rem }
@media (max-width: 560px) { .tf-grid { grid-template-columns: repeat(2, 1fr) } }
"""
    return {"after_form": html_, "css": css, "js": js}


def v10():
    top = CARTELES[:3]
    stack = "".join(f'<img src="/{t["img"]}" alt="" style="--k:{k}">' for k, t in enumerate(top))
    html_ = f'<button type="button" class="mazo" aria-label="Ver {N} fotos de la crisis"><span class="pila">{stack}</span><span class="t"><b>{N}</b> fotos</span></button>'
    js = """<script>
document.querySelector('.mazo').addEventListener('click', () => window.abrirVisor(window.FOTOS, 0));
</script>"""
    css = """
.mazo { position: fixed; right: 16px; bottom: 74px; z-index: 800; display: flex; align-items: center; gap: 10px; padding: 8px 14px 8px 8px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); color: var(--fg); box-shadow: 0 6px 20px rgb(0 0 0 / .2); cursor: pointer; font: inherit }
.mazo .pila { position: relative; width: 52px; height: 44px }
.mazo .pila img { position: absolute; inset: 0; width: 44px; height: 44px; object-fit: cover; border-radius: 6px; border: 2px solid #fff; box-shadow: 0 2px 6px rgb(0 0 0 / .25); transform: translateX(calc(var(--k) * 4px)) rotate(calc((var(--k) - 1) * 8deg)) }
.mazo .t { font-size: .9rem; white-space: nowrap } .mazo b { font-size: 1.05rem }
.mazo:hover .pila img { transform: translateX(calc(var(--k) * 7px)) rotate(calc((var(--k) - 1) * 14deg)) }
@media (prefers-reduced-motion: no-preference) { .mazo .pila img { transition: transform .25s } }
"""
    return {"end": html_, "css": css, "js": VISOR_JS + js}


VARIANTS = [
    ("Tendedero", "Una cuerda con carteles de las protestas colgados con pinzas, bajo el titular.", v1),
    ("Cinta", "Dos tiras de fotos que corren despacio bajo el titular; se detienen al pasar el cursor.", v2),
    ("Portada a sangre", "El titular sobre un muro de fotos oscurecido, como portada de periódico.", v3),
    ("Gota de fotos", "Junto a la caricatura, una gota de agua hecha de fotos que lleva a /fotos.", v4),
    ("Historias por colonia", "Círculos por colonia; al tocar uno, sus fotos se ven una por una en pantalla completa.", v5),
    ("Foto del día", "Una foto grande de portada, distinta cada día, con su pie de foto y su fuente.", v6),
    ("Día por día", "Una línea de tiempo deslizable con una foto por cada día de la crisis, antes del mapa.", v7),
    ("Citas con su foto", "Lo que publican medios y vecinos, cada cita con la foto de su misma publicación.", v8),
    ("Busca tu colonia", "Al escribir tu colonia en «¿Y en tu colonia?», aparecen sus fotos.", v9),
    ("Mazo flotante", "Un botón con un mazo de fotos siempre a la mano; abre una galería en pantalla completa.", v10),
]


def build(k, name, desc, fn):
    s = (WEB / "index.html").read_text()
    parts = fn()

    def put(anchor, text, before=True):
        nonlocal s
        assert s.count(anchor) == 1, (name, anchor[:40])
        s = s.replace(anchor, text + anchor if before else anchor + text)

    s = re.sub(r'<link rel="canonical"[^>]*>\n', "", s)
    s = s.replace("<title>", '<meta name="robots" content="noindex">\n<title>', 1)
    if "after_head" in parts:
        put(A_HEAD, "    " + parts["after_head"] + "\n")
    if "in_head" in parts:
        put('<div class="headline cartel">', parts["in_head"], before=False)
    if "after_ilus" in parts:
        i = s.index(A_ILUS)
        j = s.index(">", i) + 1
        s = s[:j] + parts["after_ilus"] + s[j:]
    if "before_map" in parts:
        put(A_MAP, "    " + parts["before_map"] + "\n")
    if "before_wall" in parts:
        put(A_WALL, "    " + parts["before_wall"] + "\n")
    if "after_form" in parts:
        assert s.count(A_FORM_END) == 1
        s = s.replace(A_FORM_END, "      </form>\n      " + parts["after_form"] + "\n    </section>\n    <section class=\"wall\"")
    cur = ' aria-current="page"'
    bar = '<nav class="vbar" aria-label="Variantes de la portada">' + "".join(
        f'<a href="/portada-{i}"{cur if i == k else ""} title="{E(d)}">{i} · {E(n)}</a>' for i, (n, d, _) in enumerate(VARIANTS, 1)) + "</nav>"
    note = f'<p class="vnote"><b>Variante {k}: {E(name)}.</b> {E(desc)}</p>\n'
    put("    <div class=\"headline cartel\">", "    " + note)
    end = (parts.get("end", "") + bar + DATA + parts.get("js", "")
           + "<script>addEventListener('load', () => { const b = document.querySelector('.vbar'), a = b.querySelector('[aria-current]'); b.scrollLeft = a.offsetLeft - (b.clientWidth - a.offsetWidth) / 2; });</script>\n")
    put("</body>", end)
    put("</head>", f"<style>{COMMON_CSS}{parts.get('css', '')}</style>\n")
    (WEB / f"portada-{k}.html").write_text(s)


def main():
    if "--force" not in sys.argv:
        sys.exit("portada-fotos: writes public pages into web/; rerun with --force")
    for k, (name, desc, fn) in enumerate(VARIANTS, 1):
        build(k, name, desc, fn)
    print(f"portada-fotos: wrote web/portada-1.html … portada-{len(VARIANTS)}.html")


if __name__ == "__main__":
    main()
