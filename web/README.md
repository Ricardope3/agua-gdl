Sitio estático de aguagdl.com, sin paso de build. `index.html` es la página de inicio.

Publicado en https://aguagdl.com con Cloudflare Pages (sin comando de build, carpeta de salida `web`); cada push a `main` lo vuelve a publicar. `www.aguagdl.com` redirige a `aguagdl.com` con una regla de Cloudflare.

`avisos.html` es la página para suscribirse; `privacidad.html` y `terminos.html` son el aviso de privacidad y los términos de uso (borradores: falta llenar los recuadros naranjas y una revisión legal).

`llego.html` («¿Qué zona me toca?») busca la zona por ubicación o colonia y `resultados.html` muestra los reportes de `/v1/results`. Las dos usan `https://api.aguagdl.com`; para probarlas con la API local, agrega `?api=http://localhost:8080` (solo acepta localhost).
