# Respuesta a incidentes

Prioriza a las personas y la integridad de los avisos sobre mantener apariencias o recuperar servicio a cualquier costo. No hay promesa de atención 24/7 mientras las funciones de respaldo estén abiertas.

## 1. Contener sin destruir evidencia

- **Avisos duplicados o posteriores a BAJA:** deshabilita el canal afectado y detén el remitente. No borres reservas ni repitas intentos `sending` o `uncertain`.
- **Datos personales expuestos:** retira el acceso público, rota credenciales si procede y limita nuevas escrituras. No copies el contenido expuesto a tickets o chats.
- **Calendario o zona incorrectos:** conserva la fuente y la versión desplegada, corrige los datos y evalúa un aviso de corrección a las zonas afectadas mediante los mecanismos idempotentes existentes.
- **Reportes o WAL en riesgo:** detén la instancia, conserva base, WAL y cualquier `.tmp`; no compactes ni reconstruyas a mano. Restaura en aislamiento antes de reabrir.
- **Sitio o fuente alterados:** congela el despliegue, conserva artefactos y hashes, revoca el acceso responsable y vuelve a una versión verificada.

## 2. Registrar el alcance

Anota tiempos con zona horaria, versiones, componentes, acciones y responsable. Guarda logs con acceso restringido y el mínimo de identificadores posible. Determina qué personas, zonas, reportes o mensajes pudieron verse afectados y qué sigue siendo incierto.

## 3. Recuperar y verificar

Usa una sola instancia, una base y un WAL conocidos. Ejecuta pruebas y comprueba idempotencia, baja, privacidad y conteos antes de habilitar avisos. Si una entrega quedó ambigua, permanece incierta salvo confirmación del proveedor.

## 4. Comunicar y corregir

Publica una nota comprensible cuando el incidente afecte decisiones vecinales o datos: qué ocurrió, alcance conocido, qué no se sabe, acción inmediata y canal de contacto. No minimices ni atribuyas causa sin evidencia. Corrige también copias, agregados y páginas derivadas; una corrección no exige conservar públicamente el dato retirado.

## 5. Aprender

Documenta causa técnica y organizativa, señales que faltaron, cambios preventivos y responsable de seguimiento. Actualiza pruebas, monitoreo, privacidad o runbooks según corresponda. No declares cerrado el incidente mientras queden accesos por revocar, datos por borrar o monitores sin restaurar.
