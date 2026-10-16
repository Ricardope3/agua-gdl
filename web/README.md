Sitio estático de aguagdl.com, sin paso de build. `index.html` es la página de inicio.

Publicado en https://aguagdl.com con Cloudflare Pages (sin comando de build, carpeta de salida `web`); cada push a `main` lo vuelve a publicar. `www.aguagdl.com` redirige a `aguagdl.com` con una regla de Cloudflare.

`avisos.html` es la página para suscribirse por WhatsApp o Telegram; `privacidad.html` y `terminos.html` son el aviso de privacidad y los términos de uso, publicados el 14 de octubre de 2026 (la app de Meta enlaza a ellos, así que no cambies sus URL).

`mizona.html` («¿Qué zona me toca?») busca la zona por ubicación o colonia (`resultados.html`, que mostraba `/v1/results`, se quitó el 16 oct 2026 hasta que haya suficientes reportes; está en el historial de git). Usa `https://api.aguagdl.com`; para probarlas con la API local, agrega `?api=http://localhost:8080` (solo acepta localhost).
