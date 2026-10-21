# Landing-page experiments

Unpublished variants of `web/index.html` (only `web/` is deployed). `v5` became `web/index.html` on 16 Oct 2026; the landing before it is `index-before-v5.html`.

`gen.py` generated all five from `index.html` (`python3 -I experiments/landing/gen.py web`); it writes every variant into `web/`, so move v1–v4 back here after running it.

Second round, 21 Oct 2026: `variantes.py` writes `web/v1.html` … `web/v5.html`, published (noindex) at /v1 … /v5, from the pieces of the current `index.html`, to compare ordering, placement and style: «Promesa contra realidad», «Acciones primero», «Cartel», «Datos en vivo» and «Lo esencial». Run it from the repo root (`python3 -I experiments/landing/variantes.py`) after changing a variant or the landing. Once one is chosen, make it `index.html` and drop the rest from `web/`.
