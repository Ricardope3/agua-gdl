#!/usr/bin/env python3
"""Write web/sitemap.xml from the pages themselves, so it can't drift from them.

Lists every web/*.html and web/colonia/*.html without a robots noindex, except /informes while it
has no weekly count. Colonia pages carry the rotation's checked date as lastmod (their only data
that changes); hand-edited pages carry none, since a guessed date is worse than no date.
Run after colonia_pages.py.

Usage: python3 pipelines/sitemap.py [--check]
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "web"
OUT = WEB / "sitemap.xml"
ORIGIN = "https://aguagdl.com"
NOINDEX = re.compile(r'<meta name="robots" content="[^"]*noindex', re.I)
EMPTY_INFORMES = "Aún no hay conteos semanales publicados"


def indexable(path):
    text = path.read_text(encoding="utf-8")
    if NOINDEX.search(text):
        return False
    if re.search(r"<meta[^>]*noindex", text, re.I):
        sys.exit(f"sitemap: {path.relative_to(ROOT)} has a noindex meta this script can't read; write it as <meta name=\"robots\" content=\"noindex\">")
    return not (path.name == "informes.html" and EMPTY_INFORMES in text)


def build():
    checked = json.loads((ROOT / "api" / "data" / "rotation.json").read_text())["checked"]
    pages = sorted(p for p in WEB.glob("*.html") if indexable(p))
    urls = [(f"{ORIGIN}/" if p.name == "index.html" else f"{ORIGIN}/{p.stem}", None) for p in pages]
    urls.sort(key=lambda u: u[0] != f"{ORIGIN}/")
    colonias = sorted(p for p in (WEB / "colonia").glob("*.html") if indexable(p))
    urls += [(f"{ORIGIN}/colonia/" if p.name == "index.html" else f"{ORIGIN}/colonia/{p.stem}", checked) for p in colonias]
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lines += [f"  <url><loc>{u}</loc>" + (f"<lastmod>{d}</lastmod>" if d else "") + "</url>" for u, d in urls]
    lines.append("</urlset>")
    return "\n".join(lines) + "\n", len(pages), len(colonias)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    xml, n_pages, n_col = build()
    if not n_pages or not n_col:
        sys.exit(f"sitemap: found {n_pages} pages and {n_col} colonia pages; expected both")
    if args.check:
        if not OUT.exists() or OUT.read_text(encoding="utf-8") != xml:
            sys.exit("web/sitemap.xml is stale: run python3 pipelines/sitemap.py")
        print(f"sitemap.xml: up to date ({n_pages} pages, {n_col} colonia pages)")
        return
    OUT.write_text(xml, encoding="utf-8")
    print(f"{OUT.relative_to(ROOT)}: {n_pages} pages, {n_col} colonia pages")


if __name__ == "__main__":
    main()
