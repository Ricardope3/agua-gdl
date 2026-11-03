// Static checks for web/: inline script syntax, JSON, internal links (with _redirects and
// Pages' clean URLs) and external hosts against the CSP in _headers. No dependencies.
// Usage: node scripts/check_web.mjs [repo-root]
import { execFileSync } from "node:child_process";
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const repo = resolve(process.argv[2] || join(dirname(fileURLToPath(import.meta.url)), ".."));
const web = join(repo, "web");
const ORIGIN = "https://aguagdl.com";
const problems = [];
const fail = (file, msg) => problems.push(`${file}: ${msg}`);

let files;
try {
  // -z keeps non-ASCII names unquoted; --others adds new files not yet staged.
  files = execFileSync("git", ["ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", "web"], { cwd: repo, encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] })
    .split("\0").filter(Boolean).map((f) => f.slice(4));
  files = [...new Set(files)];
} catch {
  const walk = (d) => readdirSync(d).flatMap((n) => (statSync(join(d, n)).isDirectory() ? walk(join(d, n)) : [join(d, n)]));
  files = walk(web).map((f) => relative(web, f));
}
files = files.filter((f) => existsSync(join(web, f)));
const read = (f) => readFileSync(join(web, f), "utf8");
const lineAt = (s, i) => s.slice(0, i).split("\n").length;
const attrs = (s) => Object.fromEntries([...s.matchAll(/([\w:-]+)(?:\s*=\s*("[^"]*"|'[^']*'|[^\s>]+))?/g)]
  .map(([, k, v = ""]) => [k.toLowerCase(), v.replace(/^["']|["']$/g, "").replace(/&amp;/g, "&")]));

// _redirects and _headers
const redirects = read("_redirects").split("\n").map((l) => l.trim().split(/\s+/)).filter((p) => p[0] && !p[0].startsWith("#"));
const csp = {};
{
  let all = false;
  for (const line of read("_headers").split("\n")) {
    if (/^\S/.test(line)) all = line.trim() === "/*";
    const m = all && line.match(/^\s+Content-Security-Policy:\s*(.+)$/i);
    if (m) for (const d of m[1].split(";")) { const [k, ...v] = d.trim().split(/\s+/); if (k) csp[k] = v; }
  }
  if (!Object.keys(csp).length) fail("_headers", "no Content-Security-Policy under /*");
}
const allowed = (directive, url) => {
  const list = csp[directive] || csp["default-src"] || [];
  const u = new URL(url);
  return list.some((s) => {
    if (s === "*") return true;
    if (s === "'self'") return u.origin === ORIGIN;
    if (/^[a-z]+:$/.test(s)) return u.protocol === s;
    const m = s.match(/^(?:([a-z]+):\/\/)?(\*\.)?([^/:]+)/);
    if (!m) return false;
    if (m[1] && `${m[1]}:` !== u.protocol) return false;
    return m[2] ? u.hostname.endsWith(`.${m[3]}`) : u.hostname === m[3];
  });
};
let external = 0;
const checkHost = (file, directive, url, where) => {
  if (/^https?:\/\//.test(url) && ++external && !allowed(directive, url)) fail(file, `${where}: ${new URL(url).origin} not allowed by CSP ${directive}`);
};

// Internal link resolution
const ids = new Map();
const idsOf = (f) => {
  if (!ids.has(f)) ids.set(f, new Set([...read(f).matchAll(/\s(?:id|name)\s*=\s*["']?([^"'\s>]+)/g)].map((m) => m[1])));
  return ids.get(f);
};
const isFile = (p) => existsSync(join(web, p)) && statSync(join(web, p)).isFile();
const target = (path) => {
  for (let hop = 0; hop < 5; hop++) {
    const r = redirects.find(([from]) => from === path || (from.endsWith("*") && path.startsWith(from.slice(0, -1))));
    if (!r) break;
    path = r[1].startsWith("/") ? r[1].replace(":splat", path.slice(r[0].length - 1)) : null;
    if (!path) return "external";
  }
  const p = path.replace(/^\/+/, "");
  for (const c of [p, `${p}.html`, `${p.replace(/\/?$/, "/")}index.html`]) if (c !== "" && isFile(c)) return c;
  return p === "" && isFile("index.html") ? "index.html" : null;
};
let links = 0;
const checkLink = (file, ref, where) => {
  if (!ref || /^(mailto|tel|javascript|data|blob|sms|whatsapp):/i.test(ref) || /^https?:\/\//i.test(ref) || ref.startsWith("//") || ref.includes("${")) return;
  links++;
  const u = new URL(ref, `${ORIGIN}/${file}`);
  let path;
  try { path = decodeURIComponent(u.pathname); } catch { return fail(file, `${where}: bad URL ${ref}`); }
  const t = ref.startsWith("#") ? file : target(path);
  if (!t) return fail(file, `${where}: ${ref} resolves to no file in web/`);
  const hash = decodeURIComponent(u.hash.slice(1));
  if (hash && t === file && t.endsWith(".html") && hash !== "top" && !idsOf(t).has(hash)) fail(file, `${where}: no #${hash} on the page`);
};

// JS sinks: literal URLs (or identifiers declared with them) passed to fetch and friends
const matchClose = (s, i) => {
  const open = s[i], close = { "(": ")", "{": "}", "[": "]" }[open];
  let depth = 0;
  for (let j = i; j < s.length; j++) {
    const c = s[j];
    if (c === '"' || c === "'" || c === "`") { for (j++; j < s.length && s[j] !== c; j++) if (s[j] === "\\") j++; continue; }
    if (c === open) depth++;
    else if (c === close && --depth === 0) return j;
  }
  return s.length;
};
const urlsIn = (s) => [...s.matchAll(/https?:\/\/[A-Za-z0-9.-]+/g)].map((m) => m[0]);
const resolveExpr = (js, expr) => {
  const out = urlsIn(expr);
  const id = expr.match(/^\s*([A-Za-z_$][\w$]*)/)?.[1];
  const decl = id && js.match(new RegExp(`\\b(?:const|let|var)\\s+${id.replace("$", "\\$")}\\s*=\\s*`));
  if (decl) {
    const start = decl.index + decl[0].length;
    const end = "({[".includes(js[start]) ? matchClose(js, start) : js.indexOf(";", start);
    out.push(...urlsIn(js.slice(start, end < 0 ? undefined : end + 1)));
  }
  return out;
};
const checkJs = (file, js, offset) => {
  const at = (i) => `line ${offset + lineAt(js, i) - 1}`;
  for (const m of js.matchAll(/\b(fetch|new\s+EventSource|new\s+WebSocket|sendBeacon|L\.tileLayer)\s*\(/g)) {
    const i = m.index + m[0].length - 1;
    const args = js.slice(i + 1, matchClose(js, i));
    let end = 0;
    for (let depth = 0; end < args.length; end++) {
      const c = args[end];
      if ('"\'`'.includes(c)) { for (end++; end < args.length && args[end] !== c; end++) if (args[end] === "\\") end++; continue; }
      if ("({[".includes(c)) depth++;
      else if (")}]".includes(c)) depth--;
      else if (c === "," && depth === 0) break;
    }
    const arg = args.slice(0, end);
    const lit = arg.match(/^\s*["'`](\/[^"'`$]*)["'`]/);
    if (lit && m[1] === "fetch") checkLink(file, lit[1], `${at(m.index)} fetch`);
    for (const u of resolveExpr(js, arg)) checkHost(file, m[1] === "L.tileLayer" ? "img-src" : "connect-src", u, at(m.index));
  }
  for (const m of js.matchAll(/\b([A-Za-z_$][\w$]*)\.src\s*=\s*([^;\n]+)/g)) {
    const el = js.slice(0, m.index).match(new RegExp(`\\b${m[1]}\\s*=\\s*[^;]*?["'\`](iframe|img|script)["'\`][^;]*;?[^]*$`))?.[1];
    const dirs = el ? [{ iframe: "frame-src", img: "img-src", script: "script-src" }[el]] : ["frame-src", "img-src", "script-src"];
    for (const u of resolveExpr(js, m[2])) if (++external && !dirs.some((d) => allowed(d, u))) fail(file, `${at(m.index)}: ${new URL(u).origin} not allowed by CSP ${dirs.join("/")}`);
  }
};

// Pages
let pages = 0, scripts = 0, jsons = 0;
const classic = new Set(["", "text/javascript", "application/javascript", "module"]);
for (const f of files.filter((f) => f.endsWith(".html"))) {
  pages++;
  const html = read(f).replace(/<!--[\s\S]*?-->/g, (c) => c.replace(/[^\n]/g, " "));
  for (const m of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)) {
    const a = attrs(m[1]), type = (a.type || "").toLowerCase(), line = lineAt(html, m.index);
    if (a.src) { checkLink(f, a.src, `line ${line} script`); checkHost(f, "script-src", a.src, `line ${line}`); continue; }
    scripts++;
    if (/json/.test(type)) { try { JSON.parse(m[2]); } catch (e) { fail(f, `line ${line} ${type}: ${e.message}`); } continue; }
    if (!classic.has(type)) continue;
    if (type !== "module") {
      try { new vm.Script(m[2], { filename: f }); }
      catch (e) { fail(f, `line ${line + (Number(e.stack.match(/:(\d+)\n/)?.[1]) || 1) - 1} script: ${e.message}`); }
    }
    checkJs(f, m[2], line);
  }
  const body = html.replace(/<script\b[^>]*>[\s\S]*?<\/script\s*>/gi, (c) => c.replace(/[^\n]/g, " "));
  for (const m of body.matchAll(/<([a-z][\w-]*)\b((?:[^>"']|"[^"]*"|'[^']*')*)>/gi)) {
    const tag = m[1].toLowerCase(), a = attrs(m[2]), where = `line ${lineAt(body, m.index)} <${tag}>`;
    const rel = (a.rel || "").toLowerCase();
    for (const k of ["href", "src", "data-src", "poster", "action"]) if (k in a && !(tag === "link" && /preconnect|dns-prefetch/.test(rel))) checkLink(f, a[k], where);
    for (const s of (a.srcset || "").split(",")) checkLink(f, s.trim().split(/\s+/)[0], where);
    const dir = { img: "img-src", iframe: "frame-src", video: "media-src", audio: "media-src", source: "media-src", embed: "object-src", object: "object-src" }[tag];
    if (dir) for (const u of [a.src, a["data-src"], ...(a.srcset || "").split(",").map((s) => s.trim().split(/\s+/)[0])]) if (u) checkHost(f, dir, u, where);
    if (a.poster) checkHost(f, "img-src", a.poster, where);
    if (tag === "link" && a.href) checkHost(f, /stylesheet/.test(rel) ? "style-src" : /icon/.test(rel) ? "img-src" : /manifest/.test(rel) ? "manifest-src" : "default-src", a.href, where);
    if (tag === "form" && a.action) checkHost(f, "form-action", a.action, where);
  }
}
for (const f of files.filter((f) => f.endsWith(".js"))) { scripts++; try { new vm.Script(read(f), { filename: f }); checkJs(f, read(f), 1); } catch (e) { fail(f, e.message); } }
for (const f of files.filter((f) => /\.(json|webmanifest)$/.test(f))) { jsons++; try { JSON.parse(read(f)); } catch (e) { fail(f, e.message); } }

for (const p of problems) console.log(p);
console.log(`check_web: ${pages} pages, ${scripts} scripts, ${jsons} JSON files, ${links} internal links, ${external} external loads, ${problems.length} problems`);
process.exit(problems.length ? 1 : 0);
