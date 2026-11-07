# Brief: searching for new reports

You gather candidates for /reportes. You never decide what gets published and never edit the repo. Your task names your slice (a network, outlet group or set of pages) and the since-date. Your output is your final reply.

## What counts

- A person or outlet saying a colonia of the Guadalajara metro (Guadalajara, Zapopan, Tlaquepaque, Tonalá, Tlajomulco, El Salto, Juanacatlán, Ixtlahuacán) has no water, N days without water, low or intermittent supply, dirty water, a pipa, a blockade over water, or that water came back.
- Not: schedule questions, future-dated protest flyers, partisan posts without a colonia, «sí hay agua» replies, «Zapopan» alone.
- Window: the since-date to today, by the Guadalajara day.

## Dedupe

- Grep `web/publicaciones.json` for each candidate's NUMERIC ids (post id, reel id, comment_id, group id). Facebook `pfbid…` URLs differ for the same post, so never dedupe on the pfbid string.
- A new comment inside a post already in the file is still a candidate.

## Facebook (Claude in Chrome)

- `facebook.com/share/…` redirects; record the canonical URL after the redirect. If a read fails with «navigated to a different domain», read again.
- Comments: switch the sort to «All comments» / «Todos los comentarios», then use the three blocks in `fb-comentarios.js` (same folder): load everything in the background and poll, extract numeric ids, ages and text, read the rows with `get_page_text`. No comment id, no candidate.
- Counts: reactions, comments and shares of the post you opened (`[aria-label]` «N comments», «N shares»). A reel page also shows the NEXT reel's counts and scrolling auto-advances: re-check the URL after scrolling. Facebook rounds («1.1K»): record 1100 and say it is rounded.
- Dates: the post's `creation_time` in the page HTML is UTC epoch seconds (subtract 6 h for Guadalajara). A comment's age («5 h») counts back from when you read (`new Date()` in the page). An age that could fall on either side of midnight is ambiguous: hover its timestamp for the exact time, or leave the comment out.
- Pages vs people: a page («Página oficial…», a community or news page) can be `en.quien` only once it is in `PAGINAS` in `pipelines/publicaciones.py`; read its About and report the bio and category.
- Stop after 3 failed attempts at the same action and report what you got.

## X, TikTok, YouTube

- X: the Latest tab; a reply links its own status URL and answers a post (`en`). Counts from the aria-labels. A neighbour's own post needs ≥5 reactions and ≥1 reply like any other.
- TikTok: caption, date and counts from the page's `__UNIVERSAL_DATA_FOR_REHYDRATION__`; comment ids (cid) from the `comment/list` network request (`read_network_requests`). A TikTok comment without a cid stays out.
- YouTube: search YouTube itself sorted by date; read `publishDate` and `shortDescription` on the watch page.

## Rules for every candidate

- Quote VERBATIM, typos and accents kept, ≤300 characters, to the end of the clause; cut before insults, slogans or names (a quote may start mid-sentence to leave a name out).
- Never a private person's name: «Cuenta de vecinos», «Cuenta personal en X», «Grupo «…»» (public groups), or the page or outlet name.
- `dias` only for a plain count («15 días», «3 semanas» = 21, «un mes» = 30); null for «casi», «más de», «alrededor de», «aproximadamente», «pasadito de» or a count from a date («desde el lunes»).
- Colonia keys from `api/data/colonias_mapa.json` (`NAME|Municipio|CP`). When a name exists in several municipios:
  - the text names the municipio: use it;
  - the thread is one municipio's (a Tlaquepaque neighbourhood page, a post about one protest) and the name exists there: use it and say so in `nota`;
  - otherwise key null.
- A name not in the map, or a street, gets `colonia_key` null with `lugar` as written; never key a part of a colonia to a neighbouring one.
- A neighbour's comment counts only inside a post with ≥5 reactions and ≥1 comment; record the parent's counts and the date read.
- «Ya llegó» needs the day it came («ayer», «anoche», «a las 3:30»): give `regreso`; with no day, leave it out.

## Output

Reply with a JSON array (at most 20 items, most informative first): `{url, fuente, red, quien, fecha, colonia_key, lugar, cita, dias, bloqueo, parcial, calidad, regreso, video, comment_id, parent_url, parent_eco, eco, nota}`, then one line `no_alcanzado: …`.
