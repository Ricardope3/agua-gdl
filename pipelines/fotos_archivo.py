"""Private archive of the photos behind the site's previews: research/fotos/ in the main checkout.

    python3 pipelines/fotos_archivo.py                 fetch what isn't archived yet, then write the manifest
    python3 pipelines/fotos_archivo.py --again         fetch every photo again
    python3 pipelines/fotos_archivo.py --dest DIR      archive somewhere else

web/fuentes/ keeps 480 px previews only. For each preview (publicaciones.json vistas) and each /noticias
photo or video thumbnail, this fetches the largest copy its source still serves (an X post's media at
name=orig, an article's or a public Facebook post's og:image, YouTube's maxresdefault), and keeps it only
when it has the preview's proportions; otherwise it copies the preview and marks original false (posts
captured from a logged-in browser, deleted posts, our text-only cards). manifest.json lists each file with
its sha256, the posts that use it (url, date in Guadalajara, quien, colonias) and its /fotos tema.
research/ is gitignored: nothing here is published.
"""
import datetime
import hashlib
import json
import pathlib
import re
import shutil
import subprocess
import sys
import time
import urllib.error
from zoneinfo import ZoneInfo

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fotos  # noqa: E402
import publicaciones as pub  # noqa: E402

root = pathlib.Path(__file__).resolve().parent.parent
WEB = root / "web"


def main_checkout():
    common = subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"], cwd=root, capture_output=True, text=True).stdout.strip()
    return pathlib.Path(common).parent if common else root


def kind(b):
    if b[:3] == b"\xff\xd8\xff":
        return "jpg"
    if b[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if b[:4] == b"RIFF" and b[8:12] == b"WEBP":
        return "webp"
    return None


def size(path, ext):
    if ext == "png":
        b = path.read_bytes()[16:24]
        return int.from_bytes(b[:4], "big"), int.from_bytes(b[4:], "big")
    return fotos.dims(path)


def candidates(url, red):
    yt = re.search(r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([\w-]{11})", url)
    if yt:
        return [f"https://i.ytimg.com/vi/{yt.group(1)}/maxresdefault.jpg", f"https://i.ytimg.com/vi/{yt.group(1)}/hqdefault.jpg"]
    if pub.X_URL.match(url):
        src = pub.x_image(url)
        return [re.sub(r"\?name=\w+$", "", src) + "?name=orig", src] if src else []
    if red == "facebook" or "facebook.com" in url:
        src = pub.og_image(url, "facebookexternalhit/1.1")
        return [src] if src else []
    if "tiktok.com" in url:
        return []
    try:
        src = pub.og_image(url)
    except urllib.error.HTTPError:
        src = pub.og_image(f"https://web.archive.org/web/2026id_/{url}")
    return [src] if src else []


def sources():
    """Every saved image with the posts that use it."""
    by = {}
    for p in json.loads(fotos.PUB.read_text())["publicaciones"]:
        v = p.get("vista")
        if not v:
            continue
        com = p.get("tipo") == "comentario"
        url = p["en"]["url"] if com else p["url"]
        e = by.setdefault(v, {"vista": v, "url": url, "red": "facebook" if com and p["red"] != "x" else p["red"], "fuentes": []})
        e["fuentes"].append({"url": p["url"], "fecha": p["fecha"], "quien": p["quien"] or (p["en"]["quien"] if com else ""),
                             "colonias": p["colonias"], **({"en": p["en"]["url"]} if com else {})})
    temas = json.loads(fotos.TEMAS.read_text())["temas"]
    for t in fotos.from_noticias({k: v for k, v in temas.items() if k.startswith("img/")} | {
            f"img/{d}/{f.name}": "" for d in ("noticias", "videos") for f in (WEB / "img" / d).iterdir()}):
        by[t["img"]] = {"vista": t["img"], "url": t["url"], "red": "x" if "x.com/" in t["url"] else "web",
                        "fuentes": [{"url": t["url"], "fecha": t["fecha"], "quien": t["quien"], "colonias": []}]}
    return by, temas


def main():
    args = sys.argv[1:]
    dest = pathlib.Path(args[args.index("--dest") + 1]) if "--dest" in args else main_checkout() / "research/fotos"
    dest.mkdir(parents=True, exist_ok=True)
    mpath = dest / "manifest.json"
    old = {e["vista"]: e for e in json.loads(mpath.read_text())["fotos"]} if mpath.is_file() else {}
    today = datetime.datetime.now(ZoneInfo("America/Mexico_City")).date().isoformat()
    by, temas = sources()
    out, got, kept = [], 0, 0
    for v, s in sorted(by.items()):
        prev = WEB / v
        if not prev.is_file():
            print(f"  {v}: preview missing", file=sys.stderr)
            continue
        pw, ph = fotos.dims(prev)
        stem = pathlib.Path(v).stem
        e = old.get(v)
        if e and (dest / e["archivo"]).is_file() and "--again" not in args:
            e.update({"fuentes": s["fuentes"], "tema": temas.get(v)})
            out.append(e)
            continue
        e = None
        if not v.startswith("img/noticias/"):
            try:
                cands = candidates(s["url"], s["red"])
            except (OSError, ValueError, KeyError, TypeError) as err:
                print(f"  {v}: {s['url']}: {err}", file=sys.stderr)
                cands = []
            for src in cands:
                try:
                    data = pub.get(src)
                except (OSError, ValueError):
                    continue
                ext = kind(data)
                if not ext:
                    continue
                f = dest / f"{stem}.{ext}"
                f.write_bytes(data)
                w, h = size(f, ext)
                if w < pw or abs(w / h - pw / ph) > 0.03:
                    f.unlink()
                    continue
                e = {"archivo": f.name, "original": True, "imagen_url": src, "ancho": w, "alto": h}
                got += 1
                break
            time.sleep(0.4)
        if not e:
            f = dest / f"{stem}{prev.suffix}"
            shutil.copyfile(prev, f)
            e = {"archivo": f.name, "original": False, "imagen_url": None, "ancho": pw, "alto": ph}
            kept += 1
        b = (dest / e["archivo"]).read_bytes()
        e = {"vista": v, **e, "sha256": hashlib.sha256(b).hexdigest(), "bytes": len(b), "obtenida": today,
             "tema": temas.get(v), "fecha": min(x["fecha"] for x in s["fuentes"]), "fuentes": s["fuentes"]}
        out.append(e)
        print(f"  {v}: {'original ' + str(e['ancho']) + ' px' if e['original'] else 'preview only'}", file=sys.stderr)
    mpath.write_text(json.dumps({"actualizado": today, "nota": "Copias privadas de las fotos detrás de web/fuentes/ y /noticias. original: false = solo la vista de 480 px (o la imagen de /noticias); no se pudo bajar una más grande con las mismas proporciones.", "fotos": out}, ensure_ascii=False, indent=1) + "\n")
    print(f"fotos_archivo: {len(out)} photos in {dest} ({sum(e['original'] for e in out)} originals; this run fetched {got}, kept {kept} previews)")


if __name__ == "__main__":
    main()
