Sitio estático de aguagdl.com, sin paso de build. `index.html` es la página de inicio.

Publicado en https://aguagdl.com con Cloudflare Pages (sin comando de build, carpeta de salida `web`); cada push a `main` lo vuelve a publicar. Las visitas se cuentan con Cloudflare Web Analytics (sin cookies; se activa en la pestaña Metrics del proyecto de Pages y Cloudflare inserta el script; `_headers` lo permite en la CSP y el aviso de privacidad lo describe en el punto 7). `www.aguagdl.com` redirige a `aguagdl.com` con una regla de Cloudflare.

`avisos.html` es la página para suscribirse por WhatsApp o Telegram; `privacidad.html` y `terminos.html` son el aviso de privacidad y los términos de uso, publicados el 14 de octubre de 2026 (la app de Meta enlaza a ellos, así que no cambies sus URL).

`mapa.html` («Mapa de la rotación», /mapa) muestra todas las colonias del área metropolitana coloreadas por zona, con búsqueda por nombre, municipio o código postal; sus datos (`colonias_siapa.topo.json`) salen de `pipelines/siapa_mapa.py`, que los toma del mapa del SIAPA, y el código del mapa (`mapa.js`) lo comparte con `mizona.html`. Cuando una colonia apenas toca el límite de otra zona, las páginas dicen «al límite con la zona N» en vez de ponerla en las dos.

`reportes.html` («¿Hay agua en tu colonia?», /reportes) es el mapa de reportes de vecinos: cada colonia del mapa del SIAPA coloreada por lo que reportaron en las últimas 24 horas, anillos con el número de reportes, una ficha por colonia con el formulario para reportar (sin cuenta y anónimo) y, después de reportar, botones para compartir el enlace de la colonia, el resumen del día y las respuestas del bot por zona. Lee y escribe en `https://api.aguagdl.com/v1/reportes` (`?api=http://localhost:PUERTO` para una API local).

`mizona.html` («¿Qué zona me toca?») busca la zona por ubicación o colonia (`resultados.html`, que mostraba `/v1/results`, se quitó el 16 oct 2026 hasta que haya suficientes reportes; está en el historial de git). Usa `https://api.aguagdl.com`; para probarlas con la API local, agrega `?api=http://localhost:8080` (solo acepta localhost).

`noticias.html` («Noticias») es la crisis al día, curada a mano: cifras del encabezado, la marcha próxima, videos que se abren en un reproductor modal y se cargan de YouTube/TikTok/X solo al tocarlos (las miniaturas están en `img/videos/`, bajadas una vez de cada plataforma, para no contactar a nadie al abrir la página), el «Día por día» filtrable (cada `<article>` lleva `data-tags`: `represion`, `justicia`, `agua`, `acueducto`, `protesta`) y «Lo que dicen». Cada nota enlaza a su fuente; actualiza la fecha de «Última actualización» al editarla.

`promesas.html` («Lo que prometieron del acueducto»; «Cuentas» en el menú) pone cada promesa del gobierno sobre el agua junto a la ley o el documento oficial. Sus tarjetas y su gráfica se generan desde `promesas.json` con `python3 pipelines/promesas.py`; no las edites a mano.
