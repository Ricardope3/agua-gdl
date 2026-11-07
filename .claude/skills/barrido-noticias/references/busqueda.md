# Brief: searching for new reports

You gather candidates for /reportes. You never decide what gets published and never edit the repo. Your task names your slice (a network, outlet group or set of pages), the since-date, the scratchpad and your output file.

## What counts

- A person or outlet saying a colonia of the Guadalajara metro (Guadalajara, Zapopan, Tlaquepaque, Tonalá, Tlajomulco, El Salto, Juanacatlán, Ixtlahuacán) has no water, N days without water, low or intermittent supply, dirty water, a pipa, a blockade over water, or that water came back.
- Not: schedule questions, future-dated protest flyers, partisan posts without a colonia, «sí hay agua» replies, «Zapopan» alone.
- Window: the since-date to today, by the Guadalajara day.

## Dedupe

- `python3 pipelines/publicaciones.py q url~<id>` for each candidate. Facebook `pfbid…` URLs differ for the same post: search the NUMERIC ids (post id, reel id, comment_id, group id), never the pfbid string.
- A new comment inside a post already in the file is still a candidate.

## Facebook (Claude in Chrome)

- `facebook.com/share/…` redirects; record the canonical URL after the redirect. If a read fails with «navigated to a different domain», read again.
- Set the comment sort to «Todos los comentarios» / «All comments», then load everything: scroll the largest scrollable div inside `[role=dialog]` and click «Ver más comentarios» / «View N replies» until nothing new loads. A long loop must run in the background (`(async()=>{…})()` storing to `window._…`) and be polled: one JS call times out at 45 s.
- Comment id: from the timestamp link `a[href*="comment_id"]`; Facebook base64-encodes it (`atob(id)` → `comment:<post>_<id>`; keep the last part). No comment id, no candidate.
- Reading hundreds of comments: tool output truncates near 1,000 characters, so put the rows in a `<pre>` inside `<main>` and read them with `get_page_text`.
- Counts: read reactions, comments and shares from the post you opened. A reel page also shows the NEXT reel's counts and scrolling auto-advances: re-check the URL after scrolling. Facebook rounds («1.1K»); record the number shown and say it is rounded.
- Dates: the post's `creation_time` in the page HTML is UTC epoch seconds (subtract 6 h for Guadalajara). A comment's age («5 h») counts back from the moment you read (`new Date()` in the page); an age that could fall on either side of midnight is ambiguous: say so.
- Pages vs people: a page («Página oficial…», a community or news page) can be `en.quien` only after it is added to `PAGINAS` in `pipelines/publicaciones.py`; read its About first.

## X, TikTok, YouTube

- X: the Latest tab; a reply links its own status URL and answers a post (`en`). Counts from the aria-labels. A neighbour's own post needs ≥5 reactions and ≥1 reply like any other.
- TikTok: caption, date and counts from the page's `__UNIVERSAL_DATA_FOR_REHYDRATION__`; comment ids (cid) from the `comment/list` network request (`read_network_requests`). A TikTok comment without a cid stays out.
- YouTube: search YouTube itself sorted by date; read `publishDate` and `shortDescription` on the watch page.

## Rules for every candidate

- Quote VERBATIM, typos and accents kept, ≤300 characters, to the end of the clause; cut before insults or names. Never a private person's name: «Cuenta de vecinos», «Cuenta personal en X», «Grupo «…»» (public groups), or the page or outlet name.
- `dias` only for a plain count («15 días», «3 semanas» = 21, «un mes» = 30); null for «casi», «más de», «alrededor de», «aproximadamente» or a count from a date («desde el lunes»).
- Colonia keys from `api/data/colonias_mapa.json` (`NAME|Municipio|CP`). If the name exists in several municipios and neither the text nor the thread settles it, key null and say why.
- A neighbour's comment counts only inside a post with ≥5 reactions and ≥1 comment; record the parent's counts and the date read.

## Output

Write a JSON array to your output file: `{url, fuente, red, quien, fecha, colonia_key, lugar, cita, dias, bloqueo, parcial, calidad, regreso, video, comment_id, parent_url, parent_eco, eco, nota}`. Final reply ≤6 lines: counts, the file, what you couldn't reach.
