// Screenshots pages at phone and desktop width through headless Chrome's DevTools protocol.
// Usage: node scripts/shot.mjs /reportes [/avisos ...] [--base http://localhost:7100] [--out DIR] [--wait MS] [--strict]
// Start the preview first (npm run dev). Writes <out>/<route>-390.png and -1300.png.
// --strict also prints one line per problem (route, width, kind, detail) and exits 1 on any that fail:
//   fail: uncaught exceptions, console.error, same-origin failed loads or HTTP >= 400, horizontal page
//         overflow, elements past the viewport edge (unless inside an overflow-x: auto/hidden/scroll box).
//   report only ("external"): other origins (OSM tiles, api.aguagdl.com) failing or >= 400, since that
//         is usually the network, not the page.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const args = process.argv.slice(2);
const value = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};
const valued = new Set(["--base", "--out", "--wait"]);
const routes = args.filter((a, i) => !a.startsWith("--") && !valued.has(args[i - 1]));
if (!routes.length) routes.push("/");
const strict = args.includes("--strict");
const base = value("--base", "http://localhost:7100");
const origin = new URL(base).origin;
const out = value("--out", join(tmpdir(), "agua-shots"));
const wait = Number(value("--wait", 2500));
const chrome = process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
// Port 0 lets Chrome pick a free port, which it writes to DevToolsActivePort in the profile.
const profile = mkdtempSync(join(tmpdir(), "agua-chrome-"));
const proc = spawn(chrome, ["--headless=new", "--remote-debugging-port=0", "--no-first-run", "--hide-scrollbars",
  `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore" });
let spawnError;
const exited = new Promise((r) => { proc.once("exit", r); proc.once("error", (e) => { spawnError = e; r(); }); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// Runs in the page: overflow of the document and elements sticking out of the viewport.
const layoutProbe = `(() => {
  const w = document.documentElement.clientWidth, found = [];
  const sw = document.documentElement.scrollWidth;
  if (sw > w + 1) found.push(["overflow", "page scrollWidth " + sw + " > " + w]);
  const clipped = (el) => { for (let p = el.parentElement; p && p !== document.body; p = p.parentElement)
    if (getComputedStyle(p).overflowX !== "visible") return true; return false; };
  const name = (el) => el.tagName.toLowerCase() + (el.id ? "#" + el.id : "") +
    (typeof el.className === "string" && el.className.trim() ? "." + el.className.trim().split(/\\s+/).join(".") : "");
  const out = new Set();
  for (const el of document.body.querySelectorAll("*")) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height || (r.right <= w + 1 && r.left >= -1)) continue;
    const s = getComputedStyle(el);
    if (s.visibility === "hidden" || s.display === "none" || clipped(el)) continue;
    let p = el.parentElement; while (p && !out.has(p)) p = p.parentElement;
    if (p) continue; // report the outermost offender only
    out.add(el);
    found.push(["offscreen", name(el) + " spans " + Math.round(r.left) + ".." + Math.round(r.right) + " of " + w]);
  }
  return found.slice(0, 8);
})()`;

let failures = 0;
const problem = (route, width, kind, detail, fatal = true) => {
  if (fatal) failures++;
  console.log(`${route}\t${width}\t${fatal ? kind : "external " + kind}\t${detail}`);
};

try {
  let target;
  for (let i = 0; i < 50 && !target && !spawnError; i++) {
    await sleep(100);
    const port = existsSync(join(profile, "DevToolsActivePort")) && readFileSync(join(profile, "DevToolsActivePort"), "utf8").split("\n")[0];
    if (port) target = await fetch(`http://127.0.0.1:${port}/json/list`).then((r) => r.json()).then((l) => l.find((t) => t.type === "page")).catch(() => null);
  }
  if (spawnError) throw new Error(`cannot run Chrome at ${chrome} (set CHROME): ${spawnError.code}`);
  if (!target) throw new Error("Chrome did not start");
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  let id = 0;
  const pending = new Map();
  let events = [];
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
    else if (m.method) events.push(m);
  };
  const send = (method, params = {}) => new Promise((r, j) => {
    pending.set(++id, (m) => (m.error ? j(new Error(`${method}: ${m.error.message}`)) : r(m.result)));
    ws.send(JSON.stringify({ id, method, params }));
  });
  if (strict) for (const d of ["Runtime", "Log", "Network"]) await send(`${d}.enable`);
  mkdirSync(out, { recursive: true });
  for (const route of routes) {
    const name = route.replace(/^\/+/, "").replace(/[^\w.-]+/g, "_") || "index";
    for (const [width, height, mobile] of [[390, 844, true], [1300, 900, false]]) {
      await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: mobile ? 2 : 1, mobile });
      const url = new URL(route, base).href;
      events = [];
      const { errorText } = await send("Page.navigate", { url });
      if (errorText) throw new Error(`${url}: ${errorText}; is the preview running (npm run dev)?`);
      await sleep(wait);
      const { data } = await send("Page.captureScreenshot", { format: "png" });
      const file = join(out, `${name}-${width}.png`);
      writeFileSync(file, Buffer.from(data, "base64"));
      console.log(file);
      if (!strict) continue;
      const urls = new Map();
      const local = (u) => { try { return new URL(u).origin === origin; } catch { return true; } };
      for (const { method, params: p } of events) {
        if (method === "Network.requestWillBeSent") urls.set(p.requestId, p.request.url);
        else if (method === "Network.responseReceived" && p.response.status >= 400)
          problem(route, width, "http", `${p.response.status} ${p.response.url}`, local(p.response.url));
        else if (method === "Network.loadingFailed" && !p.canceled) {
          const u = urls.get(p.requestId) || "?";
          problem(route, width, "load", `${p.errorText} ${u}`, local(u));
        } else if (method === "Runtime.exceptionThrown") {
          const d = p.exceptionDetails;
          problem(route, width, "exception", `${d.exception?.description?.split("\n")[0] || d.text} at ${d.url || ""}:${d.lineNumber + 1}`);
        } else if (method === "Runtime.consoleAPICalled" && p.type === "error")
          problem(route, width, "console.error", p.args.map((a) => a.value ?? a.description ?? "").join(" ").slice(0, 300));
        else if (method === "Log.entryAdded" && p.entry.level === "error" && p.entry.source !== "network" && p.entry.source !== "console-api")
          problem(route, width, `log.${p.entry.source}`, p.entry.text.slice(0, 300));
      }
      const { result } = await send("Runtime.evaluate", { expression: layoutProbe, returnByValue: true });
      for (const [kind, detail] of result.value || []) problem(route, width, kind, detail);
    }
  }
  ws.close();
  if (failures) { console.error(`shot: ${failures} problem(s)`); process.exitCode = 1; }
} catch (e) {
  console.error(`shot: ${e.message}`);
  process.exitCode = 1;
} finally {
  proc.kill();
  await Promise.race([exited, sleep(3000)]);
  rmSync(profile, { recursive: true, force: true });
}
