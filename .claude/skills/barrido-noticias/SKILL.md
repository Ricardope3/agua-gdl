---
name: barrido-noticias
description: Find and add new reports of colonias without water (or water returning) to Agua GDL's /reportes and /fotos — a sweep since a date across outlets, Facebook pages and comment threads, X, TikTok and YouTube, or a single post, reel or article Ricardo sends (a facebook.com/share, x.com, tiktok.com, youtube.com or news link, with or without words). Use it whenever Ricardo asks for new reports, sends such a link, or says «busca más reportes», «agrega los comentarios» or «mira este video».
---

Arguments: the since-date (default: the latest date in `busquedas`), optional outlets, pages or colonias to focus on, or links Ricardo sent.

## Before

- Read `.claude/rules/evidence.md`, `docs/GLOSARIO.md`, `.claude/rules/vetos.md` and `references/busqueda.md`.
- `git status --porcelain` and `git pull --ff-only`: other sessions push to `main` all day.
- The project agents (`recolector`, `navegador`, `auditor`) load only in a session started in `~/agua-gdl`. Elsewhere use general-purpose agents with the agent file's rules pasted into the prompt, and keep their tools to reading.

## A link Ricardo sends

Do it yourself in Claude in Chrome, by `references/busqueda.md`: the post (canonical URL, counts, `creation_time`), every comment (`references/fb-comentarios.js`), the article it links (curl, or Chrome when the site blocks scripts). What you read yourself in this session needs no second verifier, but quotes are still copied from the captured rows, never retyped. Then go to «Build».

## A sweep

1. Search with at most 5 Chrome agents at once (they share one browser and reset each other's tabs above that) plus any number of `recolector`s:
   - `recolector` for outlets' own sites (web search and fetch).
   - `navegador` for Facebook pages, groups and comment threads (SIAPA Guadalajara, outlets' posts, neighbourhood pages), X Latest and replies to @SIAPAGDL, TikTok and YouTube. Web search doesn't reach Facebook.
   - Each gets `references/busqueda.md`, its slice and the since-date, and answers with JSON in its reply. You write each reply to a file in the scratchpad: the agents can't write, by design. Save it with `python3 -I references/pull_json.py <task output file> <out.json>`, never by retyping.
2. Merge and drop:
   - items already in the file (numeric ids, not pfbid URLs) and items with no colonia key;
   - retellings: an outlet's reel, video or X post of its own article already in the file, or of a story you're adding. A news story retelling a neighbour's post can stay, with `de` naming that post.
   Split the rest into sets of about 15 by thread.
3. Verify:
   - Facebook and TikTok: one `navegador` per set with `references/verificacion.md`, at most 5 at once as in step 1. `pull_json.py` checks every quote against its capture; drop or re-read any miss.
   - X: no browser needed. X's public embed endpoint (`token()` in `pipelines/publicaciones.py`, as `--eco` uses it) returns each status's text, time, likes, replies and the post it answers. Check quotes and dates against it by script. A reply whose parent returns nothing can't meet the threshold: drop it.
   - News: fetch the articles yourself.
4. Judge: `navegador` reports what the page shows; the colonia key, `dias`, `regreso` and whether a quote supports them are judgement. Make those calls yourself and send any you're unsure of, with the capture, to `verificador`.

## Build

1. Write the entries to a JSON file:
   - Facebook and TikTok comments: `quien` "", `en` {quien, url, eco} (the parent's counts), `url` = `en.url?comment_id=<id>`; reel or video parents need `video: true`. An X reply links its own status URL, with `en` the post it answers.
   - Keep only the schema's fields (`python3 pipelines/publicaciones.py schema`): drop the agents' `comment_id`, `parent_*`, `captura` and `nota`. `dias` runs 1 to 120.
   - Names as the file already has them (`python3 pipelines/publicaciones.py q quien~<name>`); a new page goes in `PAGINAS` after reading its About.
   - TikTok and YouTube links are `red: web`, `video: true`.
   - A date is the Guadalajara day of the post or comment; `regreso` only with a day the source gives.
   - Every entry from one thread is fine (each comment is its own source), but one neighbour's same words count once per colonia.
2. Always add today to `busquedas` (even when nothing was found, since the next sweep starts from it) and move `actualizado` to today: both are top-level fields, edited by hand. Dry-run on a copy (`add FILE --data <copy>`), fix what the checker says, then add for real.
3. Previews: `--imagenes`, `--videos` (marks the X posts that carry a video), then `--capturas`.
   - A YouTube link takes `i.ytimg.com/vi/<id>/hqdefault.jpg` through `sips`.
   - A site that blocks scripts takes the image from its own Facebook post of the same story, saved under the article's hash.
   - Text-only posts have none: say so.
   - Look at each new preview (an HTML grid of them screenshotted with headless Chrome shows all at once); set `vista=null` on logos, group cover images and stock images and delete the file.
   - Finish every `vista` change before `--capturas`. It runs over 10 minutes (run it in the background) and writes `publicaciones.json` only at the end, from the copy it loaded: a `set` made meanwhile is overwritten, or makes that write fail and loses the captures (6 Nov).
4. /fotos: `python3 pipelines/fotos.py --pendientes`; look at every listed image (mostly the previews you just looked at: one grid serves both) and tag it in `pipelines/fotos_temas.json` (`temas`: protesta, sin-agua or calidad; `carteles` for a readable sign; `fuera` for official cards, interviews, maps, named people and duplicates of a scene); move `revisado` to today.
5. Regenerate: `python3 pipelines/fotos.py`, `python3 pipelines/videos.py`, `python3 pipelines/simple_page.py`. The first two have no `--help`: they ignore unknown flags, so `--help` runs them and writes. New `carteles` replace small tiles on the landing wall: then also run `python3 experiments/historias/build.py --force`, whose pages use the wall's copies.
6. `scripts/check.sh --quick`; for a code change, also an `auditor` on the diff.
7. Save the agents' JSON and the build script under `research/social-evidence/<date>/`, with a README of what was dropped and why. Authors are «[autor]» there too.

## Finish

- Commit locally by path (`git commit <paths>`: other sessions leave changes staged), then check the author is soporte@aguagdl.com (`git log -1 --format=%ae`). A commit publishes nothing. Tell Ricardo what was added (colonias, days, returns), what was dropped and why, what wasn't reachable, and every judgement call (a municipio taken from the thread, a rounded count).
- Push only when he says so: `git fetch`, `git rebase origin/main`, regenerate step 5 again if the rebase brought new photos or posts, `scripts/check.sh --quick`, push, then `scripts/live.sh`.
