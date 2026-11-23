// Phone screenshot of an aguagdl.com page with its Leaflet map (#mapa) dragged, for pages whose map fits
// more than the 1080 CSS px the phone frame shows. Called by build.py --capturas for pages in PANEO.
// Usage: node mapa.mjs URL OUT.png TOP DY   (TOP: CSS px skipped at the top; DY: px to drag the map up, i.e. pan south)
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const [url, out, top, dy] = [process.argv[2], process.argv[3], Number(process.argv[4]), Number(process.argv[5])];
const chrome = process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const profile = mkdtempSync(join(tmpdir(), "carrusel-chrome-"));
const proc = spawn(chrome, ["--headless=new", "--remote-debugging-port=0", "--no-first-run", "--hide-scrollbars",
  `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore" });
const exited = new Promise((r) => { proc.once("exit", r); proc.once("error", r); });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

try {
  let target;
  for (let i = 0; i < 50 && !target; i++) {
    await sleep(100);
    const port = existsSync(join(profile, "DevToolsActivePort")) && readFileSync(join(profile, "DevToolsActivePort"), "utf8").split("\n")[0];
    if (port) target = await fetch(`http://127.0.0.1:${port}/json/list`).then((r) => r.json()).then((l) => l.find((t) => t.type === "page")).catch(() => null);
  }
  if (!target) throw new Error("Chrome did not start");
  const ws = new WebSocket(target.webSocketDebuggerUrl);
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });
  let id = 0;
  const pending = new Map();
  ws.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); } };
  const send = (method, params = {}) => new Promise((r, j) => {
    pending.set(++id, (m) => (m.error ? j(new Error(`${method}: ${m.error.message}`)) : r(m.result)));
    ws.send(JSON.stringify({ id, method, params }));
  });
  const height = 1080 + top;
  await send("Emulation.setDeviceMetricsOverride", { width: 500, height, deviceScaleFactor: 2, mobile: false });
  await send("Page.navigate", { url });
  await sleep(8000);
  const { result } = await send("Runtime.evaluate", { returnByValue: true, expression:
    `(() => { const r = document.getElementById("mapa").getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; })()` });
  const [x0, y0, w, h] = result.value;
  // Grab near the map's bottom (inside the viewport) and drag up in small steps; pause before letting go so Leaflet adds no inertia.
  const x = x0 + w / 2, y = Math.min(y0 + h, height) - 20;
  if (y - dy < 0) throw new Error(`drag of ${dy} px leaves the viewport (grab at ${y})`);
  await send("Input.dispatchMouseEvent", { type: "mousePressed", x, y, button: "left", buttons: 1, clickCount: 1 });
  for (let i = 1; i <= 20; i++) {
    await send("Input.dispatchMouseEvent", { type: "mouseMoved", x, y: y - (dy * i) / 20, button: "left", buttons: 1 });
    await sleep(15);
  }
  await sleep(300);
  await send("Input.dispatchMouseEvent", { type: "mouseReleased", x, y: y - dy, button: "left", buttons: 0, clickCount: 1 });
  await send("Input.dispatchMouseEvent", { type: "mouseMoved", x: 1, y: 1 }); // move off the map so no tooltip shows
  await send("Runtime.evaluate", { expression: "document.activeElement && document.activeElement.blur()" }); // no focus ring
  await sleep(4000);
  const { data } = await send("Page.captureScreenshot", { format: "png", clip: { x: 0, y: top, width: 500, height: 1080, scale: 1 } });
  writeFileSync(out, Buffer.from(data, "base64"));
  ws.close();
} catch (e) {
  console.error(`mapa.mjs: ${e.message}`);
  process.exitCode = 1;
} finally {
  proc.kill();
  await Promise.race([exited, sleep(3000)]);
  rmSync(profile, { recursive: true, force: true });
}
