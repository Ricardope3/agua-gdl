---
name: mapas
description: Build a new feature on, or fix and improve, Agua GDL's maps (/reportes, /avisos, /mapa and the landing's frame), ship it live and keep every copy of the map in step.
disable-model-invocation: true
---

Arguments: the change or the bug, with Ricardo's screenshot if he sent one.

1. Read `.claude/rules/web.md` (the /reportes, /avisos, `mapa.js` paragraphs) and `.claude/rules/vetos.md`: no auto-selected colonia, ask before touching the landing's auto-scroll, keep the shared look. Work in a worktree off `origin/main`; another session may share it, so `git status --porcelain` before editing.
2. Find the code with `grep -n 'SECTION:' web/reportes.html` (or `avisos.html`), then read that section whole. Badges and donuts: «markers: badges and donuts» (`drawMarkers`, `dotOf`, `spanPx`); opening and closing a colonia: «selection and surrounding tiles» (`select`, `openKey`, `openZoom`). Code all three maps share goes in `web/mapa.js`, called `if (M.…)`.
3. For a bug, find the commit that brought it in (`git log -p -S'<name>' -- web/reportes.html`). Fix only that, and grep every name a commit deleted: dd30a2e6 dropped `quien` while the desktop panel still called it.
4. Sizes on the map are in screen pixels and change with zoom, colonia size and publication count. Test a small colonia, a large one, zooming out and the phone width; scale a badge's parts with the badge, and keep the normal look unless the small case needs a change («only make them small for small numbers»).
5. Preview: `node scripts/dev-server.mjs --port 7140`, open `/reportes?q=<COLONIA>&m=<Municipio>` in the built-in browser at 1300×850 and the mobile preset. A scripted `.click()` is unreliable there (the zoom buttons and the open badge's story ignored it on 5 Nov): use the mouse wheel and real clicks, or dispatch pointerdown, mousedown, pointerup, mouseup and click. Local `publicaciones.json` can be older than production: if the colonia in his screenshot has no badge locally, test one that does and say so. Then `node scripts/shot.mjs /reportes /avisos /mapa / --base http://localhost:7140 --strict`.
6. Copies: `experiments/historias/build.py --force` rebuilds `web/historias-*.html` and `web/historias-mapa-*.html` from `reportes.html` and `index.html`; rerun it after every map or landing change, or `check_web.mjs` breaks on them. `/reportes-portada` is a rewrite, nothing to copy.
7. Update the matching sentence in `.claude/rules/web.md` in the same commit (`check_docs.py` wants tracked paths). A rejected look gets a dated line in `vetos.md`.
8. Push only on a passing check and only your own commits: `if scripts/check.sh --quick; then git log --format='%h %an %s' origin/main..HEAD; git push origin HEAD:main; fi`. Never `check.sh | tail` before a push. A commit from another session in that log means ask first.
9. Wait for the deploy (`curl -s https://aguagdl.com/reportes | grep -c '<new code>'`), then tell Ricardo what changed, the commit, what you checked in the browser and what you only checked on the server.
