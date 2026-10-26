# Traspaso y continuidad

El proyecto no debe depender de la disponibilidad o la memoria de una sola persona. Hasta nombrar responsables de respaldo en `MAINTAINERS.md`, esa redundancia no existe y no debe anunciarse.

## Inventario sin secretos

Mantén fuera del repositorio un inventario fechado de titulares y accesos para:

- Repositorio y workflows de GitHub.
- Fly: aplicación, máquinas, volumen `/data`, secretos y despliegue.
- Neon: base directa, respaldos y retención.
- Cloudflare: DNS, Pages, reglas y analítica; dominio y correo de soporte.
- Telegram/BotFather, heartbeat externo y cualquier cuenta de Meta aún configurada.

El inventario identifica dónde rotar cada secreto, nunca contiene sus valores. Usa cuentas individuales, MFA y mínimo privilegio; evita cuentas compartidas.

## Alta de respaldo

1. Revisa propósito, conducta, privacidad y conflictos de interés.
2. Concede solo el acceso de su función y confirma que puedes revocarlo.
3. Ensaya una restauración aislada de Postgres y WAL con recordatorios apagados.
4. Practica fuente cambiada, caída de Neon, entrega incierta y solicitud de retiro.
5. Documenta en `MAINTAINERS.md` la función realmente aceptada.

## Salida o traspaso

Entrega estado de despliegue, pendientes, incidentes abiertos, monitores y próximos vencimientos. El responsable entrante verifica acceso antes de revocar al saliente. Rota tokens que hayan estado disponibles para más de una persona y confirma borrado o devolución de respaldos no autorizados.

Si nadie puede operar con seguridad, deshabilita recordatorios y nuevas suscripciones, conserva información estática útil con fecha de verificación y activa el cierre descrito en `SUNSET.md`. No transfieras datos vecinales a otra organización sin una base y un aviso nuevos.
