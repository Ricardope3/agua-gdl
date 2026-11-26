---
name: carrusel
description: Make Instagram carousel images (1080×1350 PNG) for Agua GDL from sourced facts with experiments/carrusel/build.py. Drafts only; Ricardo posts.
disable-model-invocation: true
---

Arguments: the topic, a colonia, or the facts to show. If the ask is vague, propose 2–3 angles with the one number each would lead with, and wait for his pick.

## Before writing

- Read `experiments/carrusel/REFERENCIAS.md` (what the carousels he admires do) and `experiments/carrusel/README.md` (slide types, fields, what the build checks), `.claude/rules/evidence.md`, `docs/EDITORIAL.md`, `~/agua-gdl/.claude/rules/vetos.md` (main's copy: a worktree's can be older), and the closest carousel in `experiments/carrusel/carruseles/`.
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
- Name the place, not its category: «Ocotlán», not «el municipio» (25 Nov), on slides, labels and the caption. Quotes and `calculo` notes keep their own words.
- «2.4 veces más» means 3.4 times: write «2.4 veces». «Todo el municipio» is wrong when another holder or use has more (Ocotlán's farms hold more well water than Nestlé).
- The build checks every «…» on slides (against the slide's cited `cita`s) and in captions (against any `cita`), capitals included; it can't check paraphrase, so still read each caption against the `cita`s.
- When a photo is shown sharp, re-check it at full size: a faint outlet watermark or a banner naming another colonia can surface (6 Nov: 0e61b3ddde0a dropped for a Mural watermark).

## Scope and records (learned on carousel 24, Nestlé, 25 Nov)

- Scope every comparison to what the data covers, in the headline and the labels, not only the kicker. A REPDA export by water type isn't the municipality's water: «el permiso más grande del municipio» was wrong because the CEA holds a 324,820,800 m³ surface title in Ocotlán; it became «el permiso de pozo más grande». Check the other water types before any «el más grande».
- Name who holds a permit as the register does («Municipio de Ocotlán», «uso industrial»), not a reading of it («el servicio público»). REPDA volumes are ceilings: say «permiso» or «límite», never «saca» or «consume».
- A figure your own research notes flag as a possible reporting error (a README's outliers, the same value in two years) stays off the slides until the agency confirms it. Carousel 24's RETC metals slide was dropped for that.
- Date and credit a quote by the page that carries it: a 2020 page that cites nestle.com.mx is «Nestlé, según The Food Tech», not «Nestlé, 2014».
- When he asks to cut context (the agriculture bar), keep the limit as one line of text and tell him you did.
- A company's own disclosures beat a permit. Its CDP answers or sustainability report list withdrawals and discharges per factory, which a REPDA ceiling can't show. Nestlé's 2020 CDP answers put 11,000 m³ of well water at the «Cero agua» plant and 341,000 m³ discharged at Ocotlán. Search the company's site for every year (`cdp-<empresa>-answers-water-security-<año>.pdf`) and use the latest. Convert its units in `calculo` (1 megalitro = 1,000 m³). Check where a facility is: the report names «Zula», not a municipio.
- Scope a claim to what the speaker said. «"Cero agua" operará sin extraer el líquido del subsuelo» is about one plant, not about Nestlé never using wells. When he asks for «miente», show him where the source is narrower and offer a blunt line the records carry. Do what he decides, then tell him which lines elsewhere (caption, the questions slide) now disagree.

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

- 5–8 slides: a cover that asks the reader's own question («¿Te toca corte mañana?») or, when one comparison is the story, that comparison itself (carousel 24 opens on its bar slide: he dropped the question cover to catch attention, 25 Nov), one fact per slide (the same map or frame, one new layer each), the evidence, the honest limit, a `sitio` slide, then the `cierre`. Numbers that make people want to check their own colonia beat abstract totals. Guides people save (how to ask for a pipa, the discount, a letter to a diputación) show the real form or message with the explained part highlighted. The caption tells the whole story, numbers included.
- Every slide earns its place by what it adds to the story; a fact that only matters next to another goes on that slide (25 Nov: he asked why the 2025 cession mattered, and it moved under the 2014 «sin extraer» claim). He cut carousel 24 from 8 slides to 5: fewer, stronger slides beat a full timeline.
- When he drops a slide that carried a limit, move the limit onto a slide that stays (a `versus` takes a `texto` line under its boxes) and keep it in the caption; check that the `lista` items still point to something shown. When the slides leave date order, reorder the caption to match and drop any «de lo más reciente a lo más antiguo».
- Say which body a carousel is about: SIAPA serves only the Guadalajara metro area; permits are the CONAGUA's.
- The `sitio` slide shows the matching aguagdl.com page with that page's own number and «link en la bio». Skip it, and say why, when the page's number for this subject isn't confirmed (carousel 24: /contamina's Nestlé 82.60 kg). Run `python3 experiments/carrusel/build.py --capturas` first and copy the live numbers into its `cita`. Screenshots skip pages showing faces, the caricature, or the /promesas stance line (`DESDE` crops it). Look at the capture before building: a map that fits more than the phone frame shows its empty edge, so set the page's drag in `PANEO` (`mapa.mjs`) and retake only that page with `--capturas <página>`.
- Backgrounds only from `experiments/carrusel/fotos.json`. To add one, open it first: no close face, no legible private name, no outlet watermark or burned-in text.
- New carousels use `"estilo": "talavera"` (25 Nov: he asked for it after a draft came out in the old dark look). Look at every slide type in it: a type the theme has no rules for renders in the dark theme's colours. Bars, versus and lists got Talavera rules on 25 Nov; add rules in `estilos.py` for any other type you use. The tile bands and double frame came out on 25 Nov: he found them busy beside highlighted text, so keep decoration off the slides. An `alarm` bar and its figure are deep red (#b3231a, from the «expediente» theme), the other bars pale blue: he chose red on the data over a red logo (25 Nov). Plain `talavera` has no rules for `linea`, card bars (`nombre`), `destacado` or `aviso`: carousel 24 uses «ficha», restyled toward Talavera (italic headline, white boxes in the double cobalt rule, timeline rules), after he asked for «more like Talavera». A `destacado` takes `"marca": "•"` instead of the star. Removing a note leaves empty space and adding a source can push the source line off the slide: open every slide at full size, and drop a source the slide no longer cites.
- Logos: a company's logo with `[[name]]` (`LOGOS` in build.py), from the file its own site serves, cut only to drop a slogan; a government body as a name badge (`SELLOS`) unless he picks its emblem: ask, since an emblem can read as endorsement (25 Nov: a badge for CONAGUA, Ocotlán's shield for the municipio's bar). Never recolour or alter a logo to pass judgement: when he asked for Nestlé's letters in red «to show they are evil» (25 Nov), the answer was that the slides show records, not intent (the «mintieron» veto), that a doctored logo hands critics an easy rebuttal and may raise a trademark complaint, and that red on the company's bar and figure makes the point from the data. Explain that and do what he decides. Put logos in labels and kickers, not inside a headline; `"marca_grande"` puts one large on the cover. Use the version that reads at label size (Ocotlán's shield alone, not the lockup whose words turn to specks) and look at it on cream before building. Downloading a logo needs his OK; a site that refuses plain requests is fetched in the built-in browser, never with a spoofed user agent; either way compare the saved file's hash with the copy the browser loaded, and note the source and hash in the README.
- A theme change reaches every carousel that uses it (`grep -l '"estilo": "talavera"' experiments/carrusel/carruseles/*.json`): tell him which ones, and rebuild one he may already have posted only when he asks.

## Look and words (learned from @ecosia, 6 Nov)

Plain and clear (25 Nov: he sent a dense mockup of carousel 24 and asked for something «more cohesive and easy to understand»):

- Headlines name the subject or ask the reader's question: «La planta «Cero agua» de Nestlé», «¿Qué pasa con el agua que usa Nestlé en Ocotlán?». Avoid headlines about the documents themselves («Lo que dijo Nestlé y lo que sigue en el registro», «Lo que se publicó y lo que registró la CONAGUA»): they make the reader work out the point.
- Tell one place's story in date order on one slide: the claim, what the company itself reported, what the register shows. A timeline (`linea`) reads more easily than two versus boxes and a footnote.
- Use one unit through the whole carousel, slides and caption (m³ here). A slide that mixes «millones de litros» and m³ makes the reader convert.
- Give one comparison anyone can hold: «Su permiso es unas 54 veces lo que reportó sacar de pozo en 2019».
- Plain names for sources on the slide («Su propio reporte, año 2019»; «Expansión, 6 de octubre de 2016»). The acronym and title go in the source line.
- The kicker is just the place. Each slide gets at most one pair of boxes and one note. Say a caveat once in the carousel, not on every slide.
- The questions slide asks what a neighbour would ask, with the numbers that make it sharp («¿Por qué conserva un permiso de 599,600 m³ al año si en 2019 reportó sacar 11,000?»). Drop meta-lines like «Son nuestras preguntas…».
- From a mockup, take its order and story, cut what isn't needed to follow it, and leave out anything without a source in the carousel (it had «Comunicado oficial de Nestlé» and «fábrica Nantli»). Tell him what you dropped.

- When he asks for other wording, give 4–5 lines checked against the data, each with a note on what it claims and on any word that would overstate, and let him pick (25 Nov: he took the third of five).
- The opening slide names its subject in words, not only with a logo: with the cover gone, «Una sola empresa…» became «Nestlé, una sola empresa…».
- One idea per slide, one sentence of at most ~15 words; the punchline bold, any context smaller. Cut the kicker when the headline says it.
- Let a sharp photo carry the point: put the number on the photo (a tag on the empty tinaco, the turbid glass, the pipa line), and compare with split slides of the same frame in two states (promised vs calendar, before vs now). Only photos with no close faces or names.
- Keep the source credit on each slide short and quiet; put the full source list in the caption («📚 Fuentes: medio, fecha, enlace»). `build.py` appends that list, with links, to `caption.txt`: don't write it in the JSON `caption`, and keep that caption near 1,100 characters so the whole stays under Instagram's 2,200.
- Pair every alarm with agency: what helped, what came back, what one person can do that works (a report on the map, a letter to the diputación, the discount claimed).
- End the caption with a question people can answer in the comments («¿Cuántos días lleva tu colonia?»).

## Build and review

1. `python3 experiments/carrusel/build.py --check` until it passes. It checks shape, not truth.
2. `python3 experiments/carrusel/build.py <id>` (render only what changed; all of them take minutes).
3. Open `out/<id>/hoja.png` and every slide at full size: overlapping labels, text running into the footer, numbers wrapping, faces in the photo. To move or drop slides, load the JSON and write it back with `json.dumps(c, ensure_ascii=False, indent=1) + "\n"`, which reproduces the files byte for byte (checked 25 Nov). Keep a figure with its unit on one line with a no-break space in the JSON (`"**2.4\u00a0veces**"`).
4. For a new carousel, one read-only reviewer (`auditor`; outside `~/agua-gdl`, an Explore agent with its rules pasted) checks every slide and the caption against the `cita`s and against the primary captures or data (the `cita` is our own copy). Carousel 24's reviewer found the surface title only because it was pointed at the exports. Re-open the source for each finding before fixing it; don't relay the reviewer's claim.
5. Replace `~/Desktop/carruseles-agua-gdl/<id>/` with the new `out/<id>/` (`rsync -a --delete`, so a dropped slide's PNG doesn't stay behind), send him the PNGs, and say what changed.
6. Commit as soporte@aguagdl.com (check `git log -1 --format=%ae`) on the carousel branch; push only when he says.

When he says a carousel went out, add it to `PUBLICADOS.md`. Never post, schedule or open Instagram. Before he posts a carousel with dated numbers (calendar, site counts, municipal pipa figures), offer to re-check them.
