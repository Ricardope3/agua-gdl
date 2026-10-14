# Agua GDL

Avisos gratuitos por WhatsApp la noche antes de cada corte de la rotación de agua del SIAPA (Guadalajara, oct 2026 – mar 2027). Servicio ciudadano, no oficial y sin partido.

- `api/` servicio en Go: webhook de WhatsApp, avisos de las 20:00, búsqueda de zona y colonia, resultados.
- `api/data/` zonas (KML público del SIAPA), 621 colonias (PDF del SIAPA del 12 oct 2026) y calendario semanal.
- `pipelines/` scripts que regeneran `api/data` desde las fuentes del SIAPA.

## Desarrollo

```sh
docker run -d --name aguagdl-pg -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=aguagdl -p 55432:5432 postgres:17-alpine
cp .env.example .env   # llena los valores
cd api && go test ./... && set -a && . ../.env && go run ./cmd/server
```

Endpoints: `GET /v1/zones`, `GET /v1/zone?lat=&lon=`, `GET /v1/colonias?q=`, `GET /v1/results`, `GET|POST /wa/webhook`.

Las pruebas de integración crean y borran esquemas aislados en una base de pruebas:
`cd api && TEST_DATABASE_URL=postgres://postgres:dev@localhost:55432/aguagdl?sslmode=disable go test -race ./...`.
CI las ejecuta con PostgreSQL 17. Sin `TEST_DATABASE_URL`, esas pruebas se omiten.

## Despliegue

`fly launch --copy-config --no-deploy`, luego `fly secrets set DATABASE_URL='…' PUBLIC_BASE_URL=https://aguagdl.com WA_TOKEN='…' WA_PHONE_NUMBER_ID=… WA_APP_SECRET='…' WA_VERIFY_TOKEN='…' HEARTBEAT_URL='…'` (con comillas simples: el `?` y el `&` de la URL de Neon rompen el comando en zsh) y `fly deploy --ha=false`. Sin `--ha=false`, el primer despliegue crea dos máquinas: no duplican avisos, pero la que termina primero cuenta como `sending` el envío en curso de la otra y manda una falsa alarma al heartbeat. Despliega desde `main` limpio: `fly deploy` sube la carpeta local. Los avisos solo salen con `REMINDERS_ENABLED=true`.

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

Si Meta rechaza el envío con un error 4xx (plantilla pausada, token inválido, sin
método de pago…), el aviso queda como `rejected`: no salió, no cuenta contra los
topes y se reintenta si el servidor vuelve a correr esa noche. Tras 5 errores
seguidos el lote se detiene: corrige la causa y reinicia con `fly machine restart`
antes de las 22:00. Si Meta reporta después que un aviso no se entregó (`failed`),
el servidor manda el heartbeat a `/fail` en ese momento.

Los topes se revisan antes de cada envío. El diario (`DAILY_CAP`) cuenta personas
distintas en una ventana móvil de 24 horas, como el límite de Meta. Si los avisos de
anoche todavía la llenan, el lote espera a que salgan de la ventana en vez de saltarse
a nadie; solo se rinde a las 22:00 o al llegar al tope mensual (`MONTHLY_CAP`, que
cuenta mensajes).

Para revisar los intentos pendientes:

```sql
select id, cut_date, zone, status from reminder
where status in ('sending', 'uncertain', 'rejected', 'failed')
order by cut_date desc, id;
```

No borres estas reservas para reintentar automáticamente: podrías duplicar un
mensaje que WhatsApp ya aceptó. Confirma el resultado en WhatsApp Manager; marca
como `sent` los aceptados, o `failed` los rechazados. Si no puedes
confirmarlo, conserva `uncertain` y publica el aviso manualmente en el Canal.

## Datos

Si el SIAPA cambia los días, edita `api/data/rotation.json` (`skip`/`extra` para fechas sueltas) y despliega. Luego avisa a los suscriptores de cada zona que cambió con la plantilla `cambio_rotacion` (los días salen de `rotation.json`):

```sh
cd api
DATABASE_URL='…' go run ./cmd/notify -zone 4 -from 2026-11-02          # solo muestra a cuántos y qué dice
DATABASE_URL='…' WA_TOKEN='…' WA_PHONE_NUMBER_ID=… go run ./cmd/notify -zone 4 -from 2026-11-02 -send
```

Cuenta para el tope diario igual que los avisos; si el tope lo detiene, vuelve a correr el mismo comando más tarde: no repite a quien ya lo recibió.

Para regenerar colonias:

```sh
python3 -m venv pipelines/.venv && pipelines/.venv/bin/pip install pdfplumber==0.11.4
pipelines/.venv/bin/python pipelines/siapa_colonias.py colonias_siapa.pdf api/data/colonias.json
```

Código bajo MIT. Datos del SIAPA / Gobierno de Jalisco.
