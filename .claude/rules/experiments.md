---
paths:
  - "experiments/**"
---

# experiments/ (not deployed)

- The design variants of /reportes (/r2…/r9, /c1…/c8, /d1…/d5) and of the landing (/h1…/h5, /m1…/m5) were retired on 2 Nov 2026 (/c6…/c8 on 3 Nov) and 301 to /reportes or / (`web/_redirects`); git history has them. Don't regenerate them.
- `experiments/reportes/colonia.py` refuses to run without `--force`: its base, `reportes-before-c3.html`, is older than production. `web/reportes.html` is the only source of /reportes; edit it directly. `status_test.mjs` tests its helpers.
- /c7 «Historias de video» (with /d1's desktop card and panel) was ported into `web/reportes.html` on 3 Nov 2026; `videos.py`, which wrote /c6…/c8, is in git history.
- `experiments/landing/` keeps earlier landings. `movil.py` and `historias.py` built /m1…/m5 and /h1…/h5; `web/index.html` was derived from /h2 and is now edited directly. `variantes.py` rewrites the dropped fourth round (/v11…/v15) as it stands. All three write straight into `web/` (public, deployed on push), so all three refuse to run without `--force`.
- `experiments/pipas/build.py` writes the noindex /pipas variants (3 Nov 2026), /pipas-v1 «Por municipio», /pipas-v2 «Paso a paso», /pipas-v3 «Directorio», /pipas-v4 «Botones grandes», /pipas-v5 «Guía completa», and their index /pipas-variantes, straight into `web/`, reusing `web/pipas.html`'s style, header and footer. Their copy and sources live in the script; edit it and rerun. Out of the sitemap. Retire them like the others once one is ported to `web/pipas.html`.
- The /pipas variants also map the water points from `web/cisternas.json` (`pipelines/cisternas.py`, see `.claude/rules/pipelines.md`).
- The ten landing photo variants /portada-1…/portada-10 (5 Nov 2026) were retired the same day: Ricardo picked /portada-3 «Portada a sangre», now in `web/index.html` (its photo wall is written by `pipelines/fotos.py`). They 301 to /; their builder, experiments/portada-fotos/build.py, is in git history.
