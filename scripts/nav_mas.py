#!/usr/bin/env python3
"""One-off: reorder the top nav to Hay agua / No cuadra / Avisos / Cisternas /
Noticias and collapse the rest into a 'Más' dropdown (<details>, no JS)."""
import re
import sys
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"

PRIMARY = ["/reportes", "/nocuadra", "/avisos", "/cisternas", "/noticias"]

CSS = (
    ".site-nav details { position: relative; flex: 0 0 auto }\n"
    ".site-nav summary { list-style: none; display: inline-flex; align-items: center; gap: 4px;"
    " padding: 6px; border-radius: 8px; color: var(--muted); font-size: .9rem; font-weight: 500;"
    " cursor: pointer; white-space: nowrap }\n"
    ".site-nav summary::-webkit-details-marker { display: none }\n"
    ".site-nav summary::after { content: \"\"; width: 7px; height: 7px; margin-left: 2px;"
    " border-right: 1.5px solid currentColor; border-bottom: 1.5px solid currentColor;"
    " transform: rotate(45deg) translateY(-2px) }\n"
    ".site-nav summary:hover, .site-nav details[open] summary { color: var(--fg); background: var(--subtle) }\n"
    ".site-nav details[open] summary::after { transform: rotate(225deg) translate(-2px, -1px) }\n"
    ".site-nav .mas-panel { position: absolute; right: 0; top: calc(100% + 6px); display: flex;"
    " flex-direction: column; min-width: 210px; padding: 6px; background: var(--surface);"
    " border: 1px solid var(--line); border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,.16); z-index: 60 }\n"
    ".site-nav .mas-panel a { display: flex; padding: 8px 10px }\n"
    "@media (max-width: 760px) { .site-nav details { flex: 1 1 22% } .site-nav summary { width: 100%;"
    " justify-content: center; padding: 6px 4px } }\n"
    "@media (max-width: 560px) { .site-nav summary { padding: 4px; font-size: .82rem; line-height: 1.35 } }\n"
)

NAV_RE = re.compile(r'(<nav class="site-nav"[^>]*>)(.*?)(</nav>)', re.S)
ANCHOR_CURRENT = re.compile(
    r"(\.site-nav a\[aria-current=\"page\"\] \{[^}]*\}\n)")
ANCHOR_BASE = re.compile(r"(\.site-nav a \{[^}]*\}\n)")


def href(link):
    return re.search(r'href="([^"]+)"', link).group(1)


def main():
    changed = []
    for path in sorted(WEB.glob("*.html")):
        text = path.read_text(encoding="utf-8")
        m = NAV_RE.search(text)
        if not m:
            continue
        inner = m.group(2)
        if 'class="nav-more"' in inner:
            continue
        links = re.findall(r'<a [^>]*>.*?</a>', inner, re.S)
        if len(links) < 5:
            sys.exit(f"{path.name}: only {len(links)} links, unexpected")

        primary, extra = [], []
        for link in links:
            (primary if href(link) in PRIMARY else extra).append(link)
        missing = [h for h in PRIMARY if h not in {href(l) for l in primary}]
        if missing:
            sys.exit(f"{path.name}: missing primary links {missing}")

        primary.sort(key=lambda l: PRIMARY.index(href(l)))
        mas = (
            '<details class="nav-more"><summary>Más</summary>\n'
            '        <div class="mas-panel">\n'
            + "\n".join("          " + l for l in extra)
            + "\n        </div></details>"
        )
        new_inner = "\n      ".join(primary) + "\n      " + mas + "\n    "
        new_text = text[: m.start(2)] + new_inner + text[m.end(2):]

        anchor = ANCHOR_CURRENT.search(new_text) or ANCHOR_BASE.search(new_text)
        if not anchor:
            print(f"skipped {path.name}: CSS anchor not found")
            continue
        insert_at = anchor.end(1)
        new_text = new_text[:insert_at] + CSS + new_text[insert_at:]

        path.write_text(new_text, encoding="utf-8")
        changed.append(path.name)
    print(f"updated {len(changed)} files:")
    print("\n".join(changed))


if __name__ == "__main__":
    main()
