---
paths:
  - "web/publicaciones.json"
  - "web/promesas.json"
  - "web/promesas.html"
  - "web/noticias.html"
  - "web/pipas.html"
  - "web/contamina.html"
  - "web/antisionismo.html"
  - "web/exige.html"
  - "web/informes.html"
  - "web/semana/**"
  - "web/fuentes/**"
  - "pipelines/publicaciones.py"
  - "pipelines/promesas.py"
  - "pipelines/videos.py"
---

# Evidence and published claims

A wrong published claim is this project's most expensive failure. Also read `docs/EDITORIAL.md`. For checking sources, use the `verificador` subagent; for finding them, `buscador`.

Field meanings, SIAPA's terms to quote as written, and word pairs agents got wrong: `docs/GLOSARIO.md`.

Errors a fact-check found are listed in `KNOWN_ERRORS` (`pipelines/copy_rules.py`); `scripts/check_known_errors.py` (in `check.sh`) fails when one comes back in `web/`, `docs/`, `pipelines/` or the local `research/`, quotes included. When you find an error that could recur, add it there in the same commit as the fix.

## `publicaciones.json` (checked by `pipelines/publicaciones.py`)

News and neighbours' posts since 12 Oct 2026 about colonias without water, each with its link, date, colonias (keys of `colonias_mapa.json`), its words as published (`cita`, checked against the post when added), the days without water it gives (`dias`, or null), `bloqueo` for street blockades, and its reactions, comments and shares with the date they were read (`eco`). Top level also carries `busquedas`, the sorted distinct ISO dates of the searches for posts (shown on /reportes as the last search). `--check` validates shape and these rules; it does not fetch sources or confirm quotes, so a pass is not verification.

- News outlets (`fuente: medio`) count without a threshold and go first; neighbours (`vecinos`) need `regla.reacciones` reactions and `regla.comentarios` comments, and a neighbour's comment (`tipo: comentario`) counts only inside a post that meets the rule (`en`); on X, a reply counts by the post it answers. One article can give several entries, one per quote; a story that retells a post names it in `de` and counts as that post's source.
- The other side of the story, only as the source's own claim: `regreso` (ISO date the source says the water came back, within `desde`..`fecha`), `parcial` (low or intermittent supply), `calidad` (quality-only complaint) and `causa` (the cause the source names, 1–80 chars). /reportes shows a colonia whose newest publication reports the return with a «regresó» headline, keeping the older days as history.
- Never a private person's name: `quien` is the outlet, «Grupo «…»» (public groups only) or «Cuenta de vecinos …»; `en.quien` (the post a comment is in) is an outlet some `medio` entry names, one of those, or a public page listed in `PAGINAS` in the script (add one only after checking it's a page, not a person; a person's X account goes as «Cuenta personal en X», never by name). A link can still show an X handle; the privacy notice says anyone can ask soporte@aguagdl.com to remove theirs.
- `--eco` refreshes the X numbers through X's public embed endpoint (`cdn.syndication.twimg.com`, no login); Facebook's need a login and keep the date they were read. `--videos` uses the same public X embed to set `video: true` where it serves a video; direct reel/watch/YouTube/TikTok links require that marker too, while an absent marker means unknown. `pipelines/videos.py` (run after `publicaciones.py --check` passes) writes `web/videos.json`, the download list of video-carrying posts, stale-checked by `python3 pipelines/videos.py --check`; no page loads it yet. `--imagenes` (macOS, `sips`) saves each post's preview as a 480 px JPEG in `web/fuentes/` (`vista`; null for a logo or stock picture, which keeps it out of later runs), so visitors never load Facebook, X or the outlets; `--capturas` (headless Chrome) saves the top of each news article as `web/fuentes/<hash>-t.jpg` (`captura`) and its `og:title` as `titular`. The private notes say how the posts were found.
- Query and edit through the script, not ad-hoc Python: `q colonia~ARCOS fecha>=2026-10-20 --fields url,dias` (TSV with index, `--count`, `--all`), `schema`, `add FILE.json` and `set INDEX field=value` (`field=` removes) validate the whole file and write only if it passes; `--data PATH` works on a copy.

## Pages

- `promesas.html` (/promesas): each government water promise beside the law or document, with a verdict and steps. Its cards and meter are generated: edit `web/promesas.json`, then run `python3 pipelines/promesas.py`. It fails unless every source has an archive.org snapshot or a private copy (`"captura": "privada"`), «Incumplida» has two independent sources, «Se contradice» quotes the document, each entry has one core step, no «miente/engañó» appears outside quotes, and «israelí» appears only in a quote; `--check` fails if the page is stale; `--drafts --out DIR` previews without archives outside `web/`. «Two independent sources» is checked only as two distinct `medio` strings: reprints of one story pass, so check independence yourself. The plan, research and private copies are in the private notes repo (`projects/promesometro.md`).
- `noticias.html` is the crisis day by day, curated by hand: videos load from YouTube, TikTok or X only when tapped (their thumbnails are in `img/videos/`, so opening the page contacts nobody), and «Día por día» filters by each `<article>`'s `data-tags`. Every item links its source; update «Última actualización» when you edit it.
- `pipas.html` (/pipas) gives SIAPATEL and each municipio's own line, each with its official source or the news report that quotes the announcement, the Ley del Agua's article 90, fracción VI, and the date they were checked. Publish a channel only when a source states it (SIAPABOT is SIAPA's line «para dudas», not a pipa channel; 073, not 070), and say a pipa is free only where the source does.
- `exige.html` (/exige) asks the governor and the 38 deputies to clean the rivers, bring clean and sufficient water, account for it and keep water public. It merges the old /exige (offices per municipio) and /escribe (the vote against the aqueduct APP, which the Congreso stopped processing on 23 Oct after the federal government took on the aqueduct); /escribe 301s here and its tab hashes still work. Tabs: Correo (the visitor's case, «¿Qué pasa en tu colonia?», builds the message until they edit it; one email per recipient, the governor first, through Gmail or their mail app), Tu diputación (INE section → district), X y Messenger, A quién (all 39 with email, accounts and phone) and Por qué. The governor's email and phone come from the Despacho's transparency directory, his X and Facebook are @GobiernoJalisco from jalisco.gob.mx; the deputies' from their Congreso profiles. Progress is kept in `localStorage` (`exige-enviados`, `exige-x`, `exige-messenger`; the privacy notice says so). `?q=&m=` from /reportes fills the colonia. Nothing is sent to Agua GDL.
- Advocacy pages: `exige.html`, `contamina.html` (Río Santiago polluters) and `antisionismo.html` (the maintainer's position against the State of Israel). Every factual claim there links its source; keep it that way, and never state that an Israeli company is part of the Jalisco aqueduct APP unless a source shows it.
- `informes.html` indexes reviewed weekly counts (`cmd/informe`, see `.claude/rules/api.md`); it says when none has been published.
