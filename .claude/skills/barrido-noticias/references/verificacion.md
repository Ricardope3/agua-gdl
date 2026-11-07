# Brief: verifying candidates

You re-read candidates another agent found. Their quotes, counts, dates and keys are claims. Read `busqueda.md` (same folder) for how to read each network; this file says what to produce.

For every candidate:

1. Open the parent (or the item) yourself and read its reactions, comments and shares (on a reel, the reel you opened).
2. Find the comment by its id (sort «All comments», load until found). On X open the status; on TikTok find the cid.
3. Write a capture: the comment's raw text exactly as the page shows it, author replaced by «[autor]», its age string and the id read from its link.
4. Build the entry in `publicaciones.json`'s shape (`python3 pipelines/publicaciones.py schema`): the quote must be a substring of the capture (an omission marked «[…]» is fine), `dias` by the rules in `busqueda.md`, the colonia key checked in `api/data/colonias_mapa.json`.
5. Reject what doesn't hold: quote not on the page, parent under the threshold, no colonia, a future cut, a person as `en.quien`, words already filed for that colonia.

Output: `verified-<set>.json` (entries plus `comment_id`, `parent_eco` and `captura` {texto, edad, leido}) and `rejected-<set>.json` (one line each with the reason), in the scratchpad. Final reply ≤6 lines.
