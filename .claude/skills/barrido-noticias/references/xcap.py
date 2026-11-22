"""Read X statuses through X's public embed endpoint (as publicaciones.py --eco does), with the posts they answer.

Usage: python3 xcap.py AGENT.json OUT.json
AGENT.json is a search agent's saved reply (a list, or {"items": [...]}); every x.com/.../status/<id> in an item's
url or parent_url is fetched, then each status's reply_to, recursively. OUT.json maps id -> {text, created (UTC),
likes, replies, reply_to, user}, or {error}: "gone" when X serves a tombstone or no counts (deleted, private or
withheld: drop it). A text that is only a link means the words are in an image: the quote can't be checked, so drop
it. Guadalajara day = created minus 6 h. Exits 1 when no status id was found or any fetch failed: a parent that
fails can't show the reply meets the threshold, so retry it or drop the reply.
"""
import json, os, re, sys, time, urllib.parse, urllib.request
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../../../pipelines'))
from publicaciones import token

A = json.load(open(sys.argv[1]))
ids = set()
for it in (A.get('items') or [] if isinstance(A, dict) else A):
    for u in (it.get('url') or '', it.get('parent_url') or ''):
        m = re.search(r'status/(\d+)', u)
        if m:
            ids.add(m.group(1))


def get(i):
    q = urllib.parse.urlencode({"id": i, "token": token(i), "lang": "es"})
    req = urllib.request.Request(f"https://cdn.syndication.twimg.com/tweet-result?{q}", headers={"User-Agent": "aguagdl-publicaciones"})
    t = json.loads(urllib.request.urlopen(req, timeout=20).read() or b'{}')
    if t.get("__typename") == "TweetTombstone" or "tombstone" in t or t.get("favorite_count") is None:
        return {"error": "gone"}
    return {"text": t.get("text"), "created": t.get("created_at"), "likes": t.get("favorite_count"), "replies": t.get("conversation_count"),
            "reply_to": t.get("in_reply_to_status_id_str"), "user": (t.get("user") or {}).get("screen_name")}


if not ids:
    sys.exit(f'xcap: no x.com status id in {sys.argv[1]}')
out, todo = {}, sorted(ids)
while todo:
    i = todo.pop()
    if i in out:
        continue
    try:
        out[i] = get(i)
    except Exception as e:
        out[i] = {"error": str(e)}
        continue
    finally:
        time.sleep(0.4)
    p = out[i].get('reply_to')
    if p and p not in out:
        todo.append(p)
json.dump(out, open(sys.argv[2], 'w'), ensure_ascii=False, indent=1)
img = [i for i, v in out.items() if re.fullmatch(r'(@\w+\s+)*https://t\.co/\w+', (v.get('text') or '').strip())]
err = {i: v['error'] for i, v in out.items() if 'error' in v}
print(len(ids), 'ids from the agent,', len(out), 'statuses with parents;', len(err), 'errors', err or '', '; text only a link (words in an image):', img)
sys.exit(1 if err else 0)
