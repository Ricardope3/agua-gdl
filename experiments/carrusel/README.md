# Carruseles de Instagram

Drafts only: Ricardo reviews and posts. Nothing here is published.

```sh
python3 experiments/carrusel/build.py            # check all, render out/<id>/01.png…, FUENTES.md, caption.txt, hoja.png
python3 experiments/carrusel/build.py 07         # only ids starting with 07
python3 experiments/carrusel/build.py --check    # checks only
python3 experiments/carrusel/build.py --capturas # retake the aguagdl.com phone screenshots
```

macOS only (headless Chrome, `sips`, Avenir Next). 1080×1350 PNG per slide; `out/` is gitignored.

## Style

A crisis photo, darkened and slightly blurred, full-bleed; the Agua GDL drop and name at the top, the slide number top right; one big figure in brand blue, a short white headline, one line of context; red (`**…**`) for the bad side of a comparison, blue (`*…*`) for emphasis. The source line and aguagdl.com sit at the bottom of every slide. The last slide is always the `cierre`: logo, one action, the URL and the nonpartisan line.

Slide types: `portada`/`texto` (kicker, cifra, titular, texto), `cita`, `barras` (comparison bars), `iconos` (n of total drops, houses, people, trucks), `calendario` (zones × days), `versus` (two columns), `lista` (numbered or checkboxes), `linea` (timeline), `pregunta` (quiz; `respuesta` marks the answer), `sitio` (an aguagdl.com page on a phone, one of the page's own numbers and «link en la bio»), `cierre`.

Every carousel has a `sitio` slide before the `cierre`, so each figure leads to the page where people can see more or find their colonia. Its numbers come from the live page itself (cited as «Agua GDL, aguagdl.com/…, consultada el …») and keep the page's caveats («según medios y vecinos», «no es una medición oficial»). Those numbers change daily: retake the screenshots with `--capturas` and update the `cita` before posting. The screenshots leave out /contamina, the landing's top and /fotos, which show a caricature or people.

## Rules the build enforces

- Every number written on a slide appears in the `cita` of a source the slide cites, in the source's own date, or in the slide's `calculo`, which says how it was derived.
- A slide with no source (other than the `cierre`) says why in `propio`: our own question, proposal, method or service. Every factual claim needs a source.
- A `cita` slide's quote is word for word in its source's `cita`.
- Every source has `url`, `medio`, `fecha`, `cita` and `revisado`; `consultada: true` for undated pages (the footer says «consultada el …»).
- Every background is in `fotos.json`, reviewed by eye: no close face, no legible private name, no outlet watermark or burned-in caption. Three were dropped on 5 Nov for showing faces.

## Rules it can't enforce

- Copy each `cita` from the source itself, the same day, and set `revisado`. A pass checks shape, not truth.
- Captions are not checked: keep them to what the slides say.
- An official's figure stays theirs («según…», «dijo»); an outlet's paraphrase is the outlet's.
- Dated claims go stale: re-check the calendar (`ajustes.php`) and any «hoy» before posting.
