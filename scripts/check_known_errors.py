#!/usr/bin/env python3
"""Fail when a known factual error comes back anywhere it could be published or filed.

    python3 scripts/check_known_errors.py            scan the repo, plus research/ when present
    python3 scripts/check_known_errors.py PATH ...   scan these files or folders too (e.g. ~/agua-gdl-notes)

The errors live in KNOWN_ERRORS (pipelines/copy_rules.py). Unlike lint_copy.py this reads inside
quotes too: several errors were misquotes. research/ is gitignored, so CI scans only tracked files.
Review records quote the errors on purpose and are skipped: fact-check-* files, error-hunt-* folders,
findings.json in verification-* folders and experiment «-before-» snapshots.
"""
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "pipelines"))
from copy_rules import known_errors  # noqa: E402

SUFFIXES = {".html", ".json", ".md", ".py", ".go", ".txt", ".yml", ".mjs", ".js", ".ics", ".xml", ".svg", ".csv", ".webmanifest"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", "worktrees", "combined", "text", "extracted", "ocr-images", "public-sources", "responses", "captures"}
SKIP_FILES = {root / "pipelines/copy_rules.py"}
DEFAULT = ["web", "docs", ".claude", ".github", "pipelines", "experiments", "api", "AGENTS.md", "README.md", "research"]

def files(paths):
    for p in paths:
        if p.is_file():
            yield p
        elif p.is_dir():
            for f in sorted(p.rglob("*")):
                if (f.is_file() and f.suffix in SUFFIXES and not f.name.startswith("fact-check-") and not (f.name == "findings.json" and any(d.startswith(("verification-", "error-hunt-")) for d in f.parts)) and not ("-before-" in f.name and "experiments" in f.parts)
                        and not any(d.startswith("error-hunt-") for d in f.relative_to(p).parts[:-1])
                        and not SKIP_DIRS & set(f.relative_to(p).parts[:-1])):
                    yield f


def scan(f):
    hits = []
    try:
        text = f.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None
    if f.suffix == ".ics":
        # A calendar folds long lines mid-word (newline + space) and escapes commas: read the
        # logical lines, so the line numbers are theirs, not the file's.
        text = re.sub(r"\\([,;])", r"\1", re.sub(r"\r?\n[ \t]", "", text)).replace("\\n", " ").replace("\\N", " ")
    for n, line in enumerate(text.splitlines(), 1):
        for e, m in known_errors(line):
            hits.append(f"{f}:{n}: [{e['id']}] «{line.strip()[max(0, m.start() - 40):m.end() + 40]}»: {e['msg']}")
    return hits


def main(argv):
    paths = [root / p for p in DEFAULT if (root / p).exists()] + [pathlib.Path(a).expanduser() for a in argv]
    read = {f: scan(f) for f in files(paths) if f.resolve() not in SKIP_FILES}
    scanned = [f for f, found in read.items() if found is not None]
    hits = [h for f in scanned for h in read[f]]
    for h in hits:
        print(h)
    calendars = sum(f.suffix == ".ics" for f in scanned)
    print(f"{len(scanned)} files scanned, {calendars} of them calendars; {len(read) - len(scanned)} unreadable as UTF-8")
    if not scanned or (not calendars and (root / "web/calendario").is_dir()):
        print("nothing to scan: the check covered no files, or none of web/calendario's calendars")
        return 1
    if hits:
        print(f"{len(hits)} known error(s) found; fix them or, if the line is right, make it state the correct form")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
