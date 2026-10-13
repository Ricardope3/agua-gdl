# Agua GDL

Avisos gratuitos por WhatsApp la noche antes de cada corte de la rotación de agua del SIAPA (Guadalajara, oct 2026 – mar 2027). Servicio ciudadano, no oficial y sin partido.

- `api/` servicio en Go: webhook de WhatsApp, avisos de las 20:00, búsqueda de zona y colonia, resultados.
- `api/data/` zonas (KML público del SIAPA), 596 colonias (PDF del SIAPA) y calendario semanal.
- `pipelines/` scripts que regeneran `api/data` desde las fuentes del SIAPA.

## Desarrollo

```sh
docker run -d --name aguagdl-pg -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=aguagdl -p 55432:5432 postgres:17-alpine
cp .env.example .env   # llena los valores
cd api && go test ./... && set -a && . ../.env && go run ./cmd/server
```

Endpoints: `GET /v1/zones`, `GET /v1/zone?lat=&lon=`, `GET /v1/colonias?q=`, `GET /v1/results`, `GET|POST /wa/webhook`.

## Despliegue

`fly launch --no-deploy`, luego `fly secrets set DATABASE_URL=… PUBLIC_BASE_URL=… WA_TOKEN=… WA_PHONE_NUMBER_ID=… WA_APP_SECRET=… WA_VERIFY_TOKEN=…` y `fly deploy`. Los avisos solo salen con `REMINDERS_ENABLED=true`.

## Datos

Si el SIAPA cambia los días, edita `api/data/rotation.json` (`skip`/`extra` para fechas sueltas). Para regenerar colonias:

```sh
python3 -m venv pipelines/.venv && pipelines/.venv/bin/pip install pdfplumber==0.11.4
pipelines/.venv/bin/python pipelines/siapa_colonias.py colonias_siapa.pdf api/data/colonias.json
```

Código bajo MIT. Datos del SIAPA / Gobierno de Jalisco.
