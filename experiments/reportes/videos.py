"""Build the standalone mobile video-feed experiments /c6, /c7 and /c8.

Only direct video publications are included: comments on somebody else's video are not
videos about the colonia themselves. Production /reportes is never written here.
Run from the repository root: python3 experiments/reportes/videos.py
"""
from pathlib import Path

import colonia as base

VIDEO_CSS = r"""
@media (max-width: 760px) {
  .v-launch { display: flex; align-items: center; gap: 10px; width: calc(100% - 32px); margin: 10px 16px 0; padding: 10px 12px; border: 0; border-radius: 12px; background: #101828; color: #fff; font: 700 .95rem var(--font); text-align: left; cursor: pointer }
  .v-launch .v-play { display: grid; place-items: center; flex: 0 0 34px; height: 34px; border-radius: 50%; background: #fff; color: #101828; font-size: 1rem }
  .v-launch small { display: block; margin-top: 2px; color: #d0d5dd; font-weight: 400 }
  .v-launch .v-arrow { margin-left: auto; font-size: 1.4rem }
  .v-stories { display: flex; gap: 10px; margin: 10px 16px 0; overflow-x: auto; scrollbar-width: none }
  .v-story { position: relative; flex: 0 0 72px; height: 96px; padding: 0; overflow: hidden; border: 2px solid #e4572e; border-radius: 12px; background: #101828; cursor: pointer }
  .v-story img { width: 100%; height: 100%; object-fit: cover }
  .v-story span { position: absolute; inset: auto 0 0; padding: 16px 4px 5px; background: linear-gradient(transparent, rgb(0 0 0 / .9)); color: #fff; font: 700 .65rem var(--font) }
  .v-reel-launch { display: grid; grid-template-columns: 76px 1fr auto; align-items: center; gap: 10px; margin: 10px 16px 0; padding: 8px; border-radius: 12px; background: #101828; color: #fff }
  .v-reel-launch img { width: 76px; height: 64px; object-fit: cover; border-radius: 8px }
  .v-reel-launch b, .v-reel-launch small { display: block } .v-reel-launch small { margin-top: 3px; color: #d0d5dd }
  .v-reel-launch button { border: 0; border-radius: 999px; padding: 9px 12px; background: #fff; color: #101828; font-weight: 800 }
}
.v-mode { position: fixed; inset: 0; z-index: 6000; display: flex; flex-direction: column; background: #080b12; color: #fff }
.v-mode[hidden] { display: none }
.v-top { position: absolute; z-index: 3; top: 0; left: 0; right: 0; display: flex; align-items: center; gap: 10px; min-height: 58px; padding: max(10px, env(safe-area-inset-top)) 14px 10px; background: linear-gradient(#080b12dd, transparent); pointer-events: none }
.v-top > * { pointer-events: auto } .v-top strong { flex: 1; font-size: .9rem } .v-top button { width: 40px; height: 40px; border: 1px solid #ffffff55; border-radius: 50%; background: #101828cc; color: #fff; font-size: 1.3rem }
.v-feed { flex: 1; overflow-y: auto; overscroll-behavior: contain; scroll-snap-type: y mandatory; scrollbar-width: none }
.v-slide { position: relative; display: flex; flex-direction: column; justify-content: flex-end; box-sizing: border-box; min-height: 100%; padding: 74px 18px max(24px, env(safe-area-inset-bottom)); overflow: hidden; scroll-snap-align: start; scroll-snap-stop: always }
.v-slide > img { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; opacity: .72 }
.v-slide::after { content: ""; position: absolute; inset: 0; background: linear-gradient(transparent 20%, #080b12 88%); pointer-events: none }
.v-content { position: relative; z-index: 1; max-width: 620px; width: 100%; margin: 0 auto }
.v-kicker { margin: 0 0 8px; color: #fda29b; font-size: .74rem; font-weight: 800; letter-spacing: .08em; text-transform: uppercase }
.v-quote { margin: 0; font: 700 1.25rem/1.35 var(--font) }
.v-meta { margin: 10px 0; color: #e4e7ec; font-size: .85rem }
.v-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px }
.v-actions button, .v-actions a { box-sizing: border-box; min-height: 44px; padding: 11px 15px; border: 1px solid #ffffff66; border-radius: 999px; background: #fff; color: #101828; font: 800 .9rem var(--font); text-decoration: none; cursor: pointer }
.v-actions .v-secondary { background: #101828bb; color: #fff }
.v-player { position: absolute; z-index: 2; inset: 58px 0 190px; display: grid; place-items: center; background: #000 }
.v-player iframe { width: 100%; height: 100%; border: 0 }
.v-nav { position: absolute; z-index: 4; right: 14px; top: 50%; display: grid; gap: 8px; transform: translateY(-50%) }
.v-nav button { width: 42px; height: 42px; border: 1px solid #ffffff55; border-radius: 50%; background: #101828dd; color: #fff; font-size: 1.2rem }
.v-nav button:disabled { opacity: .3 } .v-count { color: #fff; font-size: .75rem; text-align: center }
.v-end { justify-content: center; text-align: center; background: radial-gradient(circle at 50% 30%, #163c59, #080b12 65%) }
.v-end .v-content { margin: auto } .v-end h2 { margin: 0 0 10px; font-size: 1.7rem } .v-end p { color: #d0d5dd; line-height: 1.5 } .v-end .v-actions { justify-content: center }
.v-mode.stories .v-slide { min-height: 82%; margin: 0 auto; padding: 70px 16px 20px; scroll-snap-align: center }
.v-mode.stories .v-slide > img { inset: 62px 12px 12px; width: calc(100% - 24px); height: calc(100% - 74px); border-radius: 22px; opacity: .85 }
.v-mode.stories .v-slide::after { inset: 62px 12px 12px; border-radius: 22px }
.v-mode.compact { top: auto; height: min(78dvh, 720px); border-radius: 22px 22px 0 0; box-shadow: 0 -20px 60px #0008 }
.v-mode.compact::before { content: ""; position: fixed; z-index: -1; inset: -100vh 0 100%; background: #03081488; backdrop-filter: blur(3px) }
.v-mode.compact .v-slide { padding-top: 68px }
@media (prefers-reduced-motion: reduce) { .v-feed { scroll-behavior: auto } .v-mode.compact::before { backdrop-filter: none } }
"""

DESKTOP_CSS = r"""
@media (min-width: 761px) {
  .v-launch { display: flex; align-items: center; gap: 12px; width: calc(100% - 40px); margin: 0 20px 18px; padding: 14px; border: 0; border-radius: 4px; background: #101828; color: #fff; font: 700 1rem var(--font); text-align: left; cursor: pointer }
  .v-launch .v-play { display: grid; place-items: center; flex: 0 0 40px; height: 40px; border-radius: 50%; background: #fff; color: #101828 }
  .v-launch small { display: block; margin-top: 3px; color: #d0d5dd; font-weight: 400 } .v-launch .v-arrow { margin-left: auto; font-size: 1.4rem }
  .v-stories { display: flex; gap: 12px; padding: 14px 20px 18px; overflow-x: auto }
  .v-story { position: relative; flex: 1; min-width: 0; height: 150px; padding: 0; overflow: hidden; border: 3px double #e4572e; border-radius: 4px; background: #101828; cursor: pointer }
  .v-story img { width: 100%; height: 100%; object-fit: cover } .v-story span { position: absolute; inset: auto 0 0; padding: 28px 8px 8px; background: linear-gradient(transparent, #000e); color: #fff; font: 700 .76rem var(--font); text-align: left }
  .v-reel-launch { display: grid; grid-template-columns: 110px 1fr auto; align-items: center; gap: 12px; margin: 0 20px 18px; padding: 10px; border-radius: 4px; background: #101828; color: #fff }
  .v-reel-launch img { width: 110px; height: 78px; object-fit: cover } .v-reel-launch small { display: block; margin-top: 4px; color: #d0d5dd }
  .v-reel-launch button { padding: 10px 14px; border: 0; border-radius: 999px; background: #fff; color: #101828; font-weight: 800; cursor: pointer }
  .v-mode.full { padding: 0 max(24px, calc((100vw - 920px) / 2)); background: rgb(3 8 18 / .96) }
  .v-mode.full .v-slide { max-width: 920px; margin: auto; padding-left: 60px; padding-right: 60px }
  .v-mode.full .v-quote { font-size: 1.7rem; max-width: 720px }
  .v-mode.stories { background: rgb(3 8 18 / .94) }
  .v-mode.stories .v-slide { width: min(720px, 80vw); min-height: 100%; padding-bottom: 40px }
  .v-mode.stories .v-slide > img, .v-mode.stories .v-slide::after { inset: 70px 0 20px; width: 100%; height: calc(100% - 90px); border-radius: 12px }
  .v-mode.compact { inset: auto 24px 24px auto; width: min(520px, calc(100vw - 48px)); height: min(72vh, 700px); border: 1px solid #ffffff33; border-radius: 16px; box-shadow: 0 20px 70px #0009 }
  .v-mode.compact::before { display: none }
}
"""

VIDEO_JS = r"""
  // Direct videos only; a comment under a video is evidence, not another video.
  const videoPosts = (e) => {
    if (!e) return [];
    const seen = new Set();
    return e.posts.filter((p) => p.tipo !== "comentario" && /(?:youtube\.com\/watch|youtu\.be\/|tiktok\.com\/|facebook\.com\/(?:[^/]+\/)?(?:videos|watch|reel)|fb\.watch)/i.test(p.url || ""))
      .filter((p) => { const id = (p.url || "").split("?")[0].replace(/\/$/, ""); return !seen.has(id) && seen.add(id); })
      .sort((a, b) => b.fecha.localeCompare(a.fecha));
  };
  const vEl = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text != null) n.textContent = text; return n; };
  const vDate = (iso) => new Date(`${iso}T12:00:00`).toLocaleDateString("es-MX", { day: "numeric", month: "short", year: "numeric" }).replaceAll(".", "");
  const vYouTube = (url) => { const m = url.match(/[?&]v=([\w-]+)/) || url.match(/youtu\.be\/([\w-]+)/); return m && m[1]; };
  function videoLauncher(card, e, p, mode) {
    const videos = videoPosts(e);
    if (!videos.length) return; // Colonias without a verified direct video keep the evidence view unchanged.
    if (mode === "stories") {
      const row = vEl("div", "v-stories"); row.setAttribute("aria-label", "Videos de esta colonia");
      videos.forEach((v, i) => {
        const b = vEl("button", "v-story"); b.type = "button"; b.setAttribute("aria-label", `Abrir video ${i + 1} de ${videos.length}: ${v.quien}`);
        if (v.vista) { const img = vEl("img"); img.src = `/${v.vista}`; img.alt = ""; b.append(img); }
        b.append(vEl("span", null, `${i + 1} · ${v.quien}`)); b.onclick = () => openVideos(videos, p, mode, i); row.append(b);
      });
      (card.querySelector(".c-acc") || card.querySelector(".ev-src") || card.querySelector(".q-sec:last-of-type") || card.querySelector("h2")).after(row); return;
    }
    if (mode === "compact") {
      const box = vEl("div", "v-reel-launch");
      if (videos[0].vista) { const img = vEl("img"); img.src = `/${videos[0].vista}`; img.alt = ""; box.append(img); }
      const tx = vEl("div"); tx.append(vEl("b", null, videos.length === 1 ? "1 video" : `${videos.length} videos`), vEl("small", null, "Desliza para verlos"));
      const b = vEl("button", null, "Ver"); b.type = "button"; b.onclick = () => openVideos(videos, p, mode, 0); box.append(tx, b);
      (card.querySelector(".c-acc") || card.querySelector(".ev-src") || card.querySelector(".q-sec:last-of-type") || card.querySelector("h2")).after(box); return;
    }
    const b = vEl("button", "v-launch"); b.type = "button";
    b.append(vEl("span", "v-play", "▶"));
    const tx = vEl("span", null, videos.length === 1 ? "Ver el video" : `Ver ${videos.length} videos`); tx.append(vEl("small", null, "Uno por pantalla · con su fuente"));
    b.append(tx, vEl("span", "v-arrow", "↑")); b.onclick = () => openVideos(videos, p, mode, 0);
    (card.querySelector(".c-acc") || card.querySelector(".ev-src") || card.querySelector(".q-sec:last-of-type") || card.querySelector("h2")).after(b);
  }
  function openVideos(videos, p, mode, start) {
    const previous = document.activeElement, overlay = vEl("section", `v-mode ${mode}`), top = vEl("div", "v-top"), feed = vEl("div", "v-feed");
    overlay.setAttribute("role", "dialog"); overlay.setAttribute("aria-modal", "true"); overlay.setAttribute("aria-label", `Videos de ${p.n}`); overlay.tabIndex = -1;
    const close = vEl("button", null, "×"); close.type = "button"; close.setAttribute("aria-label", "Cerrar videos");
    top.append(close, vEl("strong", null, `${p.n} · ${videos.length === 1 ? "1 video" : `${videos.length} videos`}`));
    const slides = videos.map((v, i) => {
      const slide = vEl("article", "v-slide"); slide.dataset.index = i; slide.setAttribute("aria-label", `Video ${i + 1} de ${videos.length}`);
      if (v.vista) { const img = vEl("img"); img.src = `/${v.vista}`; img.alt = ""; slide.append(img); }
      const content = vEl("div", "v-content"); content.append(vEl("p", "v-kicker", `Video · ${i + 1} de ${videos.length}`), vEl("p", "v-quote", v.titular || v.cita), vEl("p", "v-meta", `${v.quien || "Vecina o vecino"} · ${vDate(v.fecha)}`));
      if (!v.titular) { const q = vEl("p", "v-meta", `«${v.cita}»`); content.append(q); }
      const actions = vEl("div", "v-actions"), yt = vYouTube(v.url);
      if (yt) {
        const play = vEl("button", null, "▶ Reproducir aquí"); play.type = "button";
        play.onclick = () => {
          stopPlayers();
          const player = vEl("div", "v-player"), frame = vEl("iframe");
          frame.src = `https://www.youtube-nocookie.com/embed/${encodeURIComponent(yt)}?autoplay=1&rel=0`; frame.title = `Video de ${v.quien}`; frame.allow = "autoplay; encrypted-media; picture-in-picture"; frame.allowFullscreen = true;
          player.append(frame); slide.append(player);
        };
        actions.append(play);
      }
      const source = vEl("a", null, yt ? "Abrir en YouTube" : "Ver video en la fuente"); source.href = v.url; source.target = "_blank"; source.rel = "noopener nofollow"; actions.append(source);
      content.append(actions); slide.append(content); feed.append(slide); return slide;
    });
    const end = vEl("article", "v-slide v-end"), ec = vEl("div", "v-content");
    ec.append(vEl("p", "v-kicker", "Ya viste todos los videos"), vEl("h2", null, "¿Y en tu casa hay agua?"), vEl("p", null, "Tu reporte ayuda a mostrar cómo está esta colonia ahora."));
    const ea = vEl("div", "v-actions"), report = vEl("button", null, "Reportar esta colonia"); report.type = "button";
    report.onclick = () => { shut(); document.getElementById("reporta-btn").click(); };
    const again = vEl("button", "v-secondary", "Ver de nuevo"); again.type = "button"; again.onclick = () => go(0);
    ea.append(report, again); ec.append(ea); end.append(ec); feed.append(end);
    const nav = vEl("div", "v-nav"), up = vEl("button", null, "↑"), down = vEl("button", null, "↓"), count = vEl("span", "v-count");
    up.type = down.type = "button"; up.setAttribute("aria-label", "Video anterior"); down.setAttribute("aria-label", "Siguiente"); nav.append(up, count, down);
    overlay.append(top, feed, nav); document.body.append(overlay);
    let at = 0;
    const stopPlayers = () => overlay.querySelectorAll(".v-player").forEach((n) => n.remove());
    function go(i) { at = Math.max(0, Math.min(videos.length, i)); stopPlayers(); feed.scrollTop = feed.children[at].offsetTop - feed.offsetTop; update(); }
    function update() { count.textContent = at === videos.length ? "Fin" : `${at + 1}/${videos.length}`; up.disabled = at === 0; down.disabled = at === videos.length; }
    up.onclick = () => go(at - 1); down.onclick = () => go(at + 1);
    let scrollTimer;
    feed.addEventListener("scroll", () => { clearTimeout(scrollTimer); scrollTimer = setTimeout(() => { const i = [...feed.children].reduce((best, slide, i) => Math.abs(slide.offsetTop - feed.offsetTop - feed.scrollTop) < Math.abs(feed.children[best].offsetTop - feed.offsetTop - feed.scrollTop) ? i : best, 0); if (i !== at) { at = i; stopPlayers(); update(); } }, 80); }, { passive: true });
    function shut() { stopPlayers(); document.removeEventListener("keydown", keys, true); overlay.remove(); previous?.focus?.({ preventScroll: true }); }
    close.onclick = shut;
    function keys(ev) {
      ev.stopPropagation();
      if (ev.key === "Escape") { ev.preventDefault(); shut(); }
      else if (["ArrowDown", "PageDown"].includes(ev.key)) { ev.preventDefault(); go(at + 1); }
      else if (["ArrowUp", "PageUp"].includes(ev.key)) { ev.preventDefault(); go(at - 1); }
      else if (ev.key === "Tab") {
        const focusable = [...overlay.querySelectorAll("button:not(:disabled), a[href], iframe")].filter((n) => n.offsetParent !== null);
        if (!focusable.length) return;
        const first = focusable[0], last = focusable.at(-1);
        if (ev.shiftKey && document.activeElement === first) { ev.preventDefault(); last.focus(); }
        else if (!ev.shiftKey && document.activeElement === last) { ev.preventDefault(); first.focus(); }
      }
    }
    document.addEventListener("keydown", keys, true); close.focus({ preventScroll: true }); go(start);
  }
  window.__cierraVideos = () => document.querySelector(".v-mode")?.remove();
"""

def variant(mode):
    return base.U_CSS + base.D1_CSS + VIDEO_CSS + DESKTOP_CSS, base.D1_JS + VIDEO_JS + f"""
  window.__ficha = (card, e, form, p) => {{ compacta(card, p); acciones(card, e, false); videoLauncher(card, e, p, "{mode}"); }};
  const evidenceFichaD = window.__fichaD;
  window.__fichaD = (card, e, form, p, f) => {{ evidenceFichaD(card, e, form, p, f); videoLauncher(card, e, p, "{mode}"); }};
"""


VARIANTS = {
    "c6": ("Videos verticales", *variant("full")),
    "c7": ("Historias de video", *variant("stories")),
    "c8": ("Reel compacto", *variant("compact")),
}


def main():
    src = Path(__file__).with_name("reportes-before-c3.html").read_text()
    base.VD.update(VARIANTS)
    base.DNAMES.update({k: v[0] for k, v in VARIANTS.items()})
    for name in VARIANTS:
        out = base.WEB / f"{name}.html"
        out.write_text(base.build(src, name))
        print(out.relative_to(base.ROOT))


if __name__ == "__main__":
    main()
