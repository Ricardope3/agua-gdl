"""Save an agent's JSON reply without retyping it.

Usage: python3 -I pull_json.py TASK_OUTPUT_FILE OUT.json
Takes the agent's final reply (the last message in its task output that holds a ```json block; it
stops if that message isn't among the file's last lines, since an earlier block may be an example
from the prompt), merges every ```json block in it, writes OUT.json and, for a verifier's
{"verified": [...], "rejected": [...]}, lists the entries whose cita (split on «[…]» or «[...]»)
is not in captura.texto, whitespace normalised. An entry with no captura is listed too.
"""
import json
import re
import sys

lines = open(sys.argv[1]).read().splitlines()
last = None  # (line number, text)


def walk(x, n):
    global last
    if isinstance(x, str):
        if "```json" in x:
            last = (n, x)
    elif isinstance(x, dict):
        for v in x.values():
            walk(v, n)
    elif isinstance(x, list):
        for v in x:
            walk(v, n)


for n, line in enumerate(lines):
    try:
        walk(json.loads(line), n)
    except ValueError:
        pass
if not last:
    sys.exit("no ```json block in " + sys.argv[1])
if last[0] < len(lines) - 6:
    sys.exit(f"the last ```json block is on line {last[0] + 1} of {len(lines)}: not the final reply; ask the agent to resend its reply in a ```json block")
blocks = [json.loads(b) for b in re.findall(r"```json\s*(.*?)```", last[1], re.S)]
if len(blocks) == 1:
    data = blocks[0]
elif all(isinstance(b, dict) for b in blocks):
    data = {k: v for b in blocks for k, v in b.items()}
else:
    sys.exit(f"{len(blocks)} json blocks that aren't objects: ask the agent for one {{\"verified\": [...], \"rejected\": [...]}}")
json.dump(data, open(sys.argv[2], "w"), ensure_ascii=False, indent=1)


def norm(s):
    return re.sub(r"\s+", " ", s or "").strip()


if isinstance(data, dict) and "verified" in data:
    miss = [v.get("url") for v in data["verified"]
            if not v.get("cita") or not (v.get("captura") or {}).get("texto")
            or any(norm(p) not in norm(v["captura"]["texto"]) for p in re.split(r"\[…\]|\[\.\.\.\]", v["cita"]))]
    print(len(data["verified"]), "verified,", len(data.get("rejected", [])), "rejected; quote misses or no cita/captura:", miss)
else:
    print(len(data), "items")
