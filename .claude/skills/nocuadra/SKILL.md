---
name: nocuadra
description: Build or iterate on Agua GDL's No cuadra pages (/nocuadra, /zapopan, /tlajomulco and the noindex /nocuadra-pN prototypes) — what a government announced or claimed set against its own documents, told as an animated scrolling story. Use when Ricardo asks for a new No cuadra version, a new municipio, a new contradiction, or changes to how these pages look or move.
---

Arguments: what to build or change, and which page or prototype (Ricardo names them by URL).

**Read first**
1. `.claude/rules/web.md` (the No cuadra paragraph), `.claude/rules/evidence.md`, `docs/EDITORIAL.md`, `.claude/rules/vetos.md`.
2. The live copy is the checked copy: `web/tlajomulco.html` and `web/zapopan.html`. A prototype reuses their wording; it never writes a figure they don't have.

**What the page says**
- **Tlajomulco first, always**, then Zapopan, then the municipios still waiting (`.municipios li.pendiente`).
- Each municipio leads with its sharpest contradiction, spelled out: both sides quoted as written, each with oficio and PDF page, then one «Por qué choca» line saying why both can't stand (the `.choque` rows of /nocuadra-p1). Blunt but never «mintieron», «miente» or «engañó» (veto, 25 Nov 2026): the documents show the contradiction, not intent.
- Tlajomulco: DG-135/2026 (ten points, seven photographed, ammonia at Planta 1) against DAPIH/0331-01/2026 («no existen descargas»), the 10 March boletín and DTRC/1740/2026 (no answer to the SIAPA).
- Zapopan: 45 pipas vs 34 (0150), 100 cisternas vs 49 (0876), hospitals «Sin atenciones registradas» (0148), «materializar» (7939), and **the 9,828 «Falta de agua» reports** from Cercanía Ciudadana (0878, folio 140292426004981; every one has the SIAPA as dependencia) with their map. It's Zapopan's list, not the SIAPA's: say so.
- Readings of a chart are «nuestra lectura» (pipas, ammonia). «Un reporte no es una casa». A colonia without reports is outlined, never shown as having water.

**How it moves** (Ricardo, 25 Nov 2026: he liked /nocuadra-p3's scroll and /nocuadra-p9's animations)
- Default format: the scrolling story. `.relato` > sticky `.escena` of `.capa[data-c]` layers beside `ol.pasos` of `li.paso[data-c] > .tarjeta`, driven by `NC.relato(root, { capas, alPaso, progreso })` in `web/nocuadra-lab.js`, styled by `web/nocuadra-lab.css`. One step, one fact, one source line. Without JS the layers fall into the page in order.
- Animate units, not decoration. Every announced unit is drawn and the documented ones fill in: `NC.matriz` (a circle per pipa per day), `NC.gotas` / `NC.cuadros` (100 cisternas, 49 filled), `NC.vasos` (a glass per 0.5 mg/L), `NC.cuenta` (a figure counts up). Charts: `NC.seriePipas`, `NC.serieAmoniaco` (hover, keys, screen-reader table). Maps: `NC.mapa`, `NC.marcaPunto`, `NC.cisternas`, `NC.mapaReportes`.
- Each animation plays when its layer shows or it comes into view, replays on return, shows its final state at once with reduced motion (`NC.quieto()`), and fills at once if the reader jumped past (`NC.alVer`'s `pasado`): a figure never sits at zero or empty. No infinite loops, no stamps, tilts or scaling entrances (units fade in place); a map pin's rotated shape is geometry, not motion.

**Look** (unslop, polish mode on the real brand)
- Direction: exacto, documental, sin rodeos; the world is the transparency file — oficios, «Recibido» stamps, highlighter, municipal maps, Talavera blue. The moments are the highlighted document crop and the chart or map in the scene; the signature is «Resaltado de Agua GDL» and the double rule.
- Reuse Talavera pieces (`.button`, `.duo`, `.contador`, `.documento`, `.keys`, double rules, italic serif headings); no shadows on cards or paper (hairlines instead; `nocuadra-lab.css` flattens `.hoja`), no one-off colours, spacing on a 4 px grid, no trailing period on headline-sized lines, no emoji or glyph icons.

**Build and check**
1. Prototypes: `experiments/nocuadra/gen.py` writes web/nocuadra-p1.html to p10.html from the fragments p1.html to p10.html beside it (p0.html is the index /nocuadra-propuestas). First line `<!-- titulo: X | mapa -->` (`| mapa` loads Leaflet and `mapa.js`). `{{block}}` placeholders pull checked blocks from the live pages (`--blocks` lists them; `{{doc:ID}}` is any `documentos.py` card). Pages are noindex and out of the sitemap. Each page gets the sticky `.versiones` row linking every version (from the fragments' titles); anything sticky or full-height below it accounts for `--barra-v`.
2. Data in `nocuadra-lab.js` (`PIPAS`, `AMONIACO`, `PUNTOS`) are copies of /zapopan's and /tlajomulco's: change those first.
3. `npm run dev`, then `node scripts/shot.mjs --strict /nocuadra-p3` (any prototype) (390 and 1300 px) and scroll every step in the browser: each layer shows, maps draw, counts finish.
4. `scripts/check.sh --quick`. Multi-page change: an `auditor` (code, layout, a11y) and a `verificador` (every figure and quote against the PDFs) before committing.
5. Commit by path (`git add web/nocuadra-p*.html web/nocuadra-lab.* experiments/nocuadra/…`), never the other sessions' untracked files; push; give Ricardo the links. Don't confirm live unless he asks.

**Porting a chosen prototype to /nocuadra**: copy its main and script into `web/nocuadra.html` (keep canonical and og:url, no noindex), move needed CSS from `nocuadra-lab.css` into `nocuadra.css`, run `pipelines/sitemap.py`, 301 retired prototypes in `web/_redirects`, update the web.md No cuadra paragraph, and fold what you learned back into this skill.
