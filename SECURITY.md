# Seguridad

## Reporte privado

Escribe a `soporte@aguagdl.com` con el asunto `Seguridad en Agua GDL`. Incluye el componente afectado, impacto plausible, pasos de reproducción y una forma de contacto. Usa datos sintéticos: no envíes tokens, contraseñas, números telefónicos, identificadores de suscriptores ni reportes reales.

No abras un issue público para una vulnerabilidad explotable. No prometemos un tiempo de respuesta; si el riesgo es inminente para otras personas, evita probarlo contra producción.

## Alcance prioritario

- Exposición o reidentificación de suscriptores, reportes, direcciones IP o ubicación.
- Evadir límites, umbrales de privacidad, firmas de webhooks o botones.
- Avisos duplicados, envíos después de BAJA o reintentos de entregas inciertas.
- Pérdida o duplicación de reportes durante WAL, migraciones o restauración.
- Modificación no autorizada del sitio, fuentes, pipelines o despliegue.

La denegación de servicio mediante volumen, las incidencias de proveedores sin falla del proyecto y los hallazgos puramente teóricos sin impacto pueden recibir menor prioridad.

## Manejo

El mantenedor preservará solo la evidencia necesaria, limitará su acceso y coordinará una corrección antes de divulgar detalles explotables. Si hubo exposición, seguirá [docs/INCIDENT_RESPONSE.md](docs/INCIDENT_RESPONSE.md) y documentará alcance y correcciones sin volver a publicar los datos.

No hay programa de recompensas. La investigación debe ser de buena fe, mínima y sin enviar mensajes reales, modificar datos, mantener persistencia ni acceder a cuentas ajenas.
