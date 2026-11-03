---
name: barrido-noticias
description: Sweep news and neighbours' posts about colonias without water since a date, verify them and add the ones that hold to web/publicaciones.json.
disable-model-invocation: true
---

Arguments: the since-date (default: the latest date in `busquedas`) and optional outlets or colonias to focus on.

1. Read `.claude/rules/evidence.md`, `docs/GLOSARIO.md` and `.claude/rules/vetos.md`. The project agents load only in a session started in `~/agua-gdl`.
2. Fan out `recolector` agents (one per outlet group or network; at most 8), each told the since-date and to mark URLs already in the file. Never use general-purpose agents for this. Web search doesn't reach Facebook posts, and reaches X only up to a few days back: list those as leads for a logged-in browser instead of expecting finds.
3. Drop duplicates: `python3 pipelines/publicaciones.py q url~<domain/path>` for each candidate.
4. Send every remaining candidate to `verificador`: quote verbatim, date, colonia keying, days stated in the source's own words, person vs page. Keep only "holds".
5. Write each entry to a JSON file and add it with `python3 pipelines/publicaciones.py add entries.json` (it validates before writing); first add today's date to `busquedas` and move `actualizado` to today, or a newer `fecha` fails.
6. Run `--imagenes` and `--capturas`, look at each new preview and set `vista=null` on logos and stock photos (`set INDEX vista=null`, then delete the file). Regenerate `simple_page.py` and `videos.py`.
7. Run `scripts/check.sh --quick`, then an `auditor` on the diff.
8. Report: candidates found, added, rejected and why, and what wasn't reachable (also in the notes' `log/`). Commit only if Ricardo says so.
