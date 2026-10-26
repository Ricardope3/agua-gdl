# Contribuir a Agua GDL

Agua GDL es un servicio vecinal gratuito, no oficial y sin partido. Las contribuciones deben mejorar la utilidad, accesibilidad, privacidad o verificabilidad del servicio; no convertirlo en una herramienta de campaña ni de perfilado político.

## Antes de empezar

- Para una corrección de datos o una fuente nueva, sigue `/correcciones` o abre un issue público sin incluir datos personales.
- Para una vulnerabilidad, usa el canal privado de [SECURITY.md](SECURITY.md); no publiques el detalle ni datos reales.
- Para cambios grandes, propón primero el problema, las personas afectadas y cómo se comprobará la mejora.
- No envíes padrones, conversaciones privadas, credenciales electorales, números telefónicos ni identificadores de suscriptores en issues o ejemplos.

## Desarrollo y pruebas

Trabaja en una rama y conserva cambios ajenos que ya existan. No ejecutes envíos reales de Telegram o WhatsApp: `REMINDERS_ENABLED` y `TG_REMINDERS_ENABLED` deben permanecer apagados fuera de producción.

```sh
cd api
go vet ./...
go test -count=1 ./...

docker run -d --rm --name aguagdl-pg \
  -e POSTGRES_PASSWORD=dev -e POSTGRES_DB=aguagdl \
  -p 55432:5432 postgres:17-alpine
TEST_DATABASE_URL='postgres://postgres:dev@localhost:55432/aguagdl?sslmode=disable' go test -race ./...
```

Desde la raíz:

```sh
python3 -m unittest discover -s pipelines -p 'test_*.py'
node --test experiments/reportes/status_test.mjs
python3 pipelines/mapa_colonias.py --check
python3 pipelines/promesas.py --check
python3 pipelines/publicaciones.py --check
python3 pipelines/zonas_json.py --check
python3 pipelines/simple_page.py --check
git diff --check
```

Las pruebas de integración se omiten sin `TEST_DATABASE_URL`; indica con precisión qué ejecutaste. Agrega pruebas para permisos, privacidad, límites, idempotencia y estados de error cuando cambien.

## Archivos generados y datos

No edites por separado una salida y su fuente. Regenera con el pipeline correspondiente:

- `web/reportes.html` y sus variantes: `python3 experiments/reportes/colonia.py`.
- `web/promesas.html`: `python3 pipelines/promesas.py`.
- `web/zones.json`: `python3 pipelines/zonas_json.py`.
- `web/simple.html`: `python3 pipelines/simple_page.py`.
- Calendarios: `cd api && go run ./cmd/calendars` después de cambiar la rotación.

Las migraciones aplicadas no se editan: agrega un archivo numerado nuevo. Toda afirmación pública debe conservar fuente, fecha de revisión y alcance. Respeta los umbrales de privacidad y no presentes testimonios como mediciones oficiales, muestras representativas, calidad de laboratorio o prueba de impacto.

## Revisión

Una contribución está lista cuando las pruebas aplicables pasan, la accesibilidad básica sigue intacta, el aviso de privacidad coincide con el comportamiento y las salidas generadas están actualizadas. Los mensajes de commit van en inglés, con asunto de hasta 72 caracteres.
