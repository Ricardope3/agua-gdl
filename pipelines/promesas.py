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
import zoneinfo

from copy_rules import BANNED, plain

root = pathlib.Path(__file__).resolve().parent.parent
DATA = root / "web/promesas.json"
PAGE = root / "web/promesas.html"

VERDICTS = {
    "se_cumple": "Se cumple",
    "en_curso": "En curso",
    "sin_pruebas": "Sin pruebas",
    "en_riesgo": "En riesgo",
    "incumplida": "Incumplida",
    "se_contradice": "Se contradice con los documentos",
}
ORDER = list(VERDICTS)
STEPS = {"cumplido": "Cumplido", "declarado": "Declarado, sin prueba independiente", "en_disputa": "En disputa", "incumplido": "No se cumplió", "pendiente": "Pendiente"}
NEEDS_EVIDENCE = {"cumplido", "declarado", "en_disputa", "incumplido"}
SECTIONS = {"app": "A. El acueducto (APP)", "gobierno": "B. Los demás compromisos"}
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
TODAY = datetime.datetime.now(zoneinfo.ZoneInfo("America/Mexico_City")).date()

errors = []
DRAFTS = False


def show(v):
    s = v if isinstance(v, str) and v else json.dumps(v, ensure_ascii=False)
    return s if len(s) <= 60 else s[:59] + "…"


def fail(where, field, found, rule, fix):
    errors.append((where, field, show(found), rule, fix))


def report(name):
    """One line per failure; a rule that fails more than 3 times is one line with the count."""
    groups = {}
    for e in errors:
        groups.setdefault((e[1], e[3], e[4]), []).append(e)
    lines = []
    for (field, rule, fix), es in groups.items():
        if len(es) > 3:
            at = ", ".join(e[0].split(" ")[0] for e in es[:8]) + (", …" if len(es) > 8 else "")
            found = list(dict.fromkeys(e[2] for e in es))
            shown = " | ".join(found[:3]) + (f" (+{len(found) - 3} more distinct)" if len(found) > 3 else "")
            lines.append(f"{name} {len(es)}× [{at}] {field}: found {shown}; rule: {rule}; fix: {fix}")
        else:
            lines += [f"{name} [{w}] {f}: found {v}; rule: {r}; fix: {x}" for w, f, v, r, x in es]
    return "\n".join(lines)


def date(s, where, field, future_ok=False):
    try:
        d = datetime.date.fromisoformat(s)
    except (TypeError, ValueError):
        fail(where, field, s, "an ISO date YYYY-MM-DD", "write it as YYYY-MM-DD")
        return None
    if d > TODAY and not future_ok:
        fail(where, field, s, "not in the future", "use the date it happened")
    return d


def source(src, where, field):
    if not str(src.get("url", "")).startswith("https://"):
        fail(where, f"{field}.url", src.get("url"), "starts with https://", "use the https link")
    if not DRAFTS and not str(src.get("archive") or "").startswith("https://web.archive.org/") and src.get("captura") != "privada":
        fail(where, f"{field}.archive", src.get("url"), "an archive.org snapshot, or \"captura\": \"privada\" with a copy in the notes repo", "save it on web.archive.org and set archive")
    if not src.get("medio"):
        fail(where, f"{field}.medio", src.get("medio"), "every source names its medio", "set the outlet or issuer")
    if src.get("fecha"):
        date(src["fecha"], where, f"{field}.fecha")


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
    """Quotes are verbatim and exempt from the wording checks; a title counts when it is the quote itself.
    A paraphrased cita is our wording, not a quote."""
    if path == "cita":
        return not entry.get("parafrasis")
    if path.endswith(".cita") or re.search(r"\.citas\[\d+\]\.texto$", path):
        return True
    return path == "titulo" and not entry.get("parafrasis") and text.strip("«» ") == entry.get("cita", "").strip()


def validate(data):
    date(data.get("actualizado"), "top", "actualizado")
    ids, codes = set(), set()
    for n, p in enumerate(data.get("promesas", [])):
        where = f"{n} {p.get('codigo') or p.get('id') or '?'}"
        for key, seen in (("id", ids), ("codigo", codes)):
            if p.get(key) in seen or not p.get(key):
                fail(where, key, p.get(key), "present and unique", f"set a {key} no other promesa uses")
            seen.add(p.get(key))
        if not re.fullmatch(r"[a-z0-9-]+", p.get("id") or ""):
            fail(where, "id", p.get("id"), "lowercase letters, digits and hyphens", "rename it, e.g. agua-potable-2027")
        if p.get("seccion") not in SECTIONS:
            fail(where, "seccion", p.get("seccion"), f"one of {sorted(SECTIONS)}", "set app or gobierno")
        if p.get("veredicto") not in VERDICTS:
            fail(where, "veredicto", p.get("veredicto"), f"one of {ORDER}", "use one of those keys")
        def required(node, prefix, *fields):
            for field in fields:
                if not str(node.get(field) or "").strip():
                    fail(where, prefix + field, node.get(field), "required, not blank", f"fill in {prefix + field}")
        required(p, "", "titulo", "cita", "quien", "cargo", "nota", "donde")
        date(p.get("fecha"), where, "fecha")
        date(p.get("veredicto_fecha"), where, "veredicto_fecha")
        sources = p.get("fuentes", [])
        if not sources:
            fail(where, "fuentes", sources, "at least one source for the quote", "add the quote's source")
        if p.get("parafrasis") and len({s.get("medio") for s in sources}) < 2:
            fail(where, "fuentes", sorted({str(s.get("medio")) for s in sources}), "a paraphrase needs two outlets that agree", "add a second outlet's source")
        for j, s in enumerate(sources):
            source(s, where, f"fuentes[{j}]")
        for k, t in enumerate(p.get("tambien", [])):
            required(t, f"tambien[{k}].", "cita", "quien", "cargo")
            date(t.get("fecha"), where, f"tambien[{k}].fecha")
            for j, s in enumerate(t.get("fuentes", [])):
                source(s, where, f"tambien[{k}].fuentes[{j}]")
        doc = p.get("documento") or {}
        for j, c in enumerate(doc.get("citas", [])):
            required(c, f"documento.citas[{j}].", "texto")
        for j, s in enumerate(doc.get("fuentes", [])):
            source(s, where, f"documento.fuentes[{j}]")
        plazo = p.get("plazo") or {}
        if plazo.get("tipo") not in {"explicito", "lectura"}:
            fail(where, "plazo.tipo", plazo.get("tipo"), "explicito or lectura", "set plazo.tipo")
        if plazo.get("fecha") is not None:
            date(plazo["fecha"], where, "plazo.fecha", future_ok=True)
        if not plazo.get("texto"):
            fail(where, "plazo.texto", plazo.get("texto"), "required", "describe the deadline in plazo.texto")
        steps = p.get("pasos", [])
        if sum(1 for s in steps if s.get("core")) != 1:
            fail(where, "pasos", f"{sum(1 for s in steps if s.get('core'))} core", "exactly one paso is core", "set core: true on exactly one paso")
        for i, s in enumerate(steps, 1):
            required(s, f"paso {i}.", "texto")
            if s.get("estado") not in STEPS:
                fail(where, f"paso {i}.estado", s.get("estado"), f"one of {sorted(STEPS)}", "use one of those estados")
            if s.get("estado") in NEEDS_EVIDENCE and not s.get("evidencia"):
                fail(where, f"paso {i}.evidencia", s.get("evidencia"), f"{s.get('estado')} needs evidencia", "add a source or set estado pendiente")
            for j, ev in enumerate(s.get("evidencia", [])):
                source(ev, where, f"paso {i}.evidencia[{j}]")
        if r := p.get("respuesta"):
            required(r, "respuesta.", "texto")
            date(r.get("fecha"), where, "respuesta.fecha")
        verdict = p.get("veredicto")
        if verdict == "se_contradice" and not (any(str(c.get("texto", "")).strip() for c in doc.get("citas", [])) and doc.get("fuentes")):
            fail(where, "documento", doc, "«Se contradice» needs the document's exact words and its link", "add documento.citas[].texto and documento.fuentes")
        if verdict == "incumplida":
            core = next((s for s in steps if s.get("core")), {})
            outlets = {s.get("medio") for s in doc.get("fuentes", []) + core.get("evidencia", [])}
            if len(outlets) < 2:
                fail(where, "veredicto", sorted(map(str, outlets)), "«Incumplida» needs two independent sources (documento + core evidencia)", "add a second independent medio")
            if core.get("estado") != "incumplido":
                fail(where, "veredicto", core.get("estado"), "«Incumplida» needs the core paso incumplido", "fix the core paso's estado or the verdict")
        core = next((s for s in steps if s.get("core")), {})
        if verdict == "se_cumple" and core.get("estado") != "cumplido":
            fail(where, "veredicto", core.get("estado"), "«Se cumple» needs the core paso cumplido", "fix the core paso's estado or the verdict")
        for path, text in strings(p):
            if path in {"id", "veredicto", "seccion"} or path.endswith((".url", ".archive", ".tipo", ".estado")):
                continue
            quoted = is_quote(path, p, text)
            if not quoted and BANNED.search(plain(text)):
                fail(where, path, text, "no wording that claims intent («miente», «engañó»…) outside a quote", "reword, or quote the source")
            if "israel" in plain(text) and not quoted:
                fail(where, path, text, "israelí only inside the quote (AGENTS.md)", "remove it or move it into the quote")
    for k, c in enumerate(data.get("correcciones", [])):
        date(c.get("fecha"), "top", f"correcciones[{k}].fecha")
    for k, r in enumerate(data.get("solicitudes", [])):
        date(r.get("fecha"), "top", f"solicitudes[{k}].fecha")
    if asked := data.get("replica"):
        date(asked.get("enviada"), "top", "replica.enviada")
        date(str(asked.get("cierra") or "")[:10] or None, "top", "replica.cierra", future_ok=True)


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
    headline = f'<p class="m-head">De {n} compromisos, hoy: <strong>{counts["se_contradice"]}</strong> se contradicen con los documentos · <strong>{counts["incumplida"]}</strong> incumplido{"s" if counts["incumplida"] != 1 else ""} · <strong>{counts["en_riesgo"]}</strong> en riesgo · <strong>{counts["sin_pruebas"]}</strong> sin pruebas · <strong>{counts["en_curso"]}</strong> en curso · <strong>{counts["se_cumple"]}</strong> se cumple{"n" if counts["se_cumple"] != 1 else ""}.</p>'
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
        sys.exit("promesas: " + "invalid data:\n" + report(DATA.name))
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
