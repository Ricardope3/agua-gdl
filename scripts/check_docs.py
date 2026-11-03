#!/usr/bin/env python3
"""Check that the agent docs point at things that exist.

    python3 scripts/check_docs.py    exit 1 if AGENTS.md, .claude/rules/*.md or web/llms.txt is stale

- A backticked repo path (`web/x.html`, `cmd/notify`, `promesas.py`) exists: from the repo root, under
  api/ (Go packages), or, for a bare file name, anywhere in the repo.
- A backticked `X.py --flag` mention: pipelines/X.py (or the file of that name) defines "--flag".
- Every /v1 route in web/llms.txt is registered in api/cmd/server/api.go's mux.
URLs, globs, placeholders, the private notes repo (~/agua-gdl-notes) and SIAPA's own remote paths are
in ALLOW or skipped by shape.
"""
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parent.parent
DOCS = [root / "AGENTS.md", *sorted((root / ".claude/rules").glob("*.md")), root / "web/llms.txt"]
SKIP_DIRS = {".git", "node_modules", "__pycache__"}
# SIAPA's remote files, the notes repo and server paths on Fly: not in this repo.
ALLOW = {
    "ajustes.php", "api/ajustes.php", "colonias_siapa.pdf", "/geo/rotacion-siapa.topo.json",
    "projects/promesometro.md", "/data/web-reports.wal", "/data",
    # Removed or only in git history / the notes repo, as the docs say.
    "reportes-before-c3.html", "resultados.html", "aguagdl.png",
    "web/semana/",  # cmd/informe creates it on the first published count
}
TOP = ("api/", "web/", "pipelines/", "scripts/", "docs/", ".claude/", ".github/", ".githooks/",
       "experiments/", "research/", "infra/", "internal/", "cmd/", "aguagdl_favicon/", "vendor/", "img/")
EXT = re.compile(r"\.(py|go|html|json|md|mjs|js|sh|toml|yml|csv|geojson|svg|png|jpg|txt|ics|xml|wal|ico)$")

files = set()
names = set()
for p in root.rglob("*"):
    if SKIP_DIRS & set(p.relative_to(root).parts):
        continue
    rel = p.relative_to(root).as_posix()
    files.add(rel + ("/" if p.is_dir() else ""))
    files.add(rel)
    names.add(p.name)

errors = []


def exists(path):
    path = path.rstrip("/")
    for base in ("", "api/", "web/", "pipelines/", "experiments/"):
        if base + path in files:
            return True
    return "/" not in path and path in names


def is_path(tok):
    if " " in tok or tok in ALLOW or tok.startswith(("~", "http", "/", "?", "#", "-")):
        return False
    if any(c in tok for c in "*<>…|:=(){}'\"$") or re.search(r"\bN\b|zona-N|PATH|DIR|FILE", tok):
        return False
    return tok.startswith(TOP) or bool(EXT.search(tok)) and not tok.startswith(".") or tok.startswith(".claude/")


def script_for(name):
    for cand in (root / "pipelines" / name, *root.glob(f"**/{name}")):
        if cand.is_file() and not (SKIP_DIRS & set(cand.relative_to(root).parts)):
            return cand
    return None


for doc in DOCS:
    rel = doc.relative_to(root)
    for n, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
        for tok in re.findall(r"`([^`\n]+)`", line):
            if is_path(tok) and not exists(tok):
                errors.append(f"{rel}:{n}: `{tok}` does not exist")
            for m in re.finditer(r"([\w/]+\.py)((?:\s+--?[\w-]+(?:\s+[A-Z]+)?)+)", tok):
                script = script_for(pathlib.PurePath(m.group(1)).name)
                if script is None:
                    errors.append(f"{rel}:{n}: `{m.group(1)}` does not exist")
                    continue
                src = script.read_text(encoding="utf-8")
                for flag in re.findall(r"--[\w-]+", m.group(2)):
                    if f'"{flag}"' not in src:
                        errors.append(f"{rel}:{n}: {script.relative_to(root)} has no {flag}")

routes = set(re.findall(r'mux\.HandleFunc\("(?:[A-Z]+ )?(/v1/[\w/]+)"', (root / "api/cmd/server/api.go").read_text(encoding="utf-8")))
for n, line in enumerate((root / "web/llms.txt").read_text(encoding="utf-8").splitlines(), 1):
    for route in re.findall(r"api\.aguagdl\.com(/v1/[\w/]+)", line):
        if route not in routes:
            errors.append(f"web/llms.txt:{n}: {route} is not in api/cmd/server/api.go's mux")

for e in errors:
    print(e)
sys.exit(1 if errors else 0)
