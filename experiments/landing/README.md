# Landing-page experiments

Unpublished variants of `web/index.html` (only `web/` is deployed). `v5` became `web/index.html` on 16 Oct 2026; the landing before it is `index-before-v5.html`.

`gen.py` generated all five from `index.html` (`python3 -I experiments/landing/gen.py web`); it writes every variant into `web/`, so move v1–v4 back here after running it.

Second round, 21 Oct 2026: `variantes.py` writes `web/v1.html` … `web/v5.html`, published (noindex) at /v1 … /v5, from the pieces of the current `index.html`, to compare ordering and placement: «Promesa contra realidad», «Acciones primero», «Alerta y cifras» (first «Cartel», a protest poster), «Datos en vivo» and «Lo esencial». Since the same day all five share v1's newspaper style (`STYLE`: serif headlines, quotes and figures, rules in ink) and open with /reportes in a frame (`map_hero`, `EMBED`): v1, v3 and v5 on Ciudad Granja, v2 and v4 on the whole city; `web/_headers` lets the site frame its own pages for it. Run it from the repo root (`python3 -I experiments/landing/variantes.py`) after changing a variant or the landing. Once one is chosen, make it `index.html` and drop the rest from `web/`.
