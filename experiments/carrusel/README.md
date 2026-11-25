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

Slide types: `portada`/`texto` (kicker, cifra, titular, texto), `cita`, `barras` (comparison bars), `iconos` (n of total drops, houses, people, trucks), `calendario` (zones × days), `versus` (two columns), `lista` (numbered or checkboxes), `linea` (timeline), `pregunta` (quiz; `respuesta` marks the answer), `perfil` (one bar per value in `alturas`, sorted, y axis from `eje`, with a `marca` and `mediana`), `altura` (histogram of `bins`), `desnivel` (signed bars around a centre value), `sitio` (an aguagdl.com page on a phone, one of the page's own numbers and «link en la bio»), `cierre`.

Every carousel has a `sitio` slide before the `cierre`, so each figure leads to the page where people can see more or find their colonia. Its numbers come from the live page itself (cited as «Agua GDL, aguagdl.com/…, consultada el …») and keep the page's caveats («según medios y vecinos», «no es una medición oficial»). Those numbers change daily: retake the screenshots with `--capturas` and update the `cita` before posting. The screenshots leave out the landing's top, /fotos and /contamina's top, which show a caricature or people; `contamina-dg135` starts below it, at the DG-135/2026 paragraph (`DESDE`), and stops before «El daño a la salud» (`HASTA`), which a slide about the oficio would seem to tie to it.

## Fields

A carousel is `carruseles/<id>.json`: `id` (the file name), `titulo`, `caption`, `fuentes` (key → `url`, `medio`, `fecha`, `revisado`, `cita`, optional `consultada`) and `slides`. Each slide has `tipo`, optional `foto`, `fuentes` (keys), `calculo` (how a derived number was computed) or `propio` (why it has no source), plus its type's fields. In text, `*…*` is blue and `**…**` red. `[[nestle]]` draws a company's logo from `logos/` (`LOGOS` in build.py: the file its own site serves, cut only to drop a slogan; `logos/nestle.svg` is the file as downloaded 25 Nov 2026 from nestle.com.mx, sha256 8be96582…2137) and `[[conagua]]` a name badge for a government body (`SELLOS`): no official emblems, which could read as endorsement and may carry the national coat of arms. Put logos in labels and kickers, not inside a headline. Our own analyses live in `datos/` (`elevacion.py` → `elevacion.json`, `stats.json`).

A `portada` or `texto` slide can show an official document as a paper card above its text: `documento` gives `fuente` (a key the slide cites), `membrete` (cuts of the letterhead, side by side), `recortes` (the cited lines, one cut per line, highlighted; a `"…"` between two cuts shows «[…]» where the document's text was skipped) and `dice` (the words those lines show, with «…» at each skip). The cuts are PNGs in `documentos/`, made from the PDF aguagdl.com publishes by `documentos/recortes.py` (boxes in pixels at 200 dpi, found with `documentos/boxes.swift`, macOS's text recognition). Leave out stamps, handwriting, signatures and names; carousel 22's cover shows Zapopan's letterhead this way rather than its logo on its own, which would read as the government's post.

## Rules the build enforces

- Every number written on a slide appears in the `cita` of a source the slide cites, in the source's own date, or in the slide's `calculo`, which says how it was derived.
- A slide with no source (other than the `cierre`) says why in `propio`: our own question, proposal, method or service. Every factual claim needs a source.
- A `cita` slide's quote is word for word in its source's `cita`, and so is a `documento`'s `dice`; its cuts exist, and each «…» inside the `dice` has a `"…"` in `recortes`, so the card never shows two distant lines as one passage.
- Every source has `url`, `medio`, `fecha`, `cita` and `revisado`; `consultada: true` for undated pages (the footer says «consultada el …»).
- Every background is in `fotos.json`, reviewed by eye: no close face, no legible private name, no outlet watermark or burned-in caption. Three were dropped on 5 Nov for showing faces.
- Each entry in `creditos.json` is a photo in `fotos.json` with `credito`, `porque` and `revisado`.

## Photo credits

The footer credits a background as «Foto: outlet, colonia», taken from its post in `web/publicaciones.json` (the first colonia listed), unless `creditos.json` gives a reviewed credit. The generated one is only true when the image is the outlet's own and was taken in that colonia, which the post's colonias don't show. Read the outlet's photo caption before using a background; when it credits someone outside the outlet, or names another place or none, add the photo to `creditos.json`: the credit says only what the source says, and anything we worked out ourselves (a municipio from the map) goes in `porque`. On 18 Nov 2026 all three photos checked had generated credits naming a colonia their source doesn't give: UDG TV's protest image is «de redes sociales», at Periférico and avenida Guadalupe, not in Hacienda del Tepeyac; Meganoticias' lead image has no caption, so it takes only its story's place, «nota sobre colonias de Zapopan»; NTR's caption gives a metropolitan figure and its story names colonias in two municipios, so it has no place (carousel 21, posted, has used it since its first commit, so its footer reads La Mesa Colorada Poniente). A photo whose source places it nowhere, not even through its story, doesn't go on a slide about one colonia or municipio.

## Rules it can't enforce

- Copy each `cita` from the source itself, the same day, and set `revisado`. A pass checks shape, not truth.
- Captions are not checked: keep them to what the slides say.
- An official's figure stays theirs («según…», «dijo»); an outlet's paraphrase is the outlet's.
- Dated claims go stale: re-check the calendar (`ajustes.php`) and any «hoy» before posting.
