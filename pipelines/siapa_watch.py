"""Check SIAPA's rotation sources against the baseline in siapa_sources.json.

Usage: python siapa_watch.py [--update] [siapa_sources.json]

Prints a Markdown report. The KML is also converted with siapa_zonas.py and
compared with api/data/zonas.geojson. Writes changed=true|false and a
fingerprint of the live hashes to $GITHUB_OUTPUT when it's set. Exits 1 only
when a source can't be fetched. --update rewrites the baseline with what's
live now and drops the comment of every source that changed.

SIAPA's CDN caches each file for about a day (query strings don't bypass it),
so a change can take that long to show up here.
"""

import hashlib
import http.client
import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import siapa_zonas  # noqa: E402

GEOJSON = HERE.parent / "api" / "data" / "zonas.geojson"
KML = "zonas.kml"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
TIMEOUT = 60
RETRY_DELAY = 20
GDL = timezone(timedelta(hours=-6))
HINTS = {
    "index.html": "Compara los días y el texto de la página con `api/data/rotation.json`.",
    "calendario.webp": "Compara el calendario con `api/data/rotation.json`.",
    "colonias_siapa.pdf": "Revisa que el PDF nuevo esté completo antes de regenerar `api/data/colonias.json` con `pipelines/siapa_colonias.py`.",
    KML: "Regenera las zonas: `curl -sL '{url}' -o zonas.kml && python3 pipelines/siapa_zonas.py zonas.kml api/data/zonas.geojson` y revisa el diff.",
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read(), r.headers.get("Last-Modified")
        except (OSError, http.client.HTTPException) as e:
            if attempt == 2:
                raise
            print(f"{url}: {e}; retrying in {RETRY_DELAY}s", file=sys.stderr)
            time.sleep(RETRY_DELAY)


def short(sha):
    return f"`{sha[:12]}`" if sha else "—"


def zones_report(kml):
    try:
        live = siapa_zonas.convert(kml)
    except Exception as e:
        return f"**La conversión del KML falló:** {e}"
    with open(GEOJSON, encoding="utf-8") as f:
        repo = json.load(f)

    def count(fc):
        return f"{len(fc['features'])} zonas, {sum(len(f['geometry']['coordinates']) for f in fc['features'])} polígonos"

    if live == repo:
        return f"El KML convertido es igual a `api/data/zonas.geojson` ({count(live)})."
    old = {f["properties"]["zona"]: f["geometry"] for f in repo["features"]}
    new = {f["properties"]["zona"]: f["geometry"] for f in live["features"]}
    diff = sorted(z for z in old.keys() | new.keys() if old.get(z) != new.get(z))
    return (
        f"**El KML convertido difiere de `api/data/zonas.geojson`.** "
        f"KML: {count(live)}; repo: {count(repo)}. Zonas distintas: {', '.join(diff)}."
    )


def main(args):
    update = "--update" in args
    paths = [a for a in args if a != "--update"]
    path = Path(paths[0]) if paths else HERE / "siapa_sources.json"
    with open(path, encoding="utf-8") as f:
        sources = json.load(f)

    rows, changed, errors, live, zones = [], [], [], {}, None
    for name, s in sources.items():
        link = f"[{name}]({s['url']})"
        try:
            body, modified = fetch(s["url"])
        except Exception as e:
            errors.append(name)
            rows.append(f"| {link} | **error:** {e} | | | {short(s.get('sha256'))} |")
            continue
        sha = hashlib.sha256(body).hexdigest()
        live[name] = {"sha256": sha, "bytes": len(body), "last_modified": modified}
        if name == KML:
            zones = zones_report(body)
        old_lm = s.get("last_modified")
        lm = (modified or "—") if modified == old_lm else f"{old_lm or '—'} → {modified or '—'}"
        if sha == s.get("sha256"):
            rows.append(f"| {link} | sin cambios | {len(body):,} B | {lm} | {short(sha)} |")
            continue
        changed.append(name)
        status = "**cambió**" if s.get("sha256") else "**nueva**"
        size = f"{s['bytes']:,} → {len(body):,} B" if s.get("bytes", len(body)) != len(body) else f"{len(body):,} B"
        rows.append(f"| {link} | {status} | {size} | {lm} | {short(s.get('sha256'))} → {short(sha)} |")

    now = datetime.now(GDL).strftime("%Y-%m-%d %H:%M")
    out = [
        "## Fuentes del SIAPA",
        "",
        f"Revisado el {now} (hora de Guadalajara) contra `{os.path.relpath(path, HERE.parent)}`.",
        "",
        "| Fuente | Estado | Tamaño | Last-Modified | SHA-256 |",
        "|---|---|---|---|---|",
        *rows,
    ]
    if zones:
        out += ["", "### Zonas", "", zones]
    notes = [f"- `{n}`: {sources[n]['comment']}" for n in changed if sources[n].get("comment")]
    if notes:
        out += ["", "### Notas de la línea base", "", *notes]
    if changed:
        out += ["", "### Qué hacer", ""]
        out += [f"- `{n}`: {HINTS[n].format(url=sources[n]['url'])}" for n in changed if n in HINTS]
        out += [
            "- Cuando termines, actualiza la línea base y haz commit:",
            "  `python3 pipelines/siapa_watch.py --update && git commit -m 'Update the SIAPA baseline' pipelines/siapa_sources.json`",
        ]
    fingerprint = hashlib.sha256(json.dumps({n: v["sha256"] for n, v in live.items()}).encode()).hexdigest()[:16]
    out += ["", f"<!-- siapa-watch {fingerprint} -->"]
    print("\n".join(out))

    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write(f"changed={'true' if changed else 'false'}\nfingerprint={fingerprint}\n")
    if errors:
        sys.exit(f"siapa_watch: could not fetch {', '.join(errors)}")
    if update:
        for name, v in live.items():
            if v["sha256"] != sources[name].get("sha256"):
                sources[name].pop("comment", None)
            sources[name].update(v)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(sources, f, ensure_ascii=False, indent=1)
            f.write("\n")
        print(f"updated {path}", file=sys.stderr)


if __name__ == "__main__":
    main(sys.argv[1:])
