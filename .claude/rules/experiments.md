---
paths:
  - "experiments/**"
  - "web/c6.html"
  - "web/c7.html"
  - "web/c8.html"
---

# experiments/ (not deployed) and the remaining variants

- The design variants of /reportes (/r2…/r9, /c1…/c5, /d1…/d5) and of the landing (/h1…/h5, /m1…/m5) were retired on 2 Nov 2026 and 301 to /reportes or / (`web/_redirects`); git history has them. Don't regenerate them.
- `experiments/reportes/colonia.py` refuses to run without `--force`: its base, `reportes-before-c3.html`, is older than production. `web/reportes.html` is the only source of /reportes; edit it directly. `status_test.mjs` tests its helpers.
- `experiments/reportes/videos.py` writes the noindex /c6 «Videos verticales», /c7 «Historias de video» and /c8 «Reel compacto», on both phones and desktop, from `reportes-before-c3.html` through `colonia.build()`. Every colonia with a direct video gets the corresponding launcher; comments on another post's video do not count, duplicate URLs are removed, and visual protest videos come first. The vertical viewer has local thumbnails, source links, keyboard/focus handling and a final report action; only YouTube plays inline, on demand, through `youtube-nocookie.com`. Production /reportes has the protest-first evidence order but not this video viewer; port it to `web/reportes.html` rather than regenerating from the stale base.
- `experiments/landing/` keeps earlier landings. `movil.py` and `historias.py` built /m1…/m5 and /h1…/h5; `web/index.html` was derived from /h2 and is now edited directly. `variantes.py` rewrites the dropped fourth round (/v11…/v15) as it stands. None of these should be run without a reason.
