"""Check SIAPA's rotation sources against the baseline in siapa_sources.json.

Usage: python siapa_watch.py [--update] [siapa_sources.json]

Prints a Markdown report. SIAPA's map (rotacion-siapa.topo.json, which its page draws since
16 Oct 2026; the old Google My Maps KML and calendar image are commented out there) is compared
with web/colonias_siapa.topo.json, and the cut days in ajustes.php (what SIAPA edits from its
admin panel; its page shows them) with api/data/rotation.json: a difference in either counts
as a change until the repo matches. Writes changed=true|false and a
fingerprint of the live hashes and of any such difference to $GITHUB_OUTPUT
when it's set, so a new difference gets its own comment. Exits 1 only
when a source can't be fetched. --update rewrites the baseline with what's
live now and drops the comment of every source that changed.

SIAPA's CDN caches each file for about a day (query strings don't bypass it),
so a change can take that long to show up here; ajustes.php isn't cached.
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
MAP = HERE.parent / "web" / "colonias_siapa.topo.json"
ROTATION = HERE.parent / "api" / "data" / "rotation.json"
TOPO = "rotacion-siapa.topo.json"
AJUSTES = "ajustes.php"
DAYS = {"lunes": "mon", "martes": "tue", "miercoles": "wed", "jueves": "thu", "viernes": "fri", "sabado": "sat", "domingo": "sun"}
DIAS = {v: k.replace("miercoles", "miércoles").replace("sabado", "sábado") for k, v in DAYS.items()}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
TIMEOUT = 60
MAX_BYTES = 20 * 1024 * 1024
RETRY_DELAY = 20
GDL = timezone(timedelta(hours=-6))
HINTS = {
    "index.html": "Revisa el texto de la página (los días de corte están en `ajustes.php`; el mapa, en `rotacion-siapa.topo.json`).",
    "colonias_siapa.pdf": "Revisa que el PDF nuevo esté completo antes de regenerar `api/data/colonias.json` con `pipelines/siapa_colonias.py`.",
    TOPO: "El SIAPA cambió su mapa. Regenéralo con `python3 pipelines/siapa_mapa.py` (escribe `web/colonias_siapa.topo.json` y su copia en `api/data`, que usa el bot para ubicar zonas) y luego `python3 pipelines/mapa_colonias.py`; revisa el diff.",
    AJUSTES: "El SIAPA cambió días de corte o zonas de colonias desde su panel. Si cambiaron los días, corrige `api/data/rotation.json` (con `checked` y `checked_by`), corre `go run ./cmd/calendars` desde `api/` y avisa a las zonas con `cmd/notify -channel tg`. Si cambiaron colonias, `pipelines/siapa_mapa.py` todavía no aplica esos cambios a mano: revísalos en el mapa del SIAPA.",
}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                body = r.read(MAX_BYTES + 1)
                if len(body) > MAX_BYTES:
                    raise ValueError(f"larger than {MAX_BYTES:,} bytes")
                return body, r.headers.get("Last-Modified")
        except (OSError, http.client.HTTPException) as e:
            if attempt == 2:
                raise
            print(f"{url}: {e}; retrying in {RETRY_DELAY}s", file=sys.stderr)
            time.sleep(RETRY_DELAY)


def code(text, limit=80):
    # Text from the network goes into a GitHub issue: as inline code it can't add
    # Markdown, HTML or @mentions, and without "|" it can't break the table.
    text = " ".join(str(text).split())[:limit].replace("`", "'").replace("|", "/")
    return f"`{text}`"


def short(sha):
    return f"`{sha[:12]}`" if sha else "—"


def map_report(body):
    """SIAPA's map against web/colonias_siapa.topo.json: (text, differs)."""
    try:
        live = json.loads(body)
        with open(MAP, encoding="utf-8") as f:
            repo = json.load(f)
        # Every piece as siapa_mapa.py copies it: a colonia drawn in several pieces can have other
        # zones in each, and the bot looks zones up by piece.
        pieces = lambda topo: [(  # noqa: E731
            (p["n"].strip(), p["m"].strip(), str(p.get("cp", "")).strip()),
            ",".join(str(z) for z in sorted(int(z) for z in str(p.get("z", "")).split(",") if z.strip())),
            g["type"], g["arcs"]) for g in topo["objects"]["colonias"]["geometries"] for p in [g["properties"]]]
        zonas = lambda topo: sorted((int(g["properties"]["z"]), g["type"], g["arcs"]) for g in topo["objects"]["zonas"]["geometries"])  # noqa: E731
        ours, theirs = pieces(repo), pieces(live)
        shapes = (live["arcs"], live["transform"], [p[2:] for p in theirs], zonas(live)) == (
            repo["arcs"], repo["transform"], [p[2:] for p in ours], zonas(repo))
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        return f"**No se pudo leer el mapa del SIAPA:** {code(e, 200)}", True
    old, new = {}, {}
    for found, by_key in ((ours, old), (theirs, new)):
        for key, zones, *_ in found:
            by_key.setdefault(key, []).append(zones)
    added, gone = sorted(new.keys() - old.keys()), sorted(old.keys() - new.keys())
    moved = sorted(k for k in old.keys() & new.keys() if old[k] != new[k])
    if not (added or gone or moved) and shapes:
        return f"El mapa del SIAPA es igual a `web/colonias_siapa.topo.json` ({len(new):,} colonias).", False
    name = lambda k: code(f"{k[0]} ({k[1]})", 60)  # noqa: E731
    zs = lambda v: " + ".join(z or "—" for z in v)  # noqa: E731
    parts = []
    if moved:
        parts.append(f"{len(moved)} con otras zonas, como " + ", ".join(f"{name(k)} {zs(old[k])} → {zs(new[k])}" for k in moved[:5]))
    if added:
        parts.append(f"{len(added)} nuevas, como " + ", ".join(name(k) for k in added[:5]))
    if gone:
        parts.append(f"{len(gone)} quitadas, como " + ", ".join(name(k) for k in gone[:5]))
    if not shapes:
        parts.append("cambiaron contornos o zonas")
    return f"**El mapa del SIAPA difiere de `web/colonias_siapa.topo.json`:** {'; '.join(parts)}.", True


def ajustes_sha(body):
    # A save from the panel that changes nothing only moves "actualizado".
    try:
        data = json.loads(body)
        data.pop("actualizado", None)
        body = json.dumps(data, sort_keys=True, ensure_ascii=False).encode()
    except (ValueError, TypeError, AttributeError):  # not JSON, or not an object: days_report says so
        pass
    return hashlib.sha256(body).hexdigest()


def days_report(body):
    """The cut days SIAPA's page shows against rotation.json: (text, differs)."""
    try:
        data = json.loads(body)
        live = {z: [DAYS[d] for d in v["dias"]] for z, v in data["zonas"].items()}
        moved = len(data.get("colonias") or {})
    except (ValueError, KeyError, TypeError, AttributeError) as e:
        return f"**No se pudieron leer los días de `{AJUSTES}`:** {code(e, 200)}", True
    with open(ROTATION, encoding="utf-8") as f:
        repo = json.load(f)["zones"]
    moved = f" Colonias con la zona cambiada a mano: {moved}." if moved else ""
    diff = sorted(z for z in live.keys() | repo.keys() if sorted(live.get(z, [])) != sorted(repo.get(z, [])))
    if not diff:
        # Manual colonia overrides stay an unresolved repo mismatch until siapa_mapa.py applies
        # them or a reviewer records an explicit exception. Updating the source baseline must not
        # silence them: otherwise residents can keep receiving reminders for the wrong zone.
        return f"Los días de corte de `{AJUSTES}` son iguales a `api/data/rotation.json` en las {len(live)} zonas.{moved}", moved != ""
    names = lambda days: ", ".join(DIAS[d] for d in days) or "ninguno"  # noqa: E731
    parts = [f"zona {z}: SIAPA {names(live.get(z, []))}; rotation.json {names(repo.get(z, []))}" for z in diff]
    return f"**Los días de corte de `{AJUSTES}` difieren de `api/data/rotation.json`:** {'; '.join(parts)}.{moved}", True


def main(args):
    update = "--update" in args
    paths = [a for a in args if a != "--update"]
    path = Path(paths[0]) if paths else HERE / "siapa_sources.json"
    with open(path, encoding="utf-8") as f:
        sources = json.load(f)

    rows, changed, errors, live, mapa, days, mismatch = [], [], [], {}, None, None, {}
    for name, s in sources.items():
        link = f"[{name}]({s['url']})"
        try:
            body, modified = fetch(s["url"])
        except Exception as e:
            errors.append(name)
            rows.append(f"| {link} | **error:** {code(e, 200)} | | | {short(s.get('sha256'))} |")
            continue
        sha = ajustes_sha(body) if name == AJUSTES else hashlib.sha256(body).hexdigest()
        live[name] = {"sha256": sha, "bytes": len(body), "last_modified": modified}
        differs = False
        if name == TOPO:
            mapa, differs = map_report(body)
        if name == AJUSTES:
            days, differs = days_report(body)
        if differs:
            mismatch[name] = mapa if name == TOPO else days
        old_lm = s.get("last_modified")
        lm = (code(modified) if modified else "—") if modified == old_lm else f"{code(old_lm) if old_lm else '—'} → {code(modified) if modified else '—'}"
        if sha == s.get("sha256") and not differs:
            rows.append(f"| {link} | sin cambios | {len(body):,} B | {lm} | {short(sha)} |")
            continue
        changed.append(name)
        status = "**difiere del repo**" if sha == s.get("sha256") else "**cambió**" if s.get("sha256") else "**nueva**"
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
    if mapa:
        out += ["", "### Mapa", "", mapa]
    if days:
        out += ["", "### Días de corte", "", days]
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
    # A state with no difference with the repo hashes the live hashes alone.
    state = {n: v["sha256"] for n, v in live.items()} | {f"{n} vs repo": text for n, text in mismatch.items()}
    fingerprint = hashlib.sha256(json.dumps(state).encode()).hexdigest()[:16]
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
