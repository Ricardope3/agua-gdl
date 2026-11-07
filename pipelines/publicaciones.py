"""Publications on /reportes: validate web/publicaciones.json and refresh the engagement of its X posts.

    python3 pipelines/publicaciones.py            validate
    python3 pipelines/publicaciones.py --check    same; for CI. Writes nothing.
    python3 pipelines/publicaciones.py --eco      refresh the likes and replies of the X posts through X's
                                                  public embed endpoint (no login), then validate and write
    python3 pipelines/publicaciones.py --imagenes download each post's preview image ("vista") (an article's og:image,
                                                  an X post's photo or video poster, a Facebook post's
                                                  og:image) into web/fuentes/, 480 px JPEG (macOS sips), then
                                                  validate and write. A comment gets its post's image; "vista": null marks
                                                  a logo or stock picture removed by hand, so it stays out.
    python3 pipelines/publicaciones.py --capturas  screenshot the top of each news article (its headline, as the
                                                  outlet shows it) with headless Chrome into web/fuentes/ as
                                                  "captura", and keep its og:title as "titular"; then validate
                                                  and write. Check the pictures: a cookie banner or an ad can
                                                  cover the headline (set "captura": null to leave it out).
    python3 pipelines/publicaciones.py --videos   set "video": true on the X posts whose public embed serves a
                                                  video, so a future run can download the evidence; then
                                                  validate and write. Facebook needs a browser session, so its
                                                  posts are tagged by hand when added.
    python3 pipelines/publicaciones.py q colonia~ARCOS fuente=medio fecha>=2026-10-20 dias>7 [--fields url,fecha,dias] [--count] [--all]
                                                  list matching entries as TSV with their index (50 rows unless
                                                  --all); ops = != ~ (contains) > >= < <=, dotted fields (eco.reacciones)
    python3 pipelines/publicaciones.py schema     (or --schema) each field: type, required, values, meaning
    python3 pipelines/publicaciones.py add FILE.json      append one entry or a list; written only if validate() passes
    python3 pipelines/publicaciones.py set INDEX field=value ...   value is JSON or a plain string; "field=" removes
                                                  it; written only if validate() passes. --data PATH works on a copy.

Each entry quotes a news outlet ("medio") or neighbours ("vecinos") saying a colonia has no water, with
its link, date and SIAPA colonias. Neighbours' posts count only with at least regla.reacciones reactions
and regla.comentarios comments; news outlets count without. A neighbour's comment ("tipo": "comentario")
counts by the post it is in ("en"; on X, the post a reply answers), whose reactions and comments must meet the rule. A news story that
retells a post names it in "de", so the page counts both as one source. A private person is
never named: "quien" is the outlet, the public group («Grupo «…»») or a colonia's own account («Cuenta de
vecinos …»), or empty, and the post a comment is in ("en.quien") is an outlet some "medio" entry names,
such a group or account, or one of the public pages in PAGINAS. Facebook's numbers can't be refreshed
without a login; they keep the date they were read ("al").
"""
import argparse
import hashlib
import html
import shutil
import subprocess
import tempfile
import datetime
import json
import math
import pathlib
import re
import string
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import zoneinfo

root = pathlib.Path(__file__).resolve().parent.parent
DATA = root / "web/publicaciones.json"
COLONIAS = root / "api/data/colonias_mapa.json"
WEB = root / "web"
IMAGEN = re.compile(r"^fuentes/[0-9a-f]{12}\.jpg$")
CAPTURA = re.compile(r"^fuentes/[0-9a-f]{12}-t\.jpg$")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
TODAY = datetime.datetime.now(zoneinfo.ZoneInfo("America/Mexico_City")).date()
FUENTES = {"medio", "vecinos"}
REDES = {"facebook", "x", "web"}
X_URL = re.compile(r"^https://x\.com/(\w{1,15})/status/(\d{8,20})$")
VECINOS_QUIEN = ("Grupo «", "Cuenta de vecinos ")
# Public pages, not outlets with a "medio" entry, whose posts neighbours comment on (en.quien).
# «Cuenta personal en X» describes a person's account without naming them.
PAGINAS = {"Cuenta personal en X", "Cuenta personal en TikTok", "Gobierno de Guadalajara", "Gobierno de Jalisco", "Gobierno de Zapopan", "Jalisco ZMG", "Revista Jalisco", "SIAPA Guadalajara", "Tlaquepaque San Pedro", "Las Juntas, Mercado y Pueblo"}

errors = []



# docs/GLOSARIO.md: `dias` is the days the source gives, never our conversion.
_NUM = {'un':1,'una':1,'uno':1,'dos':2,'tres':3,'cuatro':4,'cinco':5,'seis':6,'siete':7,'ocho':8,'nueve':9,'diez':10,'once':11,'doce':12,'trece':13,'catorce':14,'quince':15,'dieciseis':16,'diecisiete':17,'dieciocho':18,'diecinueve':19,'veinte':20,'veintiuno':21,'veintiun':21,'veintidos':22,'veintitres':23,'veinticuatro':24,'veinticinco':25,'veintiseis':26,'veintisiete':27,'veintiocho':28,'veintinueve':29,'treinta':30}
_UNIT = {'dia':1,'dias':1,'semana':7,'semanas':7,'mes':30,'meses':30}
def _fold(s): return ''.join(c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c)).lower()
_AMOUNT = r'(\d{1,3}|' + '|'.join(_NUM) + r')\s+(dias?|semanas?|mes(es)?)'
_HEDGE = re.compile(r'\b(casi|vamos para|van para|va para|vamos a cumplir|manana cumplimos|manana se cumplen|cumpliremos)\s+(la |el |los |las )?' + _AMOUNT)
_HEDGE_UNIT = re.compile(r'\bcasi (la|una|un) (semana|mes)\b')
_SINCE = re.compile(r'\bdesde (el |este |la |hace )?(pasado )?(lunes|martes|miercoles|jueves|viernes|sabado|domingo|ayer|antier|anoche|\d{1,2} de [a-z]+|el \d{1,2})')
def _amounts(c):
    out = []
    for m in re.finditer(r'(?<![\w.])' + _AMOUNT, c):
        n = int(m.group(1)) if m.group(1).isdigit() else _NUM[m.group(1)]
        out.append((m.start(), n * _UNIT[m.group(2)]))
    if re.search(r'mes y medio', c): out.append((c.find('mes y medio'), 45))
    return out
def own_arithmetic(cita, dias):
    """True when dias is our conversion: the quote hedges («casi», «vamos para», «mañana cumplimos») or counts from a date, and states no plain amount equal to dias."""
    if dias is None: return False
    c = _fold(cita)
    hedged = [m.start() for r in (_HEDGE, _HEDGE_UNIT) for m in r.finditer(c)]
    since = _SINCE.search(c) and 'desde hace' not in c[max(0, _SINCE.search(c).start()-1):_SINCE.search(c).end()]
    if not hedged and not since: return False
    plain = [n for pos, n in _amounts(c) if not any(h <= pos <= h + 30 for h in hedged)]
    return dias not in plain


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


def date(s, where, field):
    try:
        d = datetime.date.fromisoformat(s)
    except (TypeError, ValueError):
        fail(where, field, s, "an ISO date YYYY-MM-DD", "write it as YYYY-MM-DD")
        return None
    if d > TODAY:
        fail(where, field, s, "not in the future", "use the date it happened")
    return d


def count(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def validate(doc):
    keys = {"|".join(c[:3]) for c in json.loads(COLONIAS.read_text())}
    updated = date(doc.get("actualizado"), "top", "actualizado")
    since = date(doc.get("desde"), "top", "desde")
    rule = doc.get("regla") or {}
    if not (count(rule.get("reacciones")) and count(rule.get("comentarios"))):
        fail("top", "regla", doc.get("regla"), "needs reacciones and comentarios counts", "set both as non-negative integers")
    # busquedas logs the days collection ran, newest last; the pages show the last one.
    busquedas = doc.get("busquedas")
    if busquedas is not None:
        if not (isinstance(busquedas, list) and busquedas and all(isinstance(b, str) for b in busquedas)):
            fail("top", "busquedas", busquedas, "a nonempty list of ISO dates, newest last", "make it a list of date strings")
        else:
            dias = [date(b, "top", "busquedas") for b in busquedas]
            if any(not d for d in dias) or dias != sorted(dias) or len(set(dias)) != len(dias):
                fail("top", "busquedas", busquedas[-3:], "valid distinct dates, oldest first", "sort and dedupe the dates")
            elif since and dias[0] < since or updated and dias[-1] > updated:
                fail("top", "busquedas", [busquedas[0], busquedas[-1]], "within desde..actualizado", "drop out-of-range dates or move desde/actualizado")
    seen = set()
    said = set()
    pages = PAGINAS | {p["quien"] for p in doc.get("publicaciones") or [] if p.get("fuente") == "medio" and isinstance(p.get("quien"), str)}
    for i, p in enumerate(doc.get("publicaciones") or []):
        where = f"{i} {show(p.get('url', ''))}"
        if p.get("fuente") not in FUENTES:
            fail(where, "fuente", p.get("fuente"), f"one of {sorted(FUENTES)}", "set medio or vecinos")
        red = p.get("red")
        url = p.get("url", "")
        if red not in REDES:
            fail(where, "red", red, f"one of {sorted(REDES)}", "set facebook, x or web")
        elif red == "x" and not X_URL.match(url):
            fail(where, "url", url, "an X post links x.com/<account>/status/<id>", "use the https://x.com/<account>/status/<id> link")
        elif red == "facebook" and not url.startswith("https://www.facebook.com/"):
            fail(where, "url", url, "a Facebook post links https://www.facebook.com/…", "use the www.facebook.com link or fix red")
        elif red == "web" and (not url.startswith("https://") or re.match(r"https://(www\.)?(facebook|x|twitter)\.com/", url)):
            fail(where, "url", url, "a web article links its https page", "use the article's https URL or fix red")
        # One article can name several colonias with different days: one entry per quote.
        if (url, p.get("cita")) in seen:
            fail(where, "url+cita", p.get("cita"), "each url+cita listed once", "remove the duplicate entry")
        seen.add((url, p.get("cita")))
        # A neighbour who pastes the same words under several posts is one report.
        if p.get("fuente") == "vecinos" and isinstance(p.get("cita"), str):
            words = "".join(c for c in unicodedata.normalize("NFD", p["cita"].lower()) if c.isalnum())
            for k in p.get("colonias") or []:
                if (words, k) in said:
                    fail(where, "cita", k, "a neighbour's words count once per colonia", "drop this colonia or the repeated entry")
                said.add((words, k))
        if "de" in p and not (p.get("fuente") == "medio" and str(p["de"]).startswith("https://")):
            fail(where, "de", p["de"], "de is the https post a news story retells (fuente medio)", "set an https URL on a medio entry or remove de")
        quien = p.get("quien")
        if not isinstance(quien, str):
            fail(where, "quien", quien, "a string", "set \"\" or the outlet/group name")
        elif p.get("fuente") == "medio" and not quien:
            fail(where, "quien", quien, "a news outlet is named", "set the outlet's name")
        elif p.get("fuente") == "vecinos" and quien and not quien.startswith(VECINOS_QUIEN):
            fail(where, "quien", quien, "neighbours are never named; empty, «Grupo «…»» or «Cuenta de vecinos …»", "replace the name with an allowed form")
        if isinstance(quien, str) and "@" in quien:
            fail(where, "quien", quien, "never an @handle; the link keeps it", "remove the @handle")
        d = date(p.get("fecha"), where, "fecha")
        if d and since and d < since:
            fail(where, "fecha", p.get("fecha"), f"on or after desde ({doc.get('desde')})", "check the post date or drop the entry")
        if d and updated and d > updated:
            fail(where, "fecha", p.get("fecha"), f"on or before actualizado ({doc.get('actualizado')})", "move actualizado forward")
        cols = p.get("colonias")
        if not cols or not isinstance(cols, list):
            fail(where, "colonias", cols, "a nonempty list of colonia keys", "add the colonias the post names")
        for k in cols or []:
            if k not in keys:
                fail(where, "colonias", k, "a key of api/data/colonias_mapa.json", "use the exact name|municipio|cp key")
        if not p.get("lugar"):
            fail(where, "lugar", p.get("lugar"), "the place as the post names it", "copy the place name from the post")
        cita = p.get("cita")
        if not isinstance(cita, str) or not cita.strip() or len(cita) > 400 or "http" in cita:
            fail(where, "cita", cita, "the post's own words, 1 to 400 characters, without links", "trim to ≤400 chars and remove links")
        elif re.search(r"#\s*\d", cita):
            fail(where, "cita", cita, "never a street number (#14)", "redact it visibly, e.g. #[…]")
        dias = p.get("dias")
        if dias is not None and not (count(dias) and 1 <= dias <= 120):
            fail(where, "dias", dias, "null or an integer 1 to 120", "set the days the post gives, or null")
        elif own_arithmetic(cita or "", dias):
            fail(where, "dias", dias, "a number the quote states, not one we derived from «casi», «vamos para» or «desde <fecha>»", "set dias to null (docs/GLOSARIO.md)")
        if "desde" in p:
            s = date(p["desde"], where, "desde")
            if s and d and s > d:
                fail(where, "desde", p["desde"], f"not after fecha ({p.get('fecha')})", "fix desde or fecha")
        if "bloqueo" in p and p["bloqueo"] is not True:
            fail(where, "bloqueo", p["bloqueo"], "true or absent", "set true or remove the field")
        # The other side, always as the source's own claim, never our conclusion:
        # regreso: the day the source says the water came back; parcial: the source describes
        # low or intermittent supply rather than a cut; causa: a non-SIAPA cause or system the
        # source names; calidad: water quality (smell, color, sediment), not absence.
        if "regreso" in p:
            r = date(p.get("regreso"), where, "regreso")
            if not r or r < since or (d and r > d):
                fail(where, "regreso", p.get("regreso"), "an ISO date within desde..fecha", "use the date the source gives, or remove it")
        if p.get("parcial") not in (None, True):
            fail(where, "parcial", p.get("parcial"), "true or absent", "set true or remove the field")
        if p.get("calidad") not in (None, True):
            fail(where, "calidad", p.get("calidad"), "true or absent", "set true or remove the field")
        if "causa" in p and not (isinstance(p["causa"], str) and 0 < len(p["causa"]) <= 80):
            fail(where, "causa", p["causa"], "the non-SIAPA cause the source names, 1 to 80 characters", "shorten it or remove the field")
        if p.get("vista") is not None and not (isinstance(p["vista"], str) and IMAGEN.match(p["vista"]) and (WEB / p["vista"]).is_file()):
            fail(where, "vista", p["vista"], "null or fuentes/<12 hex>.jpg existing in web/", "run --imagenes or set null")
        if p.get("captura") is not None and not (isinstance(p["captura"], str) and CAPTURA.match(p["captura"]) and (WEB / p["captura"]).is_file()):
            fail(where, "captura", p["captura"], "null or fuentes/<12 hex>-t.jpg existing in web/", "run --capturas or set null")
        if "titular" in p and not (red == "web" and isinstance(p["titular"], str) and 0 < len(p["titular"]) <= 300):
            fail(where, "titular", p["titular"], "a web article's headline, 1 to 300 characters", "fix it or remove it (not on red facebook/x)")
        eco = p.get("eco")
        check_eco(eco, where, "eco")
        # "video": true marks a post whose link carries a video (a reel, a YouTube video, an X post
        # whose embed serves one), so a future run can download the evidence. Absent means unknown.
        if p.get("video") not in (None, True):
            fail(where, "video", p.get("video"), "true or absent", "set true or remove the field")
        if re.search(r"facebook\.com/(reel|watch)/|youtube\.com|youtu\.be/|tiktok\.com/", url) and not p.get("video"):
            fail(where, "video", p.get("video"), "a reel, watch, YouTube or TikTok link carries a video", "set \"video\": true")
        # A comment counts by the thread it is in: the post's reactions and comments meet the rule.
        tipo = p.get("tipo")
        if tipo not in (None, "comentario"):
            fail(where, "tipo", tipo, "absent or comentario", "set comentario or remove the field")
        if tipo == "comentario":
            en = p.get("en") or {}
            # On X a comment is a reply: its own post, answering the one in en.
            if red == "x":
                if not en.get("quien") or not X_URL.match(str(en.get("url", ""))):
                    fail(where, "en", p.get("en"), "a reply names the post it answers (en.quien, en.url)", "set en.quien and en.url to the X post answered")
                elif not X_URL.match(url) or url == en["url"]:
                    fail(where, "url", url, "a reply links its own post, not the one in en", "use the reply's own status URL")
            elif not en.get("quien") or not re.match(r"https://www\.(facebook\.com/|tiktok\.com/@[^/]+/video/\d+$)", str(en.get("url", ""))):
                fail(where, "en", p.get("en"), "a comment names the post it is in (en.quien, en.url)", "set en.quien and en.url (www.facebook.com or a www.tiktok.com video)")
            elif not url.startswith(en["url"] + "?comment_id="):
                fail(where, "url", url, "a comment links its post with ?comment_id=", "use en.url + ?comment_id=…")
            if en.get("quien") and not (str(en["quien"]) in pages or str(en["quien"]).startswith(VECINOS_QUIEN)):
                fail(where, "en.quien", en["quien"], "never a person: a medio outlet, «Grupo «…»», «Cuenta de vecinos …» or PAGINAS", "use an allowed form, or add a checked page to PAGINAS")
            if en.get("quien") and "@" in str(en["quien"]):
                fail(where, "en.quien", en["quien"], "never an @handle; the link keeps it", "remove the @handle")
            check_eco(en.get("eco"), where, "en.eco")
            eco = en.get("eco")
        if p.get("fuente") == "vecinos":
            if eco is None:
                fail(where, "eco", eco, "a neighbours' post needs eco", "add eco {reacciones, comentarios, al}")
            elif count(eco.get("reacciones")) and count(eco.get("comentarios")) and (
                    eco["reacciones"] < rule.get("reacciones", 0) or eco["comentarios"] < rule.get("comentarios", 0)):
                fail(where, "eco", f"{eco['reacciones']} reactions, {eco['comentarios']} comments", f"at least {rule.get('reacciones')} reactions and {rule.get('comentarios')} comments", "refresh eco or drop the entry")


def check_eco(eco, where, field):
    if eco is None:
        return
    if not (count(eco.get("reacciones")) and count(eco.get("comentarios"))):
        fail(where, field, eco, "needs reacciones and comentarios counts", "set both as non-negative integers")
    if "compartidos" in eco and not count(eco["compartidos"]):
        fail(where, f"{field}.compartidos", eco["compartidos"], "a non-negative integer", "fix the count or remove it")
    date(eco.get("al"), where, f"{field}.al")


def radix36(value):
    """JavaScript's Number.prototype.toString(36), as V8 prints a positive double."""
    chars = "0123456789abcdefghijklmnopqrstuvwxyz"
    integer = math.floor(value)
    fraction = value - integer
    delta = max(0.5 * (math.nextafter(value, math.inf) - value), math.nextafter(0.0, 1.0))
    digits = []
    if fraction >= delta:
        while True:
            fraction *= 36
            delta *= 36
            digit = int(fraction)
            digits.append(digit)
            fraction -= digit
            if (fraction > 0.5 or (fraction == 0.5 and digit & 1)) and fraction + delta > 1:
                while True:
                    if not digits:
                        integer += 1
                        break
                    last = digits.pop() + 1
                    if last < 36:
                        digits.append(last)
                        break
                break
            if fraction < delta:
                break
    out = ""
    while True:
        integer, r = divmod(integer, 36)
        out = chars[int(r)] + out
        if not integer:
            break
    return out + ("." + "".join(chars[d] for d in digits) if digits else "")


def token(post_id):
    # The token X's own embed computes: ((id / 1e15) * π) in base 36, without zeros or the point.
    return re.sub(r"0+|\.", "", radix36(int(post_id) / 1e15 * math.pi))


def refresh_x(doc):
    changed = 0
    for p in doc.get("publicaciones") or []:
        m = X_URL.match(p.get("url", ""))
        if p.get("red") != "x" or not m:
            continue
        q = urllib.parse.urlencode({"id": m.group(2), "token": token(m.group(2)), "lang": "es"})
        req = urllib.request.Request(f"https://cdn.syndication.twimg.com/tweet-result?{q}", headers={"User-Agent": "aguagdl-publicaciones"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                t = json.load(r)
        except (OSError, ValueError) as e:
            print(f"  {p['url']}: not refreshed ({e})", file=sys.stderr)
            continue
        if t.get("__typename") == "TweetTombstone" or "favorite_count" not in t:
            print(f"  {p['url']}: X doesn't show it any more; check it and remove it", file=sys.stderr)
            continue
        eco = p.setdefault("eco", {})
        new = {"reacciones": t["favorite_count"], "comentarios": t.get("conversation_count", 0), "al": TODAY.isoformat()}
        if any(eco.get(k) != v for k, v in new.items()):
            changed += 1
        eco.update(new)
        time.sleep(0.4)
    return changed


def detect_x_videos(doc):
    """Tag the X posts whose embed serves a video, for a future evidence download."""
    changed = 0
    for p in doc.get("publicaciones") or []:
        m = X_URL.match(p.get("url", ""))
        if p.get("red") != "x" or not m or p.get("video"):
            continue
        q = urllib.parse.urlencode({"id": m.group(2), "token": token(m.group(2)), "lang": "es"})
        req = urllib.request.Request(f"https://cdn.syndication.twimg.com/tweet-result?{q}", headers={"User-Agent": "aguagdl-publicaciones"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                t = json.load(r)
        except (OSError, ValueError) as e:
            print(f"  {p['url']}: not checked ({e})", file=sys.stderr)
            continue
        if t.get("__typename") == "TweetTombstone" or "favorite_count" not in t:
            continue
        media = t.get("mediaDetails") or []
        if t.get("video") or any(d.get("type") in ("video", "animated_gif") for d in media):
            p["video"] = True
            changed += 1
        time.sleep(0.4)
    return changed


def get(url, ua="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130 Safari/537.36"):
    # An og:image can carry raw accents, which urllib can't send: percent-encode them, as browsers do.
    req = urllib.request.Request(urllib.parse.quote(url, safe=string.punctuation), headers={"User-Agent": ua, "Accept-Language": "es-MX,es;q=0.9"})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read(8_000_000)


def og_image(url, ua=None):
    page = get(url, ua) if ua else get(url)
    text = page.decode("utf-8", "replace")
    for prop in ("og:image", "twitter:image", "og:image:url", "twitter:image:src"):
        for m in re.finditer(r"<meta\b[^>]*>", text, re.I):
            tag = m.group(0)
            if re.search(r'(?:property|name)\s*=\s*["\']' + re.escape(prop) + r'["\']', tag, re.I):
                c = re.search(r'content\s*=\s*["\']([^"\']+)', tag, re.I)
                if c:
                    return urllib.parse.urljoin(url, html.unescape(c.group(1)))
    return None


def x_image(url):
    m = X_URL.match(url)
    q = urllib.parse.urlencode({"id": m.group(2), "token": token(m.group(2)), "lang": "es"})
    t = json.loads(get(f"https://cdn.syndication.twimg.com/tweet-result?{q}", "aguagdl-publicaciones"))
    for d in t.get("mediaDetails") or []:
        if d.get("media_url_https"):
            return d["media_url_https"] + "?name=small"
    if (t.get("video") or {}).get("poster"):
        return t["video"]["poster"]
    vals = ((t.get("card") or {}).get("binding_values") or {})
    for k in ("thumbnail_image_large", "summary_photo_image_large", "photo_image_full_size_large", "thumbnail_image"):
        u = ((vals.get(k) or {}).get("image_value") or {}).get("url")
        if u:
            return u
    return None


def fetch_images(doc, again=False):
    out = WEB / "fuentes"
    out.mkdir(exist_ok=True)
    if not shutil.which("sips"):
        sys.exit("publicaciones: --imagenes needs macOS sips to resize")
    got = 0
    for p in doc.get("publicaciones") or []:
        if "vista" in p and not again:
            continue
        # A comment shows the picture of the post it was written under.
        url = p["en"]["url"] if p.get("tipo") == "comentario" else p["url"]
        red = "facebook" if p.get("tipo") == "comentario" and p["red"] != "x" else p["red"]
        name = f"fuentes/{hashlib.sha1(url.encode()).hexdigest()[:12]}.jpg"
        if (WEB / name).is_file():
            p["vista"] = name
            continue
        try:
            if red == "x":
                src = x_image(url)
            elif red == "facebook" or "tiktok.com/" in url:
                # TikTok serves its share card only to link-preview crawlers.
                src = og_image(url, "facebookexternalhit/1.1")
            else:
                try:
                    src = og_image(url)
                except urllib.error.HTTPError:
                    # Some outlets refuse scripts; the Wayback Machine's copy carries the same og:image.
                    src = og_image(f"https://web.archive.org/web/2026id_/{url}")
            if not src or not src.startswith("https://") or re.search(r"(logo|favicon|default|placeholder)", src, re.I):
                print(f"  {url}: no image", file=sys.stderr)
                continue
            data = get(src)
        except (OSError, ValueError) as e:
            print(f"  {url}: no image ({e})", file=sys.stderr)
            continue
        with tempfile.TemporaryDirectory() as tmp:
            raw = pathlib.Path(tmp) / "raw"
            raw.write_bytes(data)
            r = subprocess.run(["sips", "-Z", "480", "-s", "format", "jpeg", "-s", "formatOptions", "68", str(raw), "--out", str(WEB / name)], capture_output=True)
        if r.returncode or not (WEB / name).is_file():
            print(f"  {url}: not an image", file=sys.stderr)
            continue
        p["vista"] = name
        got += 1
        time.sleep(0.3)
    return got


def headline(url):
    try:
        text = get(url).decode("utf-8", "replace")
    except (OSError, ValueError):
        return None
    for prop in ("og:title", "twitter:title"):
        for m in re.finditer(r"<meta\b[^>]*>", text, re.I):
            tag = m.group(0)
            if re.search(r'(?:property|name)\s*=\s*["\']' + re.escape(prop) + r'["\']', tag, re.I):
                c = re.search(r'content\s*=\s*["\']([^"\']+)', tag, re.I)
                if c:
                    return html.unescape(c.group(1)).strip()[:300]
    return None


def fetch_captures(doc):
    if not pathlib.Path(CHROME).exists() or not shutil.which("sips"):
        sys.exit("publicaciones: --capturas needs Google Chrome and macOS sips")
    (WEB / "fuentes").mkdir(exist_ok=True)
    done = {}
    got = 0
    for p in doc.get("publicaciones") or []:
        if p.get("red") != "web" or "captura" in p:
            continue
        url = p["url"]
        if url not in done:
            name = f"fuentes/{hashlib.sha1(url.encode()).hexdigest()[:12]}-t.jpg"
            if not (WEB / name).is_file():
                # Chrome may still be writing its profile when killed, so the folder goes without complaint.
                tmp = tempfile.mkdtemp()
                try:
                    shot = pathlib.Path(tmp) / "shot.png"
                    try:
                        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--mute-audio",
                                        "--window-size=1280,900", "--virtual-time-budget=9000", f"--user-data-dir={tmp}/u",
                                        f"--screenshot={shot}", url], capture_output=True, timeout=60)
                    except subprocess.TimeoutExpired:
                        pass
                    if shot.is_file():
                        subprocess.run(["sips", "-s", "format", "jpeg", "-s", "formatOptions", "72", "-Z", "720", str(shot), "--out", str(WEB / name)], capture_output=True)
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
            if (WEB / name).is_file():
                got += 1
                done[url] = (name, headline(url))
            else:
                print(f"  {url}: no screenshot", file=sys.stderr)
                done[url] = (None, headline(url))
        name, title = done[url]
        if name:
            p["captura"] = name
        if title:
            p["titular"] = title
    return got


# field, type, required, allowed values, meaning (from .claude/rules/evidence.md)
SCHEMA = [
    ("fuente", "str", "yes", "medio|vecinos", "a news outlet (counts without threshold) or neighbours (need regla)"),
    ("red", "str", "yes", "facebook|x|web", "where it was published; fixes the url shape"),
    ("quien", "str", "yes", "outlet, «Grupo «…»», «Cuenta de vecinos …» or empty", "who published it; never a private person"),
    ("url", "str", "yes", "https link", "the post or article"),
    ("fecha", "date", "yes", "desde..actualizado", "publication date"),
    ("colonias", "list[str]", "yes", "keys of api/data/colonias_mapa.json", "SIAPA colonias it names"),
    ("lugar", "str", "yes", "", "the place as the post names it"),
    ("cita", "str", "yes", "1-400 chars, no links, no #number", "its words as published, checked against the post"),
    ("dias", "int|null", "no", "1-120 or null", "days without water it gives"),
    ("desde", "date", "no", "<= fecha", "day the source says the cut began"),
    ("bloqueo", "true", "no", "true or absent", "a street blockade"),
    ("de", "str", "no", "https url; medio only", "the post a news story retells; counted as one source"),
    ("regreso", "date", "no", "desde..fecha", "day the source says the water came back (its claim)"),
    ("parcial", "true", "no", "true or absent", "low or intermittent supply, per the source"),
    ("calidad", "true", "no", "true or absent", "quality-only complaint (smell, color, sediment)"),
    ("causa", "str", "no", "1-80 chars", "the non-SIAPA cause the source names"),
    ("eco", "obj|null", "vecinos", "{reacciones, comentarios, compartidos?, al}", "reactions, comments, shares and the date read"),
    ("tipo", "str", "no", "comentario or absent", "a comment; counts by the post it is in"),
    ("en", "obj", "if tipo", "{quien, url, eco}", "the post a comment is in (on X, the post a reply answers)"),
    ("video", "true", "no", "true or absent", "the link carries a video; absent means unknown"),
    ("vista", "str|null", "no", "fuentes/<12 hex>.jpg or null", "preview image saved by --imagenes; null = logo/stock"),
    ("captura", "str|null", "no", "fuentes/<12 hex>-t.jpg or null", "headline screenshot saved by --capturas"),
    ("titular", "str", "no", "1-300 chars; web only", "the article's og:title"),
]


def fold(s):
    return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")


def field(p, path):
    for k in path.split("."):
        if not isinstance(p, dict) or k not in p:
            return None
        p = p[k]
    return p


def matches(p, cond):
    m = re.match(r"^([\w.]+)(!=|>=|<=|~|=|>|<)(.*)$", cond)
    if not m:
        sys.exit(f"publicaciones: bad filter {cond!r}; use field OP value with OP one of = != ~ > >= < <=")
    k, op, want = m.groups()
    k = {"colonia": "colonias"}.get(k, k)
    v = field(p, k)
    vals = v if isinstance(v, list) else [v]
    if op == "!=":
        return not any(fold(x) == fold(want) for x in vals if x is not None) and not (v is None and want in ("", "null"))
    if op == "=":
        return (v is None and want in ("", "null")) or any(x is not None and fold(x) == fold(want) for x in vals)
    if op == "~":
        return any(x is not None and fold(want) in fold(x) for x in vals)
    try:
        a, b = float(v), float(want)
    except (TypeError, ValueError):
        if v is None:
            return False
        a, b = str(v), want
    return {">": a > b, ">=": a >= b, "<": a < b, "<=": a <= b}[op]


def cell(v):
    if isinstance(v, (dict, list)):
        v = json.dumps(v, ensure_ascii=False)
    return "" if v is None else str(v).replace("\t", " ").replace("\n", " ")


def query(doc, conds, fields, only_count, show_all):
    hits = [(i, p) for i, p in enumerate(doc["publicaciones"]) if all(matches(p, c) for c in conds)]
    if only_count:
        print(len(hits))
        return
    cols = fields.split(",") if fields else ["fuente", "fecha", "quien", "colonias", "dias", "url"]
    print("\t".join(["i", *cols]))
    for i, p in hits if show_all else hits[:50]:
        print("\t".join([str(i), *(cell(field(p, c)) for c in cols)]))
    if not show_all and len(hits) > 50:
        print(f"publicaciones: {len(hits)} match, 50 shown (--all for every row)", file=sys.stderr)


def assign(p, path, raw):
    keys = path.split(".")
    for k in keys[:-1]:
        if not isinstance(p.get(k), dict):
            p[k] = {}
        p = p[k]
    if raw == "":
        p.pop(keys[-1], None)
        return
    try:
        p[keys[-1]] = json.loads(raw)
    except ValueError:
        p[keys[-1]] = raw


def write(path, doc):
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    tmp.replace(path)


def edit(doc, data, cmd, rest):
    before = json.loads(json.dumps(doc["publicaciones"]))
    if cmd == "add":
        if len(rest) != 1:
            sys.exit("publicaciones: add FILE.json")
        new = json.loads(pathlib.Path(rest[0]).read_text())
        new = new if isinstance(new, list) else [new]
        start = len(doc["publicaciones"])
        doc["publicaciones"].extend(new)
        changes = [f"+ [{start + n}] {json.dumps(p, ensure_ascii=False)}" for n, p in enumerate(new)]
    else:
        if len(rest) < 2 or not rest[0].isdigit() or int(rest[0]) >= len(doc["publicaciones"]):
            sys.exit(f"publicaciones: set INDEX field=value ...; INDEX is 0..{len(doc['publicaciones']) - 1}")
        i = int(rest[0])
        p = doc["publicaciones"][i]
        changes = []
        for a in rest[1:]:
            if "=" not in a:
                sys.exit(f"publicaciones: bad assignment {a!r}; use field=value")
            k, raw = a.split("=", 1)
            old = field(p, k)
            assign(p, k, raw)
            new = field(p, k)
            if old != new or (old is None) != (new is None):
                changes.append(f"  [{i}] {k}: {json.dumps(old, ensure_ascii=False)} -> {json.dumps(new, ensure_ascii=False)}")
    validate(doc)
    if errors:
        sys.exit("publicaciones: not written; " + "invalid data:\n" + report(data.name))
    if doc["publicaciones"] == before:
        print("publicaciones: no change; not written")
        return
    write(data, doc)
    print("\n".join(changes))
    print(f"publicaciones: wrote {data}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="*", help="q COND... | schema | add FILE.json | set INDEX field=value ...")
    ap.add_argument("--schema", action="store_true", help="print each entry field's type, rule and meaning")
    ap.add_argument("--fields", help="q: comma-separated columns (dotted for nested)")
    ap.add_argument("--count", action="store_true", help="q: print only the number of matches")
    ap.add_argument("--all", action="store_true", help="q: every row, not the first 50")
    ap.add_argument("--data", type=pathlib.Path, default=DATA, help="the publicaciones.json to read and write")
    ap.add_argument("--check", action="store_true", help="validate only; write nothing")
    ap.add_argument("--eco", action="store_true", help="refresh the X posts' likes and replies, then write")
    ap.add_argument("--imagenes", action="store_true", help="download the posts' preview images, then write")
    ap.add_argument("--capturas", action="store_true", help="screenshot the news articles' headlines, then write")
    ap.add_argument("--videos", action="store_true", help="tag the X posts whose embed serves a video, then write")
    args = ap.parse_intermixed_args()
    cmd, rest = (args.cmd[0], args.cmd[1:]) if args.cmd else (None, [])
    if args.schema or cmd == "schema":
        print("\t".join(["field", "type", "required", "values", "meaning"]))
        for row in SCHEMA:
            print("\t".join(row))
        return
    if cmd not in (None, "q", "add", "set"):
        sys.exit(f"publicaciones: unknown command {cmd!r}")
    doc = json.loads(args.data.read_text())
    if cmd == "q":
        return query(doc, rest, args.fields, args.count, args.all)
    if cmd in ("add", "set"):
        return edit(doc, args.data, cmd, rest)
    if args.eco and not args.check:
        print(f"publicaciones: {refresh_x(doc)} X posts changed")
    if args.videos and not args.check:
        print(f"publicaciones: {detect_x_videos(doc)} X posts tagged as video")
    if args.capturas and not args.check:
        print(f"publicaciones: {fetch_captures(doc)} headline screenshots")
    if args.imagenes and not args.check:
        print(f"publicaciones: {fetch_images(doc)} images downloaded")
    validate(doc)
    if errors:
        sys.exit("publicaciones: " + "invalid data:\n" + report(args.data.name))
    if (args.eco or args.imagenes or args.capturas or args.videos) and not args.check:
        write(args.data, doc)
    pubs = doc["publicaciones"]
    cols = {k for p in pubs for k in p["colonias"]}
    medios = sum(p["fuente"] == "medio" for p in pubs)
    print(f"publicaciones: {len(pubs)} ({medios} de medios, {len(pubs) - medios} de vecinos), {len(cols)} colonias")


if __name__ == "__main__":
    main()
