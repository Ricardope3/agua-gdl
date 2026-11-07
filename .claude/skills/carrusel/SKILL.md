---
name: carrusel
description: Make Instagram carousel images (1080×1350 PNG) for Agua GDL from sourced facts, with experiments/carrusel/build.py. Drafts only; Ricardo posts.
disable-model-invocation: true
---

Arguments: the topic, a colonia, or the facts to show.

1. Read `experiments/carrusel/README.md`, `.claude/rules/evidence.md`, `docs/EDITORIAL.md` and `.claude/rules/vetos.md`. Look at `experiments/carrusel/carruseles/` for a carousel close to the ask and copy its shape.
2. Facts: take them from the repo's data (`publicaciones.json` via `publicaciones.py q`, `promesas.json`, `api/data/rotation.json`, /noticias) and open every source in this session. Copy the passage you rely on, word for word, into the source's `cita` and set `revisado` to today. Official figures stay theirs («según…», «dijo»); an outlet's paraphrase is the outlet's; keep qualifiers («alrededor de», «al menos», «más de»). Never relay a number you didn't read.
3. Shape, 5–8 slides: a hook (one big figure or a question), the evidence (`barras`, `iconos`, `versus`, `calendario`, `linea`, `perfil`, `cita`), the honest limit (what the data doesn't show), a `sitio` slide that sends people to the matching aguagdl.com page with that page's own number and «link en la bio», and the `cierre`. Ricardo wants numbers that draw people to the site and nothing he has already posted; ask which cards to skip.
4. Insights that are ours (a calculation, a ranking, a correlation) go in a script under `experiments/carrusel/datos/` with its output committed, are cited as «cálculo de Agua GDL», and are framed as a lead, not a cause, unless a source states the cause.
5. Backgrounds: only photos in `experiments/carrusel/fotos.json`. To add one, look at it first: no close face, no legible private name, no outlet watermark or burned-in text.
6. Run `python3 experiments/carrusel/build.py --check` until it passes (every number in a cited `cita`, the source's date or the slide's `calculo`; quotes verbatim; unsourced slides say why in `propio`). Before a `sitio` slide, run `--capturas` and copy the live page's numbers into its `cita`.
7. Render with `python3 experiments/carrusel/build.py <id>`, open `out/<id>/hoja.png` and each slide, and fix overlaps, cut-off text and anything that reads stronger than the source. For a new carousel or a big change, have one read-only reviewer check slides and caption against the `cita`s; fix what it finds.
8. Copy the result to `~/Desktop/carruseles-agua-gdl/<id>/` (replace the folder), send Ricardo the PNGs, and say where they are. Commit as soporte@aguagdl.com on the carousel branch; push only when he says.
9. Never post, schedule or open Instagram.
