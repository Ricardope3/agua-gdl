"""Save an agent's JSON reply without retyping it.

Usage: python3 -I pull_json.py TASK_OUTPUT_FILE OUT.json
Takes the agent's final reply (its last text or hand-back message in the task output; it stops if
that message isn't among the file's last lines), merges every ```json block in it, writes OUT.json and, for a verifier's
{"verified": [...], "rejected": [...]}, lists the entries whose cita (split on «[…]» or «[...]»)
is not in captura.texto, whitespace normalised. An entry with no captura is listed too.
A reply with no ```json block (21 Nov: an agent sent a bare array) falls back to the first JSON array
or object that starts a line of that same final reply, and only when it has the shape of a reply
(a list of objects with `url`, or an object with `verified` or `items`): tool results and the prompt
are never read (21 Nov review: a page's JSON in a tool result passed as the agent's reply).
"""
import json
import re
import sys

lines = open(sys.argv[1]).read().splitlines()
last = None  # (line number, text) of the agent's final reply


def replies(d):
    """The agent's own words in one transcript line: its text, or its hand-back message."""
    if d.get("type") != "assistant":
        return []
    out = []
    for b in (d.get("message") or {}).get("content") or []:
        if b.get("type") == "text":
            out.append(b.get("text") or "")
        elif b.get("type") == "tool_use" and "andback" in (b.get("name") or ""):
            out += [v for v in (b.get("input") or {}).values() if isinstance(v, str)]
    return [t for t in out if t.strip()]


def first_json(t):
    for m in re.finditer(r"^[\[{]", t, re.M):
        try:
            return json.JSONDecoder().raw_decode(t[m.start():])[0]
        except ValueError:
            pass


def shaped(j):
    if isinstance(j, list):
        return all(isinstance(x, dict) and "url" in x for x in j)
    return isinstance(j, dict) and any(isinstance(j.get(k), list) for k in ("verified", "items"))


for n, line in enumerate(lines):
    try:
        d = json.loads(line)
    except ValueError:
        continue
    for t in replies(d) if isinstance(d, dict) else []:
        last = (n, t)
if not last:
    sys.exit("no reply from the agent in " + sys.argv[1])
if last[0] < len(lines) - 6:
    sys.exit(f"the agent's last reply is on line {last[0] + 1} of {len(lines)}: not the final reply; ask the agent to resend it in a ```json block")
if "```json" in last[1]:
    blocks = [json.loads(b) for b in re.findall(r"```json\s*(.*?)```", last[1], re.S)]
else:
    j = first_json(last[1])
    if j is None or not shaped(j):
        sys.exit("the final reply has no ```json block and no bare JSON shaped like a reply: ask the agent to resend it in a ```json block")
    blocks = [j]
    print(f"bare JSON taken from the final reply (line {last[0] + 1})")
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
