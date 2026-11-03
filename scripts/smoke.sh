#!/usr/bin/env bash
# Serves web/ on a free port and runs shot.mjs --strict over the main pages at 390 and 1300 px.
# Prints SKIP and exits 0 when Chrome isn't installed (set CHROME to its binary).
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
chrome="${CHROME:-/Applications/Google Chrome.app/Contents/MacOS/Google Chrome}"
if [[ ! -x "$chrome" ]]; then
  for c in google-chrome google-chrome-stable chromium chromium-browser; do
    if command -v "$c" >/dev/null; then chrome="$(command -v "$c")"; break; fi
  done
fi
if [[ -n "${CI:-}" && -z "${SMOKE_CI:-}" ]]; then echo "SKIP smoke: CI (set SMOKE_CI=1 to run)"; exit 0; fi
if [[ ! -x "$chrome" ]]; then echo "SKIP smoke: Chrome not found (set CHROME)"; exit 0; fi
export CHROME="$chrome"
port="$(node -e 'const s=require("net").createServer().listen(0,()=>{console.log(s.address().port);s.close()})')"
node scripts/dev-server.mjs --port "$port" --host 127.0.0.1 >/dev/null 2>&1 &
server=$!
trap 'kill $server 2>/dev/null || true' EXIT
for _ in $(seq 50); do curl -fs "http://127.0.0.1:$port/" >/dev/null && break; sleep 0.1; done
node scripts/shot.mjs --strict --base "http://127.0.0.1:$port" --out "${TMPDIR:-/tmp}/agua-smoke" \
  / /reportes /avisos /mapa /exige /noticias /promesas /pipas /simple
