---
name: mapas
description: Build a new feature on, or fix and improve, Agua GDL's maps (/reportes, /avisos, /mapa and the landing's frame), from proposal to live, keeping every copy of the map in step.
disable-model-invocation: true
---

Arguments: the feature or the bug, with Ricardo's screenshot if he sent one.

**Before you touch code**
1. Read `.claude/rules/web.md` (the /reportes, /avisos and `mapa.js` paragraphs), `.claude/rules/evidence.md` and `.claude/rules/vetos.md`. A map feature must still hold the evidence rules: silence never means the water came back, no private person's name or close face, a source's claim stays its claim, no claim of representativeness, every tile or label links its source.
2. Work in a worktree off `origin/main`. Other sessions may share it: `git status --porcelain` before every edit and commit.
3. A new feature or a new look: say in two or three lines what you'll build and where it shows, unless he already described it. If he asks for options, build them as noindex variant pages with a switcher bar (as `experiments/historias/build.py` does), never in the live page; once he picks one, port it, delete the rest and 301 them in `web/_redirects`.

**Building**
4. `grep -n 'SECTION:' web/reportes.html` (or `avisos.html`), then read the whole section you change. Code more than one map uses goes in `web/mapa.js`, and pages call it `if (M.…)`. For a bug, find the commit that caused it (`git log -p -S'<name>' -- web/reportes.html`), fix only that, and grep every name that commit deleted or renamed for callers left behind.
5. Map sizes are screen pixels that change with zoom, colonia size and publication count. Scale a marker's parts with the marker, cap anything that could cover a small colonia's outline, and keep the existing look for the common case; change only what the edge case needs.
6. Images on the map are local copies (`web/fuentes/`, `web/img/`), never loaded from Facebook, X or outlets. A new external load needs the CSP in `web/_headers` and a line in the privacy notice: ask first. Respect `prefers-reduced-motion` and style dark mode only with `@media (prefers-color-scheme: dark)`.
7. A pure helper (a size or status rule) gets a case in `experiments/reportes/status_test.mjs`, which pulls helpers out of `reportes.html` by name.

**Checking**
8. `node scripts/dev-server.mjs --port 7140`; in the built-in browser open `/reportes?q=<COLONIA>&m=<Municipio>` at 1300×850 and at the mobile preset, light and dark. Cover a small colonia, a large one, zooming out with the wheel, and opening and closing. A scripted `.click()` is unreliable on Leaflet markers and controls: use real clicks and wheel, or dispatch the pointer and mouse events. Local data can be older than production: if his colonia has no marker locally, test one that does and say so.
9. `node scripts/shot.mjs /reportes /avisos /mapa / --base http://localhost:7140 --strict` (the landing frames the map). Then stop the server and reset the browser's size.
10. `python3 experiments/historias/build.py --force` rebuilds the `web/historias-*` copies of `reportes.html` and `index.html`; rerun it after every map or landing change, or `check_web.mjs` fails on them.
11. In the same commit, update the sentence in `.claude/rules/web.md` that describes what you changed; a look he rejected gets a dated line in `vetos.md`.

**Shipping**
12. `scripts/check.sh --quick` must pass (read its exit code, never `| tail`). Commit as soporte@aguagdl.com.
13. Push only if Ricardo asked for it to go live in this conversation. Before pushing, `git fetch origin && git log --format='%h %s' origin/main..HEAD` and compare the hashes with the commits you made: every session commits as Agua GDL, so the author can't tell them apart. If one isn't yours, ask him first. Then `git push origin HEAD:main`.
14. Wait for the deploy (`curl -s https://aguagdl.com/reportes | grep -c '<new code>'`). Report the commit, what you checked in the browser, and what you only confirmed on the server.
