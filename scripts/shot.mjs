// Screenshots a page at phone and desktop width through headless Chrome's DevTools protocol.
// Usage: node scripts/shot.mjs /reportes [--base http://localhost:7100] [--out DIR] [--wait MS]
// Start the preview first (npm run dev). Writes <out>/<route>-390.png and -1300.png.
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const args = process.argv.slice(2);
const value = (name, fallback) => {
  const i = args.indexOf(name);
  return i >= 0 && args[i + 1] ? args[i + 1] : fallback;
};
const route = args.find((a, i) => !a.startsWith("--") && !args[i - 1]?.startsWith("--")) || "/";
const base = value("--base", "http://localhost:7100");
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
  ws.onmessage = (e) => {
    const m = JSON.parse(e.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  };
  const send = (method, params = {}) => new Promise((r, j) => {
    pending.set(++id, (m) => (m.error ? j(new Error(`${method}: ${m.error.message}`)) : r(m.result)));
    ws.send(JSON.stringify({ id, method, params }));
  });
  mkdirSync(out, { recursive: true });
  const name = route.replace(/^\/+/, "").replace(/[^\w.-]+/g, "_") || "index";
  for (const [width, height, mobile] of [[390, 844, true], [1300, 900, false]]) {
    await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: mobile ? 2 : 1, mobile });
    const url = new URL(route, base).href;
    const { errorText } = await send("Page.navigate", { url });
    if (errorText) throw new Error(`${url}: ${errorText}; is the preview running (npm run dev)?`);
    await sleep(wait);
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    const file = join(out, `${name}-${width}.png`);
    writeFileSync(file, Buffer.from(data, "base64"));
    console.log(file);
  }
  ws.close();
} catch (e) {
  console.error(`shot: ${e.message}`);
  process.exitCode = 1;
} finally {
  proc.kill();
  await Promise.race([exited, sleep(3000)]);
  rmSync(profile, { recursive: true, force: true });
}
