// Screenshots a page at phone and desktop width through headless Chrome's DevTools protocol.
// Usage: node scripts/shot.mjs /reportes [--base http://localhost:7100] [--out DIR] [--wait MS]
// Start the preview first (npm run dev). Writes <out>/<route>-390.png and -1300.png.
import { spawn } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
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
const port = 9300 + Math.floor(Math.random() * 500);

const proc = spawn(chrome, ["--headless=new", `--remote-debugging-port=${port}`, "--no-first-run", "--hide-scrollbars",
  `--user-data-dir=${mkdtempSync(join(tmpdir(), "agua-chrome-"))}`, "about:blank"], { stdio: "ignore" });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

try {
  let target;
  for (let i = 0; i < 50 && !target; i++) {
    await sleep(100);
    target = await fetch(`http://127.0.0.1:${port}/json/list`).then((r) => r.json()).then((l) => l.find((t) => t.type === "page")).catch(() => null);
  }
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
    await send("Page.navigate", { url: new URL(route, base).href });
    await sleep(wait);
    const { data } = await send("Page.captureScreenshot", { format: "png" });
    const file = join(out, `${name}-${width}.png`);
    writeFileSync(file, Buffer.from(data, "base64"));
    console.log(file);
  }
  ws.close();
} finally {
  proc.kill();
}
