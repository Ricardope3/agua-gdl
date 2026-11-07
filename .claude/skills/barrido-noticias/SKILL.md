---
name: barrido-noticias
description: Sweep news, neighbours' posts and their comments (Facebook, X, TikTok, YouTube, outlets) about colonias without water since a date, or read a post Ricardo sends, verify each item on the page and add the ones that hold to web/publicaciones.json and /fotos.
disable-model-invocation: true
---

Arguments: the since-date (default: the latest date in `busquedas`), optional outlets, pages or colonias to focus on, or links Ricardo sent.

1. Read `.claude/rules/evidence.md`, `docs/GLOSARIO.md`, `.claude/rules/vetos.md` and this skill's `references/busqueda.md`. The project agents (`recolector`, `navegador`, `verificador`, `auditor`) load only in a session started in `~/agua-gdl`; elsewhere use general-purpose agents with the agent file's rules pasted into the prompt.
2. Search, at most 8 agents at once (Chrome is shared; more collide):
   - `recolector` for outlets' own sites (web search and fetch).
   - `navegador` (Claude in Chrome, logged in) for Facebook pages, groups and comment threads (SIAPA Guadalajara, outlets' posts, neighbourhood pages), X Latest and replies to @SIAPAGDL, TikTok and YouTube. Web search doesn't reach Facebook.
   - Each gets `references/busqueda.md`, its slice, the since-date and an output file in the scratchpad.
   - For a link Ricardo sends, do it yourself in Chrome by the same brief: the post, every comment, then the linked article.
3. Merge the agents' files, drop items already in the file (numeric ids, not pfbid URLs) and items with no colonia, and split the rest into sets of about 15 by thread.
4. Verify: one `navegador` per set with `references/verificacion.md`. Then check by script that every quote is a substring of its capture (any miss is dropped or re-read), and fetch news articles yourself (`curl` the article HTML; a site that blocks scripts is read in Chrome). Read the doubtful keys and dates yourself before deciding.
5. Build the entries in a JSON file:
   - Comments: `quien` "", `en` {quien, url, eco}, `url` = `en.url?comment_id=<id>`; reel or video parents need `video: true`.
   - Names as the file already has them (`python3 pipelines/publicaciones.py q quien~<name>`); a new page goes in `PAGINAS` after reading its About.
   - TikTok and YouTube links are `red: web`, `video: true`.
   - `regreso` only with a date the source gives; an undated «sí llegó» stays out.
   - One entry per neighbour's words per colonia (the checker refuses repeats).
   - Move `actualizado` to today and add today to `busquedas` when a `fecha` is newer.
   - Dry-run first: `python3 pipelines/publicaciones.py add FILE --data <copy>`, then add for real.
6. Previews: run `--imagenes`, then `--capturas`.
   - A YouTube link takes `i.ytimg.com/vi/<id>/hqdefault.jpg` through `sips`.
   - A site that blocks scripts takes the image from its own Facebook post of the same story, saved under the article's hash.
   - Text-only posts have none; say so.
   - Set `vista=null` on logos and stock images and delete the file.
7. /fotos: `python3 pipelines/fotos.py --pendientes`; look at every listed image and tag it in `pipelines/fotos_temas.json` (`temas`: protesta, sin-agua or calidad; `carteles` for a readable sign; `fuera` for official cards, interviews, maps, named people and duplicates of a scene); move `revisado` to today.
8. Regenerate: `fotos.py`, `videos.py` and `simple_page.py`; if `fotos.py` changed the landing wall, also `python3 experiments/historias/build.py --force`.
9. Run `scripts/check.sh --quick`; for a code change, also an `auditor` on the diff. Save the agents' files and the build script under `research/social-evidence/<date>/` with a README of what was dropped and why.
10. Report: what was added (colonias, days, returns), what was dropped and why, what wasn't reachable. Commit with the soporte@aguagdl.com author; push only when Ricardo says so, then `scripts/live.sh`.
