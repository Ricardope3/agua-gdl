// Light/dark switch. Pages style dark mode with @media (prefers-color-scheme: dark); this turns
// those rules on ("all") only when the visitor chose dark, so light is the default.
(() => {
  const KEY = "tema";
  const original = new WeakMap();
  let choice = null;
  try { choice = localStorage.getItem(KEY); } catch {}

  const darkRules = (rules, out) => {
    for (const r of rules) {
      if (r instanceof CSSMediaRule) {
        if (/prefers-color-scheme:\s*dark/.test(r.media.mediaText) || original.has(r)) out.push(r);
        darkRules(r.cssRules, out);
      }
    }
    return out;
  };

  window.aguaDark = () => choice === "dark";

  const apply = () => {
    for (const sheet of document.styleSheets) {
      let rules;
      try { rules = sheet.cssRules; } catch { continue; }
      for (const r of darkRules(rules, [])) {
        if (!original.has(r)) original.set(r, r.media.mediaText);
        r.media.mediaText = aguaDark() ? "all" : "not all";
      }
    }
    document.documentElement.style.colorScheme = aguaDark() ? "dark" : "light";
    const bar = document.querySelector('meta[name="theme-color"]');
    if (bar) bar.content = aguaDark() ? "#06141d" : "#ffffff";
    const btn = document.querySelector(".theme-btn");
    if (btn) {
      btn.innerHTML = aguaDark() ? SUN : MOON;
      btn.setAttribute("aria-label", aguaDark() ? "Usar tema claro" : "Usar tema oscuro");
      btn.title = btn.getAttribute("aria-label");
    }
  };

  const SVG = (d) => `<svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const SUN = SVG('<circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/>');
  const MOON = SVG('<path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z"/>');

  apply();

  document.addEventListener("DOMContentLoaded", () => {
    const header = document.querySelector("header.top");
    if (!header) return;
    const style = document.createElement("style");
    style.textContent = ".theme-btn{display:inline-grid;place-items:center;width:34px;height:34px;padding:0;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--muted);cursor:pointer;order:3}.theme-btn:hover{color:var(--fg);background:var(--subtle)}.theme-btn:focus-visible{outline:none;box-shadow:0 0 0 3px var(--ring)}@media (max-width:760px){.theme-btn{order:1;margin-left:auto}header.top .site-nav{order:2}}";
    document.head.append(style);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "theme-btn";
    btn.addEventListener("click", () => {
      choice = aguaDark() ? "light" : "dark";
      try { localStorage.setItem(KEY, choice); } catch {}
      apply();
    });
    header.append(btn);
    apply();
  });
})();
