---
name: barrido-noticias
description: Sweep news and neighbours' posts about colonias without water since a date, verify them and add the ones that hold to web/publicaciones.json.
disable-model-invocation: true
---

Arguments: the since-date (default: the latest date in `busquedas`) and optional outlets or colonias to focus on.

1. Read `.claude/rules/evidence.md`, `docs/GLOSARIO.md` and `.claude/rules/vetos.md`.
2. Fan out `recolector` agents (one per outlet group or network; at most 8), each told the since-date and to mark URLs already in the file. Never use general-purpose agents for this.
3. Drop duplicates: `python3 pipelines/publicaciones.py q url~<domain/path>` for each candidate.
4. Send every remaining candidate to `verificador`: quote verbatim, date, colonia keying, days stated in the source's own words, person vs page. Keep only "holds".
5. Write each entry to a JSON file and add it with `python3 pipelines/publicaciones.py add entries.json` (it validates before writing); add today's date to `busquedas`.
6. Run `scripts/check.sh --quick`, then an `auditor` on the diff.
7. Report: candidates found, added, rejected and why, and what wasn't reachable. Commit only if Ricardo says so.
