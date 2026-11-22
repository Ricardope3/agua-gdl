"""articulos.py OUTDIR URL... : save each news article's HTML and its text with the published time.

Writes OUTDIR/<sha1(url)[:10]>.html and .txt (URL, PUB, TITLE, then the paragraphs). The text is,
in order of preference: Arc Publishing's `Fusion.globalContent` text elements (Crónica; PUB is then
its `display_date`, in UTC, which can differ from the JSON-LD date), the JSON-LD `articleBody`
followed by the page's <p> text, or the <p> text alone. A file under 2 KB is fetched again. Only
http(s) URLs, no redirect to another scheme, 5 MB at most. PUB is the page's own time: one ending
in Z or +00:00 is UTC, so the Guadalajara day is 6 h earlier. A page with no PUB is flagged: date it
from the page itself, never from a search result.
Quote from the .txt, never from memory; `citas_noticias.py` checks quotes against these files.
"""
import hashlib, html, json, os, re, subprocess, sys

out = sys.argv[1]
os.makedirs(out, exist_ok=True)
for u in sys.argv[2:]:
    if not re.fullmatch(r'https?://\S+', u):
        print('skipped, not an http(s) URL:', u)
        continue
    h = hashlib.sha1(u.encode()).hexdigest()[:10]
    p = f'{out}/{h}.html'
    if not os.path.exists(p) or os.path.getsize(p) < 2000:
        subprocess.run(['curl', '-sL', '-m', '40', '--proto', '=http,https', '--proto-redir', '=http,https',
                        '--max-filesize', '5000000', '-A', 'Mozilla/5.0', '-o', p, '--', u])
    t = open(p, errors='replace').read() if os.path.exists(p) else ''
    pub = re.search(r'(?:article:published_time" content="|"datePublished"\s*:\s*")([^"]+)', t)
    pub = pub and pub.group(1)
    title = re.search(r'<meta property="og:title" content="([^"]*)"', t)
    ps = [html.unescape(re.sub(r'<[^>]+>', '', x)).strip() for x in re.findall(r'<p[^>]*>(.*?)</p>', t, re.S)]
    ps = [x for x in ps if len(x) > 40 and '{' not in x and 'googletag' not in x]
    g = re.search(r'Fusion\.globalContent=(\{.*?\});Fusion\.globalContentConfig', t, re.S)
    try:
        gc = json.loads(g.group(1)) if g else None
    except ValueError:
        gc = None
        print(h, 'Fusion.globalContent did not parse: falling back to the <p> text')
    if gc:
        ps = [html.unescape(re.sub(r'<[^>]+>', '', e.get('content', ''))) for e in gc.get('content_elements', []) if e.get('type') == 'text']
        pub = f"display_date {gc.get('display_date')} first_publish {gc.get('first_publish_date')}"
    body = None if gc else re.search(r'"articleBody"\s*:\s*("(?:[^"\\]|\\.)*")', t)
    try:
        ps = ([json.loads(body.group(1))] + ['--- <p> ---'] + ps) if body else ps
    except ValueError:
        print(h, 'articleBody did not parse: <p> text only')
    tt = title and html.unescape(title.group(1))
    open(f'{out}/{h}.txt', 'w').write(f"URL {u}\nPUB {pub}\nTITLE {tt}\n\n" + '\n'.join(ps))
    print(h, len(t), pub, (tt or '')[:90], '' if len(t) > 2000 else '  <- fetch failed or blocked',
          '' if pub else '  <- no PUB: date it from the page')
