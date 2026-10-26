# Operación de producción

Este documento es un procedimiento, no una afirmación de que todos los controles ya estén desplegados. Antes de habilitar avisos o aceptar reportes, comprueba cada requisito en el entorno real.

## Invariantes

1. **Una sola instancia activa de API y recordatorios.** El WAL es local y los reportes recientes y límites viven en memoria. Dos máquinas dividirían el mapa y escribirían archivos distintos. Detén la instancia anterior antes de activar otra; no uses despliegue azul-verde ni dos workers de recordatorios.
2. **`/data` es un volumen persistente**, montado en la instancia activa, con `REPORT_WAL=/data/web-reports.wal`. Un sistema de archivos efímero no protege los reportes reconocidos.
3. `DATABASE_URL` usa la conexión directa de Neon, no el pooler, porque las migraciones requieren el candado de Postgres.
4. `/healthz` es solo liveness del proceso y **permanece independiente de Neon y Telegram**. No lo conviertas en una dependencia que provoque reinicios durante una caída externa. Usa comprobaciones externas separadas para datos, webhooks y servicio.
5. Nunca habilites `REMINDERS_ENABLED` o `TG_REMINDERS_ENABLED` en pruebas. Telegram requiere además `TG_TOKEN` y `TG_WEBHOOK_SECRET`.

## Alta o despliegue

- Revisa y respalda la base antes de migrar; ensaya la restauración. Lee cada migración nueva y sus efectos sobre datos existentes.
- Configura secretos mediante el gestor del proveedor, nunca en el repositorio. Aplica mínimo privilegio a GitHub, Fly, Neon, Cloudflare, Telegram, correo y monitoreo.
- Verifica una máquina activa, el volumen correcto, permisos de escritura en `/data`, espacio libre y ausencia de otro remitente.
- Despliega con `--ha=false` cuando uses Fly y confirma después el inventario real de máquinas; la bandera por sí sola no sustituye esa revisión.
- Confirma `/healthz`, `GET /v1/zones`, `/zones.json`, una búsqueda POST sin coordenadas en logs, el mapa y un reporte de prueba controlado sin datos personales.
- Tras cambiar perfil o comandos del bot, ejecuta `cmd/tgsetup` una vez con los secretos en el entorno. No uses pruebas automatizadas contra el bot real.

## WAL y restauración

Cada reporte recibe un recibo aleatorio y se reconoce después de escribir y sincronizar una línea JSON en el WAL. Postgres guarda el lote de forma atómica e idempotente por `request_id`; una compactación exitosa conserva solo lo pendiente. El WAL contiene contenido de reportes y recibos, no direcciones IP.

- Respalda base y WAL; conserva también un `.tmp` si existe durante una investigación.
- No edites, truncues ni borres el WAL con el servicio activo. No lo compartas: aunque sea anónimo, contiene testimonios.
- Para restaurar, detén cualquier otra instancia, restaura primero Postgres y coloca después el WAL en `/data`. Arranca una sola instancia: la carga reproduce pendientes y el guardado vuelve a aplicarlos sin duplicar recibos.
- Verifica totales, ventana reciente, archivo pendiente y logs `web reports pending`. Una línea incompleta o inválida impide arrancar: preserva el archivo y sigue el procedimiento de incidente; no descartes testimonios reconocidos para “arreglar” rápidamente.
- Prueba periódicamente una restauración en aislamiento, con recordatorios apagados y datos sintéticos cuando sea posible.

## Monitoreo externo y revisión diaria

Configura fuera de la máquina alertas para `/healthz`, disponibilidad del sitio y API, vencimiento de certificados, heartbeat nocturno y ejecución del vigilante de fuentes. El heartbeat con `HEARTBEAT_URL` debe recibir éxito solo cuando el lote no tenga fallos; cualquier envío incierto o rechazado requiere revisión. GitHub puede retrasar o desactivar schedules: revisa el issue «SIAPA cambió sus fuentes» y la última ejecución real.

Revisa intentos pendientes y su antigüedad, no solo su número:

```sql
select channel, status, count(*),
       min(sent_at) as oldest, max(sent_at) as newest
from reminder
where status in ('sending', 'uncertain', 'rejected', 'failed')
group by channel, status
order by channel, status;
```

`rejected` puede reintentarse hasta la hora de recuperación. `sending` y `uncertain` pueden representar mensajes aceptados: no los borres ni reenvíes automáticamente. Confirma el estado en el proveedor y conserva `uncertain` si no puedes saberlo. Los topes diarios cuentan personas distintas; los mensuales, mensajes.

## Fuentes y publicación semanal

Cuando SIAPA cambie, contrasta el issue con sus archivos, actualiza datos y `checked`/`checked_by`, regenera mapa, calendarios, `/zones.json` y `/simple`, ejecuta pruebas y solo entonces actualiza `pipelines/siapa_sources.json`. Los cambios manuales de colonias detectados en `ajustes.php` requieren revisión; no se aplican automáticamente.

`cmd/informe` solo lee la base y escribe páginas locales. Genera el conteo semanal contra producción, revisa denominadores, supresión y lenguaje antes de commit/push. No publiques un conteo como representativo, causal o prueba de calidad del agua.
