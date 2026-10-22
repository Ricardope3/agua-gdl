# Agua GDL

Avisos gratuitos por Telegram antes de los cortes de la rotación de agua del SIAPA (Guadalajara, oct 2026 – mar 2027): dos días antes y la noche antes, una vez por tanda cuando los cortes van seguidos. También el mapa de reportes de los vecinos (aguagdl.com/reportes), el mapa de la rotación y un calendario por zona. Servicio ciudadano, no oficial y sin partido. WhatsApp funcionó hasta el 15 de octubre de 2026, cuando Meta cerró la cuenta; su código sigue, apagado mientras no haya `WA_TOKEN`.

- `api/` servicio en Go: webhook de Telegram (y el de WhatsApp, solo con `WA_TOKEN`), avisos de las 20:00, búsqueda de zona y colonia, reportes del mapa.
- `api/data/` el mapa del SIAPA (sus colonias con las zonas que les da y sus 7 zonas; copia de `web/colonias_siapa.topo.json`), 621 colonias (PDF del SIAPA del 12 oct 2026), las demás colonias del INE y el calendario semanal.
- `pipelines/` scripts que regeneran `api/data` desde las fuentes del SIAPA y avisan si cambian.

## Desarrollo

```sh
docker run -d --name aguagdl-pg -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=aguagdl -p 55432:5432 postgres:17-alpine
cp .env.example .env   # llena los valores
cd api && go test ./... && set -a && . ../.env && go run ./cmd/server
```

Endpoints: `GET /healthz`, `GET /v1/zones`, `GET /v1/zone?lat=&lon=`, `GET /v1/colonias?q=`, `GET|POST /v1/reportes`, `POST /tg/webhook` (con `TG_TOKEN` y `TG_WEBHOOK_SECRET`) y `GET|POST /wa/webhook` (solo con `WA_TOKEN`).

Las pruebas de integración crean y borran esquemas aislados en una base de pruebas:
`cd api && TEST_DATABASE_URL=postgres://postgres:dev@localhost:55432/aguagdl?sslmode=disable go test -race ./...`.
CI las ejecuta con PostgreSQL 17. Sin `TEST_DATABASE_URL`, esas pruebas se omiten.

## Despliegue

`fly launch --copy-config --no-deploy`, luego `fly secrets set DATABASE_URL='…' PUBLIC_BASE_URL=https://aguagdl.com HEARTBEAT_URL='…'` (con comillas simples: el `?` y el `&` de la URL de Neon rompen el comando en zsh), los secretos de Telegram (abajo) y `fly deploy --ha=false`. Sin `--ha=false`, el primer despliegue crea dos máquinas: no duplican avisos, pero la que termina primero cuenta como `sending` el envío en curso de la otra y manda una falsa alarma al heartbeat, y cada una guardaría en memoria sus propios reportes del mapa y sus límites, así que el mapa quedaría partido. Despliega desde `main` limpio: `fly deploy` sube la carpeta local. Los avisos solo salen con `TG_REMINDERS_ENABLED=true` (Telegram) o `REMINDERS_ENABLED=true` (WhatsApp, que además necesita `WA_TOKEN`, `WA_PHONE_NUMBER_ID`, `WA_APP_SECRET` y `WA_VERIFY_TOKEN`); cada canal se envía aparte y la falla de uno no detiene al otro.

Telegram: crea el bot con @BotFather, guarda `TG_TOKEN` y `TG_WEBHOOK_SECRET` (`openssl rand -hex 32`) con `fly secrets import`, despliega y corre una vez `cd api && TG_TOKEN='…' TG_WEBHOOK_SECRET='…' go run ./cmd/tgsetup`: registra el webhook, el nombre, las descripciones y el menú de comandos. Telegram no tiene plantillas, ventana de 24 horas ni tope diario; guardamos el ID de usuario de Telegram, no el número. Después de cambiar sus descripciones o comandos, vuelve a correr `tgsetup`. Si alguien bloquea el bot, se borra su suscripción. El enlace `https://t.me/<bot>?start=z4` suscribe directo a la zona 4.

Antes de desplegar la migración `005_phone_unique.sql` sobre una base que ya tenga suscriptores, revisa si algún número está en más de una suscripción; la migración conserva solo la más reciente de cada número:

```sql
select phone, count(*) from subscriber where phone is not null group by phone having count(*) > 1;
```

Cada comando y el hash de su identificador de WhatsApp se guardan en una sola
transacción. Los identificadores (`wamid`) contienen el número de teléfono, así que
la base solo guarda su hash SHA-256 y nunca se escriben en los logs.
Si falla la respuesta de confirmación, el comando queda aplicado y un reintento del
webhook no lo repite. La confirmación puede perderse; la persona puede escribir de
nuevo para consultar su estado.

Antes de enviar un aviso se guarda una reserva duradera y se vuelve a comprobar la
suscripción bajo bloqueo. BAJA y los cambios de zona se serializan con el envío:
después de confirmarse BAJA no empieza otro envío para esa suscripción. Un mensaje
ya aceptado por WhatsApp puede llegar después.

Un reinicio no reenvía intentos reservados. Si se pierde la respuesta de WhatsApp o
el proceso se detiene entre la reserva y el registro final, el aviso queda como
`sending` o `uncertain`: podría haberse enviado o no. Se cuenta contra los topes y
el heartbeat avisa de la incertidumbre al revisar el lote de esa noche. Cualquier
error de envío hace fallar el heartbeat, aunque otros avisos salgan bien.

Si WhatsApp o Telegram rechazan el envío con un error 4xx (plantilla pausada, token
inválido, sin método de pago…), el aviso queda como `rejected`: no salió, no cuenta
contra los topes y la corrida lo vuelve a intentar sola, esperando cada vez más (1, 2,
4… hasta 10 minutos), hasta `CATCH_UP_UNTIL_HOUR` (22:00). Tras 5 errores seguidos el
lote se detiene: si fueron rechazos, la corrida vuelve a intentar más tarde; si fueron
envíos inciertos, corrige la causa y reinicia con `fly machine restart` antes de las
22:00 para que la corrida de recuperación siga con quien falta. Si Meta reporta después
que un aviso no se entregó (`failed`), el servidor manda el heartbeat a `/fail` en ese
momento.

Los topes se revisan antes de cada envío. El diario (`DAILY_CAP`) cuenta personas
distintas en una ventana móvil de 24 horas, como el límite de Meta. Si los avisos de
anoche todavía la llenan, el lote espera a que salgan de la ventana en vez de saltarse
a nadie; solo se rinde a las 22:00 o al llegar al tope mensual (`MONTHLY_CAP`, que
cuenta mensajes). Cada reserva vuelve a revisar ambos topes con un candado de Postgres,
así que el lote nocturno y `notify` no pueden pasarlos aunque corran al mismo tiempo;
los avisos de `notify` también se detienen en el tope mensual.

Para revisar los intentos pendientes:

```sql
select id, cut_date, zone, status from reminder
where status in ('sending', 'uncertain', 'rejected', 'failed')
order by cut_date desc, id;
```

No borres estas reservas para reintentar automáticamente: podrías duplicar un
mensaje que WhatsApp ya aceptó. Confirma el resultado en WhatsApp Manager; marca
como `sent` los aceptados, o `failed` los rechazados. Si no puedes
confirmarlo, conserva `uncertain`.

## Sitio (`web/`)

Sitio estático de aguagdl.com, sin framework. Cloudflare Pages lo publica en cada push a `main` (carpeta de salida `web`). Su comando de build corre las revisiones de CI, para que un archivo de datos roto detenga la publicación en vez de llegar al sitio:

```sh
python3 pipelines/publicaciones.py --check && python3 pipelines/promesas.py --check && python3 pipelines/mapa_colonias.py --check
```

Todo lo que está en `web/` es público: las notas, los datos que no se usan y los borradores van fuera. Las visitas se cuentan con Cloudflare Web Analytics (sin cookies; se activa en la pestaña Metrics del proyecto de Pages, Cloudflare inserta el script y el aviso de privacidad lo describe en el punto 7). La portada carga el mapa de /reportes como `/reportes-portada`, así que en las estadísticas esas cargas no cuentan como visitas a /reportes. `www.aguagdl.com` redirige a `aguagdl.com` con una regla de Cloudflare. Las páginas que llaman a la API usan `https://api.aguagdl.com`; para probarlas con la API local, agrega `?api=http://localhost:8080` (solo acepta localhost o 127.0.0.1).

- `index.html`, la portada: bajo «El agua es un derecho. Exígelo.», el titular «El SIAPA prometió un día. Hay vecinos con semanas sin agua.»; el mapa de /reportes en un marco de orilla a orilla, abierto en Ciudad Granja; lo que prometió el SIAPA frente a las cifras de la CEA; el reporte de tu colonia; las noticias y publicaciones de vecinos, cada una con su enlace (de las personas, solo la colonia y la fecha), y pedirle al Congreso que vote no al acueducto privado. Nada de la rotación: eso está en /mizona, /mapa y /avisos.
- `reportes.html` (/reportes): el mapa de lo que publican medios y vecinos (`publicaciones.json`, que valida `pipelines/publicaciones.py`; las de medios van primero y las de vecinos solo con al menos 5 reacciones y 1 comentario) y de los reportes de los vecinos. Cada colonia se colorea por los días sin agua que dicen las publicaciones o, donde no hay, por lo que reportaron en las últimas 24 horas. Tiene la lista de las colonias con más días, una ficha por colonia con el formulario para reportar (sin cuenta y anónimo) y botones para compartirla, la semana por zona junto al calendario del SIAPA y las respuestas del bot por zona.
- `exige.html` (/exige) arma un mensaje con tu colonia, tu municipio y lo que pasa, y lo mandas tú desde tu correo, X o Facebook al gobernador, a la CEA, a tu presidencia municipal y, en Guadalajara, Zapopan, Tlaquepaque y Tonalá, al SIAPA. Cada contacto lleva su fuente oficial y la fecha en que se revisó. Agua GDL no ve ni guarda nada.
- `pipas.html` (/pipas) da el SIAPATEL y la línea de cada municipio con su fuente, y el artículo 90, fracción VI, de la Ley del Agua. Publica un número solo si una fuente lo da, y actualiza la fecha de revisión cuando los revises.
- `mizona.html` busca la zona por ubicación o colonia, y `mapa.html` muestra todas las colonias coloreadas por zona (datos de `colonias_siapa.topo.json`, de `pipelines/siapa_mapa.py`; las dos y /reportes comparten `mapa.js`). Cuando una colonia apenas toca el límite de otra zona, dicen «al límite con la zona N».
- `avisos.html`: suscribirse por Telegram o con el calendario de la zona.
- `noticias.html`: la crisis al día, curada a mano. Cada nota enlaza a su fuente; actualiza «Última actualización» al editarla. Los videos se cargan de YouTube, TikTok o X solo al tocarlos.
- `promesas.html` (/promesas): sus tarjetas y su gráfica se generan desde `promesas.json` con `python3 pipelines/promesas.py`; no las edites a mano.
- `escribe.html`, `contamina.html` y `antisionismo.html`: cada afirmación enlaza su fuente.
- `privacidad.html` y `terminos.html`: el aviso de privacidad y los términos de uso. La app de Meta enlaza a ellos, así que no cambies sus URL.
- `theme.js` (en el `<head>` de cada página) pone el botón de tema claro u oscuro; el claro es el predeterminado. También cambia el color de la barra del navegador, así que cada página lleva un solo `<meta name="theme-color" content="#ffffff">`, sin `media`. Al cambiar de tema lanza el evento `tema` en `document`, con el que los mapas se vuelven a pintar.
- `404.html`: la página de las direcciones que no existen.

El conteo semanal (`informes.html`, que escribe `api/cmd/informe`) y `resultados.html` (con `GET /v1/results`) se quitaron hasta que haya suficientes reportes; están en el historial de git.

## Datos

Si el SIAPA cambia los días, edita `api/data/rotation.json` (`skip`/`extra` para fechas sueltas; actualiza `checked` y `checked_by`), regenera los calendarios con `cd api && go run ./cmd/calendars` (la prueba de `internal/calendar` falla si no) y despliega. Luego avisa a los suscriptores de cada zona que cambió (los días salen de `rotation.json`; sin `-channel tg`, `notify` usa WhatsApp):

```sh
cd api
DATABASE_URL='…' go run ./cmd/notify -channel tg -zone 4 -from 2026-11-02          # solo muestra a cuántos y qué dice
DATABASE_URL='…' TG_TOKEN='…' go run ./cmd/notify -channel tg -zone 4 -from 2026-11-02 -send
```

Volver a correr el mismo comando no repite a quien ya lo recibió. En WhatsApp cuenta para el tope diario igual que los avisos: si el tope lo detiene, vuelve a correrlo más tarde. (`-avisos` avisaba una vez del cambio a los avisos por tandas; no se mandó.)

Solo WhatsApp (apagado): si la plantilla `aviso_corte` todavía no está aprobada (o Meta la pausó), puedes mandar el aviso de mañana como mensaje normal. WhatsApp solo entrega mensajes normales a quien escribió en las últimas 24 horas, así que llega solo a quien se suscribió o cambió de zona en las últimas 23. Queda registrado como el aviso de esa noche: la corrida de las 20:00 no se lo repite. En zsh, `read -s` pide cada valor sin mostrarlo ni guardarlo en el historial:

```sh
cd api
read -s 'DATABASE_URL?URL de Neon: '; export DATABASE_URL
go run ./cmd/notify -zone 6 -tomorrow          # solo muestra a cuántos y el texto
read -s 'WA_TOKEN?Token: '; export WA_TOKEN
WA_PHONE_NUMBER_ID=… WA_GRAPH_VERSION=… go run ./cmd/notify -zone 6 -tomorrow -send
```

Para regenerar colonias, usa el PDF del 12 de octubre de 2026 (34 páginas; está en las notas privadas del proyecto, `siapa/colonias_siapa.pdf`): el que publica hoy el SIAPA es la reedición del 13 de octubre, con columnas cortadas, y el script falla con él.

```sh
python3 -m venv pipelines/.venv && pipelines/.venv/bin/pip install pdfplumber==0.11.4
pipelines/.venv/bin/python pipelines/siapa_colonias.py colonias_siapa.pdf api/data/colonias.json
```

Para regenerar el mapa del SIAPA y lo que sale de él (solo biblioteca estándar; descarga su TopoJSON y `ajustes.php`): `siapa_mapa.py` escribe `web/colonias_siapa.topo.json` y su copia en `api/data`, con la que el bot y `/v1/zone` ubican la zona, y `mapa_colonias.py` escribe las colonias de `/reportes` y las zonas de las colonias que no están en la lista:

```sh
python3 pipelines/siapa_mapa.py && python3 pipelines/mapa_colonias.py
```

Cada hora (GitHub suele arrancarlo horas tarde), `.github/workflows/siapa-watch.yml` corre `pipelines/siapa_watch.py`: descarga la página, el PDF, el mapa (TopoJSON) y `ajustes.php` del SIAPA, compara su SHA-256 con `pipelines/siapa_sources.json`, el mapa con `web/colonias_siapa.topo.json` y los días de `ajustes.php` con `rotation.json`. Si algo cambió, abre el issue «SIAPA cambió sus fuentes» (o comenta en el que siga abierto) con el reporte, una vez por cada estado nuevo de las fuentes o de su diferencia con el repo. Revisa el cambio, actualiza `api/data` si hace falta y luego la línea base:

```sh
python3 pipelines/siapa_watch.py --update && git commit -m 'Update the SIAPA baseline' pipelines/siapa_sources.json
```

El CDN del SIAPA guarda cada archivo hasta un día, así que un cambio puede tardar ese tiempo en detectarse.

Código bajo MIT. Datos del SIAPA / Gobierno de Jalisco y del INE (contornos de colonias y secciones electorales).
