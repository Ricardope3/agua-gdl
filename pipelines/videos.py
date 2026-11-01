"""Videos referenced by /reportes' publications: write web/videos.json, the download list.

    python3 pipelines/videos.py            write web/videos.json from web/publicaciones.json
    python3 pipelines/videos.py --check    fail if web/videos.json is stale; for CI

Each entry of web/publicaciones.json tagged "video": true (a reel, a YouTube video, an X post whose
embed serves one) becomes a record here: the post's link, who published it, the date, the colonias
and the quote, plus a "video" field reserved for the downloaded file's path (null until a future
run downloads the evidence). The JSON is the input for that downloader and for a future video wall.
"""
import json
import pathlib
import sys

root = pathlib.Path(__file__).resolve().parent.parent
DATA = root / "web/publicaciones.json"
OUT = root / "web/videos.json"


def build():
    doc = json.loads(DATA.read_text())
    vids = []
    for p in doc.get("publicaciones") or []:
        if p.get("video") is not True:
            continue
        vids.append(
            {
                "url": p["url"],
                "red": p.get("red"),
                "quien": p.get("quien", ""),
                "fecha": p.get("fecha"),
                "colonias": p.get("colonias") or [],
                "lugar": p.get("lugar", ""),
                "cita": p.get("cita", ""),
                "dias": p.get("dias"),
                "video": p.get("archivo"),
            }
        )
    return {"actualizado": doc.get("actualizado"), "videos": vids}


def main():
    want = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    if "--check" in sys.argv:
        if not OUT.is_file() or OUT.read_text() != want:
            sys.exit("videos.json is stale: run python3 pipelines/videos.py")
        print(f"videos.json: up to date ({want.count(chr(10))} lines)")
        return
    OUT.write_text(want)
    print(f"wrote {OUT.relative_to(root)} ({want.count(chr(10))} lines)")


if __name__ == "__main__":
    main()
