---
paths:
  - "experiments/**"
---

# experiments/ (not deployed)

- Retired design variants 301 to /reportes or / (`web/_redirects`): /reportes' /r2…/r9, /c1…/c8 and /d1…/d5, and the landing's /h1…/h5, /m1…/m5 and /portada-1…/portada-10. Their pages and two builders (experiments/reportes/videos.py, which is not `pipelines/videos.py`, and experiments/portada-fotos/build.py) are only in git history. Don't regenerate them. The landing's photo wall in `web/index.html` is written by `pipelines/fotos.py`.
- `experiments/reportes/colonia.py` refuses to run without `--force`: its base, `reportes-before-c3.html`, is older than production. `web/reportes.html` is the only source of /reportes; edit it directly. `status_test.mjs` tests its helpers.
- `experiments/landing/` keeps earlier landings. `movil.py` and `historias.py` built /m1…/m5 and /h1…/h5; `web/index.html` was derived from /h2 and is now edited directly. `variantes.py` rewrites the dropped fourth round (/v11…/v15) as it stands. All three write straight into `web/` (public, deployed on push), so all three refuse to run without `--force`.
- `experiments/pipas/build.py` writes the noindex /pipas variants (3 Nov 2026), /pipas-v1 «Por municipio», /pipas-v2 «Paso a paso», /pipas-v3 «Directorio», /pipas-v4 «Botones grandes», /pipas-v5 «Guía completa», and their index /pipas-variantes, straight into `web/`, reusing `web/pipas.html`'s style, header and footer. Their copy and sources live in the script; edit it and rerun. Out of the sitemap. Retire them like the others once one is ported to `web/pipas.html`.
- The /pipas variants also map the water points from `web/cisternas.json` (`pipelines/cisternas.py`, see `.claude/rules/pipelines.md`).
- `experiments/historias/build.py --force` writes ten noindex «historias» variants (5 Nov 2026), /historias-1 … /historias-10: /fotos' photos as stories by colonia (a story viewer with progress bars, autoplay, hold to pause, swipe). 1–5 put them in the map: their landing frame loads /historias-mapa-N, a copy of `web/reportes.html` with two hooks (`window.__mapa`, `window.__select`) and the idea added (bubbles, photos in the colonia card, a guided tour, a strip, pinned polaroids); 6–10 put them on the landing (in the headline, a sticky bar, by municipio, by day, in «¿Y en tu colonia?»). Out of the sitemap. Rebuild after editing `web/index.html` or `web/reportes.html` (a moved anchor fails the build); retire them like the others once one is ported.
