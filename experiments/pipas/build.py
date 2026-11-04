"""Writes the noindex /pipas design variants: web/pipas-v1.html … pipas-v5.html and web/pipas-variantes.html.

Reuses web/pipas.html's <style>, header and footer so the variants keep the site's look.
"""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
WEB = ROOT / "web"
BASE = (ROOT / "web/pipas.html").read_text()

STYLE = re.search(r"(?s)<style>.*?</style>", BASE).group(0)
HEADER = re.search(r'(?s)<header class="top">.*?</header>', BASE).group(0)
FOOTER = re.search(r"(?s)<footer>.*?</footer>", BASE).group(0)

EXTRA_CSS = """
<style>
.vbar { font-size: .85rem; background: var(--subtle); border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; margin: 0 0 16px; display: flex; flex-wrap: wrap; gap: 4px 12px }
.vbar a[aria-current] { font-weight: 700; color: var(--fg) }
.tag { display: inline-block; font-size: .75rem; font-weight: 600; padding: 1px 8px; border-radius: 999px; background: var(--subtle); color: var(--link); vertical-align: .1em; margin-left: 6px }
.tag.warn { background: #fef3c7; color: #92400e }
@media (prefers-color-scheme: dark) { .tag.warn { background: #422006; color: #fcd34d } }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 20px }
.chips button { font: inherit; font-size: .95rem; padding: 8px 14px; border-radius: 999px; border: 1px solid var(--line); background: var(--surface); color: var(--fg); cursor: pointer; box-shadow: var(--shadow) }
.chips button[aria-pressed="true"] { background: var(--primary); color: var(--on-primary); border-color: transparent }
.panel[hidden] { display: none }
.steps { list-style: none; padding: 0; counter-reset: s; margin: 0 }
.steps > li { counter-increment: s; position: relative; padding: 0 0 24px 52px; margin: 0 }
.steps > li::before { content: counter(s); position: absolute; left: 0; top: 0; width: 36px; height: 36px; border-radius: 50%; background: var(--primary); color: var(--on-primary); display: grid; place-items: center; font-weight: 700 }
.steps > li::after { content: ""; position: absolute; left: 17px; top: 40px; bottom: 4px; width: 2px; background: var(--line) }
.steps > li:last-child::after { display: none }
.steps h2 { font-size: 1.25rem; margin: 4px 0 8px }
.tablewrap { overflow-x: auto; margin: 0 0 16px; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); box-shadow: var(--shadow) }
table { border-collapse: collapse; width: 100%; font-size: .95rem }
th, td { text-align: left; padding: 10px 12px; border-bottom: 1px solid var(--line); vertical-align: top }
th { font-size: .8rem; color: var(--muted); font-weight: 600; background: var(--subtle) }
tr:last-child td { border-bottom: 0 }
td .tel { font-size: 1.05rem }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0 12px }
.actions .button { font-size: 1rem }
.button.ghost { background: var(--surface); color: var(--link); border-color: var(--line) }
details { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 4px 16px; margin: 0 0 10px; box-shadow: var(--shadow) }
details summary { cursor: pointer; font-weight: 600; padding: 10px 0; display: flex; align-items: center; gap: 10px }
details[open] summary { border-bottom: 1px solid var(--line); margin-bottom: 12px }
details > *:last-child { margin-bottom: 12px }
.stat { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 0 0 12px }
.stat div { background: var(--surface); border: 1px solid var(--line); border-radius: 12px; padding: 14px }
.stat b { display: block; font-size: 1.6rem; letter-spacing: -.02em }
.stat span { color: var(--muted); font-size: .9rem }
.faq dt { font-family: var(--font); font-size: 1rem; font-weight: 600; padding: 0 }
.faq { display: block } .faq dd { margin: 4px 0 16px; color: var(--muted) }
</style>
"""


def icon(name):
    return f'<svg class="i" aria-hidden="true"><use href="/icons.svg?v=5#{name}"/></svg>'


def h2(id_, ic, text):
    return f'<h2 id="{id_}" class="ih"><span class="i-badge">{icon(ic)}</span>{text}</h2>'


def a(url, text):
    return f'<a href="{url}" rel="noopener">{text}</a>'


def via(*sources):
    return '<p class="via">Fuente: ' + " · ".join(a(u, t) for u, t in sources) + "</p>"


VERIFY = '<span class="tag warn">por confirmar</span>'

AGUA = json.loads((ROOT / "pipelines/cisternas_fuente.json").read_text())
CON_MAPA = {x["municipio"] for x in AGUA["puntos"] + AGUA["colonias"]}

MAP_HEAD = """<link rel="stylesheet" href="/vendor/leaflet-1.9.4/leaflet.css">
<style>
.mapa-agua { height: 380px; border: 1px solid var(--line); border-radius: 12px; margin: 8px 0 8px; box-shadow: var(--shadow); z-index: 0 }
@media (prefers-color-scheme: dark) { .mapa-agua .leaflet-tile-pane { filter: invert(1) hue-rotate(180deg) brightness(.9) contrast(.9) } .mapa-agua.leaflet-container { background: #0c1e2c } }
.leyenda { display: flex; flex-wrap: wrap; gap: 4px 16px; font-size: .85rem; color: var(--muted); margin: 0 0 10px }
.leyenda .pt { display: inline-block; width: 12px; height: 12px; border-radius: 50%; background: var(--brand); box-shadow: 0 0 0 2px var(--surface), 0 0 0 3px var(--brand); vertical-align: -1px; margin-right: 6px }
.leyenda .ar { display: inline-block; width: 14px; height: 10px; background: color-mix(in srgb, var(--brand) 25%, transparent); border: 1.5px dashed var(--brand); vertical-align: -1px; margin-right: 6px }
.mapa-pop { font: 14px/1.45 var(--font) } .mapa-pop b { display: block }
.lista-agua { columns: 2 260px; font-size: .95rem } .lista-agua li { break-inside: avoid }
</style>"""

MAP_SCRIPT = """<script src="/vendor/leaflet-1.9.4/leaflet.js"></script>
<script>
(async () => {
  const els = [...document.querySelectorAll('.mapa-agua')];
  if (!els.length || !window.L) return;
  let d;
  try { d = await (await fetch('/cisternas.json')).json(); } catch { return; }
  const c = getComputedStyle(document.documentElement).getPropertyValue('--brand').trim() || '#0284c7';
  const esc = s => String(s).replace(/[&<>"]/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[ch]);
  const fuente = k => { const f = d.fuentes[k]; return '<a href="' + f.url + '" target="_blank" rel="noopener">' + esc(f.titulo) + '</a>' + (f.mapa ? ' · <a href="' + f.mapa + '" target="_blank" rel="noopener">mapa oficial</a>' : ''); };
  const draw = el => {
    if (el._map) { el._map.invalidateSize(); return; }
    const m = el.dataset.m;
    const map = L.map(el, { zoomSnap: 0.25, scrollWheelZoom: false });
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' }).addTo(map);
    const b = L.latLngBounds([]);
    d.colonias.filter(x => !m || x.municipio === m).forEach(x => {
      const p = L.polygon(x.forma, { color: c, weight: 1.5, dashArray: '4 3', fillColor: c, fillOpacity: .18 }).addTo(map);
      p.bindPopup('<div class="mapa-pop"><b>Cisterna en ' + esc(x.nombre) + ', ' + esc(x.municipio) + '</b>' + (x.lugar ? esc(x.lugar) + '. ' : '') + 'Se publicó solo la colonia, no la dirección.<br>Fuente: ' + fuente(x.fuente) + '</div>');
      b.extend(p.getBounds());
    });
    d.puntos.filter(x => !m || x.municipio === m).forEach(x => {
      const k = L.circleMarker([x.lat, x.lon], { radius: 7, color: '#fff', weight: 2, fillColor: c, fillOpacity: 1 }).addTo(map);
      k.bindPopup('<div class="mapa-pop"><b>' + esc(x.lugar || 'Sin dirección publicada') + '</b>' + esc(x.municipio) + (x.capa === 'SIAPA' ? ', capa «SIAPA» del mapa' : '') + '<br>Según el mapa del Ayuntamiento.<br>Fuente: ' + fuente(x.fuente) + '</div>');
      b.extend(k.getLatLng());
    });
    map.fitBounds(b, { padding: [24, 24], maxZoom: 15 });
    el._map = map;
  };
  const visibles = () => els.forEach(el => { if (el.offsetParent) draw(el); });
  els.forEach(el => { const det = el.closest('details'); if (det) det.addEventListener('toggle', () => { if (det.open) draw(el); }); });
  window.__mapasAgua = visibles;
  visibles();
})();
</script>"""

APORTA = '<p>¿Conoces una cisterna comunitaria que no está aquí? Escríbenos a <span class="number">soporte@aguagdl.com</span> con la dirección y, si puedes, una foto. La revisamos antes de ponerla en el mapa.</p>'


def mapa(m=""):
    return f"""<div class="mapa-agua" data-m="{m}" role="region" aria-label="Mapa de cisternas comunitarias{' en ' + m if m else ''}"></div>
<p class="leyenda"><span><span class="pt"></span>Cisterna en el mapa oficial</span><span><span class="ar"></span>Hay cisterna en la colonia; no se publicó la dirección</span></p>"""


def lista_sin_mapa(m=None):
    items = [x for x in AGUA["sin_coordenadas"] + AGUA["sin_ubicar"] if not m or x["municipio"] == m]
    if not items:
        return ""
    lis = "".join(f"<li>{x['lugar']}{'' if m else ' (' + x['municipio'] + ')'}</li>" for x in items)
    return f"<details><summary>{icon('map-pin')}Otras {len(items)} sin ubicación en el mapa</summary><ul class=\"lista-agua\">{lis}</ul></details>"


# Sources (all opened and checked on 3 Nov 2026 unless marked).
S_SIAPA = ("https://www.siapa.gob.mx/medios-para-solicitar-una-pipa", "SIAPA, medios para solicitar una pipa")
S_ROT = ("https://rotaciondeserviciosiapa.jalisco.gob.mx/", "portal de la rotación")
S_BOT = ("https://www.cronica.com.mx/jalisco/guadalajara/2026/10/23/siapa-incorpora-chatbot-para-reportes-de-calidad-y-falta-de-agua/", "La Crónica, 23 de octubre")
S_GDL = ("https://guadalajara.gob.mx/noticia/apoya-guadalajara-con-pipas-a-colonias-ante-esquema-de-rotacion", "Gobierno de Guadalajara, 19 de octubre")
S_GDL_CIS = ("https://www.cronica.com.mx/jalisco/guadalajara/2026/10/27/reparte-guadalajara-mas-de-46-millones-de-litros-de-agua-e-instala-nueve-cisternas-comunitarias/", "La Crónica, 27 de octubre")
S_ZAP = ("https://www.zapopan.gob.mx/v3/noticias/zapopan-pone-en-marcha-operativo-de-suministro-de-agua-con-45-pipas-y-100-cisternas", "Gobierno de Zapopan, 19 de octubre")
S_ZAP_PRIO = ("https://www.cronica.com.mx/jalisco/guadalajara/2026/10/19/zapopan-desplegara-45-pipas-y-100-cisternas-por-tandeos-del-agua/", "La Crónica, 19 de octubre")
S_ZAP_17 = ("https://www.cronica.com.mx/jalisco/guadalajara/2026/10/21/distribuye-zapopan-hasta-375-mil-litros-de-agua-al-dia-con-11-pipas/", "La Crónica, 21 de octubre")
S_TLQ = ("https://concienciapublica.com.mx/2026/10/14/tlaquepaque-desplegara-32-pipas-gratuitas-ante-los-tandeos-del-siapa/", "Conciencia Pública, 14 de octubre")
S_TLQ_MAP = ("https://www.cronica.com.mx/jalisco/guadalajara/2026/10/22/distribuye-tlaquepaque-56-millones-de-litros-de-agua-ante-desabasto-por-tandeos", "La Crónica, 22 de octubre")
TLQ_MAP = "https://www.google.com/maps/d/viewer?mid=1RDUyGrhgZPHMVaRZDfdnN0RZvI8HL6U"
S_TON = ("https://tonala.gob.mx/portal/2026/10/14/lanza-tonala-programa-emergente-para-el-abasto-de-agua/", "Gobierno de Tonalá, 14 de octubre")
S_TON_MIL = ("https://www.milenio.com/comunidad/instalan-cisternas-tlaquepaque-tonala-apoyar-afectados", "Milenio, 15 de octubre")
S_TLJ = ("https://www.cronica.com.mx/jalisco/guadalajara/2025/12/29/tlajo-ofrece-servicio-de-pipas-gratuitas-ante-cortes-de-agua-del-siapa/", "La Crónica, 29 de diciembre de 2025")
S_BOTNOTA = ("https://www.siapa.gob.mx/prensa/siapa-bot-realiza-consultas-y-reportes-por-whatsapp-de-forma-facil-y-rapida", "SIAPA, 27 de octubre")
S_CEDHJ = ("https://cedhj.org.mx/", "CEDHJ, cómo presentar una queja")
S_NMAS = ("https://www.nmas.com.mx/jalisco/sociedad/siapa-habilita-linea-para-reportar-desabasto-y-mala-calidad-del-agua-en-guadalajara/", "N+, 23 de octubre")
S_PRECIO = ("https://labcsa.org/2026/10/23/suben-precio-de-pipas-tras-cortes-de-agua/", "MURAL, 23 de octubre (copia de LabCSA)")
S_LEY = ("https://congresoweb.congresojal.gob.mx/bibliotecavirtual/legislacion/Leyes/Documentos_PDF-Leyes/Ley%20del%20Agua%20para%20el%20Estado%20y%20sus%20Municipios-300626.pdf", "artículo 90, fracción VI")


def tel(num, href):
    return f'<a class="tel" href="{href}">{num}</a>'


SIAPA_TEL = tel("33 3668 2482", "tel:+523336682482")
SIAPA_073 = tel("073", "tel:073")
FORM = a("https://gobjal.mx/PipasGratis", "formulario en línea")
FORM_NOTE = "El 3 de noviembre el formulario no cargaba (error 504); si falla, llama."
SOCIAL = a("https://www.facebook.com/siapagdl", "Facebook") + " o " + a("https://x.com/siapagdl", "X (@siapagdl)")
BOT = '<span class="number">33 5164 4440</span>'
CEDHJ_TEL = tel("33 3669 1100", "tel:+523336691100")
CEDHJ_WA = tel("33 1156 7342", "https://wa.me/523311567342")

SIAPA_RULES = """<ul>
  <li>«Ten a la mano los datos de tu domicilio y el número de cuenta del Siapa o del agua municipal.»</li>
  <li>«Las pipas podrán surtir aljibes, tambos, cisternas o tinacos que estén a nivel de calle.»</li>
  <li>Pide tu número de reporte y anótalo: si la pipa no llega, con él puedes insistir.</li>
</ul>"""

MUNIS = {
    "guadalajara": dict(
        name="Guadalajara",
        pedir=f"El Ayuntamiento manda al SIAPATEL: {SIAPA_TEL}. Sus pipas son gratuitas; dice que tiene «una flota de hasta 77 pipas».",
        pedir_src=[S_GDL, S_GDL_CIS],
        canal="SIAPATEL 33 3668 2482", horario="24 horas", gratis="Sí",
        ir="Nueve cisternas comunitarias: Plaza Talpita (Talpita Oriente), Centro Barrial Polanquito, parroquia de La Esperanza, parroquia de Margarita Maza de Juárez (San Miguel de Huentitán), Puerto Ángel y Pedernal (San Marcos), Centro Comunitario 4 del DIF (Ampliación Talpita), Mercado Francisco I. Madero (Santa María), Unidad Deportiva 59 «El Campito» (Prados del Nilo) y la colonia San Vicente.",
        ir_src=[S_GDL_CIS],
    ),
    "zapopan": dict(
        name="Zapopan",
        pedir=f"Línea de Atención Ciudadana: {tel('33 2410 1000', 'tel:+523324101000')}, las 24 horas, «para recibir reportes relacionados con el abastecimiento». Da prioridad a «las familias que no cuentan con tinaco, aljibe u otro espacio para almacenar agua» y a «escuelas y centros de salud municipales».",
        pedir_src=[S_ZAP, S_ZAP_PRIO],
        canal="33 2410 1000", horario="24 horas", gratis="No lo dice",
        ir="Cisternas comunitarias de 10 mil litros, «administradas en coordinación con los consejos vecinales»: 17 instaladas al 21 de octubre, de una meta de 100. No ha publicado dónde están.",
        ir_src=[S_ZAP_PRIO, S_ZAP_17],
    ),
    "tlaquepaque": dict(
        name="Tlaquepaque",
        pedir=f"WhatsApp TlaqueChat: {tel('33 2804 8171', 'https://wa.me/523328048171')}, de lunes a domingo de 7:00 a 22:00. Según Conciencia Pública, la alcaldesa reiteró que «no tendrá costo para los habitantes».",
        pedir_src=[S_TLQ],
        canal="WhatsApp 33 2804 8171", horario="Lun–dom, 7:00–22:00", gratis="Sí",
        ir=f"60 cisternas en el {a(TLQ_MAP, 'mapa del Ayuntamiento')}.",
        ir_src=[S_TLQ_MAP],
    ),
    "tonala": dict(
        name="Tonalá",
        pedir=f"WhatsApp: {tel('33 2821 1120', 'https://wa.me/523328211120')}, de lunes a viernes, para reportar la falta de agua.",
        pedir_src=[S_TON],
        canal="WhatsApp 33 2821 1120", horario="Lun–vie", gratis="No lo dice",
        ir="Hasta 30 cisternas en las colonias afectadas «para que los vecinos puedan acercarse por el agua». Las primeras cinco, en Palmas, El Vado, El Moral, Pedregal de Santa Martha y Colinas de Tonalá; no publicó las direcciones.",
        ir_src=[S_TON, S_TON_MIL],
    ),
    "tlajomulco": dict(
        name="Tlajomulco",
        pedir=f"Línea de atención ciudadana {tel('33 3283 4400', 'tel:+523332834400')}, extensiones 4202 y 4226, o la plataforma Conec-Tlajo. {VERIFY} Lo anunció para el corte de enero de 2026; no encontramos un anuncio para la rotación actual.",
        pedir_src=[S_TLJ],
        canal="33 3283 4400 ext. 4202 / 4226", horario="—", gratis="Sí (dic. 2025)",
        ir="No encontramos cisternas anunciadas.",
        ir_src=[],
        verify=True,
    ),
}


def siapa_block(cls="signup"):
    return f"""<div class="{cls}">
  {h2('siapa', 'phone', 'Al SIAPA')}
  <p>{SIAPA_TEL} o {SIAPA_073}, las 24 horas.</p>
  <p>También por su {FORM} o por {SOCIAL}. {FORM_NOTE}</p>
  <p>El SIAPA dice: «Si te quedas sin agua, solicita una pipa gratuita». Sus pipas gratuitas son, según el SIAPA, «para aquellas colonias que no tienen aljibe o en las que por su altitud tienen afectaciones año con año».</p>
  {SIAPA_RULES}
  {via(S_SIAPA, S_ROT)}
</div>"""


def muni_card(key, with_ir=False):
    m = MUNIS[key]
    tag = VERIFY if m.get("verify") else ""
    ir = ""
    if with_ir:
        ir = f'<p><b>Dónde ir por agua:</b> {m["ir"]}</p>'
    srcs = m["pedir_src"] + (m["ir_src"] if with_ir else [])
    seen, uniq = set(), []
    for s in srcs:
        if s[0] not in seen:
            seen.add(s[0]); uniq.append(s)
    return f"""<div class="signup" id="{key}">
  <h3>{m['name']}{tag}</h3>
  <p>{m['pedir']}</p>
  {ir}
  {via(*uniq)}
</div>"""


CISTERNAS = f"""<section aria-labelledby="cisternas">
  {h2('cisternas', 'map-pin', 'Dónde ir por agua')}
  <p>Mientras llega la pipa, algunos municipios pusieron cisternas comunitarias. Lleva tus propios recipientes. Ningún municipio ha publicado horarios ni límites. Toca un punto para ver la dirección y la fuente.</p>
  {mapa()}
  {lista_sin_mapa()}
  <ul>
    <li><b>Guadalajara:</b> {MUNIS['guadalajara']['ir']} ({a(*S_GDL_CIS)})</li>
    <li><b>Tlaquepaque:</b> {MUNIS['tlaquepaque']['ir']} ({a(*S_TLQ_MAP)})</li>
    <li><b>Zapopan:</b> {MUNIS['zapopan']['ir']} ({a(*S_ZAP_17)})</li>
    <li><b>Tonalá:</b> {MUNIS['tonala']['ir']} ({a(*S_TON_MIL)})</li>
  </ul>
  {APORTA}
</section>"""

NO_LLEGA_ITEMS = f"""<ol>
  <li><b>Insiste con tu número de reporte</b> por el mismo canal donde la pediste.</li>
  <li><b>Reporta que no tienes agua al SIAPA Bot</b>, WhatsApp {BOT}. Según La Crónica, por ahora es solo para reportes de falta de agua y de calidad, no para pedir pipa, y da un folio. El SIAPA pide tener «tu recibo de agua o tu Cuenta Contrato» ({a(*S_BOT)}; {a(*S_BOTNOTA)}).</li>
  <li><b>Presenta una queja ante la Comisión Estatal de Derechos Humanos (CEDHJ)</b>: {CEDHJ_TEL}, WhatsApp {CEDHJ_WA}, en {a('https://cedhj.org.mx/', 'cedhj.org.mx')} o en Pedro Moreno 1616, colonia Americana ({a(*S_CEDHJ)}).</li>
</ol>"""

NO_LLEGA = f"""<section aria-labelledby="nollega">
  {h2('nollega', 'megaphone', 'Si la pipa no llega')}
  {NO_LLEGA_ITEMS}
</section>"""

DERECHO_P = f"""<p>Cuando te reducen el agua por escasez, la Ley del Agua de Jalisco te da derecho a «Exigir a las autoridades el suministro de agua potable, única y exclusivamente para uso habitacional», «mediante la dotación gratuita a través de pipas, carros tanques, hidrantes provisionales o públicos», «considerando la disponibilidad de los recursos» del ayuntamiento o del organismo del agua ({a(*S_LEY)}).</p>"""

DERECHO = f"""<section aria-labelledby="derecho">
  {h2('derecho', 'shield-check', 'Es tu derecho')}
  {DERECHO_P}
</section>"""

PRIVADAS_P = f"""<p>Pide primero la pipa gratuita. Un vecino citado por MURAL el 23 de octubre dice que las pipas privadas «te cobran unos 700 a mil 200 pesos, pero por 10 mil litros», es decir, por una pipa completa; en julio, empresas le dieron a MURAL precios de 1,300 a 1,700 pesos por la misma cantidad ({a(*S_PRECIO)}). No encontramos un precio máximo ni un registro oficial de pipas privadas.</p>"""

PRIVADAS = f"""<section aria-labelledby="privadas">
  {h2('privadas', 'info', 'Si pagas una pipa privada')}
  {PRIVADAS_P}
</section>"""

GUARDA_P = f"""<p>El SIAPA pide: «Tapa bien todos los recipientes donde almacenes agua para evitar criaderos de mosquitos y prevenir el dengue» ({a(*S_SIAPA)}).</p>"""

CIFRAS = f"""<section aria-labelledby="cifras">
  {h2('cifras', 'bar-chart', 'Cuántas pipas hay')}
  <div class="stat">
    <div><b>1,492</b><span>solicitudes de pipa al SIAPA</span></div>
    <div><b>6</b><span>pipas del SIAPA, que «han priorizado la atención a hospitales y escuelas»</span></div>
    <div><b>16</b><span>pipas de la Comisión Estatal del Agua</span></div>
  </div>
  <p class="via">Al 23 de octubre. Una sola fuente: {a(*S_NMAS)}, con datos del SIAPA. Los municipios tienen sus propias pipas aparte.</p>
</section>"""

REPORTA = f"""<section aria-labelledby="reporta">
  {h2('reporta', 'users', 'Y repórtalo en el mapa')}
  <p>Cuenta en el <a href="/reportes">mapa de los vecinos</a> que no tienes agua: sin cuenta y anónimo. Si no se reporta, no queda registro.</p>
  <a class="button" href="/reportes">{icon('map-pin')}Reportar mi colonia</a>
</section>"""

OJO = f"""<section aria-labelledby="ojo">
  {h2('ojo', 'info', 'Ten en cuenta')}
  <ul>
    <li>Revisamos estos números el 3 de noviembre de 2026 en las páginas enlazadas. Si alguno ya no funciona, avísanos a <span class="number">soporte@aguagdl.com</span>.</li>
    <li>Zapopan y Tonalá no dicen en sus anuncios si sus pipas cuestan; las del SIAPA (para colonias sin aljibe o afectadas por su altitud), Guadalajara y Tlaquepaque son gratuitas.</li>
    <li>Agua GDL no es del SIAPA ni del gobierno, no tiene partido y no puede mandar pipas.</li>
  </ul>
</section>"""

LEDE = '<p class="lede">Los teléfonos, WhatsApp y formularios oficiales para pedir una pipa, dónde ir por agua mientras llega y qué hacer si no llega. Cada dato tiene su fuente. Agua GDL es una iniciativa ciudadana: no es del SIAPA ni del gobierno y no puede mandar pipas.</p>'

VARIANTS = [
    ("v1", "Por municipio", "Eliges tu municipio y ves solo lo tuyo: a quién pedir, dónde ir por agua y qué hacer si no llega."),
    ("v2", "Paso a paso", "Cinco pasos en orden: pide, anota, ve por agua, insiste, exige."),
    ("v3", "Directorio", "Una tabla con todos los canales, su horario y si es gratis; lo demás abajo, corto."),
    ("v4", "Botones grandes", "Para el celular: botones de llamar y WhatsApp arriba, todo lo demás en secciones que se abren."),
    ("v5", "Guía completa", "La página actual con todo lo nuevo: cisternas, si no llega, pipas privadas, cifras y preguntas."),
]


def vbar(cur):
    current = ' aria-current="page"'
    links = " ".join(
        f'<a href="/pipas-{k}"{current if k == cur else ""}>{k.upper()} · {t}</a>' for k, t, _ in VARIANTS
    )
    return f'<div class="vbar"><a href="/pipas-variantes">Índice</a> {links}</div>'


def page(key, title, body, script=""):
    return f"""<!doctype html>
<html lang="es-MX">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{key.upper()} {title} · Pipas · Agua GDL</title>
<link rel="icon" href="/favicon.ico" sizes="any">
<link rel="icon" href="/logo.svg" type="image/svg+xml">
<script src="/theme.js"></script>
{STYLE}
{EXTRA_CSS}
{MAP_HEAD}
</head>
<body>
<div class="wrap">
  {HEADER}
  <main>
    {vbar(key)}
    {body}
  </main>
  {FOOTER}
</div>
{script}
{MAP_SCRIPT}
</body>
</html>
"""


def v1():
    chips = "".join(
        f'<button type="button" data-m="{k}" aria-pressed="false">{m["name"]}</button>' for k, m in MUNIS.items()
    )
    panels = []
    for k, m in MUNIS.items():
        tag = VERIFY if m.get("verify") else ""
        panels.append(f"""<div class="panel" id="p-{k}" hidden>
  <div class="options">
    <div class="signup">
      <h3 class="ih"><span class="i-badge">{icon('phone')}</span>Pide tu pipa en {m['name']}{tag}</h3>
      <p>{m['pedir']}</p>
      <p>O al SIAPA: {SIAPA_TEL} · {SIAPA_073}, las 24 horas.</p>
      {via(*m['pedir_src'], S_SIAPA)}
    </div>
    <div class="signup">
      <h3 class="ih"><span class="i-badge">{icon('map-pin')}</span>Dónde ir por agua</h3>
      <p>{m['ir']}</p>
      {via(*m['ir_src']) if m['ir_src'] else ''}
    </div>
  </div>
  {('<div class="agua-mapa-bloque">' + mapa(m['name']) + lista_sin_mapa(m['name']) + '</div>') if m['name'] in CON_MAPA else ''}
  {APORTA}
</div>""")
    body = f"""<h1>¿Sin agua? Pide una pipa</h1>
{LEDE}
<h2 class="ih"><span class="i-badge">{icon('map-pin')}</span>¿En qué municipio vives?</h2>
<div class="chips" role="group" aria-label="Municipio">{chips}</div>
<div id="none"><div class="signup"><p>Elige tu municipio para ver sus canales y sus cisternas. Si no sabes, llama al SIAPA: {SIAPA_TEL} o {SIAPA_073}, las 24 horas.</p></div></div>
{''.join(panels)}
<section aria-labelledby="como">
  {h2('como', 'info', 'Al pedirla')}
  {SIAPA_RULES}
  <p>Al SIAPA también por su {FORM} o por {SOCIAL}. {FORM_NOTE}</p>
  {via(S_SIAPA)}
</section>
{NO_LLEGA}
{DERECHO}
{REPORTA}
{OJO}"""
    script = """<script>
document.querySelectorAll('.chips button').forEach(b => b.addEventListener('click', () => {
  document.querySelectorAll('.chips button').forEach(x => x.setAttribute('aria-pressed', x === b));
  document.querySelectorAll('.panel').forEach(p => p.hidden = p.id !== 'p-' + b.dataset.m);
  document.getElementById('none').hidden = true;
  window.__mapasAgua?.();
  history.replaceState(null, '', '#' + b.dataset.m);
}));
const h = location.hash.slice(1);
if (h) document.querySelector('.chips [data-m="' + h + '"]')?.click();
</script>"""
    return page("v1", "Por municipio", body, script)


def v2():
    munis = "".join(muni_card(k) for k in MUNIS)
    body = f"""<h1>¿Sin agua? Así pides una pipa</h1>
{LEDE}
<ol class="steps">
  <li>
    <h2>Pídela al SIAPA o a tu municipio</h2>
    <p>SIAPA: {SIAPA_TEL} o {SIAPA_073}, las 24 horas; también por su {FORM} o por {SOCIAL}. {FORM_NOTE}</p>
    {via(S_SIAPA)}
    <details><summary>{icon('map-pin')}Los canales de cada municipio</summary><div class="options">{munis}</div></details>
  </li>
  <li>
    <h2>Ten tus datos y anota tu número de reporte</h2>
    {SIAPA_RULES}
  </li>
  <li>
    <h2>Mientras llega, ve por agua a una cisterna</h2>
    <ul>
      <li><b>Guadalajara:</b> {MUNIS['guadalajara']['ir']} ({a(*S_GDL_CIS)})</li>
      <li><b>Tlaquepaque:</b> {MUNIS['tlaquepaque']['ir']} ({a(*S_TLQ_MAP)})</li>
      <li><b>Tonalá:</b> {MUNIS['tonala']['ir']} ({a(*S_TON_MIL)})</li>
      <li><b>Zapopan</b> anunció cisternas, pero no ha publicado dónde están ({a(*S_ZAP_17)}).</li>
    </ul>
    {mapa()}
    {lista_sin_mapa()}
    {APORTA}
    {GUARDA_P}
  </li>
  <li>
    <h2>Si no llega, insiste y exige</h2>
    {NO_LLEGA_ITEMS}
    {DERECHO_P}
  </li>
  <li>
    <h2>Repórtalo en el mapa</h2>
    <p>Cuenta en el <a href="/reportes">mapa de los vecinos</a> que no tienes agua: sin cuenta y anónimo. Si no se reporta, no queda registro.</p>
    <a class="button" href="/reportes">{icon('map-pin')}Reportar mi colonia</a>
  </li>
</ol>
{OJO}"""
    return page("v2", "Paso a paso", body)


def v3():
    rows = [
        f'<tr><td><b>SIAPA</b></td><td>{SIAPA_TEL}<br>{SIAPA_073}<br>{FORM}*<br>{SOCIAL}</td><td>24 horas</td><td>Sí, para colonias sin aljibe o afectadas por su altitud</td><td>{a(*S_SIAPA)}</td></tr>'
    ]
    for k, m in MUNIS.items():
        canal = re.search(r'<a class="tel".*?</a>', m["pedir"]).group(0)
        extra = " (ext. 4202 / 4226) o Conec-Tlajo" if k == "tlajomulco" else ""
        tag = VERIFY if m.get("verify") else ""
        rows.append(
            f'<tr id="{k}"><td><b>{m["name"]}</b>{tag}</td><td>{canal}{extra}</td><td>{m["horario"]}</td><td>{m["gratis"]}</td><td>{a(*m["pedir_src"][0])}</td></tr>'
        )
    cis = "".join(
        f'<tr><td><b>{MUNIS[k]["name"]}</b></td><td>{MUNIS[k]["ir"]}</td><td>{a(*MUNIS[k]["ir_src"][-1])}</td></tr>'
        for k in ("guadalajara", "tlaquepaque", "zapopan", "tonala")
    )
    body = f"""<h1>¿Sin agua? Pide una pipa</h1>
{LEDE}
<div class="tablewrap"><table>
  <thead><tr><th>Quién</th><th>Cómo pedirla</th><th>Horario</th><th>¿Gratis?</th><th>Fuente</th></tr></thead>
  <tbody>{''.join(rows)}</tbody>
</table></div>
<p class="via">* {FORM_NOTE} Guadalajara manda al SIAPATEL. «Gratis: no lo dice» quiere decir que su anuncio no dice si cuesta.</p>
<section aria-labelledby="al">
  {h2('al', 'info', 'Al pedirla')}
  {SIAPA_RULES}
</section>
<section aria-labelledby="cisternas">
  {h2('cisternas', 'map-pin', 'Cisternas comunitarias')}
  {mapa()}
  {lista_sin_mapa()}
  <div class="tablewrap"><table>
    <thead><tr><th>Municipio</th><th>Dónde</th><th>Fuente</th></tr></thead>
    <tbody>{cis}</tbody>
  </table></div>
</section>
<section aria-labelledby="nollega">
  {h2('nollega', 'megaphone', 'Si no llega')}
  <div class="tablewrap"><table>
    <thead><tr><th>Dónde</th><th>Contacto</th><th>Para qué</th></tr></thead>
    <tbody>
      <tr><td><b>SIAPA Bot</b></td><td>WhatsApp {BOT}</td><td>Reportar falta de agua o calidad, con folio. Según La Crónica, no es para pedir pipa ({a(*S_BOT)}).</td></tr>
      <tr><td><b>CEDHJ</b></td><td>{CEDHJ_TEL}<br>WhatsApp {CEDHJ_WA}</td><td>Presentar una queja ({a(*S_CEDHJ)}).</td></tr>
    </tbody>
  </table></div>
  {DERECHO_P}
</section>
{REPORTA}
{OJO}"""
    return page("v3", "Directorio", body)


def v4():
    def btns(*items):
        return '<div class="actions">' + "".join(items) + "</div>"

    def b(href, ic, text, ghost=False):
        return f'<a class="button{" ghost" if ghost else ""}" href="{href}" rel="noopener">{icon(ic)}{text}</a>'

    def mb(k, buttons):
        m = MUNIS[k]
        tag = VERIFY if m.get("verify") else ""
        return f"""<div class="signup" id="{k}">
  <h3>{m['name']}{tag}</h3>
  {btns(*buttons)}
  <p>{m['horario']}. ¿Gratis? {m['gratis']}.</p>
  {via(*m['pedir_src'][:1])}
</div>"""

    body = f"""<h1>¿Sin agua? Pide una pipa</h1>
<p class="lede">Toca para llamar o escribir. Todos son canales oficiales y cada uno tiene su fuente. Agua GDL no es del gobierno y no puede mandar pipas.</p>
<div class="signup">
  {h2('siapa', 'phone', 'SIAPA, las 24 horas')}
  {btns(b('tel:+523336682482', 'phone', 'Llamar 33 3668 2482'), b('tel:073', 'phone', 'Llamar 073', True), b('https://gobjal.mx/PipasGratis', 'external-link', 'Formulario', True))}
  <p>Ten tu domicilio y tu número de cuenta. Pide tu número de reporte y anótalo. {FORM_NOTE}</p>
  {via(S_SIAPA)}
</div>
<section aria-labelledby="municipios">
  {h2('municipios', 'map-pin', 'O a tu municipio')}
  <div class="options">
    {mb('guadalajara', [b('tel:+523336682482', 'phone', 'Llamar al SIAPATEL')])}
    {mb('zapopan', [b('tel:+523324101000', 'phone', 'Llamar 33 2410 1000')])}
    {mb('tlaquepaque', [b('https://wa.me/523328048171', 'message-circle', 'WhatsApp TlaqueChat')])}
    {mb('tonala', [b('https://wa.me/523328211120', 'message-circle', 'WhatsApp Tonalá')])}
    {mb('tlajomulco', [b('tel:+523332834400', 'phone', 'Llamar 33 3283 4400')])}
  </div>
</section>
<section aria-labelledby="mas">
  {h2('mas', 'info', 'Más ayuda')}
  <details><summary>{icon('map-pin')}Dónde ir por agua mientras llega</summary>
    <ul>
      <li><b>Guadalajara:</b> {MUNIS['guadalajara']['ir']} ({a(*S_GDL_CIS)})</li>
      <li><b>Tlaquepaque:</b> {MUNIS['tlaquepaque']['ir']} ({a(*S_TLQ_MAP)})</li>
      <li><b>Tonalá:</b> {MUNIS['tonala']['ir']} ({a(*S_TON_MIL)})</li>
      <li><b>Zapopan</b> anunció cisternas, pero no ha publicado dónde están.</li>
    </ul>
    {mapa()}
    {APORTA}
  </details>
  <details><summary>{icon('megaphone')}La pipa no llegó</summary>{NO_LLEGA_ITEMS}</details>
  <details><summary>{icon('shield-check')}Es tu derecho</summary>{DERECHO_P}</details>
  <details><summary>{icon('info')}Si pagas una pipa privada</summary>{PRIVADAS_P}</details>
  <details><summary>{icon('droplet')}Guarda bien el agua</summary>{GUARDA_P}</details>
</section>
{REPORTA}
{OJO}"""
    return page("v4", "Botones grandes", body)


def v5():
    munis = "".join(muni_card(k) for k in MUNIS)
    body = f"""<h1>¿Sin agua? Pide una pipa</h1>
{LEDE}
{siapa_block()}
<section aria-labelledby="municipios">
  {h2('municipios', 'map-pin', 'En tu municipio')}
  <div class="options">{munis}</div>
</section>
{CISTERNAS}
{NO_LLEGA}
{DERECHO}
{CIFRAS}
{PRIVADAS}
<section aria-labelledby="guarda">
  {h2('guarda', 'droplet', 'Guarda bien el agua')}
  {GUARDA_P}
</section>
<section aria-labelledby="preguntas">
  {h2('preguntas', 'info', 'Preguntas')}
  <dl class="faq">
    <dt>¿El SIAPA Bot sirve para pedir pipa?</dt>
    <dd>No. Según La Crónica, en su primera etapa es «exclusivamente» para reportes de calidad del agua y falta de suministro ({a(*S_BOT)}). Pide la pipa al 073 o al 33 3668 2482.</dd>
    <dt>¿Me la llevan aunque tenga tinaco en la azotea?</dt>
    <dd>El SIAPA dice que surte recipientes «que estén a nivel de calle». Ten a nivel de calle un tambo, aljibe o cisterna.</dd>
    <dt>¿Quién tiene prioridad?</dt>
    <dd>Zapopan da prioridad a familias sin tinaco o aljibe y a escuelas y centros de salud ({a(*S_ZAP_PRIO)}). Según N+, las pipas del SIAPA «han priorizado la atención a hospitales y escuelas» ({a(*S_NMAS)}).</dd>
    <dt>¿Cuánto tarda?</dt>
    <dd>Ninguna fuente oficial da un tiempo de entrega. Si no llega, sigue los pasos de «Si la pipa no llega».</dd>
  </dl>
</section>
{REPORTA}
{OJO}"""
    return page("v5", "Guía completa", body)


def index():
    items = "".join(
        f'<li><a href="/pipas-{k}"><b>{k.upper()} · {t}</b></a>: {d}</li>' for k, t, d in VARIANTS
    )
    body = f"""<h1>Variantes de /pipas</h1>
<p class="lede">Cinco formas de organizar lo mismo. Los datos nuevos se revisaron el 3 de noviembre de 2026; lo marcado «por confirmar» no está listo para publicarse. <a href="/pipas">Página actual</a>.</p>
<ul>{items}</ul>"""
    return page("index", "Índice", body)


def main():
    (WEB / "pipas-variantes.html").write_text(index())
    for k, fn in (("v1", v1), ("v2", v2), ("v3", v3), ("v4", v4), ("v5", v5)):
        (WEB / f"pipas-{k}.html").write_text(fn())
    print("wrote 6 pages to", WEB)


if __name__ == "__main__":
    main()
