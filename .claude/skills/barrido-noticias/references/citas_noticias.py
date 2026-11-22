"""citas_noticias.py SOURCE... [--html PATH] : check every «quote» in the /noticias lines added since HEAD.

The added lines are those of web/noticias.html (or PATH) that aren't in `git show HEAD:web/noticias.html`.
Each «…» quote (split on «[…]»), in the text or in an alt/title/aria-label, must appear, capitals and
accents included, on word boundaries, inside one paragraph of one source: a *.txt capture from
articulos.py (its URL/PUB lines left out) or one `cita` of a *.json entry list under a SOURCE
directory, or one `cita` of web/publicaciones.json. Pass `<sweep>/noticias <sweep>/entradas`, never
the agents' unverified replies. A SOURCE that doesn't exist or holds nothing fails. Prints what it
covered and exits 1 on a miss or when no quote was found (21 Nov 2026: four quotes had their first
letter lowercased; only a case-sensitive match caught them).

Not covered: which article a quote is credited to (a quote found in another source passes), and a
paraphrase around the quote. Read those.
"""
import glob, html, json, os, re, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..'))
MIN = 10
args = sys.argv[1:]
path = os.path.join(ROOT, 'web/noticias.html')
if '--html' in args:
    i = args.index('--html'); path = args[i + 1]; del args[i:i + 2]
if not args:
    sys.exit(__doc__)


def norm(s):
    s = html.unescape(s).replace('“', '"').replace('”', '"').replace('’', "'").replace('­', '').replace('​', '')
    return re.sub(r'\s+', ' ', s).strip()


def citas(x):
    if isinstance(x, dict):
        return [x['cita']] if isinstance(x.get('cita'), str) else sum((citas(v) for v in x.values()), [])
    if isinstance(x, list):
        return sum((citas(v) for v in x), [])
    return []


paras, n_txt, n_cita = [], 0, 0
pub = citas(json.load(open(os.path.join(ROOT, 'web/publicaciones.json'))))
paras += [norm(c) for c in pub]
for a in args:
    if os.path.isfile(a):
        files = [a]
    elif os.path.isdir(a):
        files = glob.glob(f'{a}/**/*.txt', recursive=True) + glob.glob(f'{a}/**/*.json', recursive=True)
    else:
        sys.exit(f'citas_noticias: no such SOURCE {a}')
    got = 0
    for f in files:
        if f.endswith('.json'):
            try:
                cs = citas(json.load(open(f)))
            except ValueError:
                continue
            paras += [norm(c) for c in cs]; n_cita += len(cs); got += len(cs)
        else:
            ls = [l for l in open(f, errors='replace').read().splitlines() if l.strip() and not re.match(r'(URL|PUB):? ', l)]
            paras += [norm(l) for l in ls]; n_txt += 1; got += len(ls)
    if not got:
        sys.exit(f'citas_noticias: SOURCE {a} holds no capture or cita')

git = subprocess.run(['git', '-C', ROOT, 'show', 'HEAD:web/noticias.html'], capture_output=True, text=True)
if git.returncode:
    sys.exit('citas_noticias: git show HEAD:web/noticias.html failed: ' + git.stderr.strip())
old = set(git.stdout.splitlines())
added = [l for l in open(path).read().splitlines() if l not in old]
raw = '\n'.join(added)
attrs = re.findall(r'(?:alt|title|aria-label)="([^"]*)"', raw)
text = html.unescape(re.sub(r'<[^>]+>', '', raw) + '\n' + '\n'.join(attrs))
quotes = re.findall(r'«([^«»]*(?:«[^»]*»[^«»]*)*)»', text)


def found(part):
    rx = re.compile(r'(?<!\w)' + re.escape(part) + r'(?!\w)')
    return any(rx.search(p) for p in paras)


miss = []
for q in quotes:
    for part in re.split(r'\s*\[…\]\s*', q):
        p = norm(part)
        if not p:
            continue
        if len(p) < MIN:
            miss.append(('too short to check', p))
        elif not found(p):
            miss.append(('not in any source', p))
for why, m in miss:
    print(f'{why}: {m[:160]}')
print(f'{n_txt} captures, {n_cita} entry citas, {len(pub)} publicaciones citas; '
      f'{len(added)} added lines, {len(quotes)} quotes, {len(miss)} not found')
sys.exit(1 if miss or not quotes else 0)
