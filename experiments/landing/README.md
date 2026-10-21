# Landing-page experiments

Unpublished variants of `web/index.html` (only `web/` is deployed). `v5` became `web/index.html` on 16 Oct 2026; the landing before it is `index-before-v5.html`.

`gen.py` generated all five from `index.html` (`python3 -I experiments/landing/gen.py web`); it writes every variant into `web/`, so move v1–v4 back here after running it.

Second round, 21 Oct 2026: `variantes.py` writes `web/v1.html` … `web/v5.html`, published (noindex) at /v1 … /v5, from the pieces of the current `index.html`, to compare ordering and placement: «Promesa contra realidad», «Acciones primero», «Alerta y cifras» (first «Cartel», a protest poster), «Datos en vivo» and «Lo esencial». Later that day all five took v1's newspaper style (serif headlines, quotes and figures, rules in ink) and opened with /reportes in a frame: v1, v3 and v5 on Ciudad Granja, v2 and v4 on the whole city; `web/_headers` lets the site frame its own pages for it. v1 became `web/index.html` the same day (the landing before it is `index-before-v1.html`), and /v1 … /v5 redirect to /; their pages are in git history.

Third round, 21 Oct 2026: `variantes.py` wrote `web/v6.html` … `web/v10.html` from the blocks of the new `index.html`'s `<main>` (found by their class), each trying one idea on it: «Mapa a lo ancho», «Portada», «Mapa con lista», «Tu colonia primero» and «Breve». v6, with v7's one-row menu, became `web/index.html` the same day (the landing before it is `index-before-v6.html`), and /v6 … /v10 redirect to /.

Fourth round, 21 Oct 2026: `variantes.py` now writes `web/v11.html` … `web/v15.html` the same way: «Mapa primero», «Toda la ciudad», «La más publicada», «Mapa con lista» and «Tu colonia primero». Run it from the repo root (`python3 -I experiments/landing/variantes.py`) after changing a variant or the landing. Once one is chosen, make it `index.html` and drop the rest from `web/`.
