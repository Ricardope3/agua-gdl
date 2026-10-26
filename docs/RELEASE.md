# Lista de despliegue y publicación

Usa esta lista con el commit candidato y el entorno real a la vista. No marques un requisito por suposición: registra quién lo verificó, cuándo y cualquier incidencia. Los valores secretos se quedan en el gestor del proveedor.

## 1. Candidato y pruebas

- [ ] El candidato está basado en el `origin/main` más reciente; no contiene investigación, temporales, cachés, respaldos ni trabajo local ajeno.
- [ ] `git diff --check` no reporta errores.
- [ ] Pasan `go vet ./...` y `go test -count=1 ./...` desde `api/`.
- [ ] Pasa `TEST_DATABASE_URL='postgres://postgres:dev@localhost:55432/aguagdl?sslmode=disable' go test -race -count=1 ./...` con PostgreSQL 17, como en CI. Si se usa otra versión local, se indica y CI confirma la 17.
- [ ] Pasan las pruebas de Python y Node y los `--check` de `mapa_colonias.py`, `promesas.py`, `publicaciones.py`, `zonas_json.py` y `simple_page.py`.
- [ ] CI termina correctamente, incluido `govulncheck` y la construcción de `infra/Dockerfile`.

## 2. Respaldo y estado previo

- [ ] Anota versión anterior, máquina, volumen, hora y responsable.
- [ ] Crea y verifica un respaldo de Neon; conserva también `/data/web-reports.wal` y cualquier `.tmp` con acceso restringido. Detén escrituras antes de copiar el WAL para obtener un estado quieto.
- [ ] Confirma que sabes restaurar ambos en aislamiento; no borres ni trunques el WAL.
- [ ] Revisa las migraciones `011_web_report_receipt.sql` y `012_subscriber_zones.sql`: recibos anónimos, índice parcial, renombre del índice antiguo, tabla de membresías y backfill.
- [ ] Guarda conteos previos de suscriptores, membresías, reportes y envíos pendientes para compararlos después.

```sql
select (select count(*) from subscriber) as subscribers,
       (select count(*) from web_report) as web_reports;
select channel, status, count(*) from reminder
where status in ('sending','uncertain','rejected','failed')
group by channel, status;
```

## 3. Configuración obligatoria

- [ ] Hay exactamente **una máquina activa** para API y recordatorios; no habrá despliegue azul-verde ni otro worker concurrente.
- [ ] Un volumen persistente está montado en `/data`, tiene espacio y permisos, y `REPORT_WAL=/data/web-reports.wal`.
- [ ] `DATABASE_URL` es la conexión directa de Neon, no el pooler.
- [ ] `PUBLIC_BASE_URL`, `HEARTBEAT_URL`, `TG_TOKEN` y `TG_WEBHOOK_SECRET` están configurados; WhatsApp permanece apagado sin sus credenciales completas.
- [ ] Los recordatorios empiezan deshabilitados para el smoke test: `TG_REMINDERS_ENABLED=false` y `REMINDERS_ENABLED=false`.
- [ ] `MIN_REPORTS_SHOWN`, topes y horarios coinciden con la configuración aprobada.

## 4. Despliegue

- [ ] Despliega el commit candidato con `fly deploy --ha=false`; confirma después con el inventario de máquinas que solo quedó una activa y que la anterior se detuvo.
- [ ] Revisa que todas las migraciones terminaron y que el arranque no reporta WAL, Neon ni permisos fallidos.
- [ ] Cloudflare Pages completa el build con todos los `--check`; no uses un deploy parcial si falló.

Después de migrar, esta consulta debe devolver `0`:

```sql
select count(*) from subscriber s
where not exists (select 1 from subscriber_zone z where z.subscriber_id = s.id);
```

## 5. Smoke test sin mensajes reales

- [ ] `GET /healthz` responde; recuerda que es solo liveness y no prueba Neon o Telegram.
- [ ] `GET /v1/zones` y `/zones.json` tienen calendario, fuente y fecha de verificación coherentes.
- [ ] POST `/v1/zone` y `/v1/colonias` responden `Cache-Control: no-store`; coordenadas o búsquedas no aparecen en logs.
- [ ] `/reportes`, `/mizona`, `/mapa`, `/simple`, `/correcciones`, `/transparencia` y `/informes` cargan en móvil y escritorio, con teclado y tema claro/oscuro.
- [ ] Un reporte controlado sin datos personales queda en WAL y después en Postgres una sola vez; reinicia en aislamiento si necesitas comprobar replay. No uses el bot real para pruebas automatizadas.
- [ ] Compara suscriptores y membresías con los conteos previos; investiga cualquier pérdida antes de continuar.

## 6. Telegram y avisos

- [ ] Ejecuta una vez `cd api && TG_TOKEN='…' TG_WEBHOOK_SECRET='…' go run ./cmd/tgsetup` para actualizar perfil, descripciones, webhook y menú. Esto configura el bot; no es una prueba masiva.
- [ ] Revisa candidatos y mensajes con el dry run de `cmd/notify`; no agregues `-send` durante la revisión.
- [ ] Comprueba heartbeat externo y que no hay intentos `sending` o `uncertain` sin explicación.
- [ ] Habilita solo Telegram con `TG_REMINDERS_ENABLED=true`; deja WhatsApp apagado. Observa la primera corrida y sus logs.

## 7. Monitoreo y publicación

- [ ] Hay alertas externas para sitio, API, certificado, heartbeat y ejecución del vigilante SIAPA.
- [ ] Revisa edad y número de pendientes, `web reports pending`, espacio del volumen y el issue «SIAPA cambió sus fuentes».
- [ ] Verifica que `/simple` y los calendarios siguen al día tras cualquier cambio de fuente.
- [ ] No publiques una semana en `/informes` hasta generarla contra producción y revisar denominadores, supresión y lenguaje. Su ausencia debe seguir indicada honestamente.
- [ ] Documenta commit, hora, resultado, incidencias y responsable en el registro de operación.

## Reversión

Deshabilita recordatorios primero y detén la instancia nueva. Conserva base y WAL antes de cambiar algo. Vuelve a la imagen anterior solo si las migraciones siguen siendo compatibles; la versión anterior ignorará las membresías adicionales. No restaures un respaldo de base sobre reportes nuevos sin un plan para conservarlos, y nunca reenvíes intentos inciertos. Si la reversión no es segura, mantén avisos apagados y sigue `INCIDENT_RESPONSE.md`.
