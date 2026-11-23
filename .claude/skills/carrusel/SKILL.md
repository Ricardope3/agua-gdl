---
name: carrusel
description: Make Instagram carousel images (1080×1350 PNG) for Agua GDL from sourced facts with experiments/carrusel/build.py. Drafts only; Ricardo posts.
disable-model-invocation: true
---

Arguments: the topic, a colonia, or the facts to show. If the ask is vague, propose 2–3 angles with the one number each would lead with, and wait for his pick.

## Before writing

- Read `experiments/carrusel/REFERENCIAS.md` (what the carousels he admires do) and `experiments/carrusel/README.md` (slide types, fields, what the build checks), `.claude/rules/evidence.md`, `docs/EDITORIAL.md`, `.claude/rules/vetos.md`, and the closest carousel in `experiments/carrusel/carruseles/`.
- Read `experiments/carrusel/PUBLICADOS.md` and ask which cards he has already posted on Instagram; don't repeat them (he cut a top-5 bar chart and a protest timeline on 6 Nov for that reason).

## Facts

- Start from the repo's data (`publicaciones.py q`, `promesas.json`, `api/data/rotation.json`, /noticias), then open each source in this session. A summary in the repo, a subagent or a status file is a lead, not a source.
- Paste the passage you rely on, word for word, into that source's `cita`, with `revisado` set to today and `consultada: true` for undated pages. Quote scanned documents from the page image, not OCR.
- Every factual claim needs its source on the same slide, in `fuentes`. A slide without one says why in `propio` (our question, proposal, method or service).

## Wording traps (each one shipped in a draft and was caught on review, 5 Nov)

- An outlet's paraphrase is the outlet's: «según El Informador, la presidenta dijo…», never her words in quote marks.
- Credit the speaker the source credits, with its date: the governor's 6 Oct message is «el mensaje que reproduce Expansión (8 oct)» unless you read the original.
- Keep qualifiers: «más de», «al menos», «alrededor de», «hasta», «según». A hypothetical («puede costar») is not a fact («cuesta»).
- No cause without a source that states it, and no juxtaposition that implies one (an official promise next to a headline about a colonia without water).
- Name official programmes and figures as the government's claim, not ours («según el Gobierno de Jalisco, 4 de 10 hogares…»).
- Don't add conditions or omit them: the 80% discount always carries «hasta 25 m³» and «afectados por la calidad del agua».
- The build checks every «…» on slides (against the slide's cited `cita`s) and in captions (against any `cita`), capitals included; it can't check paraphrase, so still read each caption against the `cita`s.
- When a photo is shown sharp, re-check it at full size: a faint outlet watermark or a banner naming another colonia can surface (6 Nov: 0e61b3ddde0a dropped for a Mural watermark).

## Official documents (learned on carousel 22, 18 Nov)

- To show a number is the government's, cut its document onto the slide (a `documento`: letterhead plus the highlighted lines), not its logo alone, which reads as the government's own post. He chose «document cutout plus the new line».
- Find each cut's box with `documentos/boxes.swift` (macOS's built-in text recognition), not by eye or with ink thresholds: those merged lines on noisy scans and missed light chart labels. Pad the tight boxes about 8 px.
- Cut a wrapped sentence line by line at word boundaries, each line at most ~870 px wide at 200 dpi, so it shows at full size; the `dice` is those words, word for word.
- Leave out stamps, handwriting, signatures and every name (the official's and the requester's). Open each cut at full size before using it.
- A scanned chart's labels are ~8 px at 200 dpi, unreadable on a phone: circle the values and write them as our own tags, read from the image at 300 dpi and matched against the document's transcription.
- The `url` must be a PDF people can open. Research PDFs are gitignored; publishing one in `web/datos/` needs his OK after a check for names and personal data.
- Announced vs registered: «anunció» and «registró», never «mintieron»; the limit slide gives the innocent readings (a planned fleet, an undated list).
- Mark skipped text with a `"…"` between cuts (the card shows «[…]»); the build fails when the `dice` skips and the card doesn't. Carousel 22's limit slide joined a plan's lead-in to its third bullet as if one passage.
- Name a document as it names itself (19 Nov review of carousel 22): a chart sent «con base en los registros de seguimiento», after the daily records were declared inexistent, is «la gráfica», not «su registro diario»; a list headed «listado de cisternas instaladas» is that, not «la lista». An absence in a table says what was asked («Pedimos los registros de… centros de salud»), and a «no se localizó» names the office and its archives, never a passive «no se localizaron».

## Our own analysis

- A ranking, percentile or correlation goes in a script in `experiments/carrusel/datos/` with its output committed (see `elevacion.py`, `stats.json`), cited as «cálculo de Agua GDL» with the data source.
- Show the limit next to the finding. Frame it as a lead, not a cause, unless a source states the cause. The elevation carousel says «una explicación posible… una pista, no una prueba» because elevation barely tracks complaints across colonias (Spearman −0.03).
- Charts: the quantity people care about goes on the y axis (6 Nov: a histogram of colonias per height band confused him; a ranked profile with elevation on y didn't). Label a y axis that doesn't start at zero.

## Shape

- 5–8 slides: a cover that asks the reader's own question («¿Te toca corte mañana?»), one fact per slide (the same map or frame, one new layer each), the evidence, the honest limit, a `sitio` slide, then the `cierre`. Numbers that make people want to check their own colonia beat abstract totals. Guides people save (how to ask for a pipa, the discount, a letter to a diputación) show the real form or message with the explained part highlighted. The caption tells the whole story, numbers included.
- The `sitio` slide shows the matching aguagdl.com page with that page's own number and «link en la bio». Run `python3 experiments/carrusel/build.py --capturas` first and copy the live numbers into its `cita`. Screenshots skip pages showing faces, the caricature, or the /promesas stance line (`DESDE` crops it). Look at the capture before building: a map that fits more than the phone frame shows its empty edge, so set the page's drag in `PANEO` (`mapa.mjs`) and retake only that page with `--capturas <página>`.
- Backgrounds only from `experiments/carrusel/fotos.json`. To add one, open it first: no close face, no legible private name, no outlet watermark or burned-in text.

## Look and words (learned from @ecosia, 6 Nov)

- One idea per slide, one sentence of at most ~15 words; the punchline bold, any context smaller. Cut the kicker when the headline says it.
- Let a sharp photo carry the point: put the number on the photo (a tag on the empty tinaco, the turbid glass, the pipa line), and compare with split slides of the same frame in two states (promised vs calendar, before vs now). Only photos with no close faces or names.
- Keep the source credit on each slide short and quiet; put the full source list in the caption («📚 Fuentes: medio, fecha, enlace»).
- Pair every alarm with agency: what helped, what came back, what one person can do that works (a report on the map, a letter to the diputación, the discount claimed).
- End the caption with a question people can answer in the comments («¿Cuántos días lleva tu colonia?»).

## Build and review

1. `python3 experiments/carrusel/build.py --check` until it passes. It checks shape, not truth.
2. `python3 experiments/carrusel/build.py <id>` (all 21 take ~3 min; render only what changed).
3. Open `out/<id>/hoja.png` and every slide at full size: overlapping labels, text running into the footer, numbers wrapping, faces in the photo.
4. For a new carousel, one read-only reviewer (`auditor`; outside `~/agua-gdl`, an Explore agent with its rules pasted) checks every slide and the caption against the `cita`s. Re-open the source for each finding before fixing it; don't relay the reviewer's claim.
5. Replace `~/Desktop/carruseles-agua-gdl/<id>/` with the new `out/<id>/`, send him the PNGs, and say what changed.
6. Commit as soporte@aguagdl.com (check `git log -1 --format=%ae`) on the carousel branch; push only when he says.

When he says a carousel went out, add it to `PUBLICADOS.md`. Never post, schedule or open Instagram. Before he posts a carousel with dated numbers (calendar, site counts, municipal pipa figures), offer to re-check them.
