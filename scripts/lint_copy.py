#!/usr/bin/env python3
"""Flag wording that claims intent («miente», «engañó»…) in the site's and the bot's copy.

    python3 scripts/lint_copy.py    scan web/*.html and api/internal/bot/messages.go; exit 1 on a hit

Uses BANNED from pipelines/copy_rules.py (as pipelines/promesas.py does). Text inside «…», <q> and
<blockquote> is a quote and is skipped. «israelí» is warn-only here: pages name the State of Israel
legitimately, so only the adjective outside quotes is reported, and it never fails the run.
"""
import html
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "pipelines"))
from copy_rules import BANNED, plain  # noqa: E402

ISRAELI = re.compile(r"\bisraeli(es|as?|os?)?\b")
QUOTE = re.compile(r"«[^«»]*»")


def blank(m):
    return re.sub(r"[^\n]", " ", m.group(0))


def visible_html(text):
    text = re.sub(r"<!--.*?-->", blank, text, flags=re.S)
    text = re.sub(r"<(script|style|q|blockquote)\b.*?</\1\s*>", blank, text, flags=re.S | re.I)
    text = re.sub(r"<[^>]*>", blank, text, flags=re.S)
    return html.unescape(text)


def go_strings(text):
    # Keep only string literals ("…" and `…`), so identifiers and comments don't count.
    # One left-to-right pass, so a // inside a string and a "…" inside a comment both stay
    # what they are; rune literals are matched so '"' doesn't open a string.
    out = [" " if c != "\n" else "\n" for c in text]
    for m in re.finditer(r'"(?:[^"\\\n]|\\.)*"|`[^`]*`|//[^\n]*|/\*.*?\*/|\'(?:[^\'\\\n]|\\.)*\'', text, re.S):
        if m.group(0)[0] in '"`':
            out[m.start():m.end()] = m.group(0)
    return "".join(out)


def scan(path, text):
    hits, warns = [], []
    text = QUOTE.sub(blank, text)
    for n, line in enumerate(text.splitlines(), 1):
        p = plain(line)
        for m in BANNED.finditer(p):
            hits.append(f"{path}:{n}: «{m.group(0)}» outside a quote")
        for m in ISRAELI.finditer(p):
            warns.append(f"{path}:{n}: «{m.group(0)}» outside a quote (warning)")
    return hits, warns


def main():
    hits, warns = [], []
    for f in sorted((root / "web").glob("*.html")):
        h, w = scan(f.relative_to(root), visible_html(f.read_text(encoding="utf-8")))
        hits += h
        warns += w
    go = root / "api/internal/bot/messages.go"
    h, w = scan(go.relative_to(root), go_strings(go.read_text(encoding="utf-8")))
    hits += h
    warns += w
    for line in warns + hits:
        print(line)
    if hits:
        print(f"{len(hits)} hit(s): wording that claims intent belongs only inside «…», <q> or <blockquote>")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
