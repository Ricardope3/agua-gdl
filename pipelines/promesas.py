"""Promesómetro: validate web/promesas.json and write the cards and the meter in web/promesas.html.

    python3 pipelines/promesas.py            validate and rewrite the generated parts of web/promesas.html
    python3 pipelines/promesas.py --check    same validation; fail if the page is stale. Writes nothing.
    python3 pipelines/promesas.py --drafts --out DIR
        Preview for review: skips the archive check and writes promesas.html to DIR (a copy of web/).

Every source needs an archive.org snapshot in "archive", or "captura": "privada" when archive.org
can't save it and a copy with its SHA-256 is kept in the private notes repo.
"""
import argparse
import datetime
import html
import json
import pathlib
import re
import sys
import unicodedata
import zoneinfo

root = pathlib.Path(__file__).resolve().parent.parent
DATA = root / "web/promesas.json"
PAGE = root / "web/promesas.html"

VERDICTS = {
    "se_cumple": "Se cumple",
    "sin_pruebas": "Sin pruebas",
    "en_riesgo": "En riesgo",
    "incumplida": "Incumplida",
    "se_contradice": "Se contradice con los documentos",
}
ORDER = list(VERDICTS)
STEPS = {"cumplido": "Cumplido", "declarado": "Declarado, sin prueba independiente", "en_disputa": "En disputa", "incumplido": "No se cumplió", "pendiente": "Pendiente"}
NEEDS_EVIDENCE = {"cumplido", "declarado", "en_disputa", "incumplido"}
SECTIONS = {"app": "A. El acueducto (APP)", "gobierno": "B. Los demás compromisos"}
BANNED = re.compile(r"\b(miente|mienten|mintio|mintieron|mintiendo|mentira|mentiras|engana|enganan|enganando|engano|enganaron|traiciono|traicionaron)\b")
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
TODAY = datetime.datetime.now(zoneinfo.ZoneInfo("America/Mexico_City")).date()

errors = []
DRAFTS = False


def fail(msg):
    errors.append(msg)


def plain(s):
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().casefold()


def date(s, where, future_ok=False):
    try:
        d = datetime.date.fromisoformat(s)
    except (TypeError, ValueError):
        fail(f"{where}: bad date {s!r}")
        return None
    if d > TODAY and not future_ok:
        fail(f"{where}: date {s} is in the future")
    return d


def source(src, where):
    if not str(src.get("url", "")).startswith("https://"):
        fail(f"{where}: URL must start with https:// ({src.get('url')!r})")
    if not DRAFTS and not str(src.get("archive") or "").startswith("https://web.archive.org/") and src.get("captura") != "privada":
        fail(f"{where}: {src.get('url')} has no archive.org snapshot (or \"captura\": \"privada\" with a copy in the notes repo)")
    if not src.get("medio"):
        fail(f"{where}: source without medio")
    if src.get("fecha"):
        date(src["fecha"], where)


def strings(node, path=""):
    if isinstance(node, str):
        yield path, node
    elif isinstance(node, dict):
        for k, v in node.items():
            yield from strings(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from strings(v, f"{path}[{i}]")


def is_quote(path, entry, text):
    """Quotes are verbatim and exempt from the wording checks; a title counts when it is the quote itself."""
    if path == "cita" or path.endswith(".cita") or re.search(r"\.citas\[\d+\]\.texto$", path):
        return True
    return path == "titulo" and text.strip("«» ") == entry.get("cita", "").strip()


def validate(data):
    date(data.get("actualizado"), "actualizado")
    ids, codes = set(), set()
    for p in data.get("promesas", []):
        where = p.get("codigo") or p.get("id") or "?"
        for key, seen in (("id", ids), ("codigo", codes)):
            if p.get(key) in seen or not p.get(key):
                fail(f"{where}: missing or duplicate {key}")
            seen.add(p.get(key))
        if not re.fullmatch(r"[a-z0-9-]+", p.get("id", "")):
            fail(f"{where}: id must be lowercase letters, digits and hyphens")
        if p.get("seccion") not in SECTIONS:
            fail(f"{where}: unknown seccion {p.get('seccion')!r}")
        if p.get("veredicto") not in VERDICTS:
            fail(f"{where}: unknown veredicto {p.get('veredicto')!r}")
        for field in ("titulo", "cita", "quien", "cargo", "nota"):
            if not str(p.get(field) or "").strip():
                fail(f"{where}: missing {field}")
        date(p.get("fecha"), where)
        date(p.get("veredicto_fecha"), f"{where} veredicto_fecha")
        sources = p.get("fuentes", [])
        if not sources:
            fail(f"{where}: no sources for the quote")
        if p.get("parafrasis") and len({s.get("medio") for s in sources}) < 2:
            fail(f"{where}: a paraphrase needs two outlets that agree")
        for s in sources:
            source(s, where)
        for t in p.get("tambien", []):
            date(t.get("fecha"), f"{where} tambien")
            for s in t.get("fuentes", []):
                source(s, f"{where} tambien")
        doc = p.get("documento") or {}
        for s in doc.get("fuentes", []):
            source(s, f"{where} documento")
        plazo = p.get("plazo") or {}
        if plazo.get("tipo") not in {"explicito", "lectura"}:
            fail(f"{where}: plazo needs tipo explicito or lectura")
        if plazo.get("fecha") is not None:
            date(plazo["fecha"], f"{where} plazo", future_ok=True)
        if not plazo.get("texto"):
            fail(f"{where}: plazo needs texto")
        steps = p.get("pasos", [])
        if sum(1 for s in steps if s.get("core")) != 1:
            fail(f"{where}: exactly one paso must be core")
        for i, s in enumerate(steps, 1):
            if s.get("estado") not in STEPS:
                fail(f"{where} paso {i}: unknown estado {s.get('estado')!r}")
            if s.get("estado") in NEEDS_EVIDENCE and not s.get("evidencia"):
                fail(f"{where} paso {i}: {s.get('estado')} needs evidencia")
            for ev in s.get("evidencia", []):
                source(ev, f"{where} paso {i}")
        verdict = p.get("veredicto")
        if verdict == "se_contradice" and not (any(str(c.get("texto", "")).strip() for c in doc.get("citas", [])) and doc.get("fuentes")):
            fail(f"{where}: «Se contradice» needs the document's exact words and its link")
        if verdict == "incumplida":
            core = next((s for s in steps if s.get("core")), {})
            outlets = {s.get("medio") for s in doc.get("fuentes", []) + core.get("evidencia", [])}
            if len(outlets) < 2:
                fail(f"{where}: «Incumplida» needs two independent sources")
            if core.get("estado") != "incumplido":
                fail(f"{where}: «Incumplida» but the core paso isn't incumplido")
        if verdict == "se_cumple" and not any(s.get("estado") == "cumplido" for s in steps):
            fail(f"{where}: «Se cumple» needs at least one cumplido paso")
        for path, text in strings(p):
            if path in {"id", "veredicto", "seccion"} or path.endswith((".url", ".archive", ".tipo", ".estado")):
                continue
            quoted = is_quote(path, p, text)
            if not quoted and BANNED.search(plain(text)):
                fail(f"{where}.{path}: wording that claims intent («miente», «engañó»…) outside a quote")
            if "israel" in plain(text) and not quoted:
                fail(f"{where}.{path}: the word israelí may appear only in the quote (AGENTS.md rule)")
    for c in data.get("correcciones", []):
        date(c.get("fecha"), "correcciones")
    for r in data.get("solicitudes", []):
        date(r.get("fecha"), "solicitudes")


e = html.escape


def long_date(s):
    d = datetime.date.fromisoformat(s)
    return f"{d.day} de {MONTHS[d.month - 1]} de {d.year}"


def link(src, text=None):
    out = f'<a href="{e(src["url"])}" rel="noopener" target="_blank">{e(text or src["medio"])}</a>'
    if src.get("archive"):
        out += f' (<a href="{e(src["archive"])}" rel="noopener" target="_blank">archivo</a>)'
    return out


def links(sources):
    return " · ".join(link(s) for s in sources)


def said(p):
    quote = f"<p class=\"para\">{e(p['cita'])}</p>" if p.get("parafrasis") else f"<blockquote>«{e(p['cita'])}»</blockquote>"
    out = [
        '<div class="side said">',
        "  <h4>Lo que prometieron</h4>",
        f"  {quote}",
        f'  <p class="who">{e(p["quien"])}, {e(p["cargo"])}. {long_date(p["fecha"])}, {e(p["donde"])}.</p>',
        f'  <p class="src">{links(p["fuentes"])}</p>',
    ]
    for t in p.get("tambien", []):
        out += [
            f'  <blockquote class="also">«{e(t["cita"])}»</blockquote>',
            f'  <p class="who">{e(t["quien"])}, {e(t["cargo"])}. {long_date(t["fecha"])}. {links(t["fuentes"])}</p>',
        ]
    return out + ["</div>"]


def document(p):
    doc = p.get("documento") or {}
    out = ['<div class="side doc">', "  <h4>Lo que dicen los documentos</h4>"]
    if doc.get("titulo"):
        out.append(f'  <p class="doc-title">{e(doc["titulo"])}</p>')
    for c in doc.get("citas", []):
        ref = f'<span class="ref">{e(c["ref"])}</span> ' if c.get("ref") else ""
        out.append(f"  <blockquote>{ref}«{e(c['texto'])}»</blockquote>")
    if doc.get("texto"):
        out.append(f"  <p>{e(doc['texto'])}</p>")
    if doc.get("fuentes"):
        out.append(f'  <p class="src">{links(doc["fuentes"])}</p>')
    return out + ["</div>"]


def steps(p):
    items = p.get("pasos", [])
    done = sum(1 for s in items if s["estado"] == "cumplido")
    declared = sum(1 for s in items if s["estado"] == "declarado")
    summary = f"Pasos: {done} de {len(items)} cumplidos" + (f", {declared} declarado{'s' if declared > 1 else ''} sin prueba" if declared else "")
    cells = "".join(f'<span class="st st-{s["estado"]}"></span>' for s in items)
    rows = []
    for s in items:
        ev = f' <span class="src">{links(s["evidencia"])}</span>' if s.get("evidencia") else ""
        core = ' <span class="core">Paso clave</span>' if s.get("core") else ""
        rows.append(f'<li class="st-row"><span class="st st-{s["estado"]}" aria-hidden="true"></span><span><strong>{STEPS[s["estado"]]}.</strong> {e(s["texto"])}{core}{ev}</span></li>')
    return [f'<details class="steps"><summary><span class="cells" aria-hidden="true">{cells}</span>{summary}</summary><ol>', *rows, "</ol></details>"]


def deadline(p):
    plazo = p["plazo"]
    if plazo.get("fecha"):
        kind = "fecha oficial" if plazo["tipo"] == "explicito" else "fecha que tomamos"
        return f'<p class="deadline" data-plazo="{plazo["fecha"]}"><strong>Plazo:</strong> {long_date(plazo["fecha"])} ({kind}). <span class="countdown"></span> {e(plazo["texto"])}</p>'
    return f'<p class="deadline"><strong>Plazo:</strong> {e(plazo["texto"])}</p>'


def reply(p, data):
    r = p.get("respuesta")
    if r:
        src = f' ({link({"url": r["url"], "medio": "respuesta completa"})})' if r.get("url") else ""
        return f'<p class="reply"><strong>Respuesta de la autoridad ({long_date(r["fecha"])}):</strong> {e(r["texto"])}{src}</p>'
    asked = data.get("replica")
    if not asked:
        return ""
    closes = long_date(asked["cierra"][:10])
    if asked["cierra"][:10] < data["actualizado"]:
        return f'<p class="reply"><strong>Respuesta de la autoridad:</strong> le pedimos su versión el {long_date(asked["enviada"])}. Sin respuesta al {closes}.</p>'
    return f'<p class="reply"><strong>Respuesta de la autoridad:</strong> le pedimos su versión el {long_date(asked["enviada"])}; puede responder hasta el {closes}.</p>'


def card(p, data):
    v = p["veredicto"]
    title = p["titulo"]
    return "\n".join([
        f'<article class="promesa" id="{p["id"]}" data-veredicto="{v}">',
        f'  <header class="p-head"><span class="code">{e(p["codigo"])}</span><h3>{e(title)}</h3><span class="chip v-{v}">{VERDICTS[v]}</span></header>',
        '  <div class="sides">',
        *(f"    {line}" for line in said(p) + document(p)),
        "  </div>",
        f'  <p class="why"><strong>Por qué «{VERDICTS[v]}»:</strong> {e(p["nota"])}</p>',
        f"  {deadline(p)}",
        *(f"  {line}" for line in steps(p)),
        *([f"  {reply(p, data)}"] if reply(p, data) else []),
        f'  <p class="meta">Calificación del {long_date(p["veredicto_fecha"])} · <a href="#{p["id"]}" class="copy" data-id="{p["id"]}">Copiar enlace</a></p>',
        "</article>",
    ])


def meter(data):
    promises = data["promesas"]
    out = []
    for key, label in SECTIONS.items():
        items = sorted((p for p in promises if p["seccion"] == key), key=lambda p: (ORDER.index(p["veredicto"]), p["codigo"]))
        segs = "".join(f'<a class="seg v-{p["veredicto"]}" href="#{p["id"]}" tabindex="-1" title="{e(p["codigo"] + " · " + p["titulo"] + ": " + VERDICTS[p["veredicto"]])}"></a>' for p in items)
        out += [f'<p class="m-label">{e(label)}</p>', f'<div class="m-bar" aria-hidden="true">{segs}</div>']
    out.append(f'<p class="m-stamp">aguagdl.com/promesas · {long_date(data["actualizado"])}</p>')
    counts = {v: sum(1 for p in promises if p["veredicto"] == v) for v in ORDER}
    heads = ["A. Acueducto", "B. Lo demás"]
    out += ['<table class="m-table">', '<thead><tr><th scope="col">Calificación</th>' + "".join(f'<th scope="col">{h}</th>' for h in heads) + '<th scope="col">Total</th></tr></thead>', "<tbody>"]
    for v in ORDER:
        per = [sum(1 for p in promises if p["veredicto"] == v and p["seccion"] == k) for k in SECTIONS]
        out.append(f'<tr><th scope="row"><span class="sw v-{v}" aria-hidden="true"></span>{VERDICTS[v]}</th>' + "".join(f"<td>{n}</td>" for n in per) + f"<td>{counts[v]}</td></tr>")
    out += ["</tbody>", "</table>"]
    return "\n".join(out), counts


def render(data):
    by = {k: [card(p, data) for p in data["promesas"] if p["seccion"] == k] for k in SECTIONS}
    graphic, counts = meter(data)
    n = len(data["promesas"])
    headline = f'<p class="m-head">De {n} compromisos, hoy: <strong>{counts["se_contradice"]}</strong> se contradicen con los documentos · <strong>{counts["incumplida"]}</strong> incumplido{"s" if counts["incumplida"] != 1 else ""} · <strong>{counts["en_riesgo"]}</strong> en riesgo · <strong>{counts["sin_pruebas"]}</strong> sin pruebas · <strong>{counts["se_cumple"]}</strong> se cumple{"n" if counts["se_cumple"] != 1 else ""}.</p>'
    requests = "\n".join(
        f'<li><strong>{e(r["a"])}</strong>, folio {e(r["folio"])}, presentada el {long_date(r["fecha"])}: {e(r["tema"])}. Estado: {e(r["estado"])}.' + (f' {link({"url": r["url"], "medio": "Respuesta"})}' if r.get("url") else "") + "</li>"
        for r in data.get("solicitudes", [])
    )
    log = "\n".join(
        f'<li><strong>{long_date(c["fecha"])}</strong>, {e(c["codigo"])}: {e(c["texto"])}' + (f' ({link({"url": c["url"], "medio": "fuente"})})' if c.get("url") else "") + "</li>"
        for c in sorted(data.get("correcciones", []), key=lambda c: c["fecha"], reverse=True)
    )
    return {
        "actualizado": f'<p class="updated">Actualizado el {long_date(data["actualizado"])}.</p>',
        "medidor": headline + "\n" + graphic,
        "app": "\n".join(by["app"]),
        "gobierno": "\n".join(by["gobierno"]),
        "solicitudes": requests or "<li>Todavía no presentamos solicitudes por este proyecto.</li>",
        "correcciones": log or "<li>Sin correcciones por ahora.</li>",
    }, counts


def fill(page, parts):
    for name, content in parts.items():
        page, n = re.subn(rf"(<!-- promesas:{name}:start -->).*?([ \t]*<!-- promesas:{name}:end -->)", lambda m: m.group(1) + "\n" + content + "\n" + m.group(2), page, flags=re.S)
        assert n == 1, f"markers for {name!r} not found in promesas.html"
    return page


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="fail if web/promesas.html is stale; write nothing")
    ap.add_argument("--drafts", action="store_true", help="with --out: skip the archive check, for review")
    ap.add_argument("--out", type=pathlib.Path, help="write promesas.html here instead of web/")
    args = ap.parse_args()
    global DRAFTS
    if args.drafts:
        if not args.out or args.out.resolve() == PAGE.parent:
            sys.exit("promesas: --drafts needs an --out other than web/")
        DRAFTS = True
    data = json.loads(DATA.read_text())
    validate(data)
    if errors:
        sys.exit("promesas: " + "\n  ".join(["invalid data:", *errors]))
    parts, counts = render(data)
    page = fill(PAGE.read_text(), parts)
    if args.check:
        if PAGE.read_text() != page:
            sys.exit("promesas: web/promesas.html is stale; run python3 pipelines/promesas.py")
    else:
        out = args.out.expanduser() if args.out else PAGE.parent
        (out / PAGE.name).write_text(page)
    print("  ".join(f"{VERDICTS[v]}: {counts[v]}" for v in ORDER))


main()
