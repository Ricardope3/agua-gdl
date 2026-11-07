# Brief: verifying candidates

You re-read candidates another agent found. Their quotes, counts, dates and keys are claims. Read `busqueda.md` (same folder) for how to read each network and the rules for quotes, `dias`, keys and dates; this file says what to produce. Your output is your final reply.

For every candidate:

1. Open the parent (or the item) yourself and read its reactions, comments and shares (on a reel, the reel you opened).
2. Find the comment by its id (sort «All comments», load until found). On X open the status; on TikTok find the cid.
3. Capture the comment's raw text exactly as the page shows it, author replaced by «[autor]», with its age string and the id read from its link.
4. Build the entry in `publicaciones.json`'s shape, every field even when unchanged (not only the id and capture): the quote must be a substring of the capture (an omission marked «[…]» is fine).
5. Reject what doesn't hold: quote not on the page, parent under the threshold, no colonia, a future cut, a person as `en.quien`, an ambiguous date.

Reply with one ```json block holding one object, `{"verified": [...], "rejected": [...]}`: `verified` holds the entries plus `comment_id`, `parent_eco` and `captura` {texto, edad, leido}; `rejected` holds `{url, reason}`. Mark an omission in a quote «[…]». Then at most 5 lines on what you changed from the claims and what you couldn't open.
