// Tested on 6 Nov 2026 (367 comments on a page post); the reply-nesting filter in block 2 was added after that run. Run each block with javascript_tool on your own tab.

// 1. After switching the sort to «All comments»: load every comment in the background
//    (one javascript_tool call times out at 45 s). Poll `window._done + ' ' + window._n` until true.
window._done = false;
(async () => {
  const dlg = document.querySelector('[role=dialog]') || document;
  const sc = [...dlg.querySelectorAll('div')]
    .filter(d => d.scrollHeight > d.clientHeight + 50 && /auto|scroll/.test(getComputedStyle(d).overflowY))
    .sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
  let last = 0, still = 0;
  for (let r = 0; r < 90; r++) {
    if (sc) sc.scrollTop = sc.scrollHeight;
    await new Promise(x => setTimeout(x, 1300));
    const more = [...dlg.querySelectorAll('[role=button]')].filter(b =>
      /View more comments|Ver más comentarios|View \d+ (more )?repl|View all \d+ repl|View 1 reply|Ver \d+ respuesta|Ver todas las \d+ respuestas|Ver \d+ respuestas más|Ver más respuestas/i.test(b.innerText));
    for (const b of more.slice(0, 8)) { b.click(); await new Promise(x => setTimeout(x, 500)); }
    const n = dlg.querySelectorAll('[role=article]').length;
    window._n = n;
    if (n === last && !more.length) { if (++still > 3) break; } else still = 0;
    last = n;
  }
  window._done = true;
})();

// 2. Extract: comment id, reply flag, age, text.
//    Also record when you read: new Date() in the page.
// Links carry the id either as digits or base64 («comment:<post>_<id>»).
const dec = id => /^\d+$/.test(id) ? id : (() => { try { return atob(id).split('_').pop(); } catch (e) { return id; } })();
const root = document.querySelector('[role=dialog]') || document;
// A reply is its own article nested in its parent's: take only what belongs to this article.
const own = (a, sel) => [...a.querySelectorAll(sel)].filter(x => x.closest('[role=article]') === a);
const seen = new Set();
window._r = [...root.querySelectorAll('[role=article]')].map(a => {
  const l = own(a, 'a[href*="comment_id"]');
  if (!l.length) return null;
  const u = new URL(l[0].href);
  return {
    id: dec(u.searchParams.get('reply_comment_id') || u.searchParams.get('comment_id')),
    reply: !!u.searchParams.get('reply_comment_id'),
    age: l.map(x => x.innerText).filter(Boolean).pop() || '',
    body: own(a, 'div[dir=auto]').map(d => d.innerText).join(' / ').replace(/\s+/g, ' ').trim(),
  };
}).filter(r => r && !seen.has(r.id) && seen.add(r.id));

// 3. Tool output truncates near 1,000 characters: put the rows on the page and read them with get_page_text.
//    This replaces the page; reload the post if you need it again. Bodies are cut at 200 characters here:
//    for a longer comment you quote, read the whole text first: window._r.find(r => r.id === '<id>').body
const m = document.createElement('main'); m.setAttribute('role', 'main');
const pre = document.createElement('pre');
pre.textContent = window._r.map((r, i) => `${i}|${r.id}|${r.age}${r.reply ? '|R' : ''}|${r.body.slice(0, 200)}`).join('\n');
m.appendChild(pre); document.body.replaceChildren(m);
