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

Each entry quotes a news outlet ("medio") or neighbours ("vecinos") saying a colonia has no water, with
its link, date and SIAPA colonias. Neighbours' posts count only with at least regla.reacciones reactions
and regla.comentarios comments; news outlets count without. A neighbour's comment ("tipo": "comentario")
counts by the post it is in ("en"), whose reactions and comments must meet the rule. A news story that
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
PAGINAS = {"Jalisco ZMG", "SIAPA Guadalajara"}

errors = []


def fail(msg):
    errors.append(msg)


def date(s, where):
    try:
        d = datetime.date.fromisoformat(s)
    except (TypeError, ValueError):
        fail(f"{where}: bad date {s!r}")
        return None
    if d > TODAY:
        fail(f"{where}: date {s} is in the future")
    return d


def count(v):
    return isinstance(v, int) and not isinstance(v, bool) and v >= 0


def validate(doc):
    keys = {"|".join(c[:3]) for c in json.loads(COLONIAS.read_text())}
    updated = date(doc.get("actualizado"), "actualizado")
    since = date(doc.get("desde"), "desde")
    rule = doc.get("regla") or {}
    if not (count(rule.get("reacciones")) and count(rule.get("comentarios"))):
        fail("regla: needs reacciones and comentarios")
    seen = set()
    pages = PAGINAS | {p["quien"] for p in doc.get("publicaciones") or [] if p.get("fuente") == "medio" and isinstance(p.get("quien"), str)}
    for i, p in enumerate(doc.get("publicaciones") or []):
        where = f"publicaciones[{i}] {p.get('url', '')}"
        if p.get("fuente") not in FUENTES:
            fail(f"{where}: fuente must be one of {sorted(FUENTES)}")
        red = p.get("red")
        url = p.get("url", "")
        if red not in REDES:
            fail(f"{where}: red must be one of {sorted(REDES)}")
        elif red == "x" and not X_URL.match(url):
            fail(f"{where}: an X post links x.com/<account>/status/<id>")
        elif red == "facebook" and not url.startswith("https://www.facebook.com/"):
            fail(f"{where}: a Facebook post links https://www.facebook.com/…")
        elif red == "web" and (not url.startswith("https://") or re.match(r"https://(www\.)?(facebook|x|twitter)\.com/", url)):
            fail(f"{where}: a web article links its https page")
        # One article can name several colonias with different days: one entry per quote.
        if (url, p.get("cita")) in seen:
            fail(f"{where}: listed twice")
        seen.add((url, p.get("cita")))
        if "de" in p and not (p.get("fuente") == "medio" and str(p["de"]).startswith("https://")):
            fail(f"{where}: de is the https post a news story retells")
        quien = p.get("quien")
        if not isinstance(quien, str):
            fail(f"{where}: quien must be a string")
        elif p.get("fuente") == "medio" and not quien:
            fail(f"{where}: a news outlet is named")
        elif p.get("fuente") == "vecinos" and quien and not quien.startswith(VECINOS_QUIEN):
            fail(f"{where}: neighbours are never named; quien is empty, «Grupo «…»» or «Cuenta de vecinos …»")
        d = date(p.get("fecha"), where)
        if d and since and d < since:
            fail(f"{where}: fecha before desde")
        if d and updated and d > updated:
            fail(f"{where}: fecha after actualizado")
        cols = p.get("colonias")
        if not cols or not isinstance(cols, list):
            fail(f"{where}: needs colonias")
        for k in cols or []:
            if k not in keys:
                fail(f"{where}: colonia {k!r} isn't in api/data/colonias_mapa.json")
        if not p.get("lugar"):
            fail(f"{where}: needs lugar, the place as the post names it")
        cita = p.get("cita")
        if not isinstance(cita, str) or not cita.strip() or len(cita) > 400 or "http" in cita:
            fail(f"{where}: cita is the post's own words, 1 to 400 characters, without links")
        dias = p.get("dias")
        if dias is not None and not (count(dias) and 1 <= dias <= 120):
            fail(f"{where}: dias is null or 1 to 120")
        if "desde" in p:
            s = date(p["desde"], where)
            if s and d and s > d:
                fail(f"{where}: desde after fecha")
        if "bloqueo" in p and p["bloqueo"] is not True:
            fail(f"{where}: bloqueo is true or absent")
        if p.get("vista") is not None and not (isinstance(p["vista"], str) and IMAGEN.match(p["vista"]) and (WEB / p["vista"]).is_file()):
            fail(f"{where}: vista is null (no useful image) or fuentes/<12 hex>.jpg, in web/")
        if p.get("captura") is not None and not (isinstance(p["captura"], str) and CAPTURA.match(p["captura"]) and (WEB / p["captura"]).is_file()):
            fail(f"{where}: captura is null or fuentes/<12 hex>-t.jpg, in web/")
        if "titular" in p and not (red == "web" and isinstance(p["titular"], str) and 0 < len(p["titular"]) <= 300):
            fail(f"{where}: titular is a news article's headline, 1 to 300 characters")
        eco = p.get("eco")
        check_eco(eco, where)
        # A comment counts by the thread it is in: the post's reactions and comments meet the rule.
        tipo = p.get("tipo")
        if tipo not in (None, "comentario"):
            fail(f"{where}: tipo is absent or comentario")
        if tipo == "comentario":
            en = p.get("en") or {}
            if not en.get("quien") or not str(en.get("url", "")).startswith("https://www.facebook.com/"):
                fail(f"{where}: a comment names the post it is in (en.quien, en.url)")
            elif not url.startswith(en["url"] + "?comment_id="):
                fail(f"{where}: a comment links its post with ?comment_id=")
            if en.get("quien") and not (str(en["quien"]) in pages or str(en["quien"]).startswith(VECINOS_QUIEN)):
                fail(f"{where}: en.quien is never a person: an outlet with a medio entry, «Grupo «…»», «Cuenta de vecinos …» or one of PAGINAS")
            check_eco(en.get("eco"), where + " en")
            eco = en.get("eco")
        if p.get("fuente") == "vecinos":
            if eco is None:
                fail(f"{where}: a neighbours' post needs eco")
            elif count(eco.get("reacciones")) and count(eco.get("comentarios")) and (
                    eco["reacciones"] < rule.get("reacciones", 0) or eco["comentarios"] < rule.get("comentarios", 0)):
                fail(f"{where}: below the rule ({eco['reacciones']} reactions, {eco['comentarios']} comments)")


def check_eco(eco, where):
    if eco is None:
        return
    if not (count(eco.get("reacciones")) and count(eco.get("comentarios"))):
        fail(f"{where}: eco needs reacciones and comentarios")
    if "compartidos" in eco and not count(eco["compartidos"]):
        fail(f"{where}: eco.compartidos is a count")
    date(eco.get("al"), where)


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
        red = "facebook" if p.get("tipo") == "comentario" else p["red"]
        name = f"fuentes/{hashlib.sha1(url.encode()).hexdigest()[:12]}.jpg"
        if (WEB / name).is_file():
            p["vista"] = name
            continue
        try:
            if red == "x":
                src = x_image(url)
            elif red == "facebook":
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="validate only; write nothing")
    ap.add_argument("--eco", action="store_true", help="refresh the X posts' likes and replies, then write")
    ap.add_argument("--imagenes", action="store_true", help="download the posts' preview images, then write")
    ap.add_argument("--capturas", action="store_true", help="screenshot the news articles' headlines, then write")
    args = ap.parse_args()
    doc = json.loads(DATA.read_text())
    if args.eco and not args.check:
        print(f"publicaciones: {refresh_x(doc)} X posts changed")
    if args.capturas and not args.check:
        print(f"publicaciones: {fetch_captures(doc)} headline screenshots")
    if args.imagenes and not args.check:
        print(f"publicaciones: {fetch_images(doc)} images downloaded")
    validate(doc)
    if errors:
        sys.exit("publicaciones: " + "\n  ".join(["invalid data:", *errors]))
    if (args.eco or args.imagenes or args.capturas) and not args.check:
        DATA.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n")
    pubs = doc["publicaciones"]
    cols = {k for p in pubs for k in p["colonias"]}
    medios = sum(p["fuente"] == "medio" for p in pubs)
    print(f"publicaciones: {len(pubs)} ({medios} de medios, {len(pubs) - medios} de vecinos), {len(cols)} colonias")


if __name__ == "__main__":
    main()
