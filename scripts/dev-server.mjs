import http from "node:http";
import { createReadStream, existsSync, readFileSync, statSync } from "node:fs";
import { extname, resolve, sep } from "node:path";

const args = process.argv.slice(2);
const value = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] && !args[i + 1].startsWith("--") ? args[i + 1] : fallback;
};
const port = Number(value("--port", process.env.PORT || 7100));
const host = value("--host", "0.0.0.0");
const root = resolve("web");
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8", ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".ico": "image/x-icon", ".webp": "image/webp", ".ics": "text/calendar; charset=utf-8" };

// Cloudflare Pages' _redirects and _headers, so local matches production. The CSP also lets
// pages reach a local API (?api=http://localhost:PORT), which production blocks.
const lines = (name) => (existsSync(resolve(root, name)) ? readFileSync(resolve(root, name), "utf8").split("\n") : []);
const pattern = (p) => new RegExp(`^${p.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/\*/g, ".*").replace(/:\w+/g, "[^/]+")}$`);
const redirects = lines("_redirects").map((l) => l.trim().split(/\s+/)).filter(([from]) => from && !from.startsWith("#"))
  .map(([from, to, status = "302"]) => ({ from: pattern(from), to, status: Number(status) }));
const headers = [];
for (const line of lines("_headers")) {
  if (/^\S/.test(line)) headers.push({ path: pattern(line.trim()), set: [] });
  else if (line.includes(":") && headers.length) headers.at(-1).set.push(line.trim().split(/:\s*(.*)/s).slice(0, 2));
}
const local = (v) => v.replace(/connect-src ([^;]*)/, "connect-src $1 http://localhost:* http://127.0.0.1:*");

http.createServer((req, res) => {
  let pathname;
  try { pathname = decodeURIComponent(new URL(req.url, "http://localhost").pathname); }
  catch { res.writeHead(400).end("Bad request"); return; }
  const extra = {};
  for (const h of headers) if (h.path.test(pathname)) for (const [k, v] of h.set) extra[k] = /^content-security-policy$/i.test(k) ? local(v) : v;
  delete extra["Strict-Transport-Security"];
  const r = redirects.find((r) => r.from.test(pathname));
  if (r && r.status !== 200) { res.writeHead(r.status, { Location: r.to }).end(); return; }
  if (r) pathname = r.to;
  let file = resolve(root, `.${pathname}`);
  if (file !== root && !file.startsWith(root + sep)) { res.writeHead(403).end("Forbidden"); return; }
  if (existsSync(file) && statSync(file).isDirectory()) file = resolve(file, "index.html");
  if (!existsSync(file) && !extname(file) && existsSync(`${file}.html`)) file += ".html";
  if (!existsSync(file) || !statSync(file).isFile()) { res.writeHead(404).end("Not found"); return; }
  res.writeHead(200, { "Content-Type": types[extname(file)] || "application/octet-stream", ...extra, "Cache-Control": "no-store" });
  createReadStream(file).pipe(res);
}).listen(port, host, () => console.log(`Agua GDL preview: http://${host}:${port}/`));
