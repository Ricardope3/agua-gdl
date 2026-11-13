#!/usr/bin/env python3
"""Check that the agent docs point at things that exist.

    python3 scripts/check_docs.py    exit 1 if AGENTS.md, .claude/rules/*.md, web/llms.txt, an agent or a skill is stale

- A backticked repo path (`web/x.html`, `cmd/notify`, `promesas.py`) exists: from the repo root, under
  api/ (Go packages), or, for a bare file name, anywhere in the repo.
- A backticked `X.py --flag` mention: pipelines/X.py (or the file of that name) defines "--flag".
- Every /v1 route in web/llms.txt is registered in api/cmd/server/api.go's mux.
- Agent docs (the above bar llms.txt, plus .claude/agents and skills) say how things are now: no «was removed»
  or «used to be»; a file named beside «git history» has its full path when a tracked file shares its name.
  Only these forms are caught (was/were/got/been removed, retired, deleted or ported; used to + a verb).
- .claude/rules/vetos.md stays under the line limit it states.
URLs, globs, placeholders, the private notes repo (~/agua-gdl-notes) and SIAPA's own remote paths are
in ALLOW or skipped by shape.
"""
import pathlib
import re
import subprocess
import sys

root = pathlib.Path(__file__).resolve().parent.parent
DOCS = [root / "AGENTS.md", *sorted((root / ".claude/rules").glob("*.md")), root / "web/llms.txt"]
# research/ is the private archive (gitignored here); its scripts must not stand in for this repo's (6 Nov: a
# research build.py shadowed experiments/historias/build.py).
SKIP_DIRS = {".git", "node_modules", "__pycache__", "research"}
# SIAPA's remote files, the notes repo and server paths on Fly: not in this repo.
ALLOW = {
    "ajustes.php", "api/ajustes.php", "colonias_siapa.pdf", "/geo/rotacion-siapa.topo.json",
    "projects/promesometro.md", "/data/web-reports.wal", "/data",
    # Removed or only in git history / the notes repo, as the docs say.
    "reportes-before-c3.html", "resultados.html", "aguagdl.png",
    "web/semana/",  # cmd/informe creates it on the first published count
    # Deliberately local only: gitignored or untracked, so absent in CI.
    "research/", "aguagdl_logo.png",
}
TOP = ("api/", "web/", "pipelines/", "scripts/", "docs/", ".claude/", ".github/", ".githooks/",
       "experiments/", "research/", "infra/", "internal/", "cmd/", "aguagdl_favicon/", "vendor/", "img/")
EXT = re.compile(r"\.(py|go|html|json|md|mjs|js|sh|toml|yml|csv|geojson|svg|png|jpg|txt|ics|xml|wal|ico)$")

# Tracked files only, so a path that exists just on this machine fails here as it would in CI.
files = set()
names = set()
tracked = subprocess.run(["git", "-C", str(root), "ls-files", "-z"], capture_output=True, check=True).stdout
for rel in tracked.decode().split("\0"):
    if not rel:
        continue
    parts = rel.split("/")
    files.add(rel)
    names.add(parts[-1])
    for i in range(1, len(parts)):
        files.add("/".join(parts[:i]))
        files.add("/".join(parts[:i]) + "/")

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
                named = root / m.group(1)
                if "/" in m.group(1):
                    # A named path must be that file, in this repo: no basename fallback, nothing under research/.
                    script = named if named.is_file() and not (SKIP_DIRS & set(pathlib.PurePath(m.group(1)).parts)) else None
                else:
                    script = script_for(m.group(1))
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

# Agent docs say how things are now (AGENTS.md): the story of a change belongs in git. Text inside «…» is quoted,
# not said. A file named as gone or in git history carries its full path when a tracked file shares its name
# (12 Nov: `videos.py` «is in git history» beside the live pipelines/videos.py).
PROSE = [d for d in DOCS if d.suffix == ".md"] + sorted(
    p for pat in ("agents/*.md", "skills/*/SKILL.md", "skills/*/references/*.md")
    for p in (root / ".claude").glob(pat) if p.is_file() and not any(q.is_symlink() for q in p.parents if q != root and root in q.parents))
HISTORY = re.compile(r"\b(?:was|were|got|been) (?:removed|retired|deleted|ported)\b|\bused to (?:be|have|do|say|show|read|write|build|run|link|live|open|play)\b", re.I)
prose_lines = 0
for doc in PROSE:
    rel = doc.relative_to(root)
    for n, line in enumerate(doc.read_text(encoding="utf-8").splitlines(), 1):
        prose_lines += 1
        said = re.sub(r"«[^»]*»", "", line)
        for m in HISTORY.finditer(said):
            errors.append(f"{rel}:{n}: «{m.group(0)}» tells the history; say how it is now")
        for sentence in re.split(r"(?<=[.;:]) ", said):
            if "git history" not in sentence:
                continue
            for tok in re.findall(r"`([^`\n/ ]+\.\w+)`", sentence):
                if tok in names:
                    errors.append(f"{rel}:{n}: `{tok}` is named beside «git history» but a tracked file has that name; give full paths")

# A size limit a doc states for itself is checked here, so it can't drift (AGENTS.md's is in .githooks/pre-commit).
vetos_file = root / ".claude/rules/vetos.md"
vetos = vetos_file.read_text(encoding="utf-8") if vetos_file.is_file() else ""
limit = re.search(r"keep this file under (\d+) lines", vetos)
if not limit:
    errors.append(".claude/rules/vetos.md: its line limit is not stated as «keep this file under N lines»")
elif len(vetos.splitlines()) >= int(limit.group(1)):
    errors.append(f".claude/rules/vetos.md: {len(vetos.splitlines())} lines, its own limit is under {limit.group(1)}")

for e in errors:
    print(e)
if len(PROSE) < 15 or prose_lines < 300:
    print(f"check_docs.py: read only {len(PROSE)} agent docs, {prose_lines} lines; expected the rules, skills and agents")
    sys.exit(1)
print(f"check_docs.py: {len(DOCS)} docs for paths, {len(PROSE)} agent docs ({prose_lines} lines) for history wording")
sys.exit(1 if errors else 0)
