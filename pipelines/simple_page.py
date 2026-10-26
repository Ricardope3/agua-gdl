#!/usr/bin/env python3
"""Generate the lightweight, no-JavaScript public service page from shared data."""
import argparse
import datetime as dt
import html
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "web" / "simple.html"
MONTHS = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre")


def date_es(value):
    day = dt.date.fromisoformat(value)
    return f"{day.day} de {MONTHS[day.month - 1]} de {day.year}"


def esc(value):
    return html.escape(str(value), quote=True)


def build():
    rotation = json.loads((ROOT / "api" / "data" / "rotation.json").read_text())
    publications = json.loads((ROOT / "web" / "publicaciones.json").read_text())["publicaciones"]
    day_names = {"mon": "lunes", "tue": "martes", "wed": "miércoles", "thu": "jueves", "fri": "viernes", "sat": "sábado", "sun": "domingo"}
    zone_rows = []
    for zone, days in sorted(rotation["zones"].items(), key=lambda item: int(item[0])):
        label = ", ".join(day_names[day] for day in days)
        zone_rows.append(f'''<section class="zone" id="zona-{zone}"><h2>Zona {zone}</h2><p><strong>Días de corte:</strong> {esc(label)}.</p><p><a href="/calendario/zona-{zone}.ics">Agregar al calendario</a> · <a href="https://t.me/AvisoAguaGDLbot?start=z{zone}" rel="noopener">Avisos gratuitos por Telegram</a></p></section>''')
    latest = max((p["fecha"] for p in publications), default=rotation["checked"])
    recent = sorted((p for p in publications if p["fecha"] >= (dt.date.fromisoformat(latest) - dt.timedelta(days=6)).isoformat()), key=lambda p: (p["fecha"], p["url"]), reverse=True)
    colonias = Counter()
    for post in recent:
        for key in post["colonias"]:
            colonias[key.split("|", 1)[0].strip().title()] += 1
    names = ", ".join(name for name, _ in colonias.most_common(12)) or "Sin publicaciones registradas en este periodo"
    posts = []
    for post in recent[:8]:
        who = post.get("quien") or "Vecinas y vecinos"
        posts.append(f'<li><a href="{esc(post["url"])}" rel="noopener nofollow">{esc(post["cita"])}</a><br><small>{esc(who)} · {esc(date_es(post["fecha"]))}</small></li>')
    post_html = "\n".join(posts) or "<li>No hay publicaciones recientes registradas.</li>"
    return f'''<!doctype html>
<html lang="es-MX"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Agua GDL · Información sencilla</title><meta name="description" content="Días de corte, avisos, pipas y testimonios recientes, sin mapas ni JavaScript.">
<link rel="canonical" href="https://aguagdl.com/simple"><meta name="theme-color" content="#ffffff"><link rel="icon" href="/favicon.ico" sizes="any"><script src="/theme.js"></script>
<style>:root{{--bg:#fbfaf6;--fg:#14213d;--muted:#4f5b7a;--brand:#1d3f9e;--line:#c4cfe9}}*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:18px/1.6 system-ui,-apple-system,sans-serif}}main{{max-width:800px;margin:auto;padding:20px}}h1{{font-size:2rem;line-height:1.15}}h2{{font-size:1.3rem;margin:0 0 8px}}section{{border-top:3px double var(--brand);padding:18px 0}}a{{color:var(--brand);text-underline-offset:3px}}a:focus-visible{{outline:3px solid var(--brand);outline-offset:4px}}nav ul{{padding-left:20px}}.notice{{background:#fff;border:2px solid var(--brand);padding:14px}}.zone{{padding:14px 0}}small,.muted{{color:var(--muted)}}li{{margin-bottom:12px}}@media(prefers-color-scheme:dark){{:root{{--bg:#0c1328;--fg:#eef1fb;--muted:#a6b1d6;--brand:#a9bdfa;--line:#2a3a6e}}.notice{{background:#121b36}}}}</style></head>
<body><main><header><p><strong>Agua GDL</strong> · Servicio ciudadano, gratuito, no oficial y sin partido</p><h1>Información sobre el agua, sin mapas</h1><p>Esta página ligera funciona sin JavaScript y no carga imágenes, calles ni reproductores externos.</p></header>
<nav aria-label="Contenido"><ul><li><a href="#cortes">Días de corte por zona</a></li><li><a href="#pipas">Pedir una pipa</a></li><li><a href="#recientes">Testimonios recientes</a></li><li><a href="/reportes">Reportar cómo está el agua</a></li><li><a href="/correcciones">Proponer una fuente o pedir una corrección</a></li></ul></nav>
<section id="cortes"><h2>Calendario de la rotación</h2><p class="notice">Según el calendario semanal del SIAPA, verificado por Agua GDL el <strong>{esc(date_es(rotation["checked"]))}</strong>. Vigencia: {esc(date_es(rotation["start"]))} a {esc(date_es(rotation["end"]))}. El agua puede irse antes o tardar en volver. Confirma en la <a href="https://rotaciondeserviciosiapa.jalisco.gob.mx/" rel="noopener">fuente oficial del SIAPA</a>.</p><p>¿No sabes tu zona? Consulta el <a href="https://rotaciondeserviciosiapa.jalisco.gob.mx/" rel="noopener">mapa oficial</a> o <a href="/correcciones">pide ayuda o corrige un dato</a>.</p>{''.join(zone_rows)}</section>
<section id="pipas"><h2>Si no tienes agua</h2><p>Llama al <strong>SIAPATEL: <a href="tel:3336682482">33 3668 2482</a> o <a href="tel:073">073</a></strong>, las 24 horas. Ten a la mano tu domicilio y número de cuenta. Agua GDL no puede enviar pipas.</p><p><a href="/pipas">Teléfonos municipales, condiciones y fuentes oficiales</a> · <a href="/reportes">Dejar un testimonio anónimo</a></p></section>
<section id="recientes"><h2>Lo publicado recientemente</h2><p>Resumen de publicaciones enlazadas del {esc(date_es((dt.date.fromisoformat(latest)-dt.timedelta(days=6)).isoformat()))} al {esc(date_es(latest))}. Colonias mencionadas: {esc(names)}.</p><p class="muted">Son testimonios y notas públicas, no mediciones oficiales ni una muestra representativa. Participa más quien tiene internet y usa redes; que una colonia no aparezca no significa que tenga agua.</p><ul>{post_html}</ul><p><a href="/reportes">Ver el registro completo con fuentes</a></p></section>
<section><h2>Participa y revisa nuestro trabajo</h2><p><a href="/correcciones#fuentes">Proponer una fuente pública</a> · <a href="/correcciones">Pedir una corrección o retiro</a> · <a href="/transparencia">Transparencia</a> · <a href="/participa">Participar</a></p><p><a href="/privacidad">Privacidad</a> · <a href="/terminos">Términos</a> · <a href="mailto:soporte@aguagdl.com">soporte@aguagdl.com</a></p></section>
<footer><p>Agua GDL no pertenece al SIAPA ni al Gobierno de Jalisco. Nunca usa datos vecinales para publicidad, campañas ni propaganda política.</p></footer></main></body></html>'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = build()
    if args.check:
        if not OUT.exists() or OUT.read_text() != rendered:
            raise SystemExit("web/simple.html is stale: run python3 pipelines/simple_page.py")
        print("simple.html: up to date")
    else:
        OUT.write_text(rendered)
        print(OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
